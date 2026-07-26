#!/bin/bash
# STORM Setup Script
# Run this once after cloning to set up the environment.
# Usage: bash setup.sh
#
# Expected repo structure (after git clone --recursive):
#   STORM/
#   ├── setup.sh             (this script)
#   ├── run_infer.py         (entry point)
#   ├── software-agent-sdk/  (submodule: OpenHands SDK)
#   └── frontier-evals/      (submodule: PaperBench judge, optional)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo " STORM Setup"
echo "============================================================"
echo "  Directory: $SCRIPT_DIR"
echo ""

# --- Check prerequisites ---
echo "[1/6] Checking prerequisites..."

command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not found"; exit 1; }
command -v uv >/dev/null 2>&1 || { echo "ERROR: uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "ERROR: git not found"; exit 1; }

if ! docker info >/dev/null 2>&1; then
    echo "ERROR: Docker daemon not running"
    exit 1
fi

echo "  docker: $(docker --version | head -1)"
echo "  uv: $(uv --version)"
echo "  git: $(git --version)"
echo ""

# --- Init submodules ---
echo "[2/6] Initializing submodules..."
cd "$SCRIPT_DIR/.."
git submodule init
git submodule update --recursive
cd "$SCRIPT_DIR"

SDK_DIR="$SCRIPT_DIR/../software-agent-sdk"
EVALS_DIR="$SCRIPT_DIR/../frontier-evals"

if [ ! -d "$SDK_DIR/openhands-sdk" ]; then
    echo "ERROR: software-agent-sdk submodule not found"
    echo "  Run: git submodule update --init --recursive"
    exit 1
fi
echo "  SDK: $SDK_DIR"

if [ -d "$EVALS_DIR/project/paperbench" ]; then
    echo "  Evals: $EVALS_DIR"
    HAS_EVALS=true
else
    echo "  Evals: not found (paperbench judge unavailable, commit0 still works)"
    HAS_EVALS=false
fi
echo ""

# --- Install Python dependencies ---
echo "[3/6] Installing Python dependencies..."

uv sync 2>&1 | tail -3

# Install SDK from source (must match Docker image)
uv pip install -e "$SDK_DIR/openhands-sdk" 2>&1 | tail -3

# Install paperbench judge (optional)
if [ "$HAS_EVALS" = true ]; then
    uv pip install -e "$EVALS_DIR/project/paperbench" 2>&1 | tail -3
    uv pip install -e "$EVALS_DIR/project/common/preparedness_turn_completer" 2>&1 | tail -3
fi

echo "  Python packages installed"
echo ""

# --- Build Docker images ---
echo "[4/6] Building Docker images..."
cd "$SDK_DIR"

# Build the STORM image (for commit0)
docker build \
    -f openhands-agent-server/openhands/agent_server/docker/Dockerfile \
    --target source-minimal-storm \
    --platform linux/amd64 \
    -t agent-server:storm-base \
    . 2>&1 | tail -5
echo "  agent-server:storm-base (commit0)"

# Build PaperBench image
docker build \
    -f openhands-agent-server/openhands/agent_server/docker/Dockerfile \
    --target source-minimal-storm \
    --platform linux/amd64 \
    -t agent-server:local \
    . 2>&1 | tail -5
echo "  agent-server:local (paperbench)"

cd "$SCRIPT_DIR"
echo ""

# --- Write .env template ---
echo "[5/6] Writing environment config..."
ENV_FILE="$SCRIPT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" << ENVEOF
# STORM Environment Configuration
# Source this before running: source .env

# Bedrock agent and PaperBench judge. The normal boto3 credential provider
# chain is used, so prefer an IAM role or shared AWS credentials file.
export AWS_REGION_NAME=us-west-2
export LLM_MODEL=bedrock/us.anthropic.claude-sonnet-4-6
export JUDGE_MODEL=bedrock-mantle/openai.gpt-5.5
# GPT-5.5 is served by Bedrock Mantle in us-east-1/us-east-2.
export BEDROCK_MANTLE_REGION=us-east-1
export BEDROCK_JUDGE_MAX_CONCURRENCY=4

# SDK source directory
export SDK_SOURCE_DIR="$SDK_DIR"

# State management (always enabled for multi-agent)
export MS_ENABLE=1
ENVEOF
    echo "  Created $ENV_FILE"
else
    echo "  $ENV_FILE already exists, skipping"
fi
echo ""

# --- Verify setup ---
echo "[6/6] Verifying setup..."

# Check Docker images
if docker run --rm --entrypoint "" agent-server:storm-base echo "ok" >/dev/null 2>&1; then
    echo "  Docker (storm-base): OK"
else
    echo "  Docker (storm-base): FAILED"
fi

if docker run --rm --entrypoint "" agent-server:local echo "ok" >/dev/null 2>&1; then
    echo "  Docker (local): OK"
else
    echo "  Docker (local): FAILED"
fi

# Check commit0 data
if [ -d "$SCRIPT_DIR/data/commit0/commit0_combined_disk" ]; then
    echo "  Commit0 data: OK"
else
    echo "  Commit0 data: NOT FOUND (place at data/commit0/commit0_combined_disk)"
fi

# Check paperbench data
if [ -d "$SCRIPT_DIR/data/paperbench/papers" ]; then
    PAPER_COUNT=$(ls "$SCRIPT_DIR/data/paperbench/papers/" 2>/dev/null | wc -l)
    echo "  PaperBench data: $PAPER_COUNT papers"
else
    echo "  PaperBench data: NOT FOUND (place at data/paperbench/papers/)"
fi

echo ""
echo "============================================================"
echo " Setup complete!"
echo "============================================================"
echo ""
echo " Next steps:"
echo "   1. Fill in your API key in .env and source it:"
echo "      vim .env"
echo "      source .env"
echo ""
echo "   2. Run a single paper:"
echo "      bash scripts/run_multi.sh"
echo ""
echo "   3. Run all 20 papers:"
echo "      bash scripts/run_batch.sh"
echo ""
