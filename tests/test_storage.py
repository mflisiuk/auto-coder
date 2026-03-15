"""Tests for SQLite storage bootstrap."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_coder.storage import (
    ensure_database,
    get_task_runtime,
    latest_work_order_for_task,
    list_attempts_for_task,
    list_tables,
    load_manager_messages,
    record_attempt,
    save_manager_messages,
    set_task_runtime,
    upsert_work_order,
)


class TestStorage(unittest.TestCase):
    def test_ensure_database_creates_file(self):
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".auto-coder" / "state.db"
            ensure_database(db_path)
            self.assertTrue(db_path.exists())

    def test_schema_contains_required_tables(self):
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.db"
            ensure_database(db_path)
            tables = set(list_tables(db_path))
            self.assertTrue(
                {
                    "tasks",
                    "work_orders",
                    "attempts",
                    "run_ticks",
                    "leases",
                    "manager_threads",
                    "provider_usage",
                    "quota_snapshots",
                    "events",
                    "artifacts",
                }.issubset(tables)
            )

    def test_task_runtime_and_work_order_round_trip(self):
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.db"
            ensure_database(db_path)
            set_task_runtime(
                db_path,
                task_id="task-1",
                title="Task 1",
                priority=10,
                status="waiting_for_retry",
                payload={"attempt_count": 1},
            )
            upsert_work_order(
                db_path,
                work_order_id="task-1-wo-01",
                task_id="task-1",
                status="retry_pending",
                sequence_no=1,
                payload={"goal": "Implement feature"},
            )
            task_row = get_task_runtime(db_path, "task-1")
            work_order = latest_work_order_for_task(db_path, "task-1")
            self.assertIsNotNone(task_row)
            self.assertEqual(task_row["status"], "waiting_for_retry")
            self.assertIsNotNone(work_order)
            self.assertEqual(work_order["status"], "retry_pending")

    def test_attempts_and_manager_messages_round_trip(self):
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.db"
            ensure_database(db_path)
            record_attempt(
                db_path,
                task_id="task-1",
                work_order_id="task-1-wo-01",
                run_tick_id="run-1",
                status="review_failed",
                worker_name="cch",
                failure_signature="review_failed:missing edge case",
                payload={"note": "retry"},
            )
            save_manager_messages(
                db_path,
                task_id="task-1",
                manager_backend="anthropic",
                messages=[{"role": "assistant", "content": "Fix edge case"}],
            )
            attempts = list_attempts_for_task(db_path, "task-1")
            messages = load_manager_messages(
                db_path,
                task_id="task-1",
                manager_backend="anthropic",
            )
            self.assertEqual(len(attempts), 1)
            self.assertEqual(attempts[0]["work_order_id"], "task-1-wo-01")
            self.assertEqual(messages[0]["content"], "Fix edge case")


if __name__ == "__main__":
    unittest.main()
