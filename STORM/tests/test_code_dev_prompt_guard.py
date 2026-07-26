from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from core.utils import (
    CODE_DEV_PROMPT_KEYS,
    apply_code_dev_prompt_guard,
    apply_code_dev_terminal_timeout,
)
from tasks.paperbench import PaperbenchConfig, PaperbenchTask


PROMPTS_PATH = Path(__file__).parents[1] / "prompts" / "paperbench.yaml"
SCRIPTS_DIR = Path(__file__).parents[1] / "scripts"


def load_paperbench_prompts():
    with PROMPTS_PATH.open() as prompt_file:
        return yaml.safe_load(prompt_file)


def test_code_dev_guard_reaches_every_agent_phase():
    prompts = load_paperbench_prompts()

    guarded = apply_code_dev_prompt_guard(prompts, enabled=True)

    guard = prompts["code_dev_guard"].strip()
    assert "10-50 environment or optimizer/training iterations" in guard
    assert "never a full training run" in guard
    assert "300-second limit" in guard
    assert "do not install or probe optional benchmark environments" in guard
    for key in CODE_DEV_PROMPT_KEYS:
        assert guard in guarded[key]
        assert guarded[key].rstrip().endswith(guard)


def test_code_dev_guard_is_disabled_without_mutating_prompts():
    prompts = load_paperbench_prompts()

    unguarded = apply_code_dev_prompt_guard(prompts, enabled=False)

    assert unguarded is prompts
    assert prompts["code_dev_guard"].strip() not in prompts["scan_analysis"]


def test_code_dev_guard_is_idempotent():
    prompts = load_paperbench_prompts()

    guarded_once = apply_code_dev_prompt_guard(prompts, enabled=True)
    guarded_twice = apply_code_dev_prompt_guard(guarded_once, enabled=True)

    guard = prompts["code_dev_guard"].strip()
    for key in CODE_DEV_PROMPT_KEYS:
        assert guarded_twice[key].count(guard) == 1


def test_code_dev_guard_fails_closed_when_prompt_is_missing():
    with pytest.raises(ValueError, match="code_dev_guard"):
        apply_code_dev_prompt_guard({"scan_analysis": "scan"}, enabled=True)


def test_code_dev_terminal_timeout_is_injected():
    terminal = SimpleNamespace(name="terminal", params={})
    file_editor = SimpleNamespace(name="file_editor", params={})
    config = PaperbenchConfig(code_dev=True, agent_command_timeout=300)

    tools = apply_code_dev_terminal_timeout([terminal, file_editor], config)

    assert tools == [terminal, file_editor]
    assert terminal.params["max_command_timeout_seconds"] == 300
    assert file_editor.params == {}


def test_terminal_timeout_is_not_injected_outside_code_dev():
    terminal = SimpleNamespace(name="terminal", params={})
    config = PaperbenchConfig(code_dev=False, agent_command_timeout=300)

    apply_code_dev_terminal_timeout([terminal], config)

    assert terminal.params == {}


@pytest.mark.parametrize("timeout", [0, -1, None])
def test_code_dev_terminal_timeout_fails_closed(timeout):
    terminal = SimpleNamespace(name="terminal", params={})
    config = PaperbenchConfig(code_dev=True, agent_command_timeout=timeout)

    with pytest.raises(ValueError, match="agent_command_timeout"):
        apply_code_dev_terminal_timeout([terminal], config)


def test_code_dev_evaluation_runs_reproduce_with_short_timeout():
    class FakeWorkspace:
        def __init__(self):
            self.commands = []

        def execute_command(self, command, timeout):
            self.commands.append((command, timeout))
            if command.startswith("test -f"):
                return SimpleNamespace(stdout="exists\n", exit_code=0)
            if "bash reproduce.sh" in command:
                return SimpleNamespace(stdout="EXIT_CODE=0\n", exit_code=0)
            return SimpleNamespace(stdout="", exit_code=0)

    config = PaperbenchConfig(
        code_dev=True,
        test_max_depth=0,
        test_reproduce_timeout=300,
    )
    task = PaperbenchTask(config)
    task.task_data = {}
    workspace = FakeWorkspace()

    result = task.evaluate(workspace)

    reproduce_calls = [
        call for call in workspace.commands if "bash reproduce.sh" in call[0]
    ]
    assert reproduce_calls == [
        (
            "cd /workspace/submission && timeout 300 bash reproduce.sh 2>&1 "
            '| tee reproduce.log; echo "EXIT_CODE=${PIPESTATUS[0]}"',
            360,
        )
    ]
    assert result["reproduce_success"] is True


@pytest.mark.parametrize(
    "script_name",
    ["run_single.sh", "run_multi.sh", "run_batch.sh"],
)
def test_paperbench_launchers_default_to_caid_reproduce_timeout(script_name):
    script = (SCRIPTS_DIR / script_name).read_text()

    assert 'test_reproduce_timeout="${TEST_REPRODUCE_TIMEOUT:-300}"' in script
    assert (
        'agent_command_timeout="${PAPERBENCH_AGENT_COMMAND_TIMEOUT:-300}"'
        in script
    )
    assert "agent_command_timeout" in script
