"""Execution policy helpers."""
from __future__ import annotations

import shlex
from pathlib import Path


def _normalize_prefix(prefix: str) -> str:
    """Collapse glob suffixes (/** or /*) into a plain directory prefix."""
    item = prefix.replace("\\", "/")
    # gacli/**  -> gacli   |   gacli/*  -> gacli   |   gacli/  -> gacli
    while item.endswith("/**") or item.endswith("/*"):
        item = item.rsplit("/", 1)[0]
    return item.rstrip("/")


def path_under(path: str, prefixes: list[str]) -> bool:
    # Wildcard "**" or "*" in allowed_paths means all paths are permitted.
    if any(p.strip() in {"**", "*"} for p in prefixes):
        return True
    norm = path.replace("\\", "/").lstrip("./").rstrip("/")
    for prefix in prefixes:
        item = _normalize_prefix(prefix)
        # changed file is inside an allowed prefix: gacli/main.py under gacli/
        if norm == item or norm.startswith(item + "/"):
            return True
        # changed path is a directory that contains an allowed file: bin/ contains bin/ga
        if item.startswith(norm + "/"):
            return True
    return False


def validate_baseline_spec(task: dict, repo_root: Path) -> list[str]:
    """Return warnings when baseline commands reference files that the task
    is supposed to create (i.e. listed in allowed_paths but not yet present).

    The correct pattern for tasks that create files from scratch is to set
    baseline_commands: [] — an empty list skips the baseline entirely.
    """
    warnings: list[str] = []
    baseline = list(task.get("baseline_commands", task.get("test_commands", [])))
    allowed = list(task.get("allowed_paths", []))
    task_id = task.get("id", "<unknown>")

    for cmd in baseline:
        try:
            parts = shlex.split(cmd)
        except ValueError:
            continue
        for part in parts:
            if part.startswith("-"):
                continue
            p = Path(part)
            if not p.suffix:
                continue
            if not (repo_root / p).exists():
                for a in allowed:
                    if str(p) == a or str(p).startswith(a.rstrip("/") + "/"):
                        warnings.append(
                            f"Task '{task_id}': baseline command {cmd!r} references"
                            f" '{p}' which is in allowed_paths but does not exist."
                            f" If this task creates the file from scratch, use"
                            f" baseline_commands: []"
                        )
                        break
    return warnings


def validate_changed_files(
    files: list[str],
    *,
    allowed_paths: list[str],
    protected_paths: list[str],
) -> list[str]:
    violations: list[str] = []
    for path in files:
        if path_under(path, protected_paths):
            violations.append(f"protected:{path}")
        elif allowed_paths and not path_under(path, allowed_paths):
            violations.append(f"outside_allowed:{path}")
    return violations
