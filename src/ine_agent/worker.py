"""Worker adapters for ine-agent.

The supervisor is a dumb coordinator. A worker knows only how to invoke
one external agent CLI with a prompt and return its exit status plus
captured output. Everything else (project state, decisions, stop
conditions) stays outside this module, so a future worker change never
touches the supervisor loop.
"""

import io
import os
import shlex
import shutil
import subprocess
import threading
import time

from . import profiles

#: Captured worker output is bounded. A runaway worker must not be able to
#: flood the run report or the commander's console, and the receipt that the
#: recorder parses lives at the very end of the message, so the head and the
#: tail are kept and the middle is dropped with a marker saying so.
OUTPUT_LIMIT = 20000
OUTPUT_HEAD = 12000

#: The exit code a killed worker reports. 124 is the conventional timeout
#: status, and it is distinguishable from the tool's own failure codes.
TIMEOUT_EXIT_CODE = 124


def bound_output(text, limit=OUTPUT_LIMIT, head=OUTPUT_HEAD):
    """Keep the head and the tail of `text`, drop the middle.

    Truncating the end would be the obvious mistake: the receipt block the
    recorder parses is the last thing a worker writes, so the tail is the
    part that must always survive.
    """
    if text is None or len(text) <= limit:
        return text if text is not None else ""
    tail = limit - head
    dropped = len(text) - limit
    return ("{}\n... [{} characters dropped by the {} character output bound]"
            " ...\n{}".format(text[:head], dropped, limit, text[-tail:]))


def prompt_metrics(prompt):
    """The prompt's own size, for the per-cycle record."""
    prompt = prompt or ""
    return len(prompt), len(prompt.splitlines())


class _TimedOut(Exception):
    """Internal: carries the output collected before the wall-clock bound.

    `subprocess.TimeoutExpired` carries partial output on the capture path
    but not on the streaming one, and both paths must report a timeout the
    same way, so the partial text travels on this instead.
    """

    def __init__(self, output):
        super().__init__("timed out")
        self.output = output


class WorkerResult:
    __slots__ = ("exit_code", "output", "timed_out", "metrics")

    def __init__(self, exit_code, output, timed_out=False, metrics=None):
        self.exit_code = exit_code
        self.output = output
        self.timed_out = timed_out
        #: {prompt_chars, prompt_lines, output_chars, elapsed_seconds,
        #: timed_out} — measured locally, never inferred from a provider
        #: database that may belong to a different tool entirely.
        self.metrics = metrics or {}

    @property
    def ok(self):
        return self.exit_code == 0

    def measure(self, prompt, started):
        """Fill in this invocation's local measurements."""
        chars, lines = prompt_metrics(prompt)
        self.metrics.update({
            "prompt_chars": chars,
            "prompt_lines": lines,
            "output_chars": len(self.output),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "timed_out": self.timed_out,
        })
        return self


class Worker:
    """Base class for an external agent CLI adapter."""

    name = "worker"

    def run(self, root, prompt):
        """Invoke the worker with `prompt`. Returns a WorkerResult."""
        raise NotImplementedError


def _unquote(token):
    """Drop one layer of surrounding quotes left by a non-POSIX split."""
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        return token[1:-1]
    return token


def _split_command(text):
    """Split an env override into argv tokens.

    The override holds a command line, not merely a name: a bridge script
    needs its interpreter (`python bridge.py`), and CreateProcess cannot
    start a `.py` at all. POSIX splitting would eat the backslashes of a
    Windows path, so Windows splits non-POSIX and the quotes that mode
    keeps are stripped afterwards.
    """
    tokens = shlex.split(text, posix=os.name != "nt")
    return [_unquote(token) for token in tokens]


def _override_tokens(env_var):
    """The executable tokens an env override asks for, or None.

    A trailing space or newline in an env var is a Windows staple and must
    never become an argv token of its own, so blank means unset.
    """
    raw = os.environ.get(env_var) if env_var else None
    if raw and raw.strip():
        return raw.strip()
    return None


def effective_command(profile):
    """The argv prefix a profile would start, environment override included.

    Callable without constructing or running anything, so `doctor` and
    `--dry-run` report the command that would really run from the same
    function that runs it. A path passed whole stays whole: on Windows a
    path may contain spaces (`E:\\My Tools\\bridge.cmd`), which no splitter
    can tell from a name plus arguments.
    """
    override = _override_tokens(profile.env_var)
    if not override:
        return [shutil.which(profile.executable) or profile.executable]
    if os.path.isfile(override):
        return [override]
    return _split_command(override)


class CliWorker(Worker):
    """Runs an external CLI non-interactively in the project directory."""

    cmd_name = None              # e.g. "opencode" or "claude"
    env_var = None               # shell env override for the executable
    default_args = ()            # fixed CLI shape, e.g. ("run",)
    stdin_prompt = False         # feed `prompt` via stdin instead of argv
    timeout = None               # seconds before the child is killed; None = no bound

    def _override(self):
        """This worker's env override, whitespace-only treated as unset.

        A trailing space or newline in an env var is a Windows staple and
        must never become an argv token of its own.
        """
        raw = os.environ.get(self.env_var) if self.env_var else None
        if raw and raw.strip():
            return raw.strip()
        return None

    def _exe(self):
        override = self._override()
        if override:
            return override
        return shutil.which(self.cmd_name) or self.cmd_name

    def _command(self):
        """The argv prefix for this worker.

        An env override is a command line, not only a name — it may carry
        arguments (`INE_AGENT_CLAUDE="python bridge.py"`) — so it is split
        into tokens. A bare path is kept whole first: on Windows a path may
        contain spaces (`E:\\My Tools\\bridge.cmd`), which no splitter can
        tell from a name plus arguments. A path passed as an *argument*
        still has to be quoted by hand; `_exe()` stays the single-token
        seam the probe workers patch.
        """
        override = self._override()
        if not override:
            return [self._exe()]
        if os.path.isfile(override):
            return [override]
        return _split_command(override)

    def _shell_for(self, exe):
        """Batch files need the shell: CreateProcess cannot start .cmd/.bat."""
        return os.name == "nt" and str(exe).lower().endswith((".cmd", ".bat"))

    def _start_error(self, exc):
        """Name what was actually attempted, override included.

        A bare "could not start claude" hides the usual cause: the override
        points at something Windows cannot execute — a `.py` handed straight
        to CreateProcess, or a path that does not exist.
        """
        override = self._override()
        if override:
            return "could not start {} ({}={!r}): {}".format(
                self.cmd_name, self.env_var, override, exc)
        return "could not start {}: {}".format(self.cmd_name, exc)

    def _timeout_error(self):
        """A killed worker is reported as a timeout, not as a failure to
        start: the half-finished work is the fact the run report needs. The
        profile/worker name is used, not the resolved executable, so the
        report names the thing the commander configured."""
        return "{} exceeded its {}s timeout and was killed".format(
            self.name, self.timeout)

    def _timed_out_result(self, partial):
        """Exit code 124, whatever output arrived, and `timed_out` set.

        The partial output is the point: a worker killed at the wall-clock
        bound has usually said something worth keeping, and throwing it away
        would leave the run report with a bare timeout and no reason.
        """
        return WorkerResult(
            TIMEOUT_EXIT_CODE,
            bound_output((partial or "") + "\n" + self._timeout_error()),
            timed_out=True)

    def _capture(self, argv, root, stdin_text=None):
        """Run `argv` in `root`; return (exit_code, combined stdout+stderr).

        Stdout/stderr are decoded explicitly as UTF-8 (with surrogateescape)
        instead of the locale default (cp1252 on Windows), so agent output
        containing non-CP1252 bytes (e.g. UTF-8 byte 0x90) never raises
        UnicodeDecodeError at the subprocess boundary. surrogateescape does
        not drop data: unmatched bytes are preserved losslessly.

        `stdin_text`, when given, is written to the child's stdin instead of
        inheriting this process's. Review workers feed the prompt this way so
        the prompt never travels through the OS command line (which on
        Windows can mangle embedded quotes/metacharacters in .cmd shims).

        Output is bounded (`bound_output`). On expiry the child is killed and
        what it had written is returned, so a runaway worker costs one
        timeout rather than a hung run.
        """
        try:
            proc = subprocess.run(
                argv,
                cwd=root,
                capture_output=True,
                input=stdin_text,
                text=True,
                encoding="utf-8",
                errors="surrogateescape",
                timeout=self.timeout,
                shell=self._shell_for(argv[0]),
            )
        except subprocess.TimeoutExpired as expired:
            output = expired.output or ""
            if expired.stderr:
                output += "\n" + (expired.stderr or "")
            raise _TimedOut(output) from None
        output = proc.stdout
        if proc.stderr:
            output += "\n" + proc.stderr
        return proc.returncode, bound_output(output)

    def _stream(self, argv, root, on_line, stdin_text=None):
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
            stdin=subprocess.PIPE if stdin_text is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=self._shell_for(argv[0]),
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
            if stdin_text is not None:
                try:
                    proc.stdin.write(stdin_text.encode("utf-8"))
                finally:
                    proc.stdin.close()
            proc.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            # Kill first, then let the drain threads finish: the lines the
            # worker already wrote are collected on the way out.
            proc.kill()
            proc.wait()
            raise _TimedOut("".join(out_lines) + (
                "\n" + "".join(err_lines) if err_lines else ""))
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
        return proc.returncode, bound_output(output)

    def run(self, root, prompt, on_line=None):
        started = time.monotonic()
        if self.stdin_prompt:
            argv = [*self._command(), *self.default_args]
            kwargs = {"stdin_text": prompt}
        else:
            argv = [*self._command(), *self.default_args, prompt]
            kwargs = {}
        try:
            if on_line is None:
                exit_code, output = self._capture(argv, root, **kwargs)
            else:
                exit_code, output = self._stream(argv, root, on_line, **kwargs)
            return WorkerResult(exit_code, output).measure(prompt, started)
        except _TimedOut as expired:
            return self._timed_out_result(expired.output).measure(
                prompt, started)
        except OSError as exc:
            return WorkerResult(1, self._start_error(exc)).measure(
                prompt, started)
        except subprocess.TimeoutExpired:
            return self._timed_out_result("").measure(prompt, started)


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
        started = time.monotonic()
        argv = [*self._command(), *self.default_args, "--dir", str(root), prompt]
        try:
            if on_line is None:
                exit_code, output = self._capture(argv, root)
            else:
                exit_code, output = self._stream(argv, root, on_line)
        except _TimedOut as expired:
            return self._timed_out_result(expired.output).measure(prompt, started)
        except OSError as exc:
            return WorkerResult(1, self._start_error(exc)).measure(
                prompt, started)
        except subprocess.TimeoutExpired:
            return self._timed_out_result("").measure(prompt, started)
        return WorkerResult(exit_code, output).measure(prompt, started)


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
    stdin_prompt = True


class ProfileWorker(CliWorker):
    """Runs whatever a named profile in `profiles.py` says to run.

    The shape of the invocation is data, not code, so the commander can
    point the loop at another tool by naming a profile instead of editing
    this file. Everything `CliWorker` already handles — the environment
    override seam, the Windows `.cmd` shell bridge, the explicit UTF-8
    decode — is inherited unchanged, so a profile changes *what* runs and
    never *how* output is read.
    """

    def __init__(self, name, root, model=None, options=None):
        self.profile = profiles.resolve(root, name, model=model)
        self.name = self.profile.name
        self.cmd_name = self.profile.executable
        self.env_var = self.profile.env_var
        self.stdin_prompt = self.profile.prompt_transport == "stdin"
        self.timeout = self.profile.timeout_seconds
        self.model_args = list(self.profile.model_args)

    def __repr__(self):
        return "ProfileWorker({!r})".format(self.profile.name)

    @property
    def default_args(self):
        # `profile.argv()` is the whole command including the model args, and
        # the executable is `_command()`'s job, so everything after token 0
        # is the fixed part.
        return tuple(self.profile.argv()[1:])

    def _command(self):
        return effective_command(self.profile)

    def missing_env(self):
        """Declared variables the environment does not actually have.

        The child inherits the environment, so a declared variable is
        already passed through; this only turns "the tool failed with no
        explanation" into "OMNI_API_KEY is not set". The profile holds the
        *name*; the value is never read into the repository, here or
        anywhere else.
        """
        return [name for name in self.profile.env
                if not os.environ.get(name, "").strip()]


class StubWorker(Worker):
    """Test seam: scripted exit codes / output, per-call side effects."""

    name = "stub"

    def __init__(self, steps):
        # steps: list of (exit_code, output [, after(root)]) tuples
        self.steps = list(steps)
        self.calls = []

    def run(self, root, prompt, on_line=None):
        started = time.monotonic()
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
        return WorkerResult(exit_code, output).measure(prompt, started)


def build_worker(name, root, model=None):
    """Factory the supervisor calls with a single profile name.

    Every name that resolves is accepted — built-in or declared in
    `.agent/workers.json` — and an unresolvable one raises, so the loop can
    never silently fall back to a different tool. `root` is the project
    whose config the profile is read from; the supervisor's factory stays
    one-argument, so nothing above this line changes.
    """
    return ProfileWorker(name, root=root, model=model)