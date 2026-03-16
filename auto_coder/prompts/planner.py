"""Prompt fragments for backlog synthesis."""
from __future__ import annotations


TASKS_SCHEMA_DESCRIPTION = """
Each task must have:
  id: stable slug-like id
  title: short human-readable title
  enabled: true
  mode: safe
  priority: integer (lower = higher priority, start at 10, increment by 10)
  max_attempts_total: 6
  preferred_workers:
    - cc  (or ccg, cch, codex, qwen, gemini)
  depends_on:
    - explicit task ids this task depends on
  allowed_paths:
    - list of path prefixes the agent may modify
  baseline_commands:
    - deterministic commands that must already pass before coding starts
  completion_commands:
    - deterministic commands that must pass after implementation
  acceptance_criteria:
    - concrete reviewable outcomes
  prompt: |
    Detailed instructions for the coding agent.
"""

PLANNER_SYSTEM = (
    "You are a senior engineering manager. "
    "You receive project docs and must produce a concrete, execution-ready backlog. "
    "Output valid YAML only. No explanations, no markdown fences."
)

PLANNER_USER_TEMPLATE = """\
PROJECT CONTEXT:
{project_context}

PLANNING HINTS:
{planning_hints}

CONSTRAINTS:
{constraints}

ARCHITECTURE NOTES:
{architecture_notes}

ROADMAP:
{roadmap}

TASK SCHEMA:
{schema}

Rules:
- Each task changes at most 5-8 files.
- Add explicit depends_on even if it is an empty list.
- Add explicit baseline_commands and completion_commands.
- Add explicit allowed_paths for every task.
- Add at least one acceptance criterion for every task.
- Respect PLANNING_HINTS.md when it provides repository-specific naming, command, or pagination conventions.
- Tasks later in the list must not depend on tasks that appear after them.
- Output format: a YAML document with a top-level "tasks:" list.
"""
