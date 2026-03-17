"""Task selection and retry policy."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


RETRYABLE_STATUSES = {
    "agent_failed",
    "agent_report_missing",
    "no_changes",
    "policy_failed",
    "tests_failed",
    "review_failed",
    "quota_exhausted",
    "waiting_for_retry",
    "waiting_for_quota",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def should_retry(status: str | None) -> bool:
    return (status or "") in RETRYABLE_STATUSES


def dependencies_satisfied(task: dict[str, Any], state: dict[str, Any]) -> bool:
    task_state = state.get("tasks", {})
    # Static dependencies: must be completed.
    for dep in task.get("depends_on", []):
        if task_state.get(dep, {}).get("status") != "completed":
            return False
    # Runtime dependencies (auto-generated repair tasks): quarantined or abandoned
    # counts as resolved — the repair gave up, so the parent should proceed.
    for dep in task.get("runtime_depends_on", []):
        status = task_state.get(dep, {}).get("status")
        if status not in {"completed", "quarantined", "abandoned"}:
            return False
    return True


def select_task(tasks: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, Any] | None:
    task_state = state.get("tasks", {})
    candidates = []
    for task in tasks:
        if not task.get("enabled", True):
            continue
        task_id = task.get("id")
        if not task_id:
            continue
        task_status = task_state.get(task_id, {})
        if task_status.get("status") in {"completed", "blocked", "quarantined", "running", "leased"}:
            continue
        if not dependencies_satisfied(task, state):
            continue
        max_total = task.get("max_total_attempts")
        if max_total and int(task_status.get("attempt_count", 0)) >= int(max_total):
            continue
        if task_status.get("status") in {"waiting_for_retry", "waiting_for_quota", "quota_exhausted"}:
            retry_after = task_status.get("retry_after")
            if retry_after and now_iso() < retry_after:
                continue
        candidates.append(task)
    candidates.sort(key=lambda item: (int(item.get("priority", 100)), item.get("id", "")))
    return candidates[0] if candidates else None
