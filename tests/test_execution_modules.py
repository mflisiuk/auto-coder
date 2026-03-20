"""Tests for extracted execution-core modules."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_coder.executor import run_tests
from auto_coder.policy import validate_changed_files
from auto_coder.scheduler import select_task, should_retry
from auto_coder.worker import _build_cmd, is_quota_error


class TestPolicyModule(unittest.TestCase):
    def test_validate_changed_files_respects_allowed_and_protected(self):
        violations = validate_changed_files(
            ["src/app.py", "config/secrets.yml", "README.md"],
            allowed_paths=["src/"],
            protected_paths=["config/"],
        )
        self.assertIn("protected:config/secrets.yml", violations)
        self.assertIn("outside_allowed:README.md", violations)
        self.assertNotIn("src/app.py", "".join(violations))


class TestSchedulerModule(unittest.TestCase):
    def test_select_task_picks_first_ready_priority(self):
        task = select_task(
            [
                {"id": "b", "mode": "safe", "enabled": True, "priority": 20},
                {"id": "a", "mode": "safe", "enabled": True, "priority": 10},
            ],
            {"tasks": {}},
        )
        self.assertIsNotNone(task)
        self.assertEqual(task["id"], "a")

    def test_should_retry_for_retryable_status(self):
        self.assertTrue(should_retry("review_failed"))
        self.assertFalse(should_retry("completed"))


class TestExecutorModule(unittest.TestCase):
    def test_run_tests_writes_results(self):
        with TemporaryDirectory() as tmp:
            worktree = Path(tmp) / "wt"
            reports = Path(tmp) / "reports"
            worktree.mkdir()
            passed, results = run_tests(
                ["python3 -c 'print(123)'"],
                worktree,
                reports,
                timeout_minutes=1,
            )
            self.assertTrue(passed)
            self.assertEqual(results[0]["returncode"], 0)
            self.assertTrue((reports / "tests.json").exists())


class TestQuotaDetection(unittest.TestCase):
    def test_ignores_report_schema_text_when_command_succeeds(self):
        stdout = '{"status":"completed|partial|blocked|quota_exhausted"}'
        self.assertFalse(is_quota_error("", stdout, returncode=0))

    def test_detects_real_rate_limit_failures(self):
        stderr = "Error: 429 Too Many Requests; insufficient_quota"
        self.assertTrue(is_quota_error(stderr, "", returncode=1))

    def test_detects_hit_your_limit_in_json_with_nonzero_returncode(self):
        # Claude Code returns JSON with is_error:true and "hit your limit" message
        # It may exit with non-zero returncode
        stdout = '''🤖 Claude Code (Anthropic)
{"type":"result","subtype":"success","is_error":true,"result":"You\\'ve hit your limit · resets 7am (UTC)"}'''
        self.assertTrue(is_quota_error("", stdout, returncode=1))

    def test_detects_hit_your_limit_in_json_with_zero_returncode(self):
        # Also test with returncode=0 (original case)
        stdout = '''🤖 Claude Code (Anthropic)
{"type":"result","is_error":true,"result":"usage limit reached"}'''
        self.assertTrue(is_quota_error("", stdout, returncode=0))

    def test_detects_rate_limit_text_in_stderr(self):
        # Fallback: text-based detection
        stderr = "Error: rate limit exceeded"
        self.assertTrue(is_quota_error(stderr, "", returncode=1))


class TestWorkerCommands(unittest.TestCase):
    def test_codex_command_skips_git_repo_check(self):
        command = _build_cmd("codex", model=None, max_budget_usd=None)
        self.assertIn("--skip-git-repo-check", command)


if __name__ == "__main__":
    unittest.main()
