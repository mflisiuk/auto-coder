"""Execution helpers for running validation commands."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from auto_coder.reports import ensure_dir, save_json, write_text


# pytest exit code 5 means "no tests were collected".
# For baseline runs this is not a failure — it means the tests don't exist yet
# and the current task is expected to create them.
PYTEST_NO_TESTS_COLLECTED = 5


def run_tests(
    commands: list[str],
    worktree: Path,
    report_dir: Path,
    timeout_minutes: int,
    *,
    prefix: str = "tests",
    skip_no_tests: bool = False,
) -> tuple[bool, list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    all_passed = True
    ensure_dir(report_dir / prefix)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(worktree)

    for index, cmd in enumerate(commands, start=1):
        result = subprocess.run(
            ["bash", "-lc", cmd],
            cwd=str(worktree),
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout_minutes * 60,
            check=False,
        )
        no_tests = result.returncode == PYTEST_NO_TESTS_COLLECTED
        passed = result.returncode == 0 or (skip_no_tests and no_tests)
        write_text(report_dir / prefix / f"test-{index:02d}.stdout.log", result.stdout)
        write_text(report_dir / prefix / f"test-{index:02d}.stderr.log", result.stderr)
        results.append(
            {
                "index": index,
                "command": cmd,
                "returncode": result.returncode,
                "passed": passed,
                "skipped_no_tests": no_tests and skip_no_tests,
            }
        )
        if not passed:
            all_passed = False

    save_json(report_dir / f"{prefix}.json", {"passed": all_passed, "results": results})
    return all_passed, results
