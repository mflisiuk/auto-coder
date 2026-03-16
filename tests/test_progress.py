"""Tests for repo-visible work progress reporting."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from auto_coder.progress import render_work_progress
from auto_coder.storage import ensure_database, set_task_runtime


class TestWorkProgress(unittest.TestCase):
    def test_render_marks_completed_task_with_timestamp_and_duration(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks_path = root / "tasks.yaml"
            tasks_path.write_text(
                yaml.dump(
                    {
                        "tasks": [
                            {
                                "id": "task-1",
                                "title": "Task 1",
                                "acceptance_criteria": ["Ship the first endpoint."],
                            }
                        ]
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            db_path = root / "state.db"
            ensure_database(db_path)
            set_task_runtime(
                db_path,
                task_id="task-1",
                title="Task 1",
                priority=10,
                status="completed",
                payload={
                    "first_started_at": "2026-03-16T10:00:00+00:00",
                    "completed_at": "2026-03-16T10:30:00+00:00",
                    "elapsed_seconds": 1800,
                },
            )

            output = render_work_progress(
                tasks_path=tasks_path,
                state_db_path=db_path,
                task_overrides={},
            )

            self.assertIn("| task-1 | Task 1 | Ship the first endpoint. | yes |", output)
            self.assertIn("2026-03-16T10:30:00+00:00", output)
            self.assertIn("30m 0s", output)


if __name__ == "__main__":
    unittest.main()
