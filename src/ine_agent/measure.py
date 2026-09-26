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
#: Per-mission cost lines, written by the supervisor after each outcome is
#: known. Both are local observations: the context line is arithmetic over the
#: prompt this process built, the usage line is the provider's own delta.
_CONTEXT_RE = re.compile(
    r"^- \[mission (\d+)\] context: ([\d,]+) chars/(\d+) lines "
    r"\(~([\d,]+) tokens\), (\d+) declared file\(s\), "
    r"(\d+) previous receipt\(s\), budget ([\d,]+) chars")
_OVER_BUDGET_RE = re.compile(r"OVER BUDGET by ([\d,]+) chars")
_MISSION_USAGE_RE = re.compile(
    r"^- \[mission (\d+)\] usage: status=(\S+) worker=(\S+) model=(\S+) "
    r"elapsed=([\d.]+)s \S+ "
    r"(?:\+(\d+) requests, \+([\d,]+) in / \+([\d,]+) out tokens"
    r"|usage_unavailable)")


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
                "exit": None, "missions": {},
            }
            runs.append(run)
            continue
        if run is None:
            continue
        if _MISSION_RE.match(line):
            run["cycles"] += 1
            continue
        context = _CONTEXT_RE.match(line)
        if context:
            # One row per mission, keyed by its number, so the context and
            # usage lines of the same mission become one record.
            entry = run["missions"].setdefault(
                int(context.group(1)),
                {"number": int(context.group(1)), "status": "",
                 "chars": 0, "lines": 0, "tokens_estimate": 0, "files": 0,
                 "receipts": 0, "budget": 0, "over_by": 0, "model": "",
                 "elapsed": 0.0, "requests": 0, "tokens_in": 0,
                 "tokens_out": 0, "usage_known": None})
            entry["chars"] = _number(context.group(2))
            entry["lines"] = int(context.group(3))
            entry["tokens_estimate"] = _number(context.group(4))
            entry["files"] = int(context.group(5))
            entry["receipts"] = int(context.group(6))
            entry["budget"] = _number(context.group(7))
            over = _OVER_BUDGET_RE.search(line)
            entry["over_by"] = _number(over.group(1)) if over else 0
            continue
        mission_usage = _MISSION_USAGE_RE.match(line)
        if mission_usage:
            entry = run["missions"].setdefault(
                int(mission_usage.group(1)),
                {"number": int(mission_usage.group(1)), "status": "",
                 "chars": 0, "lines": 0, "tokens_estimate": 0, "files": 0,
                 "receipts": 0, "budget": 0, "over_by": 0, "model": "",
                 "elapsed": 0.0, "requests": 0, "tokens_in": 0,
                 "tokens_out": 0, "usage_known": None})
            entry["status"] = mission_usage.group(2)
            entry["model"] = mission_usage.group(4)
            entry["elapsed"] = float(mission_usage.group(5))
            if mission_usage.group(6) is None:
                # Recorded as unknown, not as zero: "the provider told us
                # nothing" is a different claim from "this mission was free",
                # and only the first one is true.
                entry["usage_known"] = False
            else:
                entry["usage_known"] = True
                entry["requests"] = int(mission_usage.group(6))
                entry["tokens_in"] = _number(mission_usage.group(7))
                entry["tokens_out"] = _number(mission_usage.group(8))
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
    missions = [mission for run in runs for mission in run["missions"].values()]
    measured = [mission for mission in missions if mission["chars"]]
    measured.sort(key=lambda mission: mission["number"])
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
        "missions_measured": len(measured),
        "prompt_chars_total": sum(m["chars"] for m in measured),
        "prompt_chars_max": max([m["chars"] for m in measured] or [0]),
        "over_budget": sum(1 for m in measured if m["over_by"]),
        "usage_unknown": sum(1 for m in measured
                             if m["usage_known"] is not True),
    }
    return runs, totals, measured


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


def format_missions(missions):
    """One line per measured mission: what its handoff cost, and what it used.

    The prompt column is the one this loop controls and can therefore be held
    to; the request and token columns are the provider's own account of itself
    and are shown only where it gave one.
    """
    lines = []
    for mission in missions:
        if mission["usage_known"] is True:
            spent = ("{:>4d} req {:>9,d} in {:>8,d} out".format(
                mission["requests"], mission["tokens_in"],
                mission["tokens_out"]))
        else:
            spent = "usage_unavailable"
        budget = ""
        if mission["over_by"]:
            budget = "  OVER by {:,}".format(mission["over_by"])
        lines.append(
            "  mission {:<4d} {:<10s} {:>6,} chars {:>4d} lines ~{:>5,} tok "
            "{:>2d} file(s) {:>2d} prior  {:>8s} {}".format(
                mission["number"], mission["status"] or "-",
                mission["chars"], mission["lines"],
                mission["tokens_estimate"], mission["files"],
                mission["receipts"], spent, budget).rstrip())
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
    if totals["missions_measured"]:
        lines.append(
            "missions measured: {missions_measured}  prompt: "
            "{prompt_chars_total:,} chars total, {prompt_chars_max:,} largest, "
            "{over_budget} over budget".format(**totals))
        lines.append(
            "missions with no provider usage recorded: {usage_unknown} of "
            "{missions_measured}".format(**totals))
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
    runs, totals, missions = summarize(root)
    if not runs:
        print("no run has been recorded in {}".format(state.REPORT_NAME))
        print("(the attempt ledger is {}: {} mission(s))".format(
            ATTEMPTS_NAME, totals["parked_missions"]))
        return 0
    for line in format_rows(runs):
        print(line)
    if missions:
        print("")
        for line in format_missions(missions):
            print(line)
    print("")
    for line in format_totals(totals):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
