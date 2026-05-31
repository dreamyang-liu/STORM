"""Multiagent-sync: State management for shared workspaces."""

from .manager import Manager as StateManager
from .mgr_tools import (
    install_manager_bridge,
    make_manager_file_editor_tool,
    swap_file_editor,
    manager_editor_spec,
    make_container_terminal_tool,
    swap_terminal,
)

__all__ = [
    "StateManager",
    "install_manager_bridge",
    "make_manager_file_editor_tool",
    "swap_file_editor",
    "manager_editor_spec",
    "make_container_terminal_tool",
    "swap_terminal",
]
