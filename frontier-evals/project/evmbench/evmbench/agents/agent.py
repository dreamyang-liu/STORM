import os
import re
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from evmbench.constants import (
    EXPLOIT_CHAIN_BASE_URL,
    EXPLOIT_CHAIN_RPC_PORT,
    EXPLOIT_WALLET_ADDRESS,
    EXPLOIT_WALLET_PRIVATE_KEY,
)

from evmbench.audit import Audit
from evmbench.utils import get_agents_dir
import structlog.stdlib

@dataclass(frozen=True)
class Agent:
    id: str
    name: str
    start_sh: str
    instruction_file_name: str
    env_vars: dict[str, str] | None = None
    # When EVMbenchSolver.disable_internet is enabled, we use an L4 gateway that allowlists
    # TLS by SNI. This list configures which hostnames are permitted.
    gateway_sni_hosts: list[str] | None = None

@dataclass(frozen=True)
class AgentOutput:
    time_start: float
    time_end: float
    runtime_in_seconds: float

class AgentRegistry:
    def _resolve_env_vars(self, env_vars: dict[str, str]) -> dict[str, str]:
        """
        Resolve ${{ secrets.NAME }} placeholders using host environment variables.
        If a referenced env var is not set, leave the original value in place and log a warning.
        """
        logger = structlog.stdlib.get_logger(component=__name__)
        secret_pattern = re.compile(r"\$\{\{\s*secrets\.([A-Z0-9_]+)\s*\}\}")
        resolved: dict[str, str] = {}
        for key, value in env_vars.items():
            if isinstance(value, str):
                match = secret_pattern.fullmatch(value)
                if match:
                    env_name = match.group(1)
                    env_val = os.getenv(env_name)
                    if env_val is None:
                        logger.warning(
                            f"Environment variable '{env_name}' referenced in agent config for '{key}' is not set on host.",
                        )
                        resolved[key] = value
                    else:
                        resolved[key] = env_val
                    continue
            resolved[key] = value
        return resolved

    def get_agent(self, agent_id: str) -> Agent:
        agents_dir = get_agents_dir()
        for fpath in agents_dir.glob("**/config.yaml"):
            with open(fpath, "r") as f:
                contents = yaml.safe_load(f)
            if agent_id not in contents:
                continue
            env_vars = contents[agent_id].get("env_vars", None)
            if isinstance(env_vars, dict):
                env_vars = self._resolve_env_vars(env_vars)
            gateway_sni_hosts = contents[agent_id].get("gateway_sni_hosts", None)
            if gateway_sni_hosts is not None:
                if not isinstance(gateway_sni_hosts, list) or not all(
                    isinstance(x, str) and x.strip() for x in gateway_sni_hosts
                ):
                    raise ValueError(
                        f"Invalid gateway_sni_hosts for agent '{agent_id}' in {fpath}"
                    )
                gateway_sni_hosts = [x.strip() for x in gateway_sni_hosts]
            return Agent(
                id=agent_id,
                name=fpath.parent.name,
                start_sh=str(fpath.parent / "start.sh"),
                instruction_file_name=contents[agent_id]["instruction_file_name"],
                env_vars=env_vars,
                gateway_sni_hosts=gateway_sni_hosts,
            )

    def get_instructions_path(self, mode: Literal["detect", "patch", "exploit"]) -> Path:
        return get_agents_dir() / "instructions" / f"{mode.upper()}.md"

    def load_instructions(
        self,
        mode: Literal["detect", "patch", "exploit"],
        audit: Audit,
        hint_level: Literal["none", "low", "med", "high", "max"],
        *,
        agent_rpc_host: str | None = None,
        agent_rpc_port: int | None = None,
    ) -> str:
        instructions = self.get_instructions_path(mode).read_text()

        if mode != "exploit" and hint_level in ("high", "max"):
            raise ValueError(
                f"Hint level '{hint_level}' is only supported in exploit mode (mode={mode})."
            )

        # Replace exploit specific placeholders
        if mode == "exploit":
            instructions = instructions.replace("{EXPLOIT_WALLET_ADDRESS}", audit.ploit_config.wallet_address or EXPLOIT_WALLET_ADDRESS)
            instructions = instructions.replace("{EXPLOIT_WALLET_PRIVATE_KEY}", audit.ploit_config.wallet_private_key or EXPLOIT_WALLET_PRIVATE_KEY)
            if agent_rpc_host and agent_rpc_port:
                base_url = agent_rpc_host
                rpc_port = agent_rpc_port
            else:
                # When veto is enabled, agents should connect to the Veto bind address
                # (filtered RPC surface) rather than the raw anvil RPC.
                if getattr(audit.ploit_config, "veto_enabled", False):
                    base_url = getattr(audit.ploit_config, "veto_bind_host", None) or EXPLOIT_CHAIN_BASE_URL
                    rpc_port = getattr(audit.ploit_config, "veto_bind_port", None) or EXPLOIT_CHAIN_RPC_PORT
                else:
                    base_url = audit.ploit_config.chain_base_url or EXPLOIT_CHAIN_BASE_URL
                    rpc_port = audit.ploit_config.chain_rpc_port or EXPLOIT_CHAIN_RPC_PORT
            instructions = instructions.replace("{EXPLOIT_CHAIN_BASE_URL}", str(base_url))
            instructions = instructions.replace("{EXPLOIT_CHAIN_RPC_PORT}", str(rpc_port))

        # Inject optional per-audit mode-specific instructions before hints.
        if mode in ("patch", "exploit"):
            extra = getattr(audit, f"{mode}_instructions", None)
            if extra:
                extra_text = str(extra).strip()
                if extra_text:
                    instructions = (instructions + "\n\n" + extra_text).strip()

        low_hints = audit.read_hints(mode, "low") if hint_level in ["low", "med", "high"] else ""
        med_hints = audit.read_hints(mode, "med") if hint_level in ["med", "high"] else ""
        high_hints = audit.read_hints(mode, "high") if hint_level == "high" else ""
        max_hints = audit.read_hints(mode, "max") if hint_level == "max" else ""

        first_hint = True
        for hint in [low_hints, med_hints, high_hints, max_hints]:
            if hint:
                if first_hint:
                    instructions = instructions + f"\n\nHints:"
                    first_hint = False
                instructions = instructions + f"\n\n{hint}"
                instructions = instructions.strip()
        return instructions

agent_registry = AgentRegistry()
