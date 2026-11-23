import pytest

from evals.sandbox import Sandbox, ToolError


@pytest.fixture
def sandbox(tmp_path):
    return Sandbox(tmp_path, run_timeout_s=2)


def test_write_then_read(sandbox):
    sandbox.write_file("sub/a.txt", "hi")
    assert sandbox.read_file("sub/a.txt") == "hi"
    assert sandbox.list_files() == "sub/a.txt"


@pytest.mark.parametrize("path", ["../escape.txt", "/etc/passwd", "sub/../../x"])
def test_paths_cannot_escape(sandbox, path):
    with pytest.raises(ToolError, match="escapes"):
        sandbox.write_file(path, "x")


async def test_run_python_runs_in_sandbox(sandbox):
    sandbox.write_file("data.txt", "42")
    output = await sandbox.run_python("print(open('data.txt').read())")
    assert output == "exit code 0\n42\n"


async def test_run_python_does_not_see_api_keys(sandbox, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    output = await sandbox.run_python(
        "import os; print(os.environ.get('GEMINI_API_KEY'))"
    )
    assert "secret" not in output


async def test_run_python_times_out(sandbox):
    output = await sandbox.run_python("while True: pass")
    assert output.startswith("exit code -1\ntimed out")
