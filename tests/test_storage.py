"""Tests for SQLite storage bootstrap."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_coder.storage import ensure_database, list_tables


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


if __name__ == "__main__":
    unittest.main()
