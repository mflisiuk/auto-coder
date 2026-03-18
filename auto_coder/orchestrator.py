"""Main execution loop: run_batch → run_one_task → worker → manager → commit."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from auto_coder.managers.anthropic import AnthropicManagerBackend
from auto_coder.managers.base import ReviewDecision
from auto_coder.managers.cc_bridge import CcManagerBridge
from auto_coder.managers.codex_bridge import CodexManagerBridge
from auto_coder.config import SUPPORTED_WORKERS
from auto_coder.prompts.worker_instruction import build_worker_prompt
from auto_coder.progress import write_project_progress, write_work_progress
from auto_coder.reviewer import review_attempt
from auto_coder.router import ProviderRouter
from auto_coder.storage import (
    acquire_lease,
    create_run_tick,
    export_state,
    get_task_runtime,
    latest_work_order_for_task,
    list_attempts_for_task,
    list_work_orders_for_task,
    list_task_specs,
    record_attempt,
    recover_interrupted_runs,
    release_lease,
    set_task_runtime,
    update_lease_heartbeat,
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


def _reset_tracked_changes(repo: Path) -> None:
    probe = _git(repo, "rev-parse", "--is-inside-work-tree")
    if probe.returncode != 0:
        return
    result = _git(repo, "reset", "--hard", "HEAD")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git reset --hard HEAD failed")


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


def _hash_signature(prefix: str, parts: list[str]) -> str:
    raw = " | ".join(part.strip() for part in parts if part and part.strip())
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}:{digest}"


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


def _extract_test_identifiers(text: str) -> list[str]:
    seen: set[str] = set()
    identifiers: list[str] = []
    for match in re.findall(r"([A-Za-z0-9_\\\\]+::[A-Za-z0-9_]+)", text):
        if match in seen:
            continue
        seen.add(match)
        identifiers.append(match)
    return identifiers


def _summarize_test_failures(report_dir: Path, prefix: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    commands: list[str] = []
    identifiers: list[str] = []
    excerpts: list[str] = []

    for result in results:
        if result.get("passed"):
            continue
        commands.append(str(result.get("command", "")))
        index = int(result.get("index", 0))
        stdout = _read(report_dir / prefix / f"test-{index:02d}.stdout.log")
        stderr = _read(report_dir / prefix / f"test-{index:02d}.stderr.log")
        combined = "\n".join(part for part in (stdout, stderr) if part)
        for identifier in _extract_test_identifiers(combined):
            if identifier not in identifiers:
                identifiers.append(identifier)
        interesting_lines = []
        for line in combined.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if "::" in stripped or "FAIL" in stripped or "ERROR" in stripped or "Exception" in stripped:
                interesting_lines.append(stripped)
            if len(interesting_lines) >= 4:
                break
        if not interesting_lines and combined.strip():
            interesting_lines.append(combined.strip().splitlines()[-1][:180])
        excerpts.extend(interesting_lines[:4])

    note_parts: list[str] = []
    if commands:
        note_parts.append(f"commands={', '.join(commands[:2])}")
    if identifiers:
        note_parts.append(f"failures={', '.join(identifiers[:3])}")
    if excerpts:
        note_parts.append(f"excerpt={excerpts[0][:120]}")
    note = "; ".join(note_parts) or "baseline test failure"
    signature = _hash_signature("baseline_failed", commands + identifiers + excerpts[:3])
    return {
        "commands": commands,
        "identifiers": identifiers,
        "excerpts": excerpts[:6],
        "note": note,
        "signature": signature,
    }


def _repair_task_id(task_id: str) -> str:
    return f"repair-baseline::{task_id}"


def _environment_repair_task_id(issue_slug: str) -> str:
    return f"repair-environment::{issue_slug}"


def _is_repair_task(task_id: str) -> bool:
    return task_id.startswith("repair-baseline::")


def _is_environment_repair_task(task_id: str) -> bool:
    return task_id.startswith("repair-environment::")


def _is_any_repair_task(task_id: str) -> bool:
    return _is_repair_task(task_id) or _is_environment_repair_task(task_id)


def _environment_allowed_paths(task: dict[str, Any]) -> list[str]:
    allowed: list[str] = [".auto-coder/", "scripts/", "bin/"]
    allowed.extend(str(path) for path in task.get("allowed_paths", []))
    return list(dict.fromkeys(path for path in allowed if path))


def _classify_environment_failure(task: dict[str, Any], failure_summary: dict[str, Any]) -> dict[str, Any] | None:
    corpus = "\n".join(
        [*(str(command) for command in failure_summary.get("commands", [])), *(str(item) for item in failure_summary.get("excerpts", []))]
    )
    command_not_found = re.search(r"(?:^|[\s:])([A-Za-z0-9._+-]+): command not found", corpus)
    if command_not_found:
        missing_command = command_not_found.group(1).lower()
        slug = f"missing-command-{re.sub(r'[^a-z0-9]+', '-', missing_command).strip('-')}"
        return {
            "issue_kind": "missing_command",
            "issue_slug": slug,
            "missing_command": missing_command,
            "title": f"Repair environment: missing `{missing_command}` command",
            "description": (
                f"The execution environment is missing the `{missing_command}` command. "
                "Fix the environment contract once so tasks stop failing on the same missing binary."
            ),
            "note": f"Environment missing command `{missing_command}`.",
            "prompt": (
                f"Fix the shared environment issue: `{missing_command}` command not found.\n"
                "Prefer fixing task/config/tooling contracts in-repo so future tasks run in fresh worktrees.\n"
                "Examples: replace `python` with `python3` in task commands, or add a safe compatibility shim.\n"
                f"Representative failing commands: {', '.join(failure_summary.get('commands', [])[:3]) or 'unknown'}"
            ),
        }
    return None


def _queue_environment_repair_task(
    config: dict[str, Any],
    task: dict[str, Any],
    *,
    task_id: str,
    failure_summary: dict[str, Any],
    parent_run_id: str,
) -> str | None:
    if not config.get("state_db_path") or not config.get("auto_create_environment_repair_tasks", True):
        return None
    if _is_environment_repair_task(task_id):
        return None
    env_issue = _classify_environment_failure(task, failure_summary)
    if not env_issue:
        return None

    repair_task_id = _environment_repair_task_id(str(env_issue["issue_slug"]))
    existing = get_task_runtime(config["state_db_path"], repair_task_id)
    if existing is not None:
        status = str(existing["status"])
        if status not in {"quarantined", "blocked", "abandoned"}:
            return repair_task_id
        try:
            payload = json.loads(str(existing["payload_json"])) if existing["payload_json"] else {}
        except Exception:
            payload = {}
        set_task_runtime(
            config["state_db_path"],
            task_id=repair_task_id,
            title=str(existing["title"]),
            priority=int(existing.get("priority", 0)),
            status="ready",
            payload=payload,
        )
        return repair_task_id

    # Normalize commands for repair task baseline: python -> python3
    def _normalize_python_command(cmd: str) -> str:
        """Replace bare 'python -m' with 'python3 -m' for better compatibility."""
        cmd_str = str(cmd).strip()
        # Only replace 'python -m' at start or after a separator (not 'python3 -m', 'other-python -m', etc.)
        import re as _re
        return _re.sub(r'(^|\s)python\s+-m', r'\1python3 -m', cmd_str)

    raw_commands = list(failure_summary.get("commands", []))
    normalized_commands = [_normalize_python_command(c) for c in raw_commands]

    repair_task = {
        "id": repair_task_id,
        "title": str(env_issue["title"]),
        "description": str(env_issue["description"]),
        "priority": 0,
        "enabled": True,
        "depends_on": [],
        "allowed_paths": _environment_allowed_paths(task),
        "protected_paths": list(task.get("protected_paths", [])),
        "setup_commands": [],
        "baseline_commands": normalized_commands,
        "completion_commands": normalized_commands,
        "acceptance_criteria": [
            f"Representative environment command succeeds: {', '.join(normalized_commands[:2]) or 'unknown'}",
            f"Shared environment issue `{env_issue['issue_slug']}` is resolved.",
        ],
        "preferred_workers": list(task.get("preferred_workers", [])),
        "risk_level": "normal",
        "max_attempts_total": max(2, int(task.get("max_attempts_total", 6))),
        "cooldown_minutes": int(task.get("cooldown_minutes", 60)),
        "estimated_effort": "small",
        "allow_no_changes": True,
        "report_only": False,
        "auto_generated": True,
        "repair_kind": "environment",
        "repair_issue_kind": str(env_issue["issue_kind"]),
        "repair_issue_slug": str(env_issue["issue_slug"]),
        "repair_source_run_id": parent_run_id,
        "repair_failure_signature": str(failure_summary.get("signature", "")),
        "repair_failure_commands": list(failure_summary.get("commands", [])),
        "repair_failure_excerpts": list(failure_summary.get("excerpts", [])),
        "prompt": str(env_issue["prompt"]),
    }
    set_task_runtime(
        config["state_db_path"],
        task_id=repair_task_id,
        title=str(repair_task["title"]),
        priority=int(repair_task["priority"]),
        status="ready",
        payload=repair_task,
    )
    return repair_task_id


def _queue_baseline_repair_task(
    config: dict[str, Any],
    task: dict[str, Any],
    *,
    task_id: str,
    failure_summary: dict[str, Any],
    parent_run_id: str,
) -> str | None:
    if not config.get("state_db_path") or not config.get("auto_create_baseline_repair_tasks", True):
        return None
    if _is_any_repair_task(task_id):
        return None

    repair_task_id = _repair_task_id(task_id)
    existing = get_task_runtime(config["state_db_path"], repair_task_id)
    if existing is not None and str(existing["status"]) not in {"completed", "quarantined", "blocked", "abandoned"}:
        return repair_task_id

    base_dependencies = list(task.get("depends_on", [])) + list(task.get("runtime_depends_on", []))

    # Normalize commands: python -> python3 (same as environment repair)
    def _normalize_python_command(cmd: str) -> str:
        cmd_str = str(cmd).strip()
        import re as _re
        return _re.sub(r'(^|\s)python\s+-m', r'\1python3 -m', cmd_str)

    raw_baseline = list(_baseline_commands(task))
    normalized_baseline = [_normalize_python_command(c) for c in raw_baseline]

    repair_task = {
        "id": repair_task_id,
        "title": f"Repair baseline for {task.get('title', task_id)}",
        "description": (
            "Automatically generated unblocker task. Fix the failing baseline and do not implement "
            "the parent feature beyond what is required to make baseline commands pass."
        ),
        "priority": max(int(task.get("priority", 100)) - 1, 0),
        "enabled": True,
        "depends_on": base_dependencies,
        "allowed_paths": list(task.get("allowed_paths", [])),
        "protected_paths": list(task.get("protected_paths", [])),
        "setup_commands": [],
        "baseline_commands": normalized_baseline,
        "completion_commands": normalized_baseline,
        "acceptance_criteria": [
            "Baseline commands pass in a fresh worktree.",
            f"Unblocks parent task {task_id}.",
        ],
        "preferred_workers": list(task.get("preferred_workers", [])),
        "risk_level": str(task.get("risk_level", "normal")),
        "max_attempts_total": max(2, int(task.get("max_attempts_total", 6))),
        "cooldown_minutes": int(task.get("cooldown_minutes", 60)),
        "estimated_effort": "small",
        "allow_no_changes": True,
        "report_only": False,
        "auto_generated": True,
        "repair_kind": "baseline",
        "repair_target_task_id": task_id,
        "repair_source_run_id": parent_run_id,
        "repair_failure_signature": str(failure_summary.get("signature", "")),
        "repair_failure_identifiers": list(failure_summary.get("identifiers", [])),
        "repair_failure_commands": list(failure_summary.get("commands", [])),
        "repair_failure_excerpts": list(failure_summary.get("excerpts", [])),
        "prompt": (
            f"Repair the failing baseline for parent task `{task_id}`.\n"
            f"Failure signature: {failure_summary.get('signature', '')}\n"
            f"Failing tests: {', '.join(failure_summary.get('identifiers', [])[:5]) or 'unknown'}\n"
            f"Failing commands: {', '.join(failure_summary.get('commands', [])[:2]) or 'unknown'}\n"
            "Goal: make baseline commands pass in a fresh worktree. Do not implement unrelated feature work."
        ),
    }
    set_task_runtime(
        config["state_db_path"],
        task_id=repair_task_id,
        title=str(repair_task["title"]),
        priority=int(repair_task["priority"]),
        status="ready",
        payload=repair_task,
    )
    return repair_task_id


def _queue_repair_task(
    config: dict[str, Any],
    task: dict[str, Any],
    *,
    task_id: str,
    failure_summary: dict[str, Any],
    parent_run_id: str,
) -> tuple[str | None, str]:
    environment_task_id = _queue_environment_repair_task(
        config,
        task,
        task_id=task_id,
        failure_summary=failure_summary,
        parent_run_id=parent_run_id,
    )
    if environment_task_id:
        return environment_task_id, "environment"
    baseline_task_id = _queue_baseline_repair_task(
        config,
        task,
        task_id=task_id,
        failure_summary=failure_summary,
        parent_run_id=parent_run_id,
    )
    if baseline_task_id:
        return baseline_task_id, "baseline"
    return None, "none"


def _updated_runtime_dependencies(task: dict[str, Any], repair_task_id: str, repair_kind: str) -> list[str]:
    dependencies = [str(item) for item in task.get("runtime_depends_on", []) if str(item).strip()]
    filtered = [item for item in dependencies if not _is_any_repair_task(item)]
    return list(dict.fromkeys(filtered + [repair_task_id]))


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
from auto_coder.policy import validate_baseline_spec, validate_changed_files as _validate_changed_files_impl
from auto_coder.policy import validate_pytest_k_syntax, fix_pytest_k_syntax
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


def _setup_commands(config: dict[str, Any], task: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()
    for source in (config.get("setup_commands", []), task.get("setup_commands", [])):
        for item in source or []:
            command = str(item).strip()
            if not command or command in seen:
                continue
            seen.add(command)
            commands.append(command)
    return commands


def _completion_commands(task: dict[str, Any], work_order: dict[str, Any]) -> list[str]:
    return list(work_order.get("completion_commands") or task.get("completion_commands", task.get("test_commands", [])))


def _task_contract_signature(task: dict[str, Any]) -> str:
    payload = {
        "id": str(task.get("id", "")),
        "title": str(task.get("title", "")),
        "prompt": str(task.get("prompt", "")),
        "allowed_paths": list(task.get("allowed_paths", [])),
        "protected_paths": list(task.get("protected_paths", [])),
        "setup_commands": list(task.get("setup_commands", [])),
        "baseline_commands": list(task.get("baseline_commands", task.get("test_commands", []))),
        "completion_commands": list(task.get("completion_commands", task.get("test_commands", []))),
        "preferred_workers": list(task.get("preferred_workers", [])),
        "allow_no_changes": bool(task.get("allow_no_changes", False)),
        "report_only": bool(task.get("report_only", False)),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


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

    # Support manager fallback: codex -> anthropic
    backend_name = str(config.get("manager_backend", "anthropic")).strip().lower()
    fallback_name = str(config.get("manager_fallback", "anthropic")).strip().lower()

    backends = {
        "anthropic": AnthropicManagerBackend,
        "codex": CodexManagerBridge,
        "cc": CcManagerBridge,
        "claude": CcManagerBridge,
    }

    # Try primary backend
    backend_cls = backends.get(backend_name)
    if backend_cls is None:
        raise RuntimeError(f"Unsupported manager backend: {backend_name}")

    if backend_cls.is_available():
        return backend_cls(task_id=str(task["id"]), task=task, config=config, state_path=config["state_path"])

    # Try fallback backend
    fallback_cls = backends.get(fallback_name)
    if fallback_cls is None:
        raise RuntimeError(f"Unsupported manager fallback: {fallback_name}")

    if fallback_cls.is_available():
        return fallback_cls(task_id=str(task["id"]), task=task, config=config, state_path=config["state_path"])

    raise RuntimeError(f"Manager backends unavailable: {backend_name} (primary), {fallback_name} (fallback)")


def _recover_runtime(config: dict[str, Any], state: dict[str, Any]) -> dict[str, list[str]]:
    if not config.get("state_db_path"):
        return {"run_tick_ids": [], "task_ids": [], "work_order_ids": []}
    recovered = recover_interrupted_runs(config["state_db_path"])
    for task_id in recovered.get("task_ids", []):
        state.setdefault("tasks", {}).setdefault(task_id, {})
        state["tasks"][task_id]["status"] = "waiting_for_retry"
        state["tasks"][task_id]["note"] = "Recovered from interrupted run."
    # Unblock parents stuck in waiting_for_dependency whose repair dep is quarantined/blocked.
    # This happens cross-run when a repair task failed terminally in a previous batch.
    for task_id, task_state in list(state.get("tasks", {}).items()):
        if task_state.get("status") != "waiting_for_dependency":
            continue
        for dep_id in task_state.get("runtime_depends_on", []):
            dep_state = state.get("tasks", {}).get(dep_id, {})
            if dep_state.get("status") not in {"quarantined", "blocked", "abandoned"}:
                continue
            dep_row = get_task_runtime(config["state_db_path"], dep_id)
            if dep_row is None:
                continue
            try:
                payload = json.loads(str(dep_row["payload_json"])) if dep_row["payload_json"] else {}
            except Exception:
                payload = {}
            set_task_runtime(
                config["state_db_path"],
                task_id=dep_id,
                title=str(dep_row["title"]),
                priority=int(dep_row["priority"]),
                status="ready",
                payload=payload,
            )
            state["tasks"][dep_id] = {**dep_state, "status": "ready"}
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
    work_order["task_contract_signature"] = _task_contract_signature(task)
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
    if str(work_order.get("task_contract_signature", "")) != _task_contract_signature(task):
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
    prev_attempt_count = int(prev.get("attempt_count", 0))
    # Quota exhaustion never counts against attempt limits — it is an external constraint,
    # not a development failure. Other failures increment the counter.
    attempt_count = prev_attempt_count + (0 if config["dry_run"] else 1)
    protected_paths = list(task.get("protected_paths") or []) + list(config.get("protected_paths", []))
    allow_no_changes = bool(task.get("allow_no_changes", False))
    report_only = bool(task.get("report_only", False))
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
    # Always use the union of task-level and work_order-level allowed_paths.
    # A manager work_order can focus on a subset but must never silently
    # block files that the task contract already permits.
    _task_paths = list(task.get("allowed_paths") or config.get("allowed_paths", []))
    _wo_paths = list(work_order.get("allowed_paths") or [])
    allowed_paths = list(dict.fromkeys(_task_paths + _wo_paths))  # union, preserving order
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

        # ── setup ─────────────────────────────────────────────────────────────
        setup_commands = _setup_commands(config, task)
        if setup_commands:
            setup_ok, setup_results = run_tests(
                setup_commands, worktree, report_dir,
                config["test_timeout_minutes"], prefix="setup-tests",
                skip_no_tests=True,
            )
            if not setup_ok:
                failure_summary = _summarize_test_failures(report_dir, "setup-tests", setup_results)
                repair_task_id, repair_kind = _queue_repair_task(
                    config,
                    task,
                    task_id=task_id,
                    failure_summary=failure_summary,
                    parent_run_id=run_id,
                )
                outcome = "baseline_failed"
                task_status = "baseline_failed"
                note = f"Setup commands failed: {failure_summary['note']}"
                extra = {
                    "attempt_count": attempt_count,
                    "baseline_failure_signature": failure_summary["signature"],
                    "baseline_failure_identifiers": failure_summary["identifiers"],
                    "baseline_failure_commands": failure_summary["commands"],
                    "baseline_failure_excerpts": failure_summary["excerpts"],
                }
                if repair_task_id:
                    task_status = "waiting_for_dependency"
                    note = f"{note}. Queued {repair_kind} repair task {repair_task_id}."
                    extra["repair_task_id"] = repair_task_id
                    extra["repair_task_kind"] = repair_kind
                    extra["runtime_depends_on"] = _updated_runtime_dependencies(task, repair_task_id, repair_kind)
                    # Sync in-memory state so select_task sees the reset repair task this tick.
                    if state.get("tasks", {}).get(repair_task_id, {}).get("status") in {"quarantined", "blocked", "abandoned"}:
                        state.setdefault("tasks", {})[repair_task_id] = {
                            **state["tasks"].get(repair_task_id, {}),
                            "status": "ready",
                        }
                elif config.get("auto_quarantine_failures", True):
                    task_status = "quarantined"
                _update_runtime_state(
                    config,
                    state,
                    task,
                    task_id=task_id,
                    run_id=run_id,
                    status=task_status,
                    task_status=task_status,
                    attempt_status="baseline_failed",
                    branch=branch,
                    report_dir=report_dir,
                    note=note,
                    extra=extra,
                    work_order_id=work_order_id,
                    work_order_status="cancelled",
                )
                _save_json(
                    report_dir / "run.json",
                    {
                        "run_id": run_id,
                        "status": task_status,
                        "work_order_id": work_order_id,
                        "setup_tests": setup_results,
                        "failure_summary": failure_summary,
                        "repair_task_id": repair_task_id,
                        "repair_task_kind": repair_kind,
                    },
                )
                return 1

        # ── baseline ──────────────────────────────────────────────────────────
        baseline_commands = _baseline_commands(task)
        for warning in validate_baseline_spec(task, project_root):
            print(f"[task-spec WARNING] {warning}")
        # Validate and auto-fix pytest -k syntax (| -> or, & -> and)
        k_warnings = validate_pytest_k_syntax(baseline_commands)
        for warning in k_warnings:
            print(f"[pytest-k WARNING] {warning}")
            print(f"[pytest-k AUTO-FIX] Applying automatic correction...")
        if k_warnings:
            baseline_commands = fix_pytest_k_syntax(baseline_commands)
            # Also fix in task dict so repair task gets correct commands
            if "baseline_commands" in task:
                task["baseline_commands"] = baseline_commands
            elif "test_commands" in task:
                task["test_commands"] = baseline_commands
        baseline_ok, baseline_results = run_tests(
            baseline_commands, worktree, report_dir,
            config["test_timeout_minutes"], prefix="baseline-tests",
            skip_no_tests=True,
        )
        if not baseline_ok:
            failure_summary = _summarize_test_failures(report_dir, "baseline-tests", baseline_results)
            repair_task_id, repair_kind = _queue_repair_task(
                config,
                task,
                task_id=task_id,
                failure_summary=failure_summary,
                parent_run_id=run_id,
            )
            outcome = "baseline_failed"
            task_status = "baseline_failed"
            note = f"Baseline tests failed: {failure_summary['note']}"
            extra = {
                "attempt_count": attempt_count,
                "baseline_failure_signature": failure_summary["signature"],
                "baseline_failure_identifiers": failure_summary["identifiers"],
                "baseline_failure_commands": failure_summary["commands"],
                "baseline_failure_excerpts": failure_summary["excerpts"],
            }
            if repair_task_id:
                task_status = "waiting_for_dependency"
                note = f"{note}. Queued {repair_kind} repair task {repair_task_id}."
                extra["repair_task_id"] = repair_task_id
                extra["repair_task_kind"] = repair_kind
                extra["runtime_depends_on"] = _updated_runtime_dependencies(task, repair_task_id, repair_kind)
                # Sync in-memory state so select_task sees the reset repair task this tick.
                if state.get("tasks", {}).get(repair_task_id, {}).get("status") in {"quarantined", "blocked", "abandoned"}:
                    state.setdefault("tasks", {})[repair_task_id] = {
                        **state["tasks"].get(repair_task_id, {}),
                        "status": "ready",
                    }
            elif config.get("auto_quarantine_failures", True):
                task_status = "quarantined"
            _update_runtime_state(
                config,
                state,
                task,
                task_id=task_id,
                run_id=run_id,
                status=task_status,
                task_status=task_status,
                attempt_status="baseline_failed",
                branch=branch,
                report_dir=report_dir,
                note=note,
                extra=extra,
                work_order_id=work_order_id,
                work_order_status="cancelled",
            )
            _save_json(
                report_dir / "run.json",
                {
                    "run_id": run_id,
                    "status": task_status,
                    "work_order_id": work_order_id,
                    "baseline_tests": baseline_results,
                    "failure_summary": failure_summary,
                    "repair_task_id": repair_task_id,
                    "repair_task_kind": repair_kind,
                },
            )
            return 1
        _reset_tracked_changes(worktree)

        # ── worker ────────────────────────────────────────────────────────────
        preferred = work_order.get("selected_worker") or task.get("preferred_provider") or config.get("default_worker", "cc")
        provider = "system" if report_only else router.pick(preferred, estimated_tokens=task.get("estimated_tokens"))
        if report_only:
            worker_result = SimpleNamespace(
                worker_name="system",
                command=["system:report-only"],
                returncode=0,
                stdout="",
                stderr="",
                token_usage=0,
                quota_exhausted=False,
                metadata={"report_only": True},
            )
            _save_json(
                worktree / "AGENT_REPORT.json",
                {
                    "status": "completed",
                    "summary": "Report-only task completed from deterministic checks.",
                    "completed": [
                        "Ran baseline commands",
                        "Skipped coding worker for report-only task",
                        "Prepared deterministic AGENT_REPORT",
                    ],
                    "issues": [],
                    "next": "Proceed to the next task.",
                },
            )
        else:
            worker_adapter = build_worker_adapter(provider)

            # Heartbeat thread: keeps the lease alive for long-running workers by
            # updating heartbeat_at every N seconds so expire_stale_leases does not
            # kill the lease before the worker is done.
            _heartbeat_stop = threading.Event()
            def _heartbeat_loop(stop_event: threading.Event, db_path: object, tid: str) -> None:
                interval = int(config.get("lease_heartbeat_interval_seconds", 30))
                while not stop_event.wait(interval):
                    if db_path and lease_acquired:
                        try:
                            update_lease_heartbeat(db_path, resource_type="task", resource_id=tid)
                        except Exception:
                            pass
            _heartbeat_thread = threading.Thread(
                target=_heartbeat_loop,
                args=(_heartbeat_stop, config.get("state_db_path"), task_id),
                daemon=True,
            )
            _heartbeat_thread.start()
            try:
                worker_result = worker_adapter.run(
                    prompt=prompt,
                    worktree=worktree,
                    report_dir=report_dir,
                    model=task.get("worker_model") or config.get(f"{provider}_model"),
                    max_budget_usd=task.get("worker_budget_usd"),
                    timeout_minutes=config["agent_timeout_minutes"],
                )
            finally:
                _heartbeat_stop.set()

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
                    extra={"attempt_count": prev_attempt_count, "retry_after": retry_after, "provider": provider},
                    worker_name=provider,
                    work_order_id=work_order_id,
                    work_order_status="quota_delayed",
                )
                _save_json(
                    report_dir / "run.json",
                    {"run_id": run_id, "status": "waiting_for_quota", "work_order_id": work_order_id, "retry_after": retry_after},
                )
                return 1

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

        agent_report_path = worktree / "AGENT_REPORT.json"
        agent_report = _load_json(agent_report_path, {})
        if not agent_report_path.exists() or not isinstance(agent_report, dict):
            # Worker returned 0 — synthesize a partial report rather than failing.
            # This handles agents that succeed but forget to write AGENT_REPORT.json.
            agent_report = {
                "status": "partial",
                "summary": "Worker completed without writing AGENT_REPORT.json",
                "completed": [f"Changed {len(changed)} file(s)"] if changed else [],
                "issues": ["AGENT_REPORT.json was not written by the worker"],
                "next": "Review changed files for correctness",
            }
            _save_json(agent_report_path, agent_report)
        _save_json(report_dir / "AGENT_REPORT.json", agent_report)


        if not changed and not allow_no_changes:
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
        if not changed and allow_no_changes:
            decision = ReviewDecision(
                verdict="approve",
                feedback="No source changes required for this task; completion commands passed.",
                blockers=[],
                next_work_order=None,
                source="system:no_changes_allowed",
            )
        else:
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
        # Always push work_progress.md directly to base_branch so it's visible
        # on main without hunting through feature branches.
        if config.get("auto_push"):
            _wp_src = worktree / "work_progress.md"
            _wp_dst = project_root / "work_progress.md"
            if _wp_src.exists():
                import shutil as _shutil
                _shutil.copy2(_wp_src, _wp_dst)
                _git(project_root, "add", "--", "work_progress.md")
                _git(project_root, "commit", "-m", "chore: update work_progress.md [auto-coder]",
                     "--allow-empty")
                _git(project_root, "push", "origin",
                     str(config.get("base_branch", "main")))
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

                # Create a GitHub PR after a successful push.
                pr_url: str | None = None
                if config.get("auto_pr") and shutil.which("gh"):
                    base_branch = str(config.get("base_branch", "main"))
                    pr_title = f"chore(ai): {task.get('title', task_id)} [auto-coder]"
                    pr_body = "\n".join([
                        f"Auto-generated by auto-coder for task `{task_id}`.",
                        "",
                        f"**Work order:** `{work_order_id}`",
                        f"**Worker:** `{provider}`",
                        "",
                        "## Changes",
                        "\n".join(f"- `{f}`" for f in changed_for_commit),
                    ])
                    pr_r = subprocess.run(
                        ["gh", "pr", "create",
                         "--title", pr_title,
                         "--body", pr_body,
                         "--base", base_branch,
                         "--head", branch],
                        cwd=str(worktree),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if pr_r.returncode == 0:
                        pr_url = pr_r.stdout.strip()
                        _save_json(report_dir / "pr.json", {"url": pr_url, "branch": branch})
                        # Auto-merge if configured.
                        if config.get("auto_merge") and pr_url:
                            subprocess.run(
                                ["gh", "pr", "merge", "--squash", "--auto", pr_url],
                                cwd=str(worktree),
                                capture_output=True,
                                text=True,
                                check=False,
                            )
                elif config.get("auto_merge") and not config.get("auto_pr"):
                    # No PR workflow: merge the feature branch directly into base_branch.
                    base_branch = str(config.get("base_branch", "main"))
                    _git(project_root, "fetch", "origin", branch)
                    _git(project_root, "checkout", base_branch)
                    _git(project_root, "merge", "--no-ff", f"origin/{branch}",
                         "-m", f"chore(ai): {task.get('title', task_id)} [auto-coder]")
                    _git(project_root, "push", "origin", base_branch)
                    # Delete the feature branch after successful merge.
                    _git(project_root, "push", "origin", "--delete", branch)
                    _git(project_root, "branch", "-d", branch)

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
        # Always update PROGRESS.md in the project root so GitHub shows current state.
        try:
            if config.get("tasks_path") and config.get("state_db_path"):
                write_project_progress(
                    project_root,
                    tasks_path=config["tasks_path"],
                    state_db_path=config["state_db_path"],
                )
        except Exception:
            pass


def run_batch(config: dict[str, Any], tasks: list[dict], state: dict) -> int:
    loop_mode = config.get("_loop_mode", False)
    max_ticks = int(config.get("_max_ticks", 100))
    exit_code = 0
    with _file_lock(config["lock_path"]):
        _recover_runtime(config, state)
        if loop_mode:
            return _run_loop(config, tasks, state, max_ticks=max_ticks)
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
            if config.get("state_db_path"):
                fresh = list_task_specs(config["state_db_path"])
                existing_ids = {str(t.get("id")) for t in tasks}
                for spec in fresh:
                    if str(spec.get("id")) not in existing_ids:
                        tasks.append(spec)
                state.update(export_state(config["state_db_path"]))
    return exit_code


def _run_loop(config: dict[str, Any], tasks: list[dict], state: dict, *, max_ticks: int) -> int:
    """Run ticks continuously until all tasks are done, blocked, or max_ticks reached.

    Each tick selects one task, executes it, and refreshes state from SQLite so
    dynamically created repair tasks are picked up immediately.
    """
    exit_code = 0
    tick = 0

    while tick < max_ticks:
        # Refresh task list and state from DB to pick up auto-generated repair tasks.
        if config.get("state_db_path"):
            fresh = list_task_specs(config["state_db_path"])
            existing_ids = {str(t.get("id")) for t in tasks}
            for spec in fresh:
                if str(spec.get("id")) not in existing_ids:
                    tasks.append(spec)
            db_state = export_state(config["state_db_path"])
            state.update(db_state)

        task = select_task(tasks, state)
        if not task:
            task_states = state.get("tasks", {})
            completed = sum(1 for t in task_states.values() if t.get("status") == "completed")
            terminal = sum(1 for t in task_states.values() if t.get("status") in {"completed", "blocked", "quarantined", "abandoned"})
            waiting = sum(1 for t in task_states.values() if t.get("status") in {"waiting_for_quota", "waiting_for_retry"})
            total = len(tasks)
            if waiting and terminal < total:
                print(
                    f"[loop] No tasks ready right now — {waiting} task(s) waiting for quota/retry. "
                    f"{completed}/{total} completed. Stopping; re-run after cooldown."
                )
            else:
                print(f"[loop] All tasks done. {completed}/{total} completed, {terminal - completed} in terminal error.")
            break

        tick += 1
        task_id = str(task.get("id", ""))
        print(f"[loop tick={tick}/{max_ticks}] {task_id}")

        task_exit = run_one_task(config, task, state)
        if task_exit != 0:
            exit_code = task_exit

        # Sync state after each tick so the next select_task sees fresh status.
        if config.get("state_db_path"):
            state.update(export_state(config["state_db_path"]))

    if tick >= max_ticks:
        print(f"[loop] Reached max_ticks={max_ticks} — stopping.")

    # Write final PROGRESS.md snapshot.
    try:
        if config.get("tasks_path") and config.get("state_db_path"):
            write_project_progress(
                config["project_root"],
                tasks_path=config["tasks_path"],
                state_db_path=config["state_db_path"],
            )
    except Exception:
        pass

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
