from __future__ import annotations

import json
import os
import shutil
import sqlite3
from pathlib import Path

from evals.config import Config
from evals.harness import HarnessResult, Trace, TrialEnv
from evals.pricing import cost_usd
from evals.sandbox import (
    clean_env,
    make_private_agent_dir,
    run_as_agent,
    run_command,
    stop_processes_with,
)
from evals.task import Task

BASE_TOOLSETS = ("file", "terminal", "code_execution")
OPENAI_COMPATIBLE = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),
}
NATIVE_PROVIDERS = {
    "gemini": ("gemini", "GEMINI_API_KEY"),
    "anthropic": ("anthropic", "ANTHROPIC_API_KEY"),
}


GATEWAY_IDLE_EXIT_S = 5
CONSOLE_KEY_PREFIXES = ("sk-ant-api", "sk-ant-usr", "sk-ant-svc", "sk-ant-admin")


class HermesError(Exception):
    pass


class HermesHarness:
    def __init__(self, binary: str = "hermes", extra_env: dict[str, str] | None = None):
        self.binary = binary
        self.extra_env = extra_env or {}

    async def run(
        self, task: Task, config: Config, env: TrialEnv, trace: Trace
    ) -> HarnessResult:
        answers = []
        for index, prompt in enumerate(task.sessions):
            home = session_home(env.state_dir, config, index)
            try:
                answer, finished = await self.run_session(
                    index, prompt, task, config, env, trace, home
                )
            finally:
                stop_processes_with(home)
            answers.append(answer)
            if not finished:
                trace.add("stop", session=index, reason="max_steps")
                return HarnessResult(tuple(answers), "max_steps")
        return HarnessResult(tuple(answers))

    async def run_session(
        self, index, prompt, task, config, env, trace, home
    ) -> tuple[str, bool]:
        prepare_home(home, config, env.skills_dir)
        provider, model, process_env = provider_settings(config.model, home)
        process_env |= self.extra_env
        usage_path = home / f"usage-{index}.json"
        trace.add("session_start", session=index, prompt=prompt)
        if config.settings.memory:
            before = snapshot(home, env.state_dir / f"snapshot-{index}-before")
            trace.add("memory_read", session=index, content=read_memory(before))
        args = [
            self.binary,
            "-z",
            prompt,
            "-m",
            model,
            "--provider",
            provider,
            "-t",
            ",".join(toolsets(config)),
            "--usage-file",
            str(usage_path),
        ]
        output, exit_code = await run_command(
            args,
            cwd=env.workdir,
            timeout_s=task.timeout_s,
            env=process_env,
            as_agent=True,
        )
        if exit_code == -1:
            raise TimeoutError(
                f"hermes session {index} hit the {task.timeout_s}s timeout"
            )
        after = snapshot(home, env.state_dir / f"snapshot-{index}-after")
        usage = read_json(after / usage_path.name)
        if usage is None:
            raise HermesError(
                f"hermes exited {exit_code} without a usage report: {output[-500:]}"
            )
        record_usage(trace, config.model, usage)
        trace.events.extend(
            transcript_events(after / "state.db", usage.get("session_id"), index)
        )
        if usage.get("failed"):
            raise HermesError(f"hermes run failed (exit {exit_code}): {output[-500:]}")
        return output.strip(), usage.get("completed", True)


def session_home(state_dir: Path, config: Config, index: int) -> Path:
    if config.settings.memory:
        return state_dir / "hermes"
    return state_dir / f"hermes-session-{index}"


def toolsets(config: Config) -> list[str]:
    names = list(BASE_TOOLSETS)
    if config.settings.skills:
        names.append("skills")
    if config.settings.memory:
        names += ["memory", "session_search"]
    return names


def prepare_home(home: Path, config: Config, skills_dir: Path) -> None:
    seed = home.with_name(home.name + "-seed")
    seed.mkdir(parents=True, exist_ok=True)
    for name in config.settings.skills:
        shutil.copytree(skills_dir / name, seed / "skills" / name, dirs_exist_ok=True)
    settings = config.settings
    (seed / "config.yaml").write_text(
        "agent:\n"
        f"  max_turns: {settings.max_steps}\n"
        "memory:\n"
        f"  memory_enabled: {str(settings.memory).lower()}\n"
        "  user_profile_enabled: false\n"
        "gateway:\n"
        f"  unmanaged_idle_exit_seconds: {GATEWAY_IDLE_EXIT_S}\n"
    )
    make_private_agent_dir(home, seed)


def provider_settings(model: str, home: Path) -> tuple[str, str, dict[str, str]]:
    prefix, _, name = model.partition("/")
    env = clean_env(home) | {"HERMES_HOME": str(home)}
    if prefix in NATIVE_PROVIDERS:
        provider, key_var = NATIVE_PROVIDERS[prefix]
        env[key_var] = require_env(key_var)
        if prefix == "anthropic" and not env[key_var].startswith(CONSOLE_KEY_PREFIXES):
            raise HermesError(
                "Hermes treats this Anthropic key as a Claude Code subscription token and bills it "
                "that way. Use a Console API key."
            )
        return provider, name, env
    if prefix in OPENAI_COMPATIBLE:
        base_url, key_var = OPENAI_COMPATIBLE[prefix]
        if prefix == "ollama":
            base_url = (
                os.environ.get("OLLAMA_API_BASE", "http://localhost:11434").rstrip("/")
                + "/v1"
            )
        env["OPENAI_BASE_URL"] = base_url
        env["OPENAI_API_KEY"] = require_env(key_var) if key_var else "ollama"
        return "openai-api", name, env
    raise HermesError(f"no Hermes provider mapping for model {model!r}")


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise HermesError(f"{name} is not set")
    return value


SNAPSHOT_SCRIPT = """
mkdir -p "$2"
for name in state.db state.db-wal state.db-shm; do
  [ -f "$1/$name" ] && cat "$1/$name" > "$2/$name"
done
for usage in "$1"/usage-*.json; do
  [ -f "$usage" ] && cat "$usage" > "$2/$(basename "$usage")"
done
cat "$1"/memories/*.md > "$2/memory.md" 2>/dev/null
true
"""


def snapshot(home: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run_as_agent(
        ["sh", "-c", SNAPSHOT_SCRIPT, "snapshot", str(home), str(dest)], umask="022"
    )
    return dest


def read_memory(snapshot_dir: Path) -> str:
    path = snapshot_dir / "memory.md"
    return path.read_text() if path.exists() else ""


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def record_usage(trace: Trace, model: str, usage: dict) -> None:
    input_tokens = sum(
        usage.get(k) or 0
        for k in ("input_tokens", "cache_read_tokens", "cache_write_tokens")
    )
    output_tokens = usage.get("output_tokens") or 0
    trace.count_usage(
        input_tokens, output_tokens, cost_usd(model, input_tokens, output_tokens)
    )


def transcript_events(db_path: Path, session_id: str | None, index: int) -> list[dict]:
    if not session_id or not db_path.exists():
        return []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "select role, content, tool_calls, tool_call_id, tool_name, reasoning"
            " from messages where session_id = ? order by timestamp, id",
            (session_id,),
        ).fetchall()
    events = []
    step = 0
    for row in rows:
        if row["role"] == "assistant":
            calls = json.loads(row["tool_calls"]) if row["tool_calls"] else []
            events.append(
                {
                    "type": "model_response",
                    "session": index,
                    "step": step,
                    "text": row["content"],
                    "reasoning": row["reasoning"],
                    "tool_calls": [tool_call(c) for c in calls],
                }
            )
            events += [e for c in calls if (e := side_effect(tool_call(c), index))]
            step += 1
        elif row["role"] == "tool":
            events.append(
                {
                    "type": "tool_result",
                    "session": index,
                    "step": max(step - 1, 0),
                    "call_id": row["tool_call_id"],
                    "name": row["tool_name"],
                    "error": tool_error(row["content"]),
                    "result": row["content"],
                }
            )
    return events


def tool_call(call: dict) -> dict:
    function = call.get("function", {})
    raw = function.get("arguments") or ""
    try:
        arguments = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        arguments = None
    return {
        "id": call.get("id"),
        "name": function.get("name"),
        "arguments": arguments,
        "raw_arguments": raw,
    }


def side_effect(call: dict, index: int) -> dict | None:
    args = call["arguments"] or {}
    if call["name"] == "memory":
        return {"type": "memory_write", "session": index, "content": json.dumps(args)}
    if call["name"] == "skill_view":
        return {"type": "skill_load", "session": index, "name": args.get("name")}
    if call["name"] == "session_search":
        return {"type": "memory_read", "session": index, "content": json.dumps(args)}
    return None


def tool_error(content: str | None) -> str | None:
    try:
        data = json.loads(content or "")
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and (data.get("error") or data.get("status") == "error"):
        return "tool_error"
    return None
