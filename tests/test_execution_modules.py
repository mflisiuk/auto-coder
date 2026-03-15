"""Tests for extracted execution-core modules."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_coder.executor import run_tests
from auto_coder.policy import validate_changed_files
from auto_coder.scheduler import select_task, should_retry


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


if __name__ == "__main__":
    unittest.main()
