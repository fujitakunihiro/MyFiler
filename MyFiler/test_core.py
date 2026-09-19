"""Unit tests for MyFiler core modules."""

import os
from pathlib import Path
import tempfile
import unittest

from core.config import AppConfig, ConfigManager, ExplorerTab, Workspace
from core.file_manager import FileManager


class TestCore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_file = os.path.join(self.temp_dir.name, "test_config.json")
        self.config_manager = ConfigManager(self.config_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_config_save_and_load(self):
        tab1 = ExplorerTab.create("Source", "C:\\Project\\src")
        tab2 = ExplorerTab.create("Logs", "C:\\Project\\logs")
        ws = Workspace.create("Project Alpha", [tab1, tab2])
        ws.active_tab_id = tab1.id

        config = AppConfig(
            workspaces=[ws],
            active_workspace_id=ws.id,
            window_width=1200,
            window_height=800
        )

        saved = self.config_manager.save_config(config)
        self.assertTrue(saved)
        self.assertTrue(os.path.exists(self.config_file))

        loaded = self.config_manager.load_config()
        self.assertEqual(len(loaded.workspaces), 1)
        self.assertEqual(loaded.workspaces[0].name, "Project Alpha")
        self.assertEqual(len(loaded.workspaces[0].tabs), 2)
        self.assertEqual(loaded.workspaces[0].tabs[0].name, "Source")
        self.assertEqual(loaded.workspaces[0].tabs[0].path, "C:\\Project\\src")
        self.assertEqual(loaded.active_workspace_id, ws.id)
        self.assertEqual(loaded.window_width, 1200)

    def test_file_manager_listing(self):
        # Create dummy structure
        sub_dir = Path(self.temp_dir.name) / "subdir"
        sub_dir.mkdir()
        file1 = Path(self.temp_dir.name) / "test1.txt"
        file1.write_text("hello", encoding="utf-8")
        file2 = Path(self.temp_dir.name) / "test2.log"
        file2.write_text("world", encoding="utf-8")

        items, err = FileManager.list_directory(self.temp_dir.name)
        self.assertIsNone(err)
        self.assertEqual(len(items), 3)

        # Directory should come first
        self.assertTrue(items[0].is_dir)
        self.assertEqual(items[0].name, "subdir")
        self.assertEqual(items[0].icon, "📁")

        # Files after directory
        self.assertFalse(items[1].is_dir)
        self.assertEqual(items[1].icon, "📄")

    def test_file_manager_size_format(self):
        self.assertEqual(FileManager.format_size(500), "500 B")
        self.assertEqual(FileManager.format_size(2048), "2.0 KB")
        self.assertEqual(FileManager.format_size(1024 * 1024 * 5), "5.0 MB")

    def test_file_operations(self):
        base_dir = self.temp_dir.name

        # 1. Create folder and file
        err = FileManager.create_folder(base_dir, "MyNewFolder")
        self.assertIsNone(err)
        self.assertTrue((Path(base_dir) / "MyNewFolder").is_dir())

        err = FileManager.create_text_file(base_dir, "sample.txt")
        self.assertIsNone(err)
        self.assertTrue((Path(base_dir) / "sample.txt").is_file())

        # 2. Rename item
        src_file = str(Path(base_dir) / "sample.txt")
        err = FileManager.rename_item(src_file, "renamed.txt")
        self.assertIsNone(err)
        self.assertFalse((Path(base_dir) / "sample.txt").exists())
        self.assertTrue((Path(base_dir) / "renamed.txt").exists())

        # 3. Copy & Paste
        renamed_file = str(Path(base_dir) / "renamed.txt")
        target_folder = str(Path(base_dir) / "MyNewFolder")
        err = FileManager.paste_item(renamed_file, target_folder, is_cut=False)
        self.assertIsNone(err)
        self.assertTrue((Path(base_dir) / "renamed.txt").exists())
        self.assertTrue((Path(target_folder) / "renamed.txt").exists())

        # 4. Delete item
        err = FileManager.delete_item(renamed_file)
        self.assertIsNone(err)
        self.assertFalse((Path(base_dir) / "renamed.txt").exists())

    def test_zip_operations(self):
        base_dir = self.temp_dir.name
        folder_to_zip = Path(base_dir) / "ZipTargetFolder"
        folder_to_zip.mkdir()
        (folder_to_zip / "inner_file.txt").write_text("compressed content", encoding="utf-8")

        # 1. Compress folder to zip
        zip_path, err = FileManager.compress_to_zip(str(folder_to_zip))
        self.assertIsNone(err)
        self.assertIsNotNone(zip_path)
        self.assertTrue(Path(zip_path).exists())
        self.assertTrue(zip_path.endswith(".zip"))

        # 2. Extract zip
        dest_dir, err = FileManager.extract_zip(zip_path)
        self.assertIsNone(err)
        self.assertIsNotNone(dest_dir)
        self.assertTrue(Path(dest_dir).exists())
        self.assertTrue((Path(dest_dir) / "ZipTargetFolder" / "inner_file.txt").exists())


if __name__ == "__main__":
    unittest.main()
