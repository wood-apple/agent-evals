from __future__ import annotations

import json
import os
import shutil
import sqlite3
from pathlib import Path

from evals.config import Config
from evals.harness import HarnessResult, Trace, TrialEnv
from evals.pricing import cost_usd
from evals.sandbox import clean_env, run_command
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


class HermesError(Exception):
    pass


class HermesHarness:
    def __init__(self, binary: str = "hermes", extra_env: dict[str, str] | None = None):
        self.binary = binary
        self.extra_env = extra_env or {}

    async def run(
        self, task: Task, config: Config, env: TrialEnv, trace: Trace
    ) -> HarnessResult:
        home = env.state_dir / "hermes"
        prepare_home(home, config, env.skills_dir)
        provider, model, process_env = provider_settings(config.model, home)
        process_env |= self.extra_env
        answers = []
        for index, prompt in enumerate(task.sessions):
            usage_path = home / f"usage-{index}.json"
            trace.add("session_start", session=index, prompt=prompt)
            if config.settings.memory:
                trace.add("memory_read", session=index, content=read_memory(home))
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
                args, cwd=env.workdir, timeout_s=task.timeout_s, env=process_env
            )
            if exit_code == -1:
                raise TimeoutError(
                    f"hermes session {index} hit the {task.timeout_s}s timeout"
                )
            usage = read_json(usage_path)
            if usage is None:
                raise HermesError(
                    f"hermes exited {exit_code} without a usage report: {output[-500:]}"
                )
            record_usage(trace, config.model, usage)
            trace.events.extend(
                transcript_events(home / "state.db", usage.get("session_id"), index)
            )
            if usage.get("failed"):
                raise HermesError(
                    f"hermes run failed (exit {exit_code}): {output[-500:]}"
                )
            answers.append(output.strip())
            if not usage.get("completed", True):
                trace.add("stop", session=index, reason="max_steps")
                return HarnessResult(tuple(answers), "max_steps")
        return HarnessResult(tuple(answers))


def toolsets(config: Config) -> list[str]:
    names = list(BASE_TOOLSETS)
    if config.settings.skills:
        names.append("skills")
    if config.settings.memory:
        names += ["memory", "session_search"]
    return names


def prepare_home(home: Path, config: Config, skills_dir: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    for name in config.settings.skills:
        shutil.copytree(skills_dir / name, home / "skills" / name, dirs_exist_ok=True)
    settings = config.settings
    (home / "config.yaml").write_text(
        "agent:\n"
        f"  max_turns: {settings.max_steps}\n"
        "memory:\n"
        f"  memory_enabled: {str(settings.memory).lower()}\n"
        "  user_profile_enabled: false\n"
    )


def provider_settings(model: str, home: Path) -> tuple[str, str, dict[str, str]]:
    prefix, _, name = model.partition("/")
    env = clean_env(home) | {"HERMES_HOME": str(home)}
    if prefix in NATIVE_PROVIDERS:
        provider, key_var = NATIVE_PROVIDERS[prefix]
        env[key_var] = require_env(key_var)
        if prefix == "anthropic" and not env[key_var].startswith("sk-ant-api"):
            raise HermesError(
                "Hermes treats Anthropic keys that don't start with 'sk-ant-api' as Claude Code "
                "subscription tokens and bills them that way. Use a Console API key (sk-ant-api03-...)."
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


def read_memory(home: Path) -> str:
    memories = home / "memories"
    if not memories.is_dir():
        return ""
    return "\n".join(p.read_text() for p in sorted(memories.glob("*.md")))


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
