from pathlib import Path

import pytest

from evals.config import Config, Settings
from evals.harness import Trace, TrialEnv
from evals.harnesses.hermes import (
    HermesError,
    HermesHarness,
    provider_settings,
    toolsets,
)
from evals.task import Task

FAKE = str(Path(__file__).parent / "data" / "fake_hermes.py")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    for name in ("work", "state", "skills/acme"):
        (tmp_path / name).mkdir(parents=True)
    (tmp_path / "skills/acme/SKILL.md").write_text("---\nname: acme\n---\nbody")
    return TrialEnv(tmp_path / "work", tmp_path / "state", tmp_path / "skills")


async def run(env, *sessions, timeout_s=30, mode="ok", **settings):
    task = Task(
        id="t",
        title="t",
        category="c",
        sessions=sessions or ("hi",),
        graders=(),
        timeout_s=timeout_s,
    )
    config = Config("hermes", "gemini/gemini-x", Settings(**settings))
    trace = Trace()
    result = await HermesHarness(FAKE, {"FAKE_HERMES_MODE": mode}).run(
        task, config, env, trace
    )
    return result, trace


async def test_runs_each_session_and_reads_the_transcript(env):
    result, trace = await run(env, "first", "second", memory=True)
    assert result.answers == ("ANSWER: 42", "ANSWER: 42")
    types = [e["type"] for e in trace.events if e["session"] == 1]
    assert types == [
        "session_start",
        "memory_read",
        "model_response",
        "memory_write",
        "tool_result",
        "model_response",
    ]
    assert trace.events[1]["content"] == ""
    assert (
        "first" in [e for e in trace.events if e["type"] == "memory_read"][1]["content"]
    )
    assert (trace.input_tokens, trace.output_tokens) == (300, 20)


async def test_trial_gets_isolated_home_with_config_and_skills(env):
    await run(env, skills=("acme",), max_steps=7)
    home = env.state_dir / "hermes-session-0"
    assert (home / "skills/acme/SKILL.md").exists()
    config = (home / "config.yaml").read_text()
    assert "max_turns: 7" in config
    assert "memory_enabled: false" in config


def test_memory_off_also_removes_session_search():
    assert "session_search" not in toolsets(Config("hermes", "m", Settings()))
    assert {"memory", "session_search"} <= set(
        toolsets(Config("hermes", "m", Settings(memory=True)))
    )


def test_provider_env_does_not_leak_other_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    provider, model, env = provider_settings("groq/openai/gpt-oss-120b", tmp_path)
    assert (provider, model) == ("openai-api", "openai/gpt-oss-120b")
    assert env["OPENAI_API_KEY"] == "groq-key"
    assert "gemini-key" not in env.values()


def test_unknown_provider_is_rejected(tmp_path):
    with pytest.raises(HermesError, match="no Hermes provider"):
        provider_settings("mystery/model", tmp_path)


async def test_turn_limit_is_reported(env):
    result, _ = await run(env, "a", "b", mode="turns")
    assert result.stop_reason == "max_steps"
    assert len(result.answers) == 1


async def test_provider_failure_is_an_error(env):
    with pytest.raises(HermesError, match="failed"):
        await run(env, mode="fail")


async def test_crash_without_usage_is_an_error(env):
    with pytest.raises(HermesError, match="without a usage report"):
        await run(env, mode="crash")


async def test_hang_becomes_a_timeout(env):
    with pytest.raises(TimeoutError):
        await run(env, timeout_s=1, mode="hang")


def test_non_console_anthropic_keys_are_rejected_up_front(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-oat01-subscription-token")
    with pytest.raises(HermesError, match="Console API key"):
        provider_settings("anthropic/claude-haiku-5-5", tmp_path)
    for key in ("sk-ant-api03-console-key", "sk-ant-usr-console-key"):
        monkeypatch.setenv("ANTHROPIC_API_KEY", key)
        assert (
            provider_settings("anthropic/claude-haiku-5-5", tmp_path)[0] == "anthropic"
        )


async def test_gateway_idle_exit_is_short(env):
    await run(env)
    assert (
        "unmanaged_idle_exit_seconds: 5"
        in (env.state_dir / "hermes-session-0" / "config.yaml").read_text()
    )


@pytest.mark.skipif(not Path("/proc").is_dir(), reason="needs Linux /proc")
def test_leftover_processes_of_a_trial_are_stopped(tmp_path):
    import os
    import subprocess

    from evals.sandbox import stop_processes_with

    mine = subprocess.Popen(
        ["sleep", "60"], env={**os.environ, "HERMES_HOME": str(tmp_path)}
    )
    other = subprocess.Popen(
        ["sleep", "60"], env={**os.environ, "HERMES_HOME": str(tmp_path / "other")}
    )
    try:
        assert stop_processes_with(tmp_path) == [mine.pid]
        assert mine.wait(timeout=5) == -9
        assert other.poll() is None
    finally:
        other.kill()


async def test_memory_off_gives_every_session_a_fresh_home(env):
    await run(env, "first", "second")
    first, second = (
        env.state_dir / "hermes-session-0",
        env.state_dir / "hermes-session-1",
    )
    assert (first / "memories" / "MEMORY.md").read_text() == "first\n"
    assert (second / "memories" / "MEMORY.md").read_text() == "second\n"


async def test_memory_on_shares_one_home_across_sessions(env):
    await run(env, "first", "second", memory=True)
    assert (
        env.state_dir / "hermes" / "memories" / "MEMORY.md"
    ).read_text() == "first\nsecond\n"
