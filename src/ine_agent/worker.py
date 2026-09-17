"""Worker adapters for ine-agent.

The supervisor is a dumb coordinator. A worker knows only how to invoke
one external agent CLI with a prompt and return its exit status plus
captured output. Everything else (project state, decisions, stop
conditions) stays outside this module, so a future worker change never
touches the supervisor loop.
"""

import io
import os
import shutil
import subprocess
import threading


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

    def _capture(self, argv, root):
        """Run `argv` in `root`; return (exit_code, combined stdout+stderr).

        Stdout/stderr are decoded explicitly as UTF-8 (with surrogateescape)
        instead of the locale default (cp1252 on Windows), so agent output
        containing non-CP1252 bytes (e.g. UTF-8 byte 0x90) never raises
        UnicodeDecodeError at the subprocess boundary. surrogateescape does
        not drop data: unmatched bytes are preserved losslessly.
        """
        proc = subprocess.run(
            argv,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
            timeout=None,
        )
        output = proc.stdout
        if proc.stderr:
            output += "\n" + proc.stderr
        return proc.returncode, output

    def _stream(self, argv, root, on_line):
        """Run `argv` in `root`, relaying live output lines to `on_line`.

        Both pipes are drained concurrently (one thread each) so a worker
        writing a lot to stdout and stderr never deadlocks on full pipe
        buffers. Decoding is the same UTF-8/surrogateescape boundary as
        `_capture`, so live lines carry the same bytes as the captured
        result. The combined output is still returned, so streaming never
        loses data.
        """
        proc = subprocess.Popen(
            argv,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out_lines, err_lines = [], []
        lock = threading.Lock()

        def drain(pipe, dst):
            text = io.TextIOWrapper(
                pipe, encoding="utf-8", errors="surrogateescape", newline=""
            )
            with text:
                for line in text:
                    with lock:
                        dst.append(line)
                    if on_line is not None:
                        on_line(line)

        threads = [
            threading.Thread(target=drain, args=(proc.stdout, out_lines)),
            threading.Thread(target=drain, args=(proc.stderr, err_lines)),
        ]
        try:
            for thread in threads:
                thread.start()
            proc.wait()
        except BaseException:
            proc.kill()
            proc.wait()
            raise
        finally:
            for thread in threads:
                thread.join()
        output = "".join(out_lines)
        if err_lines:
            output += "\n" + "".join(err_lines)
        return proc.returncode, output

    def run(self, root, prompt, on_line=None):
        argv = [self._exe(), *self.default_args, prompt]
        try:
            if on_line is None:
                return WorkerResult(*self._capture(argv, root))
            return WorkerResult(*self._stream(argv, root, on_line))
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

    def run(self, root, prompt, on_line=None):
        argv = [self._exe(), *self.default_args, "--dir", str(root), prompt]
        try:
            if on_line is None:
                return WorkerResult(*self._capture(argv, root))
            return WorkerResult(*self._stream(argv, root, on_line))
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

    def run(self, root, prompt, on_line=None):
        exit_code, output = 0, ""
        after = None
        if self.steps:
            step = self.steps.pop(0)
            exit_code, output = step[0], step[1]
            if len(step) > 2:
                after = step[2]
        self.calls.append({"root": root, "prompt": prompt,
                           "exit_code": exit_code, "output": output})
        if on_line is not None and output:
            for line in output.splitlines(True):
                on_line(line)
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