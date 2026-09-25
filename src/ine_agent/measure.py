"""Re-measure the autonomous loop from its own durable records.

The commander's question after a change to the loop is "did it actually get
better?" — and the answer has to be a number, not an impression. The usage
telemetry already written into `.agent/RUN_REPORTS.md` records, per run, how
many worker cycles ran, how each ended, whether anything was completed, and
what the provider charged in requests and tokens; this module reads just
that, plus the attempt ledger, and prints per-run rows and an aggregate.

Read-only: it never writes to the project and never launches a worker.

    python -m ine_agent.measure [--root .]

The headline number is completions per 1,000 requests, because that is what
"the same output, more cheaply" means in practice — a run that spends a
hundred requests and completes nothing is the failure mode this exists to
make visible.

Two honest limits of what it reads. Cycles, completions and parked counts
come from the supervisor's own record and are always complete; the request
and token numbers only exist when the worker reports into the OpenCode
database, so a run driven by `--worker claude` shows zero usage rather than
a guess. And a run with no `- exit:` line was interrupted (killed or still
running) rather than ended, which is why its exit prints as `-`.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from . import state
    from .supervisor import ATTEMPTS_NAME, read_attempts
except ImportError:  # running as a plain script
    from ine_agent import state
    from ine_agent.supervisor import ATTEMPTS_NAME, read_attempts


_RUN_RE = re.compile(r"^### run (.+?) \(pid (\d+)\)$")
_EXIT_RE = re.compile(r"^- exit: (-?\d+)$")
_MISSION_RE = re.compile(r"^- mission \[cycle (\d+)\]:")
_CYCLE_MARKER_RE = re.compile(r"^- \[cycle (\d+)\] (.+)$")
_USAGE_RE = re.compile(
    r"^\+(\d+) requests, \+([\d,]+) in / \+([\d,]+) out tokens")


def _number(text):
    return int(text.replace(",", ""))


def parse_report(text):
    """Per-run rows read out of a RUN_REPORTS.md body.

    Every row is what one run did: cycles, how each cycle ended, and the
    provider usage between the run's start and end snapshots. A malformed or
    partial report yields fewer rows, never an exception — this reads a log,
    and a log is allowed to be incomplete.
    """
    runs = []
    run = None
    for line in text.splitlines():
        match = _RUN_RE.match(line)
        if match:
            run = {
                "started": match.group(1), "pid": int(match.group(2)),
                "cycles": 0, "completed": 0, "blocked": 0, "deferred": 0,
                "parked": 0, "requests": 0, "tokens_in": 0, "tokens_out": 0,
                "exit": None,
            }
            runs.append(run)
            continue
        if run is None:
            continue
        if _MISSION_RE.match(line):
            run["cycles"] += 1
            continue
        marker = _CYCLE_MARKER_RE.match(line)
        if marker:
            what = marker.group(2)
            if what.startswith("DONE"):
                run["completed"] += 1
            elif what.startswith("BLOCKED"):
                run["blocked"] += 1
            elif what.startswith("PARKED"):
                run["parked"] += 1
            elif what.startswith(("RETRIES EXHAUSTED", "DEFERRED")):
                run["deferred"] += 1
            continue
        exit_match = _EXIT_RE.match(line)
        if exit_match:
            run["exit"] = int(exit_match.group(1))
            continue
        if line.startswith("- usage delta (run): "):
            usage = _USAGE_RE.match(line.split(": ", 1)[1])
            if usage:
                run["requests"] = _number(usage.group(1))
                run["tokens_in"] = _number(usage.group(2))
                run["tokens_out"] = _number(usage.group(3))
            continue
    return runs


def summarize(root):
    """`(per-run rows, productively-observed totals)` for `root`."""
    path = state.run_report_path(root)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            runs = parse_report(handle.read())
    except OSError:
        runs = []
    parked = len(read_attempts(root))
    totals = {
        "runs": len(runs),
        "cycles": sum(run["cycles"] for run in runs),
        "completed": sum(run["completed"] for run in runs),
        "blocked": sum(run["blocked"] for run in runs),
        "deferred": sum(run["deferred"] for run in runs),
        "parked": sum(run["parked"] for run in runs),
        "barren": sum(1 for run in runs
                      if run["cycles"] and not run["completed"]),
        "requests": sum(run["requests"] for run in runs),
        "tokens_in": sum(run["tokens_in"] for run in runs),
        "tokens_out": sum(run["tokens_out"] for run in runs),
        "parked_missions": parked,
    }
    return runs, totals


def format_rows(runs):
    """One line per run, oldest first — the shape the report already has."""
    lines = []
    for run in runs:
        exit_code = "-" if run["exit"] is None else str(run["exit"])
        lines.append(
            "{:19s} exit {:<3s} cycles {:>3d} done {:>3d} blocked {:>3d} "
            "deferred {:>3d} parked {:>3d} requests {:>5d} in {:>10,d} "
            "out {:>8,d}".format(
                run["started"], exit_code, run["cycles"], run["completed"],
                run["blocked"], run["deferred"], run["parked"],
                run["requests"], run["tokens_in"], run["tokens_out"]))
    return lines


def format_totals(totals):
    """The comparison numbers, computed from what the runs recorded."""
    lines = [
        "runs: {runs}  cycles: {cycles}  completed: {completed}  "
        "blocked: {blocked}  deferred: {deferred}".format(**totals),
        "cycles spent on a parked mission: {parked}".format(**totals),
        "provider: {requests:,} requests, {tokens_in:,} in / {tokens_out:,} "
        "out tokens".format(**totals),
        "runs that completed nothing: {barren} of {runs}".format(**totals),
        "parked missions still in the ledger: {parked_missions}".format(
            **totals),
    ]
    if totals["completed"]:
        # Robust when usage is unobserved (a `--worker claude` run records
        # no requests at all): cycles spent per finished mission still says
        # whether the loop is producing or spinning.
        lines.append("cycles per completion: {:.2f}".format(
            totals["cycles"] / float(totals["completed"])))
    if totals["requests"]:
        per_1000 = totals["completed"] * 1000.0 / totals["requests"]
        lines.append(
            "completions per 1,000 requests: {:.2f}".format(per_1000))
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ine-agent-measure",
        description="Re-measure the autonomous loop from .agent/ records.")
    parser.add_argument("--root", default=".",
                        help="project root (default: .)")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)
    if not os.path.isdir(os.path.join(root, state.AGENT_DIR)):
        print("no {} directory under {}".format(state.AGENT_DIR, root))
        return 1
    runs, totals = summarize(root)
    if not runs:
        print("no run has been recorded in {}".format(state.REPORT_NAME))
        print("(the attempt ledger is {}: {} mission(s))".format(
            ATTEMPTS_NAME, totals["parked_missions"]))
        return 0
    for line in format_rows(runs):
        print(line)
    print("")
    for line in format_totals(totals):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
