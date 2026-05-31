"""Manager-backed OpenHands file_editor.

Replaces the default OpenHands FileEditorExecutor with one that routes every
read/write through the multiagent-sync Manager, so N concurrent OpenHands
Agents sharing a workspace are mediated by state management + snapshot isolation instead
of touching the filesystem directly.

Design notes
------------
* **Sync/async bridge**: OpenHands `ToolExecutor.__call__` is sync (called from
  a worker thread while `Conversation.run()` blocks). Manager methods are
  async. We pass a dedicated asyncio event loop running on its own thread and
  submit coroutines with `asyncio.run_coroutine_threadsafe`.
* **Dependency tracking**: The executor keeps a per-instance `_read_versions`
  map. Every `view`/`str_replace`/`insert` read populates it; every write
  submits the map as the snapshot so Manager can reject writes whose
  dependencies have drifted.
* **Conflict surfacing**: on a rejected write, the returned Observation is
  `is_error=True` and its text includes `current_content` + diff so the LLM
  can retry with the fresh baseline on the next turn.
* **`undo_edit`**: not supported in multi-agent mode (history is Manager-
  level and a per-agent stack would break under concurrent writes).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openhands.sdk.tool import (
    ToolAnnotations,
    ToolExecutor,
)
from openhands.sdk.tool.registry import register_tool
from openhands.sdk.tool.spec import Tool
from openhands.tools.file_editor.definition import (
    TOOL_DESCRIPTION as _OH_TOOL_DESCRIPTION,
    FileEditorAction,
    FileEditorObservation,
    FileEditorTool,
)
from openhands.tools.file_editor.utils.config import SNIPPET_CONTEXT_WINDOW
from openhands.tools.terminal.definition import (
    TOOL_DESCRIPTION as _OH_TERMINAL_DESCRIPTION,
    TerminalAction,
    TerminalObservation,
    TerminalTool,
)
from openhands.tools.terminal.metadata import CmdOutputMetadata

if TYPE_CHECKING:
    from .manager import Manager
    from openhands.sdk.workspace.base import BaseWorkspace


def _build_coord_note(agent_id: str) -> str:
    return f"""

# === MULTI-AGENT WORKSPACE RULES (read carefully — this changes your behavior) ===

You are acting as `{agent_id}`. Other agents (different agent ids) are
editing these same files concurrently. Follow BOTH rules below on EVERY
edit.

## RULE 1 — REQUIRED: annotate every edit with an intent comment

Whenever you add, modify, or extend any block of code (whether with
str_replace, create, or insert), you MUST include an intent comment line
using the file's native comment syntax. Exact format:

    # {agent_id}: <one-line description of what this block accomplishes>

Place it on the line immediately BEFORE the block it describes.

Example — if your task is "Add input validation to add()", a correct edit's
`new_str` looks like this:

    # {agent_id}: validate numeric inputs before summing
    def add(a, b):
        if not isinstance(a, (int, float)):
            raise TypeError("a must be numeric")
        if not isinstance(b, (int, float)):
            raise TypeError("b must be numeric")
        return a + b

Use `#` for Python/Shell/YAML/Ruby, `//` for C/JS/TS/Go/Java/Rust.
One comment per logical change — do NOT annotate every line.

## RULE 2 — REQUIRED: preserve annotations from OTHER agents

When viewing code, you will see comment lines like:

    # agent-X: <intent>
    <block>

If the agent id in the comment is NOT `{agent_id}`, that block belongs to
another agent's task. You MUST preserve it verbatim unless your own task
explicitly requires changing it. If you do have to change it, update the
`# agent-X:` comment rather than deleting it silently.

If you re-edit a block YOU previously annotated, keep the comment accurate
(rewrite it if the intent evolved; do not stack multiple comments).

## Concurrency control (passive — the Manager enforces this)

- Reads return content + version. Writes require your read-baseline to
  match. If another agent wrote between your read and your write, you
  receive an error Observation containing a unified diff and the current
  content. Re-plan on the new baseline — do NOT retry the same write.
- `undo_edit` is DISABLED. To revert, use `str_replace` on current content.

The intent-comment rules (1 and 2) are your PRIMARY coordination channel
with other agents. The diff-on-conflict is only a backstop.
"""


class ManagerBackedFileEditorExecutor(ToolExecutor):
    """Executor that maps FileEditorAction commands onto a Manager."""

    CONFLICT_MODE_FULL = "full"
    CONFLICT_MODE_DIFF = "diff"
    CONFLICT_MODE_BRIEF = "brief"

    def __init__(
        self,
        manager: "Manager",
        agent_id: str,
        loop: asyncio.AbstractEventLoop,
        call_timeout: float = 60.0,
        virtual_root: str | None = None,
        conflict_mode: str = "full",
    ):
        self._manager = manager
        self._agent_id = agent_id
        self._loop = loop
        self._call_timeout = call_timeout
        self._conflict_mode = conflict_mode
        # Optional virtual root (e.g. "/workspace/minitorch_repo") that the
        # system prompt promises the agent, even though the real host
        # workspace lives somewhere else. Incoming absolute paths starting
        # with this prefix get rewritten to workspace-relative.
        self._virtual_root = virtual_root.rstrip("/") if virtual_root else None
        # Baseline of what this agent has "officially seen" — feeds both the
        # snapshot sent to Manager and the content used for string edits.
        self._read_versions: dict[str, int] = {}
        self._read_content: dict[str, str] = {}

    # ------------------------------------------------------------------
    # sync/async bridge
    # ------------------------------------------------------------------

    def _run_sync(self, coro):
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=self._call_timeout)

    # ------------------------------------------------------------------
    # output formatters — match OpenHands' native `cat -n` snippet format
    # so LLMs trained on the canonical str_replace/insert output stay in
    # their expected distribution.
    # ------------------------------------------------------------------

    @staticmethod
    def _numbered_snippet(lines: list[str], start_0indexed: int) -> str:
        return "\n".join(
            f"{start_0indexed + i + 1:6}\t{line}"
            for i, line in enumerate(lines)
        )

    @classmethod
    def _edit_success_message(
        cls,
        path_label: str,
        new_content: str,
        edit_line_0indexed: int,
        new_str: str,
        verb: str = "edited",
    ) -> str:
        lines = new_content.splitlines()
        start = max(0, edit_line_0indexed - SNIPPET_CONTEXT_WINDOW)
        end = min(
            len(lines),
            edit_line_0indexed + SNIPPET_CONTEXT_WINDOW + new_str.count("\n") + 1,
        )
        snippet = cls._numbered_snippet(lines[start:end], start)
        return (
            f"The file {path_label} has been {verb}. "
            f"Here's the result of running `cat -n` on a snippet of {path_label}:\n"
            f"{snippet}\n"
            "Review the changes and make sure they are as expected. "
            "Edit the file again if necessary."
        )

    def _normalize_path(self, path: str) -> str:
        """Make path workspace-relative (Manager expects relative paths).

        Handles three cases in order:
          1. Absolute path under the real host workspace root → relative_to.
          2. Absolute path under the configured virtual_root (e.g. Docker-
             style `/workspace/minitorch_repo/...`) → strip virtual_root.
          3. Lenient fallback: strip leading `/` if that yields an existing
             path in workspace. Catches LLMs that habitually write
             `/calc.py` on a workspace rooted elsewhere.
        """
        p = Path(path)
        if p.is_absolute():
            try:
                return str(p.relative_to(self._manager.workspace))
            except ValueError:
                pass
            if self._virtual_root and path.startswith(self._virtual_root + "/"):
                return path[len(self._virtual_root) + 1 :]
            if self._virtual_root and path == self._virtual_root:
                return "."
            stripped = path.lstrip("/")
            if stripped and (self._manager.workspace / stripped).exists():
                return stripped
            return path
        return path

    # ------------------------------------------------------------------
    # entry point
    # ------------------------------------------------------------------

    def __call__(
        self,
        action: FileEditorAction,
        conversation: Any = None,  # noqa: ARG002 — signature match
    ) -> FileEditorObservation:
        try:
            cmd = action.command
            if cmd == "view":
                return self._do_view(action)
            if cmd == "create":
                return self._do_create(action)
            if cmd == "str_replace":
                return self._do_str_replace(action)
            if cmd == "insert":
                return self._do_insert(action)
            if cmd == "undo_edit":
                return FileEditorObservation.from_text(
                    text=(
                        "undo_edit is not supported in multi-agent mode. "
                        "Use `view` to see the current content then `str_replace` "
                        "to revert."
                    ),
                    command="undo_edit",
                    path=action.path,
                    is_error=True,
                )
            return FileEditorObservation.from_text(
                text=f"unknown command: {cmd}",
                command=cmd,
                is_error=True,
            )
        except FileNotFoundError as e:
            return FileEditorObservation.from_text(
                text=str(e), command=action.command, path=action.path, is_error=True
            )
        except Exception as e:  # noqa: BLE001 — never crash the agent loop
            return FileEditorObservation.from_text(
                text=f"[ManagerBackedFileEditor] unexpected error: {e!r}",
                command=action.command,
                path=action.path,
                is_error=True,
            )

    # ------------------------------------------------------------------
    # view
    # ------------------------------------------------------------------

    def _do_view(self, action: FileEditorAction) -> FileEditorObservation:
        rel = self._normalize_path(action.path)
        full = self._manager.workspace / rel

        if full.exists() and full.is_dir():
            entries = self._run_sync(self._manager.list_dir(rel))
            label = rel if rel and rel != "." else "."
            text = (
                f"Here's the files and directories up to 2 levels deep in "
                f"{label}, excluding hidden items:\n" + "\n".join(entries)
            )
            return FileEditorObservation.from_text(
                text=text, command="view", path=action.path
            )

        resp = self._run_sync(self._manager.read_file(self._agent_id, rel))
        content = resp.content
        self._read_versions[rel] = resp.version
        self._read_content[rel] = content

        lines = content.splitlines()
        if action.view_range:
            start, end = action.view_range
            start = max(start, 1)
            end = len(lines) if end == -1 else min(end, len(lines))
            display_lines = lines[start - 1 : end]
            offset_0 = start - 1
        else:
            display_lines = lines
            offset_0 = 0

        numbered = self._numbered_snippet(display_lines, offset_0)
        text = (
            f"Here's the result of running `cat -n` on {rel} "
            f"(v{resp.version}, multi-agent-aware):\n{numbered}"
        )

        return FileEditorObservation(
            content=[_text_content(text)],
            command="view",
            path=action.path,
            prev_exist=True,
            new_content=content,
        )

    # ------------------------------------------------------------------
    # create
    # ------------------------------------------------------------------

    def _do_create(self, action: FileEditorAction) -> FileEditorObservation:
        if action.file_text is None:
            return FileEditorObservation.from_text(
                text="create requires file_text",
                command="create",
                path=action.path,
                is_error=True,
            )

        rel = self._normalize_path(action.path)
        resp = self._run_sync(
            self._manager.write_file(
                self._agent_id,
                rel,
                action.file_text,
                expected_version=0,
                snapshot=dict(self._read_versions),
            )
        )
        if resp.success:
            self._read_versions[rel] = resp.new_version or 1
            self._read_content[rel] = action.file_text
            msg = (
                f"File created successfully at: {rel} "
                f"(v{resp.new_version}, multi-agent-aware)"
            )
            return FileEditorObservation(
                content=[_text_content(msg)],
                command="create",
                path=action.path,
                prev_exist=False,
                new_content=action.file_text,
            )
        return self._conflict_observation(action, resp, "create")

    # ------------------------------------------------------------------
    # str_replace
    # ------------------------------------------------------------------

    def _do_str_replace(self, action: FileEditorAction) -> FileEditorObservation:
        if not action.old_str:
            return FileEditorObservation.from_text(
                text="str_replace requires old_str",
                command="str_replace",
                path=action.path,
                is_error=True,
            )

        rel = self._normalize_path(action.path)
        # Strict state management: operate on the CACHED baseline (what the agent saw on
        # its last view/create/successful edit). This way any concurrent
        # write by another agent surfaces as a REJECTED Observation with the
        # fresh content attached, rather than a misleading "old_str not
        # found". First-touch with no prior view falls back to fresh read.
        if rel in self._read_versions and rel in self._read_content:
            content = self._read_content[rel]
            version = self._read_versions[rel]
        else:
            read = self._run_sync(self._manager.read_file(self._agent_id, rel))
            content = read.content
            version = read.version
            self._read_versions[rel] = version
            self._read_content[rel] = content

        # Match OpenHands str_replace semantics: find all literal occurrences,
        # retry once with whitespace-stripped old_str/new_str if the first pass
        # yields none (handles common LLM whitespace drift).
        old_str = action.old_str
        new_str = action.new_str or ""
        storm_positions = _all_positions(content, old_str)
        if not storm_positions:
            stripped_old = old_str.strip()
            stripped_new = new_str.strip()
            storm_positions = _all_positions(content, stripped_old)
            if storm_positions:
                old_str, new_str = stripped_old, stripped_new
            else:
                return FileEditorObservation.from_text(
                    text=(
                        f"No replacement was performed, old_str `{old_str}` "
                        f"did not appear verbatim in {rel}."
                    ),
                    command="str_replace",
                    path=action.path,
                    is_error=True,
                )
        if len(storm_positions) > 1:
            lines_of_occ = sorted(
                {content.count("\n", 0, p) + 1 for p in storm_positions}
            )
            return FileEditorObservation.from_text(
                text=(
                    f"No replacement was performed. Multiple occurrences of "
                    f"old_str `{old_str}` in lines {lines_of_occ}. Please "
                    "ensure it is unique."
                ),
                command="str_replace",
                path=action.path,
                is_error=True,
            )

        idx = storm_positions[0]
        replacement_line_0 = content.count("\n", 0, idx)
        new_content = content[:idx] + new_str + content[idx + len(old_str):]

        write = self._run_sync(
            self._manager.write_file(
                self._agent_id,
                rel,
                new_content,
                expected_version=version,
                snapshot=dict(self._read_versions),
                base_content=content,
            )
        )
        if write.success:
            self._read_versions[rel] = write.new_version or (version + 1)
            self._read_content[rel] = new_content
            label = f"{rel} (v{version}->v{write.new_version}, multi-agent-aware)"
            msg = self._edit_success_message(
                label, new_content, replacement_line_0, new_str
            )
            return FileEditorObservation(
                content=[_text_content(msg)],
                command="str_replace",
                path=action.path,
                prev_exist=True,
                old_content=content,
                new_content=new_content,
            )
        return self._conflict_observation(action, write, "str_replace")

    # ------------------------------------------------------------------
    # insert
    # ------------------------------------------------------------------

    def _do_insert(self, action: FileEditorAction) -> FileEditorObservation:
        if action.insert_line is None or action.new_str is None:
            return FileEditorObservation.from_text(
                text="insert requires insert_line and new_str",
                command="insert",
                path=action.path,
                is_error=True,
            )

        rel = self._normalize_path(action.path)
        # Same cache-first policy as str_replace (see _do_str_replace).
        if rel in self._read_versions and rel in self._read_content:
            content = self._read_content[rel]
            version = self._read_versions[rel]
        else:
            read = self._run_sync(self._manager.read_file(self._agent_id, rel))
            content = read.content
            version = read.version
            self._read_versions[rel] = version
            self._read_content[rel] = content

        lines = content.splitlines()
        n = len(lines)
        if action.insert_line < 0 or action.insert_line > n:
            return FileEditorObservation.from_text(
                text=(
                    f"insert_line={action.insert_line} out of range "
                    f"(file has {n} lines)"
                ),
                command="insert",
                path=action.path,
                is_error=True,
            )

        inserted = action.new_str.splitlines() or [""]
        new_lines = lines[: action.insert_line] + inserted + lines[action.insert_line :]
        new_content = "\n".join(new_lines)
        if content.endswith("\n"):
            new_content += "\n"

        write = self._run_sync(
            self._manager.write_file(
                self._agent_id,
                rel,
                new_content,
                expected_version=version,
                snapshot=dict(self._read_versions),
                base_content=content,
            )
        )
        if write.success:
            self._read_versions[rel] = write.new_version or (version + 1)
            self._read_content[rel] = new_content
            label = f"{rel} (v{version}->v{write.new_version}, multi-agent-aware)"
            msg = self._edit_success_message(
                label, new_content, action.insert_line, action.new_str
            )
            return FileEditorObservation(
                content=[_text_content(msg)],
                command="insert",
                path=action.path,
                prev_exist=True,
                old_content=content,
                new_content=new_content,
            )
        return self._conflict_observation(action, write, "insert")

    # ------------------------------------------------------------------
    # conflict → Observation
    # ------------------------------------------------------------------

    def _conflict_observation(
        self, action: FileEditorAction, resp, command: str
    ) -> FileEditorObservation:
        rel = self._normalize_path(action.path)

        # Always invalidate stale dependency caches regardless of mode.
        if resp.stale_files:
            for sf in resp.stale_files:
                self._read_versions.pop(sf.path, None)
                self._read_content.pop(sf.path, None)

        # Always update local cache if we got current content back.
        if resp.current_content is not None:
            self._read_content[rel] = resp.current_content
            if resp.current_version is not None:
                self._read_versions[rel] = resp.current_version

        if self._conflict_mode == self.CONFLICT_MODE_BRIEF:
            return self._conflict_brief(rel, resp, command, action)
        if self._conflict_mode == self.CONFLICT_MODE_FULL:
            return self._conflict_diff(rel, resp, command, action, include_content=True)
        return self._conflict_diff(rel, resp, command, action, include_content=False)

    def _conflict_brief(
        self, rel: str, resp, command: str, action: FileEditorAction
    ) -> FileEditorObservation:
        parts: list[str] = [f"WRITE REJECTED on {rel} ({command})."]
        if resp.changed_by:
            parts.append(
                f"File was modified by {resp.changed_by} "
                f"(now v{resp.current_version})."
            )
        if resp.stale_files:
            stale_names = [sf.path for sf in resp.stale_files]
            parts.append(
                f"Stale dependencies: {', '.join(stale_names)}."
            )
        if resp.has_reservation:
            parts.append("You have a reservation on this file.")
        parts.append(
            "Use `view` to re-read the file(s), then replan your edit."
        )
        return FileEditorObservation.from_text(
            text=" ".join(parts),
            command=command,
            path=action.path,
            is_error=True,
        )

    def _conflict_diff(
        self, rel: str, resp, command: str, action: FileEditorAction,
        include_content: bool = False,
    ) -> FileEditorObservation:
        parts: list[str] = [f"WRITE REJECTED on {rel} ({command})."]
        if resp.diff:
            parts.append(
                f"Target conflict: file is now at v{resp.current_version} "
                f"(last modified by {resp.changed_by}). "
                "Unified diff showing what changed since you last read this file:"
            )
            parts.append(f"```diff\n{resp.diff}\n```")
        if resp.stale_files:
            sf_desc = ", ".join(
                f"{sf.path}(v{sf.expected_version}->v{sf.current_version} "
                f"by {sf.changed_by})"
                for sf in resp.stale_files
            )
            parts.append(f"Stale dependencies: {sf_desc}.")
        if resp.has_reservation:
            parts.append(
                "You have been granted a reservation on this file — retry "
                "promptly after re-reading."
            )
        parts.append(
            "Re-view the changed file(s) and replan. Do NOT re-issue the same "
            "write verbatim."
        )
        # Always include full current content — the LLM needs it to pick a
        # fresh `old_str` for the retry. The diff above explains *why* it got
        # rejected; the full content gives material for the next edit.
        if resp.current_content is not None:
            parts.append(
                f"\nFull current content of {rel} (v{resp.current_version}):\n"
                f"{resp.current_content}"
            )
        return FileEditorObservation.from_text(
            text="\n".join(parts),
            command=command,
            path=action.path,
            is_error=True,
        )


# ----------------------------------------------------------------------
# Tool factory + registry bridge
# ----------------------------------------------------------------------


def _text_content(text: str):
    from openhands.sdk import TextContent

    return TextContent(text=text)


def _all_positions(haystack: str, needle: str) -> list[int]:
    """Return 0-indexed start positions of every literal occurrence of needle."""
    if not needle:
        return []
    positions: list[int] = []
    start = 0
    while True:
        p = haystack.find(needle, start)
        if p == -1:
            return positions
        positions.append(p)
        start = p + 1  # allow overlapping (rare for str_replace targets)


def make_manager_file_editor_tool(
    manager: "Manager",
    agent_id: str,
    loop: asyncio.AbstractEventLoop,
    virtual_root: str | None = None,
    conflict_mode: str = "diff",
) -> FileEditorTool:
    """Construct a fully-initialized FileEditorTool wired to Manager."""
    executor = ManagerBackedFileEditorExecutor(
        manager, agent_id, loop, virtual_root=virtual_root,
        conflict_mode=conflict_mode,
    )
    workspace_root = str(manager.workspace)
    path_note = (
        f"\nYour current working directory is: {workspace_root}\n"
        f"All paths resolve relative to this root. Prefer workspace-"
        f"relative paths (e.g. 'src/foo.py'). Absolute paths must start "
        f"with {workspace_root}.\n"
    )
    if virtual_root:
        path_note += (
            f"Paths that look like Docker-style `{virtual_root}/...` are "
            f"also accepted and will be rewritten to workspace-relative "
            f"automatically.\n"
        )
    # Put the multi-agent rules at the TOP so the LLM reads them before
    # the long OpenHands tool-description body; the annotation rules were
    # being ignored when they came after.
    description = (
        _build_coord_note(agent_id)
        + "\n"
        + _OH_TOOL_DESCRIPTION
        + path_note
    )
    return FileEditorTool(
        action_type=FileEditorAction,
        observation_type=FileEditorObservation,
        description=description,
        annotations=ToolAnnotations(
            title="file_editor",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
        executor=executor,
    )


# The registry is global, so we keep a small bridge of Manager+loop by key.
_BRIDGE: dict[str, tuple["Manager", asyncio.AbstractEventLoop]] = {}


def install_manager_bridge(
    manager: "Manager",
    loop: asyncio.AbstractEventLoop,
    *,
    key: str = "default",
) -> None:
    """Register a Manager-backed `file_editor` in the global OpenHands registry.

    After calling this, any `Tool(name="file_editor", params={"agent_id": ...})`
    spec will resolve to an executor bound to this Manager + loop.
    Tools without `agent_id` fall back to the default file_editor.

    Repeated calls with the same key overwrite the binding.
    """
    global _DEFAULT_RESOLVER
    from openhands.sdk.tool.registry import _REG, _LOCK
    with _LOCK:
        existing = _REG.get("file_editor")
        if existing:
            _DEFAULT_RESOLVER = existing
    _BRIDGE[key] = (manager, loop)
    register_tool("file_editor", _factory)


_DEFAULT_RESOLVER = None

def _factory(conv_state, agent_id: str | None = None, bridge_key: str = "default",
             virtual_root: str | None = None, conflict_mode: str = "diff", **_):
    if not agent_id:
        if _DEFAULT_RESOLVER:
            return _DEFAULT_RESOLVER({}, conv_state)
        from openhands.tools.file_editor.definition import FileEditorTool
        return FileEditorTool.create(conv_state=conv_state)
    if bridge_key not in _BRIDGE:
        raise RuntimeError(
            f"No Manager bridge installed for key={bridge_key!r}. "
            "Call install_manager_bridge(manager, loop) first."
        )
    manager, loop = _BRIDGE[bridge_key]
    return [make_manager_file_editor_tool(
        manager, agent_id, loop, virtual_root=virtual_root,
        conflict_mode=conflict_mode,
    )]


def manager_editor_spec(agent_id: str, *, bridge_key: str = "default",
                        virtual_root: str | None = None) -> Tool:
    """Build a Tool spec pointing at the Manager-backed file_editor."""
    params = {"agent_id": agent_id, "bridge_key": bridge_key}
    if virtual_root:
        params["virtual_root"] = virtual_root
    return Tool(name="file_editor", params=params)


def swap_file_editor(
    tools: list[Tool],
    agent_id: str,
    *,
    bridge_key: str = "default",
) -> list[Tool]:
    """Take a list of Tool specs (e.g. from get_default_tools()) and swap
    the default `file_editor` for a Manager-backed one bound to `agent_id`.

    Requires `install_manager_bridge()` to have been called beforehand.
    """
    return [
        manager_editor_spec(agent_id, bridge_key=bridge_key)
        if t.name == "file_editor"
        else t
        for t in tools
    ]


# ======================================================================
# Container-backed `terminal` — proxies each bash call to a persistent
# sandbox container via its agent-server HTTP (caid_workspace.execute_command).
#
# Does NOT go through Manager — shell writes are invisible to state management (same
# known limitation as the stock Phase 1/2 terminal). Purpose is purely to
# run commands inside the deps-installed container instead of host.
# ======================================================================


class ContainerTerminalExecutor(ToolExecutor):
    """Executor that forwards TerminalAction to a BaseWorkspace (Docker/Remote).

    The target workspace is a long-lived ``DockerDevWorkspace`` (or similar)
    whose ``.execute_command()`` posts to an agent-server inside the sandbox
    container. Each call spawns a fresh shell — **shell state (cwd, env,
    history) does NOT persist across calls**. A ``default_cwd`` is passed
    with every call so relative paths resolve predictably; agents should
    chain multi-step work with ``&&`` within a single command.
    """

    def __init__(
        self,
        container_workspace: "BaseWorkspace",
        default_cwd: str | None = None,
        default_timeout: float = 120.0,
    ):
        self._ws = container_workspace
        self._default_cwd = default_cwd
        self._default_timeout = default_timeout

    def __call__(
        self,
        action: TerminalAction,
        conversation: Any = None,  # noqa: ARG002 — signature match
    ) -> TerminalObservation:
        if action.is_input:
            # We run one-shot commands against the agent-server; no attached
            # process to send stdin to. Agents should run short commands
            # and chain with && / ;.
            return TerminalObservation.from_text(
                text=(
                    "is_input=True is not supported in ContainerTerminalExecutor. "
                    "Run self-contained commands; use && or ; to chain."
                ),
                command=action.command,
                exit_code=-1,
                is_error=True,
            )

        timeout = (
            float(action.timeout) if action.timeout is not None else self._default_timeout
        )
        try:
            result = self._ws.execute_command(
                action.command, cwd=self._default_cwd, timeout=timeout,
            )
        except Exception as e:  # noqa: BLE001 — never crash the agent loop
            return TerminalObservation.from_text(
                text=f"[container exec error] {e!r}",
                command=action.command,
                exit_code=-1,
                is_error=True,
            )

        # Combine stdout + stderr for the LLM (bash tools typically merge the
        # two). Keep stderr labelled so the model can tell them apart.
        parts: list[str] = []
        if result.stdout:
            parts.append(result.stdout.rstrip())
        if result.stderr:
            parts.append(f"[stderr]\n{result.stderr.rstrip()}")
        text = "\n".join(parts) if parts else ""

        return TerminalObservation(
            content=[_text_content(text)],
            command=action.command,
            exit_code=result.exit_code,
            timeout=bool(result.timeout_occurred),
            metadata=CmdOutputMetadata(
                exit_code=result.exit_code,
                working_dir=self._default_cwd or "/workspace",
            ),
            is_error=(result.exit_code != 0),
        )


# Override the stock "persistent session" promise — our transport gives a
# fresh shell every call. Keep it ahead of the boilerplate because LLMs
# reliably read the first few lines.
_CONTAINER_TERMINAL_OVERRIDE = """Execute a bash command in a SANDBOXED CONTAINER (isolated from the host).

### CRITICAL — shell is stateless across calls
Each `terminal` call starts a NEW bash process inside the container. `cd`,
`export`, shell variables, and any interactive state DO NOT persist to the
next call. Two consequences:

  1. Always use absolute paths (e.g. `/workspace/<repo>/foo.py`), or chain
     within one command: `cd /workspace/<repo> && pytest tests/`.
  2. Virtual-env activation (`source .venv/bin/activate`) is lost after
     the call. If you need the env, invoke the interpreter directly:
     `/testbed/.venv/bin/python ...` or prepend PATH inline.

A default working directory is injected on each call (typically the repo
root), so `pytest` / `ls` without explicit `cd` still resolve correctly
against that default.

### is_input / reset
  * `is_input=True` is NOT supported — returns an error observation.
  * `reset=True` is ignored (each call is a fresh shell already).

"""  # noqa: E501


def make_container_terminal_tool(
    container_workspace: "BaseWorkspace",
    default_cwd: str | None = None,
) -> TerminalTool:
    """Construct a fully-initialized TerminalTool wired to a container workspace."""
    executor = ContainerTerminalExecutor(container_workspace, default_cwd=default_cwd)
    # Prepend our stateless-shell warning to the stock description so LLMs
    # that memorised the stock text still see the deviation up front.
    description = _CONTAINER_TERMINAL_OVERRIDE + "\n" + _OH_TERMINAL_DESCRIPTION
    return TerminalTool(
        action_type=TerminalAction,
        observation_type=TerminalObservation,
        description=description,
        annotations=ToolAnnotations(
            title="terminal",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=True,
        ),
        executor=executor,
    )


_TERMINAL_BRIDGE: dict[str, tuple["BaseWorkspace", str | None]] = {}


def install_container_terminal_bridge(
    container_workspace: "BaseWorkspace",
    *,
    default_cwd: str | None = None,
    key: str = "default",
) -> None:
    """Register a Container-backed `terminal` in the OpenHands registry.

    After calling this, any ``Tool(name="terminal", params={"bridge_key": key})``
    spec resolves to an executor that runs bash inside ``container_workspace``
    with the given ``default_cwd``.
    """
    _TERMINAL_BRIDGE[key] = (container_workspace, default_cwd)
    register_tool("terminal", _terminal_factory)


def _terminal_factory(conv_state, bridge_key: str = "default", **_):
    if bridge_key not in _TERMINAL_BRIDGE:
        raise RuntimeError(
            f"No container-terminal bridge installed for key={bridge_key!r}. "
            "Call install_container_terminal_bridge(workspace) first."
        )
    ws, default_cwd = _TERMINAL_BRIDGE[bridge_key]
    return [make_container_terminal_tool(ws, default_cwd=default_cwd)]


def container_terminal_spec(*, bridge_key: str = "default") -> Tool:
    """Build a Tool spec pointing at the Container-backed terminal."""
    return Tool(name="terminal", params={"bridge_key": bridge_key})


def swap_terminal(
    tools: list[Tool],
    *,
    bridge_key: str = "default",
) -> list[Tool]:
    """Take a list of Tool specs and swap `terminal` for a container-backed one."""
    return [
        container_terminal_spec(bridge_key=bridge_key)
        if t.name == "terminal"
        else t
        for t in tools
    ]
