"""Execution helpers for running validation commands."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from auto_coder.reports import ensure_dir, save_json, write_text


def run_tests(
    commands: list[str],
    worktree: Path,
    report_dir: Path,
    timeout_minutes: int,
    *,
    prefix: str = "tests",
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
        write_text(report_dir / prefix / f"test-{index:02d}.stdout.log", result.stdout)
        write_text(report_dir / prefix / f"test-{index:02d}.stderr.log", result.stderr)
        results.append(
            {
                "index": index,
                "command": cmd,
                "returncode": result.returncode,
                "passed": result.returncode == 0,
            }
        )
        if result.returncode != 0:
            all_passed = False

    save_json(report_dir / f"{prefix}.json", {"passed": all_passed, "results": results})
    return all_passed, results
