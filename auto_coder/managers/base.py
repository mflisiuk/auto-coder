"""Base interfaces for manager backends."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ReviewDecision:
    verdict: str
    feedback: str
    blockers: list[str] = field(default_factory=list)
    next_work_order: dict[str, Any] | None = None
    source: str = "manager"


class ManagerBackend(ABC):
    @classmethod
    @abstractmethod
    def name(cls) -> str:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        raise NotImplementedError

    @classmethod
    def probe_live(cls, config: dict[str, Any]) -> str:
        raise NotImplementedError(f"{cls.__name__} does not implement live probing")

    @abstractmethod
    def create_work_order(
        self,
        task: dict[str, Any],
        history: list[dict[str, Any]],
        repo_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def review_attempt(
        self,
        task: dict[str, Any],
        work_order: dict[str, Any],
        attempt_context: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> ReviewDecision:
        raise NotImplementedError

    @abstractmethod
    def load_thread(self, task_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def save_thread(self, task_id: str, thread_state: list[dict[str, Any]]) -> None:
        raise NotImplementedError
