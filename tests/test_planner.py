"""Tests for Planner: generate_backlog, hash-based change detection."""
from __future__ import annotations
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from auto_coder.config import AUTO_CODER_DIR, load_config
from auto_coder.planner import Planner, _brief_hash


def _make_config(root: Path) -> dict:
    (root / AUTO_CODER_DIR).mkdir(parents=True, exist_ok=True)
    return load_config(root)


def _mock_anthropic(tasks_yaml: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=tasks_yaml)]
    client = MagicMock()
    client.messages.create.return_value = msg
    return client


SAMPLE_TASKS_YAML = """
tasks:
  - id: sprint1-auth
    title: "Add auth module"
    enabled: true
    mode: safe
    priority: 10
    max_attempts_total: 6
    preferred_workers:
      - cc
    depends_on: []
    allowed_paths:
      - src/auth/
      - tests/
    baseline_commands:
      - python3 -m pytest tests/
    completion_commands:
      - python3 -m pytest tests/
    acceptance_criteria:
      - login flow works
    prompt: |
      Implement basic auth.
"""

VALID_ROADMAP = """\
## Project Goal
Build auth module.

## Target User
- Internal user

## Ordered Milestones
### Milestone 1
Implement auth.

## In Scope
- login

## Out of Scope
- oauth

## Acceptance Criteria
- login route works
"""

VALID_PROJECT = """\
## Tech Stack
- Python 3.12

## Repo Structure
src/
tests/

## Commands
```bash
python3 -m pytest tests/
```

## Editable Paths
- src/
- tests/

## Protected Paths
- .github/

## Environment Assumptions
- local only
"""


class TestPlanner(unittest.TestCase):
    def test_generate_creates_tasks_yaml(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ROADMAP.md").write_text(VALID_ROADMAP, encoding="utf-8")
            (root / "PROJECT.md").write_text(VALID_PROJECT, encoding="utf-8")
            config = _make_config(root)
            client = _mock_anthropic(SAMPLE_TASKS_YAML)
            with patch("anthropic.Anthropic", return_value=client):
                planner = Planner(config)
                tasks = planner.generate()
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["id"], "sprint1-auth")
            self.assertTrue(config["tasks_generated_path"].exists())
            self.assertTrue(config["tasks_path"].exists())

    def test_load_tasks_returns_empty_when_no_file(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _make_config(root)
            planner = Planner(config)
            self.assertEqual(planner.load_tasks(), [])

    def test_refresh_if_changed_regenerates_on_roadmap_change(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            roadmap = root / "ROADMAP.md"
            roadmap.write_text(VALID_ROADMAP, encoding="utf-8")
            (root / "PROJECT.md").write_text(VALID_PROJECT, encoding="utf-8")
            config = _make_config(root)
            client = _mock_anthropic(SAMPLE_TASKS_YAML)
            with patch("anthropic.Anthropic", return_value=client):
                planner = Planner(config)
                regenerated = planner.refresh_if_changed()
            self.assertTrue(regenerated)

    def test_refresh_if_changed_skips_when_unchanged(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            roadmap = root / "ROADMAP.md"
            roadmap.write_text(VALID_ROADMAP, encoding="utf-8")
            (root / "PROJECT.md").write_text(VALID_PROJECT, encoding="utf-8")
            config = _make_config(root)
            client = _mock_anthropic(SAMPLE_TASKS_YAML)
            with patch("anthropic.Anthropic", return_value=client):
                planner = Planner(config)
                planner.refresh_if_changed()    # first run — regenerates
                regenerated = planner.refresh_if_changed()  # same hash — skips
            self.assertFalse(regenerated)

    def test_strips_markdown_fences(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ROADMAP.md").write_text(VALID_ROADMAP, encoding="utf-8")
            (root / "PROJECT.md").write_text(VALID_PROJECT, encoding="utf-8")
            config = _make_config(root)
            fenced = f"```yaml\n{SAMPLE_TASKS_YAML}\n```"
            client = _mock_anthropic(fenced)
            with patch("anthropic.Anthropic", return_value=client):
                planner = Planner(config)
                tasks = planner.generate()
            self.assertEqual(tasks[0]["id"], "sprint1-auth")

    def test_generate_rejects_unclear_brief(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ROADMAP.md").write_text("# Build auth module", encoding="utf-8")
            config = _make_config(root)
            planner = Planner(config)
            with self.assertRaises(RuntimeError):
                planner.generate()

    def test_generate_merges_local_overrides(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ROADMAP.md").write_text(VALID_ROADMAP, encoding="utf-8")
            (root / "PROJECT.md").write_text(VALID_PROJECT, encoding="utf-8")
            config = _make_config(root)
            config["tasks_local_path"].write_text(
                """
tasks:
  - id: sprint1-auth
    priority: 5
    enabled: false
""".strip()
                + "\n",
                encoding="utf-8",
            )
            client = _mock_anthropic(SAMPLE_TASKS_YAML)
            with patch("anthropic.Anthropic", return_value=client):
                planner = Planner(config)
                tasks = planner.generate()
            self.assertEqual(tasks[0]["priority"], 5)
            self.assertFalse(tasks[0]["enabled"])

    def test_generate_preserves_stable_ids_across_replans(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ROADMAP.md").write_text(VALID_ROADMAP, encoding="utf-8")
            (root / "PROJECT.md").write_text(VALID_PROJECT, encoding="utf-8")
            config = _make_config(root)
            first = _mock_anthropic(SAMPLE_TASKS_YAML)
            second = _mock_anthropic(
                SAMPLE_TASKS_YAML.replace("id: sprint1-auth", "id: new-random-id")
            )
            with patch("anthropic.Anthropic", return_value=first):
                planner = Planner(config)
                first_tasks = planner.generate()
            with patch("anthropic.Anthropic", return_value=second):
                planner = Planner(config)
                second_tasks = planner.generate()
            self.assertEqual(first_tasks[0]["id"], second_tasks[0]["id"])

    def test_generate_rejects_invalid_task_schema(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ROADMAP.md").write_text(VALID_ROADMAP, encoding="utf-8")
            (root / "PROJECT.md").write_text(VALID_PROJECT, encoding="utf-8")
            config = _make_config(root)
            invalid_yaml = """
tasks:
  - id: broken-task
    title: Broken
    depends_on: []
"""
            client = _mock_anthropic(invalid_yaml)
            with patch("anthropic.Anthropic", return_value=client):
                planner = Planner(config)
                with self.assertRaises(RuntimeError):
                    planner.generate()

    def test_generate_can_use_codex_backend(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ROADMAP.md").write_text(VALID_ROADMAP, encoding="utf-8")
            (root / "PROJECT.md").write_text(VALID_PROJECT, encoding="utf-8")
            config = _make_config(root)
            config["manager_backend"] = "codex"
            response_payload = {
                "ok": True,
                "result": {
                    "tasks": [
                        {
                            "id": "sprint1-auth",
                            "title": "Add auth module",
                            "enabled": True,
                            "mode": "safe",
                            "priority": 10,
                            "max_attempts_total": 6,
                            "preferred_workers": ["codex"],
                            "depends_on": [],
                            "allowed_paths": ["src/auth/", "tests/"],
                            "baseline_commands": ["python3 -m pytest tests/"],
                            "completion_commands": ["python3 -m pytest tests/"],
                            "acceptance_criteria": ["login flow works"],
                            "prompt": "Implement basic auth."
                        }
                    ]
                }
            }
            with patch("subprocess.run") as run:
                run.return_value.returncode = 0
                run.return_value.stdout = json.dumps(response_payload)
                run.return_value.stderr = ""
                planner = Planner(config)
                tasks = planner.generate()
            self.assertEqual(tasks[0]["preferred_workers"], ["codex"])

    def test_brief_hash_ignores_tasks_local_overrides(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ROADMAP.md").write_text(VALID_ROADMAP, encoding="utf-8")
            (root / "PROJECT.md").write_text(VALID_PROJECT, encoding="utf-8")
            acd = root / AUTO_CODER_DIR
            acd.mkdir(parents=True, exist_ok=True)
            first_hash = _brief_hash(root)
            (acd / "tasks.local.yaml").write_text("tasks:\n  - id: custom\n", encoding="utf-8")
            second_hash = _brief_hash(root)
            self.assertEqual(first_hash, second_hash)

    def test_stabilize_ids_rewrites_dependencies_to_stable_ids(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _make_config(root)
            planner = Planner(config)
            existing_tasks = [
                {
                    "id": "stable-a",
                    "title": "Task A",
                    "allowed_paths": ["src/"],
                    "prompt": "Task A prompt",
                },
                {
                    "id": "stable-b",
                    "title": "Task B",
                    "allowed_paths": ["src/"],
                    "prompt": "Task B prompt",
                },
            ]
            remapped = planner._stabilize_ids(
                [
                    {
                        "id": "new-a",
                        "title": "Task A",
                        "depends_on": [],
                        "allowed_paths": ["src/"],
                        "prompt": "Task A prompt",
                    },
                    {
                        "id": "new-b",
                        "title": "Task B",
                        "depends_on": ["new-a"],
                        "allowed_paths": ["src/"],
                        "prompt": "Task B prompt",
                    },
                ],
                existing_tasks,
            )
            self.assertEqual(remapped[0]["id"], "stable-a")
            self.assertEqual(remapped[1]["id"], "stable-b")
            self.assertEqual(remapped[1]["depends_on"], ["stable-a"])


if __name__ == "__main__":
    unittest.main()
