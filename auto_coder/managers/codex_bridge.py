"""Codex manager backend using a small bridge process."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from auto_coder.managers.base import ManagerBackend, ReviewDecision
from auto_coder.storage import load_manager_thread, save_manager_messages


class CodexManagerBridge(ManagerBackend):
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
        return "codex"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("codex") is not None and shutil.which("node") is not None

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
                "reasoning_effort": self.config.get("codex_reasoning_effort", "medium"),
                "thread_id": self._thread_id or None,
            },
        )
        result = dict(response["result"])
        sequence_no = len([entry for entry in history if entry.get("kind") == "work_order"]) + 1
        selected_worker = result.get("selected_worker") or (
            (task.get("preferred_workers") or [self.config.get("default_worker", "cc")])[0]
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
                "reasoning_effort": self.config.get("codex_reasoning_effort", "medium"),
                "thread_id": self._thread_id or None,
            },
        )
        result = dict(response["result"])
        next_work_order = None
        if isinstance(result.get("next_work_order"), dict):
            sequence_no = len([entry for entry in history if entry.get("kind") == "work_order"]) + 1
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
                "selected_worker": str(
                    result["next_work_order"].get("selected_worker")
                    or (task.get("preferred_workers") or [self.config.get("default_worker", "cc")])[0]
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
        bridge_path = Path(self.config.get("codex_bridge_path") or (Path(__file__).resolve().parents[2] / "bridges" / "codex-manager" / "src" / "index.mjs"))
        if not bridge_path.exists():
            raise RuntimeError(f"Codex bridge not found: {bridge_path}")
        self._append_message(role="user", content=json.dumps({"action": action, "payload": payload}, ensure_ascii=False))
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump(payload, handle, ensure_ascii=False)
            temp_path = Path(handle.name)
        try:
            result = subprocess.run(
                ["node", str(bridge_path), action, str(temp_path)],
                cwd=str(self.config["project_root"]),
                capture_output=True,
                text=True,
                timeout=int(self.config.get("manager_timeout_seconds", 180)),
                check=False,
            )
        finally:
            temp_path.unlink(missing_ok=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Codex bridge failed")
        parsed = json.loads(result.stdout.strip() or "{}")
        thread_id = parsed.get("thread_id")
        if thread_id:
            self._thread_id = str(thread_id)
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
