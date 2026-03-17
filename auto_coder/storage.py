"""SQLite storage bootstrap and small helpers for auto-coder."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ready',
    priority INTEGER NOT NULL DEFAULT 100,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS work_orders (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    sequence_no INTEGER NOT NULL DEFAULT 1,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    work_order_id TEXT,
    run_tick_id TEXT,
    status TEXT NOT NULL,
    worker_name TEXT,
    failure_signature TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS run_ticks (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'started',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS leases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    run_tick_id TEXT NOT NULL,
    owner_pid INTEGER,
    heartbeat_at TEXT,
    expires_at TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS manager_threads (
    task_id TEXT NOT NULL,
    manager_backend TEXT NOT NULL,
    thread_key TEXT NOT NULL,
    external_thread_id TEXT,
    state_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(task_id, manager_backend, thread_key)
);

CREATE TABLE IF NOT EXISTS provider_usage (
    provider TEXT NOT NULL,
    usage_date TEXT NOT NULL,
    tokens INTEGER NOT NULL DEFAULT 0,
    calls INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(provider, usage_date)
);

CREATE TABLE IF NOT EXISTS quota_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    quota_state TEXT NOT NULL,
    usage_ratio REAL,
    retry_after TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_database(db_path: Path) -> Path:
    """Create the SQLite database and schema if it does not exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
    return db_path


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Yield a connection with row access by column name."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def list_tables(db_path: Path) -> list[str]:
    """Return tables currently present in the database."""
    if not db_path.exists():
        return []
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
    return [str(row["name"]) for row in rows]


def sync_tasks(db_path: Path, tasks: list[dict]) -> None:
    """Upsert tasks from the current backlog into SQLite."""
    ensure_database(db_path)
    with connect(db_path) as conn:
        for task in tasks:
            task_id = str(task["id"])
            title = str(task.get("title", task_id))
            priority = int(task.get("priority", 100))
            existing = conn.execute(
                "SELECT payload_json FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            existing_payload: dict = {}
            if existing and existing["payload_json"]:
                try:
                    existing_payload = json.loads(str(existing["payload_json"]))
                except Exception:
                    existing_payload = {}
            payload_json = json.dumps({**existing_payload, **task}, ensure_ascii=False)
            conn.execute(
                """
                INSERT INTO tasks (id, title, priority, payload_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    priority = excluded.priority,
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (task_id, title, priority, payload_json),
            )
        conn.commit()


def set_task_runtime(
    db_path: Path,
    *,
    task_id: str,
    title: str,
    priority: int,
    status: str,
    payload: dict,
) -> None:
    ensure_database(db_path)
    payload_json = json.dumps(payload, ensure_ascii=False)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO tasks (id, title, status, priority, payload_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                status = excluded.status,
                priority = excluded.priority,
                payload_json = excluded.payload_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (task_id, title, status, priority, payload_json),
        )
        conn.commit()


def list_task_runtime(db_path: Path) -> list[sqlite3.Row]:
    if not db_path.exists():
        return []
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, title, status, priority, payload_json, updated_at FROM tasks ORDER BY priority, id"
        ).fetchall()
    return rows


def list_task_specs(db_path: Path) -> list[dict]:
    """Return task payloads from SQLite ordered like the scheduler sees them."""
    specs: list[dict] = []
    for row in list_task_runtime(db_path):
        try:
            payload = json.loads(str(row["payload_json"])) if row["payload_json"] else {}
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("id", str(row["id"]))
        payload.setdefault("title", str(row["title"]))
        payload.setdefault("priority", int(row["priority"]))
        payload.setdefault("enabled", True)
        payload["status"] = str(row["status"])
        specs.append(payload)
    return specs


def get_task_runtime(db_path: Path, task_id: str) -> sqlite3.Row | None:
    if not db_path.exists():
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT id, title, status, priority, payload_json, updated_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    return row


def get_task_last_attempt_time(db_path: Path, task_id: str) -> str | None:
    """Get the most recent attempt's updated_at timestamp for a task."""
    if not db_path.exists():
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            """SELECT updated_at FROM attempts
               WHERE task_id = ?
               ORDER BY updated_at DESC
               LIMIT 1""",
            (task_id,),
        ).fetchone()
        return str(row["updated_at"]) if row else None


def list_task_runtime_with_attempts(db_path: Path) -> list[dict]:
    """Return task runtime info with latest attempt timestamp."""
    if not db_path.exists():
        return []
    with connect(db_path) as conn:
        rows = conn.execute(
            """SELECT t.id, t.title, t.status, t.priority, t.payload_json, t.updated_at,
                      a.updated_at as last_attempt_at
               FROM tasks t
               LEFT JOIN (
                   SELECT task_id, MAX(updated_at) as updated_at
                   FROM attempts
                   GROUP BY task_id
               ) a ON t.id = a.task_id
               ORDER BY t.priority, t.id"""
        ).fetchall()
        return [dict(row) for row in rows]


def count_tasks_by_status(db_path: Path) -> dict[str, int]:
    """Count tasks grouped by status."""
    if not db_path.exists():
        return {}
    with connect(db_path) as conn:
        rows = conn.execute(
            """SELECT status, COUNT(*) as count FROM tasks GROUP BY status"""
        ).fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}


def upsert_work_order(
    db_path: Path,
    *,
    work_order_id: str,
    task_id: str,
    status: str,
    sequence_no: int,
    payload: dict,
) -> None:
    ensure_database(db_path)
    payload_json = json.dumps(payload, ensure_ascii=False)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO work_orders (id, task_id, status, sequence_no, payload_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                task_id = excluded.task_id,
                status = excluded.status,
                sequence_no = excluded.sequence_no,
                payload_json = excluded.payload_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (work_order_id, task_id, status, sequence_no, payload_json),
        )
        conn.commit()


def get_work_order(db_path: Path, work_order_id: str) -> sqlite3.Row | None:
    if not db_path.exists():
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, task_id, status, sequence_no, payload_json, created_at, updated_at
            FROM work_orders
            WHERE id = ?
            """,
            (work_order_id,),
        ).fetchone()
    return row


def list_work_orders_for_task(db_path: Path, task_id: str) -> list[sqlite3.Row]:
    if not db_path.exists():
        return []
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, task_id, status, sequence_no, payload_json, created_at, updated_at
            FROM work_orders
            WHERE task_id = ?
            ORDER BY sequence_no, id
            """,
            (task_id,),
        ).fetchall()
    return rows


def latest_work_order_for_task(db_path: Path, task_id: str) -> sqlite3.Row | None:
    rows = list_work_orders_for_task(db_path, task_id)
    return rows[-1] if rows else None


def create_run_tick(db_path: Path, run_tick_id: str, *, status: str = "started", payload: dict | None = None) -> None:
    ensure_database(db_path)
    payload_json = json.dumps(payload or {}, ensure_ascii=False)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO run_ticks (id, status, payload_json)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                payload_json = excluded.payload_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (run_tick_id, status, payload_json),
        )
        conn.commit()


def update_run_tick(db_path: Path, run_tick_id: str, *, status: str, payload: dict | None = None) -> None:
    ensure_database(db_path)
    payload_json = json.dumps(payload or {}, ensure_ascii=False)
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE run_ticks
            SET status = ?, payload_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, payload_json, run_tick_id),
        )
        conn.commit()


def list_run_ticks(db_path: Path, *, limit: int = 20) -> list[sqlite3.Row]:
    if not db_path.exists():
        return []
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, status, payload_json, created_at, updated_at
            FROM run_ticks
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return rows


def get_run_tick(db_path: Path, run_tick_id: str) -> sqlite3.Row | None:
    if not db_path.exists():
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, status, payload_json, created_at, updated_at
            FROM run_ticks
            WHERE id = ?
            """,
            (run_tick_id,),
        ).fetchone()
    return row


def record_attempt(
    db_path: Path,
    *,
    task_id: str,
    run_tick_id: str,
    status: str,
    payload: dict | None = None,
    worker_name: str | None = None,
    failure_signature: str | None = None,
    work_order_id: str | None = None,
) -> None:
    ensure_database(db_path)
    payload_json = json.dumps(payload or {}, ensure_ascii=False)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO attempts (task_id, work_order_id, run_tick_id, status, worker_name, failure_signature, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, work_order_id, run_tick_id, status, worker_name, failure_signature, payload_json),
        )
        conn.commit()


def list_attempts_for_task(db_path: Path, task_id: str) -> list[sqlite3.Row]:
    if not db_path.exists():
        return []
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, task_id, work_order_id, run_tick_id, status, worker_name, failure_signature, payload_json, created_at, updated_at
            FROM attempts
            WHERE task_id = ?
            ORDER BY id
            """,
            (task_id,),
        ).fetchall()
    return rows


def force_task_retry(db_path: Path, task_id: str, *, note: str, retry_after: str) -> bool:
    if not db_path.exists():
        return False
    with connect(db_path) as conn:
        conn.execute(
            "DELETE FROM leases WHERE resource_type = ? AND resource_id = ?",
            ("task", task_id),
        )
        row = conn.execute(
            "SELECT id, title, priority, payload_json FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if not row:
            return False
        try:
            payload = json.loads(str(row["payload_json"])) if row["payload_json"] else {}
        except Exception:
            payload = {}
        payload["note"] = note
        payload["retry_after"] = retry_after
        payload.pop("runtime_depends_on", None)
        payload.pop("repair_task_id", None)
        payload.pop("repair_task_kind", None)
        conn.execute(
            """
            UPDATE tasks
            SET status = 'waiting_for_retry', payload_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (json.dumps(payload, ensure_ascii=False), task_id),
        )
        latest_work_order = conn.execute(
            """
            SELECT id, payload_json
            FROM work_orders
            WHERE task_id = ?
            ORDER BY sequence_no DESC, id DESC
            LIMIT 1
            """,
            (task_id,),
        ).fetchone()
        if latest_work_order:
            try:
                work_order_payload = json.loads(str(latest_work_order["payload_json"])) if latest_work_order["payload_json"] else {}
            except Exception:
                work_order_payload = {}
            work_order_payload["forced_retry"] = True
            conn.execute(
                """
                UPDATE work_orders
                SET status = 'retry_pending', payload_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (json.dumps(work_order_payload, ensure_ascii=False), str(latest_work_order["id"])),
            )
        conn.commit()
    return True


def export_state(db_path: Path) -> dict:
    """Build a lightweight state.json-compatible snapshot from SQLite."""
    state: dict[str, object] = {"tasks": {}, "runs": []}
    if not db_path.exists():
        return state
    with connect(db_path) as conn:
        task_rows = conn.execute(
            "SELECT id, status, payload_json, updated_at FROM tasks ORDER BY priority, id"
        ).fetchall()
        run_rows = conn.execute(
            "SELECT id, status, payload_json, updated_at FROM run_ticks ORDER BY created_at, id"
        ).fetchall()

    tasks_payload: dict[str, dict] = {}
    for row in task_rows:
        try:
            payload = json.loads(str(row["payload_json"])) if row["payload_json"] else {}
        except Exception:
            payload = {}
        tasks_payload[str(row["id"])] = {
            **payload,
            "status": str(row["status"]),
            "updated_at": str(row["updated_at"] or payload.get("updated_at") or ""),
        }
    state["tasks"] = tasks_payload

    runs_payload: list[dict] = []
    for row in run_rows:
        try:
            payload = json.loads(str(row["payload_json"])) if row["payload_json"] else {}
        except Exception:
            payload = {}
        runs_payload.append(
            {
                "run_id": str(row["id"]),
                "task_id": payload.get("task_id"),
                "status": str(row["status"]),
                "updated_at": str(row["updated_at"] or ""),
                "note": payload.get("note", ""),
                **payload,
            }
        )
    state["runs"] = runs_payload
    return state


def acquire_lease(
    db_path: Path,
    *,
    resource_type: str,
    resource_id: str,
    run_tick_id: str,
    expires_at: str,
) -> bool:
    ensure_database(db_path)
    now_expr = "CURRENT_TIMESTAMP"
    now_iso = _now_iso()
    with connect(db_path) as conn:
        conn.execute(
            "DELETE FROM leases WHERE resource_type = ? AND resource_id = ? AND expires_at IS NOT NULL AND expires_at <= ?",
            (resource_type, resource_id, now_iso),
        )
        existing = conn.execute(
            "SELECT id FROM leases WHERE resource_type = ? AND resource_id = ?",
            (resource_type, resource_id),
        ).fetchone()
        if existing:
            conn.commit()
            return False
        conn.execute(
            """
            INSERT INTO leases (resource_type, resource_id, run_tick_id, owner_pid, heartbeat_at, expires_at, payload_json)
            VALUES (?, ?, ?, ?, {now_expr}, ?, '{}')
            """.replace("{now_expr}", now_expr),
            (resource_type, resource_id, run_tick_id, os.getpid(), expires_at),
        )
        conn.commit()
        return True


def release_lease(db_path: Path, *, resource_type: str, resource_id: str) -> None:
    if not db_path.exists():
        return
    with connect(db_path) as conn:
        conn.execute(
            "DELETE FROM leases WHERE resource_type = ? AND resource_id = ?",
            (resource_type, resource_id),
        )
        conn.commit()


def save_manager_messages(
    db_path: Path,
    *,
    task_id: str,
    manager_backend: str,
    messages: list[dict],
    external_thread_id: str | None = None,
    thread_key: str = "default",
) -> None:
    ensure_database(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO manager_threads (task_id, manager_backend, thread_key, external_thread_id, state_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(task_id, manager_backend, thread_key) DO UPDATE SET
                external_thread_id = excluded.external_thread_id,
                state_json = excluded.state_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                task_id,
                manager_backend,
                thread_key,
                external_thread_id,
                json.dumps({"messages": messages}, ensure_ascii=False),
            ),
        )
        conn.commit()


def load_manager_messages(
    db_path: Path,
    *,
    task_id: str,
    manager_backend: str,
    thread_key: str = "default",
) -> list[dict]:
    if not db_path.exists():
        return []
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT state_json
            FROM manager_threads
            WHERE task_id = ? AND manager_backend = ? AND thread_key = ?
            """,
            (task_id, manager_backend, thread_key),
        ).fetchone()
    if not row:
        return []
    try:
        payload = json.loads(str(row["state_json"]))
    except Exception:
        return []
    messages = payload.get("messages", [])
    return list(messages) if isinstance(messages, list) else []


def load_manager_thread(
    db_path: Path,
    *,
    task_id: str,
    manager_backend: str,
    thread_key: str = "default",
) -> dict[str, object] | None:
    if not db_path.exists():
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT external_thread_id, state_json, updated_at
            FROM manager_threads
            WHERE task_id = ? AND manager_backend = ? AND thread_key = ?
            """,
            (task_id, manager_backend, thread_key),
        ).fetchone()
    if not row:
        return None
    try:
        payload = json.loads(str(row["state_json"]))
    except Exception:
        payload = {}
    return {
        "external_thread_id": row["external_thread_id"],
        "messages": list(payload.get("messages", [])) if isinstance(payload.get("messages", []), list) else [],
        "updated_at": row["updated_at"],
    }


def record_quota_snapshot(
    db_path: Path,
    *,
    provider: str,
    quota_state: str,
    usage_ratio: float | None,
    retry_after: str | None = None,
    payload: dict | None = None,
) -> None:
    ensure_database(db_path)
    payload_json = json.dumps({**(payload or {}), "retry_after": retry_after}, ensure_ascii=False)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO quota_snapshots (provider, quota_state, usage_ratio, retry_after, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (provider, quota_state, usage_ratio, retry_after, payload_json),
        )
        conn.commit()


def latest_quota_snapshots(db_path: Path) -> list[sqlite3.Row]:
    if not db_path.exists():
        return []
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT q1.provider, q1.quota_state, q1.usage_ratio, q1.retry_after, q1.payload_json, q1.created_at
            FROM quota_snapshots q1
            INNER JOIN (
                SELECT provider, MAX(id) AS max_id
                FROM quota_snapshots
                GROUP BY provider
            ) q2 ON q1.provider = q2.provider AND q1.id = q2.max_id
            ORDER BY q1.provider
            """
        ).fetchall()
    return rows


def update_lease_heartbeat(db_path: Path, *, resource_type: str, resource_id: str) -> None:
    """Renew the heartbeat timestamp for an active lease so it is not expired."""
    if not db_path.exists():
        return
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE leases SET heartbeat_at = CURRENT_TIMESTAMP WHERE resource_type = ? AND resource_id = ?",
            (resource_type, resource_id),
        )
        conn.commit()


def expire_stale_leases(db_path: Path, *, heartbeat_grace_seconds: int = 90) -> list[sqlite3.Row]:
    """Expire leases whose expires_at has passed AND whose heartbeat is stale.

    A lease with a recent heartbeat is considered still-active even if expires_at
    has technically passed, preventing false interruptions of long-running workers.
    """
    if not db_path.exists():
        return []
    now_iso = _now_iso()
    heartbeat_cutoff = (
        datetime.now(timezone.utc) - timedelta(seconds=heartbeat_grace_seconds)
    ).replace(microsecond=0).isoformat()
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, resource_type, resource_id, run_tick_id, expires_at
            FROM leases
            WHERE expires_at IS NOT NULL AND expires_at <= ?
              AND (heartbeat_at IS NULL OR heartbeat_at <= ?)
            """,
            (now_iso, heartbeat_cutoff),
        ).fetchall()
        conn.execute(
            "DELETE FROM leases WHERE expires_at IS NOT NULL AND expires_at <= ? AND (heartbeat_at IS NULL OR heartbeat_at <= ?)",
            (now_iso, heartbeat_cutoff),
        )
        conn.commit()
    return rows


def recover_interrupted_runs(db_path: Path) -> dict[str, list[str]]:
    """Mark stale in-flight runtime records as interrupted before a new tick starts."""
    ensure_database(db_path)
    stale_run_ids: list[str] = []
    stale_task_ids: list[str] = []
    stale_work_order_ids: list[str] = []

    expired_leases = expire_stale_leases(db_path)
    stale_run_ids.extend(str(row["run_tick_id"]) for row in expired_leases if row["run_tick_id"])

    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, payload_json
            FROM run_ticks
            WHERE status IN ('started', 'running')
            """
        ).fetchall()
        for row in rows:
            run_id = str(row["id"])
            if run_id not in stale_run_ids:
                stale_run_ids.append(run_id)
            try:
                payload = json.loads(str(row["payload_json"])) if row["payload_json"] else {}
            except Exception:
                payload = {}
            task_id = payload.get("task_id")
            work_order_id = payload.get("work_order_id")
            if task_id and task_id not in stale_task_ids:
                stale_task_ids.append(str(task_id))
            if work_order_id and work_order_id not in stale_work_order_ids:
                stale_work_order_ids.append(str(work_order_id))

        if stale_run_ids:
            # Release leases held by interrupted runs so the next run can acquire them.
            conn.executemany(
                "DELETE FROM leases WHERE run_tick_id = ?",
                [(run_id,) for run_id in stale_run_ids],
            )
            conn.executemany(
                """
                UPDATE run_ticks
                SET status = 'interrupted', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                [(run_id,) for run_id in stale_run_ids],
            )
            conn.executemany(
                """
                UPDATE attempts
                SET status = 'interrupted', updated_at = CURRENT_TIMESTAMP
                WHERE run_tick_id = ? AND status = 'started'
                """,
                [(run_id,) for run_id in stale_run_ids],
            )

        if stale_task_ids:
            task_rows = conn.execute(
                f"""
                SELECT id, title, priority, payload_json
                FROM tasks
                WHERE id IN ({",".join("?" for _ in stale_task_ids)})
                """,
                stale_task_ids,
            ).fetchall()
            for row in task_rows:
                try:
                    payload = json.loads(str(row["payload_json"])) if row["payload_json"] else {}
                except Exception:
                    payload = {}
                payload["note"] = "Recovered from interrupted run."
                payload["updated_at"] = "recovered"
                conn.execute(
                    """
                    UPDATE tasks
                    SET status = 'waiting_for_retry', payload_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (json.dumps(payload, ensure_ascii=False), str(row["id"])),
                )

        if stale_work_order_ids:
            rows = conn.execute(
                f"""
                SELECT id, payload_json
                FROM work_orders
                WHERE id IN ({",".join("?" for _ in stale_work_order_ids)})
                """,
                stale_work_order_ids,
            ).fetchall()
            for row in rows:
                try:
                    payload = json.loads(str(row["payload_json"])) if row["payload_json"] else {}
                except Exception:
                    payload = {}
                payload["recovered"] = True
                conn.execute(
                    """
                    UPDATE work_orders
                    SET status = 'retry_pending', payload_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (json.dumps(payload, ensure_ascii=False), str(row["id"])),
                )

        conn.commit()

    return {
        "run_tick_ids": stale_run_ids,
        "task_ids": stale_task_ids,
        "work_order_ids": stale_work_order_ids,
    }
