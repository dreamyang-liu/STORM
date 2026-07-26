import asyncio
import json

from pydantic import BaseModel

from judge.bedrock_mantle_turn_completer import (
    BedrockMantleTurnCompleter,
    bedrock_mantle_model_id,
    bedrock_mantle_responses_url,
    conversation_to_responses_input,
    extract_response_text,
    resolve_bedrock_mantle_region,
)
from judge.judge_runner import _build_completer_config


MODEL = "bedrock-mantle/openai.gpt-5.5"


class ParsedScore(BaseModel):
    valid_score: bool
    score: int
    explanation: str


def test_model_region_and_gpt_responses_path(monkeypatch):
    monkeypatch.delenv("BEDROCK_MANTLE_REGION", raising=False)
    assert bedrock_mantle_model_id(MODEL) == "openai.gpt-5.5"
    assert resolve_bedrock_mantle_region() == "us-east-1"
    assert resolve_bedrock_mantle_region("us-east-2") == "us-east-2"
    assert bedrock_mantle_responses_url("openai.gpt-5.5", "us-east-1") == (
        "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses"
    )


def test_judge_runner_routes_mantle_models_to_responses_config(monkeypatch):
    monkeypatch.setenv("BEDROCK_MANTLE_REGION", "us-east-1")
    config = _build_completer_config(MODEL, response_format=ParsedScore)
    completer = config.build()
    assert isinstance(config, BedrockMantleTurnCompleter.Config)
    assert isinstance(completer, BedrockMantleTurnCompleter)
    assert completer.reasoning_effort == "low"


def test_conversation_and_structured_payload(monkeypatch):
    monkeypatch.setenv("BEDROCK_MANTLE_REGION", "us-east-1")
    conversation = [
        {"role": "system", "content": "Grade carefully."},
        {"role": "user", "content": "Return the score."},
    ]
    assert conversation_to_responses_input(conversation) == conversation

    completer = BedrockMantleTurnCompleter(
        model=MODEL,
        response_format=ParsedScore,
        reasoning_effort="low",
        max_tokens=512,
    )
    payload = completer._build_payload(conversation)
    assert payload["model"] == "openai.gpt-5.5"
    assert payload["store"] is False
    assert payload["max_output_tokens"] == 512
    assert payload["reasoning"] == {"effort": "low"}
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True
    assert payload["text"]["format"]["schema"]["additionalProperties"] is False


def test_extract_response_text_from_bedrock_shape():
    response = {
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "first",
                    },
                    {
                        "type": "output_text",
                        "text": "second",
                    },
                ],
            }
        ]
    }
    assert extract_response_text(response) == "first\nsecond"


def test_async_completion_preserves_structured_output_and_usage(monkeypatch):
    monkeypatch.setenv("BEDROCK_MANTLE_REGION", "us-east-1")
    completer = BedrockMantleTurnCompleter(
        model=MODEL,
        response_format=ParsedScore,
        max_tokens=512,
    )
    captured = {}

    def fake_send(payload):
        captured["payload"] = payload
        return {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": (
                                '{"valid_score":true,"score":1,'
                                '"explanation":"passes"}'
                            ),
                        }
                    ],
                }
            ],
            "usage": {
                "input_tokens": 20,
                "output_tokens": 10,
                "total_tokens": 30,
            },
        }

    monkeypatch.setattr(completer, "_send_response_request", fake_send)
    result = asyncio.run(
        completer.async_completion(
            [{"role": "user", "content": "The implementation passes."}]
        )
    )

    assert captured["payload"]["model"] == "openai.gpt-5.5"
    assert json.loads(result.output_messages[0].content) == {
        "valid_score": True,
        "score": 1,
        "explanation": "passes",
    }
    assert result.usage is not None
    assert result.usage.prompt_tokens == 20
    assert result.usage.completion_tokens == 10
