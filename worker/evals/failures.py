from __future__ import annotations

from evals.graders import Grade

TOOL_ALIASES = {
    "run_python": {"run_python", "execute_code", "terminal"},
    "read_file": {"read_file", "search_files"},
    "write_file": {"write_file", "patch"},
}
BUDGET_STOPS = {"max_steps", "token_budget"}
CATEGORIES = (
    "step_exhaustion",
    "timeout",
    "hallucinated_tool",
    "bad_tool_args",
    "gave_up_early",
    "wrong_tool",
    "grader_disagreement",
    "wrong_answer",
)


def classify(
    status: str,
    passed: bool | None,
    events: list[dict],
    grades: list[Grade],
    expected_tools: tuple[str, ...],
) -> str | None:
    if status == "error" or passed:
        return None
    if status == "timeout":
        budget_hit = any(
            e["type"] == "stop" and e.get("reason") in BUDGET_STOPS for e in events
        )
        return "step_exhaustion" if budget_hit else "timeout"
    tool_errors = {e.get("error") for e in events if e["type"] == "tool_result"}
    if "unknown_tool" in tool_errors:
        return "hallucinated_tool"
    if tool_errors & {"invalid_arguments", "tool_error"} and not used_after_error(
        events
    ):
        return "bad_tool_args"
    used = {
        c["name"]
        for e in events
        if e["type"] == "model_response"
        for c in e.get("tool_calls", [])
    }
    if expected_tools and not used:
        return "gave_up_early"
    if any(not (TOOL_ALIASES.get(tool, {tool}) & used) for tool in expected_tools):
        return "wrong_tool"
    if len({g.passed for g in grades}) > 1:
        return "grader_disagreement"
    return "wrong_answer"


def used_after_error(events: list[dict]) -> bool:
    results = [e for e in events if e["type"] == "tool_result"]
    last_error = max((i for i, e in enumerate(results) if e.get("error")), default=-1)
    return any(not e.get("error") for e in results[last_error + 1 :])
