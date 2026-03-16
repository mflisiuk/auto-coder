"""Tests for SQLite storage bootstrap."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_coder.storage import (
    ensure_database,
    export_state,
    force_task_retry,
    get_task_runtime,
    latest_work_order_for_task,
    list_attempts_for_task,
    list_tables,
    latest_quota_snapshots,
    load_manager_messages,
    record_quota_snapshot,
    record_attempt,
    save_manager_messages,
    set_task_runtime,
    sync_tasks,
    upsert_work_order,
    acquire_lease,
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

    def test_latest_quota_snapshots_returns_newest_per_provider(self):
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.db"
            ensure_database(db_path)
            record_quota_snapshot(db_path, provider="ccg", quota_state="healthy", usage_ratio=0.2, payload={})
            record_quota_snapshot(db_path, provider="ccg", quota_state="near_limit", usage_ratio=0.9, payload={})
            rows = latest_quota_snapshots(db_path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["quota_state"], "near_limit")

    def test_sync_tasks_preserves_runtime_payload_fields(self):
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.db"
            ensure_database(db_path)
            set_task_runtime(
                db_path,
                task_id="task-1",
                title="Task 1",
                priority=10,
                status="waiting_for_retry",
                payload={"attempt_count": 2, "retry_after": "2026-03-16T12:00:00+00:00"},
            )
            sync_tasks(
                db_path,
                [{"id": "task-1", "title": "Task 1", "priority": 5, "allowed_paths": ["src/"]}],
            )
            row = get_task_runtime(db_path, "task-1")
            self.assertIsNotNone(row)
            payload = export_state(db_path)["tasks"]["task-1"]
            self.assertEqual(payload["attempt_count"], 2)
            self.assertEqual(payload["retry_after"], "2026-03-16T12:00:00+00:00")

    def test_force_task_retry_releases_existing_task_lease(self):
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
            acquired = acquire_lease(
                db_path,
                resource_type="task",
                resource_id="task-1",
                run_tick_id="run-1",
                expires_at="2099-01-01T00:00:00+00:00",
            )
            self.assertTrue(acquired)
            self.assertTrue(
                force_task_retry(
                    db_path,
                    "task-1",
                    note="retry",
                    retry_after="2026-03-16T12:00:00+00:00",
                )
            )
            reacquired = acquire_lease(
                db_path,
                resource_type="task",
                resource_id="task-1",
                run_tick_id="run-2",
                expires_at="2099-01-01T00:00:00+00:00",
            )
            self.assertTrue(reacquired)


if __name__ == "__main__":
    unittest.main()
