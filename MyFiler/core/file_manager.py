"""File system operations and metadata reader for MyFiler.

Adheres to strict security requirements:
- Does not inspect, parse, or store file contents.
- Uses standard metadata (name, path, size, mtime, is_dir).
- Safely launches files with system defaults.
"""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple
import zipfile


@dataclass
class FileItem:
    """Metadata for a file or directory item."""
    name: str
    path: str
    is_dir: bool
    size_bytes: int
    size_str: str
    modified_time: float
    modified_str: str
    extension: str

    @property
    def icon(self) -> str:
        """Simple text/emoji indicator for item type."""
        return "📁" if self.is_dir else "📄"


class FileManager:
    """Provides safe file operations, metadata scanning, and launching."""

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Format byte size into human readable string (KB, MB, GB)."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    @classmethod
    def list_directory(cls, dir_path: str) -> Tuple[List[FileItem], Optional[str]]:
        """List files and folders in the specified directory path.

        Returns:
            Tuple of (list_of_file_items, error_message_if_any)
        """
        path_obj = Path(dir_path)
        if not path_obj.exists():
            return [], f"Path does not exist: {dir_path}"
        if not path_obj.is_dir():
            return [], f"Path is not a directory: {dir_path}"

        items: List[FileItem] = []
        try:
            with os.scandir(dir_path) as entries:
                for entry in entries:
                    try:
                        stat = entry.stat(follow_symlinks=False)
                        is_dir = entry.is_dir(follow_symlinks=False)
                        size_bytes = 0 if is_dir else stat.st_size
                        size_str = "" if is_dir else cls.format_size(size_bytes)
                        
                        mtime = stat.st_mtime
                        dt = datetime.fromtimestamp(mtime)
                        mtime_str = dt.strftime("%Y-%m-%d %H:%M")

                        ext = "" if is_dir else Path(entry.name).suffix.lower()

                        items.append(FileItem(
                            name=entry.name,
                            path=entry.path,
                            is_dir=is_dir,
                            size_bytes=size_bytes,
                            size_str=size_str,
                            modified_time=mtime,
                            modified_str=mtime_str,
                            extension=ext
                        ))
                    except (PermissionError, OSError):
                        items.append(FileItem(
                            name=entry.name,
                            path=entry.path,
                            is_dir=entry.is_dir(),
                            size_bytes=0,
                            size_str="<Locked>",
                            modified_time=0.0,
                            modified_str="",
                            extension=""
                        ))
        except PermissionError:
            return [], f"Permission denied: {dir_path}"
        except OSError as e:
            return [], f"Error accessing directory: {e.strerror or str(e)}"

        # Sort: directories first, then alphabetical by name (case-insensitive)
        items.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        return items, None

    @staticmethod
    def open_item(item_path: str) -> Optional[str]:
        """Opens a file or directory with the system default handler."""
        path_obj = Path(item_path)
        if not path_obj.exists():
            return f"Path does not exist: {item_path}"

        try:
            if sys.platform == "win32":
                os.startfile(item_path)
            else:
                subprocess.run(["xdg-open", item_path], check=False)
            return None
        except Exception as e:
            return f"Failed to open item: {str(e)}"

    @staticmethod
    def open_in_explorer(target_path: str) -> Optional[str]:
        """Opens the folder or highlights the file in Windows Explorer."""
        path_obj = Path(target_path)
        if not path_obj.exists():
            return f"Path does not exist: {target_path}"

        try:
            if sys.platform == "win32":
                if path_obj.is_dir():
                    os.startfile(str(path_obj))
                else:
                    subprocess.run(["explorer", f"/select,{str(path_obj.resolve())}"], check=False)
            else:
                folder = str(path_obj if path_obj.is_dir() else path_obj.parent)
                subprocess.run(["xdg-open", folder], check=False)
            return None
        except Exception as e:
            return f"Failed to open explorer: {str(e)}"

    @staticmethod
    def rename_item(target_path: str, new_name: str) -> Optional[str]:
        """Renames a file or folder."""
        src = Path(target_path)
        if not src.exists():
            return f"対象が存在しません: {target_path}"

        dst = src.parent / new_name
        if dst.exists():
            return f"同名のファイルまたはフォルダが既に存在します: {new_name}"

        try:
            src.rename(dst)
            return None
        except Exception as e:
            return f"名前の変更に失敗しました: {str(e)}"

    @classmethod
    def delete_item(cls, target_path: str) -> Optional[str]:
        """Deletes a file or directory (sends to Recycle Bin on Windows if possible)."""
        src = Path(target_path)
        if not src.exists():
            return f"対象が存在しません: {target_path}"

        # Try Windows Recycle Bin via SHFileOperationW
        if sys.platform == "win32":
            try:
                class SHFILEOPSTRUCTW(ctypes.Structure):
                    _fields_ = [
                        ("hwnd", wintypes.HWND),
                        ("wFunc", wintypes.UINT),
                        ("pFrom", wintypes.LPCWSTR),
                        ("pTo", wintypes.LPCWSTR),
                        ("fFlags", wintypes.WORD),
                        ("fAnyOperationsAborted", wintypes.BOOL),
                        ("hNameMappings", wintypes.LPVOID),
                        ("lpszProgressTitle", wintypes.LPCWSTR)
                    ]

                FO_DELETE = 3
                FOF_ALLOWUNDO = 0x0040       # Send to Recycle Bin
                FOF_NOCONFIRMATION = 0x0010  # Don't ask built-in confirmation (UI handles it)
                FOF_SILENT = 0x0004

                # Double null-terminated string required
                p_from = str(src.resolve()) + "\0\0"
                file_op = SHFILEOPSTRUCTW()
                file_op.hwnd = None
                file_op.wFunc = FO_DELETE
                file_op.pFrom = p_from
                file_op.pTo = None
                file_op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT

                res = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(file_op))
                if res == 0:
                    return None
            except Exception:
                pass

        # Fallback to standard deletion
        try:
            if src.is_dir():
                shutil.rmtree(src)
            else:
                src.unlink()
            return None
        except Exception as e:
            return f"削除に失敗しました: {str(e)}"

    @staticmethod
    def create_folder(parent_dir: str, folder_name: str) -> Optional[str]:
        """Creates a new folder in parent_dir."""
        target = Path(parent_dir) / folder_name
        if target.exists():
            return f"同名のフォルダが既に存在します: {folder_name}"
        try:
            target.mkdir(parents=False, exist_ok=False)
            return None
        except Exception as e:
            return f"フォルダ作成に失敗しました: {str(e)}"

    @staticmethod
    def create_text_file(parent_dir: str, file_name: str) -> Optional[str]:
        """Creates a new empty text file in parent_dir."""
        target = Path(parent_dir) / file_name
        if target.exists():
            return f"同名のファイルが既に存在します: {file_name}"
        try:
            target.touch(exist_ok=False)
            return None
        except Exception as e:
            return f"ファイル作成に失敗しました: {str(e)}"

    @classmethod
    def paste_item(cls, src_path: str, dest_dir: str, is_cut: bool) -> Optional[str]:
        """Pastes (copy or move) a file or folder into dest_dir with collision avoidance."""
        src = Path(src_path)
        dest_dir_path = Path(dest_dir)

        if not src.exists():
            return f"元のファイルが見つかりません: {src_path}"
        if not dest_dir_path.exists() or not dest_dir_path.is_dir():
            return f"移動先のフォルダが見つかりません: {dest_dir}"

        target = dest_dir_path / src.name

        # If moving to the same directory, nothing to do
        if is_cut and src.parent == dest_dir_path:
            return None

        # Resolve name collision
        if target.exists():
            stem = src.stem
            suffix = src.suffix
            counter = 1
            while target.exists():
                new_name = f"{stem} - コピー ({counter}){suffix}" if not src.is_dir() else f"{stem} - コピー ({counter})"
                target = dest_dir_path / new_name
                counter += 1

        try:
            if is_cut:
                shutil.move(str(src), str(target))
            else:
                if src.is_dir():
                    shutil.copytree(str(src), str(target))
                else:
                    shutil.copy2(str(src), str(target))
            return None
        except Exception as e:
            return f"貼り付けに失敗しました: {str(e)}"

    @staticmethod
    def show_properties(target_path: str) -> Optional[str]:
        """Displays Windows native properties dialog for file/folder."""
        path_obj = Path(target_path)
        if not path_obj.exists():
            return f"対象が存在しません: {target_path}"

        if sys.platform == "win32":
            try:
                class SHELLEXECUTEINFOW(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", wintypes.DWORD),
                        ("fMask", wintypes.ULONG),
                        ("hwnd", wintypes.HWND),
                        ("lpVerb", wintypes.LPCWSTR),
                        ("lpFile", wintypes.LPCWSTR),
                        ("lpParameters", wintypes.LPCWSTR),
                        ("lpDirectory", wintypes.LPCWSTR),
                        ("nShow", ctypes.c_int),
                        ("hInstApp", wintypes.HINSTANCE),
                        ("lpIDList", wintypes.LPVOID),
                        ("lpClass", wintypes.LPCWSTR),
                        ("hkeyClass", wintypes.HKEY),
                        ("dwHotKey", wintypes.DWORD),
                        ("hIconOrMonitor", wintypes.HANDLE),
                        ("hProcess", wintypes.HANDLE)
                    ]

                SEE_MASK_INVOKEIDLIST = 0x0000000C
                SW_SHOW = 5

                sei = SHELLEXECUTEINFOW()
                sei.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
                sei.fMask = SEE_MASK_INVOKEIDLIST
                sei.hwnd = None
                sei.lpVerb = "properties"
                sei.lpFile = str(path_obj.resolve())
                sei.nShow = SW_SHOW

                success = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei))
                if not success:
                    return "プロパティの表示に失敗しました"
                return None
            except Exception as e:
                return f"プロパティの表示に失敗しました: {str(e)}"
        return None

    @classmethod
    def compress_to_zip(cls, target_path: str) -> Tuple[Optional[str], Optional[str]]:
        """Compresses a file or directory into a .zip archive in the same parent directory.

        Returns:
            Tuple of (created_zip_path, error_message_if_any)
        """
        src = Path(target_path)
        if not src.exists():
            return None, f"対象が存在しません: {target_path}"

        parent_dir = src.parent
        zip_name = f"{src.name}.zip" if not src.is_dir() else f"{src.name}.zip"
        zip_path = parent_dir / zip_name

        # Resolve name collision
        counter = 1
        stem = src.stem if not src.is_dir() else src.name
        while zip_path.exists():
            counter += 1
            zip_path = parent_dir / f"{stem} ({counter}).zip"

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                if src.is_dir():
                    for root, _, files in os.walk(src):
                        for file in files:
                            full_path = Path(root) / file
                            # Relative path inside the zip
                            rel_path = full_path.relative_to(parent_dir)
                            zf.write(full_path, arcname=str(rel_path))
                else:
                    zf.write(src, arcname=src.name)
            return str(zip_path), None
        except Exception as e:
            # Clean up incomplete zip file on error
            if zip_path.exists():
                try:
                    zip_path.unlink()
                except Exception:
                    pass
            return None, f"ZIP圧縮に失敗しました: {str(e)}"

    @classmethod
    def extract_zip(cls, zip_path_str: str) -> Tuple[Optional[str], Optional[str]]:
        """Extracts a .zip archive into a folder in the same parent directory."""
        zip_file = Path(zip_path_str)
        if not zip_file.exists() or not zipfile.is_zipfile(zip_file):
            return None, f"有効なZIPファイルではありません: {zip_path_str}"

        parent_dir = zip_file.parent
        dest_dir_name = zip_file.stem
        dest_dir = parent_dir / dest_dir_name

        # Resolve name collision
        counter = 1
        while dest_dir.exists():
            counter += 1
            dest_dir = parent_dir / f"{zip_file.stem} ({counter})"

        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_file, "r") as zf:
                # Safe extraction preventing path traversal
                for member in zf.infolist():
                    target_member_path = (dest_dir / member.filename).resolve()
                    if not str(target_member_path).startswith(str(dest_dir.resolve())):
                        raise Exception(f"安全でないパスが含まれています: {member.filename}")
                zf.extractall(dest_dir)
            return str(dest_dir), None
        except Exception as e:
            return None, f"ZIP展開に失敗しました: {str(e)}"
