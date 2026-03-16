"""Tests for orchestrator: validate_changed_files, select_task, run_tests, run_batch."""
from __future__ import annotations
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from auto_coder.orchestrator import (
    _reset_tracked_changes,
    validate_changed_files,
    select_task,
    run_tests,
    run_batch,
    should_retry,
)
from auto_coder.config import AUTO_CODER_DIR, load_config


class TestValidateChangedFiles(unittest.TestCase):
    def test_allows_files_under_allowed_paths(self):
        violations = validate_changed_files(
            ["src/auth/login.py", "tests/test_auth.py"],
            allowed_paths=["src/", "tests/"],
            protected_paths=["config/"],
        )
        self.assertEqual(violations, [])

    def test_blocks_protected_paths(self):
        violations = validate_changed_files(
            ["config/secrets.yaml"],
            allowed_paths=["src/"],
            protected_paths=["config/"],
        )
        self.assertIn("protected:config/secrets.yaml", violations)

    def test_blocks_outside_allowed(self):
        violations = validate_changed_files(
            ["README.md"],
            allowed_paths=["src/"],
            protected_paths=[],
        )
        self.assertIn("outside_allowed:README.md", violations)

    def test_no_violation_when_no_allowed_paths(self):
        violations = validate_changed_files(
            ["anything.py"],
            allowed_paths=[],
            protected_paths=[],
        )
        self.assertEqual(violations, [])


class TestSelectTask(unittest.TestCase):
    def _tasks(self):
        return [
            {"id": "task-a", "mode": "safe", "enabled": True, "priority": 10},
            {"id": "task-b", "mode": "safe", "enabled": True, "priority": 20},
        ]

    def test_picks_highest_priority(self):
        task = select_task(self._tasks(), {"tasks": {}, "runs": []})
        self.assertEqual(task["id"], "task-a")

    def test_skips_completed(self):
        state = {"tasks": {"task-a": {"status": "completed"}}, "runs": []}
        task = select_task(self._tasks(), state)
        self.assertEqual(task["id"], "task-b")

    def test_skips_disabled(self):
        tasks = [{"id": "off", "mode": "safe", "enabled": False, "priority": 1},
                 {"id": "on",  "mode": "safe", "enabled": True,  "priority": 2}]
        task = select_task(tasks, {"tasks": {}, "runs": []})
        self.assertEqual(task["id"], "on")

    def test_skips_exhausted(self):
        tasks = [{"id": "t1", "mode": "safe", "enabled": True, "priority": 1, "max_total_attempts": 2},
                 {"id": "t2", "mode": "safe", "enabled": True, "priority": 2}]
        state = {"tasks": {"t1": {"attempt_count": 2, "status": "tests_failed"}}}
        task = select_task(tasks, state)
        self.assertEqual(task["id"], "t2")

    def test_returns_none_when_all_done(self):
        state = {"tasks": {"task-a": {"status": "completed"}, "task-b": {"status": "completed"}}}
        task = select_task(self._tasks(), state)
        self.assertIsNone(task)

    def test_skips_quarantined(self):
        state = {"tasks": {"task-a": {"status": "quarantined"}}, "runs": []}
        task = select_task(self._tasks(), state)
        self.assertEqual(task["id"], "task-b")

    def test_waiting_for_dependency_uses_runtime_depends_on(self):
        tasks = [
            {
                "id": "task-a",
                "mode": "safe",
                "enabled": True,
                "priority": 10,
                "runtime_depends_on": ["repair-baseline::task-a"],
            },
            {"id": "task-b", "mode": "safe", "enabled": True, "priority": 20},
        ]
        state = {
            "tasks": {
                "task-a": {"status": "waiting_for_dependency"},
                "repair-baseline::task-a": {"status": "ready"},
            },
            "runs": [],
        }
        task = select_task(tasks, state)
        self.assertEqual(task["id"], "task-b")


class TestShouldRetry(unittest.TestCase):
    def test_retryable_statuses(self):
        for s in ("tests_failed", "review_failed", "agent_failed", "no_changes",
                  "policy_failed", "quota_exhausted"):
            self.assertTrue(should_retry(s), s)

    def test_non_retryable_statuses(self):
        for s in ("completed", "baseline_failed", "runner_failed", None):
            self.assertFalse(should_retry(s), s)


class TestRunTests(unittest.TestCase):
    def test_passes_when_command_exits_zero(self):
        with TemporaryDirectory() as tmp:
            worktree = Path(tmp) / "wt"
            report_dir = Path(tmp) / "report"
            worktree.mkdir()
            passed, results = run_tests(["python3 -c 'print(1)'"], worktree, report_dir, timeout_minutes=1)
            self.assertTrue(passed)
            self.assertEqual(results[0]["returncode"], 0)

    def test_fails_when_command_exits_nonzero(self):
        with TemporaryDirectory() as tmp:
            worktree = Path(tmp) / "wt"
            report_dir = Path(tmp) / "report"
            worktree.mkdir()
            passed, results = run_tests(["python3 -c 'raise SystemExit(1)'"], worktree, report_dir, timeout_minutes=1)
            self.assertFalse(passed)
            self.assertEqual(results[0]["returncode"], 1)

    def test_saves_stdout_stderr_logs(self):
        with TemporaryDirectory() as tmp:
            worktree = Path(tmp) / "wt"
            report_dir = Path(tmp) / "report"
            worktree.mkdir()
            run_tests(["python3 -c \"import sys; sys.stdout.write('out'); sys.stderr.write('err')\""],
                      worktree, report_dir, timeout_minutes=1)
            self.assertIn("out", (report_dir / "tests" / "test-01.stdout.log").read_text())
            self.assertIn("err", (report_dir / "tests" / "test-01.stderr.log").read_text())


class TestWorktreeReset(unittest.TestCase):
    def test_reset_tracked_changes_preserves_untracked_files(self):
        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            import subprocess

            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            (repo / "tracked.txt").write_text("original\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True, text=True)

            (repo / "tracked.txt").write_text("mutated\n", encoding="utf-8")
            (repo / "untracked.txt").write_text("keep\n", encoding="utf-8")

            _reset_tracked_changes(repo)

            self.assertEqual((repo / "tracked.txt").read_text(encoding="utf-8"), "original\n")
            self.assertEqual((repo / "untracked.txt").read_text(encoding="utf-8"), "keep\n")


class TestRunBatch(unittest.TestCase):
    def _make_config(self, tmp: str) -> dict:
        root = Path(tmp)
        acd = root / AUTO_CODER_DIR
        acd.mkdir(parents=True)
        config = load_config(root)
        config["dry_run"] = False
        return config

    def test_respects_max_tasks_per_run(self):
        with TemporaryDirectory() as tmp:
            config = self._make_config(tmp)
            config["max_tasks_per_run"] = 2
            config["max_attempts_per_task_per_run"] = 1
            tasks = [{"id": f"t{i}", "mode": "safe", "enabled": True, "priority": i} for i in range(3)]
            state: dict = {"tasks": {}, "runs": []}
            calls = []

            def fake_run(_config, task, _state):
                calls.append(task["id"])
                _state.setdefault("tasks", {})[task["id"]] = {"status": "completed"}
                return 0

            with patch("auto_coder.orchestrator.run_one_task", side_effect=fake_run):
                run_batch(config, tasks, state)

            self.assertEqual(len(calls), 2)

    def test_does_not_retry_same_task_within_single_tick(self):
        with TemporaryDirectory() as tmp:
            config = self._make_config(tmp)
            config["max_tasks_per_run"] = 1
            config["max_attempts_per_task_per_run"] = 3
            tasks = [{"id": "t1", "mode": "safe", "enabled": True, "priority": 1}]
            state: dict = {"tasks": {}, "runs": []}
            attempt = {"n": 0}

            def fake_run(_config, task, shared_state):
                attempt["n"] += 1
                ts = shared_state.setdefault("tasks", {}).setdefault(task["id"], {})
                if attempt["n"] == 1:
                    ts["status"] = "waiting_for_retry"
                    return 1
                ts["status"] = "completed"
                return 0

            with patch("auto_coder.orchestrator.run_one_task", side_effect=fake_run):
                exit_code = run_batch(config, tasks, state)

            self.assertEqual(exit_code, 1)
            self.assertEqual(attempt["n"], 1)

    def test_continues_to_next_task_when_first_is_waiting_for_dependency(self):
        with TemporaryDirectory() as tmp:
            config = self._make_config(tmp)
            config["max_tasks_per_run"] = 2
            tasks = [
                {"id": "t1", "mode": "safe", "enabled": True, "priority": 1},
                {"id": "t2", "mode": "safe", "enabled": True, "priority": 2},
            ]
            state: dict = {"tasks": {}, "runs": []}
            calls = []

            def fake_run(_config, task, shared_state):
                calls.append(task["id"])
                shared_state.setdefault("tasks", {}).setdefault(task["id"], {})
                if task["id"] == "t1":
                    shared_state["tasks"]["t1"]["status"] = "waiting_for_dependency"
                    shared_state["tasks"]["t1"]["runtime_depends_on"] = ["repair-baseline::t1"]
                    shared_state.setdefault("tasks", {})["repair-baseline::t1"] = {"status": "ready"}
                    return 1
                shared_state["tasks"]["t2"] = {"status": "completed"}
                return 0

            with patch("auto_coder.orchestrator.run_one_task", side_effect=fake_run):
                exit_code = run_batch(config, tasks, state)

            self.assertEqual(exit_code, 1)
            self.assertEqual(calls, ["t1", "t2"])


if __name__ == "__main__":
    unittest.main()
