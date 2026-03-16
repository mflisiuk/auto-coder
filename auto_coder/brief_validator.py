"""Validate project briefing files before planning."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re


ROADMAP_REQUIRED_SECTIONS = (
    "Project Goal",
    "Target User",
    "Ordered Milestones",
    "In Scope",
    "Out of Scope",
    "Acceptance Criteria",
)

PROJECT_REQUIRED_SECTIONS = (
    "Tech Stack",
    "Repo Structure",
    "Commands",
    "Editable Paths",
    "Protected Paths",
    "Environment Assumptions",
)

AMBIGUOUS_MARKERS = ("tbd", "todo", "to decide", "later", "somehow", "maybe")
DETERMINISTIC_COMMAND_PATTERNS = (
    r"\bpytest\b",
    r"\bpython(?:3)?\s+-m\s+pytest\b",
    r"\bpython(?:3)?\s+-m\s+unittest\b",
    r"\bpython(?:3)?\s+-m\s+compileall\b",
    r"\buv\s+run\s+pytest\b",
    r"\bnpm\s+test\b",
    r"\bpnpm\s+test\b",
    r"\byarn\s+test\b",
    r"\bcomposer\s+test\b",
    r"(?:^|[\s`])\.?/?.*vendor/bin/phpunit\b",
    r"\bphpunit\b",
    r"\bphp\s+artisan\s+test\b",
    r"\bcargo\s+test\b",
    r"\bgo\s+test\b",
    r"\bmake\s+test\b",
)


@dataclass
class BriefValidationResult:
    missing_files: list[str] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    ambiguous_points: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (
            self.missing_files
            or self.missing_sections
            or self.ambiguous_points
            or self.contradictions
        )

    def summary(self) -> str:
        if self.ok:
            return "brief ok"
        parts = []
        if self.missing_files:
            parts.append(f"missing files: {', '.join(self.missing_files)}")
        if self.missing_sections:
            parts.append(f"missing sections: {', '.join(self.missing_sections)}")
        if self.ambiguous_points:
            parts.append(f"ambiguous points: {', '.join(self.ambiguous_points)}")
        if self.contradictions:
            parts.append(f"contradictions: {', '.join(self.contradictions)}")
        return "brief niejasny - " + "; ".join(parts)

    def raise_if_invalid(self) -> None:
        if self.ok:
            return
        lines = [self.summary()]
        if self.next_actions:
            lines.append("next actions:")
            lines.extend(f"- {item}" for item in self.next_actions)
        raise RuntimeError("\n".join(lines))


def validate_project_brief(project_root: Path) -> BriefValidationResult:
    """Validate required project briefing files in the repo root."""
    roadmap_path = project_root / "ROADMAP.md"
    project_path = project_root / "PROJECT.md"
    constraints_path = project_root / "CONSTRAINTS.md"

    roadmap_text = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else ""
    project_text = project_path.read_text(encoding="utf-8") if project_path.exists() else ""
    constraints_text = constraints_path.read_text(encoding="utf-8") if constraints_path.exists() else ""

    return validate_brief_texts(
        roadmap_text=roadmap_text,
        project_text=project_text,
        constraints_text=constraints_text,
        roadmap_exists=roadmap_path.exists(),
        project_exists=project_path.exists(),
    )


def validate_brief_texts(
    *,
    roadmap_text: str,
    project_text: str,
    constraints_text: str = "",
    roadmap_exists: bool = True,
    project_exists: bool = True,
) -> BriefValidationResult:
    """Validate the content of ROADMAP and PROJECT documents."""
    result = BriefValidationResult()
    if not roadmap_exists:
        result.missing_files.append("ROADMAP.md")
    if not project_exists:
        result.missing_files.append("PROJECT.md")

    if roadmap_exists:
        _check_required_sections(result, "ROADMAP.md", roadmap_text, ROADMAP_REQUIRED_SECTIONS)
    if project_exists:
        _check_required_sections(result, "PROJECT.md", project_text, PROJECT_REQUIRED_SECTIONS)
        _check_commands_section(result, project_text)
        _check_path_policy(result, project_text)

    _check_ambiguity(result, "ROADMAP.md", roadmap_text)
    _check_ambiguity(result, "PROJECT.md", project_text)
    _check_ambiguity(result, "CONSTRAINTS.md", constraints_text)

    if "do not add new runtime dependencies" in constraints_text.lower() and "no new dependencies" not in constraints_text.lower():
        # Nothing contradictory here; placeholder so the validator structure can grow.
        pass

    if result.missing_files:
        result.next_actions.extend(f"Create {name}" for name in result.missing_files)
    if result.missing_sections:
        result.next_actions.extend(f"Add section {section}" for section in result.missing_sections)
    if not result.ok and not result.next_actions:
        result.next_actions.append("Clarify the brief until milestones, commands, and path scope are explicit.")
    return result


def _check_required_sections(
    result: BriefValidationResult,
    filename: str,
    text: str,
    sections: tuple[str, ...],
) -> None:
    lowered = text.lower()
    for section in sections:
        if section.lower() not in lowered:
            result.missing_sections.append(f"{filename}::{section}")


def _check_commands_section(result: BriefValidationResult, project_text: str) -> None:
    lowered = project_text.lower()
    if "commands" not in lowered:
        return
    if not any(re.search(pattern, lowered) for pattern in DETERMINISTIC_COMMAND_PATTERNS):
        result.ambiguous_points.append("PROJECT.md::Commands has no deterministic test command")
        result.next_actions.append("Add at least one deterministic test or verification command to PROJECT.md.")


def _check_path_policy(result: BriefValidationResult, project_text: str) -> None:
    lowered = project_text.lower()
    if "editable paths" not in lowered:
        return
    if "protected paths" not in lowered:
        return
    if lowered.count("`") == 0 and "-" not in project_text:
        result.ambiguous_points.append("PROJECT.md path policy is present but has no concrete path entries")
        result.next_actions.append("List editable and protected path prefixes explicitly in PROJECT.md.")


def _check_ambiguity(result: BriefValidationResult, filename: str, text: str) -> None:
    lowered = text.lower()
    for marker in AMBIGUOUS_MARKERS:
        if marker in lowered:
            result.ambiguous_points.append(f"{filename} contains ambiguous marker: {marker}")
