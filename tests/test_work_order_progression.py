"""Tests for work-order reuse across ticks."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_coder.config import AUTO_CODER_DIR, load_config
from auto_coder.orchestrator import _prepare_work_order
from auto_coder.storage import ensure_database, upsert_work_order


class TestWorkOrderProgression(unittest.TestCase):
    def test_existing_queued_work_order_is_reused(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            acd = root / AUTO_CODER_DIR
            acd.mkdir(parents=True, exist_ok=True)
            ensure_database(acd / "state.db")
            config = load_config(root)
            upsert_work_order(
                config["state_db_path"],
                work_order_id="task-1-wo-02",
                task_id="task-1",
                status="queued",
                sequence_no=2,
                payload={
                    "id": "task-1-wo-02",
                    "task_id": "task-1",
                    "sequence_no": 2,
                    "goal": "Fix the missing edge case.",
                    "manager_feedback": "Handle empty input.",
                    "status": "queued",
                },
            )
            work_order = _prepare_work_order(
                config,
                {"id": "task-1", "title": "Task 1", "prompt": "Base goal"},
                manager_backend=None,
            )
            self.assertEqual(work_order["id"], "task-1-wo-02")
            self.assertEqual(work_order["manager_feedback"], "Handle empty input.")


if __name__ == "__main__":
    unittest.main()
