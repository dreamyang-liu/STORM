import asyncio
import difflib
import hashlib
import logging
import time
from pathlib import Path

from .context import AgentContext
from .models import (
    CommandRecord,
    CommandResponse,
    FileState,
    ReadResponse,
    StaleFile,
    WriteResponse,
)

# Use a logger so state management events surface in structured log environments (e.g.
# uvicorn/agent-server in Phase 3) while still printing on plain hosts
# (Phase 1/2) — basicConfig is a no-op if handlers are already configured.
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("multiagent-sync.manager")
logger.setLevel(logging.INFO)

LOG_PREFIX = "  [Manager]"

RESERVATION_TIMEOUT = 30.0  # Reservation timeout to prevent deadlock if agent dies


class RWLock:
    """Simple async read-write lock: concurrent reads, exclusive writes."""

    def __init__(self):
        self._readers: int = 0
        self._writer = asyncio.Lock()       # Writer mutual exclusion
        self._no_readers = asyncio.Event()  # set = no readers
        self._no_readers.set()
        self._read_gate = asyncio.Lock()    # Prevents new readers when writer is waiting

    def read_lock(self) -> "_RWLockReadCtx":
        return _RWLockReadCtx(self)

    def write_lock(self) -> "_RWLockWriteCtx":
        return _RWLockWriteCtx(self)


class _RWLockReadCtx:
    def __init__(self, rw: RWLock):
        self._rw = rw

    async def __aenter__(self):
        # read_gate prevents infinite reader insertion when a writer is waiting
        async with self._rw._read_gate:
            self._rw._readers += 1
            if self._rw._readers == 1:
                self._rw._no_readers.clear()

    async def __aexit__(self, *_):
        self._rw._readers -= 1
        if self._rw._readers == 0:
            self._rw._no_readers.set()


class _RWLockWriteCtx:
    def __init__(self, rw: RWLock):
        self._rw = rw

    async def __aenter__(self):
        await self._rw._writer.acquire()
        # Block new readers from entering
        await self._rw._read_gate.acquire()
        # Wait for existing readers to finish
        await self._rw._no_readers.wait()

    async def __aexit__(self, *_):
        self._rw._read_gate.release()
        self._rw._writer.release()


class FileGuard:
    """Per-file concurrency control: RWLock + resolve reservation."""

    def __init__(self):
        self.rw = RWLock()                       # Read-write lock
        self.reservation_holder: str | None = None  # Who holds the reservation
        self.reservation_event = asyncio.Event()    # set = no holder, clear = held
        self.reservation_event.set()
        self.reserved_at: float = 0.0               # When reservation was acquired


class Manager:
    """Central Manager: all agent file reads/writes and command execution go through here."""

    def __init__(self, workspace: str):
        self.workspace = Path(workspace)
        self.files: dict[str, FileState] = {}
        self.command_log: list[CommandRecord] = []
        self.command_seq: int = 0
        self.agent_last_cmd_seq: dict[str, int] = {}

        self._guards: dict[str, FileGuard] = {}
        self._cmd_lock = asyncio.Lock()
        self._agent_contexts: dict[str, AgentContext] = {}

        self._scan_workspace()

    def register_context(self, agent_id: str, ctx: AgentContext):
        """Register an agent's context for push invalidation."""
        self._agent_contexts[agent_id] = ctx

    def _notify_file_changed(self, path: str, new_version: int, changed_by: str):
        """Push invalidation to all agent contexts holding this file."""
        for aid, ctx in self._agent_contexts.items():
            if aid != changed_by and path in ctx.file_views:
                ctx.invalidate_file(path, new_version, changed_by)
                logger.info(
                    f"{LOG_PREFIX} pushed invalidation: {path} v{new_version} -> {aid}"
                )

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _scan_workspace(self):
        for f in self.workspace.rglob("*"):
            if not f.is_file():
                continue
            # Skip git metadata + hidden dirs; agents never touch them.
            rel = f.relative_to(self.workspace)
            if any(part.startswith(".") for part in rel.parts):
                continue
            # Skip binary files — Manager tracks text only. Agents will get
            # an encoding error on view anyway for binaries.
            try:
                content = f.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            self.files[str(rel)] = FileState(
                path=str(rel),
                version=1,
                content_hash=self._hash(content),
                last_modified_by="system",
            )

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()

    def _guard(self, path: str) -> FileGuard:
        if path not in self._guards:
            self._guards[path] = FileGuard()
        return self._guards[path]

    @staticmethod
    def _stat_key(path: Path) -> tuple[int, int]:
        """Return (mtime_ns, size) as a fast file-change fingerprint."""
        st = path.stat()
        return (st.st_mtime_ns, st.st_size)

    def _snapshot(self) -> dict[str, tuple[int, int]]:
        """Lightweight workspace snapshot: mtime_ns + size only, no file content read."""
        snap: dict[str, tuple[int, int]] = {}
        for f in self.workspace.rglob("*"):
            if f.is_file():
                rel = str(f.relative_to(self.workspace))
                try:
                    snap[rel] = self._stat_key(f)
                except OSError:
                    pass
        return snap

    def _release_reservation(self, path: str, reason: str = ""):
        """Release a file's resolve reservation."""
        guard = self._guard(path)
        holder = guard.reservation_holder
        if holder:
            guard.reservation_holder = None
            guard.reservation_event.set()
            suffix = f" ({reason})" if reason else ""
            logger.info(f"{LOG_PREFIX} reservation on {path} released by {holder}{suffix}")

    # ------------------------------------------------------------------
    # File read — not affected by reservations, any agent can read
    # ------------------------------------------------------------------

    async def read_file(self, agent_id: str, path: str) -> ReadResponse:
        guard = self._guard(path)
        async with guard.rw.read_lock():
            full = self.workspace / path
            if not full.exists():
                raise FileNotFoundError(f"{path} not found in workspace")

            content = full.read_text()

            if path not in self.files:
                self.files[path] = FileState(
                    path=path,
                    version=1,
                    content_hash=self._hash(content),
                    last_modified_by="system",
                )

            state = self.files[path]
            logger.info(f"{LOG_PREFIX} {agent_id} reads {path} -> v{state.version}")
            return ReadResponse(content=content, version=state.version)

    # ------------------------------------------------------------------
    # Directory listing (for `view` on a directory)
    # ------------------------------------------------------------------

    async def list_dir(self, path: str, max_depth: int = 2) -> list[str]:
        """List files/dirs under `path` up to `max_depth` levels (skips hidden).

        Returns workspace-relative paths; directories end with '/'.
        """
        base = self.workspace if path in ("", ".") else (self.workspace / path)
        if not base.exists():
            raise FileNotFoundError(f"{path} not found in workspace")
        if not base.is_dir():
            raise NotADirectoryError(f"{path} is not a directory")

        base_depth = len(base.parts)
        entries: list[str] = []
        for f in base.rglob("*"):
            rel_from_base = f.relative_to(base)
            depth = len(rel_from_base.parts)
            if depth > max_depth:
                continue
            if any(part.startswith(".") for part in rel_from_base.parts):
                continue
            try:
                rel = str(f.relative_to(self.workspace))
            except ValueError:
                continue
            entries.append(rel + "/" if f.is_dir() else rel)
        return sorted(entries)

    # ------------------------------------------------------------------
    # File write (state management + resolve reservation)
    # ------------------------------------------------------------------

    def _check_snapshot(
        self, agent_id: str, target_path: str, snapshot: dict[str, int] | None
    ) -> list[StaleFile]:
        """Check if all file versions in the agent's snapshot are still valid."""
        if not snapshot:
            return []
        stale: list[StaleFile] = []
        for p, expected_v in snapshot.items():
            if p == target_path:
                continue  # Target file is checked separately by the main flow
            current = self.files.get(p)
            if current and current.version != expected_v:
                stale.append(StaleFile(
                    path=p,
                    expected_version=expected_v,
                    current_version=current.version,
                    changed_by=current.last_modified_by,
                ))
        return stale

    async def write_file(
        self,
        agent_id: str,
        path: str,
        content: str,
        expected_version: int,
        snapshot: dict[str, int] | None = None,
        base_content: str | None = None,
    ) -> WriteResponse:
        guard = self._guard(path)

        # ---- Phase 1: If another agent holds reservation, wait for it ----
        if guard.reservation_holder and guard.reservation_holder != agent_id:
            holder = guard.reservation_holder
            logger.info(
                f"{LOG_PREFIX} {agent_id} BLOCKED on {path} — "
                f"waiting for {holder}'s reservation to resolve"
            )
            try:
                await asyncio.wait_for(
                    guard.reservation_event.wait(),
                    timeout=RESERVATION_TIMEOUT,
                )
            except asyncio.TimeoutError:
                self._release_reservation(path, reason="timeout")
            logger.info(f"{LOG_PREFIX} {agent_id} UNBLOCKED on {path}")

        # ---- Phase 2: Acquire write lock, perform version check ----
        async with guard.rw.write_lock():
            # Re-check: someone may have grabbed reservation while we waited
            if guard.reservation_holder and guard.reservation_holder != agent_id:
                state = self.files.get(path)
                logger.info(
                    f"{LOG_PREFIX} {agent_id} preempted by "
                    f"{guard.reservation_holder} on {path}, retry needed"
                )
                return WriteResponse(
                    success=False,
                    current_version=state.version if state else 0,
                    changed_by=guard.reservation_holder,
                )

            full = self.workspace / path

            # New file
            if path not in self.files:
                # New files also need snapshot check
                stale = self._check_snapshot(agent_id, path, snapshot)
                if stale:
                    names = [s.path for s in stale]
                    logger.info(
                        f"{LOG_PREFIX} SNAPSHOT VIOLATION: {agent_id} writing new "
                        f"file {path}, but dependencies stale: {names}"
                    )
                    return WriteResponse(
                        success=False,
                        stale_files=stale,
                    )

                full.parent.mkdir(parents=True, exist_ok=True)
                full.write_text(content)
                self.files[path] = FileState(
                    path=path,
                    version=1,
                    content_hash=self._hash(content),
                    last_modified_by=agent_id,
                )
                if guard.reservation_holder == agent_id:
                    self._release_reservation(path, reason="resolved")
                logger.info(f"{LOG_PREFIX} {agent_id} creates {path} -> v1")
                return WriteResponse(success=True, new_version=1)

            state = self.files[path]

            # --- Target file version mismatch -> CONFLICT ---
            target_conflict = state.version != expected_version

            # --- Snapshot validation: check all dependency files ---
            stale = self._check_snapshot(agent_id, path, snapshot)

            if target_conflict or stale:
                current_content = full.read_text()
                diff_text = ""
                if target_conflict and base_content is not None:
                    diff_text = "\n".join(
                        difflib.unified_diff(
                            base_content.splitlines(),
                            current_content.splitlines(),
                            fromfile=f"{path} (your base, v{expected_version})",
                            tofile=f"{path} (current, v{state.version} by {state.last_modified_by})",
                            lineterm="",
                        )
                    )
                elif target_conflict:
                    diff_text = "\n".join(
                        difflib.unified_diff(
                            content.splitlines(),
                            current_content.splitlines(),
                            fromfile=f"{path} (yours, v{expected_version})",
                            tofile=f"{path} (current, v{state.version})",
                            lineterm="",
                        )
                    )

                # Grant reservation (if nobody holds one yet)
                granted = False
                if not guard.reservation_holder:
                    guard.reservation_holder = agent_id
                    guard.reservation_event.clear()
                    guard.reserved_at = time.time()
                    granted = True

                # Log
                if target_conflict:
                    logger.info(
                        f"{LOG_PREFIX} CONFLICT: {agent_id} expected v{expected_version}, "
                        f"but {path} is at v{state.version} (by {state.last_modified_by})"
                        + (" [reservation GRANTED]" if granted else "")
                    )
                if stale:
                    names = [f"{s.path}(v{s.expected_version}->v{s.current_version})" for s in stale]
                    logger.info(
                        f"{LOG_PREFIX} SNAPSHOT VIOLATION: {agent_id} has stale deps: {names}"
                        + (" [reservation GRANTED]" if granted and not target_conflict else "")
                    )

                return WriteResponse(
                    success=False,
                    current_version=state.version,
                    changed_by=state.last_modified_by,
                    diff=diff_text if target_conflict else None,
                    current_content=current_content,
                    has_reservation=granted,
                    stale_files=stale,
                )

            # --- All checks passed -> write ---
            full.write_text(content)
            state.version += 1
            state.content_hash = self._hash(content)
            state.last_modified_by = agent_id

            if guard.reservation_holder == agent_id:
                self._release_reservation(path, reason="resolved")

            logger.info(f"{LOG_PREFIX} {agent_id} writes {path} -> v{state.version}")
            self._notify_file_changed(path, state.version, agent_id)
            return WriteResponse(success=True, new_version=state.version)

    # ------------------------------------------------------------------
    # Voluntarily release reservation (agent gives up resolve)
    # ------------------------------------------------------------------

    async def release_reservation(self, agent_id: str, path: str):
        guard = self._guard(path)
        if guard.reservation_holder == agent_id:
            self._release_reservation(path, reason=f"{agent_id} gave up")

    # ------------------------------------------------------------------
    # Command execution (with history sync + file watcher)
    # ------------------------------------------------------------------

    async def execute_command(
        self, agent_id: str, command: str
    ) -> CommandResponse:
        # --- Phase 1 (brief lock): read missed commands + take snapshot ---
        async with self._cmd_lock:
            last_seq = self.agent_last_cmd_seq.get(agent_id, 0)
            missed = [r for r in self.command_log if r.seq > last_seq]
            before = self._snapshot()

        if missed:
            logger.info(
                f"{LOG_PREFIX} {agent_id} has {len(missed)} missed command(s), "
                "syncing before execution"
            )

        # --- Phase 2 (no lock): async command execution — concurrent with others ---
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.workspace),
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=30,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise

        class _Result:
            pass

        result = _Result()
        result.stdout = stdout_bytes.decode()
        result.stderr = stderr_bytes.decode()
        result.returncode = proc.returncode

        # --- Phase 3 (brief lock): diff snapshot + update state ---
        async with self._cmd_lock:
            after = self._snapshot()
            affected: list[str] = []

            # Modified or new: only read file content when stat fingerprint changed
            for p, stat_key in after.items():
                if before.get(p) != stat_key:
                    affected.append(p)
                    try:
                        content_hash = self._hash(
                            (self.workspace / p).read_text()
                        )
                    except Exception:
                        content_hash = ""
                    if p in self.files:
                        self.files[p].version += 1
                        self.files[p].content_hash = content_hash
                        self.files[p].last_modified_by = agent_id
                    else:
                        self.files[p] = FileState(
                            path=p, version=1,
                            content_hash=content_hash,
                            last_modified_by=agent_id,
                        )

            # Deleted
            for p in before:
                if p not in after:
                    affected.append(p)
                    self.files.pop(p, None)

            # Record to command log
            self.command_seq += 1
            record = CommandRecord(
                seq=self.command_seq,
                agent_id=agent_id,
                command=command,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                affected_files=affected,
            )
            self.command_log.append(record)
            self.agent_last_cmd_seq[agent_id] = self.command_seq

            if affected:
                logger.info(f"{LOG_PREFIX} command affected: {affected}")
                for p in affected:
                    if p in self.files:
                        self._notify_file_changed(
                            p, self.files[p].version, agent_id
                        )

        logger.info(
            f"{LOG_PREFIX} {agent_id} executed `{command}` "
            f"(exit={result.returncode})"
        )

        return CommandResponse(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            missed_commands=missed,
            affected_files=affected,
        )
