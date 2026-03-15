"""Tests for quota probes and snapshot handling."""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_coder.quota.local_counter import LocalCounterQuotaProbe


class TestLocalCounterQuotaProbe(unittest.TestCase):
    def test_near_limit_when_usage_crosses_threshold(self):
        with TemporaryDirectory() as tmp:
            usage_path = Path(tmp) / "usage.json"
            usage_path.write_text(
                json.dumps(
                    {
                        "ccg": {
                            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                            "tokens": 85_000,
                            "calls": 2,
                        }
                    }
                ),
                encoding="utf-8",
            )
            probe = LocalCounterQuotaProbe("ccg", usage_path)
            config = {"providers": {"ccg": {"token_limit_daily": 100_000, "quota_threshold": 0.8}}}
            snapshot = probe.check_quota(config)
            self.assertEqual(snapshot.quota_state, "near_limit")

    def test_mark_exhausted_sets_retry_after(self):
        with TemporaryDirectory() as tmp:
            probe = LocalCounterQuotaProbe("ccg", Path(tmp) / "usage.json")
            snapshot = probe.mark_exhausted(cooldown_hours=1)
            self.assertEqual(snapshot.quota_state, "exhausted")
            self.assertIsNotNone(snapshot.retry_after)


if __name__ == "__main__":
    unittest.main()
