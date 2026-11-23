from evals.failures import classify
from evals.graders import Grade


def response(*names):
    return {"type": "model_response", "tool_calls": [{"name": n} for n in names]}


def result(error=None):
    return {"type": "tool_result", "error": error}


FAIL = [Grade("exact_match", False, 0.0, "")]


def test_passing_and_errored_trials_have_no_category():
    assert classify("ok", True, [], [], ()) is None
    assert classify("error", None, [], [], ()) is None


def test_timeouts():
    assert (
        classify("timeout", False, [{"type": "stop", "reason": "max_steps"}], [], ())
        == "step_exhaustion"
    )
    assert classify("timeout", False, [], [], ()) == "timeout"


def test_hallucinated_tool():
    events = [response("delete_all"), result("unknown_tool"), response()]
    assert classify("ok", False, events, FAIL, ()) == "hallucinated_tool"


def test_bad_arguments_only_when_not_recovered():
    events = [response("read_file"), result("tool_error")]
    assert classify("ok", False, events, FAIL, ()) == "bad_tool_args"
    recovered = [*events, response("read_file"), result()]
    assert classify("ok", False, recovered, FAIL, ("read_file",)) == "wrong_answer"


def test_gave_up_and_wrong_tool():
    assert classify("ok", False, [response()], FAIL, ("write_file",)) == "gave_up_early"
    assert (
        classify("ok", False, [response("read_file"), result()], FAIL, ("write_file",))
        == "wrong_tool"
    )


def test_hermes_tool_names_count_as_expected_tools():
    events = [response("execute_code"), result()]
    assert classify("ok", False, events, FAIL, ("run_python",)) == "wrong_answer"


def test_grader_disagreement():
    grades = [Grade("judge", False, 0.25, ""), Grade("structure", True, 1.0, "")]
    assert classify("ok", False, [response()], grades, ()) == "grader_disagreement"
