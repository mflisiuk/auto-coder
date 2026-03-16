"""Generate a repo-visible work progress table from runtime state."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from auto_coder.storage import get_task_runtime, list_attempts_for_task


def write_work_progress(
    output_path: Path,
    *,
    tasks_path: Path,
    state_db_path: Path,
    task_overrides: dict[str, dict[str, Any]] | None = None,
) -> Path:
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
        payload = {}
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
