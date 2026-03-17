"""Tests for planner task schema validation."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_coder.config import AUTO_CODER_DIR, load_config
from auto_coder.planner import Planner
from auto_coder.policy import validate_baseline_spec


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
                        "setup_commands": ["python3 -c 'print(1)'"],
                        "baseline_commands": ["python3 -m unittest"],
                        "completion_commands": ["python3 -m unittest"],
                        "acceptance_criteria": ["done"],
                        "allow_no_changes": True,
                        "report_only": True,
                        "prompt": "Do the task",
                    }
                ]
            )
            self.assertEqual(tasks[0]["id"], "task-1")
            self.assertTrue(tasks[0]["allow_no_changes"])
            self.assertTrue(tasks[0]["report_only"])
            self.assertEqual(tasks[0]["setup_commands"], ["python3 -c 'print(1)'"])


class TestValidateBaselineSpec(unittest.TestCase):
    def test_no_warnings_when_baseline_empty(self):
        task = {"id": "t1", "allowed_paths": ["tests/"], "baseline_commands": []}
        with TemporaryDirectory() as tmp:
            warnings = validate_baseline_spec(task, Path(tmp))
        self.assertEqual(warnings, [])

    def test_no_warnings_when_file_exists(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "tests" / "test_foo.py").write_text("")
            task = {
                "id": "t1",
                "allowed_paths": ["tests/"],
                "baseline_commands": ["python3 -m pytest tests/test_foo.py"],
            }
            warnings = validate_baseline_spec(task, root)
        self.assertEqual(warnings, [])

    def test_warns_when_file_missing_and_in_allowed_paths(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = {
                "id": "t1",
                "allowed_paths": ["tests/"],
                "baseline_commands": ["python3 -m pytest tests/test_foo.py"],
            }
            warnings = validate_baseline_spec(task, root)
        self.assertEqual(len(warnings), 1)
        self.assertIn("tests/test_foo.py", warnings[0])
        self.assertIn("baseline_commands: []", warnings[0])

    def test_no_warnings_when_file_missing_but_not_in_allowed_paths(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = {
                "id": "t1",
                "allowed_paths": ["src/"],
                "baseline_commands": ["python3 -m pytest tests/test_foo.py"],
            }
            warnings = validate_baseline_spec(task, root)
        self.assertEqual(warnings, [])

    def test_ignores_flags_and_bare_module_names(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = {
                "id": "t1",
                "allowed_paths": ["tests/"],
                "baseline_commands": ["python3 -m pytest -q --tb=short"],
            }
            warnings = validate_baseline_spec(task, root)
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
