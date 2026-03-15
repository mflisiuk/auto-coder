"""Tests for deterministic reviewer and manager handoff."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_coder.managers.base import ReviewDecision
from auto_coder.reviewer import deterministic_review, review_attempt


class _FakeManager:
    def __init__(self, decision: ReviewDecision):
        self.decision = decision
        self.called = False

    def review_attempt(self, task, work_order, attempt_context, history):
        self.called = True
        return self.decision


class TestReviewer(unittest.TestCase):
    def test_deterministic_review_rejects_missing_report(self):
        result = deterministic_review(
            {
                "baseline_passed": True,
                "worker_report_present": False,
                "policy_violations": [],
                "completion_passed": True,
            }
        )
        self.assertFalse(result.passed)
        self.assertIn("worker_report_missing", result.blockers)

    def test_manager_is_not_called_when_deterministic_gates_fail(self):
        manager = _FakeManager(ReviewDecision(verdict="approve", feedback="ok"))
        with TemporaryDirectory() as tmp:
            decision = review_attempt(
                task={"id": "t1"},
                work_order={"id": "wo-1"},
                attempt_context={
                    "attempt_no": 1,
                    "baseline_passed": True,
                    "worker_report_present": True,
                    "policy_violations": ["outside_allowed:README.md"],
                    "completion_passed": True,
                },
                history=[],
                manager_backend=manager,
                report_dir=Path(tmp),
            )
        self.assertEqual(decision.verdict, "retry")
        self.assertFalse(manager.called)
        self.assertIn("outside_allowed:README.md", decision.blockers)

    def test_manager_is_called_after_deterministic_pass(self):
        manager = _FakeManager(
            ReviewDecision(
                verdict="retry",
                feedback="Add missing edge case.",
                blockers=["missing_edge_case"],
                next_work_order={"id": "wo-2", "task_id": "t1", "sequence_no": 2},
            )
        )
        with TemporaryDirectory() as tmp:
            decision = review_attempt(
                task={"id": "t1"},
                work_order={"id": "wo-1"},
                attempt_context={
                    "attempt_no": 1,
                    "worker_name": "cch",
                    "worker_returncode": 0,
                    "baseline_passed": True,
                    "worker_report_present": True,
                    "policy_violations": [],
                    "completion_passed": True,
                },
                history=[{"kind": "work_order", "id": "wo-1"}],
                manager_backend=manager,
                report_dir=Path(tmp),
            )
        self.assertTrue(manager.called)
        self.assertEqual(decision.verdict, "retry")
        self.assertEqual(decision.next_work_order["id"], "wo-2")


if __name__ == "__main__":
    unittest.main()
