"""Workspace and Tab navigation view component for MyFiler.

Allows managing Workspaces and their associated folder Tabs.
"""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable, Optional

from core.config import AppConfig, ExplorerTab, Workspace


class WorkspaceView(ttk.Frame):
    """Component managing Workspaces and Explorer Tabs (Left sidebar)."""

    def __init__(
        self,
        parent,
        config: AppConfig,
        on_tab_selected: Callable[[ExplorerTab], None],
        on_workspace_changed: Optional[Callable[[Workspace], None]] = None,
        on_config_modified: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent)
        self.config = config
        self.on_tab_selected = on_tab_selected
        self.on_workspace_changed = on_workspace_changed
        self.on_config_modified = on_config_modified

        self._build_ui()
        self.refresh_workspaces()

    def _build_ui(self):
        # 1. Workspace Section (Top)
        ws_frame = ttk.LabelFrame(self, text="📁 ワークスペース", padding=6)
        ws_frame.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)

        self.ws_combo_var = tk.StringVar()
        self.ws_combo = ttk.Combobox(ws_frame, textvariable=self.ws_combo_var, state="readonly")
        self.ws_combo.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))
        self.ws_combo.bind("<<ComboboxSelected>>", self._on_workspace_combo_selected)

        ws_btn_frame = ttk.Frame(ws_frame)
        ws_btn_frame.pack(side=tk.TOP, fill=tk.X)

        btn_add_ws = ttk.Button(ws_btn_frame, text="+ 新規", width=6, command=self._add_workspace)
        btn_add_ws.pack(side=tk.LEFT, padx=(0, 2))

        btn_ren_ws = ttk.Button(ws_btn_frame, text="✏ 変更", width=6, command=self._rename_workspace)
        btn_ren_ws.pack(side=tk.LEFT, padx=(0, 2))

        btn_del_ws = ttk.Button(ws_btn_frame, text="🗑 削除", width=6, command=self._delete_workspace)
        btn_del_ws.pack(side=tk.LEFT)

        # 2. Explorer Tab Section (Bottom)
        tab_frame = ttk.LabelFrame(self, text="📑 タブ (作業フォルダ)", padding=6)
        tab_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Tab List Treeview (shows Tab Name and Path)
        list_container = ttk.Frame(tab_frame)
        list_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.tab_tree = ttk.Treeview(list_container, columns=("name",), show="tree", selectmode="browse")
        self.tab_tree.column("#0", width=180, stretch=True)

        v_scroll = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.tab_tree.yview)
        self.tab_tree.configure(yscrollcommand=v_scroll.set)

        self.tab_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tab_tree.bind("<<TreeviewSelect>>", self._on_tab_selected_event)
        self.tab_tree.bind("<Button-3>", self._show_tab_context_menu)

        # Tab Action Buttons
        tab_btn_frame = ttk.Frame(tab_frame)
        tab_btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(4, 0))

        btn_add_tab = ttk.Button(tab_btn_frame, text="+ フォルダ追加", command=self._add_tab)
        btn_add_tab.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        btn_del_tab = ttk.Button(tab_btn_frame, text="🗑 削除", width=6, command=self._delete_tab)
        btn_del_tab.pack(side=tk.LEFT)

        # Tab context menu
        self._build_tab_context_menu()

    def _build_tab_context_menu(self):
        self.tab_menu = tk.Menu(self, tearoff=0)
        self.tab_menu.add_command(label="名前を変更", command=self._rename_tab)
        self.tab_menu.add_command(label="フォルダパスを変更", command=self._change_tab_path)
        self.tab_menu.add_separator()
        self.tab_menu.add_command(label="タブを削除", command=self._delete_tab)

    def refresh_workspaces(self):
        """Update workspace dropdown and select active workspace."""
        ws_names = [ws.name for ws in self.config.workspaces]
        self.ws_combo["values"] = ws_names

        active_ws = self.config.get_active_workspace()
        if active_ws and active_ws.name in ws_names:
            self.ws_combo_var.set(active_ws.name)
            self.refresh_tabs()
        elif ws_names:
            self.ws_combo_var.set(ws_names[0])
            self.config.active_workspace_id = self.config.workspaces[0].id
            self.refresh_tabs()

    def refresh_tabs(self):
        """Update tabs treeview for the currently selected workspace."""
        for row in self.tab_tree.get_children():
            self.tab_tree.delete(row)

        active_ws = self.config.get_active_workspace()
        if not active_ws:
            return

        for tab in active_ws.tabs:
            item_id = tab.id
            display_text = f"📁 {tab.name}"
            self.tab_tree.insert("", tk.END, iid=item_id, text=display_text)

        # Restore selection
        if active_ws.active_tab_id and active_ws.active_tab_id in self.tab_tree.get_children():
            self.tab_tree.selection_set(active_ws.active_tab_id)
        elif active_ws.tabs:
            first_id = active_ws.tabs[0].id
            active_ws.active_tab_id = first_id
            self.tab_tree.selection_set(first_id)

    def _on_workspace_combo_selected(self, event):
        selected_name = self.ws_combo_var.get()
        for ws in self.config.workspaces:
            if ws.name == selected_name:
                self.config.active_workspace_id = ws.id
                self.refresh_tabs()
                if self.on_workspace_changed:
                    self.on_workspace_changed(ws)
                active_tab = self.config.get_active_tab(ws)
                if active_tab:
                    self.on_tab_selected(active_tab)
                if self.on_config_modified:
                    self.on_config_modified()
                break

    def _on_tab_selected_event(self, event):
        selection = self.tab_tree.selection()
        if not selection:
            return
        selected_id = selection[0]
        active_ws = self.config.get_active_workspace()
        if not active_ws:
            return

        for tab in active_ws.tabs:
            if tab.id == selected_id:
                active_ws.active_tab_id = tab.id
                self.on_tab_selected(tab)
                if self.on_config_modified:
                    self.on_config_modified()
                break

    def _add_workspace(self):
        name = simpledialog.askstring("新規ワークスペース", "ワークスペース名を入力してください:", parent=self)
        if not name:
            return
        name = name.strip()
        if not name:
            return

        # Check duplicate
        if any(ws.name == name for ws in self.config.workspaces):
            messagebox.showwarning("警告", f"'{name}' は既に存在します。")
            return

        new_ws = Workspace.create(name=name)
        self.config.workspaces.append(new_ws)
        self.config.active_workspace_id = new_ws.id
        self.refresh_workspaces()
        if self.on_config_modified:
            self.on_config_modified()

    def _rename_workspace(self):
        active_ws = self.config.get_active_workspace()
        if not active_ws:
            return

        new_name = simpledialog.askstring(
            "ワークスペース名変更",
            "新しいワークスペース名を入力してください:",
            initialvalue=active_ws.name,
            parent=self
        )
        if not new_name or not new_name.strip():
            return
        new_name = new_name.strip()

        active_ws.name = new_name
        self.refresh_workspaces()
        if self.on_config_modified:
            self.on_config_modified()

    def _delete_workspace(self):
        active_ws = self.config.get_active_workspace()
        if not active_ws:
            return

        if len(self.config.workspaces) <= 1:
            messagebox.showinfo("通知", "最後のワークスペースは削除できません。")
            return

        confirm = messagebox.askyesno(
            "削除確認",
            f"ワークスペース '{active_ws.name}' を削除しますか？\n（※実際のフォルダやファイルは削除されません）",
            parent=self
        )
        if not confirm:
            return

        self.config.workspaces = [ws for ws in self.config.workspaces if ws.id != active_ws.id]
        self.config.active_workspace_id = self.config.workspaces[0].id
        self.refresh_workspaces()
        if self.on_config_modified:
            self.on_config_modified()

    def _add_tab(self):
        active_ws = self.config.get_active_workspace()
        if not active_ws:
            return

        selected_dir = filedialog.askdirectory(title="作業フォルダを選択", parent=self)
        if not selected_dir:
            return

        default_name = Path(selected_dir).name or selected_dir
        tab_name = simpledialog.askstring(
            "タブ名入力",
            "タブの表示名を入力してください:",
            initialvalue=default_name,
            parent=self
        )
        if not tab_name:
            tab_name = default_name

        new_tab = ExplorerTab.create(name=tab_name.strip(), path=selected_dir)
        active_ws.tabs.append(new_tab)
        active_ws.active_tab_id = new_tab.id
        self.refresh_tabs()
        self.on_tab_selected(new_tab)
        if self.on_config_modified:
            self.on_config_modified()

    def _rename_tab(self):
        selection = self.tab_tree.selection()
        if not selection:
            return
        selected_id = selection[0]
        active_ws = self.config.get_active_workspace()
        if not active_ws:
            return

        target_tab = next((t for t in active_ws.tabs if t.id == selected_id), None)
        if not target_tab:
            return

        new_name = simpledialog.askstring(
            "タブ名変更",
            "新しいタブ名を入力してください:",
            initialvalue=target_tab.name,
            parent=self
        )
        if not new_name or not new_name.strip():
            return

        target_tab.name = new_name.strip()
        self.refresh_tabs()
        if self.on_config_modified:
            self.on_config_modified()

    def _change_tab_path(self):
        selection = self.tab_tree.selection()
        if not selection:
            return
        selected_id = selection[0]
        active_ws = self.config.get_active_workspace()
        if not active_ws:
            return

        target_tab = next((t for t in active_ws.tabs if t.id == selected_id), None)
        if not target_tab:
            return

        new_dir = filedialog.askdirectory(
            title="新しいフォルダを選択",
            initialdir=target_tab.path if Path(target_tab.path).exists() else None,
            parent=self
        )
        if not new_dir:
            return

        target_tab.path = new_dir
        self.on_tab_selected(target_tab)
        if self.on_config_modified:
            self.on_config_modified()

    def _delete_tab(self):
        selection = self.tab_tree.selection()
        if not selection:
            return
        selected_id = selection[0]
        active_ws = self.config.get_active_workspace()
        if not active_ws:
            return

        target_tab = next((t for t in active_ws.tabs if t.id == selected_id), None)
        if not target_tab:
            return

        confirm = messagebox.askyesno(
            "削除確認",
            f"タブ '{target_tab.name}' を削除しますか？\n（※実際のフォルダやファイルは削除されません）",
            parent=self
        )
        if not confirm:
            return

        active_ws.tabs = [t for t in active_ws.tabs if t.id != selected_id]
        if active_ws.active_tab_id == selected_id:
            active_ws.active_tab_id = active_ws.tabs[0].id if active_ws.tabs else None

        self.refresh_tabs()
        active_tab = self.config.get_active_tab(active_ws)
        if active_tab:
            self.on_tab_selected(active_tab)
        if self.on_config_modified:
            self.on_config_modified()

    def _show_tab_context_menu(self, event):
        iid = self.tab_tree.identify_row(event.y)
        if iid:
            self.tab_tree.selection_set(iid)
            self.tab_menu.post(event.x_root, event.y_root)
