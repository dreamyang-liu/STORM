# STORM Agent Runbook

This file is the operational source of truth for agents setting up and running
STORM in this repository. The repository root contains the runnable `STORM/`
project and the vendored `software-agent-sdk/`. Run inference commands from
`STORM/`, not from the repository root.

## Safety and repository hygiene

- Never commit `.env`, AWS credentials, API keys, task data, or generated
  `outputs/`.
- Preserve unrelated working-tree changes.
- Use a unique `--run_id` for every repeated experiment. A repeated run with
  the same arguments and run ID writes to the same output directory.
- Treat `report.json` and `<repo>_test_output.txt` as the authoritative test
  result. A process exit code of zero only means the outer runner completed; it
  does not mean all repository tests passed.
- Keep top-level concurrency at or below four unless the user explicitly asks
  for a different limit.

## Original environment setup

Requirements:

- Linux on `linux/amd64`
- Python 3.12 or newer
- Git
- `uv`
- Docker with a running daemon
- Sufficient Docker disk space for the agent-server and Commit0 task images

Clone and initialize the source tree:

```bash
git clone --recursive https://github.com/dreamyang-liu/STORM.git
cd STORM/STORM
```

The standard setup installs Python dependencies, installs the vendored SDK,
builds both agent-server images, and creates `STORM/.env` if it is missing:

```bash
bash setup.sh
```

The resulting images are:

```text
agent-server:storm-base  # Commit0
agent-server:local       # PaperBench
```

Verify them with:

```bash
docker image inspect agent-server:storm-base >/dev/null
docker image inspect agent-server:local >/dev/null
```

The equivalent manual Commit0 setup is:

```bash
cd /path/to/STORM/STORM
uv sync
uv pip install -e ../software-agent-sdk/openhands-sdk

cd ../software-agent-sdk
docker build \
  -f openhands-agent-server/openhands/agent_server/docker/Dockerfile \
  --target source-minimal-storm \
  --platform linux/amd64 \
  -t agent-server:storm-base \
  .
cd ../STORM
```

Rebuild `agent-server:storm-base` after changing the SDK, its Dockerfile, or
dependencies copied into the image. A rebuild is not required between ordinary
runs against the same source revision. Commit0 also uses base images named
`docker.io/wentingzhao/<repo>:v0`; Docker pulls/builds and caches the
task-specific layer automatically.

## Commit0 data

Store the Hugging Face dataset in on-disk format:

```bash
cd /path/to/STORM/STORM
mkdir -p data/commit0
uv run python - <<'PY'
from datasets import load_dataset

dataset = load_dataset("wentingzhao/commit0_combined", split="test")
dataset.save_to_disk("data/commit0/commit0_combined_disk")
PY
```

Validate the local copy:

```bash
uv run python - <<'PY'
from datasets import load_from_disk

dataset = load_from_disk("data/commit0/commit0_combined_disk")
print(dataset.num_rows)
print(sorted(set(dataset["repo"])))
PY
```

## AWS Bedrock configuration

This branch supports native LiteLLM/OpenHands Bedrock model identifiers.
Credentials are read from the standard AWS environment variables and are
wrapped as secrets before being passed to the SDK.

From `STORM/`, configure each shell that launches a run:

```bash
export AWS_REGION_NAME=us-west-2
export AWS_ACCESS_KEY_ID='...'
export AWS_SECRET_ACCESS_KEY='...'
# Only for temporary credentials:
export AWS_SESSION_TOKEN='...'

export SDK_SOURCE_DIR="$(cd .. && pwd)/software-agent-sdk"
export MS_ENABLE=1
export ENABLE_GPU=0
export OPENHANDS_SUPPRESS_BANNER=1
```

`AWS_REGION` or `AWS_DEFAULT_REGION` can be used instead of
`AWS_REGION_NAME`. Do not set or require `LLM_API_KEY` for a native
`bedrock/...` model. Set `ENABLE_GPU=1` only on a host with a working Docker
GPU runtime.

The model used for the runs below is:

```text
bedrock/us.anthropic.claude-sonnet-4-6
```

PaperBench can use the same Bedrock model and AWS credentials for its judge.
No OpenRouter key is required in this configuration:

```bash
export LLM_MODEL=bedrock/us.anthropic.claude-sonnet-4-6
export JUDGE_MODEL=bedrock/us.anthropic.claude-sonnet-4-6
export BEDROCK_JUDGE_MAX_CONCURRENCY=4
```

The judge uses the native Bedrock Converse API. Its structured grading replies
are validated locally, so the model does not need Bedrock native structured
output support.

To launch the prepared two-engineer PaperBench STORM case after supplying AWS
credentials:

```bash
cd /path/to/STORM/STORM
set -a
source .env
set +a
PAPER_ID=rice RUN_ID=sonnet46-rice-storm-r1 bash scripts/run_multi.sh
```

This runs two engineer subagents for 80 iterations, a 50-iteration manager, two
rounds of manager/engineer discussion, and the code-development-only judge.
As in CAID's public PaperBench harness, the submitted `reproduce.sh` is run for
at most 300 seconds before judging. Set `TEST_REPRODUCE_TIMEOUT` only when a
different bounded validation timeout is intentional.
During PaperBench code-dev, every manager/subagent terminal command is also
hard-limited to 300 seconds. The agent cannot raise the limit through the tool's
own timeout argument. Set `PAPERBENCH_AGENT_COMMAND_TIMEOUT` to change this
limit explicitly.
Keep the run ID unique to avoid overwriting an earlier result.

## Single-agent smoke test

Use `cachetools` as the small initial validation:

```bash
cd /path/to/STORM/STORM

uv run python run_infer.py \
  --task commit0 \
  --repo cachetools \
  --dataset_path data/commit0/commit0_combined_disk \
  --model bedrock/us.anthropic.claude-sonnet-4-6 \
  --nomulti_agent \
  --max_iterations 100 \
  --run_id sonnet46-cachetools-smoke
```

`--nomulti_agent` is required for the single-agent baseline. The
`max_subagents`, `sub_iterations`, and `rounds_of_chat` values encoded in the
generated path are configuration defaults and do not create subagents in this
mode.

## Full two-run batch with four-way global concurrency

The following reproduces the current experiment: all 15 remaining Commit0-lite
repositories (everything in the checked-in list except the already-run
`cachetools` smoke test), two independent run IDs, 100 single-agent iterations,
and at most four top-level runs at once.

Run it from `STORM/` after exporting the Bedrock environment above:

```bash
batch_dir='outputs/batches/sonnet46-full-20260725'
mkdir -p "$batch_dir/logs" "$batch_dir/status"

repos=(
  babel chardet cookiecutter deprecated imapclient
  jinja marshmallow minitorch parsel portalocker
  pyjwt simpy tinydb voluptuous wcwidth
)
run_ids=(sonnet46-full-r1 sonnet46-full-r2)
max_parallel=4

run_one() {
  local repo="$1"
  local run_id="$2"
  local log_file="$batch_dir/logs/${run_id}__${repo}.log"
  local status_file="$batch_dir/status/${run_id}__${repo}.tsv"
  local start_time end_time exit_code

  start_time=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  printf '[BATCH] START run_id=%s repo=%s at=%s\n' \
    "$run_id" "$repo" "$start_time"

  AWS_REGION_NAME="${AWS_REGION_NAME:-us-west-2}" \
  ENABLE_GPU=0 \
  MS_ENABLE=1 \
  SDK_SOURCE_DIR="$SDK_SOURCE_DIR" \
  OPENHANDS_SUPPRESS_BANNER=1 \
  uv run python run_infer.py \
    --task commit0 \
    --repo "$repo" \
    --dataset_path data/commit0/commit0_combined_disk \
    --model bedrock/us.anthropic.claude-sonnet-4-6 \
    --nomulti_agent \
    --max_iterations 100 \
    --run_id "$run_id" \
    >"$log_file" 2>&1
  exit_code=$?

  end_time=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  printf '%s\t%s\t%s\t%s\t%s\n' \
    "$run_id" "$repo" "$exit_code" "$start_time" "$end_time" \
    >"$status_file"
  printf '[BATCH] END run_id=%s repo=%s exit=%s at=%s\n' \
    "$run_id" "$repo" "$exit_code" "$end_time"
}

running=0
for run_id in "${run_ids[@]}"; do
  for repo in "${repos[@]}"; do
    if (( running >= max_parallel )); then
      wait -n || true
      running=$((running - 1))
    fi
    run_one "$repo" "$run_id" &
    running=$((running + 1))
  done
done

while (( running > 0 )); do
  wait -n || true
  running=$((running - 1))
done

printf '[BATCH] ALL COMPLETE at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

The worker pool deliberately records each failure and continues the remaining
tasks. Two run IDs create distinct result directories:

```text
outputs/commit0/us.anthropic.claude-sonnet-4-6/<repo>/single-agent/\
manageriters=100_subagents=4_subiters=50_rchats=2_run=sonnet46-full-r1/

outputs/commit0/us.anthropic.claude-sonnet-4-6/<repo>/single-agent/\
manageriters=100_subagents=4_subiters=50_rchats=2_run=sonnet46-full-r2/
```

Batch logs and status rows are stored under:

```text
outputs/batches/sonnet46-full-20260725/
├── logs/<run-id>__<repo>.log
└── status/<run-id>__<repo>.tsv
```

## Monitoring and validation

Count completed tasks and active agent containers:

```bash
find outputs/batches/sonnet46-full-20260725/status -type f | wc -l
docker ps --filter name=agent-server- --format '{{.Names}}'
```

Follow one task:

```bash
tail -f \
  outputs/batches/sonnet46-full-20260725/logs/\
sonnet46-full-r2__simpy.log
```

Inspect a structured result and cost:

```bash
run_dir='outputs/commit0/us.anthropic.claude-sonnet-4-6/simpy/single-agent/manageriters=100_subagents=4_subiters=50_rchats=2_run=sonnet46-full-r2'
jq '{summary,duration}' "$run_dir/report.json"
jq '{cost:.total.cost,tokens:.total.total_tokens,wall:.total.wall_clock_duration}' \
  "$run_dir/cost.json"
```

If `report.json` is empty or malformed, inspect the raw output:

```bash
tail -n 100 "$run_dir/simpy_test_output.txt"
```

Bedrock requests have a 300-second timeout and SDK-managed retries. Do not kill
a run merely because one request is quiet for several minutes. A
`MaxIterationsReached` agent status also does not stop the outer runner from
executing pytest and saving the final repository.

With `MS_ENABLE=1`, the SDK logs versioned manager reads and writes. To verify
that file-version tracking was active for a live container:

```bash
docker logs <container-id> 2>&1 |
  jq -Rr 'fromjson? | select(.name=="multiagent-sync.manager") | .message' |
  rg ' reads | writes | creates '
```

Single-agent mode still exercises the versioned file manager, but it does not
create cross-agent write contention.
