"""Tests for CLI bootstrap commands."""
from __future__ import annotations

import argparse
import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from contextlib import redirect_stdout

from auto_coder.brief_validator import BriefValidationResult
from auto_coder.cli import cmd_bootstrap_brief, cmd_doctor, cmd_init
from auto_coder.config import AUTO_CODER_DIR
from auto_coder.storage import ensure_database
from auto_coder.config import load_config


class TestCliInit(unittest.TestCase):
    def test_init_creates_config_and_state_db(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = argparse.Namespace(path=str(root), force=False)
            exit_code = cmd_init(args)
            self.assertEqual(exit_code, 0)
            self.assertTrue((root / AUTO_CODER_DIR / "config.yaml").exists())
            self.assertTrue((root / AUTO_CODER_DIR / "state.db").exists())

    def test_init_writes_gitignore_runtime_entries(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = argparse.Namespace(path=str(root), force=False)
            cmd_init(args)
            content = (root / AUTO_CODER_DIR / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("state.db", content)
            self.assertIn("reports/", content)


class TestCliDoctor(unittest.TestCase):
    def test_doctor_fails_when_brief_validation_fails(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            acd = root / AUTO_CODER_DIR
            acd.mkdir(parents=True, exist_ok=True)
            ensure_database(acd / "state.db")
            config = load_config(root)
            invalid = BriefValidationResult(missing_sections=["PROJECT.md::Commands"])

            def fake_run(*args, **kwargs):
                class Result:
                    returncode = 0
                    stdout = "origin\tgit@example.com:repo.git (fetch)\n"
                return Result()

            stream = io.StringIO()
            with patch("auto_coder.cli.find_project_root", return_value=root), \
                 patch("auto_coder.cli.load_config", return_value=config), \
                 patch("auto_coder.cli.validate_project_brief", return_value=invalid), \
                 patch("auto_coder.cli.shutil.which", return_value="/usr/bin/fake"), \
                 patch("subprocess.run", side_effect=fake_run), \
                 patch("auto_coder.git_ops.resolve_worktree_base_ref", return_value="main"), \
                 redirect_stdout(stream):
                exit_code = cmd_doctor(argparse.Namespace())

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("Brief validation:", output)
            self.assertIn("FAIL", output)
            self.assertNotIn("All checks passed.", output)

    def test_doctor_runs_live_probe_when_requested(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            acd = root / AUTO_CODER_DIR
            acd.mkdir(parents=True, exist_ok=True)
            ensure_database(acd / "state.db")
            config = load_config(root)
            config["manager_backend"] = "codex"
            valid = BriefValidationResult()

            def fake_run(*args, **kwargs):
                class Result:
                    returncode = 0
                    stdout = "origin\tgit@example.com:repo.git (fetch)\n"
                return Result()

            stream = io.StringIO()
            with patch("auto_coder.cli.find_project_root", return_value=root), \
                 patch("auto_coder.cli.load_config", return_value=config), \
                 patch("auto_coder.cli.validate_project_brief", return_value=valid), \
                 patch("auto_coder.cli._probe_manager_backend", return_value='{"status":"ok"}'), \
                 patch("auto_coder.cli.shutil.which", return_value="/usr/bin/fake"), \
                 patch("subprocess.run", side_effect=fake_run), \
                 patch("auto_coder.git_ops.resolve_worktree_base_ref", return_value="main"), \
                 redirect_stdout(stream):
                exit_code = cmd_doctor(argparse.Namespace(probe_live=True))

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Live probe:", output)
            self.assertIn("manager live probe succeeded", output)


class TestBootstrapBrief(unittest.TestCase):
    def test_bootstrap_brief_creates_expected_files(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Demo\n\nExisting repository for tests.\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "api.md").write_text("# API\n\nNotes.\n", encoding="utf-8")
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = cmd_bootstrap_brief(argparse.Namespace(path=str(root), force=False))

            self.assertEqual(exit_code, 0)
            self.assertTrue((root / "ROADMAP.md").exists())
            self.assertTrue((root / "PROJECT.md").exists())
            self.assertTrue((root / "PLANNING_HINTS.md").exists())


if __name__ == "__main__":
    unittest.main()
