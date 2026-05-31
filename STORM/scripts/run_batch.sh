#!/bin/bash
# Run STORM on multiple papers/repos in parallel
# Usage: bash scripts/run_batch.sh

# ===================== API Configuration =====================
export LLM_API_KEY="${LLM_API_KEY:-}"
export LLM_BASE_URL="${LLM_BASE_URL:-https://openrouter.ai/api/v1}"
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-$LLM_API_KEY}"
export SDK_SOURCE_DIR="${SDK_SOURCE_DIR:-$(cd "$(dirname "$0")/.." && pwd)/software-agent-sdk}"

# ===================== Configuration =====================
task="commit0"           # "commit0" or "paperbench"
model="openai/deepseek-v4-pro"
max_parallel=4

# STORM settings
max_iterations=50
max_subagents=4
sub_iterations=80
rounds_of_chat=2

# PaperBench settings
judge_model="openrouter/anthropic/claude-sonnet-4-6"
test_max_depth=999
test_reproduce_timeout=3600
code_dev=true

# ===================== Paper/Repo Lists =====================
paperbench_papers=(
    "adaptive-pruning"
    "all-in-one"
    "bam"
    "bbox"
    "bridging-data-gaps"
    "fre"
    "ftrl"
    "lbcs"
    "lca-on-the-line"
    "mechanistic-understanding"
    "pinn"
    "rice"
    "robust-clip"
    "sample-specific-masks"
    "sapg"
    "sequential-neural-score-estimation"
    "stay-on-topic-with-classifier-free-guidance"
    "stochastic-interpolants"
    "test-time-model-adaptation"
    "what-will-my-model-forget"
)

commit0_repos=(
    "babel"
    "cachetools"
    "chardet"
    "cookiecutter"
    "deprecated"
    "imapclient"
    "jinja"
    "marshmallow"
    "minitorch"
    "parsel"
    "portalocker"
    "pyjwt"
    "simpy"
    "tinydb"
    "voluptuous"
    "wcwidth"
)

# ===================== Runner =====================
run_paperbench() {
    local paper_id=$1
    echo "[STORM] Starting: $paper_id"
    uv run python run_infer.py \
        --task paperbench \
        --paper_id "$paper_id" \
        --max_iterations "$max_iterations" \
        --max_subagents "$max_subagents" \
        --sub_iterations "$sub_iterations" \
        --rounds_of_chat "$rounds_of_chat" \
        --model "$model" \
        --multi_agent \
        --test_max_depth "$test_max_depth" \
        --test_reproduce_timeout "$test_reproduce_timeout" \
        --judge_type simple \
        --judge_model "$judge_model" \
        $([ "$code_dev" = "true" ] && echo "--code_dev" || echo "--nocode_dev")
    echo "[STORM] Finished: $paper_id (exit=$?)"
}

run_commit0() {
    local repo=$1
    echo "[STORM] Starting: $repo"
    uv run python run_infer.py \
        --task commit0 \
        --repo "$repo" \
        --dataset_path data/commit0/commit0_combined_disk \
        --max_iterations "$max_iterations" \
        --max_subagents "$max_subagents" \
        --sub_iterations "$sub_iterations" \
        --rounds_of_chat "$rounds_of_chat" \
        --model "$model" \
        --multi_agent
    echo "[STORM] Finished: $repo (exit=$?)"
}

# ===================== Worker Pool =====================
if [ "$task" = "paperbench" ]; then
    items=("${paperbench_papers[@]}")
    runner="run_paperbench"
elif [ "$task" = "commit0" ]; then
    items=("${commit0_repos[@]}")
    runner="run_commit0"
else
    echo "Unknown task: $task"
    exit 1
fi

running=0
for item in "${items[@]}"; do
    while (( running >= max_parallel )); do
        wait -n
        ((running--))
    done
    $runner "$item" &
    ((running++))
done

wait
echo "[STORM] All complete."
