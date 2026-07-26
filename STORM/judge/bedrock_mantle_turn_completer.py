from __future__ import annotations

import asyncio
import json
import os
import re
from functools import cached_property
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import boto3
import tiktoken
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from openai import NOT_GIVEN, NotGiven
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletionMessage
from preparedness_turn_completer.oai_completions_turn_completer import (
    OpenAICompletionsTurnCompleter,
)
from preparedness_turn_completer.turn_completer import TurnCompleter
from pydantic import BaseModel


BEDROCK_MANTLE_PREFIX = "bedrock-mantle/"
DEFAULT_BEDROCK_MANTLE_REGION = "us-east-1"
DEFAULT_CONTEXT_WINDOW = 272_000
DEFAULT_MAX_OUTPUT_TOKENS = 4096


def is_bedrock_mantle_model(model: str) -> bool:
    return model.startswith(BEDROCK_MANTLE_PREFIX)


def bedrock_mantle_model_id(model: str) -> str:
    return model.removeprefix(BEDROCK_MANTLE_PREFIX)


def resolve_bedrock_mantle_region(region_name: str | None = None) -> str:
    # GPT-5.5 is currently offered in us-east-1 and us-east-2. Do not inherit
    # AWS_REGION_NAME here because the agent may intentionally run elsewhere.
    return (
        region_name
        or os.getenv("BEDROCK_MANTLE_REGION")
        or DEFAULT_BEDROCK_MANTLE_REGION
    )


def bedrock_mantle_responses_url(model_id: str, region_name: str) -> str:
    base_url = f"https://bedrock-mantle.{region_name}.api.aws"
    if model_id.startswith("openai.gpt-"):
        return f"{base_url}/openai/v1/responses"
    return f"{base_url}/v1/responses"


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


def conversation_to_responses_input(
    conversation: TurnCompleter.RuntimeConversation,
) -> list[dict[str, str]]:
    response_input: list[dict[str, str]] = []
    for message in conversation:
        role = str(message.get("role", "user"))
        if role not in {"system", "developer", "user", "assistant"}:
            raise ValueError(f"Unsupported Bedrock Responses message role: {role}")
        content = _content_to_text(message.get("content"))
        if content:
            response_input.append({"role": role, "content": content})

    if not response_input:
        raise ValueError("Bedrock Responses conversation contains no text messages")
    return response_input


def _json_schema_format(response_format: type[BaseModel]) -> dict[str, Any]:
    schema = response_format.model_json_schema()
    if schema.get("type") == "object":
        schema.setdefault("additionalProperties", False)
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", response_format.__name__)[:64]
    return {
        "type": "json_schema",
        "name": name or "paperbench_judge_response",
        "schema": schema,
        "strict": True,
    }


def extract_response_text(response: dict[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    text_parts: list[str] = []
    for output_item in response.get("output", []):
        if not isinstance(output_item, dict) or output_item.get("type") != "message":
            continue
        for content_item in output_item.get("content", []):
            if (
                isinstance(content_item, dict)
                and content_item.get("type") == "output_text"
                and isinstance(content_item.get("text"), str)
            ):
                text_parts.append(content_item["text"])
    return "\n".join(text_parts).strip()


class BedrockMantleTurnCompleter(OpenAICompletionsTurnCompleter):
    """PaperBench completer for Bedrock Mantle's OpenAI Responses endpoint."""

    def __init__(
        self,
        model: str,
        reasoning_effort: str | None | NotGiven = NOT_GIVEN,
        response_format: type[BaseModel] | NotGiven = NOT_GIVEN,
        temperature: float | None | NotGiven = NOT_GIVEN,
        max_tokens: int | None | NotGiven = NOT_GIVEN,
        top_p: float | None | NotGiven = NOT_GIVEN,
        region_name: str | None = None,
        context_window: int = DEFAULT_CONTEXT_WINDOW,
        completion_attempts: int = 3,
        request_timeout: int = 300,
        **_: Any,
    ):
        if not is_bedrock_mantle_model(model):
            raise ValueError(
                f"Expected a {BEDROCK_MANTLE_PREFIX}... judge model, got: {model}"
            )
        self.model = model
        self.model_id = bedrock_mantle_model_id(model)
        self.reasoning_effort = reasoning_effort
        self.response_format = response_format
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.region_name = resolve_bedrock_mantle_region(region_name)
        self.responses_url = bedrock_mantle_responses_url(
            self.model_id, self.region_name
        )
        self.encoding_name = "o200k_base"
        self.token_encoder = tiktoken.get_encoding(self.encoding_name)
        self.n_ctx = context_window
        self.completion_attempts = max(1, completion_attempts)
        self.request_timeout = request_timeout

    class Config(OpenAICompletionsTurnCompleter.Config):
        region_name: str | None = None
        context_window: int = DEFAULT_CONTEXT_WINDOW
        completion_attempts: int = 3
        request_timeout: int = 300

        def build(self) -> BedrockMantleTurnCompleter:
            return BedrockMantleTurnCompleter(
                model=self.model,
                reasoning_effort=self.reasoning_effort,
                response_format=self.response_format,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                top_p=self.top_p,
                region_name=self.region_name,
                context_window=self.context_window,
                completion_attempts=self.completion_attempts,
                request_timeout=self.request_timeout,
            )

    @cached_property
    def _boto_session(self) -> boto3.Session:
        return boto3.Session()

    def _build_payload(
        self, conversation: TurnCompleter.RuntimeConversation
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model_id,
            "input": conversation_to_responses_input(conversation),
            "max_output_tokens": (
                DEFAULT_MAX_OUTPUT_TOKENS
                if isinstance(self.max_tokens, NotGiven) or self.max_tokens is None
                else self.max_tokens
            ),
            # PaperBench sends the complete conversation each time, so retaining
            # response state in Bedrock is unnecessary.
            "store": False,
        }
        if (
            not isinstance(self.reasoning_effort, NotGiven)
            and self.reasoning_effort is not None
        ):
            payload["reasoning"] = {"effort": self.reasoning_effort}
        if not isinstance(self.temperature, NotGiven) and self.temperature is not None:
            payload["temperature"] = self.temperature
        if not isinstance(self.top_p, NotGiven) and self.top_p is not None:
            payload["top_p"] = self.top_p
        if not isinstance(self.response_format, NotGiven):
            payload["text"] = {"format": _json_schema_format(self.response_format)}
        return payload

    def _send_response_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, separators=(",", ":")).encode()
        credentials = self._boto_session.get_credentials()
        if credentials is None:
            raise RuntimeError("No AWS credentials available for Bedrock GPT-5.5 judge")

        aws_request = AWSRequest(
            method="POST",
            url=self.responses_url,
            data=body,
            headers={"content-type": "application/json", "accept": "application/json"},
        )
        SigV4Auth(
            credentials.get_frozen_credentials(),
            "bedrock-mantle",
            self.region_name,
        ).add_auth(aws_request)

        request = Request(
            self.responses_url,
            data=body,
            headers=dict(aws_request.headers.items()),
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.request_timeout) as response:
                response_body = response.read()
        except HTTPError as exc:
            error_body = exc.read().decode(errors="replace")
            request_id = exc.headers.get("x-request-id") or exc.headers.get(
                "x-amzn-requestid"
            )
            raise RuntimeError(
                f"Bedrock Mantle request failed ({exc.code}, request_id={request_id}): "
                f"{error_body[:2000]}"
            ) from exc

        parsed = json.loads(response_body)
        if not isinstance(parsed, dict):
            raise ValueError("Bedrock Mantle returned a non-object response")
        return parsed

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
            raise ValueError(
                f"Unsupported Bedrock Mantle completion parameters: {params}"
            )

        payload = self._build_payload(conversation)
        last_error: Exception | None = None
        for attempt in range(1, self.completion_attempts + 1):
            try:
                response = await asyncio.to_thread(
                    self._send_response_request, payload
                )
                text = extract_response_text(response)
                if not text:
                    raise ValueError(
                        "Bedrock GPT-5.5 judge returned no final text "
                        f"(status={response.get('status')})"
                    )
                if not isinstance(self.response_format, NotGiven):
                    validated = self.response_format.model_validate_json(text)
                    text = validated.model_dump_json()

                usage_data = response.get("usage") or {}
                prompt_tokens = int(usage_data.get("input_tokens", 0))
                completion_tokens = int(usage_data.get("output_tokens", 0))
                total_tokens = int(
                    usage_data.get(
                        "total_tokens", prompt_tokens + completion_tokens
                    )
                )
                return OpenAICompletionsTurnCompleter.Completion(
                    input_conversation=conversation,
                    output_messages=[
                        ChatCompletionMessage(role="assistant", content=text)
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
