"""Base interfaces for worker adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class WorkerRunResult:
    worker_name: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    token_usage: int
    quota_exhausted: bool
    metadata: dict[str, Any]


class WorkerAdapter(ABC):
    @classmethod
    @abstractmethod
    def name(cls) -> str:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def is_installed(cls) -> bool:
        raise NotImplementedError

    @abstractmethod
    def run(
        self,
        *,
        prompt: str,
        worktree: Path,
        report_dir: Path,
        model: str | None,
        timeout_minutes: int,
        max_budget_usd: float | None = None,
    ) -> WorkerRunResult:
        raise NotImplementedError

