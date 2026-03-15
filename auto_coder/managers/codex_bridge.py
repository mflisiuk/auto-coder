"""Codex manager backend bridge placeholder."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from auto_coder.managers.base import ManagerBackend, ReviewDecision
from auto_coder.storage import load_manager_messages, save_manager_messages


class CodexManagerBridge(ManagerBackend):
    def __init__(self, *, task_id: str, task: dict[str, Any], config: dict[str, Any], state_path: Path):
        self.task_id = task_id
        self.task = task
        self.config = config
        self.state_path = state_path
        self.state_db_path: Path | None = config.get("state_db_path")

    @classmethod
    def name(cls) -> str:
        return "codex"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("codex") is not None

    def create_work_order(
        self,
        task: dict[str, Any],
        history: list[dict[str, Any]],
        repo_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError("Codex manager bridge is planned but not implemented yet.")

    def review_attempt(
        self,
        task: dict[str, Any],
        work_order: dict[str, Any],
        attempt_context: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> ReviewDecision:
        raise NotImplementedError("Codex manager bridge is planned but not implemented yet.")

    def load_thread(self, task_id: str) -> list[dict[str, Any]]:
        if task_id != self.task_id:
            return []
        if self.state_db_path and self.state_db_path.exists():
            return load_manager_messages(
                self.state_db_path,
                task_id=self.task_id,
                manager_backend=self.name(),
            )
        if not self.state_path.exists():
            return []
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return list(payload.get("tasks", {}).get(self.task_id, {}).get("manager_messages", []))

    def save_thread(self, task_id: str, thread_state: list[dict[str, Any]]) -> None:
        if task_id != self.task_id:
            return
        if self.state_db_path:
            save_manager_messages(
                self.state_db_path,
                task_id=self.task_id,
                manager_backend=self.name(),
                messages=thread_state,
            )
