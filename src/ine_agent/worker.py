"""Worker adapters for ine-agent.

The supervisor is a dumb coordinator. A worker knows only how to invoke
one external agent CLI with a prompt and return its exit status plus
captured output. Everything else (project state, decisions, stop
conditions) stays outside this module, so a future worker change never
touches the supervisor loop.
"""

import os
import shutil
import subprocess


class WorkerResult:
    __slots__ = ("exit_code", "output")

    def __init__(self, exit_code, output):
        self.exit_code = exit_code
        self.output = output

    @property
    def ok(self):
        return self.exit_code == 0


class Worker:
    """Base class for an external agent CLI adapter."""

    name = "worker"

    def run(self, root, prompt):
        """Invoke the worker with `prompt`. Returns a WorkerResult."""
        raise NotImplementedError


def _resolve(exe):
    """Resolve an executable name, honoring an explicit env override first."""
    if exe:
        return exe
    return None


class CliWorker(Worker):
    """Runs an external CLI non-interactively in the project directory."""

    cmd_name = None              # e.g. "opencode" or "claude"
    env_var = None               # shell env override for the executable
    default_args = ()            # fixed CLI shape, e.g. ("run",)

    def _exe(self):
        override = os.environ.get(self.env_var) if self.env_var else None
        if override:
            return override
        return shutil.which(self.cmd_name) or self.cmd_name

    def run(self, root, prompt):
        argv = [self._exe(), *self.default_args, prompt]
        try:
            proc = subprocess.run(
                argv,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=None,
            )
            output = proc.stdout
            if proc.stderr:
                output += "\n" + proc.stderr
            return WorkerResult(proc.returncode, output)
        except OSError as exc:
            return WorkerResult(1, "could not start {}: {}".format(self.cmd_name, exc))


class OpenCodeWorker(CliWorker):
    """The default implementation worker: `opencode run <prompt>`.

    `--pure` disables external plugins for a more reproducible build;
    `--dir` pins the project root so module discovery is explicit.
    """

    name = "opencode"
    cmd_name = "opencode"
    env_var = "INE_AGENT_OPENCODE"
    default_args = ("run", "--pure")

    def run(self, root, prompt):
        argv = [self._exe(), *self.default_args, "--dir", str(root), prompt]
        try:
            proc = subprocess.run(
                argv,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=None,
            )
            output = proc.stdout
            if proc.stderr:
                output += "\n" + proc.stderr
            return WorkerResult(proc.returncode, output)
        except OSError as exc:
            return WorkerResult(1, "could not start opencode: {}".format(exc))


class ClaudeReviewWorker(CliWorker):
    """Optional review pre-pass: `claude -p <prompt>` (print mode, exits).

    Used only when the plan's first EXECUTABLE task is explicitly tagged
    `CLAUDE_REVIEW`. It reviews/decomposes; implementation still goes
    through the OpenCode worker. It never rewrites semantics or overrides
    DECISIONS.md on its own.
    """

    name = "claude"
    cmd_name = "claude"
    env_var = "INE_AGENT_CLAUDE"
    default_args = ("-p",)


class StubWorker(Worker):
    """Test seam: scripted exit codes / output, per-call side effects."""

    name = "stub"

    def __init__(self, steps):
        # steps: list of (exit_code, output [, after(root)]) tuples
        self.steps = list(steps)
        self.calls = []

    def run(self, root, prompt):
        exit_code, output = 0, ""
        after = None
        if self.steps:
            step = self.steps.pop(0)
            exit_code, output = step[0], step[1]
            if len(step) > 2:
                after = step[2]
        self.calls.append({"root": root, "prompt": prompt,
                           "exit_code": exit_code, "output": output})
        if after is not None:
            after(root)
        return WorkerResult(exit_code, output)


def build_worker(name):
    """Factory for the built-in worker CLIs. Unknown names raise ValueError
    so the loop never silently falls back to a different worker."""
    if name == "opencode":
        return OpenCodeWorker()
    if name == "claude":
        return ClaudeReviewWorker()
    raise ValueError("unknown worker '{}'".format(name))