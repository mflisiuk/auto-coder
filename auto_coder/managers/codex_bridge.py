"""Codex manager backend bridge placeholder."""
from __future__ import annotations

import shutil
from typing import Any

from auto_coder.managers.base import ManagerBackend, ReviewDecision


class CodexManagerBridge(ManagerBackend):
    @classmethod
    def name(cls) -> str:
        return "codex"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("codex") is not None

    def create_work_order(self, task: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError("Codex manager bridge is planned but not implemented yet.")

    def review_attempt(self, task: dict[str, Any], attempt_context: dict[str, Any]) -> ReviewDecision:
        raise NotImplementedError("Codex manager bridge is planned but not implemented yet.")

