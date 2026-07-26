#!/bin/bash
# Re-judge papers that failed or need re-evaluation
# Usage: bash scripts/rejudge.sh <output_dir> [paper1 paper2 ...]
#
# Examples:
#   bash scripts/rejudge.sh outputs/paperbench/deepseek-v4-pro rice pinn
#   bash scripts/rejudge.sh outputs/paperbench/deepseek-v4-pro  # all papers

# ===================== Configuration =====================
judge_model="${JUDGE_MODEL:-bedrock-mantle/openai.gpt-5.5}"
max_parallel=4
params="multi-agent/manageriters=50_subagents=2_subiters=80_rchats=2_codedev=true"

# ===================== Parse Args =====================
if [ -z "$1" ]; then
    echo "Usage: bash scripts/rejudge.sh <output_dir> [paper1 paper2 ...]"
    exit 1
fi

BASE="$1"
shift

if [ $# -gt 0 ]; then
    papers=("$@")
else
    papers=($(ls "$BASE" 2>/dev/null))
fi

# ===================== Runner =====================
rejudge() {
    local paper=$1
    local tar_path="$BASE/$paper/$params/final_submission/submission.tar.gz"

    if [ ! -f "$tar_path" ]; then
        echo "[$paper] No tarball, skipping"
        return
    fi

    local tmpdir=$(mktemp -d)
    tar xzf "$tar_path" -C "$tmpdir" 2>/dev/null

    uv run python -m judge.judge_runner \
        --submission_path "$tmpdir/submission" \
        --paper_id "$paper" \
        --result_file "$BASE/$paper/$params/grade.json" \
        --judge_model "$judge_model" \
        --code_dev 2>&1 | tail -3

    rm -rf "$tmpdir"
    echo "[$paper] done"
}

# ===================== Worker Pool =====================
running=0
for paper in "${papers[@]}"; do
    while (( running >= max_parallel )); do
        wait -n
        ((running--))
    done
    rejudge "$paper" &
    ((running++))
done

wait
echo "All re-judges complete."
