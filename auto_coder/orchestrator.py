"""Main execution loop: run_batch → run_one_task → worker → manager → commit."""
from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auto_coder.managers.anthropic import AnthropicManagerBackend
from auto_coder.managers.codex_bridge import CodexManagerBridge
from auto_coder.config import SUPPORTED_WORKERS
from auto_coder.prompts.worker_instruction import build_worker_prompt
from auto_coder.progress import write_work_progress
from auto_coder.reviewer import review_attempt
from auto_coder.router import ProviderRouter
from auto_coder.storage import (
    acquire_lease,
    create_run_tick,
    latest_work_order_for_task,
    list_attempts_for_task,
    list_work_orders_for_task,
    record_attempt,
    recover_interrupted_runs,
    release_lease,
    set_task_runtime,
    upsert_work_order,
    update_run_tick,
)
from auto_coder.workers import build_worker_adapter

RETRYABLE_STATUSES = {"agent_failed", "no_changes", "policy_failed", "tests_failed", "review_failed", "quota_exhausted"}


# ═══════════════════════════════════════════════════════════════════════ helpers

def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-") or "task"


def _ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save_json(path: Path, payload: Any) -> None:
    _ensure(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(path: Path, text: str) -> None:
    _ensure(path.parent)
    path.write_text(text, encoding="utf-8")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


@contextmanager
def _file_lock(path: Path):
    _ensure(path.parent)
    with path.open("w", encoding="utf-8") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"auto-coder already running: {path}") from exc
        fh.write(f"pid={os.getpid()}\nstarted_at={_now()}\n")
        fh.flush()
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


# ══════════════════════════════════════════════════════════════════════ git ops

def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, timeout=120, check=False
    )


def _changed_files(repo: Path) -> list[str]:
    result = _git(repo, "status", "--porcelain")
    files: list[str] = []
    for line in result.stdout.splitlines():
        line = line.rstrip()
        if not line:
            continue
        part = line[3:] if len(line) > 3 else line
        if " -> " in part:
            part = part.split(" -> ", 1)[1]
        files.append(part.strip())
    return sorted(set(files))


def _create_worktree(root: Path, worktree: Path, base_ref: str, branch: str) -> None:
    if worktree.exists():
        shutil.rmtree(worktree)
    r = _git(root, "worktree", "add", "--detach", str(worktree), base_ref)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "git worktree add failed")
    r = _git(worktree, "checkout", "-b", branch)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "git checkout -b failed")


# ════════════════════════════════════════════════════════════════════ validation

def _path_under(path: str, prefixes: list[str]) -> bool:
    norm = path.replace("\\", "/").lstrip("./")
    for prefix in prefixes:
        p = prefix.replace("\\", "/").rstrip("/")
        if norm == p or norm.startswith(p + "/"):
            return True
    return False


def validate_changed_files(
    files: list[str],
    *,
    allowed_paths: list[str],
    protected_paths: list[str],
) -> list[str]:
    violations = []
    for f in files:
        if _path_under(f, protected_paths):
            violations.append(f"protected:{f}")
        elif allowed_paths and not _path_under(f, allowed_paths):
            violations.append(f"outside_allowed:{f}")
    return violations


# ═══════════════════════════════════════════════════════════════════ test runner

def run_tests(
    commands: list[str],
    worktree: Path,
    report_dir: Path,
    timeout_minutes: int,
    *,
    prefix: str = "tests",
) -> tuple[bool, list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    all_passed = True
    _ensure(report_dir / prefix)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(worktree)

    for idx, cmd in enumerate(commands, start=1):
        r = subprocess.run(
            ["bash", "-lc", cmd],
            cwd=str(worktree),
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout_minutes * 60,
            check=False,
        )
        _write(report_dir / prefix / f"test-{idx:02d}.stdout.log", r.stdout)
        _write(report_dir / prefix / f"test-{idx:02d}.stderr.log", r.stderr)
        results.append({"index": idx, "command": cmd, "returncode": r.returncode, "passed": r.returncode == 0})
        if r.returncode != 0:
            all_passed = False

    _save_json(report_dir / f"{prefix}.json", {"passed": all_passed, "results": results})
    return all_passed, results


# ════════════════════════════════════════════════════════════════════ state mgmt

def _update_state(
    state_path: Path,
    state: dict,
    *,
    task_id: str,
    run_id: str,
    status: str,
    branch: str,
    report_dir: Path,
    note: str = "",
    extra: dict | None = None,
) -> None:
    state.setdefault("tasks", {}).setdefault("runs", [])
    current = state["tasks"].get(task_id, {})
    payload = {
        **current,
        "status": status,
        "last_run_id": run_id,
        "branch": branch,
        "report_dir": str(report_dir),
        "updated_at": _now(),
        "note": note,
        **(extra or {}),
    }
    state["tasks"][task_id] = payload
    state.setdefault("runs", []).append(
        {"run_id": run_id, "task_id": task_id, "status": status, "updated_at": _now(), "note": note, **(extra or {})}
    )
    _save_json(state_path, state)


def _failure_signature(status: str, note: str = "") -> str:
    base = f"{status}:{(note or '').strip()}".strip(":")
    return base[:200]


def _elapsed_seconds(started_at: str, ended_at: str) -> int | None:
    try:
        start = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(ended_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return max(int((end - start).total_seconds()), 0)


def _update_runtime_state(
    config: dict[str, Any],
    state: dict[str, Any],
    task: dict[str, Any],
    *,
    task_id: str,
    run_id: str,
    status: str,
    branch: str,
    report_dir: Path,
    note: str = "",
    extra: dict | None = None,
    worker_name: str | None = None,
    task_status: str | None = None,
    attempt_status: str | None = None,
    work_order_id: str | None = None,
    work_order_status: str | None = None,
) -> str:
    prev = state.get("tasks", {}).get(task_id, {})
    payload_extra = dict(extra or {})
    timestamp = _now()
    signature = ""
    task_status = task_status or status
    attempt_status = attempt_status or status
    if task_status == "running" and not prev.get("first_started_at"):
        payload_extra["first_started_at"] = timestamp
    if task_status == "completed":
        payload_extra["completed_at"] = timestamp
        started_at = str(prev.get("first_started_at") or payload_extra.get("first_started_at") or "")
        duration_seconds = _elapsed_seconds(started_at, timestamp) if started_at else None
        if duration_seconds is not None:
            payload_extra["elapsed_seconds"] = duration_seconds
    failure_statuses = {
        "baseline_failed",
        "agent_failed",
        "agent_report_missing",
        "no_changes",
        "policy_failed",
        "tests_failed",
        "review_failed",
        "quota_exhausted",
        "commit_failed",
        "push_failed",
        "runner_failed",
    }
    if attempt_status in failure_statuses:
        signature = _failure_signature(attempt_status, note)
        same_count = 1
        if prev.get("last_failure_signature") == signature:
            same_count = int(prev.get("same_failure_count", 0)) + 1
        payload_extra["last_failure_signature"] = signature
        payload_extra["same_failure_count"] = same_count
        threshold = int(config.get("failure_block_threshold", 3))
        if attempt_status != "quota_exhausted" and same_count >= threshold:
            task_status = "blocked"
            note = f"Repeated failure: {signature}"
    else:
        payload_extra["last_failure_signature"] = ""
        payload_extra["same_failure_count"] = 0

    _update_state(
        config["state_path"],
        state,
        task_id=task_id,
        run_id=run_id,
        status=task_status,
        branch=branch,
        report_dir=report_dir,
        note=note,
        extra=payload_extra,
    )

    if config.get("state_db_path"):
        task_payload = state.get("tasks", {}).get(task_id, {})
        set_task_runtime(
            config["state_db_path"],
            task_id=task_id,
            title=str(task.get("title", task_id)),
            priority=int(task.get("priority", 100)),
            status=task_status,
            payload=task_payload,
        )
        if work_order_id:
            existing_work_order = latest_work_order_for_task(config["state_db_path"], task_id)
            existing_payload: dict[str, Any] = {}
            sequence_no = 1
            if existing_work_order and str(existing_work_order["id"]) == work_order_id:
                try:
                    existing_payload = json.loads(str(existing_work_order["payload_json"]))
                except Exception:
                    existing_payload = {}
                sequence_no = int(existing_work_order["sequence_no"])
            payload = {**existing_payload, **payload_extra}
            upsert_work_order(
                config["state_db_path"],
                work_order_id=work_order_id,
                task_id=task_id,
                status=work_order_status or task_status,
                sequence_no=sequence_no,
                payload=payload,
            )
        update_run_tick(
            config["state_db_path"],
            run_id,
            status=task_status,
            payload={
                "task_id": task_id,
                "branch": branch,
                "report_dir": str(report_dir),
                "work_order_id": work_order_id,
                "note": note,
                **payload_extra,
            },
        )
        if attempt_status != "running":
            record_attempt(
                config["state_db_path"],
                task_id=task_id,
                run_tick_id=run_id,
                status=attempt_status,
                payload={"report_dir": str(report_dir), "note": note, **payload_extra},
                worker_name=worker_name,
                failure_signature=signature or None,
                work_order_id=work_order_id,
            )
    return task_status


# ═════════════════════════════════════════════════════════════ extracted modules

from auto_coder.executor import run_tests as _run_tests_impl
from auto_coder.git_ops import changed_files as _changed_files_impl
from auto_coder.git_ops import cleanup_worktrees as _cleanup_worktrees_impl
from auto_coder.git_ops import create_worktree as _create_worktree_impl
from auto_coder.git_ops import git as _git_impl
from auto_coder.git_ops import remove_worktree as _remove_worktree_impl
from auto_coder.git_ops import resolve_worktree_base_ref as _resolve_worktree_base_ref_impl
from auto_coder.policy import validate_changed_files as _validate_changed_files_impl
from auto_coder.reports import ensure_dir as _ensure_impl
from auto_coder.reports import load_json as _load_json_impl
from auto_coder.reports import read_text as _read_impl
from auto_coder.reports import save_json as _save_json_impl
from auto_coder.reports import write_text as _write_impl
from auto_coder.scheduler import RETRYABLE_STATUSES as _RETRYABLE_STATUSES_IMPL
from auto_coder.scheduler import select_task as _select_task_impl
from auto_coder.scheduler import should_retry as _should_retry_impl

RETRYABLE_STATUSES = _RETRYABLE_STATUSES_IMPL
_ensure = _ensure_impl
_save_json = _save_json_impl
_load_json = _load_json_impl
_write = _write_impl
_read = _read_impl
_git = _git_impl
_changed_files = _changed_files_impl
_cleanup_worktrees = _cleanup_worktrees_impl
_create_worktree = _create_worktree_impl
_resolve_worktree_base_ref = _resolve_worktree_base_ref_impl
validate_changed_files = _validate_changed_files_impl
run_tests = _run_tests_impl
should_retry = _should_retry_impl
select_task = _select_task_impl


# ══════════════════════════════════════════════════════════════════════ core loop

def _baseline_commands(task: dict[str, Any]) -> list[str]:
    return list(task.get("baseline_commands", task.get("test_commands", [])))


def _completion_commands(task: dict[str, Any], work_order: dict[str, Any]) -> list[str]:
    return list(work_order.get("completion_commands") or task.get("completion_commands", task.get("test_commands", [])))


def _load_history_for_task(config: dict[str, Any], task_id: str) -> list[dict[str, Any]]:
    if not config.get("state_db_path"):
        return []
    history: list[dict[str, Any]] = []
    for row in list_work_orders_for_task(config["state_db_path"], task_id):
        try:
            payload = json.loads(str(row["payload_json"]))
        except Exception:
            payload = {}
        history.append(
            {
                "kind": "work_order",
                "id": str(row["id"]),
                "status": str(row["status"]),
                "sequence_no": int(row["sequence_no"]),
                "payload": payload,
            }
        )
    for row in list_attempts_for_task(config["state_db_path"], task_id):
        try:
            payload = json.loads(str(row["payload_json"]))
        except Exception:
            payload = {}
        history.append(
            {
                "kind": "attempt",
                "id": int(row["id"]),
                "status": str(row["status"]),
                "work_order_id": row["work_order_id"],
                "payload": payload,
            }
        )
    return history


def _resolve_manager_backend(config: dict[str, Any], task: dict[str, Any]):
    if not config.get("manager_enabled", True):
        return None
    backend_name = str(config.get("manager_backend", "anthropic")).strip().lower()
    backend_cls = {
        "anthropic": AnthropicManagerBackend,
        "codex": CodexManagerBridge,
    }.get(backend_name)
    if backend_cls is None:
        raise RuntimeError(f"Unsupported manager backend: {backend_name}")
    if not backend_cls.is_available():
        raise RuntimeError(f"Manager backend unavailable: {backend_name}")
    return backend_cls(task_id=str(task["id"]), task=task, config=config, state_path=config["state_path"])


def _recover_runtime(config: dict[str, Any], state: dict[str, Any]) -> dict[str, list[str]]:
    if not config.get("state_db_path"):
        return {"run_tick_ids": [], "task_ids": [], "work_order_ids": []}
    recovered = recover_interrupted_runs(config["state_db_path"])
    for task_id in recovered.get("task_ids", []):
        state.setdefault("tasks", {}).setdefault(task_id, {})
        state["tasks"][task_id]["status"] = "waiting_for_retry"
        state["tasks"][task_id]["note"] = "Recovered from interrupted run."
    cleanup_names = set(recovered.get("run_tick_ids", []))
    _cleanup_worktrees(
        config["project_root"],
        config["worktree_root"],
        remove_names=cleanup_names,
        older_than_days=int(config.get("cleanup_worktree_older_than_days", 7)),
    )
    return recovered


def _prepare_work_order(
    config: dict[str, Any],
    task: dict[str, Any],
    manager_backend: AnthropicManagerBackend | None,
) -> dict[str, Any]:
    task_id = str(task["id"])
    if config.get("state_db_path"):
        existing = latest_work_order_for_task(config["state_db_path"], task_id)
        if existing and str(existing["status"]) in {"queued", "retry_pending", "quota_delayed"}:
            payload = json.loads(str(existing["payload_json"])) if existing["payload_json"] else {}
            payload.setdefault("id", str(existing["id"]))
            payload.setdefault("task_id", task_id)
            payload.setdefault("sequence_no", int(existing["sequence_no"]))
            payload.setdefault("status", str(existing["status"]))
            if _work_order_is_reusable(payload, task):
                return payload
            upsert_work_order(
                config["state_db_path"],
                work_order_id=str(existing["id"]),
                task_id=task_id,
                status="rejected",
                sequence_no=int(existing["sequence_no"]),
                payload={**payload, "rejected_reason": "invalid_cached_work_order"},
            )
    history = _load_history_for_task(config, task_id)
    next_sequence_no = max(
        [int(entry.get("sequence_no", 0)) for entry in history if entry["kind"] == "work_order"],
        default=0,
    ) + 1
    preferred_workers = list(task.get("preferred_workers") or [])
    selected_worker = preferred_workers[0] if preferred_workers else (task.get("preferred_provider") or config.get("default_worker", "cc"))
    work_order = (
        manager_backend.create_work_order(task, history, {"project_root": str(config["project_root"])})
        if manager_backend
        else {
            "id": f"{task_id}-wo-{next_sequence_no:02d}",
            "task_id": task_id,
            "sequence_no": next_sequence_no,
            "goal": task.get("prompt", ""),
            "scope_summary": task.get("title", task_id),
            "allowed_paths": list(task.get("allowed_paths") or config.get("allowed_paths", [])),
            "completion_commands": list(task.get("completion_commands", task.get("test_commands", []))),
            "selected_worker": selected_worker,
            "manager_feedback": "",
            "status": "queued",
            "created_by": "system",
        }
    )
    if config.get("state_db_path"):
        upsert_work_order(
            config["state_db_path"],
            work_order_id=str(work_order["id"]),
            task_id=task_id,
            status=str(work_order.get("status", "queued")),
            sequence_no=int(work_order.get("sequence_no", 1)),
            payload=work_order,
        )
    return work_order


def _work_order_is_reusable(work_order: dict[str, Any], task: dict[str, Any]) -> bool:
    if str(work_order.get("task_id", "")) != str(task.get("id", "")):
        return False
    selected_worker = str(work_order.get("selected_worker", "")).strip()
    if selected_worker not in SUPPORTED_WORKERS:
        return False
    allowed_paths = work_order.get("allowed_paths")
    completion_commands = work_order.get("completion_commands")
    if not isinstance(allowed_paths, list) or not allowed_paths:
        return False
    if not isinstance(completion_commands, list) or not completion_commands:
        return False
    return True


def run_one_task(
    config: dict[str, Any],
    task: dict[str, Any],
    state: dict[str, Any],
) -> int:
    project_root: Path = config["project_root"]
    task_id: str = task["id"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = f"{_slugify(task_id)}-{stamp}"
    branch = f"ai/{_slugify(task_id)}-{stamp}"
    report_dir = _ensure(config["reports_root"] / "runs" / run_id)
    worktree = config["worktree_root"] / run_id
    outcome = "running"

    prev = state.get("tasks", {}).get(task_id, {})
    attempt_count = int(prev.get("attempt_count", 0)) + (0 if config["dry_run"] else 1)
    protected_paths = list(task.get("protected_paths") or []) + list(config.get("protected_paths", []))
    lease_acquired = False
    work_order: dict[str, Any] | None = None
    work_order_id: str | None = None

    if config.get("state_db_path"):
        create_run_tick(
            config["state_db_path"],
            run_id,
            status="started",
            payload={"task_id": task_id, "branch": branch, "report_dir": str(report_dir)},
        )
        from datetime import timedelta

        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=int(config.get("stale_running_timeout_minutes", 120)))).isoformat()
        lease_acquired = acquire_lease(
            config["state_db_path"],
            resource_type="task",
            resource_id=task_id,
            run_tick_id=run_id,
            expires_at=expires_at,
        )
        if not lease_acquired:
            update_run_tick(
                config["state_db_path"],
                run_id,
                status="blocked",
                payload={"task_id": task_id, "note": "Task already leased by another run."},
            )
            return 1

    router = ProviderRouter(config, config["usage_path"])
    manager_backend = _resolve_manager_backend(config, task)
    work_order = _prepare_work_order(config, task, manager_backend)
    work_order_id = str(work_order["id"])
    allowed_paths = list(work_order.get("allowed_paths") or task.get("allowed_paths") or config.get("allowed_paths", []))
    prompt = build_worker_prompt(
        task=task,
        work_order=work_order,
        allowed_paths=allowed_paths,
        protected_paths=protected_paths,
    )
    _write(report_dir / "prompt.txt", prompt)
    if work_order.get("manager_feedback"):
        _write(report_dir / "retry-context.txt", str(work_order["manager_feedback"]).strip() + "\n")

    _update_runtime_state(
        config,
        state,
        task,
        task_id=task_id,
        run_id=run_id,
        status="running",
        task_status="running",
        attempt_status="started",
        branch=branch,
        report_dir=report_dir,
        note="Run started.",
        extra={"attempt_count": attempt_count},
        work_order_id=work_order_id,
        work_order_status="running",
    )

    try:
        base_ref = _resolve_worktree_base_ref(
            project_root,
            config.get("worktree_base_ref"),
            str(config.get("base_branch", "main")),
        )
        _create_worktree(project_root, worktree, base_ref, branch)

        if config.get("dry_run"):
            outcome = "dry_run"
            _update_runtime_state(
                config,
                state,
                task,
                task_id=task_id,
                run_id=run_id,
                status="dry_run",
                branch=branch,
                report_dir=report_dir,
                note="Dry run.",
                extra={"attempt_count": attempt_count},
                work_order_id=work_order_id,
                work_order_status="selected",
            )
            return 0

        # ── baseline ──────────────────────────────────────────────────────────
        baseline_ok, baseline_results = run_tests(
            _baseline_commands(task), worktree, report_dir,
            config["test_timeout_minutes"], prefix="baseline-tests",
        )
        if not baseline_ok:
            failed_commands = [item["command"] for item in baseline_results if not item.get("passed")]
            outcome = "baseline_failed"
            _update_runtime_state(
                config,
                state,
                task,
                task_id=task_id,
                run_id=run_id,
                status="baseline_failed",
                branch=branch,
                report_dir=report_dir,
                note=f"Baseline tests failed: {', '.join(failed_commands[:2]) or 'unknown command'}",
                extra={"attempt_count": attempt_count},
                work_order_id=work_order_id,
                work_order_status="cancelled",
            )
            _save_json(
                report_dir / "run.json",
                {"run_id": run_id, "status": "baseline_failed", "work_order_id": work_order_id, "baseline_tests": baseline_results},
            )
            return 1

        # ── worker ────────────────────────────────────────────────────────────
        preferred = work_order.get("selected_worker") or task.get("preferred_provider") or config.get("default_worker", "cc")
        provider = router.pick(preferred, estimated_tokens=task.get("estimated_tokens"))
        worker_adapter = build_worker_adapter(provider)
        worker_result = worker_adapter.run(
            prompt=prompt,
            worktree=worktree,
            report_dir=report_dir,
            model=task.get("worker_model") or config.get(f"{provider}_model"),
            max_budget_usd=task.get("worker_budget_usd"),
            timeout_minutes=config["agent_timeout_minutes"],
        )
        tokens = worker_result.token_usage
        if tokens:
            router.record(provider, tokens)

        if worker_result.quota_exhausted:
            outcome = "waiting_for_quota"
            snapshot = router.mark_quota_exhausted(provider)
            retry_after = snapshot.retry_after or _now()
            _update_runtime_state(
                config,
                state,
                task,
                task_id=task_id,
                run_id=run_id,
                status="waiting_for_quota",
                task_status="waiting_for_quota",
                attempt_status="quota_exhausted",
                branch=branch,
                report_dir=report_dir,
                note=f"Quota exhausted on {provider}. Retry after {retry_after}.",
                extra={"attempt_count": attempt_count, "retry_after": retry_after, "provider": provider},
                worker_name=provider,
                work_order_id=work_order_id,
                work_order_status="quota_delayed",
            )
            _save_json(
                report_dir / "run.json",
                {"run_id": run_id, "status": "waiting_for_quota", "work_order_id": work_order_id, "retry_after": retry_after},
            )
            return 1

        agent_report_path = worktree / "AGENT_REPORT.json"
        agent_report = _load_json(agent_report_path, {})
        if not agent_report_path.exists() or not isinstance(agent_report, dict):
            outcome = "waiting_for_retry"
            _update_runtime_state(
                config,
                state,
                task,
                task_id=task_id,
                run_id=run_id,
                status="waiting_for_retry",
                task_status="waiting_for_retry",
                attempt_status="agent_report_missing",
                branch=branch,
                report_dir=report_dir,
                note="Worker did not leave a valid AGENT_REPORT.json.",
                extra={"attempt_count": attempt_count, "retry_after": _now()},
                worker_name=provider,
                work_order_id=work_order_id,
                work_order_status="retry_pending",
            )
            return 1
        _save_json(report_dir / "AGENT_REPORT.json", agent_report)

        changed = _changed_files(worktree)
        _save_json(report_dir / "changed-files.json", {"files": changed})

        if worker_result.returncode != 0:
            worker_error = (worker_result.stderr or worker_result.stdout or "").strip().splitlines()
            worker_note = worker_error[-1][:240] if worker_error else "Worker returned non-zero exit."
            outcome = "waiting_for_retry"
            _update_runtime_state(
                config,
                state,
                task,
                task_id=task_id,
                run_id=run_id,
                status="waiting_for_retry",
                task_status="waiting_for_retry",
                attempt_status="agent_failed",
                branch=branch,
                report_dir=report_dir,
                note=worker_note,
                extra={"attempt_count": attempt_count, "retry_after": _now()},
                worker_name=provider,
                work_order_id=work_order_id,
                work_order_status="retry_pending",
            )
            return 1

        if not changed:
            outcome = "waiting_for_retry"
            _update_runtime_state(
                config,
                state,
                task,
                task_id=task_id,
                run_id=run_id,
                status="waiting_for_retry",
                task_status="waiting_for_retry",
                attempt_status="no_changes",
                branch=branch,
                report_dir=report_dir,
                note="No files changed.",
                extra={"attempt_count": attempt_count, "retry_after": _now()},
                worker_name=provider,
                work_order_id=work_order_id,
                work_order_status="retry_pending",
            )
            return 1

        violations = validate_changed_files(changed, allowed_paths=allowed_paths, protected_paths=protected_paths)
        _save_json(report_dir / "policy.json", {"violations": violations})
        if violations:
            outcome = "waiting_for_retry"
            _update_runtime_state(
                config,
                state,
                task,
                task_id=task_id,
                run_id=run_id,
                status="waiting_for_retry",
                task_status="waiting_for_retry",
                attempt_status="policy_failed",
                branch=branch,
                report_dir=report_dir,
                note="Policy violations.",
                extra={"attempt_count": attempt_count, "retry_after": _now()},
                worker_name=provider,
                work_order_id=work_order_id,
                work_order_status="retry_pending",
            )
            return 1

        # ── tests + manager ───────────────────────────────────────────────────
        completion_commands = _completion_commands(task, work_order)
        tests_ok, test_results = run_tests(
            completion_commands, worktree, report_dir, config["test_timeout_minutes"], prefix="completion-tests",
        )
        test_stdout = {
            r["command"]: _read(report_dir / "completion-tests" / f"test-{r['index']:02d}.stdout.log")[:3000]
            for r in test_results
        }
        test_stderr = {
            r["command"]: _read(report_dir / "completion-tests" / f"test-{r['index']:02d}.stderr.log")[:3000]
            for r in test_results
        }

        history = _load_history_for_task(config, task_id)
        attempt_context = {
            "attempt_no": attempt_count,
            "worker_name": provider,
            "worker_returncode": worker_result.returncode,
            "changed_files": changed,
            "policy_violations": violations,
            "test_results": test_results,
            "test_stdout": test_stdout,
            "test_stderr": test_stderr,
            "diff_patch": _git(worktree, "diff").stdout[:6000],
            "diff_stat": _git(worktree, "diff", "--stat").stdout,
            "worker_stdout_excerpt": worker_result.stdout[:2000],
            "quota_error": False,
            "baseline_passed": baseline_ok,
            "worker_report_present": True,
            "completion_passed": tests_ok,
            "agent_report": agent_report,
        }
        decision = review_attempt(
            task=task,
            work_order=work_order,
            attempt_context=attempt_context,
            history=history,
            manager_backend=manager_backend,
            report_dir=report_dir,
        )
        review = {
            "verdict": decision.verdict,
            "summary": decision.feedback,
            "blockers": decision.blockers,
            "source": decision.source,
        }
        if decision.verdict != "approve":
            retry_after = _now()
            next_work_order = decision.next_work_order
            if next_work_order and config.get("state_db_path"):
                upsert_work_order(
                    config["state_db_path"],
                    work_order_id=str(next_work_order["id"]),
                    task_id=task_id,
                    status=str(next_work_order.get("status", "queued")),
                    sequence_no=int(next_work_order.get("sequence_no", 1)),
                    payload=next_work_order,
                )
            if decision.verdict == "abandon":
                outcome = "blocked"
                _update_runtime_state(
                    config,
                    state,
                    task,
                    task_id=task_id,
                    run_id=run_id,
                    status="blocked",
                    task_status="blocked",
                    attempt_status="review_failed",
                    branch=branch,
                    report_dir=report_dir,
                    note=decision.feedback,
                    extra={"attempt_count": attempt_count},
                    worker_name=provider,
                    work_order_id=work_order_id,
                    work_order_status="cancelled",
                )
                _save_json(report_dir / "run.json", {"run_id": run_id, "status": "blocked", "review": review})
                return 1

            attempt_status = "tests_failed" if not tests_ok else "review_failed"
            outcome = "waiting_for_retry"
            _update_runtime_state(
                config,
                state,
                task,
                task_id=task_id,
                run_id=run_id,
                status="waiting_for_retry",
                task_status="waiting_for_retry",
                attempt_status=attempt_status,
                branch=branch,
                report_dir=report_dir,
                note=decision.feedback,
                extra={"attempt_count": attempt_count, "retry_after": retry_after},
                worker_name=provider,
                work_order_id=work_order_id,
                work_order_status="retry_pending",
            )
            _save_json(report_dir / "run.json", {"run_id": run_id, "status": "waiting_for_retry", "review": review})
            return 1

        # ── commit / push ─────────────────────────────────────────────────────
        progress_started_at = str(state.get("tasks", {}).get(task_id, {}).get("first_started_at") or "")
        completion_timestamp = _now()
        progress_duration = _elapsed_seconds(progress_started_at, completion_timestamp) if progress_started_at else None
        write_work_progress(
            worktree / "work_progress.md",
            tasks_path=config["tasks_path"],
            state_db_path=config["state_db_path"],
            task_overrides={
                task_id: {
                    "status": "completed",
                    "first_started_at": progress_started_at,
                    "completed_at": completion_timestamp,
                    "duration_seconds": progress_duration,
                }
            },
        )
        changed_for_commit = sorted(set(changed + ["work_progress.md"]))
        if config.get("auto_commit"):
            msg = f"chore(ai): {task.get('title', task_id)} [auto-coder]"
            _git(worktree, "add", "--", *changed_for_commit)
            commit_r = _git(worktree, "commit", "-m", msg)
            if commit_r.returncode != 0:
                commit_note = (commit_r.stderr or commit_r.stdout or "Git commit failed.").strip().splitlines()
                outcome = "commit_failed"
                _update_runtime_state(
                    config,
                    state,
                    task,
                    task_id=task_id,
                    run_id=run_id,
                    status="commit_failed",
                    branch=branch,
                    report_dir=report_dir,
                    note=commit_note[-1][:240] if commit_note else "Git commit failed.",
                    extra={"attempt_count": attempt_count},
                    worker_name=provider,
                    work_order_id=work_order_id,
                    work_order_status="retry_pending",
                )
                return 1
            if config.get("auto_push"):
                push_r = _git(worktree, "push", "-u", "origin", branch)
                if push_r.returncode != 0:
                    push_note = (push_r.stderr or push_r.stdout or "Git push failed.").strip().splitlines()
                    outcome = "push_failed"
                    _update_runtime_state(
                        config,
                        state,
                        task,
                        task_id=task_id,
                        run_id=run_id,
                        status="push_failed",
                        branch=branch,
                        report_dir=report_dir,
                        note=push_note[-1][:240] if push_note else "Git push failed.",
                        extra={"attempt_count": attempt_count},
                        worker_name=provider,
                        work_order_id=work_order_id,
                        work_order_status="retry_pending",
                    )
                    return 1

        outcome = "completed"
        _update_runtime_state(
            config,
            state,
            task,
            task_id=task_id,
            run_id=run_id,
            status="completed",
            branch=branch,
            report_dir=report_dir,
            note="Task completed.",
            extra={"attempt_count": attempt_count, "agent_report": agent_report},
            worker_name=provider,
            work_order_id=work_order_id,
            work_order_status="completed",
        )
        _save_json(
            report_dir / "run.json",
            {
                "run_id": run_id,
                "status": "completed",
                "work_order_id": work_order_id,
                "changed_files": changed_for_commit,
                "review": review,
                "completed_at": completion_timestamp,
                "duration_seconds": progress_duration,
            },
        )
        return 0

    except Exception as exc:
        outcome = "runner_failed"
        _update_runtime_state(
            config,
            state,
            task,
            task_id=task_id,
            run_id=run_id,
            status="runner_failed",
            branch=branch,
            report_dir=report_dir,
            note=str(exc),
            extra={"attempt_count": attempt_count},
            work_order_id=work_order_id,
            work_order_status="cancelled" if work_order_id else None,
        )
        return 1
    finally:
        success = outcome in {"completed", "dry_run"}
        cleanup = config.get("cleanup_worktree_on_success") if success else config.get("cleanup_worktree_on_failure")
        if cleanup and worktree.exists():
            _remove_worktree_impl(project_root, worktree)
        if config.get("state_db_path") and lease_acquired:
            release_lease(config["state_db_path"], resource_type="task", resource_id=task_id)


def run_batch(config: dict[str, Any], tasks: list[dict], state: dict) -> int:
    exit_code = 0
    with _file_lock(config["lock_path"]):
        _recover_runtime(config, state)
        max_tasks = max(1, int(config.get("max_tasks_per_run", 1)))
        processed = 0
        attempted_ids: set[str] = set()
        while processed < max_tasks:
            available_tasks = [task for task in tasks if str(task.get("id")) not in attempted_ids]
            task = select_task(available_tasks, state)
            if not task:
                break
            processed += 1
            attempted_ids.add(str(task.get("id")))
            task_exit = run_one_task(config, task, state)
            if task_exit != 0:
                exit_code = task_exit
    return exit_code


def _legacy_retry_context(state: dict, task_id: str, report_dir: Path) -> str:
    """Fallback: plain text context when manager is not available."""
    ts = state.get("tasks", {}).get(task_id, {})
    status = ts.get("status")
    if not status or status in {"queued", "completed", "dry_run"}:
        return ""
    review = _load_json(report_dir / "review.json", {})
    lines = [f"PREVIOUS ATTEMPT: status={status}"]
    blockers = review.get("blockers") or []
    if blockers:
        lines += ["Blockers:"] + [f"- {b}" for b in blockers]
    lines.append("Fix these issues. Do not repeat the same failure.")
    return "\n".join(lines)
