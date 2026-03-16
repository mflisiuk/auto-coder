"""Anthropic-backed manager adapter."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from auto_coder.manager import AttemptResult, ManagerBrain
from auto_coder.managers.base import ManagerBackend, ReviewDecision


class AnthropicManagerBackend(ManagerBackend):
    def __init__(self, *, task_id: str, task: dict[str, Any], config: dict[str, Any], state_path: Path):
        self.task_id = task_id
        self.task = task
        self.config = config
        self.state_path = state_path
        self._brain = ManagerBrain(
            task_id=task_id,
            task=task,
            config=config,
            state_path=state_path,
            model=config.get("manager_model", "claude-opus-4-6"),
        )

    @classmethod
    def name(cls) -> str:
        return "anthropic"

    @classmethod
    def is_available(cls) -> bool:
        return ManagerBrain.is_available()

    @classmethod
    def probe_live(cls, config: dict[str, Any]) -> str:
        import anthropic

        client = anthropic.Anthropic()
        response = client.messages.create(
            model=config.get("manager_model", "claude-opus-4-6"),
            max_tokens=64,
            system="Return compact JSON only.",
            messages=[{"role": "user", "content": 'Reply with {"status":"ok","backend":"anthropic"} only.'}],
        )
        blocks = getattr(response, "content", []) or []
        text = "".join(getattr(block, "text", "") for block in blocks).strip()
        if not text:
            raise RuntimeError("Anthropic probe returned an empty response.")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return text[:200]
        if payload.get("status") != "ok":
            raise RuntimeError(f"Anthropic probe returned unexpected payload: {payload}")
        return json.dumps(payload, ensure_ascii=False)

    def create_work_order(
        self,
        task: dict[str, Any],
        history: list[dict[str, Any]],
        repo_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        feedback = self._brain.build_worker_feedback()
        sequence_no = max(
            [int(entry.get("sequence_no", 0)) for entry in history if entry.get("kind") == "work_order"],
            default=0,
        ) + 1
        selected_worker = (
            (task.get("preferred_workers") or [task.get("preferred_provider") or self.config.get("default_worker", "cc")])[0]
        )
        return {
            "task_id": task.get("id"),
            "id": f"{task.get('id')}-wo-{sequence_no:02d}",
            "sequence_no": sequence_no,
            "goal": task.get("prompt", ""),
            "scope_summary": task.get("title", task.get("id")),
            "allowed_paths": list(task.get("allowed_paths") or self.config.get("allowed_paths", [])),
            "completion_commands": list(task.get("completion_commands", task.get("test_commands", []))),
            "selected_worker": selected_worker,
            "manager_feedback": feedback,
            "status": "queued",
            "created_by": self.name(),
        }

    def review_attempt(
        self,
        task: dict[str, Any],
        work_order: dict[str, Any],
        attempt_context: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> ReviewDecision:
        result = AttemptResult(
            attempt_no=int(attempt_context.get("attempt_no", 1)),
            worker_returncode=int(attempt_context.get("worker_returncode", 0)),
            changed_files=list(attempt_context.get("changed_files", [])),
            policy_violations=list(attempt_context.get("policy_violations", [])),
            test_results=list(attempt_context.get("test_results", [])),
            test_stdout=dict(attempt_context.get("test_stdout", {})),
            test_stderr=dict(attempt_context.get("test_stderr", {})),
            diff_patch=str(attempt_context.get("diff_patch", "")),
            diff_stat=str(attempt_context.get("diff_stat", "")),
            worker_stdout_excerpt=str(attempt_context.get("worker_stdout_excerpt", "")),
            quota_error=bool(attempt_context.get("quota_error", False)),
        )
        decision = self._brain.evaluate_attempt(result)
        next_work_order = None
        if decision.verdict == "retry":
            refreshed_history = history + [{"kind": "review", "feedback": decision.feedback, "blockers": decision.blockers}]
            next_work_order = self.create_work_order(task, refreshed_history)
        return ReviewDecision(
            verdict=decision.verdict,
            feedback=decision.feedback,
            blockers=list(decision.blockers),
            next_work_order=next_work_order,
            source=self.name(),
        )

    def load_thread(self, task_id: str) -> dict[str, Any] | None:
        if task_id != self.task_id:
            return None
        return {"external_thread_id": None, "messages": list(self._brain.messages)}

    def save_thread(self, task_id: str, thread_state: list[dict[str, Any]]) -> None:
        if task_id != self.task_id:
            return
        self._brain.messages = list(thread_state)
        self._brain._save_messages()
