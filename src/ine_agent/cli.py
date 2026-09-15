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
    from .state import ProjectError, find_project_root
    from .supervisor import STOP_ERROR, STOP_HUMAN, STOP_OK, Supervisor
    from .worker import build_worker
except ImportError:  # running as a plain script: python src/ine_agent/cli.py
    from ine_agent.state import ProjectError, find_project_root
    from ine_agent.supervisor import STOP_ERROR, STOP_HUMAN, STOP_OK, Supervisor
    from ine_agent.worker import build_worker


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
    return parser


def _resolve_root(requested):
    if requested is not None:
        requested = os.path.abspath(requested)
        if not os.path.isdir(requested):
            raise ProjectError("project root does not exist: {}".format(requested))
        return find_project_root(requested)
    return find_project_root(os.getcwd())


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        root = _resolve_root(args.root)
    except ProjectError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1

    supervisor = Supervisor(
        root=root,
        worker_factory=build_worker,
        impl_worker=args.worker,
        max_cycles=args.cycle_limit,
        max_attempts=args.max_attempts,
        dry_run=args.dry_run,
    )
    return supervisor.run()


if __name__ == "__main__":
    raise SystemExit(main())