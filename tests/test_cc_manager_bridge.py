"""Tests for CcManagerBridge (Claude Code manager backend)."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from auto_coder.managers.base import ReviewDecision
from auto_coder.managers.cc_bridge import CcManagerBridge


class TestCcManagerBridgeAvailability(unittest.TestCase):
    """Test availability checks for the Claude Code manager backend."""

    @patch("shutil.which")
    def test_is_available_when_claude_in_path(self, mock_which):
        mock_which.return_value = "/usr/bin/claude"
        self.assertTrue(CcManagerBridge.is_available())
        mock_which.assert_called_once_with("claude")

    @patch("shutil.which")
    def test_is_not_available_when_no_claude(self, mock_which):
        mock_which.return_value = None
        self.assertFalse(CcManagerBridge.is_available())
        mock_which.assert_called_once_with("claude")


class TestCcManagerBridgeProbeLive(unittest.TestCase):
    """Test probe_live functionality."""

    @patch("shutil.which")
    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_probe_live_success(self, mock_exists, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/claude"
        mock_exists.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"ok": true, "thread_id": null, "result": {"status": "ok", "backend": "cc"}, "events": []}'
        )

        config = {"project_root": Path("/tmp/test"), "manager_timeout_seconds": 180}
        result = CcManagerBridge.probe_live(config)

        self.assertIn("status", json.loads(result))
        self.assertEqual(json.loads(result)["status"], "ok")

    @patch("shutil.which")
    @patch("pathlib.Path.exists")
    def test_probe_live_bridge_not_found(self, mock_exists, mock_which):
        mock_which.return_value = "/usr/bin/claude"
        mock_exists.return_value = False

        config = {"project_root": Path("/tmp/test")}
        with self.assertRaises(RuntimeError) as ctx:
            CcManagerBridge.probe_live(config)
        self.assertIn("Cc bridge not found", str(ctx.exception))

    @patch("shutil.which")
    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_probe_live_removes_claudecode_env_var(self, mock_exists, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/claude"
        mock_exists.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"ok": true, "thread_id": null, "result": {"status": "ok", "backend": "cc"}, "events": []}'
        )

        # Set CLAUDECODE env var
        import os
        os.environ["CLAUDECODE"] = "/some/path"

        try:
            config = {"project_root": Path("/tmp/test")}
            CcManagerBridge.probe_live(config)

            # Verify subprocess.run was called
            self.assertTrue(mock_run.called)
            call_args = mock_run.call_args
            # Verify CLAUDECODE is NOT in the env passed to subprocess
            env_arg = call_args.kwargs.get("env") if call_args.kwargs else None
            if env_arg:
                self.assertNotIn("CLAUDECODE", env_arg)
        finally:
            # Clean up
            os.environ.pop("CLAUDECODE", None)


class TestCcManagerBridgeCreateWorkOrder(unittest.TestCase):
    """Test create_work_order functionality."""

    @patch("shutil.which")
    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    @patch("auto_coder.managers.cc_bridge.save_manager_messages")
    @patch("auto_coder.managers.cc_bridge.load_manager_thread")
    def test_create_work_order_returns_valid_structure(
        self, mock_load_thread, mock_save, mock_exists, mock_run, mock_which
    ):
        mock_which.return_value = "/usr/bin/claude"
        mock_exists.return_value = True
        mock_load_thread.return_value = None

        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({
                "ok": True,
                "thread_id": "thread-123",
                "result": {
                    "goal": "Implement feature X",
                    "scope_summary": "Add feature X to module Y",
                    "allowed_paths": ["src/"],
                    "completion_commands": ["pytest tests/"],
                    "selected_worker": "cc",
                    "manager_feedback": "Focus on module Y"
                },
                "events": []
            })
        )

        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "project_root": Path(tmp),
                "state_db_path": Path(tmp) / "state.db",
                "manager_timeout_seconds": 180,
            }
            task = {"id": "task-1", "title": "Feature X", "allowed_paths": ["src/"], "completion_commands": ["pytest tests/"]}
            state_path = Path(tmp)

            bridge = CcManagerBridge(task_id="task-1", task=task, config=config, state_path=state_path)
            work_order = bridge.create_work_order(task, [], {})

            self.assertEqual(work_order["task_id"], "task-1")
            self.assertEqual(work_order["sequence_no"], 1)
            self.assertEqual(work_order["goal"], "Implement feature X")
            self.assertEqual(work_order["selected_worker"], "cc")
            self.assertEqual(work_order["status"], "queued")


class TestCcManagerBridgeReviewAttempt(unittest.TestCase):
    """Test review_attempt functionality."""

    @patch("shutil.which")
    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    @patch("auto_coder.managers.cc_bridge.save_manager_messages")
    @patch("auto_coder.managers.cc_bridge.load_manager_thread")
    def test_review_attempt_approve(self, mock_load_thread, mock_save, mock_exists, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/claude"
        mock_exists.return_value = True
        mock_load_thread.return_value = None

        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({
                "ok": True,
                "thread_id": "thread-123",
                "result": {
                    "verdict": "approve",
                    "feedback": "Looks good",
                    "blockers": [],
                    "next_work_order": None
                },
                "events": []
            })
        )

        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "project_root": Path(tmp),
                "state_db_path": Path(tmp) / "state.db",
                "manager_timeout_seconds": 180,
            }
            task = {"id": "task-1", "title": "Feature X"}
            work_order = {"id": "wo-1", "goal": "Implement X"}
            attempt_context = {"changed_files": ["src/file.py"]}
            state_path = Path(tmp)

            bridge = CcManagerBridge(task_id="task-1", task=task, config=config, state_path=state_path)
            decision = bridge.review_attempt(task, work_order, attempt_context, [])

            self.assertIsInstance(decision, ReviewDecision)
            self.assertEqual(decision.verdict, "approve")
            self.assertEqual(decision.feedback, "Looks good")
            self.assertEqual(decision.blockers, [])
            self.assertIsNone(decision.next_work_order)
            self.assertEqual(decision.source, "cc")

    @patch("shutil.which")
    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    @patch("auto_coder.managers.cc_bridge.save_manager_messages")
    @patch("auto_coder.managers.cc_bridge.load_manager_thread")
    def test_review_attempt_retry_with_next_work_order(self, mock_load_thread, mock_save, mock_exists, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/claude"
        mock_exists.return_value = True
        mock_load_thread.return_value = None

        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({
                "ok": True,
                "thread_id": "thread-123",
                "result": {
                    "verdict": "retry",
                    "feedback": "Fix the imports",
                    "blockers": ["missing-import"],
                    "next_work_order": {
                        "goal": "Fix imports",
                        "scope_summary": "Add missing imports",
                        "allowed_paths": ["src/"],
                        "completion_commands": ["pytest tests/"],
                        "selected_worker": "cc",
                        "manager_feedback": "Add the imports"
                    }
                },
                "events": []
            })
        )

        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "project_root": Path(tmp),
                "state_db_path": Path(tmp) / "state.db",
                "manager_timeout_seconds": 180,
            }
            task = {"id": "task-1", "title": "Feature X"}
            work_order = {"id": "wo-1", "goal": "Implement X"}
            attempt_context = {"changed_files": ["src/file.py"]}
            state_path = Path(tmp)

            bridge = CcManagerBridge(task_id="task-1", task=task, config=config, state_path=state_path)
            decision = bridge.review_attempt(task, work_order, attempt_context, [])

            self.assertEqual(decision.verdict, "retry")
            self.assertEqual(decision.feedback, "Fix the imports")
            self.assertEqual(decision.blockers, ["missing-import"])
            self.assertIsNotNone(decision.next_work_order)
            self.assertEqual(decision.next_work_order["goal"], "Fix imports")


class TestCcManagerBridgeName(unittest.TestCase):
    """Test name method."""

    def test_name_returns_cc(self):
        self.assertEqual(CcManagerBridge.name(), "cc")


if __name__ == "__main__":
    unittest.main()
