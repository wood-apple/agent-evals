from __future__ import annotations

import json

from evals.model import ModelResponse, ToolCall


def call(tool_name: str, **arguments) -> ToolCall:
    raw = json.dumps(arguments)
    return ToolCall(
        id=f"{tool_name}-{abs(hash(raw)) % 10_000}",
        name=tool_name,
        arguments=arguments,
        raw_arguments=raw,
    )


def reply(text: str = "", *tool_calls: ToolCall, tokens: int = 10) -> ModelResponse:
    return ModelResponse(
        text=text,
        tool_calls=tuple(tool_calls),
        input_tokens=tokens,
        output_tokens=tokens,
        cost_usd=0.001,
    )


class ScriptedModel:
    def __init__(self, *responses: ModelResponse):
        self.responses = list(responses)
        self.requests: list[list[dict]] = []

    async def complete(self, messages, tools, temperature, max_tokens):
        self.requests.append([dict(m) for m in messages])
        if not self.responses:
            return reply("out of script")
        return self.responses.pop(0)
