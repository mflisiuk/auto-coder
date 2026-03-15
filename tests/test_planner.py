"""Tests for Planner: generate_backlog, hash-based change detection."""
from __future__ import annotations
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from auto_coder.config import AUTO_CODER_DIR, load_config
from auto_coder.planner import Planner


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
    max_total_attempts: 6
    preferred_provider: cc
    allowed_paths:
      - src/auth/
      - tests/
    test_commands:
      - python3 -m pytest tests/
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


if __name__ == "__main__":
    unittest.main()
