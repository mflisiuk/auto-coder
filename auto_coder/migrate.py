"""Helpers for importing legacy task files."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from auto_coder.planner import Planner


def migrate_legacy_tasks(config: dict[str, Any], source_path: Path) -> list[dict[str, Any]]:
    if not source_path.exists():
        raise RuntimeError(f"Legacy task file not found: {source_path}")
    raw = yaml.safe_load(source_path.read_text(encoding="utf-8")) or {}
    tasks = raw.get("tasks")
    if not isinstance(tasks, list):
        raise RuntimeError("Legacy task file must contain a top-level tasks: list.")
    planner = Planner(config)
    validated = planner._validate_tasks([dict(task) for task in tasks if isinstance(task, dict)])
    config["tasks_local_path"].parent.mkdir(parents=True, exist_ok=True)
    config["tasks_local_path"].write_text(
        yaml.dump({"tasks": validated}, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return validated
