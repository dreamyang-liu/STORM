"""
AgentContext: mutable working memory + compressible action log.

Core ideas:
  - file_views are mutable; Manager can update/invalidate directly without new messages
  - action_log is append-only but can be compacted (old actions compressed into a summary)
  - build_prompt() always generates the latest prompt; stale content naturally disappears
"""

import time
from dataclasses import dataclass, field


@dataclass
class FileView:
    """Agent's current view of a file."""
    path: str
    content: str | None   # None = invalidated, needs re-read
    version: int
    stale: bool = False
    loaded_at: float = field(default_factory=time.time)


@dataclass
class Action:
    """A single record in the action log."""
    type: str        # read, write, write_rejected, command, invalidated, summary
    description: str
    timestamp: float = field(default_factory=time.time)


class AgentContext:
    """Agent context manager — mutable working memory + compressible log."""

    def __init__(self, agent_id: str, task: str = ""):
        self.agent_id = agent_id
        self.task = task
        self.file_views: dict[str, FileView] = {}
        self.action_log: list[Action] = []

    # ------------------------------------------------------------------
    # Working memory operations (mutable, no extra tokens)
    # ------------------------------------------------------------------

    def load_file(self, path: str, content: str, version: int):
        """Agent read a file — store in working memory."""
        self.file_views[path] = FileView(
            path=path, content=content, version=version,
        )
        self.action_log.append(Action("read", f"Read {path} (v{version})"))

    def update_file_in_place(self, path: str, content: str, version: int):
        """Manager pushed an update — replace content in place, no new action."""
        if path in self.file_views:
            fv = self.file_views[path]
            fv.content = content
            fv.version = version
            fv.stale = False
            fv.loaded_at = time.time()
            # Note: not appended to action_log — this is a silent update

    def invalidate_file(self, path: str, new_version: int, changed_by: str):
        """Manager notified file changed — mark stale, clear content (save tokens)."""
        if path in self.file_views:
            fv = self.file_views[path]
            fv.stale = True
            fv.content = None  # Free tokens
            fv.version = new_version
            self.action_log.append(Action(
                "invalidated",
                f"{path} changed by {changed_by} (v{new_version}), content cleared",
            ))

    def record_write(self, path: str, new_version: int):
        """Write succeeded."""
        if path in self.file_views:
            self.file_views[path].version = new_version
            self.file_views[path].stale = False
        self.action_log.append(Action("write", f"Wrote {path} (v{new_version})"))

    def record_write_rejected(self, path: str, reason: str):
        """Write was rejected."""
        self.action_log.append(Action("write_rejected", f"Write {path} rejected: {reason}"))

    def record_command(self, command: str, exit_code: int):
        """Command executed."""
        self.action_log.append(Action("command", f"`{command}` (exit={exit_code})"))

    # ------------------------------------------------------------------
    # Action log compaction
    # ------------------------------------------------------------------

    def compact(self, keep_last_n: int = 5):
        """Compress old actions into a one-line summary, keep last N."""
        if len(self.action_log) <= keep_last_n:
            return
        old = self.action_log[:-keep_last_n]
        # Count action types
        counts: dict[str, int] = {}
        for a in old:
            counts[a.type] = counts.get(a.type, 0) + 1
        parts = [f"{count} {typ}" for typ, count in counts.items()]
        summary = f"[Earlier: {', '.join(parts)}]"
        self.action_log = [
            Action("summary", summary, timestamp=old[0].timestamp)
        ] + self.action_log[-keep_last_n:]

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def build_prompt(self) -> str:
        """Build the full prompt for the LLM — always reflects the latest state."""
        sections: list[str] = []

        # Task
        if self.task:
            sections.append(f"## Task\n{self.task}")

        # Working memory: file state
        if self.file_views:
            lines = ["## Current File State"]
            for path, fv in self.file_views.items():
                status = "STALE - re-read before using" if fv.stale else "fresh"
                header = f"\n### {path} (v{fv.version}, {status})"
                if fv.content is not None:
                    lines.append(f"{header}\n```\n{fv.content}```")
                else:
                    lines.append(f"{header}\n[Content invalidated — use READ to reload]")
            sections.append("\n".join(lines))

        # Action Log
        if self.action_log:
            lines = ["## Action History"]
            for a in self.action_log:
                lines.append(f"- [{a.type}] {a.description}")
            sections.append("\n".join(lines))

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Token estimation
    # ------------------------------------------------------------------

    def estimate_tokens(self) -> int:
        """Rough token estimate (~4 chars/token)."""
        return len(self.build_prompt()) // 4

    def file_tokens(self) -> dict[str, int]:
        """Token count per file."""
        result: dict[str, int] = {}
        for path, fv in self.file_views.items():
            if fv.content is not None:
                result[path] = len(fv.content) // 4
            else:
                result[path] = 0
        return result

    def stats(self) -> str:
        """Return a stats summary of the context."""
        ft = self.file_tokens()
        file_parts = []
        for path, fv in self.file_views.items():
            status = "STALE" if fv.stale else "fresh"
            tokens = ft.get(path, 0)
            file_parts.append(f"{path}(v{fv.version}, {status}, ~{tokens}tok)")
        total = self.estimate_tokens()
        return (
            f"Files: {', '.join(file_parts) or 'none'} | "
            f"Actions: {len(self.action_log)} | "
            f"Total: ~{total} tokens"
        )
