"""Planner: converts ROADMAP.md + PROJECT.md into .auto-coder/tasks.yaml via Claude API."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import yaml


TASKS_SCHEMA_DESCRIPTION = """
Each task must have:
  id: unique slug (e.g. "sprint1-auth-module")
  title: short human-readable title
  enabled: true
  mode: safe
  priority: integer (lower = higher priority, start at 10, increment by 10)
  max_total_attempts: 6
  preferred_provider: cc  (or ccg, cch, codex)
  allowed_paths:
    - list of path prefixes the agent may modify (e.g. "src/auth/", "tests/")
  test_commands:
    - shell commands that must all pass (exit 0) for the task to be considered done
    - only include commands that can run BEFORE the task starts (existing tests)
    - do NOT include tests that don't exist yet (the agent will create them)
  prompt: |
    Detailed instructions for the coding agent. Include:
    - What to implement
    - Which files to create or modify
    - What the tests should verify
    - Any constraints
"""

PLANNER_SYSTEM = (
    "You are a senior engineering manager. "
    "You receive a project roadmap and context, and produce a concrete task backlog. "
    "Output valid YAML only. No explanations, no markdown fences."
)

PLANNER_USER_TEMPLATE = """\
PROJECT CONTEXT:
{project_context}

ROADMAP:
{roadmap}

TASK SCHEMA:
{schema}

Rules:
- Each task changes at most 5–8 files.
- Tasks of size LARGE must be split into 2–3 MEDIUM tasks.
- test_commands must only reference test files that ALREADY EXIST in the repo.
- Ordering: tasks later in the list must not depend on tasks that appear after them (topological order).
- Output format: a YAML document with a top-level "tasks:" list.
"""


class Planner:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.project_root: Path = config["project_root"]
        self.tasks_path: Path = config["tasks_path"]
        self.auto_coder_dir: Path = config["auto_coder_dir"]
        self.model: str = config.get("planner_model") or config.get("manager_model", "claude-opus-4-6")
        self._hash_path = self.auto_coder_dir / ".roadmap_hash"

    @classmethod
    def is_available(cls) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    def refresh_if_changed(self) -> bool:
        """Regenerate tasks.yaml if ROADMAP.md changed. Returns True if regenerated."""
        roadmap_path = self.project_root / "ROADMAP.md"
        if not roadmap_path.exists():
            return False
        current_hash = _file_hash(roadmap_path)
        stored_hash = self._hash_path.read_text(encoding="utf-8").strip() if self._hash_path.exists() else ""
        if current_hash == stored_hash and self.tasks_path.exists():
            return False
        self.generate()
        return True

    def generate(self) -> list[dict]:
        """Generate tasks.yaml from ROADMAP.md + PROJECT.md. Returns parsed tasks list."""
        roadmap = _read(self.project_root / "ROADMAP.md")
        project_context = _read(self.project_root / "PROJECT.md")
        if not roadmap:
            raise RuntimeError("ROADMAP.md not found or empty.")

        tasks = self._call_api(roadmap, project_context)
        self._save(tasks)
        # store hash so we don't regenerate on next run
        roadmap_hash = _file_hash(self.project_root / "ROADMAP.md")
        self._hash_path.write_text(roadmap_hash + "\n", encoding="utf-8")
        return tasks

    def load_tasks(self) -> list[dict]:
        """Load tasks from .auto-coder/tasks.yaml."""
        if not self.tasks_path.exists():
            return []
        raw = yaml.safe_load(self.tasks_path.read_text(encoding="utf-8")) or {}
        return list(raw.get("tasks", []))

    # ----------------------------------------------------------------- private

    def _call_api(self, roadmap: str, project_context: str) -> list[dict]:
        import anthropic
        client = anthropic.Anthropic()
        user_msg = PLANNER_USER_TEMPLATE.format(
            project_context=project_context or "(no PROJECT.md provided)",
            roadmap=roadmap,
            schema=TASKS_SCHEMA_DESCRIPTION,
        )
        response = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=PLANNER_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw_yaml = response.content[0].text.strip()
        # strip accidental markdown fences
        if raw_yaml.startswith("```"):
            lines = raw_yaml.splitlines()
            raw_yaml = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        parsed = yaml.safe_load(raw_yaml) or {}
        tasks = parsed.get("tasks") or []
        if not isinstance(tasks, list):
            raise ValueError(f"Planner returned unexpected structure: {raw_yaml[:300]}")
        return tasks

    def _save(self, tasks: list[dict]) -> None:
        self.auto_coder_dir.mkdir(parents=True, exist_ok=True)
        payload = {"tasks": tasks}
        self.tasks_path.write_text(
            yaml.dump(payload, allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        print(f"Wrote {len(tasks)} task(s) to {self.tasks_path}")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
