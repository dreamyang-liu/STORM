from .context import AgentContext
from .models import CommandResponse, WriteResponse
from .manager import Manager


class Agent:
    """Base agent class: all operations go through the Manager, maintains AgentContext.

    AgentContext provides mutable working memory:
      - File contents are updated/invalidated in place, no new messages produced
      - Action log is compressible
    """

    def __init__(self, agent_id: str, manager: Manager, task: str = ""):
        self.agent_id = agent_id
        self.manager = manager
        self.known_versions: dict[str, int] = {}
        self.file_cache: dict[str, str] = {}
        self.ctx = AgentContext(agent_id, task)
        manager.register_context(agent_id, self.ctx)

    async def read_file(self, path: str) -> str:
        resp = await self.manager.read_file(self.agent_id, path)
        self.known_versions[path] = resp.version
        self.file_cache[path] = resp.content
        self.ctx.load_file(path, resp.content, resp.version)
        return resp.content

    async def write_file(
        self,
        path: str,
        content: str,
        dependencies: list[str] | None = None,
    ) -> WriteResponse:
        """Write a file with state management.

        Args:
            dependencies: Explicit list of file paths this write depends on.
                          Only these files are checked for staleness (snapshot
                          isolation).  If None, falls back to *all* known
                          versions (legacy behaviour, but noisy).
        """
        expected = self.known_versions.get(path, 0)

        if dependencies is not None:
            snapshot = {
                p: self.known_versions[p]
                for p in dependencies
                if p in self.known_versions and p != path
            }
        else:
            snapshot = dict(self.known_versions)

        resp = await self.manager.write_file(
            self.agent_id,
            path,
            content,
            expected,
            snapshot=snapshot,
        )

        if resp.success:
            self.known_versions[path] = resp.new_version
            self.file_cache[path] = content
            self.ctx.record_write(path, resp.new_version)
            # Keep working memory in sync
            self.ctx.update_file_in_place(path, content, resp.new_version)
        else:
            # Update local cache for target file
            if resp.current_version is not None:
                self.known_versions[path] = resp.current_version
            if resp.current_content is not None:
                self.file_cache[path] = resp.current_content
                # Update working memory with latest content (in-place replace)
                self.ctx.update_file_in_place(
                    path, resp.current_content, resp.current_version
                )

            # Invalidate stale dependency files
            reason_parts = []
            if resp.diff:
                reason_parts.append("target conflict")
            for sf in resp.stale_files:
                self.known_versions.pop(sf.path, None)
                self.file_cache.pop(sf.path, None)
                reason_parts.append(f"{sf.path} stale")

            self.ctx.record_write_rejected(
                path, "; ".join(reason_parts) or "conflict"
            )

        return resp

    async def release_reservation(self, path: str):
        """Voluntarily give up a resolve reservation."""
        await self.manager.release_reservation(self.agent_id, path)

    async def run_command(self, command: str) -> CommandResponse:
        resp = await self.manager.execute_command(self.agent_id, command)

        self.ctx.record_command(command, resp.exit_code)

        # Invalidate file caches affected by missed commands or this command
        invalidate = set(resp.affected_files)
        for cmd in resp.missed_commands:
            invalidate.update(cmd.affected_files)

        for f in invalidate:
            self.known_versions.pop(f, None)
            self.file_cache.pop(f, None)

        return resp
