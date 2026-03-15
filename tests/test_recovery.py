"""Tests for runtime recovery before a new tick starts."""
from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_coder.storage import (
    create_run_tick,
    ensure_database,
    recover_interrupted_runs,
    record_attempt,
    set_task_runtime,
    upsert_work_order,
)


class TestRecovery(unittest.TestCase):
    def test_recover_interrupted_runs_marks_runtime_records(self):
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.db"
            ensure_database(db_path)
            set_task_runtime(
                db_path,
                task_id="task-1",
                title="Task 1",
                priority=10,
                status="running",
                payload={"attempt_count": 1},
            )
            upsert_work_order(
                db_path,
                work_order_id="task-1-wo-01",
                task_id="task-1",
                status="running",
                sequence_no=1,
                payload={"goal": "Do it"},
            )
            create_run_tick(
                db_path,
                "run-1",
                status="started",
                payload={"task_id": "task-1", "work_order_id": "task-1-wo-01"},
            )
            record_attempt(
                db_path,
                task_id="task-1",
                work_order_id="task-1-wo-01",
                run_tick_id="run-1",
                status="started",
                payload={},
            )

            recovered = recover_interrupted_runs(db_path)

            self.assertEqual(recovered["run_tick_ids"], ["run-1"])
            with sqlite3.connect(db_path) as conn:
                task_status = conn.execute("SELECT status FROM tasks WHERE id = 'task-1'").fetchone()[0]
                work_order_status = conn.execute("SELECT status FROM work_orders WHERE id = 'task-1-wo-01'").fetchone()[0]
                run_tick_status = conn.execute("SELECT status FROM run_ticks WHERE id = 'run-1'").fetchone()[0]
                attempt_status = conn.execute(
                    "SELECT status FROM attempts WHERE run_tick_id = 'run-1' ORDER BY id DESC LIMIT 1"
                ).fetchone()[0]

            self.assertEqual(task_status, "waiting_for_retry")
            self.assertEqual(work_order_status, "retry_pending")
            self.assertEqual(run_tick_status, "interrupted")
            self.assertEqual(attempt_status, "interrupted")


if __name__ == "__main__":
    unittest.main()
