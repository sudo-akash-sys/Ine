"""Command-line entry point for the ine-agent supervisor tool.

    ine-agent run

drives safe autonomous work in the Ine repository. This is developer
tooling, not part of the Ine language: the durable intelligence lives in
`.agent/`, and this CLI only coordinates a worker process against it.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .state import (
        ProjectError, find_project_root, read_plan, record_resolution,
    )
    from .supervisor import STOP_ERROR, STOP_HUMAN, STOP_OK, Supervisor
    from .worker import build_worker
except ImportError:  # running as a plain script: python src/ine_agent/cli.py
    from ine_agent.state import (
        ProjectError, find_project_root, read_plan, record_resolution,
    )
    from ine_agent.supervisor import STOP_ERROR, STOP_HUMAN, STOP_OK, Supervisor
    from ine_agent.worker import build_worker


def _resolve_blocked(root, needle, blueprint):
    """Find the first BLOCKED mission whose headline contains `needle` and
    record `blueprint` as a resolution remark (preserving the original
    blocker text). Returns the Task or None."""
    needle = needle.strip().lower()
    for item in read_plan(root).items:
        if item.tag == "BLOCKED" and needle in item.text.splitlines()[0].lower():
            record_resolution(root, item.identity, blueprint)
            return item
    return None


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ine-agent",
        description="Autonomous supervisor for the Ine repository "
                    "(reads .agent/, drives a worker CLI).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the supervisor loop")
    run.add_argument(
        "--root", default=None,
        help="project root (default: search upward from the current directory)",
    )
    run.add_argument(
        "--worker", default="opencode", choices=("opencode", "claude"),
        help="implementation worker CLI (default: opencode)",
    )
    run.add_argument(
        "--dry-run", action="store_true",
        help="resolve the project and the first executable task, print them, "
             "and stop without launching any worker",
    )
    run.add_argument(
        "--cycle-limit", type=int, default=20,
        help="hard bound on worker cycles (default: 20)",
    )
    run.add_argument(
        "--max-attempts", type=int, default=2,
        help="consecutive cycles without plan progress before stopping "
             "(default: 2)",
    )
    run.add_argument(
        "--quiet", action="store_true",
        help="hide live worker output; show only mission and result",
    )
    run.add_argument(
        "--verbose", action="store_true",
        help="relay raw worker output (keeps ANSI, no prefix)",
    )
    run.add_argument(
        "--usage-warn-requests", type=int, default=None,
        help="warn (and notify) once observed OpenCode requests for today "
             "reach this number; advisory only, never stops the run "
             "(default: INE_AGENT_USAGE_WARN_REQUESTS)",
    )
    run.add_argument(
        "--notify", action="store_true",
        help="show a Windows notification for run completion, blocked "
             "missions, failed missions, and HUMAN_DECISION_REQUIRED gates "
             "(also enabled by INE_AGENT_NOTIFY=1; never blocks the loop)",
    )
    resolve = sub.add_parser(
        "resolve",
        help="record a commander resolution/blueprint for a blocked mission "
             "(preserves the original blocker record)",
    )
    resolve.add_argument(
        "--root", default=None,
        help="project root (default: search upward from the current directory)",
    )
    resolve.add_argument(
        "mission",
        help="headline text of the BLOCKED mission (substring, "
             "case-insensitive)",
    )
    resolve.add_argument(
        "blueprint",
        help="the resolution or blueprint the commander is supplying",
    )
    return parser


def _resolve_root(requested):
    if requested is not None:
        requested = os.path.abspath(requested)
        if not os.path.isdir(requested):
            raise ProjectError("project root does not exist: {}".format(requested))
        return find_project_root(requested)
    return find_project_root(os.getcwd())


def _usage_warn_requests(args):
    """--usage-warn-requests wins over the INE_AGENT_USAGE_WARN_REQUESTS env
    override. A missing/invalid env value simply means no warning."""
    value = args.usage_warn_requests
    if value is not None:
        return value
    raw = os.environ.get("INE_AGENT_USAGE_WARN_REQUESTS")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _safe_stdout():
    """Make console writes never crash on non-console-safe bytes (cp1252).

    The worker boundary decodes UTF-8 with surrogateescape; relaying those
    lines back to a cp1252 console under strict error handling would raise
    UnicodeEncodeError. backslashreplace keeps live output and summaries
    printable regardless of the terminal encoding.
    """
    try:
        sys.stdout.reconfigure(errors="backslashreplace")
    except (AttributeError, ValueError):
        pass


def _resolve_blocked_cli(root, needle, blueprint):
    """Record a commander resolution as a new remark under the matching
    BLOCKED mission. Original blocker text is never rewritten."""
    resolved = _resolve_blocked(root, needle, blueprint)
    if resolved is None:
        print("error: no BLOCKED mission matches '{}'".format(needle),
              file=sys.stderr)
        return 1
    print("recorded resolution for PLAN item {}:".format(resolved.number))
    print("  " + resolved.text.splitlines()[0])
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    if getattr(args, "quiet", False) and getattr(args, "verbose", False):
        print("error: --quiet and --verbose are mutually exclusive",
              file=sys.stderr)
        return 1
    try:
        root = _resolve_root(args.root)
    except ProjectError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1
    if args.command == "resolve":
        return _resolve_blocked_cli(root, args.mission, args.blueprint)

    _safe_stdout()
    supervisor = Supervisor(
        root=root,
        worker_factory=build_worker,
        impl_worker=args.worker,
        max_cycles=args.cycle_limit,
        max_attempts=args.max_attempts,
        dry_run=args.dry_run,
        quiet=args.quiet,
        verbose=args.verbose,
        notify=args.notify,
        usage_warn_requests=_usage_warn_requests(args),
    )
    return supervisor.run()


if __name__ == "__main__":
    raise SystemExit(main())