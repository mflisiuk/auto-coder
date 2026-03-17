"""Execution policy helpers."""
from __future__ import annotations


def _normalize_prefix(prefix: str) -> str:
    """Collapse glob suffixes (/** or /*) into a plain directory prefix."""
    item = prefix.replace("\\", "/")
    # gacli/**  -> gacli   |   gacli/*  -> gacli   |   gacli/  -> gacli
    while item.endswith("/**") or item.endswith("/*"):
        item = item.rsplit("/", 1)[0]
    return item.rstrip("/")


def path_under(path: str, prefixes: list[str]) -> bool:
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
