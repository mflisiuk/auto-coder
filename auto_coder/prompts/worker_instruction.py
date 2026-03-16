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

    feedback_block = f"\n\nMANAGER FEEDBACK (address every point before finishing):\n{manager_feedback}\n" if manager_feedback else ""

    # Include acceptance criteria so the worker knows what "done" means
    criteria = list(task.get("acceptance_criteria") or [])
    criteria_block = ""
    if criteria:
        criteria_lines = "\n".join(f"  - {c}" for c in criteria)
        criteria_block = f"\n\nACCEPTANCE CRITERIA (all must be satisfied):\n{criteria_lines}"

    # Include completion commands so the worker knows how to verify its work
    completion_cmds = list(work_order.get("completion_commands") or task.get("completion_commands") or task.get("test_commands") or [])
    verify_block = ""
    if completion_cmds:
        cmds_lines = "\n".join(f"  {c}" for c in completion_cmds)
        verify_block = f"\n\nVERIFICATION COMMANDS (must all pass before you finish):\n{cmds_lines}"

    return f"""You are an autonomous coding agent working inside a git worktree.

TASK ID: {task.get('id')}
WORK ORDER ID: {work_order.get('id')}
TITLE: {task.get('title')}
SCOPE SUMMARY: {scope_summary}

GOAL:
{goal}{criteria_block}{verify_block}

HARD RULES:
- Work only inside the current git worktree. Do not push, merge, deploy, or touch production systems.
- Only modify files under: {', '.join(allowed_paths) or '(none specified)'}.
- Never touch protected paths: {', '.join(protected_paths) or '(none specified)'}.
- Leave the branch in a testable and committable state.
- Run the VERIFICATION COMMANDS above and confirm they pass before finishing.{feedback_block}

MANDATORY LAST ACTION:
Before finishing, write a file called AGENT_REPORT.json in the current directory with this structure:
{{"status": "completed"|"partial"|"blocked"|"quota_exhausted",
  "summary": "short summary of what was done",
  "completed": ["list each thing you implemented"],
  "issues": ["list any problems encountered"],
  "next": "suggested next step if any"}}"""
