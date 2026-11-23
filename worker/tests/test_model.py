from types import SimpleNamespace

import litellm
import pytest

from evals import model as model_module
from evals.model import LiteLLMModel, ModelError, parse_response, retry_delay


def fake_response(content=None, tool_calls=(), prompt_tokens=10, completion_tokens=5):
    calls = [
        SimpleNamespace(
            id=f"call_{i}", function=SimpleNamespace(name=name, arguments=args)
        )
        for i, (name, args) in enumerate(tool_calls)
    ]
    message = SimpleNamespace(content=content, tool_calls=calls or None)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
        ),
    )


async def no_sleep(_):
    pass


def test_parse_text_reply():
    response = parse_response(fake_response("hello"), "ollama/x", latency_ms=12)
    assert response.text == "hello"
    assert response.tool_calls == ()
    assert (response.input_tokens, response.output_tokens) == (10, 5)


def test_parse_tool_calls_keeps_raw_arguments():
    response = parse_response(
        fake_response(tool_calls=[("add", '{"a": 1}'), ("add", "{not json")]),
        "ollama/x",
        0,
    )
    good, bad = response.tool_calls
    assert good.arguments == {"a": 1}
    assert bad.arguments is None
    assert bad.raw_arguments == "{not json"


def test_assistant_message_round_trips_tool_calls():
    response = parse_response(
        fake_response("thinking", [("add", '{"a": 1}')]), "ollama/x", 0
    )
    message = response.to_message()
    assert message["role"] == "assistant"
    assert message["tool_calls"][0]["id"] == "call_0"
    assert message["tool_calls"][0]["function"] == {
        "name": "add",
        "arguments": '{"a": 1}',
    }


def test_cost_uses_known_prices():
    response = parse_response(
        fake_response("hi", prompt_tokens=1_000_000, completion_tokens=0),
        "groq/openai/gpt-oss-120b",
        0,
    )
    assert response.cost_usd == pytest.approx(0.15)


async def test_retries_rate_limits_then_succeeds(monkeypatch):
    calls = []

    async def flaky(**kwargs):
        calls.append(kwargs)
        if len(calls) < 3:
            raise litellm.RateLimitError("slow down", llm_provider="x", model="m")
        return fake_response("ok")

    monkeypatch.setattr(model_module.litellm, "acompletion", flaky)
    response = await LiteLLMModel("ollama/x", sleep=no_sleep).complete([], [], 0.0, 100)
    assert response.text == "ok"
    assert response.retries == 2


async def test_gives_up_after_max_attempts(monkeypatch):
    async def always_down(**kwargs):
        raise litellm.RateLimitError("slow down", llm_provider="x", model="m")

    monkeypatch.setattr(model_module.litellm, "acompletion", always_down)
    with pytest.raises(ModelError, match="after 3 attempts"):
        await LiteLLMModel("ollama/x", max_attempts=3, sleep=no_sleep).complete(
            [], [], 0.0, 100
        )


async def test_bad_request_is_not_retried(monkeypatch):
    calls = []

    async def bad(**kwargs):
        calls.append(1)
        raise litellm.BadRequestError("bad", model="m", llm_provider="x")

    monkeypatch.setattr(model_module.litellm, "acompletion", bad)
    with pytest.raises(ModelError):
        await LiteLLMModel("ollama/x", sleep=no_sleep).complete([], [], 0.0, 100)
    assert len(calls) == 1


async def test_provider_rejected_tool_call_is_returned_not_raised(monkeypatch):
    async def rejects(**kwargs):
        raise litellm.BadRequestError(
            'GroqException - {"error": {"code": "tool_use_failed"}}',
            model="m",
            llm_provider="groq",
        )

    monkeypatch.setattr(model_module.litellm, "acompletion", rejects)
    response = await LiteLLMModel("groq/x", sleep=no_sleep).complete([], [], 0.0, 100)
    assert "tool_use_failed" in response.rejected_tool_call
    assert response.tool_calls == ()


def test_retry_delay_honours_the_provider_hint():
    error = Exception("Rate limit reached. Please try again in 33.77s. Upgrade")
    assert retry_delay(error, 0, 1.0) == pytest.approx(34.77)
    assert retry_delay(Exception("try again in 1m2.5s"), 0, 1.0) == pytest.approx(63.5)
    assert 2 <= retry_delay(Exception("busy"), 1, 2.0) <= 6


async def test_ollama_gets_a_large_context_window(monkeypatch):
    seen = {}

    async def capture(**kwargs):
        seen.update(kwargs)
        return fake_response("ok")

    monkeypatch.setattr(model_module.litellm, "acompletion", capture)
    await LiteLLMModel("ollama_chat/qwen3:8b").complete([], [], 0.0, 100)
    assert seen["num_ctx"] == 32_768
    seen.clear()
    await LiteLLMModel("groq/x").complete([], [], 0.0, 100)
    assert "num_ctx" not in seen


def test_thinking_switch_is_passed_to_ollama_only():
    from evals.model import provider_options

    assert provider_options("ollama_chat/qwen3:8b", False) == {
        "num_ctx": 32_768,
        "think": False,
    }
    assert provider_options("ollama_chat/qwen3:8b") == {"num_ctx": 32_768}
    assert provider_options("anthropic/claude-haiku-5-5", False) == {}
