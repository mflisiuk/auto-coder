"""Planner: synthesise backlog from project docs into generated and effective task files."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

import yaml

from auto_coder.brief_validator import validate_project_brief
from auto_coder.models import TaskSpec
from auto_coder.prompts.planner import PLANNER_SYSTEM, PLANNER_USER_TEMPLATE, TASKS_SCHEMA_DESCRIPTION
from auto_coder.storage import sync_tasks
from auto_coder.task_graph import validate_task_graph


REQUIRED_TASK_FIELDS = (
    "id",
    "title",
    "depends_on",
    "allowed_paths",
    "baseline_commands",
    "completion_commands",
    "acceptance_criteria",
    "prompt",
)


class Planner:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.project_root: Path = config["project_root"]
        self.tasks_path: Path = config["tasks_path"]
        self.tasks_generated_path: Path = config["tasks_generated_path"]
        self.tasks_local_path: Path = config["tasks_local_path"]
        self.auto_coder_dir: Path = config["auto_coder_dir"]
        self.model: str = config.get("planner_model") or config.get("manager_model", "claude-opus-4-6")
        self._hash_path = self.auto_coder_dir / ".roadmap_hash"

    @classmethod
    def is_available(cls) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    def refresh_if_changed(self) -> bool:
        """Regenerate effective tasks when any planning input changes."""
        if not (self.project_root / "ROADMAP.md").exists():
            return False
        current_hash = _brief_hash(self.project_root)
        stored_hash = self._hash_path.read_text(encoding="utf-8").strip() if self._hash_path.exists() else ""
        if current_hash == stored_hash and self.tasks_path.exists():
            return False
        self.generate()
        return True

    def generate(self) -> list[dict[str, Any]]:
        validation = validate_project_brief(self.project_root)
        validation.raise_if_invalid()

        roadmap = _read(self.project_root / "ROADMAP.md")
        project_context = _read(self.project_root / "PROJECT.md")
        constraints = _read(self.project_root / "CONSTRAINTS.md")
        architecture_notes = _read(self.project_root / "ARCHITECTURE_NOTES.md")

        if not roadmap:
            raise RuntimeError("ROADMAP.md not found or empty.")

        generated_tasks = self._call_api(
            roadmap=roadmap,
            project_context=project_context,
            constraints=constraints,
            architecture_notes=architecture_notes,
        )
        existing_generated = self._load_yaml_tasks(self.tasks_generated_path)
        stable_generated = self._stabilize_ids(generated_tasks, existing_generated)
        validated_generated = self._validate_tasks(stable_generated)
        merged_tasks = self._merge_with_local_overrides(validated_generated)
        validated_merged = self._validate_tasks(merged_tasks)

        self._save_tasks(self.tasks_generated_path, validated_generated)
        self._save_tasks(self.tasks_path, validated_merged)
        sync_tasks(self.config["state_db_path"], validated_merged)

        self._hash_path.write_text(_brief_hash(self.project_root) + "\n", encoding="utf-8")
        print(f"Wrote {len(validated_generated)} generated task(s) to {self.tasks_generated_path}")
        print(f"Wrote {len(validated_merged)} effective task(s) to {self.tasks_path}")
        return validated_merged

    def load_tasks(self) -> list[dict[str, Any]]:
        if self.tasks_path.exists():
            return self._load_yaml_tasks(self.tasks_path)
        return []

    # ----------------------------------------------------------------- private

    def _call_api(
        self,
        *,
        roadmap: str,
        project_context: str,
        constraints: str,
        architecture_notes: str,
    ) -> list[dict[str, Any]]:
        import anthropic

        client = anthropic.Anthropic()
        user_msg = PLANNER_USER_TEMPLATE.format(
            project_context=project_context or "(no PROJECT.md provided)",
            constraints=constraints or "(none)",
            architecture_notes=architecture_notes or "(none)",
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
        if raw_yaml.startswith("```"):
            lines = raw_yaml.splitlines()
            raw_yaml = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        parsed = yaml.safe_load(raw_yaml) or {}
        tasks = parsed.get("tasks") or []
        if not isinstance(tasks, list):
            raise RuntimeError("Planner returned invalid structure: expected top-level tasks list.")
        return [dict(task) for task in tasks]

    def _validate_tasks(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        errors: list[str] = []
        for index, task in enumerate(tasks, start=1):
            item = dict(task)
            if "baseline_commands" not in item and "test_commands" in item:
                item["baseline_commands"] = list(item.get("test_commands", []))
            if "completion_commands" not in item and "test_commands" in item:
                item["completion_commands"] = list(item.get("test_commands", []))
            if "preferred_workers" not in item and item.get("preferred_provider"):
                item["preferred_workers"] = [item["preferred_provider"]]
            for field in REQUIRED_TASK_FIELDS:
                if field not in item:
                    errors.append(f"task[{index}] missing required field: {field}")
            try:
                spec = TaskSpec.from_mapping(item)
            except Exception as exc:
                errors.append(f"task[{index}] invalid schema: {exc}")
                continue
            if not spec.allowed_paths:
                errors.append(f"{spec.id}: allowed_paths must not be empty")
            if not spec.baseline_commands:
                errors.append(f"{spec.id}: baseline_commands must not be empty")
            if not spec.completion_commands:
                errors.append(f"{spec.id}: completion_commands must not be empty")
            if not spec.acceptance_criteria:
                errors.append(f"{spec.id}: acceptance_criteria must not be empty")
            normalized.append(spec.to_mapping())
        errors.extend(validate_task_graph(normalized))
        if errors:
            raise RuntimeError("invalid planner output:\n- " + "\n- ".join(sorted(set(errors))))
        return normalized

    def _merge_with_local_overrides(self, generated_tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        local_tasks = self._load_yaml_tasks(self.tasks_local_path)
        if not local_tasks:
            return list(generated_tasks)
        generated_by_id = {str(task["id"]): dict(task) for task in generated_tasks}
        merged: list[dict[str, Any]] = []
        local_by_id = {str(task["id"]): dict(task) for task in local_tasks}

        for task in generated_tasks:
            task_id = str(task["id"])
            if task_id in local_by_id:
                merged.append({**task, **local_by_id[task_id]})
            else:
                merged.append(dict(task))

        for task_id, task in local_by_id.items():
            if task_id not in generated_by_id:
                merged.append(task)

        merged.sort(key=lambda item: (int(item.get("priority", 100)), str(item.get("id", ""))))
        return merged

    def _stabilize_ids(
        self,
        tasks: list[dict[str, Any]],
        existing_tasks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        existing_by_fingerprint = {_task_fingerprint(task): str(task["id"]) for task in existing_tasks if task.get("id")}
        existing_by_title = {str(task.get("title", "")).strip().lower(): str(task["id"]) for task in existing_tasks if task.get("id")}
        used_ids = {str(task["id"]) for task in existing_tasks if task.get("id")}
        stable_tasks: list[dict[str, Any]] = []
        for index, task in enumerate(tasks, start=1):
            item = dict(task)
            fingerprint = _task_fingerprint(item)
            candidate_id = existing_by_fingerprint.get(fingerprint) or existing_by_title.get(str(item.get("title", "")).strip().lower())
            if candidate_id:
                item["id"] = candidate_id
            else:
                item["id"] = _ensure_unique_id(_slugify(item.get("id") or item.get("title") or f"task-{index}"), used_ids)
            used_ids.add(str(item["id"]))
            stable_tasks.append(item)
        return stable_tasks

    def _save_tasks(self, path: Path, tasks: list[dict[str, Any]]) -> None:
        self.auto_coder_dir.mkdir(parents=True, exist_ok=True)
        payload = {"tasks": tasks}
        path.write_text(
            yaml.dump(payload, allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )

    def _load_yaml_tasks(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        tasks = raw.get("tasks") or []
        return [dict(task) for task in tasks if isinstance(task, dict)]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _brief_hash(project_root: Path) -> str:
    parts = []
    for name in ("ROADMAP.md", "PROJECT.md", "CONSTRAINTS.md", "ARCHITECTURE_NOTES.md"):
        path = project_root / name
        parts.append(path.read_text(encoding="utf-8") if path.exists() else "")
    tasks_local_path = project_root / ".auto-coder" / "tasks.local.yaml"
    parts.append(tasks_local_path.read_text(encoding="utf-8") if tasks_local_path.exists() else "")
    return hashlib.sha256("\n---\n".join(parts).encode("utf-8")).hexdigest()


def _task_fingerprint(task: dict[str, Any]) -> str:
    title = str(task.get("title", "")).strip().lower()
    allowed_paths = "|".join(sorted(str(item) for item in task.get("allowed_paths", [])))
    prompt = re.sub(r"\s+", " ", str(task.get("prompt", "")).strip().lower())
    return hashlib.sha256(f"{title}|{allowed_paths}|{prompt}".encode("utf-8")).hexdigest()


def _slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-") or "task"


def _ensure_unique_id(candidate: str, used_ids: set[str]) -> str:
    if candidate not in used_ids:
        return candidate
    counter = 2
    while f"{candidate}-{counter}" in used_ids:
        counter += 1
    return f"{candidate}-{counter}"
