"""Tests for task graph validation."""
from __future__ import annotations

import unittest

from auto_coder.task_graph import validate_task_graph


class TestTaskGraph(unittest.TestCase):
    def test_rejects_unknown_dependency(self):
        errors = validate_task_graph(
            [
                {"id": "a", "depends_on": ["b"]},
                {"id": "b", "depends_on": []},
            ][0:1]
        )
        self.assertTrue(any("unknown dependency" in error for error in errors))

    def test_rejects_cycle(self):
        errors = validate_task_graph(
            [
                {"id": "a", "depends_on": ["b"]},
                {"id": "b", "depends_on": ["a"]},
            ]
        )
        self.assertTrue(any("cycle detected" in error for error in errors))

    def test_accepts_valid_graph(self):
        errors = validate_task_graph(
            [
                {"id": "a", "depends_on": []},
                {"id": "b", "depends_on": ["a"]},
            ]
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
