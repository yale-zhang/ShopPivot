"""Skill 子进程 Runner：无 shell、命令/超时/环境受控。"""
from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


class CliSkillRunner:
    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def run(
        self,
        command: str,
        args: list[str],
        *,
        cwd: str | Path,
        timeout_seconds: int | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        argv = [*shlex.split(command), *args]
        baseline = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"}
        if env:
            baseline.update(env)
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds or self.timeout_seconds,
            env=baseline,
            check=False,
        )
        return CommandResult(
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
        )
