"""Provider router: quota probes, token counting, fallback selection."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from auto_coder.quota.base import QuotaSnapshot
from auto_coder.quota.cc import CcQuotaProbe
from auto_coder.quota.ccg import CcgQuotaProbe
from auto_coder.quota.local_counter import LocalCounterQuotaProbe
from auto_coder.storage import record_quota_snapshot


class ProviderRouter:
    def __init__(self, config: dict[str, Any], usage_path: Path):
        self.config = config
        self.usage_path = usage_path
        self.state_db_path: Path | None = config.get("state_db_path")
        self._usage: dict[str, Any] = self._load()
        self._probes = self._build_probes()
        self._snapshots: dict[str, QuotaSnapshot] = {}

    # ------------------------------------------------------------------ public

    def pick(self, preferred: str, estimated_tokens: int | None = None) -> str:
        """Return the best available provider, falling back when quota is tight."""
        candidates = [preferred]
        fallback = self.config.get("providers", {}).get(preferred, {}).get("fallback")
        if fallback:
            candidates.append(str(fallback))

        for provider in candidates:
            snapshot = self.check_quota(provider)
            probe = self._probes[provider]
            if probe.should_accept_work(snapshot, estimated_tokens):
                return provider
        return candidates[-1]

    def check_quota(self, provider: str) -> QuotaSnapshot:
        if provider in self._snapshots:
            return self._snapshots[provider]
        probe = self._probes.get(provider)
        if probe is None:
            probe = LocalCounterQuotaProbe(provider, self.usage_path)
            self._probes[provider] = probe
        snapshot = probe.check_quota(self.config)
        if snapshot.payload.get("token_limit_daily") is None:
            limit = self.config.get("providers", {}).get(provider, {}).get("token_limit_daily")
            if limit is not None:
                snapshot.payload["token_limit_daily"] = limit
        self._snapshots[provider] = snapshot
        self._persist_snapshot(snapshot)
        return snapshot

    def mark_quota_exhausted(self, provider: str) -> QuotaSnapshot:
        cooldown_hours = int(self.config.get("quota_cooldown_hours", 4))
        probe = self._probes.get(provider)
        if isinstance(probe, LocalCounterQuotaProbe):
            snapshot = probe.mark_exhausted(cooldown_hours=cooldown_hours)
        else:
            retry_after = (datetime.now(timezone.utc) + timedelta(hours=cooldown_hours)).replace(microsecond=0).isoformat()
            snapshot = QuotaSnapshot(
                provider=provider,
                quota_state="exhausted",
                usage_ratio=1.0,
                retry_after=retry_after,
                source="router",
                payload={"reason": "quota_exhausted_signal"},
            )
        self._snapshots[provider] = snapshot
        self._persist_snapshot(snapshot)
        return snapshot

    def record(self, provider: str, tokens: int) -> None:
        """Add tokens to the daily counter for a provider."""
        today = _today()
        bucket = self._usage.setdefault(provider, {})
        if bucket.get("date") != today:
            bucket["date"] = today
            bucket["tokens"] = 0
            bucket["calls"] = 0
            bucket.pop("retry_after", None)
            bucket.pop("ratio", None)
        bucket["tokens"] = int(bucket.get("tokens", 0)) + tokens
        bucket["calls"] = int(bucket.get("calls", 0)) + 1
        self._save()
        self._snapshots.pop(provider, None)

    def usage_ratio(self, provider: str) -> float:
        """Return 0.0–1.0 daily usage ratio. 0.0 if no limit configured."""
        limit = self.config.get("providers", {}).get(provider, {}).get("token_limit_daily")
        if not limit:
            return 0.0
        return min(self._daily_tokens(provider) / limit, 1.0)

    def summary(self) -> dict[str, Any]:
        out = {}
        providers = set(self.config.get("providers", {}).keys()) | set(self._usage.keys())
        for provider in sorted(providers):
            bucket = self._usage.get(provider, {})
            if bucket.get("date") not in {None, _today()}:
                bucket = {}
            limit = self.config.get("providers", {}).get(provider, {}).get("token_limit_daily")
            snapshot = self.check_quota(provider)
            out[provider] = {
                "tokens_today": int(bucket.get("tokens", 0)) if bucket else 0,
                "calls_today": int(bucket.get("calls", 0)) if bucket else 0,
                "limit": limit,
                "ratio": round(self.usage_ratio(provider), 3),
                "quota_state": snapshot.quota_state,
                "retry_after": snapshot.retry_after,
                "probe_source": snapshot.source,
            }
        return out

    def probe_availability(self) -> dict[str, str]:
        out = {}
        for provider, probe in self._probes.items():
            available = probe.is_available(self.config)
            out[provider] = probe.__class__.__name__ if available else "local-fallback"
        return out

    # ----------------------------------------------------------------- private

    def _build_probes(self) -> dict[str, Any]:
        providers = set(self.config.get("providers", {}).keys())
        probes: dict[str, Any] = {}
        for provider in providers:
            if provider == "ccg" and CcgQuotaProbe.is_available(self.config):
                probes[provider] = CcgQuotaProbe()
            elif provider == "cc" and CcQuotaProbe.is_available(self.config):
                probes[provider] = CcQuotaProbe()
            else:
                probes[provider] = LocalCounterQuotaProbe(provider, self.usage_path)
        return probes

    def _persist_snapshot(self, snapshot: QuotaSnapshot) -> None:
        if not self.state_db_path:
            return
        record_quota_snapshot(
            self.state_db_path,
            provider=snapshot.provider,
            quota_state=snapshot.quota_state,
            usage_ratio=snapshot.usage_ratio,
            retry_after=snapshot.retry_after,
            payload={"source": snapshot.source, **snapshot.payload},
        )

    def _daily_tokens(self, provider: str) -> int:
        bucket = self._usage.get(provider, {})
        if bucket.get("date") != _today():
            return 0
        return int(bucket.get("tokens", 0))

    def _load(self) -> dict[str, Any]:
        if not self.usage_path.exists():
            return {}
        try:
            return json.loads(self.usage_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self) -> None:
        self.usage_path.parent.mkdir(parents=True, exist_ok=True)
        self.usage_path.write_text(
            json.dumps(self._usage, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")
