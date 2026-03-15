"""Tests for config discovery and loading."""
from __future__ import annotations
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_coder.config import find_project_root, load_config, AUTO_CODER_DIR


class TestFindProjectRoot(unittest.TestCase):
    def test_finds_root_in_current_dir(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / AUTO_CODER_DIR).mkdir()
            found = find_project_root(root)
            self.assertEqual(found, root)

    def test_finds_root_in_parent(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / AUTO_CODER_DIR).mkdir()
            subdir = root / "src" / "module"
            subdir.mkdir(parents=True)
            found = find_project_root(subdir)
            self.assertEqual(found, root)

    def test_raises_when_not_found(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                find_project_root(Path(tmp))


class TestLoadConfig(unittest.TestCase):
    def test_returns_defaults_when_no_yaml(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / AUTO_CODER_DIR).mkdir()
            config = load_config(root)
            self.assertEqual(config["base_branch"], "main")
            self.assertTrue(config["dry_run"])
            self.assertIsInstance(config["project_root"], Path)

    def test_user_values_override_defaults(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            acd = root / AUTO_CODER_DIR
            acd.mkdir()
            (acd / "config.yaml").write_text(
                "base_branch: develop\ndry_run: false\n", encoding="utf-8"
            )
            config = load_config(root)
            self.assertEqual(config["base_branch"], "develop")
            self.assertFalse(config["dry_run"])

    def test_path_keys_are_path_objects(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / AUTO_CODER_DIR).mkdir()
            config = load_config(root)
            self.assertIsInstance(config["state_path"], Path)
            self.assertIsInstance(config["state_db_path"], Path)
            self.assertIsInstance(config["tasks_generated_path"], Path)
            self.assertIsInstance(config["tasks_local_path"], Path)
            self.assertIsInstance(config["reports_root"], Path)
            self.assertIsInstance(config["worktree_root"], Path)


if __name__ == "__main__":
    unittest.main()
