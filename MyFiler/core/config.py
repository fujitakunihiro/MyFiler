"""Configuration and data models for MyFiler.

Handles loading, saving, and managing Workspaces and Tabs.
"""

from dataclasses import dataclass, field, asdict
import json
import os
from pathlib import Path
from typing import List, Optional
import uuid


@dataclass
class ExplorerTab:
    """Represents a folder bookmark / working directory tab in a Workspace."""
    id: str
    name: str
    path: str

    @classmethod
    def create(cls, name: str, path: str) -> "ExplorerTab":
        return cls(id=str(uuid.uuid4()), name=name, path=path)


@dataclass
class Workspace:
    """Represents a working unit (project/task) containing multiple tabs."""
    id: str
    name: str
    tabs: List[ExplorerTab] = field(default_factory=list)
    active_tab_id: Optional[str] = None
    shortcut_key: Optional[int] = None

    @classmethod
    def create(cls, name: str, tabs: Optional[List[ExplorerTab]] = None) -> "Workspace":
        tab_list = tabs or []
        active_tab_id = tab_list[0].id if tab_list else None
        return cls(id=str(uuid.uuid4()), name=name, tabs=tab_list, active_tab_id=active_tab_id)


@dataclass
class AppConfig:
    """Global application settings and workspace state."""
    workspaces: List[Workspace] = field(default_factory=list)
    active_workspace_id: Optional[str] = None
    window_width: int = 1000
    window_height: int = 650

    def get_active_workspace(self) -> Optional[Workspace]:
        for ws in self.workspaces:
            if ws.id == self.active_workspace_id:
                return ws
        return self.workspaces[0] if self.workspaces else None

    def get_active_tab(self, workspace: Optional[Workspace] = None) -> Optional[ExplorerTab]:
        ws = workspace or self.get_active_workspace()
        if not ws or not ws.tabs:
            return None
        for tab in ws.tabs:
            if tab.id == ws.active_tab_id:
                return tab
        return ws.tabs[0]


class ConfigManager:
    """Manages loading and saving AppConfig to a JSON file."""

    DEFAULT_CONFIG_FILENAME = "myfiler_config.json"

    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config_path = Path(config_path)
        else:
            # Save configuration in the local application directory
            base_dir = Path(__file__).resolve().parent.parent
            self.config_path = base_dir / self.DEFAULT_CONFIG_FILENAME

    def load_config(self) -> AppConfig:
        """Load configuration from JSON file or return default configuration."""
        if not self.config_path.exists():
            return self._create_default_config()

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            workspaces: List[Workspace] = []
            for ws_data in data.get("workspaces", []):
                tabs = [
                    ExplorerTab(
                        id=t.get("id", str(uuid.uuid4())),
                        name=t.get("name", "Unnamed Tab"),
                        path=t.get("path", "")
                    )
                    for t in ws_data.get("tabs", [])
                ]
                workspaces.append(
                    Workspace(
                        id=ws_data.get("id", str(uuid.uuid4())),
                        name=ws_data.get("name", "Default Workspace"),
                        tabs=tabs,
                        active_tab_id=ws_data.get("active_tab_id")
                        ,shortcut_key=ws_data.get("shortcut_key")
                    )
                )

            config = AppConfig(
                workspaces=workspaces,
                active_workspace_id=data.get("active_workspace_id"),
                window_width=data.get("window_width", 1000),
                window_height=data.get("window_height", 650)
            )

            # Ensure valid active workspace
            if config.workspaces:
                if not any(ws.id == config.active_workspace_id for ws in config.workspaces):
                    config.active_workspace_id = config.workspaces[0].id

            return config

        except Exception:
            # Fallback to default if JSON is corrupted or invalid
            return self._create_default_config()

    def save_config(self, config: AppConfig) -> bool:
        """Save configuration to JSON file."""
        try:
            data = {
                "active_workspace_id": config.active_workspace_id,
                "window_width": config.window_width,
                "window_height": config.window_height,
                "workspaces": [
                    {
                        "id": ws.id,
                        "name": ws.name,
                        "active_tab_id": ws.active_tab_id,
                        "shortcut_key": ws.shortcut_key,
                        "tabs": [asdict(t) for t in ws.tabs]
                    }
                    for ws in config.workspaces
                ]
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def _create_default_config(self) -> AppConfig:
        """Creates initial default workspace and tabs."""
        user_home = Path.home()
        documents_dir = user_home / "Documents"
        downloads_dir = user_home / "Downloads"

        default_tabs = [
            ExplorerTab.create(
                name="Home",
                path=str(user_home)
            )
        ]
        if documents_dir.exists():
            default_tabs.append(ExplorerTab.create(name="Documents", path=str(documents_dir)))
        if downloads_dir.exists():
            default_tabs.append(ExplorerTab.create(name="Downloads", path=str(downloads_dir)))

        default_workspace = Workspace.create(name="Default Workspace", tabs=default_tabs)
        config = AppConfig(
            workspaces=[default_workspace],
            active_workspace_id=default_workspace.id
        )
        self.save_config(config)
        return config
