"""Tests for the Codex manager bridge backend."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from auto_coder.config import AUTO_CODER_DIR, load_config
from auto_coder.managers.codex_bridge import CodexManagerBridge
from auto_coder.storage import ensure_database, load_manager_thread


class TestCodexManagerBridge(unittest.TestCase):
    def _config(self, root: Path) -> dict:
        acd = root / AUTO_CODER_DIR
        acd.mkdir(parents=True, exist_ok=True)
        ensure_database(acd / "state.db")
        config = load_config(root)
        config["manager_backend"] = "codex"
        return config

    def test_create_work_order_persists_thread_id(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self._config(root)
            bridge = CodexManagerBridge(
                task_id="task-1",
                task={"id": "task-1", "title": "Task 1", "prompt": "Build feature", "allowed_paths": ["src/"]},
                config=config,
                state_path=config["state_path"],
            )
            fake_stdout = json.dumps(
                {
                    "ok": True,
                    "thread_id": "thread-123",
                    "result": {
                        "goal": "Implement feature",
                        "scope_summary": "Task 1 slice",
                        "allowed_paths": ["src/"],
                        "completion_commands": ["python3 -m unittest"],
                        "selected_worker": "codex",
                        "manager_feedback": "Focus on the happy path"
                    }
                }
            )
            with patch("subprocess.run") as run:
                run.return_value.returncode = 0
                run.return_value.stdout = fake_stdout
                run.return_value.stderr = ""
                work_order = bridge.create_work_order({"id": "task-1", "title": "Task 1", "prompt": "Build feature", "allowed_paths": ["src/"]}, history=[])

            self.assertEqual(work_order["selected_worker"], "codex")
            thread = load_manager_thread(config["state_db_path"], task_id="task-1", manager_backend="codex")
            self.assertIsNotNone(thread)
            self.assertEqual(thread["external_thread_id"], "thread-123")

    def test_review_attempt_returns_decision_and_next_work_order(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self._config(root)
            bridge = CodexManagerBridge(
                task_id="task-1",
                task={"id": "task-1", "title": "Task 1", "prompt": "Build feature", "allowed_paths": ["src/"]},
                config=config,
                state_path=config["state_path"],
            )
            fake_stdout = json.dumps(
                {
                    "ok": True,
                    "thread_id": "thread-123",
                    "result": {
                        "verdict": "retry",
                        "feedback": "Cover the error path.",
                        "blockers": ["missing_error_path"],
                        "next_work_order": {
                            "goal": "Add error-path coverage",
                            "scope_summary": "Error handling",
                            "allowed_paths": ["src/"],
                            "completion_commands": ["python3 -m unittest"],
                            "selected_worker": "codex",
                            "manager_feedback": "Add tests for the error path"
                        }
                    }
                }
            )
            with patch("subprocess.run") as run:
                run.return_value.returncode = 0
                run.return_value.stdout = fake_stdout
                run.return_value.stderr = ""
                decision = bridge.review_attempt(
                    task={"id": "task-1", "title": "Task 1", "prompt": "Build feature", "allowed_paths": ["src/"]},
                    work_order={"id": "task-1-wo-01"},
                    attempt_context={"attempt_no": 1},
                    history=[],
                )

            self.assertEqual(decision.verdict, "retry")
            self.assertEqual(decision.next_work_order["selected_worker"], "codex")


if __name__ == "__main__":
    unittest.main()
