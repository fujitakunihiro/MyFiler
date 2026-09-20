"""Main application window for MyFiler.

Integrates WorkspaceView and FileListView in a split-pane layout.
"""

from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

from core.config import AppConfig, ConfigManager, ExplorerTab, Workspace
from ui.file_list_view import FileListView
from ui.workspace_view import WorkspaceView


class MainWindow(tk.Tk):
    """Main window class for MyFiler."""

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.app_config: AppConfig = self.config_manager.load_config()

        self._setup_window()
        self._build_menu()
        self._build_ui()
        self._bind_workspace_shortcuts()
        self._restore_initial_view()

    def _bind_workspace_shortcuts(self):
        for number in range(1, 10):
            self.bind_all(f"<Control-Key-{number}>", lambda event, n=number: self._switch_workspace_shortcut(n))

    def _switch_workspace_shortcut(self, number: int):
        self.workspace_view.select_workspace_by_shortcut(number)
        return "break"

    def _setup_window(self):
        self.title("MyFiler - 仕事用ファイラー")
        self.geometry(f"{self.app_config.window_width}x{self.app_config.window_height}")
        self.minsize(700, 450)
        self._set_app_icon()

        # Keep the visual language native to Windows while making the hierarchy
        # easier to scan.  This uses only ttk, so no extra theme package is
        # required.
        style = ttk.Style(self)
        # Use the clean Windows UI font when available; Tk falls back safely
        # on systems where Yu Gothic UI is not installed.
        for font_name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(font_name).configure(family="Yu Gothic UI", size=9)
            except tk.TclError:
                pass
        try:
            style.theme_use("vista")
        except tk.TclError:
            style.theme_use("clam")
        # Paris palette: limestone facades, slate roofs, muted shutters and
        # warm terracotta/brass accents.
        style.configure("App.TFrame", background="#f3eee5")
        style.configure("Sidebar.TFrame", background="#e7dfd2")
        style.configure("Toolbar.TFrame", background="#fbf8f2")
        style.configure("Panel.TLabelframe", background="#e7dfd2", bordercolor="#c9bca9")
        style.configure("Panel.TLabelframe.Label", background="#e7dfd2", foreground="#394b57", font=("Yu Gothic UI", 9, "bold"))
        style.configure("Section.TLabel", background="#e7dfd2", foreground="#586c72", font=("Yu Gothic UI", 9, "bold"))
        style.configure("Path.TLabel", background="#fbf8f2", foreground="#657277", font=("Yu Gothic UI", 9))
        style.configure("Status.TLabel", background="#ddd2c2", foreground="#4e5d61", padding=(10, 5))
        style.configure("ToolbarIcon.TButton", font=("Segoe UI Symbol", 12), padding=(2, 1), width=3)
        style.configure("Treeview", rowheight=28, font=("Yu Gothic UI", 9), background="#fffdf9", fieldbackground="#fffdf9")
        style.configure("Treeview.Heading", background="#d7c8b5", foreground="#394b57", font=("Yu Gothic UI", 9, "bold"), padding=(8, 6))
        style.map("Treeview", background=[("selected", "#b9c7c1")], foreground=[("selected", "#263c43")])
        style.configure("Accent.TButton", foreground="#7b4b3d", font=("Yu Gothic UI", 9, "bold"))

        # Intercept window close to save settings
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_app_icon(self):
        """Set a small folder/document icon without external image assets."""
        icon = tk.PhotoImage(width=16, height=16)
        icon.put("#f3eee5", to=(0, 0, 16, 16))
        # Document behind the folder.
        icon.put("#fffdf9", to=(5, 2, 13, 12))
        icon.put("#b9c7c1", to=(5, 2, 13, 3))
        icon.put("#d7c8b5", to=(6, 5, 12, 6))
        icon.put("#d7c8b5", to=(6, 8, 11, 9))
        # Limestone/terracotta folder in front.
        icon.put("#b76e57", to=(2, 7, 14, 14))
        icon.put("#c88968", to=(3, 5, 9, 8))
        icon.put("#d7a07d", to=(3, 8, 13, 9))
        self._app_icon = icon
        self.iconphoto(True, self._app_icon)

    def _build_menu(self):
        menubar = tk.Menu(self)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="設定を保存", command=self._save_config)
        file_menu.add_separator()
        file_menu.add_command(label="終了", command=self._on_close)
        menubar.add_cascade(label="ファイル (F)", menu=file_menu)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="MyFilerについて", command=self._show_about)
        menubar.add_cascade(label="ヘルプ (H)", menu=help_menu)

        self.configure(menu=menubar)

    def _build_ui(self):
        # Main split paned window
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.FLAT, sashwidth=5, bg="#b08d68", bd=0)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left pane: Workspace & Tab Management
        self.workspace_view = WorkspaceView(
            parent=paned,
            config=self.app_config,
            on_tab_selected=self._on_tab_selected,
            on_workspace_changed=self._on_workspace_changed,
            on_config_modified=self._save_config
        )
        self.configure(bg="#f3eee5")
        paned.add(self.workspace_view, minsize=220, width=260)

        # Right pane: File List
        self.file_list_view = FileListView(
            parent=paned,
            on_path_changed=self._on_path_changed
        )
        paned.add(self.file_list_view, minsize=400)

    def _restore_initial_view(self):
        """Restore previous active workspace and tab on startup."""
        active_ws = self.app_config.get_active_workspace()
        if active_ws:
            active_tab = self.app_config.get_active_tab(active_ws)
            if active_tab and active_tab.path:
                self.file_list_view.navigate_to(active_tab.path)

    def _on_tab_selected(self, tab: ExplorerTab):
        """Callback when a tab is clicked in the left sidebar."""
        if tab.path:
            self.file_list_view.navigate_to(tab.path)
            self._update_title(tab.name)

    def _on_workspace_changed(self, workspace: Workspace):
        """Callback when a workspace is changed."""
        self._update_title()

    def _on_path_changed(self, new_path: str):
        """Callback when navigating directories in file list view."""
        # Optionally update the active tab's current path
        active_ws = self.app_config.get_active_workspace()
        if active_ws:
            active_tab = self.app_config.get_active_tab(active_ws)
            if active_tab:
                # Update window title
                self._update_title(f"{active_tab.name} - {Path(new_path).name}")

    def _update_title(self, extra_info: str = ""):
        active_ws = self.app_config.get_active_workspace()
        ws_name = active_ws.name if active_ws else "MyFiler"
        if extra_info:
            self.title(f"MyFiler - [{ws_name}] {extra_info}")
        else:
            self.title(f"MyFiler - [{ws_name}]")

    def _save_config(self):
        """Persist window state and workspace config to JSON."""
        self.app_config.window_width = self.winfo_width()
        self.app_config.window_height = self.winfo_height()
        self.config_manager.save_config(self.app_config)

    def _show_about(self):
        messagebox.showinfo(
            "MyFiler について",
            "MyFiler v1.0\n\n"
            "仕事用フォルダ管理・作業切り替え支援ファイラー\n"
            "Windows Explorerと連携し、タスク別の作業場所を整理します。\n\n"
            "※Python標準ライブラリのみで動作し、外部通信は行いません。"
        )

    def _on_close(self):
        """Handle window close event."""
        self._save_config()
        self.destroy()
