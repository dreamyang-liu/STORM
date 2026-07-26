from __future__ import annotations

import asyncio
import json
import os
from functools import cached_property
from typing import Any

import boto3
import tiktoken
from botocore.config import Config as BotocoreConfig
from json_repair import loads as repair_json_loads
from openai import NOT_GIVEN, NotGiven
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletionMessage
from preparedness_turn_completer.oai_completions_turn_completer import (
    OpenAICompletionsTurnCompleter,
)
from preparedness_turn_completer.turn_completer import TurnCompleter
from pydantic import BaseModel


DEFAULT_BEDROCK_CONTEXT_WINDOW = 1_000_000
DEFAULT_MAX_TOKENS = 4096


def is_bedrock_model(model: str) -> bool:
    return model.startswith("bedrock/")


def bedrock_model_id(model: str) -> str:
    return model.removeprefix("bedrock/")


def resolve_bedrock_region(region_name: str | None = None) -> str:
    region = (
        region_name
        or os.getenv("AWS_REGION_NAME")
        or os.getenv("AWS_REGION")
        or os.getenv("AWS_DEFAULT_REGION")
    )
    if not region:
        raise ValueError(
            "Please set AWS_REGION_NAME, AWS_REGION, or AWS_DEFAULT_REGION "
            "for a Bedrock judge"
        )
    return region


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)

    parts: list[str] = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
        elif isinstance(part, dict):
            text = part.get("text") or part.get("content")
            if isinstance(text, str):
                parts.append(text)
        else:
            text = getattr(part, "text", None)
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)


def conversation_to_bedrock(
    conversation: TurnCompleter.RuntimeConversation,
    response_format: type[BaseModel] | NotGiven = NOT_GIVEN,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    system_parts: list[str] = []
    messages: list[dict[str, Any]] = []

    for message in conversation:
        role = str(message.get("role", "user"))
        text = _content_to_text(message.get("content"))
        if not text:
            continue

        if role in {"system", "developer"}:
            system_parts.append(text)
            continue
        if role not in {"user", "assistant"}:
            raise ValueError(f"Unsupported Bedrock judge message role: {role}")

        if messages and messages[-1]["role"] == role:
            messages[-1]["content"][0]["text"] += f"\n\n{text}"
        else:
            messages.append({"role": role, "content": [{"text": text}]})

    if not messages:
        raise ValueError("Bedrock judge conversation contains no user or assistant message")

    if not isinstance(response_format, NotGiven):
        schema = response_format.model_json_schema()
        system_parts.append(
            "Return only one valid JSON object matching this JSON Schema. "
            "Do not wrap it in Markdown fences and do not add prose outside the object.\n"
            f"{json.dumps(schema, ensure_ascii=False)}"
        )

    system = [{"text": "\n\n".join(system_parts)}] if system_parts else []
    return messages, system


def canonicalize_structured_response(
    text: str, response_format: type[BaseModel] | NotGiven
) -> str:
    if isinstance(response_format, NotGiven):
        return text

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = repair_json_loads(text)

    validated = response_format.model_validate(payload)
    return validated.model_dump_json()


class BedrockTurnCompleter(OpenAICompletionsTurnCompleter):
    """PaperBench TurnCompleter backed by the native Bedrock Converse API.

    This subclasses the OpenAI completer so PaperBench's existing token-accounting
    code continues to recognize its CompletionUsage objects.
    """

    def __init__(
        self,
        model: str,
        response_format: type[BaseModel] | NotGiven = NOT_GIVEN,
        temperature: float | None | NotGiven = NOT_GIVEN,
        max_tokens: int | None | NotGiven = NOT_GIVEN,
        top_p: float | None | NotGiven = NOT_GIVEN,
        region_name: str | None = None,
        context_window: int = DEFAULT_BEDROCK_CONTEXT_WINDOW,
        completion_attempts: int = 3,
        **_: Any,
    ):
        if not is_bedrock_model(model):
            raise ValueError(f"Expected a bedrock/... judge model, got: {model}")
        self.model = model
        self.response_format = response_format
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.region_name = resolve_bedrock_region(region_name)
        self.encoding_name = "o200k_base"
        self.token_encoder = tiktoken.get_encoding(self.encoding_name)
        self.n_ctx = context_window
        self.completion_attempts = max(1, completion_attempts)

    class Config(OpenAICompletionsTurnCompleter.Config):
        region_name: str | None = None
        context_window: int = DEFAULT_BEDROCK_CONTEXT_WINDOW
        completion_attempts: int = 3

        def build(self) -> BedrockTurnCompleter:
            return BedrockTurnCompleter(
                model=self.model,
                response_format=self.response_format,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                top_p=self.top_p,
                region_name=self.region_name,
                context_window=self.context_window,
                completion_attempts=self.completion_attempts,
            )

    @cached_property
    def _bedrock_client(self):
        return boto3.client(
            "bedrock-runtime",
            region_name=self.region_name,
            config=BotocoreConfig(
                connect_timeout=10,
                read_timeout=300,
                retries={"max_attempts": 8, "mode": "adaptive"},
            ),
        )

    def completion(
        self,
        conversation: TurnCompleter.RuntimeConversation,
        **params: Any,
    ) -> OpenAICompletionsTurnCompleter.Completion:
        raise NotImplementedError("Not implemented, use async_completion instead")

    async def async_completion(
        self,
        conversation: TurnCompleter.RuntimeConversation,
        **params: Any,
    ) -> OpenAICompletionsTurnCompleter.Completion:
        if params:
            raise ValueError(f"Unsupported Bedrock judge completion parameters: {params}")

        messages, system = conversation_to_bedrock(
            conversation, response_format=self.response_format
        )
        inference_config: dict[str, Any] = {
            "maxTokens": (
                DEFAULT_MAX_TOKENS
                if isinstance(self.max_tokens, NotGiven) or self.max_tokens is None
                else self.max_tokens
            )
        }
        if not isinstance(self.temperature, NotGiven) and self.temperature is not None:
            inference_config["temperature"] = self.temperature
        if not isinstance(self.top_p, NotGiven) and self.top_p is not None:
            inference_config["topP"] = self.top_p

        request: dict[str, Any] = {
            "modelId": bedrock_model_id(self.model),
            "messages": messages,
            "inferenceConfig": inference_config,
        }
        if system:
            request["system"] = system

        last_error: Exception | None = None
        for attempt in range(1, self.completion_attempts + 1):
            try:
                response = await asyncio.to_thread(
                    self._bedrock_client.converse, **request
                )
                content_blocks = response["output"]["message"]["content"]
                text = "\n".join(
                    block["text"]
                    for block in content_blocks
                    if isinstance(block, dict) and isinstance(block.get("text"), str)
                ).strip()
                if not text:
                    raise ValueError("Bedrock judge returned no text content")
                text = canonicalize_structured_response(text, self.response_format)

                usage = response.get("usage", {})
                prompt_tokens = int(usage.get("inputTokens", 0))
                completion_tokens = int(usage.get("outputTokens", 0))
                total_tokens = int(
                    usage.get(
                        "totalTokens", prompt_tokens + completion_tokens
                    )
                )
                return OpenAICompletionsTurnCompleter.Completion(
                    input_conversation=conversation,
                    output_messages=[
                        ChatCompletionMessage(
                            role="assistant",
                            content=text,
                        )
                    ],
                    usage=CompletionUsage(
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                    ),
                )
            except Exception as exc:
                last_error = exc
                if attempt == self.completion_attempts:
                    break
                await asyncio.sleep(min(2 ** (attempt - 1), 10))

        assert last_error is not None
        raise last_error
