import asyncio
import json

from openai import NOT_GIVEN
from pydantic import BaseModel

from judge.bedrock_turn_completer import (
    BedrockTurnCompleter,
    bedrock_model_id,
    canonicalize_structured_response,
    conversation_to_bedrock,
    resolve_bedrock_region,
)
from judge.judge_runner import _build_completer_config


MODEL = "bedrock/us.anthropic.claude-sonnet-4-6"


class ParsedScore(BaseModel):
    valid_score: bool
    score: int
    explanation: str


def test_model_and_region_resolution(monkeypatch):
    monkeypatch.setenv("AWS_REGION_NAME", "us-west-2")
    assert bedrock_model_id(MODEL) == "us.anthropic.claude-sonnet-4-6"
    assert resolve_bedrock_region() == "us-west-2"
    assert resolve_bedrock_region("us-east-1") == "us-east-1"


def test_judge_runner_routes_bedrock_models_to_native_config(monkeypatch):
    monkeypatch.setenv("AWS_REGION_NAME", "us-west-2")
    config = _build_completer_config(MODEL, response_format=ParsedScore)
    completer = config.build()
    assert isinstance(config, BedrockTurnCompleter.Config)
    assert isinstance(completer, BedrockTurnCompleter)


def test_conversation_conversion_merges_adjacent_messages_and_adds_schema():
    messages, system = conversation_to_bedrock(
        [
            {"role": "system", "content": "Grade carefully."},
            {"role": "user", "content": "First context."},
            {"role": "user", "content": "Second context."},
        ],
        response_format=ParsedScore,
    )

    assert messages == [
        {
            "role": "user",
            "content": [{"text": "First context.\n\nSecond context."}],
        }
    ]
    assert system[0]["text"].startswith("Grade carefully.")
    assert '"valid_score"' in system[0]["text"]


def test_unstructured_conversion_does_not_add_json_instruction():
    _, system = conversation_to_bedrock(
        [
            {"role": "system", "content": "Select files."},
            {"role": "user", "content": "List the relevant files."},
        ],
        response_format=NOT_GIVEN,
    )
    assert system == [{"text": "Select files."}]


def test_structured_response_is_repaired_validated_and_canonicalized():
    result = canonicalize_structured_response(
        '```json\n{"valid_score": true, "score": 1, "explanation": "ok"}\n```',
        ParsedScore,
    )
    assert json.loads(result) == {
        "valid_score": True,
        "score": 1,
        "explanation": "ok",
    }


def test_async_completion_uses_converse_and_preserves_usage(monkeypatch):
    monkeypatch.setenv("AWS_REGION_NAME", "us-west-2")
    completer = BedrockTurnCompleter(
        model=MODEL,
        response_format=ParsedScore,
        max_tokens=512,
    )

    class FakeClient:
        def __init__(self):
            self.request = None

        def converse(self, **request):
            self.request = request
            return {
                "output": {
                    "message": {
                        "content": [
                            {
                                "text": (
                                    '{"valid_score":true,"score":1,'
                                    '"explanation":"passes"}'
                                )
                            }
                        ]
                    }
                },
                "usage": {
                    "inputTokens": 12,
                    "outputTokens": 8,
                    "totalTokens": 20,
                },
            }

    fake_client = FakeClient()
    completer.__dict__["_bedrock_client"] = fake_client
    result = asyncio.run(
        completer.async_completion(
            [
                {"role": "system", "content": "Parse the score."},
                {"role": "user", "content": "The score is one."},
            ]
        )
    )

    assert fake_client.request["modelId"] == "us.anthropic.claude-sonnet-4-6"
    assert fake_client.request["inferenceConfig"]["maxTokens"] == 512
    assert json.loads(result.output_messages[0].content) == {
        "valid_score": True,
        "score": 1,
        "explanation": "passes",
    }
    assert result.usage is not None
    assert result.usage.prompt_tokens == 12
    assert result.usage.completion_tokens == 8
