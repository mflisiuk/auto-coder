"""Tests for git worktree cleanup helpers."""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from auto_coder.git_ops import changed_files, cleanup_worktrees, resolve_worktree_base_ref


class TestGitOps(unittest.TestCase):
    def test_changed_files_ignores_agent_report_runtime_artifact(self):
        fake_status = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout="?? AGENT_REPORT.json\n M src/app.py\n",
            stderr="",
        )
        with patch("auto_coder.git_ops.git", return_value=fake_status):
            files = changed_files(Path("/tmp/repo"))
        self.assertEqual(files, ["src/app.py"])

    def test_cleanup_worktrees_removes_requested_names(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            worktree_root = root / "worktrees"
            target = worktree_root / "run-1"
            keep = worktree_root / "run-2"
            target.mkdir(parents=True)
            keep.mkdir(parents=True)

            with patch("auto_coder.git_ops.remove_worktree") as remove_worktree:
                removed = cleanup_worktrees(root, worktree_root, remove_names={"run-1"})

            self.assertEqual(removed, ["run-1"])
            remove_worktree.assert_called_once()
            self.assertFalse(target.exists())
            self.assertTrue(keep.exists())

    def test_resolve_worktree_base_ref_falls_back_to_head(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True, capture_output=True, text=True)
            (root / "README.md").write_text("hello\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True, text=True)

            resolved = resolve_worktree_base_ref(root, "origin/main", "main")

            self.assertEqual(resolved, "main")

    def test_resolve_worktree_base_ref_raises_without_commit(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True, text=True)

            with self.assertRaises(RuntimeError):
                resolve_worktree_base_ref(root, "origin/main", "main")


if __name__ == "__main__":
    unittest.main()
