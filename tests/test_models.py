"""Tests for domain model parsing."""
from __future__ import annotations

import unittest

from auto_coder.models import AttemptStatus, TaskSpec, TaskStatus, WorkOrderSpec, WorkOrderStatus


class TestEnums(unittest.TestCase):
    def test_status_values_are_strings(self):
        self.assertEqual(TaskStatus.READY, "ready")
        self.assertEqual(WorkOrderStatus.QUEUED, "queued")
        self.assertEqual(AttemptStatus.APPROVED, "approved")


class TestTaskSpec(unittest.TestCase):
    def test_from_mapping_supports_legacy_keys(self):
        spec = TaskSpec.from_mapping(
            {
                "id": "task-1",
                "title": "Task One",
                "preferred_provider": "ccg",
                "test_commands": ["python3 -m pytest tests/"],
                "max_total_attempts": 4,
            }
        )
        self.assertEqual(spec.preferred_workers, ["ccg"])
        self.assertEqual(spec.baseline_commands, ["python3 -m pytest tests/"])
        self.assertEqual(spec.max_attempts_total, 4)

    def test_to_mapping_round_trips_core_fields(self):
        spec = TaskSpec(id="task-1", title="Task One", preferred_workers=["cch"])
        payload = spec.to_mapping()
        self.assertEqual(payload["id"], "task-1")
        self.assertEqual(payload["preferred_workers"], ["cch"])


class TestWorkOrderSpec(unittest.TestCase):
    def test_round_trip(self):
        spec = WorkOrderSpec(
            id="task-1-wo-01",
            task_id="task-1",
            sequence_no=1,
            goal="Do the thing",
            manager_feedback="Fix edge case",
            selected_worker="cch",
        )
        payload = spec.to_mapping()
        restored = WorkOrderSpec.from_mapping(payload)
        self.assertEqual(restored.id, "task-1-wo-01")
        self.assertEqual(restored.selected_worker, "cch")
        self.assertEqual(restored.manager_feedback, "Fix edge case")


if __name__ == "__main__":
    unittest.main()
