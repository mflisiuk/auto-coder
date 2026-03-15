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


class ManagerBackend(ABC):
    @classmethod
    @abstractmethod
    def name(cls) -> str:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        raise NotImplementedError

    @abstractmethod
    def create_work_order(self, task: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def review_attempt(self, task: dict[str, Any], attempt_context: dict[str, Any]) -> ReviewDecision:
        raise NotImplementedError

