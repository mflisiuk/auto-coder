"""Anthropic-backed manager adapter."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from auto_coder.manager import AttemptResult, ManagerBrain
from auto_coder.managers.base import ManagerBackend, ReviewDecision


class AnthropicManagerBackend(ManagerBackend):
    def __init__(self, *, task_id: str, task: dict[str, Any], config: dict[str, Any], state_path: Path):
        self._brain = ManagerBrain(
            task_id=task_id,
            task=task,
            config=config,
            state_path=state_path,
            model=config.get("manager_model", "claude-opus-4-6"),
        )

    @classmethod
    def name(cls) -> str:
        return "anthropic"

    @classmethod
    def is_available(cls) -> bool:
        return ManagerBrain.is_available()

    def create_work_order(self, task: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
        feedback = self._brain.build_worker_feedback()
        return {
            "task_id": task.get("id"),
            "goal": task.get("prompt", ""),
            "manager_feedback": feedback,
            "history_length": len(history),
        }

    def review_attempt(self, task: dict[str, Any], attempt_context: dict[str, Any]) -> ReviewDecision:
        result = AttemptResult(**attempt_context)
        decision = self._brain.evaluate_attempt(result)
        return ReviewDecision(
            verdict=decision.verdict,
            feedback=decision.feedback,
            blockers=list(decision.blockers),
        )

