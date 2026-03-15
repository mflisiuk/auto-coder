"""Quota probe for ccg / Z.ai usage command when configured."""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from auto_coder.quota.base import QuotaProbe, QuotaSnapshot


class CcgQuotaProbe(QuotaProbe):
    @classmethod
    def provider_name(cls) -> str:
        return "ccg"

    @classmethod
    def is_available(cls, config: dict[str, Any]) -> bool:
        return bool(config.get("ccg_usage_command")) and shutil.which(str(config["ccg_usage_command"][0])) is not None

    def check_quota(self, config: dict[str, Any]) -> QuotaSnapshot:
        command = list(config.get("ccg_usage_command") or [])
        if not command:
            return QuotaSnapshot(provider="ccg", quota_state="unknown", source="ccg_probe")
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        payload = _parse_payload(result.stdout)
        ratio = _extract_ratio(payload)
        state = "healthy"
        threshold = float(config.get("providers", {}).get("ccg", {}).get("quota_threshold", 0.8))
        if ratio is not None and ratio >= threshold:
            state = "near_limit"
        return QuotaSnapshot(provider="ccg", quota_state=state, usage_ratio=ratio, source="ccg_probe", payload=payload)

    def should_accept_work(self, snapshot: QuotaSnapshot, estimated_tokens: int | None) -> bool:
        return snapshot.quota_state not in {"near_limit", "exhausted"}

    def retry_after(self, snapshot: QuotaSnapshot) -> str | None:
        return snapshot.retry_after


def _parse_payload(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


def _extract_ratio(payload: dict[str, Any]) -> float | None:
    if "usage_ratio" in payload:
        return float(payload["usage_ratio"])
    used = payload.get("used_tokens")
    limit = payload.get("token_limit")
    if used is not None and limit:
        return min(float(used) / float(limit), 1.0)
    return None
