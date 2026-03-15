"""Execution policy helpers."""
from __future__ import annotations


def path_under(path: str, prefixes: list[str]) -> bool:
    norm = path.replace("\\", "/").lstrip("./")
    for prefix in prefixes:
        item = prefix.replace("\\", "/").rstrip("/")
        if norm == item or norm.startswith(item + "/"):
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
