#!/bin/bash
# Run STORM multi-agent
# Usage: bash scripts/run_multi.sh

# ===================== API Configuration =====================
export LLM_API_KEY="${LLM_API_KEY:-}"
export LLM_BASE_URL="${LLM_BASE_URL:-https://openrouter.ai/api/v1}"
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-$LLM_API_KEY}"
export SDK_SOURCE_DIR="${SDK_SOURCE_DIR:-$(cd "$(dirname "$0")/../.." && pwd)/software-agent-sdk}"

# ===================== Configuration =====================
task="${STORM_TASK:-paperbench}"           # "commit0" or "paperbench"
model="${LLM_MODEL:-bedrock/us.anthropic.claude-sonnet-4-6}"
max_iterations=50
max_subagents=2             # PaperBench: 2, Commit0: 4
sub_iterations=80
rounds_of_chat=2
run_id="${RUN_ID:-sonnet46-paperbench-$(date -u +%Y%m%dT%H%M%SZ)}"

# Commit0 settings
repo="minitorch"
dataset_path="data/commit0/commit0_combined_disk"

# PaperBench settings
paper_id="${PAPER_ID:-rice}"
judge_model="${JUDGE_MODEL:-bedrock-mantle/openai.gpt-5.5}"
test_max_depth=999
test_reproduce_timeout="${TEST_REPRODUCE_TIMEOUT:-300}"
agent_command_timeout="${PAPERBENCH_AGENT_COMMAND_TIMEOUT:-300}"
code_dev=true

# ===================== Run =====================
flags="--multi_agent"

if [ "$task" = "paperbench" ]; then
    flags="$flags --test_max_depth=$test_max_depth --test_reproduce_timeout=$test_reproduce_timeout"
    flags="$flags --agent_command_timeout=$agent_command_timeout"
    flags="$flags --judge_type=simple --judge_model=$judge_model"
    [ "$code_dev" = "true" ] && flags="$flags --code_dev" || flags="$flags --nocode_dev"

    uv run python run_infer.py \
        --task "$task" \
        --paper_id "$paper_id" \
        --max_iterations "$max_iterations" \
        --max_subagents "$max_subagents" \
        --sub_iterations "$sub_iterations" \
        --rounds_of_chat "$rounds_of_chat" \
        --run_id "$run_id" \
        --model "$model" \
        $flags

elif [ "$task" = "commit0" ]; then
    uv run python run_infer.py \
        --task "$task" \
        --repo "$repo" \
        --dataset_path "$dataset_path" \
        --max_iterations "$max_iterations" \
        --max_subagents "$max_subagents" \
        --sub_iterations "$sub_iterations" \
        --rounds_of_chat "$rounds_of_chat" \
        --run_id "$run_id" \
        --model "$model" \
        $flags
fi
