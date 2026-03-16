"""Domain models and enums for auto-coder."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TaskStatus(StrEnum):
    WAITING_FOR_DEPENDENCY = "waiting_for_dependency"
    READY = "ready"
    LEASED = "leased"
    RUNNING = "running"
    WAITING_FOR_RETRY = "waiting_for_retry"
    WAITING_FOR_QUOTA = "waiting_for_quota"
    QUARANTINED = "quarantined"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class WorkOrderStatus(StrEnum):
    QUEUED = "queued"
    SELECTED = "selected"
    RUNNING = "running"
    NEEDS_REVIEW = "needs_review"
    RETRY_PENDING = "retry_pending"
    QUOTA_DELAYED = "quota_delayed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AttemptStatus(StrEnum):
    STARTED = "started"
    BASELINE_FAILED = "baseline_failed"
    WORKER_FAILED = "worker_failed"
    QUOTA_EXHAUSTED = "quota_exhausted"
    NO_CHANGES = "no_changes"
    POLICY_FAILED = "policy_failed"
    TESTS_FAILED = "tests_failed"
    REVIEW_FAILED = "review_failed"
    APPROVED = "approved"
    INTERRUPTED = "interrupted"


@dataclass(slots=True)
class WorkOrderSpec:
    id: str
    task_id: str
    sequence_no: int = 1
    goal: str = ""
    scope_summary: str = ""
    allowed_paths: list[str] = field(default_factory=list)
    completion_commands: list[str] = field(default_factory=list)
    selected_worker: str = ""
    manager_feedback: str = ""
    status: str = WorkOrderStatus.QUEUED.value
    retry_after: str | None = None
    created_by: str = "system"

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "WorkOrderSpec":
        return cls(
            id=str(payload["id"]),
            task_id=str(payload["task_id"]),
            sequence_no=int(payload.get("sequence_no", 1)),
            goal=str(payload.get("goal", "")),
            scope_summary=str(payload.get("scope_summary", "")),
            allowed_paths=list(payload.get("allowed_paths", [])),
            completion_commands=list(payload.get("completion_commands", [])),
            selected_worker=str(payload.get("selected_worker", "")),
            manager_feedback=str(payload.get("manager_feedback", "")),
            status=str(payload.get("status", WorkOrderStatus.QUEUED.value)),
            retry_after=str(payload["retry_after"]) if payload.get("retry_after") else None,
            created_by=str(payload.get("created_by", "system")),
        )

    def to_mapping(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "task_id": self.task_id,
            "sequence_no": self.sequence_no,
            "goal": self.goal,
            "scope_summary": self.scope_summary,
            "allowed_paths": self.allowed_paths,
            "completion_commands": self.completion_commands,
            "selected_worker": self.selected_worker,
            "manager_feedback": self.manager_feedback,
            "status": self.status,
            "created_by": self.created_by,
        }
        if self.retry_after:
            payload["retry_after"] = self.retry_after
        return payload


@dataclass(slots=True)
class TaskSpec:
    id: str
    title: str
    description: str = ""
    priority: int = 100
    enabled: bool = True
    depends_on: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    protected_paths: list[str] = field(default_factory=list)
    setup_commands: list[str] = field(default_factory=list)
    baseline_commands: list[str] = field(default_factory=list)
    completion_commands: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    preferred_workers: list[str] = field(default_factory=list)
    risk_level: str = "normal"
    max_attempts_total: int = 6
    cooldown_minutes: int = 60
    estimated_effort: str = ""
    estimated_tokens: int | None = None
    allow_no_changes: bool = False
    report_only: bool = False
    prompt: str = ""

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "TaskSpec":
        preferred = payload.get("preferred_workers")
        if not preferred:
            single = payload.get("preferred_provider") or payload.get("preferred_worker")
            preferred = [single] if single else []
        return cls(
            id=str(payload["id"]),
            title=str(payload.get("title", payload["id"])),
            description=str(payload.get("description", "")),
            priority=int(payload.get("priority", 100)),
            enabled=bool(payload.get("enabled", True)),
            depends_on=list(payload.get("depends_on", [])),
            allowed_paths=list(payload.get("allowed_paths", [])),
            protected_paths=list(payload.get("protected_paths", [])),
            setup_commands=list(payload.get("setup_commands", [])),
            baseline_commands=list(payload.get("baseline_commands", payload.get("test_commands", []))),
            completion_commands=list(payload.get("completion_commands", payload.get("test_commands", []))),
            acceptance_criteria=list(payload.get("acceptance_criteria", [])),
            preferred_workers=[item for item in preferred if item],
            risk_level=str(payload.get("risk_level", "normal")),
            max_attempts_total=int(payload.get("max_attempts_total", payload.get("max_total_attempts", 6))),
            cooldown_minutes=int(payload.get("cooldown_minutes", 60)),
            estimated_effort=str(payload.get("estimated_effort", "")),
            estimated_tokens=(
                int(payload["estimated_tokens"]) if payload.get("estimated_tokens") is not None else None
            ),
            allow_no_changes=bool(payload.get("allow_no_changes", False)),
            report_only=bool(payload.get("report_only", False)),
            prompt=str(payload.get("prompt", "")),
        )

    def to_mapping(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "title": self.title,
            "enabled": self.enabled,
            "priority": self.priority,
            "depends_on": self.depends_on,
            "allowed_paths": self.allowed_paths,
            "protected_paths": self.protected_paths,
            "setup_commands": self.setup_commands,
            "baseline_commands": self.baseline_commands,
            "completion_commands": self.completion_commands,
            "acceptance_criteria": self.acceptance_criteria,
            "preferred_workers": self.preferred_workers,
            "risk_level": self.risk_level,
            "max_attempts_total": self.max_attempts_total,
            "cooldown_minutes": self.cooldown_minutes,
            "estimated_effort": self.estimated_effort,
            "prompt": self.prompt,
        }
        if self.description:
            payload["description"] = self.description
        if self.estimated_tokens is not None:
            payload["estimated_tokens"] = self.estimated_tokens
        if self.allow_no_changes:
            payload["allow_no_changes"] = True
        if self.report_only:
            payload["report_only"] = True
        return payload
