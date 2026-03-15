"""Tests for CLI bootstrap commands."""
from __future__ import annotations

import argparse
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_coder.cli import cmd_init
from auto_coder.config import AUTO_CODER_DIR


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


if __name__ == "__main__":
    unittest.main()
