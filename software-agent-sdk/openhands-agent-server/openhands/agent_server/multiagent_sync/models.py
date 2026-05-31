from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass
class FileState:
    """Internal file state maintained by the Manager."""
    path: str
    version: int = 0
    content_hash: str = ""
    last_modified_by: str = ""


@dataclass
class CommandRecord:
    """A single record in the global command log."""
    seq: int
    agent_id: str
    command: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    timestamp: float = field(default_factory=time.time)
    affected_files: list[str] = field(default_factory=list)


@dataclass
class ReadResponse:
    content: str
    version: int


@dataclass
class StaleFile:
    """A stale file detected during snapshot validation."""
    path: str
    expected_version: int
    current_version: int
    changed_by: str


@dataclass
class WriteResponse:
    success: bool
    new_version: Optional[int] = None
    # On conflict (target file)
    current_version: Optional[int] = None
    changed_by: Optional[str] = None
    diff: Optional[str] = None
    current_content: Optional[str] = None
    has_reservation: bool = False
    # Snapshot violation: which non-target files are also stale
    stale_files: list[StaleFile] = field(default_factory=list)


@dataclass
class CommandResponse:
    stdout: str
    stderr: str
    exit_code: int
    missed_commands: list[CommandRecord] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
