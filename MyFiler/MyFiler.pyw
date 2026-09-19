"""Entry point for MyFiler application."""

import ctypes
import os
import sys

from core.config import ConfigManager
from ui.main_window import MainWindow


def enable_high_dpi_awareness():
    """Enable high-DPI awareness on Windows to prevent blurry text."""
    if sys.platform == "win32":
        try:
            # PROCESS_PER_MONITOR_DPI_AWARE = 2
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def main():
    enable_high_dpi_awareness()
    config_manager = ConfigManager()
    app = MainWindow(config_manager)
    app.mainloop()


if __name__ == "__main__":
    main()
