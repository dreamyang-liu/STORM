"""Tests for TerminalTool subclass."""

import shutil
import tempfile
from uuid import uuid4

import pytest
from pydantic import SecretStr

from openhands.sdk.agent import Agent
from openhands.sdk.conversation.state import ConversationState
from openhands.sdk.llm import LLM
from openhands.sdk.workspace import LocalWorkspace
from openhands.tools.terminal import (
    TerminalAction,
    TerminalObservation,
    TerminalTool,
)


def _create_test_conv_state(temp_dir: str) -> ConversationState:
    """Helper to create a test conversation state."""
    llm = LLM(model="gpt-4o-mini", api_key=SecretStr("test-key"), usage_id="test-llm")
    agent = Agent(llm=llm, tools=[])
    return ConversationState.create(
        id=uuid4(),
        agent=agent,
        workspace=LocalWorkspace(working_dir=temp_dir),
    )


def test_bash_tool_initialization():
    """Test that TerminalTool initializes correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = TerminalTool.create(conv_state)
        tool = tools[0]

        # Check that the tool has the correct name and properties
        assert tool.name == "terminal"
        assert tool.executor is not None
        assert tool.action_type == TerminalAction


def test_bash_tool_with_username():
    """Test that TerminalTool initializes correctly with username."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = TerminalTool.create(conv_state, username="testuser")
        tool = tools[0]

        # Check that the tool has the correct name and properties
        assert tool.name == "terminal"
        assert tool.executor is not None
        assert tool.action_type == TerminalAction


def test_bash_tool_execution():
    """Test that TerminalTool can execute commands."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = TerminalTool.create(conv_state)
        tool = tools[0]

        # Create an action
        action = TerminalAction(command="echo 'Hello, World!'")

        # Execute the action
        result = tool(action)

        # Check the result
        assert result is not None
        assert isinstance(result, TerminalObservation)
        assert "Hello, World!" in result.text


def test_bash_tool_working_directory():
    """Test that TerminalTool respects the working directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = TerminalTool.create(conv_state)
        tool = tools[0]

        # Create an action to check current directory
        action = TerminalAction(command="pwd")

        # Execute the action
        result = tool(action)

        # Check that the working directory is correct
        assert isinstance(result, TerminalObservation)
        assert temp_dir in result.text


def test_bash_tool_to_openai_tool():
    """Test that TerminalTool can be converted to OpenAI tool format."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = TerminalTool.create(conv_state)
        tool = tools[0]

        # Convert to OpenAI tool format
        openai_tool = tool.to_openai_tool()

        # Check the format
        assert openai_tool["type"] == "function"
        assert openai_tool["function"]["name"] == "terminal"
        assert "description" in openai_tool["function"]
        assert "parameters" in openai_tool["function"]


@pytest.mark.parametrize(
    "terminal_type",
    [
        "subprocess",
        pytest.param(
            "tmux",
            marks=pytest.mark.skipif(
                shutil.which("tmux") is None,
                reason="tmux is not installed",
            ),
        ),
    ],
)
def test_harness_command_timeout_is_clamped_and_terminates_process(terminal_type):
    """A model cannot request a timeout above the harness hard limit."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = TerminalTool.create(
            conv_state,
            terminal_type=terminal_type,
            max_command_timeout_seconds=0.2,
        )
        tool = tools[0]
        assert tool.executor is not None

        try:
            result = tool(
                TerminalAction(
                    command="sleep 10",
                    timeout=3600,
                )
            )

            assert result.timeout is True
            assert result.exit_code == 124
            assert result.metadata.exit_code == 124
            assert "terminated by the harness after 0.2 seconds" in (
                result.metadata.suffix
            )

            followup = tool(TerminalAction(command="echo terminal-reset-worked"))
            assert followup.exit_code == 0
            assert "terminal-reset-worked" in followup.text
        finally:
            tool.executor.close()


def test_harness_command_timeout_is_applied_when_model_omits_timeout():
    """Commands without a model-selected timeout still receive the hard cap."""
    with tempfile.TemporaryDirectory() as temp_dir:
        conv_state = _create_test_conv_state(temp_dir)
        tools = TerminalTool.create(
            conv_state,
            terminal_type="subprocess",
            max_command_timeout_seconds=300,
        )
        tool = tools[0]
        assert tool.executor is not None

        try:
            bounded = tool.executor._apply_command_timeout_cap(
                TerminalAction(command="python train.py")
            )
            assert bounded.timeout == 300
        finally:
            tool.executor.close()
