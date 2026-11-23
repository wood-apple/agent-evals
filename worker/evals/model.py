from __future__ import annotations

import asyncio
import json
import random
import time
from dataclasses import dataclass, field
from typing import Protocol

import litellm
import openai

from evals.pricing import cost_usd

litellm.suppress_debug_info = True
litellm.drop_params = True

RETRYABLE = (
    litellm.RateLimitError,
    litellm.APIConnectionError,
    litellm.Timeout,
    litellm.InternalServerError,
    litellm.ServiceUnavailableError,
)


class ModelError(Exception):
    pass


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict | None
    raw_arguments: str = ""

    def to_message(self) -> dict:
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": self.raw_arguments or "{}"},
        }


@dataclass(frozen=True)
class ModelResponse:
    text: str | None
    tool_calls: tuple[ToolCall, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    retries: int = 0
    rejected_tool_call: str | None = None

    def to_message(self) -> dict:
        message = {"role": "assistant", "content": self.text}
        if self.tool_calls:
            message["tool_calls"] = [call.to_message() for call in self.tool_calls]
        return message


class Model(Protocol):
    name: str

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> ModelResponse: ...


@dataclass
class LiteLLMModel:
    name: str
    max_attempts: int = 5
    base_delay_s: float = 2.0
    request_timeout_s: float = 120.0
    sleep: object = field(default=asyncio.sleep, repr=False)

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> ModelResponse:
        for attempt in range(self.max_attempts):
            started = time.monotonic()
            try:
                response = await litellm.acompletion(
                    model=self.name,
                    messages=messages,
                    tools=tools or None,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=self.request_timeout_s,
                )
            except RETRYABLE as e:
                if attempt == self.max_attempts - 1:
                    raise ModelError(
                        f"{type(e).__name__} after {attempt + 1} attempts: {e}"
                    ) from e
                await self.sleep(backoff(attempt, self.base_delay_s))
                continue
            except litellm.BadRequestError as e:
                if "tool_use_failed" in str(e):
                    return ModelResponse(
                        text=None, rejected_tool_call=str(e), retries=attempt
                    )
                raise ModelError(f"{type(e).__name__}: {e}") from e
            except openai.OpenAIError as e:
                raise ModelError(f"{type(e).__name__}: {e}") from e
            latency_ms = int((time.monotonic() - started) * 1000)
            return parse_response(response, self.name, latency_ms, retries=attempt)
        raise AssertionError("unreachable")


def backoff(attempt: int, base_delay_s: float) -> float:
    return base_delay_s * 2**attempt * random.uniform(0.5, 1.5)


def parse_response(
    response, model: str, latency_ms: int, retries: int = 0
) -> ModelResponse:
    message = response.choices[0].message
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0
    return ModelResponse(
        text=message.content,
        tool_calls=tuple(parse_tool_call(call) for call in message.tool_calls or ()),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd(model, input_tokens, output_tokens),
        latency_ms=latency_ms,
        retries=retries,
    )


def parse_tool_call(call) -> ToolCall:
    raw = call.function.arguments or ""
    try:
        arguments = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        arguments = None
    if not isinstance(arguments, dict):
        arguments = None
    return ToolCall(
        id=call.id, name=call.function.name, arguments=arguments, raw_arguments=raw
    )
