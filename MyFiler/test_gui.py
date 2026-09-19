"""GUI integration tests for MyFiler."""

import os
from pathlib import Path
import tempfile
import unittest

from core.config import ConfigManager
from ui.main_window import MainWindow


class TestGUIIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_file = os.path.join(self.temp_dir.name, "test_config.json")
        self.config_manager = ConfigManager(self.config_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_main_window_lifecycle(self):
        # Create MainWindow and process idle events
        app = MainWindow(self.config_manager)
        app.update_idletasks()

        # Check that workspace and file list components are mounted
        self.assertIsNotNone(app.workspace_view)
        self.assertIsNotNone(app.file_list_view)

        # Check default workspace creation
        self.assertGreaterEqual(len(app.app_config.workspaces), 1)

        # Navigate to temp_dir
        app.file_list_view.navigate_to(self.temp_dir.name)
        app.update_idletasks()
        self.assertEqual(app.file_list_view.current_path, str(Path(self.temp_dir.name).resolve()))

        # Close and check config saved
        app._on_close()
        self.assertTrue(os.path.exists(self.config_file))

    def test_workspace_operations(self):
        app = MainWindow(self.config_manager)
        app.update_idletasks()

        # Add a new workspace programmatically
        new_ws = app.app_config.workspaces[0]
        tab1 = app.app_config.get_active_tab(new_ws)
        self.assertIsNotNone(tab1)

        # Trigger selection
        app.workspace_view._on_tab_selected_event(None)
        app.update_idletasks()

        app.destroy()


if __name__ == "__main__":
    unittest.main()
