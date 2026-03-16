"""Tests for project brief validation."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_coder.brief_validator import validate_brief_texts, validate_project_brief


VALID_ROADMAP = """\
# ROADMAP.md

## Project Goal
Build an internal dashboard.

## Target User
- Ops team

## Ordered Milestones
### Milestone 1
Create the dashboard shell.

## In Scope
- dashboard shell

## Out of Scope
- auth

## Acceptance Criteria
- dashboard page renders
"""


VALID_PROJECT = """\
# PROJECT.md

## Tech Stack
- Python 3.12

## Repo Structure
app/
tests/

## Commands
```bash
python3 -m pytest tests/
```

## Editable Paths
- app/
- tests/

## Protected Paths
- .github/

## Environment Assumptions
- local sqlite only
"""


class TestBriefValidator(unittest.TestCase):
    def test_accepts_valid_minimal_brief(self):
        result = validate_brief_texts(
            roadmap_text=VALID_ROADMAP,
            project_text=VALID_PROJECT,
        )
        self.assertTrue(result.ok)

    def test_rejects_missing_required_files(self):
        result = validate_brief_texts(
            roadmap_text="",
            project_text="",
            roadmap_exists=False,
            project_exists=False,
        )
        self.assertFalse(result.ok)
        self.assertIn("ROADMAP.md", result.missing_files)
        self.assertIn("PROJECT.md", result.missing_files)

    def test_rejects_missing_sections(self):
        result = validate_brief_texts(
            roadmap_text="# ROADMAP.md\n\n## Project Goal\nBuild app\n",
            project_text=VALID_PROJECT,
        )
        self.assertFalse(result.ok)
        self.assertTrue(any(item.startswith("ROADMAP.md::") for item in result.missing_sections))

    def test_validate_project_brief_reads_files(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ROADMAP.md").write_text(VALID_ROADMAP, encoding="utf-8")
            (root / "PROJECT.md").write_text(VALID_PROJECT, encoding="utf-8")
            result = validate_project_brief(root)
            self.assertTrue(result.ok)

    def test_accepts_phpunit_command(self):
        project_text = VALID_PROJECT.replace("python3 -m pytest tests/", "./vendor/bin/phpunit")
        result = validate_brief_texts(
            roadmap_text=VALID_ROADMAP,
            project_text=project_text,
        )
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
