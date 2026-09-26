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
    from . import budget, profiles, verify
    from .measure import main as measure_main
    from .state import (
        ProjectError, WORKER_INSTRUCTIONS_NAME, find_project_root, read_plan,
        record_resolution,
    )
    from .supervisor import (
        DEFAULT_MAX_FAILURES, DEFAULT_STALL_LIMIT, STOP_ERROR, STOP_HUMAN,
        STOP_OK, Supervisor, worker_instructions,
    )
    from .worker import effective_command
except ImportError:  # running as a plain script: python src/ine_agent/cli.py
    from ine_agent import budget, profiles, verify
    from ine_agent.measure import main as measure_main
    from ine_agent.state import (
        ProjectError, WORKER_INSTRUCTIONS_NAME, find_project_root, read_plan,
        record_resolution,
    )
    from ine_agent.supervisor import (
        DEFAULT_MAX_FAILURES, DEFAULT_STALL_LIMIT, STOP_ERROR, STOP_HUMAN,
        STOP_OK, Supervisor, worker_instructions,
    )
    from ine_agent.worker import effective_command


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
        "--worker", default="opencode",
        help="worker profile name: a built-in ('opencode', 'claude') or one "
             "declared in .agent/workers.json (default: opencode)",
    )
    run.add_argument(
        "--model", default=None,
        help="model to request; passed to the tool only by a profile that "
             "declares how it wants one, otherwise the tool's own default is "
             "used (also INE_AGENT_MODEL)",
    )
    run.add_argument(
        "--dry-run", action="store_true",
        help="resolve the profile, the command, the queue and the budget, "
             "print them, and stop without launching any worker",
    )
    run.add_argument(
        "--max-missions", "--cycle-limit", dest="max_missions", type=int,
        default=None, metavar="N",
        help="stop after N missions have been attempted; unset (the "
             "default) runs the executable queue to exhaustion, which is "
             "finite because a mission is attempted once and then left "
             "DONE, BLOCKED or DEFERRED. --cycle-limit is the old name for "
             "the same bound and still works",
    )
    run.add_argument(
        "--max-attempts", type=int, default=None,
        help="attempts one mission may be given within a run before it is "
             "deferred so independent work continues (default: the policy's "
             "max_attempts, which is 1 — one request per mission, and a "
             "second attempt is the commander's call, not the loop's; given "
             "here, this flag wins over the policy)",
    )
    run.add_argument(
        "--max-failures", type=int, default=DEFAULT_MAX_FAILURES,
        help="failed attempts recorded across runs before a mission is "
             "parked and no longer picked, until it is rewritten or its "
             "entry is removed from .agent/attempts.json (default: {}; 0 "
             "disables parking)".format(DEFAULT_MAX_FAILURES),
    )
    run.add_argument(
        "--stall-limit", type=int, default=DEFAULT_STALL_LIMIT,
        help="consecutive cycles that neither complete nor block anything "
             "and change no file outside .agent/ before the run stops early "
             "(default: {}; 0 disables the guard)".format(DEFAULT_STALL_LIMIT),
    )
    run.add_argument(
        "--heartbeat", type=int, default=30, metavar="SECONDS",
        help="while a worker is quiet, print a '[heartbeat] ... still "
             "running' line every SECONDS (default: 30; 0 turns it off). A "
             "CLI in its own non-interactive print mode emits nothing until "
             "it finishes, so this line is the only sign of life a long "
             "mission gives - lower it to watch a run more closely",
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
    doctor = sub.add_parser(
        "doctor",
        help="resolve the selected worker profile and report exactly what "
             "would run, without calling a model",
    )
    doctor.add_argument(
        "--root", default=None,
        help="project root (default: search upward from the current directory)",
    )
    doctor.add_argument(
        "--worker", default="opencode",
        help="worker profile name to check (default: opencode)",
    )
    doctor.add_argument(
        "--model", default=None,
        help="model to resolve into the command (also INE_AGENT_MODEL)",
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
    measure = sub.add_parser(
        "measure",
        help="re-measure past runs from .agent/ records: what each run and "
             "each mission cost, in cycles, requests, tokens and prompt "
             "characters (read-only; launches nothing)",
    )
    measure.add_argument(
        "--root", default=None,
        help="project root (default: search upward from the current directory)",
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
    """Make console writes safe and *immediate*.

    Two separate problems, both of which look like "the tool is doing
    nothing":

    - **Encoding.** The worker boundary decodes UTF-8 with surrogateescape;
      relaying those lines back to a cp1252 console under strict error
      handling would raise UnicodeEncodeError. backslashreplace keeps live
      output and summaries printable regardless of the terminal encoding.
    - **Buffering.** Python block-buffers stdout when it is not a terminal,
      so a piped or redirected run showed *nothing at all* until the process
      exited - nine seconds of proven silence in the probe that found this,
      including output the worker itself had flushed. A supervisor that
      streams a worker it cannot see streaming is indistinguishable from a
      hung one. `line_buffering` makes every print site in the package
      appear as it happens, without touching all of them.
    """
    try:
        sys.stdout.reconfigure(
            errors="backslashreplace", line_buffering=True)
    except (AttributeError, ValueError, OSError):
        # A stream that cannot be reconfigured (a test double, a closed pipe)
        # must not stop the run; _print still flushes explicitly.
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


def _model(args):
    """--model wins; otherwise INE_AGENT_MODEL; otherwise the tool's own."""
    value = getattr(args, "model", None)
    if value is not None:
        return value
    return os.environ.get("INE_AGENT_MODEL") or ""


def _describe_worker(root, name, model, out=sys.stdout):
    """Resolve `name` and print what it would run. Returns (code, profile).

    No worker is constructed and nothing is spawned: a preview that builds
    the thing it is previewing can drift from it, and a dry run that
    constructs a worker is a dry run that has already half-run.
    """
    try:
        profile = profiles.resolve(root, name, model=model)
        command = profiles.check_executable(
            profile, [*effective_command(profile), *profile.argv()[1:]])
        template = worker_instructions(root)
    except profiles.ProfileError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1, None
    except ProjectError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1, None
    print("profile    : {} ({})".format(
        profile.name, profile.description or "no description"), file=out)
    print("prompt     : {}".format(profile.where_prompt_goes()), file=out)
    print("instructions: {} ({} lines, you edit this to change what the "
          "worker is told to do)".format(
              os.path.join(".agent", WORKER_INSTRUCTIONS_NAME),
              len(template.splitlines())), file=out)
    print("model      : {}".format(profile.model or "the tool's default"),
          file=out)
    print("timeout    : {}".format(
        "{}s".format(int(profile.timeout_seconds)) if profile.timeout_seconds
        else "none"), file=out)
    print("command    : {}".format(profiles.display_command(command)),
          file=out)
    print("             (the prompt is appended at run time)", file=out)
    missing = [entry for entry in profile.env
               if not os.environ.get(entry, "").strip()]
    if missing:
        print("warning    : {} not set in the environment".format(
            ", ".join(missing)), file=out)
    return 0, profile


def _doctor_cli(root, args):
    _safe_stdout()
    code, _ = _describe_worker(root, args.worker, _model(args))
    return code


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
    if args.command == "doctor":
        return _doctor_cli(root, args)
    if args.command == "measure":
        # The same read-only report the standalone `ine_agent.measure` module
        # prints, reached through the one CLI the commander is told to use.
        # It resolves the root the same way, so it works from a subdirectory.
        return measure_main(["--root", root])

    _safe_stdout()
    model = _model(args)
    try:
        supervisor = Supervisor(
            root=root,
            # No `worker_factory` here on purpose. The supervisor already owns
            # that contract and binds the root and the model into it; passing
            # `build_worker` in raw meant a second, wrong copy of it - the
            # loop printed a correct command in `--dry-run` and then died with
            # a TypeError on the first real cycle, because a dry run never
            # builds a worker. One place decides how a worker is built.
            impl_worker=args.worker,
            model=model,
            max_cycles=args.max_missions,
            max_attempts=args.max_attempts,
            max_failures=args.max_failures,
            stall_limit=args.stall_limit,
            dry_run=args.dry_run,
            quiet=args.quiet,
            verbose=args.verbose,
            notify=args.notify,
            usage_warn_requests=_usage_warn_requests(args),
            # Only `run` reaches here, and only `run` declares --heartbeat,
            # so this is the one place the interval can be set from the
            # command line. Everything else keeps the supervisor's default.
            heartbeat_seconds=args.heartbeat,
        )
    except (ProjectError, budget.PolicyError, verify.VerifyError) as exc:
        # A control-plane fault, not a crash: an unusable instructions file, an
        # unreadable plan or a malformed `workers.json` stops the run with its
        # remedy rather than a traceback, and without launching a worker. The
        # config errors are strict by design — a bad check list is reported,
        # never quietly ignored into a green run.
        print("error: {}".format(exc), file=sys.stderr)
        return 1
    try:
        return supervisor.run()
    except ProjectError as exc:
        # A control-plane fault, not a crash: an unusable instructions file
        # or an unreadable plan stops the run with its remedy rather than a
        # traceback, and without launching a worker.
        print("error: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())