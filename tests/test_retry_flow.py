"""Integration-style tests for retry semantics."""
from __future__ import annotations

import json
import subprocess
import unittest
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from auto_coder.config import AUTO_CODER_DIR, load_config
from auto_coder.managers.base import ReviewDecision
from auto_coder.orchestrator import run_one_task
from auto_coder.storage import ensure_database, get_task_runtime, latest_work_order_for_task, list_attempts_for_task


class _FakeManagerBackend:
    @classmethod
    def is_available(cls) -> bool:
        return True

    def __init__(self):
        self.created = 0

    def create_work_order(self, task, history, repo_context=None):
        self.created += 1
        return {
            "id": f"{task['id']}-wo-{self.created:02d}",
            "task_id": task["id"],
            "sequence_no": self.created,
            "goal": task.get("prompt", ""),
            "scope_summary": task.get("title", task["id"]),
            "allowed_paths": list(task.get("allowed_paths", [])),
            "completion_commands": list(task.get("completion_commands", [])),
            "selected_worker": "cch",
            "manager_feedback": "Fix the missing edge case." if self.created > 1 else "",
            "status": "queued",
            "created_by": "fake-manager",
        }

    def review_attempt(self, task, work_order, attempt_context, history):
        return ReviewDecision(
            verdict="retry",
            feedback="Fix the missing edge case.",
            blockers=["missing_edge_case"],
            next_work_order=self.create_work_order(task, history, None),
            source="fake-manager",
        )


class TestRetryFlow(unittest.TestCase):
    def _config(self, root: Path) -> dict:
        acd = root / AUTO_CODER_DIR
        acd.mkdir(parents=True, exist_ok=True)
        ensure_database(acd / "state.db")
        config = load_config(root)
        config["dry_run"] = False
        config["manager_enabled"] = True
        return config

    def test_retry_persists_feedback_and_queues_next_work_order(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self._config(root)
            state: dict = {"tasks": {}, "runs": []}
            task = {
                "id": "task-1",
                "title": "Task 1",
                "prompt": "Implement feature.",
                "allowed_paths": ["src/"],
                "baseline_commands": [],
                "completion_commands": ["python3 -c 'print(1)'"],
            }

            def fake_create_worktree(_root, worktree, _base_ref, _branch):
                worktree.mkdir(parents=True, exist_ok=True)

            class FakeWorker:
                def run(self, **kwargs):
                    worktree = kwargs["worktree"]
                    (worktree / "src").mkdir(parents=True, exist_ok=True)
                    (worktree / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
                    (worktree / "AGENT_REPORT.json").write_text(
                        json.dumps({"status": "completed", "summary": "done", "completed": ["x"], "issues": [], "next": ""}),
                        encoding="utf-8",
                    )
                    return SimpleNamespace(
                        worker_name="cch",
                        command=["cch"],
                        returncode=0,
                        stdout="",
                        stderr="",
                        token_usage=0,
                        quota_exhausted=False,
                        metadata={},
                    )

            def fake_git(_repo, *args):
                if args == ("diff",):
                    return subprocess.CompletedProcess(args=["git", *args], returncode=0, stdout="diff", stderr="")
                if args == ("diff", "--stat"):
                    return subprocess.CompletedProcess(args=["git", *args], returncode=0, stdout=" src/app.py | 1 +", stderr="")
                return subprocess.CompletedProcess(args=["git", *args], returncode=0, stdout="", stderr="")

            with patch("auto_coder.orchestrator._resolve_manager_backend", return_value=_FakeManagerBackend()), \
                 patch("auto_coder.orchestrator._resolve_worktree_base_ref", return_value="HEAD"), \
                 patch("auto_coder.orchestrator._create_worktree", side_effect=fake_create_worktree), \
                 patch("auto_coder.orchestrator.build_worker_adapter", return_value=FakeWorker()), \
                 patch("auto_coder.orchestrator._changed_files", return_value=["src/app.py"]), \
                 patch("auto_coder.orchestrator._git", side_effect=fake_git):
                exit_code = run_one_task(config, task, state)

            self.assertEqual(exit_code, 1)
            task_row = get_task_runtime(config["state_db_path"], "task-1")
            self.assertIsNotNone(task_row)
            self.assertEqual(task_row["status"], "waiting_for_retry")
            latest_work_order = latest_work_order_for_task(config["state_db_path"], "task-1")
            self.assertIsNotNone(latest_work_order)
            self.assertEqual(latest_work_order["status"], "queued")
            attempts = list_attempts_for_task(config["state_db_path"], "task-1")
            self.assertEqual(len(attempts), 2)
            self.assertEqual(attempts[0]["status"], "started")
            self.assertEqual(attempts[-1]["status"], "review_failed")

    def test_allow_no_changes_task_can_complete_without_source_diff(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self._config(root)
            config["auto_commit"] = False
            config["manager_enabled"] = False
            state: dict = {"tasks": {}, "runs": []}
            task = {
                "id": "task-report",
                "title": "Report task",
                "prompt": "Verify baseline and report.",
                "allowed_paths": ["src/"],
                "baseline_commands": [],
                "completion_commands": ["python3 -c 'print(1)'"],
                "allow_no_changes": True,
                "report_only": True,
            }

            def fake_create_worktree(_root, worktree, _base_ref, _branch):
                worktree.mkdir(parents=True, exist_ok=True)

            with patch("auto_coder.orchestrator._resolve_worktree_base_ref", return_value="HEAD"), \
                 patch("auto_coder.orchestrator._create_worktree", side_effect=fake_create_worktree), \
                 patch("auto_coder.orchestrator._changed_files", return_value=[]):
                exit_code = run_one_task(config, task, state)

            self.assertEqual(exit_code, 0)
            task_row = get_task_runtime(config["state_db_path"], "task-report")
            self.assertIsNotNone(task_row)
            self.assertEqual(task_row["status"], "completed")

    def test_setup_commands_run_before_baseline(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self._config(root)
            config["auto_commit"] = False
            config["manager_enabled"] = False
            state: dict = {"tasks": {}, "runs": []}
            task = {
                "id": "task-setup",
                "title": "Setup task",
                "prompt": "Verify setup is executed.",
                "allowed_paths": ["src/"],
                "setup_commands": ["mkdir -p vendor/bin && printf '#!/bin/sh\\nexit 0\\n' > vendor/bin/phpunit && chmod +x vendor/bin/phpunit"],
                "baseline_commands": ["./vendor/bin/phpunit"],
                "completion_commands": ["python3 -c 'print(1)'"],
                "allow_no_changes": True,
                "report_only": True,
            }

            def fake_create_worktree(_root, worktree, _base_ref, _branch):
                worktree.mkdir(parents=True, exist_ok=True)

            with patch("auto_coder.orchestrator._resolve_worktree_base_ref", return_value="HEAD"), \
                 patch("auto_coder.orchestrator._create_worktree", side_effect=fake_create_worktree), \
                 patch("auto_coder.orchestrator._changed_files", return_value=[]):
                exit_code = run_one_task(config, task, state)

            self.assertEqual(exit_code, 0)
            task_row = get_task_runtime(config["state_db_path"], "task-setup")
            self.assertIsNotNone(task_row)
            self.assertEqual(task_row["status"], "completed")


if __name__ == "__main__":
    unittest.main()
