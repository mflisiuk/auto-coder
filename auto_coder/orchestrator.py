"""Main execution loop: run_batch → run_one_task → worker → manager → commit."""
from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auto_coder.config import find_project_root, load_config
from auto_coder.manager import AttemptResult, ManagerBrain, ManagerDecision
from auto_coder.router import ProviderRouter
from auto_coder.worker import extract_token_usage, is_quota_error, run_worker

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


# ══════════════════════════════════════════════════════════════════ prompt builder

def _build_prompt(
    task: dict,
    allowed_paths: list[str],
    protected_paths: list[str],
    *,
    retry_context: str = "",
) -> str:
    task_prompt = (task.get("prompt") or "").strip()
    retry_block = f"\n\n{retry_context.strip()}\n" if retry_context.strip() else ""
    return f"""You are an autonomous coding agent.

TASK ID: {task.get('id')}
TITLE: {task.get('title')}

GOAL:
{task_prompt}

HARD RULES:
- Work only inside the current git worktree.
- Do not push, merge, deploy, or touch production systems.
- Only modify files under: {', '.join(allowed_paths) or '(none specified)'}.
- Never touch protected paths: {', '.join(protected_paths) or '(none specified)'}.
- Use only standard-library Python for tests (unittest). No pytest.
- Do not add new package dependencies.
- Leave the branch in a testable state.

MANDATORY LAST ACTION:
Before finishing, write a file called AGENT_REPORT.json in the current directory:
{{"status": "completed"|"partial"|"blocked",
  "completed": ["list what you did"],
  "issues": ["list problems encountered"],
  "next": "suggested next step"}}
{retry_block}"""


# ═════════════════════════════════════════════════════════════ extracted modules

from auto_coder.executor import run_tests as _run_tests_impl
from auto_coder.git_ops import changed_files as _changed_files_impl
from auto_coder.git_ops import create_worktree as _create_worktree_impl
from auto_coder.git_ops import git as _git_impl
from auto_coder.git_ops import remove_worktree as _remove_worktree_impl
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
_create_worktree = _create_worktree_impl
validate_changed_files = _validate_changed_files_impl
run_tests = _run_tests_impl
should_retry = _should_retry_impl
select_task = _select_task_impl


# ══════════════════════════════════════════════════════════════════════ core loop

def should_retry(status: str | None) -> bool:
    return (status or "") in RETRYABLE_STATUSES


def select_task(tasks: list[dict], state: dict) -> dict | None:
    task_state = state.get("tasks", {})
    candidates = []
    for task in tasks:
        if not task.get("enabled", True):
            continue
        if task.get("mode", "safe") != "safe":
            continue
        task_id = task.get("id")
        if not task_id:
            continue
        ts = task_state.get(task_id, {})
        if ts.get("status") == "completed":
            continue
        max_total = task.get("max_total_attempts")
        if max_total and int(ts.get("attempt_count", 0)) >= int(max_total):
            continue
        # skip quota_exhausted tasks until retry_after has passed
        if ts.get("status") == "quota_exhausted":
            retry_after = ts.get("retry_after")
            if retry_after and _now() < retry_after:
                continue
        candidates.append(task)
    candidates.sort(key=lambda t: (int(t.get("priority", 100)), t.get("id", "")))
    return candidates[0] if candidates else None


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
    allowed_paths = list(task.get("allowed_paths") or config.get("allowed_paths", []))
    protected_paths = list(config.get("protected_paths", []))

    # manager + router
    router = ProviderRouter(config, config["usage_path"])
    manager: ManagerBrain | None = None
    if config.get("manager_enabled", True) and ManagerBrain.is_available():
        manager = ManagerBrain(
            task_id=task_id,
            task=task,
            config=config,
            state_path=config["state_path"],
            model=config.get("manager_model", "claude-opus-4-6"),
        )

    retry_context = manager.build_worker_feedback() if (manager and manager.has_feedback()) else _legacy_retry_context(state, task_id, report_dir)
    prompt = _build_prompt(task, allowed_paths, protected_paths, retry_context=retry_context)
    _write(report_dir / "prompt.txt", prompt)
    if retry_context:
        _write(report_dir / "retry-context.txt", retry_context + "\n")

    _update_state(config["state_path"], state, task_id=task_id, run_id=run_id,
                  status="running", branch=branch, report_dir=report_dir,
                  note="Run started.", extra={"attempt_count": attempt_count})

    try:
        _create_worktree(project_root, worktree, config.get("worktree_base_ref", config["base_branch"]), branch)

        if config.get("dry_run"):
            outcome = "dry_run"
            _update_state(config["state_path"], state, task_id=task_id, run_id=run_id,
                          status="dry_run", branch=branch, report_dir=report_dir,
                          note="Dry run.", extra={"attempt_count": attempt_count})
            return 0

        # ── baseline ──────────────────────────────────────────────────────────
        baseline_ok, baseline_results = run_tests(
            list(task.get("test_commands") or []), worktree, report_dir,
            config["test_timeout_minutes"], prefix="baseline-tests",
        )
        if not baseline_ok:
            outcome = "baseline_failed"
            _update_state(config["state_path"], state, task_id=task_id, run_id=run_id,
                          status="baseline_failed", branch=branch, report_dir=report_dir,
                          note="Baseline tests failed.", extra={"attempt_count": attempt_count})
            _save_json(report_dir / "run.json", {"run_id": run_id, "status": "baseline_failed", "baseline_tests": baseline_results})
            return 1

        # ── worker ────────────────────────────────────────────────────────────
        preferred = task.get("preferred_provider") or config.get("default_worker", "cc")
        provider = router.pick(preferred)
        worker_result = run_worker(
            provider=provider,
            prompt=prompt,
            worktree=worktree,
            report_dir=report_dir,
            model=task.get("worker_model") or config.get(f"{provider}_model"),
            max_budget_usd=task.get("worker_budget_usd"),
            timeout_minutes=config["agent_timeout_minutes"],
        )
        tokens = extract_token_usage(worker_result.stdout)
        if tokens:
            router.record(provider, tokens)

        changed = _changed_files(worktree)
        _save_json(report_dir / "changed-files.json", {"files": changed})

        # quota error?
        if is_quota_error(worker_result.stderr, worker_result.stdout):
            outcome = "quota_exhausted"
            from datetime import timedelta
            retry_after = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
            _update_state(config["state_path"], state, task_id=task_id, run_id=run_id,
                          status="quota_exhausted", branch=branch, report_dir=report_dir,
                          note=f"Quota exhausted on {provider}. Retry after {retry_after}.",
                          extra={"attempt_count": attempt_count, "retry_after": retry_after})
            return 1

        if worker_result.returncode != 0:
            outcome = "agent_failed"
            _update_state(config["state_path"], state, task_id=task_id, run_id=run_id,
                          status="agent_failed", branch=branch, report_dir=report_dir,
                          note="Worker returned non-zero exit.", extra={"attempt_count": attempt_count})
            return 1

        if not changed:
            outcome = "no_changes"
            _update_state(config["state_path"], state, task_id=task_id, run_id=run_id,
                          status="no_changes", branch=branch, report_dir=report_dir,
                          note="No files changed.", extra={"attempt_count": attempt_count})
            return 1

        violations = validate_changed_files(changed, allowed_paths=allowed_paths, protected_paths=protected_paths)
        _save_json(report_dir / "policy.json", {"violations": violations})
        if violations:
            outcome = "policy_failed"
            _update_state(config["state_path"], state, task_id=task_id, run_id=run_id,
                          status="policy_failed", branch=branch, report_dir=report_dir,
                          note="Policy violations.", extra={"attempt_count": attempt_count})
            return 1

        # ── tests + manager ───────────────────────────────────────────────────
        tests_ok, test_results = run_tests(
            list(task.get("test_commands") or []), worktree, report_dir, config["test_timeout_minutes"],
        )
        test_stdout = {r["command"]: _read(report_dir / "tests" / f"test-{r['index']:02d}.stdout.log")[:3000] for r in test_results}
        test_stderr = {r["command"]: _read(report_dir / "tests" / f"test-{r['index']:02d}.stderr.log")[:3000] for r in test_results}

        if manager:
            attempt_result = AttemptResult(
                attempt_no=attempt_count,
                worker_returncode=worker_result.returncode,
                changed_files=changed,
                policy_violations=[],
                test_results=test_results,
                test_stdout=test_stdout,
                test_stderr=test_stderr,
                diff_patch=_git(worktree, "diff").stdout[:6000],
                diff_stat=_git(worktree, "diff", "--stat").stdout,
                worker_stdout_excerpt=worker_result.stdout[:2000],
                quota_error=False,
            )
            decision = manager.evaluate_attempt(attempt_result)
            review = {"verdict": decision.verdict, "summary": decision.feedback,
                      "blockers": decision.blockers, "source": "manager_brain"}
            _save_json(report_dir / "review.json", review)
            if decision.verdict != "approve":
                outcome = "review_failed"
                _update_state(config["state_path"], state, task_id=task_id, run_id=run_id,
                              status="review_failed", branch=branch, report_dir=report_dir,
                              note=decision.feedback, extra={"attempt_count": attempt_count})
                _save_json(report_dir / "run.json", {"run_id": run_id, "status": "review_failed", "review": review})
                return 1
        else:
            if not tests_ok:
                outcome = "tests_failed"
                _update_state(config["state_path"], state, task_id=task_id, run_id=run_id,
                              status="tests_failed", branch=branch, report_dir=report_dir,
                              note="Tests failed.", extra={"attempt_count": attempt_count})
                return 1
            review = {"verdict": "approve", "summary": "No manager — tests passed.", "blockers": []}
            _save_json(report_dir / "review.json", review)

        # ── commit / push ─────────────────────────────────────────────────────
        if config.get("auto_commit"):
            msg = f"chore(ai): {task.get('title', task_id)} [auto-coder]"
            _git(worktree, "add", "--", *changed)
            commit_r = _git(worktree, "commit", "-m", msg)
            if commit_r.returncode != 0:
                outcome = "commit_failed"
                _update_state(config["state_path"], state, task_id=task_id, run_id=run_id,
                              status="commit_failed", branch=branch, report_dir=report_dir,
                              note="Git commit failed.", extra={"attempt_count": attempt_count})
                return 1
            if config.get("auto_push"):
                push_r = _git(worktree, "push", "-u", "origin", branch)
                if push_r.returncode != 0:
                    outcome = "push_failed"
                    _update_state(config["state_path"], state, task_id=task_id, run_id=run_id,
                                  status="push_failed", branch=branch, report_dir=report_dir,
                                  note="Git push failed.", extra={"attempt_count": attempt_count})
                    return 1

        outcome = "completed"
        _update_state(config["state_path"], state, task_id=task_id, run_id=run_id,
                      status="completed", branch=branch, report_dir=report_dir,
                      note="Task completed.", extra={"attempt_count": attempt_count})
        _save_json(report_dir / "run.json", {"run_id": run_id, "status": "completed",
                                              "changed_files": changed, "review": review})
        return 0

    except Exception as exc:
        outcome = "runner_failed"
        _update_state(config["state_path"], state, task_id=task_id, run_id=run_id,
                      status="runner_failed", branch=branch, report_dir=report_dir,
                      note=str(exc), extra={"attempt_count": attempt_count})
        return 1
    finally:
        success = outcome in {"completed", "dry_run"}
        cleanup = config.get("cleanup_worktree_on_success") if success else config.get("cleanup_worktree_on_failure")
        if cleanup and worktree.exists():
            _remove_worktree_impl(project_root, worktree)


def run_batch(config: dict[str, Any], tasks: list[dict], state: dict) -> int:
    exit_code = 0
    with _file_lock(config["lock_path"]):
        max_tasks = max(1, int(config.get("max_tasks_per_run", 1)))
        processed = 0
        while processed < max_tasks:
            task = select_task(tasks, state)
            if not task:
                break
            processed += 1
            max_attempts = max(1, int(config.get("max_attempts_per_task_per_run", 3)))
            for attempt_no in range(1, max_attempts + 1):
                task_exit = run_one_task(config, task, state)
                current_status = state.get("tasks", {}).get(task.get("id"), {}).get("status")
                if task_exit == 0:
                    break
                if attempt_no >= max_attempts or not should_retry(current_status):
                    exit_code = task_exit
                    break
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
