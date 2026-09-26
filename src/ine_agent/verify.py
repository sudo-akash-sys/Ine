"""Cheap, deterministic verification of a mission's result — no model.

A worker that says `done` is making a claim. This module is the loop's way of
checking that claim with something that is not a second opinion:

    {
      "verify": [
        "python -X utf8 -m pytest -q tests/test_parser.py",
        ["python", "-c", "import ine_parser"]
      ]
    }

in `.agent/workers.json`, or nothing at all — the default, and the only setting
in this repository today.

Four rules shape what it is allowed to be:

- **Never a model.** Every check is a command this process runs itself. A
  verification that cost a request would cost more than the mission it is
  checking, and it would be the same model agreeing with itself.
- **Cheap by construction, and bounded anyway.** The commands are the ones the
  commander wrote, chosen to be fast; each is still given a wall-clock bound
  (`DEFAULT_TIMEOUT_SECONDS`) so a check that hangs costs a timeout and not the
  run, and its output is truncated to a tail. A check that runs for an hour is
  a mission, not a check.
- **Off unless configured.** With no `verify` key the supervisor runs nothing
  extra and its behaviour is byte-for-byte what it was before this module
  existed. Nothing is inferred, discovered or defaulted into existence.
- **A failing check is reported, never argued with.** It does not re-run the
  mission, retry, or ask a model to adjudicate: re-running would meet the same
  deterministic check. The failure is recorded and the run ends non-zero, so a
  green run always means the checks passed.

A check runs only after a mission reports `done`, because that is the only
claim there is to check. `failed`, `needs_commander` and
`missing_prerequisite` are already the loop's own words for "not done".
"""

import os
import shlex
import subprocess
import sys

#: Wall-clock bound for one check. Long enough for a real test file, short
#: enough that a hanging check cannot become the run's problem.
DEFAULT_TIMEOUT_SECONDS = 600

#: How much of a check's output is kept. Enough to see the failure, small
#: enough that a chatty check cannot fill the run report.
TAIL_CHARS = 400


class VerifyError(ValueError):
    """A `verify` list in `.agent/workers.json` cannot be used.

    A ValueError, so the "bad configuration is reported, never silently
    ignored" contract the rest of the config surface already keeps.
    """


def _config_path(root, config_path=None):
    return config_path or os.path.join(
        os.path.abspath(root), ".agent", "workers.json")


def load_checks(root, config_path=None):
    """The verification commands for `root`, or `[]` when none are configured.

    Accepts each entry as a string (split into an argv list) or as a list of
    strings used verbatim, because `["python", "-m", "pytest"]` is
    unambiguous and needs no shell, while the string form is what a person
    writes in JSON. A missing file, or a file with no `verify` key, is the
    empty list and not an error.
    """
    path = _config_path(root, config_path)
    if not os.path.isfile(path):
        return []
    import json
    try:
        with open(path, "r", encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as exc:
        raise VerifyError("cannot read {}: {}".format(path, exc))
    if not isinstance(document, dict):
        raise VerifyError("{} must hold an object, not {}".format(
            path, type(document).__name__))
    if "verify" not in document:
        return []
    entries = document["verify"]
    if not isinstance(entries, list) or not entries:
        raise VerifyError(
            "{}: 'verify' must be a non-empty list of commands, or left out "
            "entirely".format(path))
    checks = []
    for position, entry in enumerate(entries, 1):
        if isinstance(entry, str):
            argv = shlex.split(entry, posix=(os.name != "nt"))
        elif isinstance(entry, list) and entry and all(
                isinstance(part, str) and part for part in entry):
            argv = list(entry)
        else:
            raise VerifyError(
                "{}: verify[{}] must be a string or a non-empty list of "
                "strings".format(path, position))
        if not argv:
            raise VerifyError(
                "{}: verify[{}] is empty".format(path, position))
        checks.append(argv)
    return checks


def _tail(text):
    text = (text or "").strip()
    if len(text) <= TAIL_CHARS:
        return text
    return "..." + text[-TAIL_CHARS:]


def run_checks(root, checks, timeout=DEFAULT_TIMEOUT_SECONDS, runner=None):
    """Run each check in `root`; return one result dict per check, in order.

    Every check runs, even after one fails, so     a single run reports every
    problem rather than only the first. A check that cannot be started at all
    (no such executable) is a failure of that check, not an exception out of
    the supervisor: verification is a report, and a report does not crash the
    thing it is reporting on.

    Checks are launched non-interactively (`stdin=DEVNULL`). A check that
    stops to ask a question would otherwise hold the console and burn the
    whole timeout before the report that would have explained it appeared.

    `runner` is the seam for tests: anything with `run(argv, cwd=..., ...)`
    returning a completed-process shape works.
    """
    results = []
    for argv in checks:
        label = " ".join(argv)
        try:
            if runner is not None:
                completed = runner(argv, cwd=root)
                code = int(getattr(completed, "returncode", 1))
                output = getattr(completed, "stdout", "") or ""
                timed_out = False
            else:
                completed = subprocess.run(
                    argv, cwd=root, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, timeout=timeout,
                    universal_newlines=True, errors="backslashreplace")
                code = int(completed.returncode)
                output = completed.stdout or ""
                timed_out = False
        except subprocess.TimeoutExpired:
            code, output, timed_out = None, "", True
        except (OSError, ValueError) as exc:
            code, output, timed_out = None, str(exc), False
        results.append({
            "command": argv, "label": label, "exit_code": code,
            "timed_out": timed_out, "timeout": timeout, "tail": _tail(output),
            "ok": code == 0 and not timed_out,
        })
    return results


def format_result(result):
    """The one report line for one check, in the run report's `- ` style."""
    if result["timed_out"]:
        return "- verify: TIMED OUT after {}s — {}".format(
            result.get("timeout", DEFAULT_TIMEOUT_SECONDS), result["label"])
    status = "ok" if result["ok"] else "FAILED (exit {})".format(
        result["exit_code"])
    line = "- verify: {} — {}".format(status, result["label"])
    if result["tail"] and not result["ok"]:
        line += "\n    " + result["tail"].replace("\n", "\n    ")
    return line


if __name__ == "__main__":  # pragma: no cover - a manual probe
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    for check in run_checks(root, load_checks(root)):
        print(format_result(check))
