"""Quota probe for cc status output when configured."""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from auto_coder.quota.base import QuotaProbe, QuotaSnapshot


class CcQuotaProbe(QuotaProbe):
    @classmethod
    def provider_name(cls) -> str:
        return "cc"

    @classmethod
    def is_available(cls, config: dict[str, Any]) -> bool:
        return bool(config.get("cc_usage_command")) and shutil.which(str(config["cc_usage_command"][0])) is not None

    def check_quota(self, config: dict[str, Any]) -> QuotaSnapshot:
        command = list(config.get("cc_usage_command") or [])
        if not command:
            return QuotaSnapshot(provider="cc", quota_state="unknown", source="cc_probe")
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        payload = _parse_payload(result.stdout)
        ratio = payload.get("usage_ratio")
        if ratio is None:
            used = payload.get("used_tokens")
            limit = payload.get("token_limit")
            if used is not None and limit:
                ratio = min(float(used) / float(limit), 1.0)
        threshold = float(config.get("providers", {}).get("cc", {}).get("quota_threshold", 0.9))
        state = "healthy"
        if ratio is not None and float(ratio) >= threshold:
            state = "near_limit"
        return QuotaSnapshot(provider="cc", quota_state=state, usage_ratio=float(ratio) if ratio is not None else None, source="cc_probe", payload=payload)

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
