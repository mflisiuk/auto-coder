"""Tests for planner task schema validation."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_coder.config import AUTO_CODER_DIR, load_config
from auto_coder.planner import Planner


class TestTaskValidation(unittest.TestCase):
    def _planner(self, root: Path) -> Planner:
        (root / AUTO_CODER_DIR).mkdir(parents=True, exist_ok=True)
        return Planner(load_config(root))

    def test_rejects_missing_allowed_paths(self):
        with TemporaryDirectory() as tmp:
            planner = self._planner(Path(tmp))
            with self.assertRaises(RuntimeError):
                planner._validate_tasks(
                    [
                        {
                            "id": "task-1",
                            "title": "Task 1",
                            "depends_on": [],
                            "baseline_commands": ["python3 -m unittest"],
                            "completion_commands": ["python3 -m unittest"],
                            "acceptance_criteria": ["done"],
                            "prompt": "Do the task",
                        }
                    ]
                )

    def test_accepts_complete_task_schema(self):
        with TemporaryDirectory() as tmp:
            planner = self._planner(Path(tmp))
            tasks = planner._validate_tasks(
                [
                    {
                        "id": "task-1",
                        "title": "Task 1",
                        "depends_on": [],
                        "allowed_paths": ["src/"],
                        "baseline_commands": ["python3 -m unittest"],
                        "completion_commands": ["python3 -m unittest"],
                        "acceptance_criteria": ["done"],
                        "prompt": "Do the task",
                    }
                ]
            )
            self.assertEqual(tasks[0]["id"], "task-1")


if __name__ == "__main__":
    unittest.main()
