"""Claude Code (cc) manager backend using a small bridge process."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from auto_coder.config import SUPPORTED_WORKERS
from auto_coder.managers.base import ManagerBackend, ReviewDecision
from auto_coder.storage import load_manager_thread, save_manager_messages


class CcManagerBridge(ManagerBackend):
    def __init__(self, *, task_id: str, task: dict[str, Any], config: dict[str, Any], state_path: Path):
        self.task_id = task_id
        self.task = task
        self.config = config
        self.state_path = state_path
        self.state_db_path: Path | None = config.get("state_db_path")
        thread = self.load_thread(task_id)
        self._messages = list(thread.get("messages", [])) if thread else []
        self._thread_id = str(thread.get("external_thread_id") or "") if thread else ""

    @classmethod
    def name(cls) -> str:
        return "cc"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("claude") is not None

    @classmethod
    def probe_live(cls, config: dict[str, Any]) -> str:
        response = cls._run_bridge_action(
            config=config,
            action="probe-live",
            payload={
                "cwd": str(config["project_root"]),
                "model": config.get("manager_model"),
            },
        )
        result = dict(response.get("result") or {})
        if result.get("status") != "ok":
            raise RuntimeError(f"cc probe returned unexpected payload: {result}")
        return json.dumps(result, ensure_ascii=False)

    def create_work_order(
        self,
        task: dict[str, Any],
        history: list[dict[str, Any]],
        repo_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self._call_bridge(
            "create-work-order",
            {
                "task": task,
                "history": history,
                "repo_context": repo_context or {},
                "cwd": str((repo_context or {}).get("project_root") or self.config["project_root"]),
                "model": self.config.get("manager_model"),
                "default_worker": self.config.get("default_worker", "ccg"),
                "thread_id": self._thread_id or None,
            },
        )
        result = dict(response["result"])
        sequence_no = max(
            [int(entry.get("sequence_no", 0)) for entry in history if entry.get("kind") == "work_order"],
            default=0,
        ) + 1
        selected_worker = self._resolve_worker_name(
            result.get("selected_worker"),
            task=task,
        )
        work_order = {
            "id": f"{task.get('id')}-wo-{sequence_no:02d}",
            "task_id": task.get("id"),
            "sequence_no": sequence_no,
            "goal": str(result.get("goal") or task.get("prompt", "")),
            "scope_summary": str(result.get("scope_summary") or task.get("title", task.get("id"))),
            "allowed_paths": list(result.get("allowed_paths") or task.get("allowed_paths", [])),
            "completion_commands": list(result.get("completion_commands") or task.get("completion_commands", task.get("test_commands", []))),
            "selected_worker": str(selected_worker),
            "manager_feedback": str(result.get("manager_feedback") or ""),
            "status": "queued",
            "created_by": self.name(),
        }
        self._append_message(
            role="assistant",
            content=json.dumps({"action": "create_work_order", "work_order": work_order}, ensure_ascii=False),
        )
        self._save_thread_state()
        return work_order

    def review_attempt(
        self,
        task: dict[str, Any],
        work_order: dict[str, Any],
        attempt_context: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> ReviewDecision:
        response = self._call_bridge(
            "review-attempt",
            {
                "task": task,
                "work_order": work_order,
                "attempt_context": attempt_context,
                "history": history,
                "cwd": str(self.config["project_root"]),
                "model": self.config.get("manager_model"),
                "thread_id": self._thread_id or None,
            },
        )
        result = dict(response["result"])
        next_work_order = None
        if isinstance(result.get("next_work_order"), dict):
            sequence_no = max(
                [int(entry.get("sequence_no", 0)) for entry in history if entry.get("kind") == "work_order"],
                default=0,
            ) + 1
            next_work_order = {
                "id": f"{task.get('id')}-wo-{sequence_no:02d}",
                "task_id": task.get("id"),
                "sequence_no": sequence_no,
                "goal": str(result["next_work_order"].get("goal") or task.get("prompt", "")),
                "scope_summary": str(result["next_work_order"].get("scope_summary") or task.get("title", task.get("id"))),
                "allowed_paths": list(result["next_work_order"].get("allowed_paths") or task.get("allowed_paths", [])),
                "completion_commands": list(
                    result["next_work_order"].get("completion_commands")
                    or task.get("completion_commands", task.get("test_commands", []))
                ),
                "selected_worker": self._resolve_worker_name(
                    result["next_work_order"].get("selected_worker"),
                    task=task,
                ),
                "manager_feedback": str(result["next_work_order"].get("manager_feedback") or result.get("feedback", "")),
                "status": "queued",
                "created_by": self.name(),
            }
        decision = ReviewDecision(
            verdict=str(result.get("verdict", "retry")),
            feedback=str(result.get("feedback", "")),
            blockers=list(result.get("blockers", [])),
            next_work_order=next_work_order,
            source=self.name(),
        )
        self._append_message(
            role="assistant",
            content=json.dumps({"action": "review_attempt", "decision": decision.verdict, "feedback": decision.feedback}, ensure_ascii=False),
        )
        self._save_thread_state()
        return decision

    def load_thread(self, task_id: str) -> dict[str, object] | None:
        if task_id != self.task_id or not self.state_db_path:
            return None
        return load_manager_thread(
            self.state_db_path,
            task_id=self.task_id,
            manager_backend=self.name(),
        )

    def save_thread(self, task_id: str, thread_state: list[dict[str, Any]]) -> None:
        if task_id != self.task_id or not self.state_db_path:
            return
        self._messages = list(thread_state)
        self._save_thread_state()

    # ----------------------------------------------------------------- helpers

    def _call_bridge(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._append_message(role="user", content=json.dumps({"action": action, "payload": payload}, ensure_ascii=False))
        parsed = self._run_bridge_action(config=self.config, action=action, payload=payload)
        thread_id = parsed.get("thread_id")
        if thread_id:
            self._thread_id = str(thread_id)
        return parsed

    @classmethod
    def _bridge_path(cls, config: dict[str, Any]) -> Path:
        return Path(
            config.get("cc_bridge_path")
            or (Path(__file__).resolve().parents[2] / "bridges" / "cc-manager" / "src" / "index.mjs")
        )

    @classmethod
    def _run_bridge_action(
        cls,
        *,
        config: dict[str, Any],
        action: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        bridge_path = cls._bridge_path(config)
        if not bridge_path.exists():
            raise RuntimeError(f"Cc bridge not found: {bridge_path}")
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump(payload, handle, ensure_ascii=False)
            temp_path = Path(handle.name)
        try:
            result = subprocess.run(
                ["node", str(bridge_path), action, str(temp_path)],
                cwd=str(config["project_root"]),
                capture_output=True,
                text=True,
                timeout=int(config.get("manager_timeout_seconds", 180)),
                check=False,
            )
        finally:
            temp_path.unlink(missing_ok=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Cc bridge failed")
        parsed = json.loads(result.stdout.strip() or "{}")
        return parsed

    def _append_message(self, *, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})

    def _save_thread_state(self) -> None:
        if not self.state_db_path:
            return
        save_manager_messages(
            self.state_db_path,
            task_id=self.task_id,
            manager_backend=self.name(),
            messages=self._messages,
            external_thread_id=self._thread_id or None,
        )

    def _resolve_worker_name(self, requested: object, *, task: dict[str, Any]) -> str:
        requested_name = str(requested or "").strip()
        if requested_name in SUPPORTED_WORKERS:
            return requested_name

        for candidate in task.get("preferred_workers") or []:
            name = str(candidate or "").strip()
            if name in SUPPORTED_WORKERS:
                return name

        default_worker = str(self.config.get("default_worker", "cc")).strip()
        if default_worker in SUPPORTED_WORKERS:
            return default_worker

        fallback_worker = str(self.config.get("fallback_worker", "")).strip()
        if fallback_worker in SUPPORTED_WORKERS:
            return fallback_worker

        return "cc"
