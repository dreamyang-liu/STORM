# STORM: Multi-agent Collaboration with State Management

Multi-agent orchestration framework for code implementation (Commit0) and paper reproduction (PaperBench) benchmarks. Built on OpenHands SDK.

<p align="center">
  <img src="STORM/teaser/arch.png" alt="STORM Overview" width="80%">
</p>

## Setup

### Prerequisites

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Docker](https://docs.docker.com/get-docker/)

### Quick Start

```bash
# Clone the repository (with submodules)
git clone --recursive https://github.com/dreamyang-liu/STORM.git
cd STORM/STORM

# Run the setup script (installs deps + builds Docker images)
bash setup.sh

# Set your API key
source .env   # edit .env first to fill in LLM_API_KEY and OPENROUTER_API_KEY
```

### Manual Installation

```bash
cd STORM/STORM

# Install Python dependencies
uv sync

# Build Docker image
cd ../software-agent-sdk
docker build \
  -f openhands-agent-server/openhands/agent_server/docker/Dockerfile \
  --target source-minimal-storm \
  --platform linux/amd64 \
  -t agent-server:storm-base \
  .
cd ../STORM
```

### Environment Variables

```bash
# Native AWS Bedrock for the agents and Bedrock Mantle for the judge
export AWS_REGION_NAME=us-west-2
export AWS_ACCESS_KEY_ID=<your-access-key>
export AWS_SECRET_ACCESS_KEY=<your-secret-key>
# export AWS_SESSION_TOKEN=<your-session-token>    # temporary credentials only
export LLM_MODEL=bedrock/us.anthropic.claude-sonnet-4-6
export JUDGE_MODEL=bedrock-mantle/openai.gpt-5.5
export BEDROCK_MANTLE_REGION=us-east-1
export BEDROCK_JUDGE_MAX_CONCURRENCY=4

# SDK path
export SDK_SOURCE_DIR=<path-to>/software-agent-sdk
```

## Prepare Data

### Commit0

Download the [commit0_combined](https://huggingface.co/datasets/wentingzhao/commit0_combined) dataset:

```bash
# Place at STORM/data/commit0/commit0_combined_disk/
```

### PaperBench

Place the PaperBench data from [frontier-evals](https://github.com/openai/frontier-evals) at:

```
STORM/data/paperbench/papers/
├── rice/
│   ├── config.yaml
│   ├── paper.pdf
│   ├── paper.md
│   ├── rubric.json
│   ├── addendum.md
│   └── blacklist.txt
└── ...
```

PaperBench judge requires additional packages:
```bash
uv pip install -e ../frontier-evals/project/paperbench
uv pip install -e ../frontier-evals/project/common/preparedness_turn_completer
```

## Running Experiments

### Single-Agent Baseline

```bash
bash scripts/run_single.sh
```

### Multi-Agent (STORM)

```bash
PAPER_ID=rice RUN_ID=sonnet46-rice-storm-r1 bash scripts/run_multi.sh
```

### Batch Run (all papers/repos in parallel)

```bash
bash scripts/run_batch.sh
```

Edit the parameters at the top of each script (model, task, paper_id/repo, etc.) before running.

### Key Parameters

| Parameter | Description |
|-----------|-------------|
| `task` | `"commit0"` or `"paperbench"` |
| `model` | LiteLLM model identifier (e.g., `openai/deepseek-v4-pro`) |
| `max_subagents` | Number of parallel engineer subagents |
| `max_iterations` | Maximum LLM iterations for the manager |
| `sub_iterations` | Maximum LLM iterations per subagent |
| `rounds_of_chat` | Maximum rounds of task assignment per engineer |

### Output

Results are saved to `outputs/<task>/<model>/<identifier>/<mode>/<params>/`:
- `cost.json` — token usage and cost breakdown
- `runtime.txt` — wall-clock runtime in seconds
- `outputs.jsonl` — structured event log
- `grade.json` — (PaperBench) judge evaluation results
- `report.json` — (Commit0) pytest results

### Re-judge

```bash
bash scripts/rejudge.sh <output_dir> [paper1 paper2 ...]
```

## Acknowledgements

We thank the following open-source projects that STORM builds upon:
- [OpenHands](https://docs.openhands.dev/sdk) for the agent SDK framework
- [Commit0](https://commit-0.github.io/) for the code implementation benchmark
- [PaperBench](https://arxiv.org/abs/2504.01848) for the paper reproduction benchmark

## Citation

```bibtex
@misc{liu2026multiagentcollaborationstatemanagement,
      title={Multi-agent Collaboration with State Management},
      author={Mengyang Liu and Taozhi Chen and Zhenhua Xu and Xue Jiang and Yihong Dong},
      year={2026},
      eprint={2605.20563},
      archivePrefix={arXiv},
      primaryClass={cs.MA},
      url={https://arxiv.org/abs/2605.20563},
}
```
