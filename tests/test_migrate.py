"""Tests for legacy task migration."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from auto_coder.config import AUTO_CODER_DIR, load_config
from auto_coder.migrate import migrate_legacy_tasks
from auto_coder.storage import ensure_database


class TestMigrateLegacyTasks(unittest.TestCase):
    def test_migrate_writes_tasks_local_yaml(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            acd = root / AUTO_CODER_DIR
            acd.mkdir(parents=True, exist_ok=True)
            ensure_database(acd / "state.db")
            legacy_path = root / "legacy.yaml"
            legacy_path.write_text(
                yaml.dump(
                    {
                        "tasks": [
                            {
                                "id": "task-1",
                                "title": "Task 1",
                                "depends_on": [],
                                "allowed_paths": ["auto_coder/"],
                                "baseline_commands": ["python3 -m unittest"],
                                "completion_commands": ["python3 -m unittest"],
                                "acceptance_criteria": ["tests pass"],
                                "prompt": "Add one small change",
                            }
                        ]
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            tasks = migrate_legacy_tasks(load_config(root), legacy_path)

            self.assertEqual(len(tasks), 1)
            payload = yaml.safe_load((acd / "tasks.local.yaml").read_text(encoding="utf-8"))
            self.assertEqual(payload["tasks"][0]["id"], "task-1")


if __name__ == "__main__":
    unittest.main()
