"""Operator-facing helpers for config, task overrides, and schedulers."""
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from auto_coder.planner import Planner
from auto_coder.storage import sync_tasks

CRON_BEGIN = "# BEGIN auto-coder"
CRON_END = "# END auto-coder"


def update_config_yaml(config: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    config_path = config["auto_coder_dir"] / "config.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    raw.update(updates)
    config_path.write_text(
        yaml.dump(raw, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return raw


def install_cron_job(
    config: dict[str, Any],
    *,
    schedule: str,
    with_plan: bool = False,
) -> str:
    project_root = Path(config["project_root"]).resolve()
    commands = []
    if with_plan:
        commands.append(
            f"{schedule} cd {project_root} && /usr/bin/env auto-coder plan >> .auto-coder/cron.log 2>&1"
        )
    commands.append(
        f"{schedule} cd {project_root} && /usr/bin/env auto-coder run --live >> .auto-coder/cron.log 2>&1"
    )
    block = "\n".join([CRON_BEGIN, *commands, CRON_END]) + "\n"

    result = subprocess.run(
        ["crontab", "-l"],
        capture_output=True,
        text=True,
        check=False,
    )
    current = result.stdout if result.returncode == 0 else ""
    pattern = re.compile(
        rf"{re.escape(CRON_BEGIN)}.*?{re.escape(CRON_END)}\n?",
        re.DOTALL,
    )
    if pattern.search(current):
        updated = pattern.sub(block, current)
    else:
        updated = current.rstrip() + ("\n\n" if current.strip() else "") + block

    subprocess.run(
        ["crontab", "-"],
        input=updated,
        text=True,
        check=True,
    )
    return block


def install_systemd_units(
    config: dict[str, Any],
    *,
    interval_minutes: int,
    enable: bool = True,
) -> tuple[Path, Path]:
    project_root = Path(config["project_root"]).resolve()
    unit_name = f"auto-coder-{project_root.name}"
    systemd_root = Path.home() / ".config" / "systemd" / "user"
    systemd_root.mkdir(parents=True, exist_ok=True)

    service_path = systemd_root / f"{unit_name}.service"
    timer_path = systemd_root / f"{unit_name}.timer"

    service_path.write_text(
        "\n".join(
            [
                "[Unit]",
                f"Description=auto-coder tick for {project_root.name}",
                "",
                "[Service]",
                "Type=oneshot",
                f"WorkingDirectory={project_root}",
                "ExecStart=/usr/bin/env auto-coder run --live",
                "",
            ]
        ),
        encoding="utf-8",
    )
    timer_path.write_text(
        "\n".join(
            [
                "[Unit]",
                f"Description=auto-coder timer for {project_root.name}",
                "",
                "[Timer]",
                f"OnUnitActiveSec={interval_minutes}min",
                "OnBootSec=2min",
                "Persistent=true",
                "",
                "[Install]",
                "WantedBy=timers.target",
                "",
            ]
        ),
        encoding="utf-8",
    )

    if enable and subprocess.run(["which", "systemctl"], capture_output=True, text=True, check=False).returncode == 0:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        subprocess.run(["systemctl", "--user", "enable", "--now", f"{unit_name}.timer"], check=False)

    return service_path, timer_path


def apply_go_live_profile(
    config: dict[str, Any],
    *,
    manager_backend: str | None = None,
    default_worker: str | None = None,
) -> dict[str, Any]:
    updates: dict[str, Any] = {
        "dry_run": False,
        "auto_commit": True,
        "auto_push": True,
        "auto_merge": False,
        "review_required": True,
    }
    if manager_backend:
        updates["manager_backend"] = manager_backend
    if default_worker:
        updates["default_worker"] = default_worker
    return update_config_yaml(config, updates)


def apply_task_override(config: dict[str, Any], task_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    planner = Planner(config)
    generated = planner._load_yaml_tasks(config["tasks_generated_path"])
    effective = planner._load_yaml_tasks(config["tasks_path"])
    local = planner._load_yaml_tasks(config["tasks_local_path"])

    effective_by_id = {str(task["id"]): dict(task) for task in effective}
    local_by_id = {str(task["id"]): dict(task) for task in local}
    if task_id not in effective_by_id and task_id not in local_by_id:
        raise RuntimeError(f"Task not found: {task_id}")

    base = dict(effective_by_id.get(task_id) or local_by_id.get(task_id) or {})
    current_local = dict(local_by_id.get(task_id) or {})
    updated = {**base, **current_local, **patch, "id": task_id}
    local_by_id[task_id] = updated
    updated_local = sorted(local_by_id.values(), key=lambda item: (int(item.get("priority", 100)), str(item.get("id", ""))))
    config["tasks_local_path"].parent.mkdir(parents=True, exist_ok=True)
    config["tasks_local_path"].write_text(
        yaml.dump({"tasks": updated_local}, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

    merged = planner._merge_with_local_overrides(generated)
    validated = planner._validate_tasks(merged)
    planner._save_tasks(config["tasks_path"], validated)
    sync_tasks(config["state_db_path"], validated)
    return next(task for task in validated if str(task["id"]) == task_id)


def load_latest_report_dir(config: dict[str, Any]) -> Path | None:
    reports_root = Path(config["reports_root"]) / "runs"
    if not reports_root.exists():
        return None
    directories = sorted((path for path in reports_root.iterdir() if path.is_dir()), key=lambda item: item.stat().st_mtime)
    return directories[-1] if directories else None


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
