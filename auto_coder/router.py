"""Provider router: token counting, quota tracking, fallback selection."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ProviderRouter:
    def __init__(self, config: dict[str, Any], usage_path: Path):
        self.config = config
        self.usage_path = usage_path
        self._usage: dict[str, Any] = self._load()

    # ------------------------------------------------------------------ public

    def pick(self, preferred: str) -> str:
        """Return best available provider, falling back if quota near limit."""
        provider_cfg = self.config.get("providers", {}).get(preferred, {})
        limit = provider_cfg.get("token_limit_daily")
        threshold = float(provider_cfg.get("quota_threshold", 1.0))
        fallback = provider_cfg.get("fallback")

        if limit:
            ratio = self._daily_tokens(preferred) / limit
            if ratio >= threshold and fallback:
                return fallback

        return preferred

    def record(self, provider: str, tokens: int) -> None:
        """Add tokens to daily counter for provider."""
        today = _today()
        bucket = self._usage.setdefault(provider, {})
        if bucket.get("date") != today:
            bucket["date"] = today
            bucket["tokens"] = 0
            bucket["calls"] = 0
        bucket["tokens"] = int(bucket.get("tokens", 0)) + tokens
        bucket["calls"] = int(bucket.get("calls", 0)) + 1
        self._save()

    def usage_ratio(self, provider: str) -> float:
        """Return 0.0–1.0 daily usage ratio. 0.0 if no limit configured."""
        limit = self.config.get("providers", {}).get(provider, {}).get("token_limit_daily")
        if not limit:
            return 0.0
        return min(self._daily_tokens(provider) / limit, 1.0)

    def summary(self) -> dict[str, Any]:
        out = {}
        for provider, bucket in self._usage.items():
            if bucket.get("date") != _today():
                continue
            limit = self.config.get("providers", {}).get(provider, {}).get("token_limit_daily")
            out[provider] = {
                "tokens_today": bucket.get("tokens", 0),
                "calls_today": bucket.get("calls", 0),
                "limit": limit,
                "ratio": round(self.usage_ratio(provider), 3),
            }
        return out

    # ----------------------------------------------------------------- private

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
