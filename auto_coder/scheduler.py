"""Task selection and retry policy."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


RETRYABLE_STATUSES = {
    "agent_failed",
    "no_changes",
    "policy_failed",
    "tests_failed",
    "review_failed",
    "quota_exhausted",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def should_retry(status: str | None) -> bool:
    return (status or "") in RETRYABLE_STATUSES


def select_task(tasks: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, Any] | None:
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
        task_status = task_state.get(task_id, {})
        if task_status.get("status") == "completed":
            continue
        max_total = task.get("max_total_attempts")
        if max_total and int(task_status.get("attempt_count", 0)) >= int(max_total):
            continue
        if task_status.get("status") == "quota_exhausted":
            retry_after = task_status.get("retry_after")
            if retry_after and now_iso() < retry_after:
                continue
        candidates.append(task)
    candidates.sort(key=lambda item: (int(item.get("priority", 100)), item.get("id", "")))
    return candidates[0] if candidates else None
