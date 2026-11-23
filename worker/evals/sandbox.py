from __future__ import annotations

import asyncio
import grp
import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

MAX_OUTPUT_CHARS = 10_000
AGENT_USER = os.environ.get("EVALS_AGENT_USER") or None
TRIALS_DIR = os.environ.get("EVALS_TRIALS_DIR") or None

REAPER = """
import os, signal, sys
marker = sys.argv[1].encode()
if os.path.isdir("/proc"):
    for pid in os.listdir("/proc"):
        if not pid.isdigit() or int(pid) == os.getpid():
            continue
        try:
            environ = open(f"/proc/{pid}/environ", "rb").read()
        except OSError:
            continue
        if marker in environ:
            try:
                os.kill(int(pid), signal.SIGKILL)
                print(pid)
            except OSError:
                pass
"""


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
            [self.python, "-c", code],
            cwd=self.root,
            timeout_s=self.run_timeout_s,
            as_agent=True,
        )
        return f"exit code {exit_code}\n{output}"


async def run_command(
    args: list[str],
    cwd: Path,
    timeout_s: float,
    env: dict[str, str] | None = None,
    as_agent: bool = False,
    agent_umask: str = "002",
) -> tuple[str, int]:
    env = env if env is not None else clean_env(cwd)
    if as_agent:
        args, env = agent_command(args, env, umask=agent_umask)
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout_s)
    except TimeoutError:
        await kill(process)
        return f"timed out after {timeout_s:g}s", -1
    except asyncio.CancelledError:
        await kill(process)
        raise
    return truncate(stdout.decode(errors="replace")), process.returncode


def agent_command(
    args: list[str], env: dict[str, str], user: str | None = None, umask: str = "002"
) -> tuple[list[str], dict[str, str]]:
    user = user or AGENT_USER
    if not user:
        return args, env
    assignments = [f"{key}={value}" for key, value in env.items()]
    wrapped = [
        "sudo",
        "-n",
        "-u",
        user,
        "/usr/bin/env",
        "-i",
        *assignments,
        "/bin/sh",
        "-c",
        f'umask {umask}; exec "$@"',
        "agent",
        *args,
    ]
    return wrapped, {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}


def stop_processes_with(marker: Path) -> list[int]:
    args = ["python3", "-c", REAPER, str(marker)]
    if AGENT_USER:
        args, _ = agent_command(args, {"PATH": "/usr/bin:/bin"})
    try:
        result = subprocess.run(
            args, check=False, capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [int(line) for line in result.stdout.split()]


@contextmanager
def trial_directory(prefix: str = "trial-") -> Iterator[Path]:
    with tempfile.TemporaryDirectory(
        prefix=prefix, dir=TRIALS_DIR, ignore_cleanup_errors=True
    ) as scratch:
        path = Path(scratch)
        share_with_agent(path)
        try:
            yield path
        finally:
            stop_processes_with(path)
            release_to_group(path)


def make_private_agent_dir(path: Path, seed: Path) -> None:
    if not AGENT_USER:
        shutil.copytree(seed, path, dirs_exist_ok=True)
        return
    script = 'mkdir -p "$1" && cp -R "$2"/. "$1"/'
    run_as_agent(["sh", "-c", script, "copy", str(path), str(seed)], umask="022")


def run_as_agent(args: list[str], umask: str = "002") -> None:
    args, env = agent_command(args, {"PATH": "/usr/bin:/bin"}, umask=umask)
    subprocess.run(args, env=env, check=True, capture_output=True, timeout=30)


def release_to_group(path: Path) -> None:
    if AGENT_USER:
        args, env = agent_command(
            ["chmod", "-R", "g+rwX", str(path)], {"PATH": "/usr/bin:/bin"}
        )
        subprocess.run(args, env=env, check=False, capture_output=True, timeout=30)


def share_with_agent(path: Path) -> None:
    if not AGENT_USER:
        return
    os.chown(path, -1, grp.getgrnam(AGENT_USER).gr_gid)
    path.chmod(0o2770)


async def kill(process: asyncio.subprocess.Process) -> None:
    if process.returncode is None:
        process.kill()
        await process.wait()


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
