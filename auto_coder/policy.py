"""Execution policy helpers."""
from __future__ import annotations

import re
import shlex
from pathlib import Path


# Pytest -k expressions use Python boolean operators, not regex.
# Common mistakes: using | instead of 'or', & instead of 'and'
PYTEST_K_REGEX_OPERATORS = re.compile(r"-k\s*['\"][^'\"]*\|[^'\"]*['\"]")
PYTEST_K_FIXES = [
    (re.compile(r"\|"), " or "),
    (re.compile(r"&"), " and "),
    (re.compile(r"!"), " not "),
]


def validate_pytest_k_syntax(commands: list[str]) -> list[str]:
    """Validate pytest -k expressions for common syntax errors.

    Pytest's -k option uses Python boolean expressions, not regex.
    Common mistake: using | instead of 'or', & instead of 'and'.

    Returns list of warnings for commands with invalid syntax.
    """
    warnings: list[str] = []
    for cmd in commands:
        if "pytest" not in cmd:
            continue
        if "-k" not in cmd:
            continue

        # Check for regex operators in -k expression
        if PYTEST_K_REGEX_OPERATORS.search(cmd):
            # Extract the -k expression for the warning
            match = re.search(r"-k\s*['\"]([^'\"]+)['\"]", cmd)
            expr = match.group(1) if match else "<unknown>"
            warnings.append(
                f"pytest -k expression uses regex syntax: '{expr}'. "
                f"Use 'or' instead of '|', 'and' instead of '&', 'not' instead of '!'."
            )
    return warnings


def fix_pytest_k_syntax(commands: list[str]) -> list[str]:
    """Auto-fix common pytest -k syntax errors.

    Converts regex operators to Python boolean operators:
    - | -> or
    - & -> and
    - ! -> not (at start of word)
    """
    fixed: list[str] = []
    for cmd in commands:
        if "pytest" not in cmd or "-k" not in cmd:
            fixed.append(cmd)
            continue

        # Find and fix the -k expression
        def replace_expr(m: re.Match) -> str:
            expr = m.group(1)
            original = expr
            for pattern, replacement in PYTEST_K_FIXES:
                expr = pattern.sub(replacement, expr)
            # Clean up extra spaces
            expr = re.sub(r"\s+", " ", expr).strip()
            if expr != original:
                pass  # Was fixed
            return f"-k '{expr}'"

        # Match -k followed by quoted expression
        cmd_fixed = re.sub(r"-k\s*['\"]([^'\"]+)['\"]", replace_expr, cmd)
        fixed.append(cmd_fixed)

    return fixed


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


# Paths that should always be ignored (auto-generated, never committed)
IGNORED_PATTERNS = [
    "__pycache__",
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".egg-info",
]


def _should_ignore(path: str) -> bool:
    """Check if path should be ignored (auto-generated artifacts)."""
    norm = path.replace("\\", "/")
    for pattern in IGNORED_PATTERNS:
        if pattern in norm:
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
        # Skip auto-generated artifacts that should never be committed
        if _should_ignore(path):
            continue
        if path_under(path, protected_paths):
            violations.append(f"protected:{path}")
        elif allowed_paths and not path_under(path, allowed_paths):
            violations.append(f"outside_allowed:{path}")
    return violations
