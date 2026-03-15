"""Deterministic review gates and optional manager review."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auto_coder.managers.base import ManagerBackend, ReviewDecision
from auto_coder.reports import save_json


@dataclass(slots=True)
class DeterministicReview:
    passed: bool
    blockers: list[str]
    feedback: str


def deterministic_review(attempt_context: dict[str, Any]) -> DeterministicReview:
    blockers: list[str] = []
    if not attempt_context.get("baseline_passed", False):
        blockers.append("baseline_failed")
    if not attempt_context.get("worker_report_present", False):
        blockers.append("worker_report_missing")
    blockers.extend(list(attempt_context.get("policy_violations", [])))
    if not attempt_context.get("completion_passed", False):
        blockers.append("completion_commands_failed")
    passed = not blockers
    feedback = "Deterministic gates passed." if passed else "Deterministic gates failed: " + ", ".join(blockers)
    return DeterministicReview(passed=passed, blockers=blockers, feedback=feedback)


def review_attempt(
    *,
    task: dict[str, Any],
    work_order: dict[str, Any],
    attempt_context: dict[str, Any],
    history: list[dict[str, Any]],
    manager_backend: ManagerBackend | None,
    report_dir: Path,
) -> ReviewDecision:
    deterministic = deterministic_review(attempt_context)
    if not deterministic.passed:
        decision = ReviewDecision(
            verdict="retry",
            feedback=deterministic.feedback,
            blockers=deterministic.blockers,
            source="deterministic",
        )
        save_review_artifact(report_dir, decision, attempt_context=attempt_context)
        return decision

    if manager_backend is None:
        decision = ReviewDecision(
            verdict="approve",
            feedback="No manager backend configured and deterministic gates passed.",
            blockers=[],
            source="deterministic",
        )
        save_review_artifact(report_dir, decision, attempt_context=attempt_context)
        return decision

    decision = manager_backend.review_attempt(task, work_order, attempt_context, history)
    save_review_artifact(report_dir, decision, attempt_context=attempt_context)
    return decision


def save_review_artifact(report_dir: Path, decision: ReviewDecision, *, attempt_context: dict[str, Any]) -> None:
    payload = {
        "verdict": decision.verdict,
        "feedback": decision.feedback,
        "blockers": list(decision.blockers),
        "source": decision.source,
        "attempt": {
            "attempt_no": attempt_context.get("attempt_no"),
            "worker_name": attempt_context.get("worker_name"),
            "worker_returncode": attempt_context.get("worker_returncode"),
            "baseline_passed": attempt_context.get("baseline_passed"),
            "completion_passed": attempt_context.get("completion_passed"),
        },
    }
    if decision.next_work_order:
        payload["next_work_order"] = dict(decision.next_work_order)
    save_json(report_dir / "review.json", payload)
