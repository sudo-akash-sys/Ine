"""The ine-agent supervisor loop.

A dumb coordinator. It reads `.agent/` on every cycle, applies the PLAN
selection rule deterministically, runs exactly one worker per cycle
(sequentially — never concurrent), and stops on the defined conditions:

- no executable work        -> normal stop (exit 0)
- HUMAN_DECISION_REQUIRED   -> commander-judgment flag (exit 2)
- worker cannot advance     -> bounded-stop after `max_attempts` (exit 1)
- cycle-limit reached       -> hard bound (exit 1)

Since Session 41 the loop is also a RECORDING loop (commander directive):
a mission that becomes blocked, fails, or requires commander judgment is
recorded durably (PLAN remark / BLOCKERS entry / run report — original
text preserved), deferred for the rest of the run, and the loop continues
with the next independent executable task instead of halting. Every
mission and run end also fires an optional Windows notification (a
task-started banner, an outcome banner per mission, and a run-complete /
decision / usage event), each pointing at the durable run report
(.agent/RUN_REPORTS.md); notifications are best-effort, streamed to one
headline line, and never stop or delay execution.

The supervisor loads MISSION_PROMPT.md and MISSION.md once per cycle and
embeds them in the worker prompt, so the worker never needs to read them
from disk. It never unblocks evidence-gated work and never invents
semantics.
"""

import os
import re
import sys

from . import state, usage
from .notifier import create_notifier
from .worker import WorkerResult, build_worker

STOP_OK = 0
STOP_ERROR = 1
STOP_HUMAN = 2


# CSI sequences (colors, cursor moves) are stripped from the default live
# relay so a cp1252 Windows console never receives raw control sequences.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _strip_ansi(text):
    return _ANSI_RE.sub("", text)


def _mission_block(root):
    """Load MISSION_PROMPT.md and MISSION.md, returning a combined preamble.

    Both files are optional — when absent the preamble is empty. Embedding
    them means the worker never needs to read them from disk; the
    supervisor takes care of it on every cycle.
    """
    mission_prompt = state._read_optional_text(
        root, state.MISSION_PROMPT_NAME).strip()
    mission = state._read_optional_text(
        root, state.MISSION_NAME).strip()
    block = ""
    if mission_prompt:
        block += (
            "MISSION (follow this as your autonomous operating rules):\n\n"
            + mission_prompt + "\n\n"
        )
    if mission:
        block += "PROJECT CONTEXT:\n\n" + mission + "\n\n"
    return block


def _distill_state(root, limit=1600):
    """The current-state essentials a worker needs for ONE mission.

    Extracts just the 'Current focus' and 'Health' sections from STATE.md
    instead of the whole file, so the worker gets the position summary it
    needs without re-reading the full control-plane records on every cycle.
    """
    text = state._read_optional_text(root, state.STATE_NAME)
    if not text:
        return "(no .agent/STATE.md yet — treat the mission text as the state)"
    sections = {}
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections.setdefault(current, [])
        elif current in ("current focus", "health"):
            sections[current].append(line)
    blocks = []
    for key in ("current focus", "health"):
        body = sections.get(key, [])
        if body:
            blocks.append("## " + key.title() + "\n" + "\n".join(body).strip())
    joined = "\n\n".join(blocks).strip()
    if not joined:
        return "(no 'Current focus' or 'Health' sections in STATE.md)"
    if len(joined) > limit:
        joined = joined[:limit].rstrip() + "\n...(truncated)"
    return joined


def impl_prompt(root, task):
    """The prompt handed to the implementation worker (OpenCode by default).

    The autonomous mission preamble (MISSION_PROMPT.md), project context
    (MISSION.md), and a distilled current-state snapshot are embedded at the
    top so the worker never needs to re-read the control-plane files on
    every cycle. The orchestrator has already selected exactly ONE mission;
    the worker drives that mission to a verified finish and stops, so the
    supervisor's deterministic selection advances the plan between cycles.
    """
    return (
        _mission_block(root)
        + "You are the autonomous implementation worker for the Ine repository.\n"
        "\n"
        "The orchestrator has selected EXACTLY ONE mission for you (below).\n"
        "Execute it as one complete problem-solving arc: research -> understand\n"
        "-> implement -> test -> verify -> record -> clean up. Drive it to a\n"
        "genuine, verified finish. When the mission is complete, STOP and\n"
        "report. Do NOT re-scan .agent/PLAN.md to pick more missions and do\n"
        "NOT continue to further missions — the orchestrator selects the next\n"
        "one after this cycle.\n"
        "\n"
        "1. Operating rules: read AGENTS.md in full. The .agent/ control files\n"
        "   remain your records, but the essentials you need are embedded\n"
        "   below — do not re-read the whole of STATE.md or PLAN.md.\n"
        "2. Current state (distilled for this cycle):\n"
        "\n"
        "   {snapshot}\n"
        "\n"
        "3. Mission (the entire scope of this cycle):\n"
        "\n"
        "   {task}\n"
        "\n"
        "4. Run focused tests, review your changes, run broader regression\n"
        "   when appropriate, and update .agent/STATE.md and .agent/HISTORY.md\n"
        "   per the AGENTS.md workflow in ONE final pass — never incrementally\n"
        "   as you work.\n"
        "5. Be resource-budget frugal: every tool call is a model request.\n"
        "   Batch all independent reads/greps into a single message, read\n"
        "   files whole rather than in slices, run tests once per mission\n"
        "   rather than after every edit, and prefer direct work over\n"
        "   spawning subagents or fetching web pages unless genuinely needed.\n"
        "\n"
        "Guardrails (never violated): do not invent language semantics, do\n"
        "not unblock evidence-gated work, do not modify DECISIONS.md, do\n"
        "not change parser/semantic/backend behavior except when the task\n"
        "explicitly requires it, and keep temporary artifacts under .tmp/.\n"
        "If the task genuinely requires commander judgment, print\n"
        "HUMAN_DECISION_REQUIRED and stop.\n"
    ).format(snapshot=_distill_state(root), task=task.raw.strip())


def review_prompt(root, task):
    """The optional Claude review prompt (only for CLAUDE_REVIEW tasks).

    Includes the mission preamble and project context so the reviewer
    understands the project constraints without reading from disk.
    """
    return (
        _mission_block(root)
        + "You are the design-review step of the Ine autonomous workflow. Do NOT\n"
        "implement anything. Review and decompose the following task, check\n"
        "whether it requires commander judgment, and report a short plan plus\n"
        "any stop recommendation. The implementation worker will handle the\n"
        "rest; never rewrite semantics or override DECISIONS.md.\n"
        "\n"
        "Task to review:\n"
        "{task}\n"
        "\n"
        "If the task requires commander judgment, print HUMAN_DECISION_REQUIRED.\n"
    ).format(task=task.raw.strip())


class Supervisor:
    """Sequential worker loop over .agent/ executable work."""

    def __init__(self, root, worker_factory=None, impl_worker="opencode",
                 max_cycles=20, max_attempts=2, dry_run=False, out=None,
                 quiet=False, verbose=False, notify=False, notifier=None,
                 usage_warn_requests=None, usage_reporter=None):
        self.root = root
        self.worker_factory = worker_factory or build_worker
        self.impl_worker = impl_worker
        self.max_cycles = max_cycles
        self.max_attempts = max_attempts
        self.dry_run = dry_run
        self.quiet = quiet
        self.verbose = verbose
        self.notify = notify
        self.out = out if out is not None else sys.stdout
        self._notifier = notifier
        self.usage_warn_requests = usage_warn_requests
        self._usage = usage_reporter or usage.UsageReporter()
        self._report_path = state.run_report_path(root)

    def _print(self, message, end="\n"):
        print(message, end=end, file=self.out)

    def _command_line(self):
        return " ".join(sys.argv)

    def _notify(self, title, body, report=None):
        """Fire-and-forget commander notification.

        Never awaited and always swallowed: a notification failure must
        never stop or delay autonomous execution (see notifier.py). The
        report path is passed separately so the popup never shows raw
        file paths — only the commander point it at the durable record.
        """
        try:
            if self._notifier is None:
                self._notifier = create_notifier(self.notify)
            self._notifier.notify(title, body, self._report_path)
        except Exception:
            pass

    @staticmethod
    def _run_summary(code):
        """Human phrase for the run's overall exit code — no raw codes in
        commander-facing prose."""
        if code == STOP_ERROR:
            return "A task failed; it was recorded and deferred for a future run."
        if code == STOP_HUMAN:
            return "A task awaits your decision; the rest of the work was recorded."
        return "All tasks done — nothing left to run."

    @staticmethod
    def _truncate(text, limit=90):
        text = " ".join((text or "").split())
        return text if len(text) <= limit else text[: limit - 3] + "..."

    def _usage_warning(self, observed_requests):
        """Warn (once) and notify the commander when observed usage crosses
        the configured threshold.

        The number is the locally-observed OpenCode request count for today
        (see usage.py); it is NOT the provider quota. The warning is purely
        advisory — it never stops or delays the loop.
        """
        if self.usage_warn_requests is None or getattr(
                self, "_warned_usage", False):
            return
        if observed_requests is None or observed_requests < self.usage_warn_requests:
            return
        self._warned_usage = True
        message = (
            "Observed OpenCode usage today reached {} requests "
            "(warning threshold {}). This is locally observed usage, not an "
            "exact provider quota.".format(
                observed_requests, self.usage_warn_requests))
        self._print("[usage] " + message)
        state.append_run_report(self.root, ["- usage warning: {}".format(message)])
        self._notify(
            "Ine · usage warning",
            "Observed usage reached {} requests today; warning threshold "
            "{}.".format(observed_requests, self.usage_warn_requests))

    def _handle_line(self, line):
        """Live worker stdout/stderr relay.

        Default relays the line indented with ANSI control sequences
        stripped; `--verbose` relays it raw and unindented, as if the
        worker ran directly; `--quiet` drops live lines entirely.
        """
        if self.quiet:
            return
        if self.verbose:
            self._print(line, end="")
        else:
            self._print("  " + _strip_ansi(line), end="")

    def _worker(self, name):
        return self.worker_factory(name)

    def _no_work(self):
        self._print("No executable work remains.")
        self._print("ine-agent stopped normally.")

    def _human_stop(self, task=None):
        self._print("HUMAN_DECISION_REQUIRED")
        headline = self._current_headline(task) if task is not None else ""
        self._print(
            "ine-agent stopped: commander judgment is required"
            + (" for: " + headline if headline else "") + "."
        )

    def _current_headline(self, task):
        """The task's headline as PLAN.md shows it right now.

        A worker may complete and re-tag the task (e.g. mark it DONE) before
        its transcript is checked, so the commander-facing message uses the
        fresh tag rather than the pre-cycle snapshot — otherwise a completed
        mission would be reported as an abandoned EXECUTABLE one.
        """
        try:
            for item in state.read_plan(self.root).items:
                if self._same_mission(item, task):
                    return item.text.splitlines()[0]
        except OSError:
            pass
        return task.text.splitlines()[0]

    @staticmethod
    def _same_mission(item, task):
        """Whether two Task snapshots describe the same mission.

        Keyed on the headline only, NOT the tag: a worker that finishes a
        task re-tags it EXECUTABLE -> DONE, so a tag-agnostic comparison is
        what lets the outcome logic see the freshly re-tagged item.
        """
        return state.headline_key(item.text) == state.headline_key(task.text)

    def _run_task(self, task, on_line=None):
        """Run optional review (CLAUDE_REVIEW tag) then the implementation
        worker, sequentially. Never concurrent."""
        if task.wants_claude_review:
            review = self._worker("claude").run(
                self.root, review_prompt(self.root, task), on_line=on_line)
            if state.output_marks_human_decision(review.output):
                return review
        return self._worker(self.impl_worker).run(
            self.root, impl_prompt(self.root, task), on_line=on_line
        )

    def _outcome(self, result, task, plan):
        """Classify what one worker cycle did to `task`.

        Returns 'done', 'human', 'blocked', 'failed', or 'stuck'.

        The plan is re-read AFTER the cycle, so a worker that finished marks
        the item DONE/removed and a worker that hit an evidence wall marks
        it BLOCKED. The HUMAN_DECISION_REQUIRED marker is checked FIRST
        (line-based, own-line only) because a decision gate dominates any
        incidental re-tag the worker performed.
        """
        if state.output_marks_human_decision(result.output):
            return "human"
        fresh = plan.item(identity=task.identity)
        if fresh is None:
            return "done"        # item removed by the worker
        if fresh.tag == "DONE":
            return "done"
        if fresh.tag == "BLOCKED":
            return "blocked"
        if result.exit_code != 0:
            return "failed"
        return "stuck"

    def _finish(self, code, message, notify_title=None, notify_body=None,
                print_message=True, report_summary=None):
        """End the run report, print (optional) and notify run completion."""
        baseline = getattr(self, "_usage_before", None)
        if baseline is not None:
            final = self._usage.snapshot()
            run_delta = self._usage.delta(baseline, final)
            if usage.has_usage(run_delta):
                state.append_run_report(self.root, [
                    "- usage end: " + usage.format_snapshot(final),
                    "- usage delta (run): " + usage.format_delta(run_delta),
                ])
            self._usage.close()
            self._usage_before = None
        state.end_run_report(self.root, code, report_summary or message or "done")
        if message and print_message:
            self._print(message)
        self._notify(
            notify_title or "Ine · run complete",
            notify_body if notify_body is not None
            else self._run_summary(code))
        return code

    def run(self):
        plan = state.read_plan(self.root)
        task = plan.first_executable()
        self._print("project: {}".format(self.root))

        if state.human_decision_indicated(self.root):
            # Pre-existing gate: nothing has been attempted, so the run stops
            # immediately (exit 2) with a notification and a durable record.
            self._human_stop()
            state.begin_run_report(self.root, self._command_line())
            state.append_run_report(self.root, [
                "- outcome: pre-existing HUMAN_DECISION_REQUIRED gate"])
            self._notify(
                "Ine · decision required",
                "A mission is waiting for your judgment; work is on hold "
                "until then.")
            return self._finish(
                STOP_HUMAN,
                "commander judgment is already required; no work was run.")

        if task is None:
            self._no_work()
            state.begin_run_report(self.root, self._command_line())
            self._notify(
                "Ine · run complete",
                "All tasks done — nothing left to run.")
            return self._finish(
                STOP_OK, None, print_message=False,
                report_summary="no executable work remains.")

        if self.dry_run:
            headline = task.text.splitlines()[0]
            self._print("[dry-run] worker '{}' would run for: {}".format(
                self.impl_worker, headline))
            return STOP_OK

        state.begin_run_report(self.root, self._command_line())

        self._usage_before = self._usage.snapshot()
        self._usage_prev = dict(self._usage_before)
        self._warned_usage = False
        state.append_run_report(self.root, [
            "- usage start: " + usage.format_snapshot(self._usage_before)])

        attempts = 0
        cycles = 0
        deferred = set()       # mission identities deferred this run
        pending_human = False  # a genuine decision gate is open
        had_failure = False    # at least one mission failed this run
        ran_any = False

        while True:
            if task is None:
                break
            if state.human_decision_indicated(self.root):
                # A gate appeared mid-run (e.g. the worker wrote it to a
                # .agent/ file). Record and stop: the plan already carries
                # the marker and the next run will respect it.
                self._human_stop(task)
                state.append_run_report(self.root, [
                    "- outcome: mid-run HUMAN_DECISION_REQUIRED gate"])
                self._notify(
                    "Ine · decision required",
                    self._truncate(headline))
                return self._finish(
                    STOP_HUMAN,
                    "commander judgment required for: "
                    + self._current_headline(task))

            if cycles >= self.max_cycles:
                self._print(
                    "Reached the maximum of {} worker cycle(s); execution stopped."
                    .format(self.max_cycles))
                return self._finish(
                    STOP_ERROR,
                    "reached the maximum of {} worker cycle(s)."
                    .format(self.max_cycles))

            if attempts >= self.max_attempts:
                self._print(
                    "Worker could not advance the plan after {} attempt(s); "
                    "execution stopped.".format(self.max_attempts))
                return self._finish(
                    STOP_ERROR,
                    "worker could not advance the plan after {} attempt(s)."
                    .format(self.max_attempts))

            headline = task.text.splitlines()[0]
            worker_name = (self.impl_worker
                           if not task.wants_claude_review
                           else "claude+opencode")
            self._print("")
            self._print("[cycle {}] worker '{}'".format(cycles + 1, worker_name))
            self._print("[cycle {}] mission: {}".format(cycles + 1, headline))
            self._print("-" * 60)
            state.append_run_report(self.root, [
                "- mission [cycle {}]: {}".format(
                    cycles + 1, self._truncate(headline, 110))])
            self._notify("Ine · task started", self._truncate(headline))
            result = self._run_task(task, on_line=self._handle_line)
            self._print("")
            self._print("[cycle {}] worker exit code {}".format(
                cycles + 1, result.exit_code))
            if result.exit_code != 0 and result.output:
                self._print("[cycle {}] worker output (first 20 lines):"
                            .format(cycles + 1))
                for line in result.output.splitlines()[:20]:
                    self._print("  " + line)

            cycles += 1
            ran_any = True
            plan = state.read_plan(self.root)
            outcome = self._outcome(result, task, plan)
            task_id = task.identity

            if outcome == "done":
                state.append_run_report(self.root, [
                    "- [cycle {}] DONE".format(cycles)])
                self._print("[cycle {}] mission completed.".format(cycles))
                attempts = 0
                self._notify("Ine · task done", self._truncate(headline))

            elif outcome == "human":
                pending_human = True
                state.append_run_report(self.root, [
                    "- [cycle {}] HUMAN_DECISION_REQUIRED — recorded and "
                    "deferred".format(cycles)])
                item = plan.item(identity=task_id)
                if item is not None and item.executable:
                    state.mark_blocked(
                        self.root, task_id,
                        "mission requires commander judgment "
                        "(HUMAN_DECISION_REQUIRED); original text preserved")
                    state.append_blocker(
                        self.root, task.number, self._truncate(headline, 90),
                        "Worker signalled HUMAN_DECISION_REQUIRED during the "
                        "run; mission tagged BLOCKED (original text preserved) "
                        "and deferred so independent work continues. Awaiting "
                        "a commander resolution.")
                deferred.add(task_id)
                attempts = 0
                self._print(
                    "[cycle {}] HUMAN_DECISION_REQUIRED — mission recorded "
                    "and deferred; independent work continues."
                    .format(cycles))
                self._notify(
                    "Ine · decision required",
                    self._truncate(headline))

            elif outcome == "blocked":
                state.append_run_report(self.root, [
                    "- [cycle {}] BLOCKED — recorded and deferred"
                    .format(cycles)])
                deferred.add(task_id)
                attempts = 0
                self._print(
                    "[cycle {}] mission became blocked — recorded and "
                    "deferred; independent work continues.".format(cycles))
                self._notify(
                    "Ine · task blocked",
                    self._truncate(headline))

            elif outcome == "failed":
                had_failure = True
                state.append_run_report(self.root, [
                    "- [cycle {}] FAILED (worker exit {}) — recorded and "
                    "deferred".format(cycles, result.exit_code)])
                state.append_item_remark(
                    self.root, task_id,
                    "mission failed (worker exit {}); recorded and deferred "
                    "so independent work continues".format(result.exit_code))
                deferred.add(task_id)
                attempts = 0
                self._print(
                    "[cycle {}] mission failed (worker exit {}) — recorded "
                    "and deferred; independent work continues.".format(
                        cycles, result.exit_code))
                self._notify(
                    "Ine · task failed",
                    self._truncate(headline))

            else:  # stuck: exit 0 and the plan did not move
                state.append_run_report(self.root, [
                    "- [cycle {}] no plan progress".format(cycles)])
                attempts += 1
                self._print(
                    "[cycle {}] worker made no plan progress ({} of {} "
                    "attempts).".format(cycles, attempts, self.max_attempts))
                self._notify(
                    "Ine · task stuck",
                    self._truncate(headline))

            task = plan.first_executable(skip=deferred)

            after_usage = self._usage.snapshot()
            mission_delta = self._usage.delta(self._usage_prev, after_usage)
            self._usage_prev = after_usage
            if usage.has_usage(mission_delta):
                state.append_run_report(self.root, [
                    "- usage [cycle {}]: {}".format(
                        cycles, usage.format_delta(mission_delta))])
            self._usage_warning(after_usage["day_requests"])

        # Loop ended because `task` became None: every remaining item is
        # BLOCKED/DONE or deferred. Pick the honest exit code.
        if pending_human:
            return self._finish(
                STOP_HUMAN,
                "missions remain held for commander judgment; "
                "independent work completed.")
        if had_failure:
            return self._finish(
                STOP_ERROR,
                "missions deferred after failing; "
                "no executable work remains.")
        self._no_work()
        return self._finish(
            STOP_OK, None, print_message=False,
            report_summary="no executable work remains.")