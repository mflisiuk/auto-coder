"""Generate an initial brief from existing repository documents and manifests."""
from __future__ import annotations

import json
from pathlib import Path


def bootstrap_brief(project_root: Path, *, force: bool = False) -> dict[str, Path]:
    targets = {
        "ROADMAP.md": project_root / "ROADMAP.md",
        "PROJECT.md": project_root / "PROJECT.md",
        "PLANNING_HINTS.md": project_root / "PLANNING_HINTS.md",
        "CONSTRAINTS.md": project_root / "CONSTRAINTS.md",
        "ARCHITECTURE_NOTES.md": project_root / "ARCHITECTURE_NOTES.md",
    }
    existing = [name for name, path in targets.items() if path.exists()]
    if existing and not force:
        raise RuntimeError(
            "Refusing to overwrite existing brief files without --force: "
            + ", ".join(existing)
        )

    repo_name = project_root.name
    readme = _read(project_root / "README.md")
    doc_files = sorted(path for path in (project_root / "docs").rglob("*.md")) if (project_root / "docs").exists() else []
    doc_titles = [_markdown_title(path) or path.stem.replace("-", " ").title() for path in doc_files[:8]]
    top_level_dirs = [path.name for path in sorted(project_root.iterdir()) if path.is_dir() and not path.name.startswith(".")]
    commands = _detect_commands(project_root)
    tech_stack = _detect_tech_stack(project_root)
    editable_paths = [f"{name}/" for name in top_level_dirs if name not in {"docs", "infra", "deploy", "secrets", ".auto-coder"}]
    architecture_notes = _build_architecture_notes(doc_titles, top_level_dirs)

    roadmap = _build_roadmap(repo_name, readme, doc_titles, editable_paths, commands)
    project = _build_project(repo_name, tech_stack, top_level_dirs, commands, editable_paths)
    constraints = _build_constraints()
    planning_hints = _build_planning_hints(commands)

    targets["ROADMAP.md"].write_text(roadmap, encoding="utf-8")
    targets["PROJECT.md"].write_text(project, encoding="utf-8")
    targets["PLANNING_HINTS.md"].write_text(planning_hints, encoding="utf-8")
    targets["CONSTRAINTS.md"].write_text(constraints, encoding="utf-8")
    targets["ARCHITECTURE_NOTES.md"].write_text(architecture_notes, encoding="utf-8")
    return targets


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _markdown_title(path: Path) -> str:
    for line in _read(path).splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""


def _detect_commands(project_root: Path) -> list[str]:
    commands: list[str] = []
    if (project_root / "composer.json").exists():
        commands.extend(["composer test", "./vendor/bin/phpunit"])
    if (project_root / "package.json").exists():
        commands.append("npm test")
    if (project_root / "Cargo.toml").exists():
        commands.append("cargo test")
    if (project_root / "go.mod").exists():
        commands.append("go test ./...")
    if (project_root / "pyproject.toml").exists():
        commands.append("python3 -m pytest")
    if not commands:
        commands.append("python3 -m unittest")
    deduped: list[str] = []
    for command in commands:
        if command not in deduped:
            deduped.append(command)
    return deduped


def _detect_tech_stack(project_root: Path) -> list[str]:
    stack: list[str] = []
    if (project_root / "pyproject.toml").exists():
        stack.append("Python project (pyproject.toml present)")
    if (project_root / "composer.json").exists():
        stack.append("PHP project (composer.json present)")
    if (project_root / "package.json").exists():
        stack.append("Node.js project (package.json present)")
    if (project_root / "Cargo.toml").exists():
        stack.append("Rust project (Cargo.toml present)")
    if (project_root / "go.mod").exists():
        stack.append("Go project (go.mod present)")
    if not stack:
        stack.append("Tech stack inferred from repository layout")
    return stack


def _build_roadmap(
    repo_name: str,
    readme: str,
    doc_titles: list[str],
    editable_paths: list[str],
    commands: list[str],
) -> str:
    milestone_titles = doc_titles or [path.rstrip("/").replace("-", " ").title() for path in editable_paths[:4] or ["core application"]]
    milestone_lines = []
    for index, title in enumerate(milestone_titles[:5], start=1):
        milestone_lines.append(f"### Milestone {index}\nStabilise and deliver the documented area: {title}.")
    in_scope = editable_paths[:6] or ["application source code", "tests", "migrations"]
    acceptance = [f"- `{command}` passes" for command in commands[:3]]
    acceptance.append("- documented user-facing flows remain available after changes")
    goal = _first_sentence(readme) or f"Consolidate and continue delivery for the existing {repo_name} application."
    return (
        "# ROADMAP.md\n\n"
        "## Project Goal\n"
        f"{goal}\n\n"
        "## Target User\n"
        "- existing application users\n"
        "- repository maintainers\n\n"
        "## Ordered Milestones\n"
        + "\n\n".join(milestone_lines)
        + "\n\n## In Scope\n"
        + "\n".join(f"- {item}" for item in in_scope)
        + "\n\n## Out of Scope\n"
        "- infrastructure redesign\n"
        "- secret rotation\n"
        "- auth model changes unless explicitly documented elsewhere\n\n"
        "## Acceptance Criteria\n"
        + "\n".join(acceptance)
        + "\n"
    )


def _build_project(
    repo_name: str,
    tech_stack: list[str],
    top_level_dirs: list[str],
    commands: list[str],
    editable_paths: list[str],
) -> str:
    repo_lines = top_level_dirs or ["src/", "tests/"]
    editable = editable_paths or ["src/", "tests/"]
    protected = [".github/", "infra/", "deploy/", "secrets/", ".env"]
    return (
        "# PROJECT.md\n\n"
        "## Tech Stack\n"
        + "\n".join(f"- {item}" for item in tech_stack)
        + "\n\n## Repo Structure\n"
        + "\n".join(f"- {item}/" if not item.endswith("/") else f"- {item}" for item in repo_lines)
        + "\n\n## Commands\n"
        + "\n".join(f"- `{command}`" for command in commands)
        + "\n\n## Editable Paths\n"
        + "\n".join(f"- `{path}`" for path in editable)
        + "\n\n## Protected Paths\n"
        + "\n".join(f"- `{path}`" for path in protected)
        + "\n\n## Environment Assumptions\n"
        f"- local development for `{repo_name}` should run without production secrets\n"
        "- deterministic verification commands must be available in the repo\n"
    )


def _build_constraints() -> str:
    return (
        "# CONSTRAINTS.md\n\n"
        "## Dependency Policy\n"
        "- do not add new runtime dependencies unless clearly justified by the task\n\n"
        "## Testing Policy\n"
        "- every task must preserve or improve automated verification coverage\n"
        "- completion commands must remain deterministic\n\n"
        "## Forbidden Changes\n"
        "- do not edit protected paths unless the brief is updated explicitly\n"
        "- do not merge directly to protected branches by default\n\n"
        "## Security Boundaries\n"
        "- do not commit secrets\n"
        "- do not weaken authentication, authorization, or input validation without an explicit requirement\n"
    )


def _build_planning_hints(commands: list[str]) -> str:
    command_lines = "\n".join(f"- prefer `{command}` when you need deterministic verification" for command in commands[:4])
    return (
        "# PLANNING_HINTS.md\n\n"
        "## Repo-Specific Hints\n"
        f"{command_lines or '- keep existing command naming as-is'}\n"
        "- preserve existing naming conventions already visible in the repository\n"
        "- prefer existing pagination, CLI flag, and folder naming patterns over inventing new ones\n"
        "- if the repo already exposes a command form, mirror it instead of introducing a synonym\n"
    )


def _build_architecture_notes(doc_titles: list[str], top_level_dirs: list[str]) -> str:
    payload = {
        "documented_areas": doc_titles,
        "top_level_dirs": top_level_dirs,
    }
    return (
        "# ARCHITECTURE_NOTES.md\n\n"
        "## Existing Documentation Signals\n"
        "The following signals were inferred from the repository during bootstrap:\n\n"
        "```json\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n```\n"
    )


def _first_sentence(text: str) -> str:
    for line in text.splitlines():
        clean = line.strip()
        if clean and not clean.startswith("#"):
            return clean.rstrip(".") + "."
    return ""
