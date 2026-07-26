"""
python -m judge.judge_runner
"""
import asyncio
import copy
import json
import os
import re
from pathlib import Path
import fire
from litellm import cost_per_token
from openai import NOT_GIVEN
from paperbench.judge.graded_task_node import GradedTaskNode
from paperbench.judge.create_judge import create_judge, handle_judge_kwargs
from paperbench.judge.simple import ParsedJudgeResponseFloat, ParsedJudgeResponseInt
from paperbench.judge.token_usage import get_total_token_usage
from paperbench.paper_registry import paper_registry
from paperbench.rubric.tasks import TaskNode
from preparedness_turn_completer.oai_completions_turn_completer import (
    OpenAICompletionsTurnCompleter,
)

from judge.bedrock_mantle_turn_completer import (
    BedrockMantleTurnCompleter,
    is_bedrock_mantle_model,
)
from judge.bedrock_turn_completer import BedrockTurnCompleter, is_bedrock_model


DEFAULT_DATA_DIR = str(Path(__file__).resolve().parents[1] / "data" / "paperbench")
SCORE_AFTER_HEADING_RE = re.compile(
    r"#\s*Score\b.{0,100}?\b([01])(?:\.0)?\b",
    flags=re.IGNORECASE | re.DOTALL,
)


def _load_resumable_leaf_results(log_dir):
    """Load completed leaf grades from SimpleJudge message transcripts."""
    if not log_dir:
        return {}

    cached = {}
    for message_path in Path(log_dir).glob("*_messages.jsonl"):
        try:
            messages = [
                json.loads(line)
                for line in message_path.read_text().splitlines()
                if line.strip()
            ]
            assistant_messages = [
                message.get("content", "")
                for message in messages
                if message.get("role") == "assistant"
            ]
            if not assistant_messages:
                continue

            response = assistant_messages[-1]
            match = SCORE_AFTER_HEADING_RE.search(response)
            if not match:
                continue

            node_id = message_path.name.removesuffix("_messages.jsonl")
            cached[node_id] = {
                "score": int(match.group(1)),
                "response": response,
                "source": str(message_path),
            }
        except (OSError, json.JSONDecodeError):
            continue
    return cached


def _content_mentions_json(content):
    if isinstance(content, str):
        return "json" in content.lower()
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                text = part.get("text") or part.get("content")
                if isinstance(text, str) and "json" in text.lower():
                    return True
    return False


def _conversation_mentions_json(conversation):
    for message in conversation:
        if isinstance(message, dict) and _content_mentions_json(message.get("content")):
            return True
    return False


def _inject_json_hint(conversation):
    if _conversation_mentions_json(conversation):
        return conversation

    hint = "IMPORTANT: Return a valid JSON object that matches the requested schema."
    patched = copy.deepcopy(conversation)
    for message in patched:
        if (
            isinstance(message, dict)
            and message.get("role") == "system"
            and isinstance(message.get("content"), str)
        ):
            message["content"] = f"{message['content']}\n\n{hint}"
            return patched

    patched.insert(0, {"role": "system", "content": hint})
    return patched


def _patch_structured_output_requests():
    if getattr(OpenAICompletionsTurnCompleter, "_storm_json_hint_patch", False):
        return

    original_async_completion = OpenAICompletionsTurnCompleter.async_completion

    async def patched_async_completion(self, conversation, **params):
        response_format = getattr(self, "response_format", None)
        if response_format is not None and type(response_format).__name__ != "NotGiven":
            conversation = _inject_json_hint(conversation)
        return await original_async_completion(self, conversation, **params)

    OpenAICompletionsTurnCompleter.async_completion = patched_async_completion
    OpenAICompletionsTurnCompleter._storm_json_hint_patch = True


def _build_completer_config(
    judge_model,
    response_format=NOT_GIVEN,
    max_tokens=4096,
):
    if is_bedrock_mantle_model(judge_model):
        config_class = BedrockMantleTurnCompleter.Config
    elif is_bedrock_model(judge_model):
        config_class = BedrockTurnCompleter.Config
    else:
        config_class = OpenAICompletionsTurnCompleter.Config
    kwargs = {
        "model": judge_model,
        "max_tokens": max_tokens,
    }
    if response_format is not NOT_GIVEN:
        kwargs["response_format"] = response_format
    if not is_bedrock_model(judge_model):
        kwargs["reasoning_effort"] = "low"
    return config_class(**kwargs)


def run(
    submission_path,
    paper_id,
    result_file,
    judge_type="simple",
    judge_model="bedrock-mantle/openai.gpt-5.5",
    max_depth=999,
    code_dev=True,
    log_dir=None,
    resume_from_log_dir=None,
    data_dir=None,
):
    os.environ["PAPERBENCH_DATA_DIR"] = data_dir or os.environ.get(
        "PAPERBENCH_DATA_DIR", DEFAULT_DATA_DIR
    )

    if is_bedrock_model(judge_model) or is_bedrock_mantle_model(judge_model):
        max_concurrency = int(os.getenv("BEDROCK_JUDGE_MAX_CONCURRENCY", "4"))
    else:
        # OpenAI-compatible judges use JUDGE_API_KEY/JUDGE_BASE_URL, then
        # fall back to the historical OpenRouter/LLM environment variables.
        judge_key = (
            os.environ.get("JUDGE_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("LLM_API_KEY")
        )
        judge_base = os.environ.get("JUDGE_BASE_URL") or "https://openrouter.ai/api/v1"
        if judge_key:
            os.environ["OPENAI_API_KEY"] = judge_key
        os.environ["OPENAI_BASE_URL"] = judge_base
        _patch_structured_output_requests()
        max_concurrency = 100

    completer_config = None
    if judge_type == "simple":
        completer_config = _build_completer_config(judge_model)

    submission_path = Path(submission_path)
    out_dir = Path(log_dir) if log_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    cached_leaf_results = _load_resumable_leaf_results(resume_from_log_dir)

    async def _run():
        paper = paper_registry.get_paper(paper_id)
        with open(paper.rubric, "r") as f:
            task_tree = TaskNode.from_dict(json.load(f))

        if code_dev:
            task_tree = task_tree.code_only() or task_tree.set_task_category(
                "Code Development"
            ).set_sub_tasks([])

        judge_kwargs = handle_judge_kwargs(judge_type, code_dev, paper, completer_config)

        # Pass structured completer configs so SimpleJudge doesn't fall back
        # to the hardcoded neulab/gpt-4o-2024-08-06 model.
        # Use reasoning_effort="low" and high max_tokens because the parsing
        # task is trivial and reasoning models waste output tokens on thinking.
        if judge_type == "simple" and completer_config is not None:
            judge_kwargs["float_completer_config"] = _build_completer_config(
                judge_model,
                response_format=ParsedJudgeResponseFloat,
            )
            judge_kwargs["int_completer_config"] = _build_completer_config(
                judge_model,
                response_format=ParsedJudgeResponseInt,
            )

        judge = create_judge(
            judge_type=judge_type,
            judge_kwargs=judge_kwargs,
            paper_path=paper.paper_pdf,
            rubric=task_tree,
            addendum=paper.addendum.read_text() if paper.addendum else None,
            judge_addendum=paper.judge_addendum.read_text() if paper.judge_addendum.exists() else None,
            submission_dir=submission_path,
            paper_md=paper.paper_md,
            log_path=out_dir,
            max_depth=max_depth,
        )
        judge.leaf_semaphore = asyncio.Semaphore(max(1, max_concurrency))

        async def grade_leaf_with_resume(task):
            cached = cached_leaf_results.get(task.id)
            if cached is None:
                return await judge.grade_leaf(task)
            return GradedTaskNode.from_task(
                task,
                score=cached["score"],
                valid_score=True,
                explanation=cached["response"],
                judge_metadata={
                    "full_judge_response": cached["response"],
                    "resumed_from": cached["source"],
                },
            )

        return await judge.judge(grade_leaf_fn=grade_leaf_with_resume)

    graded_tree = asyncio.run(_run())

    token_usage = get_total_token_usage(graded_tree)
    total_cost = 0.0
    for model, usage in token_usage.to_dict().items():
        try:
            prompt_cost, completion_cost = cost_per_token(
                model=model, prompt_tokens=usage["in"], completion_tokens=usage["out"],
            )
            total_cost += prompt_cost + completion_cost
        except Exception:
            pass

    leaf_nodes = graded_tree.get_leaf_nodes()
    result = {
        "score": graded_tree.score,
        "num_nodes": len(leaf_nodes),
        "num_invalid_nodes": len([n for n in leaf_nodes if not n.valid_score]),
        "num_resumed_nodes": sum(node.id in cached_leaf_results for node in leaf_nodes),
        "token_usage": token_usage.to_dict(),
        "cost": total_cost,
        "graded_task_tree": graded_tree.to_dict(),
    }

    with open(result_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Judge score: {result['score']}")
    print(f"Nodes: {result['num_nodes']}, Invalid: {result['num_invalid_nodes']}")
    print(f"Resumed nodes: {result['num_resumed_nodes']}")
    print(f"Judge cost: ${total_cost:.4f}")
    print(f"Results saved to: {result_file}")


if __name__ == "__main__":
    fire.Fire(run)
