"""Tests for ProviderRouter: token counting, fallback, daily reset."""
from __future__ import annotations
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_coder.router import ProviderRouter, _today


def _make_router(tmp: str, providers: dict | None = None) -> ProviderRouter:
    config = {
        "providers": providers or {
            "ccg": {"token_limit_daily": 100_000, "quota_threshold": 0.80, "fallback": "cch"},
            "cc":  {"token_limit_daily": 500_000, "quota_threshold": 0.90, "fallback": "cch"},
            "cch": {"token_limit_daily": None,    "quota_threshold": 1.00, "fallback": None},
        }
    }
    return ProviderRouter(config, Path(tmp) / "usage.json")


class TestProviderRouter(unittest.TestCase):
    def test_returns_preferred_when_under_threshold(self):
        with TemporaryDirectory() as tmp:
            router = _make_router(tmp)
            router.record("ccg", 50_000)   # 50% of 100k limit
            self.assertEqual(router.pick("ccg"), "ccg")

    def test_falls_back_when_over_threshold(self):
        with TemporaryDirectory() as tmp:
            router = _make_router(tmp)
            router.record("ccg", 85_000)   # 85% > 80% threshold
            self.assertEqual(router.pick("ccg"), "cch")

    def test_no_fallback_when_no_limit(self):
        with TemporaryDirectory() as tmp:
            router = _make_router(tmp)
            self.assertEqual(router.pick("cch"), "cch")

    def test_tokens_accumulate(self):
        with TemporaryDirectory() as tmp:
            router = _make_router(tmp)
            router.record("cc", 10_000)
            router.record("cc", 20_000)
            summary = router.summary()
            self.assertEqual(summary["cc"]["tokens_today"], 30_000)

    def test_persists_to_disk(self):
        with TemporaryDirectory() as tmp:
            usage_path = Path(tmp) / "usage.json"
            router1 = ProviderRouter({"providers": {}}, usage_path)
            router1.record("cc", 12_345)
            router2 = ProviderRouter({"providers": {}}, usage_path)
            summary = router2.summary()
            self.assertEqual(summary["cc"]["tokens_today"], 12_345)

    def test_resets_on_new_day(self):
        with TemporaryDirectory() as tmp:
            router = _make_router(tmp)
            # Manually write yesterday's usage
            yesterday = "2000-01-01"
            usage = {"ccg": {"date": yesterday, "tokens": 99_000, "calls": 5}}
            (Path(tmp) / "usage.json").write_text(json.dumps(usage), encoding="utf-8")
            router2 = _make_router(tmp)
            # Since it's a different date, daily tokens should be 0
            self.assertEqual(router2.usage_ratio("ccg"), 0.0)

    def test_usage_ratio_zero_when_no_limit(self):
        with TemporaryDirectory() as tmp:
            router = _make_router(tmp)
            router.record("cch", 999_999)
            self.assertEqual(router.usage_ratio("cch"), 0.0)

    def test_mark_quota_exhausted_sets_retry_after(self):
        with TemporaryDirectory() as tmp:
            router = _make_router(tmp)
            snapshot = router.mark_quota_exhausted("ccg")
            self.assertEqual(snapshot.quota_state, "exhausted")
            self.assertIsNotNone(snapshot.retry_after)

    def test_summary_contains_quota_state(self):
        with TemporaryDirectory() as tmp:
            router = _make_router(tmp)
            summary = router.summary()
            self.assertIn("quota_state", summary["ccg"])
            self.assertIn("probe_source", summary["ccg"])

    def test_follows_multi_hop_fallback_chain(self):
        with TemporaryDirectory() as tmp:
            router = _make_router(
                tmp,
                providers={
                    "codex": {"token_limit_daily": 100, "quota_threshold": 0.50, "fallback": "gemini"},
                    "gemini": {"token_limit_daily": 100, "quota_threshold": 0.50, "fallback": "cch"},
                    "cch": {"token_limit_daily": None, "quota_threshold": 1.00, "fallback": None},
                },
            )
            router.record("codex", 80)
            router.record("gemini", 80)
            self.assertEqual(router.pick("codex"), "cch")

    def test_appends_global_fallback_worker(self):
        with TemporaryDirectory() as tmp:
            router = ProviderRouter(
                {
                    "fallback_worker": "cch",
                    "providers": {
                        "codex": {"token_limit_daily": 100, "quota_threshold": 0.50, "fallback": None},
                        "cch": {"token_limit_daily": None, "quota_threshold": 1.00, "fallback": None},
                    },
                },
                Path(tmp) / "usage.json",
            )
            router.record("codex", 80)
            self.assertEqual(router.pick("codex"), "cch")


if __name__ == "__main__":
    unittest.main()
