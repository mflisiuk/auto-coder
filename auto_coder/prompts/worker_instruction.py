"""Worker instruction prompt builder."""
from __future__ import annotations


def build_worker_prompt(
    *,
    task: dict,
    work_order: dict,
    allowed_paths: list[str],
    protected_paths: list[str],
) -> str:
    goal = (work_order.get("goal") or task.get("prompt") or "").strip()
    manager_feedback = (work_order.get("manager_feedback") or "").strip()
    scope_summary = (work_order.get("scope_summary") or task.get("title") or task.get("id") or "").strip()
    feedback_block = f"\n\nMANAGER FEEDBACK:\n{manager_feedback}\n" if manager_feedback else ""
    return f"""You are an autonomous coding agent.

TASK ID: {task.get('id')}
WORK ORDER ID: {work_order.get('id')}
TITLE: {task.get('title')}
SCOPE SUMMARY: {scope_summary}

GOAL:
{goal}

HARD RULES:
- Work only inside the current git worktree.
- Do not push, merge, deploy, or touch production systems.
- Only modify files under: {', '.join(allowed_paths) or '(none specified)'}.
- Never touch protected paths: {', '.join(protected_paths) or '(none specified)'}.
- Use only standard-library Python for tests (unittest). No pytest.
- Do not add new package dependencies.
- Leave the branch in a testable state.{feedback_block}

MANDATORY LAST ACTION:
Before finishing, write a file called AGENT_REPORT.json in the current directory:
{{"status": "completed"|"partial"|"blocked"|"quota_exhausted",
  "summary": "short summary",
  "completed": ["list what you did"],
  "issues": ["list problems encountered"],
  "next": "suggested next step"}}"""
