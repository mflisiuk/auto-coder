"""Git helpers for worktree-based execution."""
from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

IGNORED_RUNTIME_FILES = {"AGENT_REPORT.json"}


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
        normalized = part.strip()
        if normalized in IGNORED_RUNTIME_FILES:
            continue
        files.append(normalized)
    return sorted(set(files))


def ref_exists(repo: Path, ref: str) -> bool:
    result = git(repo, "rev-parse", "--verify", ref)
    return result.returncode == 0


def resolve_worktree_base_ref(root: Path, configured_ref: str | None, base_branch: str) -> str:
    candidates = []
    if configured_ref:
        candidates.append(str(configured_ref))
    remote_candidate = f"origin/{base_branch}"
    if remote_candidate not in candidates:
        candidates.append(remote_candidate)
    if base_branch not in candidates:
        candidates.append(base_branch)
    candidates.append("HEAD")

    for candidate in candidates:
        if ref_exists(root, candidate):
            return candidate
    raise RuntimeError(
        "No valid worktree base ref found. Commit the repository first or set "
        "worktree_base_ref to an existing branch/ref."
    )


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


def cleanup_worktrees(
    root: Path,
    worktree_root: Path,
    *,
    remove_names: set[str] | None = None,
    older_than_days: int | None = None,
) -> list[str]:
    removed: list[str] = []
    if not worktree_root.exists():
        return removed

    cutoff = None
    if older_than_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

    for entry in worktree_root.iterdir():
        if not entry.is_dir():
            continue
        should_remove = False
        if remove_names and entry.name in remove_names:
            should_remove = True
        elif cutoff is not None:
            modified_at = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc)
            should_remove = modified_at <= cutoff
        if should_remove:
            remove_worktree(root, entry)
            if entry.exists():
                shutil.rmtree(entry, ignore_errors=True)
            removed.append(entry.name)
    return removed
