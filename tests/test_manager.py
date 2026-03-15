"""Tests for ManagerBrain: evaluation, persistence, fallback."""
from __future__ import annotations
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from auto_coder.manager import AttemptResult, ManagerBrain, ManagerDecision


def _make_result(**kw) -> AttemptResult:
    defaults = dict(
        attempt_no=1, worker_returncode=0, changed_files=[],
        policy_violations=[], test_results=[], test_stdout={},
        test_stderr={}, diff_patch="", diff_stat="", worker_stdout_excerpt="",
    )
    defaults.update(kw)
    return AttemptResult(**defaults)


def _make_brain(state_path: Path, task_id: str = "t1") -> ManagerBrain:
    task = {"id": task_id, "title": "Test", "allowed_paths": ["src/"]}
    config = {"protected_paths": ["config/"], "allowed_paths": ["src/"]}
    return ManagerBrain(task_id=task_id, task=task, config=config,
                        state_path=state_path, model="claude-opus-4-6")


class TestManagerAvailability(unittest.TestCase):
    def test_false_when_no_key(self):
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(ManagerBrain.is_available())

    def test_true_when_key_present(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            self.assertTrue(ManagerBrain.is_available())


class TestManagerEvaluate(unittest.TestCase):
    def _mock_client(self, response: dict) -> MagicMock:
        msg = MagicMock()
        msg.content = [MagicMock(text=json.dumps(response))]
        client = MagicMock()
        client.messages.create.return_value = msg
        return client

    def test_approve_when_tests_pass(self):
        with TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            brain = _make_brain(state_path)
            client = self._mock_client({"verdict": "approve", "feedback": "Good.", "blockers": []})
            result = _make_result(test_results=[{"command": "pytest", "returncode": 0, "passed": True}])
            with patch("anthropic.Anthropic", return_value=client):
                decision = brain.evaluate_attempt(result)
            self.assertEqual(decision.verdict, "approve")

    def test_retry_when_tests_fail(self):
        with TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            brain = _make_brain(state_path)
            client = self._mock_client({"verdict": "retry", "feedback": "Fix line 5.", "blockers": ["test_foo"]})
            result = _make_result(test_results=[{"command": "pytest", "returncode": 1, "passed": False}],
                                  test_stderr={"pytest": "AssertionError"})
            with patch("anthropic.Anthropic", return_value=client):
                decision = brain.evaluate_attempt(result)
            self.assertEqual(decision.verdict, "retry")

    def test_messages_persist_to_disk(self):
        with TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            brain = _make_brain(state_path)
            client = self._mock_client({"verdict": "retry", "feedback": "Try again.", "blockers": []})
            with patch("anthropic.Anthropic", return_value=client):
                brain.evaluate_attempt(_make_result())
            # reload from disk
            brain2 = _make_brain(state_path)
            self.assertEqual(len(brain2.messages), 2)  # user + assistant
            self.assertTrue(brain2.has_feedback())

    def test_messages_accumulate_across_instances(self):
        with TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            client = self._mock_client({"verdict": "retry", "feedback": "Fix it.", "blockers": []})
            with patch("anthropic.Anthropic", return_value=client):
                brain1 = _make_brain(state_path)
                brain1.evaluate_attempt(_make_result(attempt_no=1))
                brain2 = _make_brain(state_path)  # simulates next cron run
                brain2.evaluate_attempt(_make_result(attempt_no=2))
            brain3 = _make_brain(state_path)
            self.assertEqual(len(brain3.messages), 4)  # 2 user + 2 assistant

    def test_graceful_fallback_on_api_error(self):
        with TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            brain = _make_brain(state_path)
            client = MagicMock()
            client.messages.create.side_effect = RuntimeError("network error")
            with patch("anthropic.Anthropic", return_value=client):
                decision = brain.evaluate_attempt(_make_result())
            self.assertIn(decision.verdict, {"retry", "abandon"})
            self.assertTrue(len(decision.blockers) > 0)

    def test_build_worker_feedback_empty_before_first_call(self):
        with TemporaryDirectory() as tmp:
            brain = _make_brain(Path(tmp) / "state.json")
            self.assertEqual(brain.build_worker_feedback(), "")

    def test_build_worker_feedback_contains_last_feedback(self):
        with TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            brain = _make_brain(state_path)
            client = self._mock_client({"verdict": "retry", "feedback": "Fix auth.py line 12.", "blockers": ["b1"]})
            with patch("anthropic.Anthropic", return_value=client):
                brain.evaluate_attempt(_make_result())
            feedback = brain.build_worker_feedback()
            self.assertIn("MANAGER FEEDBACK", feedback)
            self.assertIn("Fix auth.py", feedback)
            self.assertIn("b1", feedback)


class TestParseDecision(unittest.TestCase):
    def _brain(self, tmp: str) -> ManagerBrain:
        return _make_brain(Path(tmp) / "state.json")

    def test_clean_json(self):
        with TemporaryDirectory() as tmp:
            d = self._brain(tmp)._parse_decision('{"verdict":"approve","feedback":"ok","blockers":[]}')
            self.assertEqual(d.verdict, "approve")

    def test_json_in_prose(self):
        with TemporaryDirectory() as tmp:
            d = self._brain(tmp)._parse_decision('Here: {"verdict":"retry","feedback":"fix","blockers":["b"]}')
            self.assertEqual(d.verdict, "retry")

    def test_malformed_returns_retry(self):
        with TemporaryDirectory() as tmp:
            d = self._brain(tmp)._parse_decision("this is not json")
            self.assertEqual(d.verdict, "retry")
            self.assertIn("malformed_manager_response", d.blockers)


if __name__ == "__main__":
    unittest.main()
