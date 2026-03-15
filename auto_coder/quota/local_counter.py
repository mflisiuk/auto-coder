"""Local quota probe based on usage.json token accounting."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from auto_coder.quota.base import QuotaProbe, QuotaSnapshot


class LocalCounterQuotaProbe(QuotaProbe):
    def __init__(self, provider: str, usage_path: Path):
        self.provider = provider
        self.usage_path = usage_path

    @classmethod
    def provider_name(cls) -> str:
        return "local"

    @classmethod
    def is_available(cls, config: dict[str, Any]) -> bool:
        return True

    def check_quota(self, config: dict[str, Any]) -> QuotaSnapshot:
        usage = _load_usage(self.usage_path)
        bucket = usage.get(self.provider, {})
        provider_cfg = config.get("providers", {}).get(self.provider, {})
        limit = provider_cfg.get("token_limit_daily")
        threshold = float(provider_cfg.get("quota_threshold", 1.0))
        retry_after = bucket.get("retry_after")
        if retry_after and datetime.now(timezone.utc).isoformat() < retry_after:
            return QuotaSnapshot(
                provider=self.provider,
                quota_state="exhausted",
                usage_ratio=float(bucket.get("ratio", 1.0)),
                retry_after=retry_after,
                source="local_counter",
                payload=bucket,
            )
        if not limit:
            return QuotaSnapshot(
                provider=self.provider,
                quota_state="healthy",
                usage_ratio=0.0,
                source="local_counter",
                payload=bucket,
            )
        tokens = int(bucket.get("tokens", 0)) if bucket.get("date") == _today() else 0
        ratio = min(tokens / limit, 1.0)
        state = "near_limit" if ratio >= threshold else "healthy"
        return QuotaSnapshot(
            provider=self.provider,
            quota_state=state,
            usage_ratio=ratio,
            retry_after=retry_after if state == "exhausted" else None,
            source="local_counter",
            payload={**bucket, "tokens": tokens},
        )

    def should_accept_work(self, snapshot: QuotaSnapshot, estimated_tokens: int | None) -> bool:
        if snapshot.quota_state == "exhausted":
            return False
        if snapshot.usage_ratio is None:
            return True
        provider_limit = snapshot.payload.get("token_limit_daily")
        if provider_limit and estimated_tokens:
            return (snapshot.usage_ratio + (estimated_tokens / provider_limit)) < 1.0
        return snapshot.quota_state == "healthy"

    def retry_after(self, snapshot: QuotaSnapshot) -> str | None:
        return snapshot.retry_after

    def mark_exhausted(self, cooldown_hours: int = 4) -> QuotaSnapshot:
        usage = _load_usage(self.usage_path)
        retry_after = (datetime.now(timezone.utc) + timedelta(hours=cooldown_hours)).replace(microsecond=0).isoformat()
        bucket = usage.setdefault(self.provider, {})
        bucket["date"] = _today()
        bucket["retry_after"] = retry_after
        bucket["ratio"] = 1.0
        self.usage_path.parent.mkdir(parents=True, exist_ok=True)
        self.usage_path.write_text(json.dumps(usage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return QuotaSnapshot(
            provider=self.provider,
            quota_state="exhausted",
            usage_ratio=1.0,
            retry_after=retry_after,
            source="local_counter",
            payload=bucket,
        )


def _load_usage(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")
