"""Git helpers for worktree-based execution."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def changed_files(repo: Path) -> list[str]:
    result = git(repo, "status", "--porcelain")
    files: list[str] = []
    for line in result.stdout.splitlines():
        line = line.rstrip()
        if not line:
            continue
        part = line[3:] if len(line) > 3 else line
        if " -> " in part:
            part = part.split(" -> ", 1)[1]
        files.append(part.strip())
    return sorted(set(files))


def create_worktree(root: Path, worktree: Path, base_ref: str, branch: str) -> None:
    if worktree.exists():
        shutil.rmtree(worktree)
    result = git(root, "worktree", "add", "--detach", str(worktree), base_ref)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git worktree add failed")
    result = git(worktree, "checkout", "-b", branch)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git checkout -b failed")


def remove_worktree(root: Path, worktree: Path) -> None:
    if worktree.exists():
        git(root, "worktree", "remove", "--force", str(worktree))
