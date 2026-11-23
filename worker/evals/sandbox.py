from __future__ import annotations

import asyncio
import os
from pathlib import Path

MAX_OUTPUT_CHARS = 10_000


class ToolError(Exception):
    pass


class Sandbox:
    def __init__(
        self, root: Path, python: str = "python3", run_timeout_s: float = 30.0
    ):
        self.root = root.resolve()
        self.python = python
        self.run_timeout_s = run_timeout_s

    def resolve(self, path: str) -> Path:
        target = (self.root / path).resolve()
        if not target.is_relative_to(self.root):
            raise ToolError(f"path escapes the sandbox: {path}")
        return target

    def list_files(self) -> str:
        files = sorted(
            p.relative_to(self.root).as_posix()
            for p in self.root.rglob("*")
            if p.is_file()
        )
        return "\n".join(files) or "(no files)"

    def read_file(self, path: str) -> str:
        target = self.resolve(path)
        if not target.is_file():
            raise ToolError(f"no such file: {path}")
        return truncate(target.read_text(errors="replace"))

    def write_file(self, path: str, content: str) -> str:
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"wrote {len(content)} characters to {path}"

    async def run_python(self, code: str) -> str:
        output, exit_code = await run_command(
            [self.python, "-c", code], cwd=self.root, timeout_s=self.run_timeout_s
        )
        return f"exit code {exit_code}\n{output}"


async def run_command(args: list[str], cwd: Path, timeout_s: float) -> tuple[str, int]:
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        env=clean_env(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout_s)
    except TimeoutError:
        process.kill()
        await process.wait()
        return f"timed out after {timeout_s:g}s", -1
    return truncate(stdout.decode(errors="replace")), process.returncode


def clean_env(home: Path) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }


def truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return (
        text[:MAX_OUTPUT_CHARS]
        + f"\n... truncated {len(text) - MAX_OUTPUT_CHARS} characters"
    )
