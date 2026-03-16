"""Generate repo-visible work progress reports from runtime state."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from auto_coder.storage import get_task_runtime, list_attempts_for_task


# ─────────────────────────────────────────────────────── worktree progress (legacy)

def write_work_progress(
    output_path: Path,
    *,
    tasks_path: Path,
    state_db_path: Path,
    task_overrides: dict[str, dict[str, Any]] | None = None,
) -> Path:
    """Write a minimal progress table into the current worktree (committed with the task)."""
    output_path.write_text(
        render_work_progress(
            tasks_path=tasks_path,
            state_db_path=state_db_path,
            task_overrides=task_overrides or {},
        ),
        encoding="utf-8",
    )
    return output_path


def render_work_progress(
    *,
    tasks_path: Path,
    state_db_path: Path,
    task_overrides: dict[str, dict[str, Any]],
) -> str:
    tasks = _load_tasks(tasks_path)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        "# Work Progress",
        "",
        f"_Generated at {generated_at}_",
        "",
        "| Task ID | Task | Short Description | Done? | Completed At | Duration |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for task in tasks:
        task_id = str(task.get("id", ""))
        row = get_task_runtime(state_db_path, task_id)
        payload: dict = {}
        status = "queued"
        updated_at = ""
        if row is not None:
            try:
                payload = json.loads(str(row["payload_json"])) if row["payload_json"] else {}
            except Exception:
                payload = {}
            status = str(row["status"])
            updated_at = str(row["updated_at"] or "")

        override = task_overrides.get(task_id, {})
        status = str(override.get("status") or status or "queued")
        completed = status == "completed"

        first_started_at = str(override.get("first_started_at") or payload.get("first_started_at") or "")
        completed_at = str(
            override.get("completed_at")
            or payload.get("completed_at")
            or (updated_at if completed else "")
        )
        duration_seconds = override.get("duration_seconds", payload.get("elapsed_seconds"))
        if duration_seconds in {None, ""} and completed_at:
            duration_seconds = _fallback_duration_seconds(
                state_db_path,
                task_id=task_id,
                first_started_at=first_started_at,
                completed_at=completed_at,
            )

        lines.append(
            "| {task_id} | {title} | {description} | {done} | {completed_at} | {duration} |".format(
                task_id=_escape_md(task_id),
                title=_escape_md(str(task.get("title", task_id))),
                description=_escape_md(_task_description(task)),
                done="yes" if completed else "no",
                completed_at=_escape_md(_format_timestamp(completed_at)),
                duration=_escape_md(_format_duration(duration_seconds)),
            )
        )

    if len(lines) == 6:
        lines.append("| - | - | No tasks planned yet. | no | - | - |")
    lines.append("")
    return "\n".join(lines)


# ──────────────────────────────────────────────────── project-root PROGRESS.md

_STATUS_EMOJI = {
    "completed": "✅",
    "blocked": "🚫",
    "quarantined": "🚫",
    "abandoned": "🚫",
    "waiting_for_quota": "⏳",
    "waiting_for_retry": "🔁",
    "waiting_for_dependency": "⏸",
    "running": "⚙️",
    "leased": "⚙️",
    "ready": "⏹",
    "queued": "⏹",
    "dry_run": "🧪",
    "baseline_failed": "❌",
    "runner_failed": "❌",
}

_TERMINAL_STATUSES = {"completed", "blocked", "quarantined", "abandoned"}
_ERROR_STATUSES = {"blocked", "quarantined", "abandoned", "baseline_failed", "runner_failed"}


def write_project_progress(
    project_root: Path,
    *,
    tasks_path: Path,
    state_db_path: Path,
) -> Path:
    """Write PROGRESS.md to the project root with full error details.

    This file stays in the repo (not just the worktree) so it is always
    visible on GitHub even after worktrees are cleaned up.
    """
    output_path = project_root / "PROGRESS.md"
    output_path.write_text(
        render_project_progress(tasks_path=tasks_path, state_db_path=state_db_path),
        encoding="utf-8",
    )
    return output_path


def render_project_progress(
    *,
    tasks_path: Path,
    state_db_path: Path,
) -> str:
    tasks = _load_tasks(tasks_path)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    # Compute summary counts from DB
    all_rows = {str(t.get("id", "")): t for t in tasks}
    status_counts: dict[str, int] = {}
    for task in tasks:
        task_id = str(task.get("id", ""))
        row = get_task_runtime(state_db_path, task_id)
        status = str(row["status"]) if row else "queued"
        status_counts[status] = status_counts.get(status, 0) + 1

    total = len(tasks)
    completed = status_counts.get("completed", 0)
    errors = sum(v for k, v in status_counts.items() if k in _ERROR_STATUSES)
    in_progress = sum(v for k, v in status_counts.items() if k in {"running", "leased", "waiting_for_retry", "waiting_for_quota", "waiting_for_dependency"})
    not_started = total - completed - errors - in_progress

    lines = [
        "# PROGRESS",
        "",
        f"_Last updated: {generated_at}_",
        "",
        "## Summary",
        "",
        f"| Total | Done | In progress | Not started | Errors |",
        f"| --- | --- | --- | --- | --- |",
        f"| {total} | {completed} | {in_progress} | {not_started} | {errors} |",
        "",
        "## Tasks",
        "",
        "| Status | Task | Worker | Attempts | Started | Completed / Failed at | Duration | Error |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for task in tasks:
        task_id = str(task.get("id", ""))
        title = str(task.get("title", task_id))

        row = get_task_runtime(state_db_path, task_id)
        payload: dict = {}
        status = "queued"
        if row is not None:
            try:
                payload = json.loads(str(row["payload_json"])) if row["payload_json"] else {}
            except Exception:
                payload = {}
            status = str(row["status"])

        emoji = _STATUS_EMOJI.get(status, "⏹")
        status_display = f"{emoji} {status}"

        attempts = list_attempts_for_task(state_db_path, task_id)
        attempt_count = len(attempts)

        # Worker from last attempt
        worker = "-"
        if attempts:
            worker = str(attempts[-1]["worker_name"] or "-")

        first_started_at = str(payload.get("first_started_at") or "")
        completed_at = str(payload.get("completed_at") or "")
        if not completed_at and status in _TERMINAL_STATUSES:
            completed_at = str(row["updated_at"] or "") if row else ""

        duration_seconds = payload.get("elapsed_seconds")
        if duration_seconds in {None, ""} and completed_at and first_started_at:
            duration_seconds = _fallback_duration_seconds(
                state_db_path,
                task_id=task_id,
                first_started_at=first_started_at,
                completed_at=completed_at,
            )

        # Error summary: collect from last N failed attempts
        error_msg = "-"
        if status in _ERROR_STATUSES or status == "waiting_for_retry":
            note = str(payload.get("note") or "")
            failure_sig = str(payload.get("last_failure_signature") or "")
            if note and note != "Run started.":
                error_msg = _truncate(note, 120)
            elif failure_sig:
                error_msg = _truncate(failure_sig, 120)
        if status == "waiting_for_quota":
            retry_after = str(payload.get("retry_after") or "")
            provider = str(payload.get("provider") or "unknown")
            error_msg = f"quota exhausted on `{provider}`" + (f", retry after {retry_after}" if retry_after else "")

        lines.append(
            "| {status} | **{task_id}**<br>{title} | {worker} | {attempts} | {started} | {finished} | {duration} | {error} |".format(
                status=_escape_md(status_display),
                task_id=_escape_md(task_id),
                title=_escape_md(title),
                worker=_escape_md(worker),
                attempts=str(attempt_count),
                started=_escape_md(_format_timestamp(first_started_at)),
                finished=_escape_md(_format_timestamp(completed_at)),
                duration=_escape_md(_format_duration(duration_seconds)),
                error=_escape_md(error_msg),
            )
        )

    lines.append("")

    # Detailed error section for failed tasks
    error_tasks = []
    for task in tasks:
        task_id = str(task.get("id", ""))
        row = get_task_runtime(state_db_path, task_id)
        if row is None:
            continue
        status = str(row["status"])
        if status not in _ERROR_STATUSES:
            continue
        try:
            payload = json.loads(str(row["payload_json"])) if row["payload_json"] else {}
        except Exception:
            payload = {}
        error_tasks.append((task_id, str(task.get("title", task_id)), status, payload))

    if error_tasks:
        lines += ["", "## Error Details", ""]
        for task_id, title, status, payload in error_tasks:
            lines += [
                f"### `{task_id}` — {title}",
                "",
                f"**Status:** {status}",
            ]
            note = str(payload.get("note") or "")
            if note and note != "Run started.":
                lines.append(f"**Reason:** {note}")
            sig = str(payload.get("last_failure_signature") or "")
            if sig:
                lines.append(f"**Failure signature:** `{sig}`")
            lines.append("")

            # Last 3 failed attempts
            attempts = list_attempts_for_task(state_db_path, task_id)
            failed = [a for a in attempts if str(a["status"]) not in {"started", "approved"}][-3:]
            if failed:
                lines.append("**Last attempts:**")
                for attempt in failed:
                    try:
                        apayload = json.loads(str(attempt["payload_json"])) if attempt["payload_json"] else {}
                    except Exception:
                        apayload = {}
                    anote = str(apayload.get("note") or "")[:200]
                    lines.append(
                        f"- attempt #{attempt['id']}: `{attempt['status']}`"
                        + (f" — {anote}" if anote else "")
                    )
                lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("_Generated by [auto-coder](https://github.com/mflisiuk/auto-coder)_")
    lines.append("")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────── helpers

def _load_tasks(tasks_path: Path) -> list[dict[str, Any]]:
    if not tasks_path.exists():
        return []
    raw = yaml.safe_load(tasks_path.read_text(encoding="utf-8")) or {}
    tasks = raw.get("tasks") or []
    return [dict(task) for task in tasks if isinstance(task, dict)]


def _task_description(task: dict[str, Any]) -> str:
    acceptance = task.get("acceptance_criteria") or []
    if isinstance(acceptance, list) and acceptance:
        return _truncate(str(acceptance[0]), 100)
    prompt = str(task.get("prompt", "")).strip()
    if prompt:
        return _truncate(" ".join(prompt.split()), 100)
    return ""


def _fallback_duration_seconds(
    state_db_path: Path,
    *,
    task_id: str,
    first_started_at: str,
    completed_at: str,
) -> int | None:
    if first_started_at:
        return _elapsed_seconds(first_started_at, completed_at)
    attempts = list_attempts_for_task(state_db_path, task_id)
    if not attempts:
        return None
    started_at = str(attempts[0]["created_at"] or "")
    return _elapsed_seconds(started_at, completed_at)


def _elapsed_seconds(started_at: str, completed_at: str) -> int | None:
    start = _parse_timestamp(started_at)
    end = _parse_timestamp(completed_at)
    if start is None or end is None:
        return None
    delta = int((end - start).total_seconds())
    return max(delta, 0)


def _parse_timestamp(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_timestamp(value: str) -> str:
    dt = _parse_timestamp(value)
    if dt is None:
        return "-"
    return dt.replace(microsecond=0).isoformat()


def _format_duration(value: Any) -> str:
    if value in {None, ""}:
        return "-"
    try:
        total = int(value)
    except (TypeError, ValueError):
        return "-"
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip() or "-"
