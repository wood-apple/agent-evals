from __future__ import annotations

from collections.abc import Callable

from evals.config import Config
from evals.harness import HarnessResult, Trace, TrialEnv
from evals.model import LiteLLMModel, Model, ToolCall
from evals.sandbox import Sandbox, ToolError
from evals.skills import Skill, load_skills
from evals.task import Task

SYSTEM_PROMPT = """\
You are an autonomous agent working in a sandbox directory that contains the user's files.
Use the tools to inspect and change files and to run Python. Check your work when you can.
When you are finished, reply with your final answer and do not call any more tools."""

DEFAULT_TOOLS = ("list_files", "read_file", "write_file", "run_python")


def function(tool_name: str, description: str, **properties: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    key: {"type": "string", "description": text}
                    for key, text in properties.items()
                },
                "required": list(properties),
            },
        },
    }


TOOL_SPECS = {
    "list_files": function("list_files", "List every file in the sandbox."),
    "read_file": function(
        "read_file", "Read a text file.", path="Path relative to the sandbox"
    ),
    "write_file": function(
        "write_file",
        "Create or overwrite a text file.",
        path="Path relative to the sandbox",
        content="Full new file content",
    ),
    "run_python": function(
        "run_python",
        "Run a Python 3 program in the sandbox directory and return its output.",
        code="Python source code",
    ),
    "read_skill": function(
        "read_skill", "Load the full instructions of a skill.", name="Skill name"
    ),
    "remember": function(
        "remember",
        "Save a note to long-term memory. Notes are shown to you in future sessions.",
        note="What to remember",
    ),
}


class BaselineHarness:
    def __init__(self, model_factory: Callable[[str], Model] = LiteLLMModel):
        self.model_factory = model_factory

    async def run(
        self, task: Task, config: Config, env: TrialEnv, trace: Trace
    ) -> HarnessResult:
        session = Session(
            model=self.model_factory(config.model),
            config=config,
            sandbox=Sandbox(env.workdir),
            skills=load_skills(env.skills_dir, config.settings.skills),
            memory_path=env.state_dir / "MEMORY.md" if config.settings.memory else None,
            trace=trace,
        )
        answers = []
        for index, prompt in enumerate(task.sessions):
            answer, stop_reason = await session.run(index, prompt)
            answers.append(answer)
            if stop_reason != "done":
                return HarnessResult(tuple(answers), stop_reason)
        return HarnessResult(tuple(answers))


class Session:
    def __init__(self, model, config, sandbox, skills, memory_path, trace):
        self.model = model
        self.settings = config.settings
        self.sandbox = sandbox
        self.skills: dict[str, Skill] = skills
        self.memory_path = memory_path
        self.trace = trace
        self.tools = [TOOL_SPECS[name] for name in self.tool_names()]

    def tool_names(self) -> list[str]:
        names = list(self.settings.tools or DEFAULT_TOOLS)
        if self.skills:
            names.append("read_skill")
        if self.memory_path:
            names.append("remember")
        return names

    async def run(self, index: int, prompt: str) -> tuple[str, str]:
        system = self.system_prompt(index)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        self.trace.add("session_start", session=index, system=system, prompt=prompt)
        for step in range(self.settings.max_steps):
            if self.trace.total_tokens >= self.settings.token_budget:
                self.trace.add("stop", session=index, reason="token_budget")
                return "", "token_budget"
            response = await self.model.complete(
                messages,
                self.tools,
                self.settings.temperature,
                self.settings.max_tokens,
            )
            self.trace.count_usage(
                response.input_tokens, response.output_tokens, response.cost_usd
            )
            self.trace.add(
                "model_response",
                session=index,
                step=step,
                text=response.text,
                tool_calls=[
                    {
                        "id": c.id,
                        "name": c.name,
                        "arguments": c.arguments,
                        "raw_arguments": c.raw_arguments,
                    }
                    for c in response.tool_calls
                ],
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost_usd=response.cost_usd,
                latency_ms=response.latency_ms,
                retries=response.retries,
            )
            messages.append(response.to_message())
            if not response.tool_calls:
                return response.text or "", "done"
            for call in response.tool_calls:
                result = await self.call_tool(index, step, call)
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": result}
                )
        self.trace.add("stop", session=index, reason="max_steps")
        return "", "max_steps"

    def system_prompt(self, index: int) -> str:
        parts = [SYSTEM_PROMPT]
        if self.skills:
            listing = "\n".join(
                f"- {s.name}: {s.description}" for s in self.skills.values()
            )
            parts.append(
                f"Skills you can load with read_skill when relevant:\n{listing}"
            )
        if self.memory_path:
            notes = self.memory_path.read_text() if self.memory_path.exists() else ""
            self.trace.add("memory_read", session=index, content=notes)
            parts.append(
                "Use the remember tool to save facts that may matter in later sessions.\n"
                f"Your memory from earlier sessions:\n{notes or '(empty)'}"
            )
        return "\n\n".join(parts)

    async def call_tool(self, index: int, step: int, call: ToolCall) -> str:
        allowed = {spec["function"]["name"] for spec in self.tools}
        if call.name not in allowed:
            error, result = (
                "unknown_tool",
                f"error: there is no tool named {call.name!r}",
            )
        elif call.arguments is None:
            error, result = (
                "invalid_arguments",
                "error: arguments are not a valid JSON object",
            )
        else:
            try:
                result, error = (
                    await self.execute(index, call.name, call.arguments),
                    None,
                )
            except (ToolError, KeyError, TypeError) as e:
                error, result = "tool_error", f"error: {describe(e)}"
        self.trace.add(
            "tool_result",
            session=index,
            step=step,
            call_id=call.id,
            name=call.name,
            error=error,
            result=result,
        )
        return result

    async def execute(self, index: int, name: str, args: dict) -> str:
        match name:
            case "list_files":
                return self.sandbox.list_files()
            case "read_file":
                return self.sandbox.read_file(args["path"])
            case "write_file":
                return self.sandbox.write_file(args["path"], args["content"])
            case "run_python":
                return await self.sandbox.run_python(args["code"])
            case "read_skill":
                skill = self.skills.get(args["name"])
                if skill is None:
                    raise ToolError(f"unknown skill {args['name']!r}")
                self.trace.add("skill_load", session=index, name=skill.name)
                return skill.body
            case "remember":
                note = args["note"].strip()
                with self.memory_path.open("a") as f:
                    f.write(f"- {note}\n")
                self.trace.add("memory_write", session=index, content=note)
                return "saved"
        raise ToolError(f"unknown tool {name!r}")


def describe(error: Exception) -> str:
    if isinstance(error, KeyError):
        return f"missing argument {error.args[0]!r}"
    return str(error)
