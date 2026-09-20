"""File list view component for MyFiler.

Renders directory contents using ttk.Treeview with sorting, navigation,
full right-click context menus, and Explorer-like file operations (including ZIP compression/extraction).
"""

from pathlib import Path
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable, List, Optional

from core.file_manager import FileItem, FileManager


class FileListView(ttk.Frame):
    """Component displaying files and folders with full context menu support."""

    def __init__(self, parent, on_path_changed: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self.on_path_changed = on_path_changed
        self.current_path: str = ""
        self.items: List[FileItem] = []
        self._sort_column: str = "name"
        self._sort_reverse: bool = False
        self._navigation_history: List[str] = []
        self._history_index: int = -1

        # Clipboard for cut/copy operations
        self._clipboard_path: Optional[str] = None
        self._clipboard_is_cut: bool = False

        self._build_ui()

    def _create_item_icons(self):
        """Create crisp 16px icons that render consistently across Windows fonts."""
        self._folder_icon = tk.PhotoImage(width=16, height=16)
        self._folder_icon.put("#fffdf9", to=(0, 0, 16, 16))
        self._folder_icon.put("#8c5a3c", to=(1, 5, 15, 14))
        self._folder_icon.put("#c8894f", to=(2, 4, 8, 6))
        self._folder_icon.put("#dca86b", to=(2, 7, 14, 12))
        self._folder_icon.put("#b57444", to=(2, 13, 14, 14))

        self._file_icon = tk.PhotoImage(width=16, height=16)
        self._file_icon.put("#fffdf9", to=(0, 0, 16, 16))
        self._file_icon.put("#71828a", to=(4, 2, 13, 14))
        self._file_icon.put("#eef2ef", to=(5, 3, 12, 13))
        self._file_icon.put("#c88968", to=(5, 5, 10, 6))
        self._file_icon.put("#b9c7c1", to=(5, 8, 11, 9))
        self._file_icon.put("#b9c7c1", to=(5, 11, 10, 12))

    def _build_ui(self):
        self._create_item_icons()
        # 1. Top Navigation & Path Bar
        nav_frame = ttk.Frame(self, padding=(12, 10, 12, 8), style="Toolbar.TFrame")
        nav_frame.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(nav_frame, text="現在地", style="Path.TLabel").pack(side=tk.LEFT, padx=(0, 8))
        self.btn_up = ttk.Button(nav_frame, text="↑", width=3, command=self._navigate_up)
        self.btn_up.pack(side=tk.LEFT, padx=(0, 2))

        self.btn_reload = ttk.Button(nav_frame, text="↻", width=3, command=self.reload)
        self.btn_reload.pack(side=tk.LEFT, padx=(0, 4))

        self.path_var = tk.StringVar()
        self.path_entry = ttk.Entry(nav_frame, textvariable=self.path_var)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.path_entry.bind("<Return>", lambda e: self.navigate_to(self.path_var.get()))

        self.btn_explorer = ttk.Button(nav_frame, text="Explorerで開く", command=self._open_current_in_explorer, style="Accent.TButton")
        self.btn_explorer.pack(side=tk.RIGHT)

        # 2. File List (Treeview)
        tree_frame = ttk.Frame(self, padding=(12, 0, 12, 0), style="App.TFrame")
        tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        columns = ("name", "modified", "type", "size")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="browse"
        )

        self.tree.heading("name", text="名前", command=lambda: self._sort_by("name"))
        self.tree.heading("modified", text="更新日時", command=lambda: self._sort_by("modified"))
        self.tree.heading("type", text="種類", command=lambda: self._sort_by("type"))
        self.tree.heading("size", text="サイズ", anchor=tk.E, command=lambda: self._sort_by("size"))

        self.tree.column("name", width=320, minwidth=150, anchor=tk.W)
        self.tree.column("modified", width=140, minwidth=100, anchor=tk.W)
        self.tree.column("type", width=80, minwidth=60, anchor=tk.W)
        self.tree.column("size", width=90, minwidth=70, anchor=tk.E)

        # Scrollbars
        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        # 3. Status Bar
        self.status_var = tk.StringVar(value="準備完了")
        status_bar = ttk.Label(self, textvariable=self.status_var, anchor=tk.W, style="Status.TLabel")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Mouse & Keyboard Bindings
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Return>", self._on_enter_key)
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<F2>", lambda e: self._rename_selected_item())
        self.tree.bind("<Delete>", lambda e: self._delete_selected_item())
        self.tree.bind("<F5>", lambda e: self.reload())
        self.tree.bind("<Control-c>", lambda e: self._copy_selected_item())
        self.tree.bind("<Control-x>", lambda e: self._cut_selected_item())
        self.tree.bind("<Control-v>", lambda e: self._paste_item())
        # Mouse side-button event names differ between Tk builds. Register
        # only events supported by the current runtime so startup is safe.
        for sequence, handler in (
            ("<XButton1>", self._navigate_back),
            ("<XButton2>", self._navigate_forward),
            ("<Button-8>", self._navigate_back),
            ("<Button-9>", self._navigate_forward),
        ):
            try:
                self.tree.bind(sequence, handler)
            except tk.TclError:
                pass
        self.tree.bind("<Alt-Left>", self._navigate_back)
        self.tree.bind("<Alt-Right>", self._navigate_forward)

        # Build Context Menus
        self._build_context_menus()

    def _build_context_menus(self):
        # 1. Item Context Menu (Right-click on a file/folder)
        self.item_menu = tk.Menu(self, tearoff=0)
        self.item_menu.add_command(label="開く / 起動", font=("Segoe UI", 9, "bold"), command=self._open_selected_item)
        self.item_menu.add_command(label="Explorerで表示", command=self._open_selected_in_explorer)
        self.item_menu.add_separator()
        self.item_menu.add_command(label="🗜 ZIPファイルに圧縮", command=self._compress_selected_item)
        self.item_menu.add_command(label="📦 すべて展開 (解凍)", command=self._extract_selected_item)
        self.item_menu.add_separator()
        self.item_menu.add_command(label="切り取り (Ctrl+X)", command=self._cut_selected_item)
        self.item_menu.add_command(label="コピー (Ctrl+C)", command=self._copy_selected_item)
        self.item_menu.add_separator()
        self.item_menu.add_command(label="名前の変更 (F2)", command=self._rename_selected_item)
        self.item_menu.add_command(label="削除 (Delete)", command=self._delete_selected_item)
        self.item_menu.add_separator()
        self.item_menu.add_command(label="フルパスをコピー", command=self._copy_selected_path)
        self.item_menu.add_command(label="ファイル名をコピー", command=self._copy_selected_name)
        self.item_menu.add_separator()
        self.item_menu.add_command(label="プロパティ", command=self._show_selected_properties)

        # 2. Blank Area Context Menu (Right-click on background)
        self.blank_menu = tk.Menu(self, tearoff=0)
        self.blank_menu.add_command(label="最新の情報に更新 (F5)", command=self.reload)
        self.blank_menu.add_command(label="貼り付け (Ctrl+V)", command=self._paste_item)
        self.blank_menu.add_separator()

        # Submenu: New
        new_submenu = tk.Menu(self.blank_menu, tearoff=0)
        new_submenu.add_command(label="📁 フォルダ", command=self._new_folder)
        new_submenu.add_command(label="📄 テキスト ドキュメント", command=self._new_text_file)
        self.blank_menu.add_cascade(label="新規作成", menu=new_submenu)

        self.blank_menu.add_separator()
        self.blank_menu.add_command(label="Explorerで開く", command=self._open_current_in_explorer)
        self.blank_menu.add_command(label="フォルダパスをコピー", command=self._copy_current_path)
        self.blank_menu.add_separator()
        self.blank_menu.add_command(label="プロパティ", command=self._show_current_properties)

    def navigate_to(self, target_path: str, record_history: bool = True):
        """Navigate to the target directory and refresh contents."""
        target_path = target_path.strip().strip('"')
        if not target_path:
            return

        path_obj = Path(target_path)
        if not path_obj.exists():
            messagebox.showerror("エラー", f"指定されたパスが存在しません:\n{target_path}")
            self.path_var.set(self.current_path)
            return

        if not path_obj.is_dir():
            path_obj = path_obj.parent

        resolved_path = str(path_obj.resolve())
        if record_history and resolved_path != self.current_path:
            # A new route after going back starts a new branch.
            self._navigation_history = self._navigation_history[: self._history_index + 1]
            self._navigation_history.append(resolved_path)
            self._history_index = len(self._navigation_history) - 1

        self.current_path = resolved_path
        self.path_var.set(self.current_path)
        self.reload()

        if self.on_path_changed:
            self.on_path_changed(self.current_path)

    def _navigate_history(self, offset: int):
        target_index = self._history_index + offset
        if not (0 <= target_index < len(self._navigation_history)):
            return
        self._history_index = target_index
        self.navigate_to(self._navigation_history[target_index], record_history=False)

    def _navigate_back(self, event=None):
        self._navigate_history(-1)
        return "break"

    def _navigate_forward(self, event=None):
        self._navigate_history(1)
        return "break"

    def reload(self):
        """Reload items for current path."""
        if not self.current_path:
            return

        items, error = FileManager.list_directory(self.current_path)
        if error:
            self.status_var.set(f"エラー: {error}")
            messagebox.showwarning("アクセスエラー", error)
            return

        self.items = items
        self._render_items()

        dir_count = sum(1 for item in items if item.is_dir)
        file_count = len(items) - dir_count
        self.status_var.set(f"フォルダ: {dir_count} 個, ファイル: {file_count} 個")

    def _render_items(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        for item in self.items:
            item_type = "フォルダ" if item.is_dir else (item.extension.upper()[1:] + " ファイル" if item.extension else "ファイル")
            self.tree.insert(
                "",
                tk.END,
                iid=item.path,
                image=self._folder_icon if item.is_dir else self._file_icon,
                values=(item.name, item.modified_str, item_type, item.size_str)
            )

    def _navigate_up(self):
        if not self.current_path:
            return
        parent = Path(self.current_path).parent
        if parent != Path(self.current_path):
            self.navigate_to(str(parent))

    def _get_selected_item(self) -> Optional[FileItem]:
        selection = self.tree.selection()
        if not selection:
            return None
        selected_path = selection[0]
        for item in self.items:
            if item.path == selected_path:
                return item
        return None

    def _on_double_click(self, event):
        item = self._get_selected_item()
        if not item:
            return

        if item.is_dir:
            self.navigate_to(item.path)
        else:
            err = FileManager.open_item(item.path)
            if err:
                messagebox.showerror("起動エラー", err)

    def _on_enter_key(self, event):
        self._on_double_click(event)

    def _show_context_menu(self, event):
        """Show appropriate right-click menu based on click position."""
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            item = self._get_selected_item()
            # Enable extract option only for .zip files
            if item and item.extension.lower() == ".zip":
                self.item_menu.entryconfigure("📦 すべて展開 (解凍)", state=tk.NORMAL)
            else:
                self.item_menu.entryconfigure("📦 すべて展開 (解凍)", state=tk.DISABLED)

            self.item_menu.post(event.x_root, event.y_root)
        else:
            # Clicked empty space
            self.tree.selection_remove(self.tree.selection())
            state = tk.NORMAL if self._clipboard_path else tk.DISABLED
            self.blank_menu.entryconfigure("貼り付け (Ctrl+V)", state=state)
            self.blank_menu.post(event.x_root, event.y_root)

    def _open_selected_item(self):
        item = self._get_selected_item()
        if item:
            if item.is_dir:
                self.navigate_to(item.path)
            else:
                err = FileManager.open_item(item.path)
                if err:
                    messagebox.showerror("起動エラー", err)

    def _open_selected_in_explorer(self):
        item = self._get_selected_item()
        if item:
            FileManager.open_in_explorer(item.path)
        elif self.current_path:
            FileManager.open_in_explorer(self.current_path)

    def _open_current_in_explorer(self):
        if self.current_path:
            FileManager.open_in_explorer(self.current_path)

    def _copy_selected_path(self):
        item = self._get_selected_item()
        target = item.path if item else self.current_path
        if target:
            self.clipboard_clear()
            self.clipboard_append(target)
            self.status_var.set(f"パスをコピーしました: {target}")

    def _copy_selected_name(self):
        item = self._get_selected_item()
        if item:
            self.clipboard_clear()
            self.clipboard_append(item.name)
            self.status_var.set(f"名前をコピーしました: {item.name}")

    def _copy_current_path(self):
        if self.current_path:
            self.clipboard_clear()
            self.clipboard_append(self.current_path)
            self.status_var.set(f"フォルダパスをコピーしました: {self.current_path}")

    def _rename_selected_item(self):
        item = self._get_selected_item()
        if not item:
            return

        new_name = simpledialog.askstring(
            "名前の変更",
            "新しい名前を入力してください:",
            initialvalue=item.name,
            parent=self
        )
        if not new_name or not new_name.strip() or new_name.strip() == item.name:
            return

        err = FileManager.rename_item(item.path, new_name.strip())
        if err:
            messagebox.showerror("エラー", err)
        else:
            self.reload()

    def _delete_selected_item(self):
        item = self._get_selected_item()
        if not item:
            return

        confirm = messagebox.askyesno(
            "削除の確認",
            f"'{item.name}' を削除しますか？\n（可能な場合はごみ箱へ移動します）",
            parent=self
        )
        if not confirm:
            return

        err = FileManager.delete_item(item.path)
        if err:
            messagebox.showerror("エラー", err)
        else:
            self.reload()

    def _compress_selected_item(self):
        """Compresses the selected item to a .zip archive in a background worker."""
        item = self._get_selected_item()
        if not item:
            return

        self.status_var.set(f"ZIP圧縮中: {item.name} ...")

        def worker():
            zip_path, err = FileManager.compress_to_zip(item.path)

            def on_complete():
                if err:
                    self.status_var.set("ZIP圧縮に失敗しました")
                    messagebox.showerror("ZIP圧縮エラー", err)
                else:
                    self.status_var.set(f"ZIP圧縮完了: {Path(zip_path).name}")
                    self.reload()

            self.after(0, on_complete)

        threading.Thread(target=worker, daemon=True).start()

    def _extract_selected_item(self):
        """Extracts the selected .zip archive in a background worker."""
        item = self._get_selected_item()
        if not item or item.extension.lower() != ".zip":
            return

        self.status_var.set(f"ZIP展開中: {item.name} ...")

        def worker():
            dest_dir, err = FileManager.extract_zip(item.path)

            def on_complete():
                if err:
                    self.status_var.set("ZIP展開に失敗しました")
                    messagebox.showerror("ZIP展開エラー", err)
                else:
                    self.status_var.set(f"ZIP展開完了: {Path(dest_dir).name}")
                    self.reload()

            self.after(0, on_complete)

        threading.Thread(target=worker, daemon=True).start()

    def _cut_selected_item(self):
        item = self._get_selected_item()
        if item:
            self._clipboard_path = item.path
            self._clipboard_is_cut = True
            self.status_var.set(f"切り取り: {item.name}")

    def _copy_selected_item(self):
        item = self._get_selected_item()
        if item:
            self._clipboard_path = item.path
            self._clipboard_is_cut = False
            self.status_var.set(f"コピー: {item.name}")

    def _paste_item(self):
        if not self._clipboard_path or not self.current_path:
            return

        err = FileManager.paste_item(self._clipboard_path, self.current_path, self._clipboard_is_cut)
        if err:
            messagebox.showerror("貼り付けエラー", err)
        else:
            if self._clipboard_is_cut:
                self._clipboard_path = None
                self._clipboard_is_cut = False
            self.reload()

    def _new_folder(self):
        if not self.current_path:
            return

        name = simpledialog.askstring("新規フォルダ", "フォルダ名を入力してください:", initialvalue="新しいフォルダー", parent=self)
        if not name or not name.strip():
            return

        err = FileManager.create_folder(self.current_path, name.strip())
        if err:
            messagebox.showerror("エラー", err)
        else:
            self.reload()

    def _new_text_file(self):
        if not self.current_path:
            return

        name = simpledialog.askstring("新規ファイル", "ファイル名を入力してください:", initialvalue="新規テキスト ドキュメント.txt", parent=self)
        if not name or not name.strip():
            return

        err = FileManager.create_text_file(self.current_path, name.strip())
        if err:
            messagebox.showerror("エラー", err)
        else:
            self.reload()

    def _show_selected_properties(self):
        item = self._get_selected_item()
        if item:
            err = FileManager.show_properties(item.path)
            if err:
                messagebox.showerror("エラー", err)

    def _show_current_properties(self):
        if self.current_path:
            err = FileManager.show_properties(self.current_path)
            if err:
                messagebox.showerror("エラー", err)

    def _sort_by(self, col: str):
        if self._sort_column == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = col
            self._sort_reverse = False

        if col == "name":
            self.items.sort(key=lambda x: (not x.is_dir, x.name.lower()), reverse=self._sort_reverse)
        elif col == "modified":
            self.items.sort(key=lambda x: (not x.is_dir, x.modified_time), reverse=self._sort_reverse)
        elif col == "type":
            self.items.sort(key=lambda x: (not x.is_dir, x.extension.lower(), x.name.lower()), reverse=self._sort_reverse)
        elif col == "size":
            self.items.sort(key=lambda x: (not x.is_dir, x.size_bytes), reverse=self._sort_reverse)

        self._render_items()
