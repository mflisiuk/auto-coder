"""Base interfaces for quota probes."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class QuotaSnapshot:
    provider: str
    quota_state: str
    usage_ratio: float | None = None
    retry_after: str | None = None
    source: str = "unknown"
    payload: dict[str, Any] = field(default_factory=dict)


class QuotaProbe(ABC):
    @classmethod
    @abstractmethod
    def provider_name(cls) -> str:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def is_available(cls, config: dict[str, Any]) -> bool:
        raise NotImplementedError

    @abstractmethod
    def check_quota(self, config: dict[str, Any]) -> QuotaSnapshot:
        raise NotImplementedError

    @abstractmethod
    def should_accept_work(self, snapshot: QuotaSnapshot, estimated_tokens: int | None) -> bool:
        raise NotImplementedError

    @abstractmethod
    def retry_after(self, snapshot: QuotaSnapshot) -> str | None:
        raise NotImplementedError
