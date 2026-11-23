import dataclasses

import pytest
from fakes import ScriptedModel, call, reply

from evals.config import Config, Settings
from evals.harness import Trace, TrialEnv
from evals.harnesses.baseline import BaselineHarness
from evals.task import Task


def make_task(*prompts):
    return Task(
        id="t", title="t", category="c", sessions=prompts or ("do it",), graders=()
    )


@pytest.fixture
def env(tmp_path):
    (tmp_path / "work").mkdir()
    (tmp_path / "state").mkdir()
    skill = tmp_path / "skills" / "acme"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: acme\ndescription: ACME rules\n---\nIDs start with INV."
    )
    return TrialEnv(
        workdir=tmp_path / "work",
        state_dir=tmp_path / "state",
        skills_dir=tmp_path / "skills",
    )


async def run(model, env, task=None, **settings):
    trace = Trace()
    config = Config(harness="baseline", model="fake", settings=Settings(**settings))
    result = await BaselineHarness(lambda _: model).run(
        task or make_task(), config, env, trace
    )
    return result, trace


def types(trace):
    return [e["type"] for e in trace.events]


async def test_tool_loop_writes_file_and_answers(env):
    model = ScriptedModel(
        reply("", call("write_file", path="out.txt", content="hi")), reply("done")
    )
    result, trace = await run(model, env)
    assert result.final_answer == "done"
    assert (env.workdir / "out.txt").read_text() == "hi"
    assert types(trace) == [
        "session_start",
        "model_response",
        "tool_result",
        "model_response",
    ]
    assert trace.input_tokens == 20
    assert model.requests[1][-1] == {
        "role": "tool",
        "tool_call_id": model.requests[1][-2]["tool_calls"][0]["id"],
        "content": "wrote 2 characters to out.txt",
    }


async def test_unknown_tool_and_bad_arguments_are_reported_to_the_model(env):
    model = ScriptedModel(
        reply("", call("delete_everything"), call("read_file", wrong="x")),
        reply("sorry"),
    )
    _, trace = await run(model, env)
    errors = [e["error"] for e in trace.events if e["type"] == "tool_result"]
    assert errors == ["unknown_tool", "tool_error"]
    assert model.requests[1][-1]["content"] == "error: missing argument 'path'"


async def test_tools_setting_limits_available_tools(env):
    model = ScriptedModel(reply("", call("run_python", code="print(1)")), reply("ok"))
    _, trace = await run(model, env, tools=("read_file",))
    assert trace.events[2]["error"] == "unknown_tool"


async def test_step_limit_stops_the_loop(env):
    model = ScriptedModel(*[reply("", call("list_files")) for _ in range(5)])
    result, trace = await run(model, env, max_steps=3)
    assert result.stop_reason == "max_steps"
    assert trace.events[-1] == {
        "type": "stop",
        "t_ms": trace.events[-1]["t_ms"],
        "session": 0,
        "reason": "max_steps",
    }


async def test_token_budget_stops_the_loop(env):
    model = ScriptedModel(*[reply("", call("list_files"), tokens=60) for _ in range(5)])
    result, _ = await run(model, env, token_budget=200)
    assert result.stop_reason == "token_budget"
    assert len(model.requests) == 2


async def test_memory_carries_over_between_sessions(env):
    model = ScriptedModel(
        reply("", call("remember", note="host is db-7")),
        reply("noted"),
        reply("db-7"),
    )
    result, trace = await run(
        model, env, task=make_task("remember this", "what host?"), memory=True
    )
    assert result.answers == ("noted", "db-7")
    assert "host is db-7" in model.requests[2][0]["content"]
    assert "memory_write" in types(trace)


async def test_without_memory_sessions_start_fresh(env):
    model = ScriptedModel(
        reply("", call("remember", note="x")), reply("ok"), reply("?")
    )
    _, trace = await run(model, env, task=make_task("a", "b"))
    assert trace.events[2]["error"] == "unknown_tool"
    assert "memory" not in model.requests[2][0]["content"].lower()


async def test_skills_are_listed_and_loaded_on_demand(env):
    model = ScriptedModel(reply("", call("read_skill", name="acme")), reply("INV-1"))
    _, trace = await run(model, env, skills=("acme",))
    assert "acme: ACME rules" in model.requests[0][0]["content"]
    assert "IDs start with INV." not in model.requests[0][0]["content"]
    assert model.requests[1][-1]["content"] == "IDs start with INV."
    assert "skill_load" in types(trace)


async def test_rejected_tool_call_is_fed_back_as_an_agent_error(env):
    model = ScriptedModel(
        dataclasses.replace(
            reply(""), rejected_tool_call="tool_use_failed: missing 'path'"
        ),
        reply("done"),
    )
    result, trace = await run(model, env)
    assert result.final_answer == "done"
    assert trace.events[2]["error"] == "invalid_arguments"
    assert model.requests[1][-1]["role"] == "user"
    assert "rejected" in model.requests[1][-1]["content"]


async def test_thinking_setting_reaches_the_model(env):
    model = ScriptedModel(reply("done"))
    await run(model, env, thinking=False)
    assert model.thinking is False
