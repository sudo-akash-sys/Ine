"""Focused tests for the ine-agent supervisor.

These tests never launch a real AI agent: the worker boundary is replaced
with a scripted stub, and CLI-level tests run with --dry-run or against
plan fixtures with no executable work.
"""

import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ine_agent import cli
from ine_agent import usage
from ine_agent.notifier import (
    NOTIFY_ENV, NullNotifier, WindowsPowerShellNotifier, create_notifier,
    default_chime_path, notifications_enabled,
)
from ine_agent.state import (
    ProjectError, append_blocker, append_item_remark, begin_run_report,
    end_run_report, find_project_root, human_decision_indicated, mark_blocked,
    output_marks_human_decision, read_plan, record_resolution,
    run_report_path,
)
from ine_agent.supervisor import (
    STOP_ERROR, STOP_HUMAN, STOP_OK, Supervisor, _mission_block,
)
from ine_agent.worker import CliWorker, OpenCodeWorker, StubWorker

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# `.tmp/` is gitignored temporary storage (see AGENTS.md / DECISIONS.md);
# every fixture root is stashed here and removed once the run finishes.
TMP = os.path.join(REPO_ROOT, ".tmp")

_CREATED_ROOTS = []


def make_root(plan, state_text="state", history_text="history",
              blockers_text="blockers", mission_prompt_text=None,
              mission_text=None):
    os.makedirs(TMP, exist_ok=True)
    root = tempfile.mkdtemp(prefix="ineagent-", dir=TMP)
    _CREATED_ROOTS.append(root)
    agent = os.path.join(root, ".agent")
    os.makedirs(agent)
    with open(os.path.join(agent, "PLAN.md"), "w", encoding="utf-8") as handle:
        handle.write(plan)
    with open(os.path.join(agent, "STATE.md"), "w", encoding="utf-8") as handle:
        handle.write(state_text)
    with open(os.path.join(agent, "HISTORY.md"), "w", encoding="utf-8") as handle:
        handle.write(history_text)
    with open(os.path.join(agent, "BLOCKERS.md"), "w", encoding="utf-8") as handle:
        handle.write(blockers_text)
    if mission_prompt_text is not None:
        with open(os.path.join(agent, "MISSION_PROMPT.md"), "w",
                  encoding="utf-8") as handle:
            handle.write(mission_prompt_text)
    if mission_text is not None:
        with open(os.path.join(agent, "MISSION.md"), "w",
                  encoding="utf-8") as handle:
            handle.write(mission_text)
    return root


def plan_containing(items):
    """Build a PLAN.md body with an Active section holding `items`.

    items: list of (tag, headline); tag None leaves the item unmarked.
    """
    lines = [
        "# .agent/PLAN.md",
        "",
        "## How an autonomous worker picks its next task",
        "",
        "- Selection rule: take the first EXECUTABLE item in list order.",
        "",
        "## Active — next smallest steps",
        "",
        "Each item is marked `EXECUTABLE` or `BLOCKED`.",
        "",
    ]
    for number, (tag, headline) in enumerate(items, 1):
        tag_text = "`{}`".format(tag) if tag else ""
        lines.append("{}. {} — **{}.**".format(number, tag_text, headline))
        lines.append("")
    return "\n".join(lines)


def plugin_text(headline):
    """The promoted-plan text used by scripted workers that finish a task."""
    def after(root):
        path = os.path.join(root, ".agent", "PLAN.md")
        plan = open(path, encoding="utf-8").read()
        kept = []
        number = 1
        for line in plan.splitlines():
            if re.match(r"^\s*\d+\.\s+", line):
                if headline in line:
                    continue
                line = re.sub(r"^\s*\d+", str(number), line)
                number += 1
            kept.append(line)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(kept))
    return after


def plugin_blocked_text(headline):
    """A BLOCKED outcome: the item is tagged BLOCKED (kept, renumbering the
    rest) — the realistic "hit an evidence wall" record."""
    def after(root):
        path = os.path.join(root, ".agent", "PLAN.md")
        plan = open(path, encoding="utf-8").read()
        kept = []
        number = 1
        for line in plan.splitlines():
            if re.match(r"^\s*\d+\.\s+", line):
                if headline in line:
                    line = re.sub(r"`EXECUTABLE`", "`BLOCKED`", line)
                else:
                    line = re.sub(r"^\s*\d+", str(number), line)
                    number += 1
            kept.append(line)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(kept))
    return after


def plugin_done_text(headline):
    """A finished task is marked `DONE` (renumbering the rest) instead of
    being deleted outright — the realistic summary the worker writes."""
    def after(root):
        path = os.path.join(root, ".agent", "PLAN.md")
        plan = open(path, encoding="utf-8").read()
        kept = []
        number = 1
        for line in plan.splitlines():
            if re.match(r"^\s*\d+\.\s+", line):
                if headline in line:
                    line = re.sub(r"`EXECUTABLE`", "`DONE`", line)
                else:
                    line = re.sub(r"^\s*\d+", str(number), line)
                    number += 1
            kept.append(line)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(kept))
    return after


class TrackingStub(StubWorker):
    def __init__(self, steps):
        super().__init__(steps)
        self.depth = 0
        self.overlaps = 0

    def run(self, root, prompt, on_line=None):
        self.depth += 1
        if self.depth > 1:
            self.overlaps += 1
        try:
            return super().run(root, prompt, on_line=on_line)
        finally:
            self.depth -= 1


class ProbeWorker(CliWorker):
    """Runs a probe script through the real CliWorker subprocess boundary."""

    name = "probe"
    cmd_name = "probe"
    env_var = None

    def __init__(self, script):
        self._script = script

    @property
    def default_args(self):
        return (self._script,)

    def _exe(self):
        return sys.executable


class ProbeOpenCodeWorker(OpenCodeWorker):
    """Same probe through the OpenCodeWorker run path (`--dir` branch)."""

    def __init__(self, script):
        self._script = script

    @property
    def default_args(self):
        return (self._script,)

    def _exe(self):
        return sys.executable


class ZeroUsage:
    """Scripted no-op usage reporter so supervisor tests never touch the
    real OpenCode database. Yields ZERO snapshots unless fed a queue."""

    def __init__(self, snapshots=None):
        self._queue = list(snapshots) if snapshots else []
        self.last = dict(usage.ZERO)

    def snapshot(self):
        if self._queue:
            self.last = self._queue.pop(0)
        return dict(self.last)

    def delta(self, before, after):
        return usage.delta(before, after)

    def has_usage(self, delta_dict):
        return usage.has_usage(delta_dict)

    def close(self):
        pass


# Emits UTF-8 whose bytes are undefined in cp1252 (0x90 in "\xd0\x90", and a
# lone trailing 0x90), plus a non-ASCII stderr line. The first stdout line
# is what made `subprocess.run(..., text=True)` crash with
# "UnicodeDecodeError: 'charmap' codec can't decode byte 0x90" on Windows.
PROBE_SCRIPT = (
    "import sys\n"
    "sys.stdout.buffer.write(b'caf\\xc3\\xa9 \\xd0\\x90 \\xe2\\x94\\x90\\n')\n"
    "sys.stdout.buffer.write(b'lone: \\x90\\n')\n"
    "sys.stdout.buffer.flush()\n"
    "sys.stderr.buffer.write(b'err: \\xd1\\x8f\\n')\n"
    "sys.stderr.buffer.flush()\n"
)


# Streaming probes. STREAM_PROBE emits labeled lines on both pipes a few at
# a time; BIG_PIPE_PROBE overfills both pipe buffers (256 KiB each, well over
# the OS pipe capacity) so a sequential reader would deadlock on the second
# write — the streaming drain must read both pipes concurrently.
STREAM_PROBE = (
    "import sys, time\n"
    "for i in range(5):\n"
    "    sys.stdout.write('out line {}'.format(i) + '\\n')\n"
    "    sys.stdout.flush()\n"
    "    time.sleep(0.01)\n"
    "for i in range(5):\n"
    "    sys.stderr.write('err line {}'.format(i) + '\\n')\n"
    "    sys.stderr.flush()\n"
    "    time.sleep(0.01)\n"
)

BIG_PIPE_PROBE = (
    "import sys\n"
    "sys.stdout.write('A' * 262144 + '\\n')\n"
    "sys.stdout.flush()\n"
    "sys.stderr.write('B' * 262144 + '\\n')\n"
    "sys.stderr.flush()\n"
)


class StateReadingTests(unittest.TestCase):
    def test_plan_parses_tags_and_executability(self):
        plan = plan_containing([
            ("BLOCKED", "first enumerated choice value (no evidence)"),
            ("DONE", "already completed task"),
            ("EXECUTABLE", "property-value completion"),
            ("CLAUDE_REVIEW", "design review of a risky rewrite"),
            (None, "unmarked item is executable"),
        ])
        parsed = read_plan(make_root(plan)).items
        self.assertEqual(len(parsed), 5)
        self.assertEqual(parsed[0].tag, "BLOCKED")
        self.assertFalse(parsed[0].executable)
        self.assertFalse(parsed[1].executable)
        self.assertTrue(parsed[2].executable)
        self.assertTrue(parsed[3].wants_claude_review)
        self.assertTrue(parsed[4].executable)
        self.assertIn("property-value completion", parsed[2].text)

    def test_done_items_are_not_picked_as_first_executable(self):
        plan = plan_containing([
            ("DONE", "finished first"),
            ("BLOCKED", "still blocked"),
            ("EXECUTABLE", "still to do"),
        ])
        first = read_plan(make_root(plan)).first_executable()
        self.assertIn("still to do", first.text)

    def test_first_executable_follows_list_order(self):
        plan = plan_containing([
            ("BLOCKED", "blocked item"),
            ("EXECUTABLE", "first workable"),
            ("EXECUTABLE", "second workable"),
        ])
        path = make_root(plan)
        first = read_plan(path).first_executable()
        self.assertIn("first workable", first.text)

    def test_no_active_section_means_no_work(self):
        root = make_root("# plan\n\nNo active section here.\n")
        self.assertIsNone(read_plan(root).first_executable())

    def test_missing_marker_files_means_no_human_gate(self):
        root = make_root(plan_containing([("EXECUTABLE", "x")]))
        self.assertFalse(human_decision_indicated(root))

    def test_marker_file_raises_human_gate(self):
        root = make_root(plan_containing([("EXECUTABLE", "x")]),
                         state_text="HUMAN_DECISION_REQUIRED\n")
        self.assertTrue(human_decision_indicated(root))

    def test_marker_in_prose_does_not_raise_human_gate(self):
        root = make_root(plan_containing([("EXECUTABLE", "x")]),
                         state_text="exit code 2 = HUMAN_DECISION_REQUIRED gate\n")
        self.assertFalse(human_decision_indicated(root))

    def test_output_marker_on_own_line_is_detected(self):
        self.assertTrue(output_marks_human_decision(
            "finished normally\nHUMAN_DECISION_REQUIRED\nneeds a decision"))

    def test_output_marker_line_with_reason_is_detected(self):
        self.assertTrue(output_marks_human_decision(
            "HUMAN_DECISION_REQUIRED: which containment is authoritative?"))

    def test_output_marker_mentioned_in_prose_is_not_a_stop(self):
        prose = ("Reviewed the guardrail: only a genuine decision would need "
                 "HUMAN_DECISION_REQUIRED, and this mission did not. "
                 "Completed it instead.")
        self.assertFalse(output_marks_human_decision(prose))

    def test_find_project_root_walks_up(self):
        root = make_root(plan_containing([("EXECUTABLE", "x")]))
        nested = os.path.join(root, "a", "b")
        os.makedirs(nested)
        self.assertEqual(find_project_root(nested), root)

    def test_find_project_root_refuses_bare_directory(self):
        bare = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, bare, True)
        with self.assertRaises(ProjectError):
            find_project_root(bare)


class MissionTests(unittest.TestCase):
    def test_mission_block_empty_when_no_files(self):
        root = make_root(plan_containing([("EXECUTABLE", "x")]))
        self.assertEqual(_mission_block(root), "")

    def test_mission_block_with_prompt_only(self):
        root = make_root(
            plan_containing([("EXECUTABLE", "x")]),
            mission_prompt_text="Autonomous rules for this project.\n",
        )
        block = _mission_block(root)
        self.assertIn("Autonomous rules for this project.", block)
        self.assertIn("MISSION (follow this as your autonomous operating rules):", block)

    def test_mission_block_with_context_only(self):
        root = make_root(
            plan_containing([("EXECUTABLE", "x")]),
            mission_text="Ine is a language for describing what, not how.\n",
        )
        block = _mission_block(root)
        self.assertIn("Ine is a language for describing what, not how.", block)
        self.assertIn("PROJECT CONTEXT:", block)

    def test_mission_block_with_both_files(self):
        root = make_root(
            plan_containing([("EXECUTABLE", "x")]),
            mission_prompt_text="Follow the rules.\n",
            mission_text="Ine context.\n",
        )
        block = _mission_block(root)
        self.assertIn("Follow the rules.", block)
        self.assertIn("Ine context.", block)
        self.assertIn("MISSION (follow this as your autonomous operating rules):", block)
        self.assertIn("PROJECT CONTEXT:", block)

    def test_impl_prompt_embeds_mission_content(self):
        root = make_root(
            plan_containing([("EXECUTABLE", "do the thing")]),
            mission_prompt_text="Always read before writing.\n",
            mission_text="Ine is a language.\n",
        )
        from ine_agent.supervisor import impl_prompt
        prompt = impl_prompt(root, read_plan(root).first_executable())
        self.assertIn("Always read before writing.", prompt)
        self.assertIn("Ine is a language.", prompt)
        self.assertIn("do the thing", prompt)
        # Step 1 no longer tells worker to read MISSION.md
        self.assertNotIn("Read AGENTS.md in full, then the .agent/ files (MISSION.md,", prompt)

    def test_review_prompt_embeds_mission_content(self):
        root = make_root(
            plan_containing([("CLAUDE_REVIEW", "review this")]),
            mission_prompt_text="Operate carefully.\n",
            mission_text="Project context here.\n",
        )
        from ine_agent.supervisor import review_prompt
        task = read_plan(root).first_executable()
        prompt = review_prompt(root, task)
        self.assertIn("Operate carefully.", prompt)
        self.assertIn("Project context here.", prompt)
        self.assertIn("review this", prompt)

    def test_impl_prompt_omits_mission_when_files_absent(self):
        root = make_root(plan_containing([("EXECUTABLE", "x")]))
        from ine_agent.supervisor import impl_prompt
        prompt = impl_prompt(root, read_plan(root).first_executable())
        self.assertNotIn("MISSION (follow this as your autonomous operating rules):", prompt)
        self.assertNotIn("PROJECT CONTEXT:", prompt)


class SupervisorTests(unittest.TestCase):
    def _run(self, root, worker=None, factory=None, **kwargs):
        if worker is None and factory is None:
            worker = StubWorker([])
        if factory is None:
            factory = lambda name: worker
        out = io.StringIO()
        kwargs["usage_reporter"] = ZeroUsage()
        code = Supervisor(root, worker_factory=factory, out=out, **kwargs).run()
        calls = [] if worker is None else list(worker.calls)
        return code, out.getvalue(), calls, worker

    def test_no_executable_work_is_a_clean_stop(self):
        root = make_root(plan_containing([("BLOCKED", "blocked only")]))
        code, out, calls, _ = self._run(root)
        self.assertEqual(code, STOP_OK)
        self.assertIn("No executable work remains.", out)
        self.assertIn("ine-agent stopped normally.", out)
        self.assertEqual(calls, [])

    def test_executable_work_invokes_the_worker(self):
        root = make_root(plan_containing([("EXECUTABLE", "do the thing")]))
        worker = StubWorker([(0, "", plugin_text("do the thing"))])
        code, out, calls, _ = self._run(root, worker=worker)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 1)
        self.assertIn("do the thing", calls[0]["prompt"])
        self.assertIn("No executable work remains.", out)

    def test_human_decision_from_worker_output_stops_immediately(self):
        root = make_root(plan_containing([("EXECUTABLE", "risky task")]))
        worker = StubWorker([(0, "HUMAN_DECISION_REQUIRED\nneeds a call")])
        code, out, calls, _ = self._run(root, worker=worker, max_attempts=5)
        self.assertEqual(code, STOP_HUMAN)
        self.assertEqual(len(calls), 1)
        self.assertIn("HUMAN_DECISION_REQUIRED", out)

    def test_human_decision_from_state_file_stops_before_worker(self):
        root = make_root(
            plan_containing([("EXECUTABLE", "anything")]),
            state_text="pending\nHUMAN_DECISION_REQUIRED\n",
        )
        worker = StubWorker([])
        code, out, calls, _ = self._run(root, worker=worker)
        self.assertEqual(code, STOP_HUMAN)
        self.assertIn("HUMAN_DECISION_REQUIRED", out)
        self.assertEqual(calls, [])

    def test_prose_marker_mention_does_not_stop_the_loop(self):
        # Regression (Session 38): the guardrail phrase lives in the worker's
        # own prompt, so a completed transcript can mention it in prose
        # without flagging a decision. The mission WAS completed and marked
        # DONE; the loop must finish normally, not stop on fake judgment.
        root = make_root(plan_containing([("EXECUTABLE", "do it")]))
        worker = StubWorker([(
            0,
            "Checked the guardrail: HUMAN_DECISION_REQUIRED applies only to\n"
            "genuine commander decisions, which this task did not need.\n",
            plugin_done_text("do it"),
        )])
        code, out, calls, _ = self._run(root, worker=worker)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("commander judgment", out)
        self.assertIn("No executable work remains.", out)

    def test_own_line_marker_still_stops_and_reports_fresh_tag(self):
        # A real stop marker (its own line) still halts with exit 2. The run
        # records and defers the mission, and since the worker had ALREADY
        # marked it DONE, the final message must not present it as an
        # abandoned EXECUTABLE one (the plan shows the fresh DONE tag).
        root = make_root(plan_containing([("EXECUTABLE", "do it")]))
        worker = StubWorker([(
            0, "findings summarized.\nHUMAN_DECISION_REQUIRED\nscope",
            plugin_done_text("do it"),
        )])
        code, out, calls, _ = self._run(root, worker=worker)
        self.assertEqual(code, STOP_HUMAN)
        self.assertEqual(len(calls), 1)
        stop_lines = [l for l in out.splitlines() if "commander judgment" in l]
        self.assertIn("commander judgment", " ".join(stop_lines))
        for stop_line in stop_lines:
            self.assertNotIn("`EXECUTABLE`", stop_line)
        plan_text = open(os.path.join(root, ".agent", "PLAN.md"),
                         encoding="utf-8").read()
        self.assertIn("`DONE`", plan_text)

    def test_review_prose_marker_does_not_stop_the_loop(self):
        # The optional Claude review branch uses the same line-based gate; a
        # prose mention in the review output must not halt the run.
        root = make_root(plan_containing([("CLAUDE_REVIEW", "design the change")]))
        def flip_tag(root):
            path = os.path.join(root, ".agent", "PLAN.md")
            plan = open(path, encoding="utf-8").read()
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(plan.replace("`CLAUDE_REVIEW`", "`DONE`"))

        def factory(name):
            if name == "claude":
                return StubWorker([(
                    0, "Review done; HUMAN_DECISION_REQUIRED is only for real "
                    "decisions, none here.",
                )])
            return StubWorker([(0, "implemented.", flip_tag)])
        code, out, _, _ = self._run(root, factory=factory)
        self.assertEqual(code, STOP_OK)
        self.assertNotIn("commander judgment", out)
        self.assertIn("No executable work remains.", out)

    def test_worker_failure_is_recorded_deferred_and_stops_with_error(self):
        # Session 41 semantics: a failing worker no longer retries to
        # max_attempts. The failure is recorded on the PLAN item and the
        # mission deferred so independent work continues; when it is the only
        # task, the run ends with the documented error code (exit 1) — the
        # message reports the deferred failure, not a bogus bounded-stop.
        root = make_root(plan_containing([("EXECUTABLE", "always fails")]))
        worker = StubWorker([(1, "boom")] * 10)
        code, out, calls, _ = self._run(root, worker=worker, max_attempts=2)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 1)
        self.assertIn("mission failed (worker exit 1) — recorded and "
                      "deferred", out)
        self.assertIn("missions deferred after failing", out)
        self.assertIn("no executable work remains", out)

    def test_successful_cycle_advances_and_rereads_state(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "first task"),
            ("EXECUTABLE", "second task"),
        ]))
        worker = StubWorker([
            (0, "", plugin_text("first task")),
            (0, "", plugin_text("second task")),
        ])
        code, out, calls, _ = self._run(root, worker=worker)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 2)
        self.assertIn("first task", calls[0]["prompt"])
        self.assertIn("second task", calls[1]["prompt"])

    def test_done_marked_task_does_not_stop_the_loop(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "first task"),
            ("EXECUTABLE", "second task"),
        ]))
        worker = StubWorker([
            (0, "", plugin_done_text("first task")),
            (0, "", plugin_done_text("second task")),
        ])
        code, out, calls, _ = self._run(root, worker=worker)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 2)
        self.assertIn("first task", calls[0]["prompt"])
        self.assertIn("second task", calls[1]["prompt"])
        self.assertNotIn("could not advance", out)

    def test_workers_are_sequential_not_concurrent(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "one"),
            ("EXECUTABLE", "two"),
            ("EXECUTABLE", "three"),
        ]))
        worker = TrackingStub([
            (0, "", plugin_text("one")),
            (0, "", plugin_text("two")),
            (0, "", plugin_text("three")),
        ])
        code, out, calls, _ = self._run(root, worker=worker)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 3)
        self.assertEqual(worker.overlaps, 0)

    def test_dry_run_does_not_launch_a_worker(self):
        root = make_root(plan_containing([("EXECUTABLE", "something")]))
        def factory(name):
            raise AssertionError("no worker may be launched in dry-run")
        code, out, _, _ = self._run(root, factory=factory, dry_run=True)
        self.assertEqual(code, STOP_OK)
        self.assertIn("[dry-run]", out)

    def test_cycle_limit_is_a_hard_bound(self):
        # A worker that never advances but never fails must be bounded.
        root = make_root(plan_containing([("EXECUTABLE", "stays put")]))
        worker = StubWorker([(0, "")] * 30)
        code, out, calls, _ = self._run(
            root, worker=worker, max_cycles=3, max_attempts=20)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 3)
        self.assertIn("maximum of 3 worker cycle", out)


    def test_live_worker_output_is_relayed_and_summarized(self):
        root = make_root(plan_containing([("EXECUTABLE", "do it")]))
        worker = StubWorker([(0, "step one\nstep two\n", plugin_text("do it"))])
        code, out, calls, _ = self._run(root, worker=worker)
        self.assertEqual(code, STOP_OK)
        self.assertIn("mission:", out)
        self.assertIn("do it", out)
        self.assertIn("  step one", out)
        self.assertIn("  step two", out)
        self.assertIn("worker exit code 0", out)
        self.assertIn("No executable work remains.", out)

    def test_quiet_mode_hides_live_lines(self):
        root = make_root(plan_containing([("EXECUTABLE", "do it")]))
        worker = StubWorker([(0, "step one\n", plugin_text("do it"))])
        code, out, calls, _ = self._run(root, worker=worker, quiet=True)
        self.assertEqual(code, STOP_OK)
        self.assertIn("mission:", out)
        self.assertIn("worker exit code 0", out)
        self.assertNotIn("step one", out)

    def test_verbose_mode_relays_lines_raw_and_unindented(self):
        root = make_root(plan_containing([("EXECUTABLE", "do it")]))
        worker = StubWorker([(0, "step one\n", plugin_text("do it"))])
        code, out, calls, _ = self._run(root, worker=worker, verbose=True)
        self.assertEqual(code, STOP_OK)
        self.assertIn("step one", out)
        self.assertNotIn("  step one", out)


class UsageTests(unittest.TestCase):
    """Read-only telemetry plus the supervisor's warn-only wiring.

    Uses a throwaway sqlite database with the same minimal shape as
    `opencode.db` (session / message + JSON `data`), so nothing here touches
    the real OpenCode database.
    """

    def _db(self):
        os.makedirs(TMP, exist_ok=True)
        folder = tempfile.mkdtemp(prefix="usage-", dir=TMP)
        self.addCleanup(shutil.rmtree, folder, True)
        conn = sqlite3.connect(os.path.join(folder, "opencode.db"))
        conn.execute(
            "create table session (id text primary key, title text, "
            "model text, cost real, time_created integer)")
        conn.execute(
            "create table message (id text primary key, session_id text, "
            "time_created integer, data text)")
        conn.commit()
        return conn

    def _session(self, conn, sid, title, created_ms, cost=0.0):
        conn.execute(
            "insert into session (id, title, model, cost, time_created) "
            "values (?,?,?,?,?)",
            (sid, title, "{}", cost, created_ms))

    def _message(self, conn, sid, mid, created_ms, role, model,
                 tin=0, tout=0, reasoning=0):
        data = json.dumps({
            "role": role,
            "modelID": model,
            "tokens": {"input": tin, "output": tout, "reasoning": reasoning},
        })
        conn.execute(
            "insert into message (id, session_id, time_created, data) "
            "values (?,?,?,?)",
            (mid, sid, created_ms, data))

    def _now(self):
        return int(time.time() * 1000)

    def test_assistant_messages_count_as_requests(self):
        conn = self._db()
        self._session(conn, "s1", "session one", self._now())
        self._message(conn, "s1", "m1", self._now(), "assistant", "big-pickle", 10, 20)
        self._message(conn, "s1", "m2", self._now(), "assistant", "big-pickle", 5, 5)
        self._message(conn, "s1", "m3", self._now(), "user", "big-pickle", 40, 0)
        snap = usage.snapshot(conn)
        self.assertEqual(snap["requests"], 2)
        self.assertEqual(snap["tokens_input"], 15)
        self.assertEqual(snap["tokens_output"], 25)
        self.assertEqual(snap["by_model"], {"big-pickle": 2})

    def test_day_requests_only_counts_today(self):
        conn = self._db()
        self._session(conn, "s1", "s", self._now())
        self._message(conn, "s1", "today", self._now(), "assistant", "big-pickle")
        self._message(
            conn, "s1", "old",
            self._now() - 3 * 86400 * 1000, "assistant", "big-pickle")
        self.assertEqual(usage.snapshot(conn)["day_requests"], 1)

    def test_snapshot_breaks_down_by_session(self):
        conn = self._db()
        self._session(conn, "a", "older session", self._now() - 1000)
        self._session(conn, "b", "newer session", self._now())
        self._message(conn, "b", "m1", self._now(), "assistant", "big-pickle", 3, 4)
        self._message(conn, "a", "m2", self._now() - 1000, "assistant", "big-pickle", 1, 1)
        snap = usage.snapshot(conn)
        self.assertEqual([s["id"] for s in snap["sessions"]], ["b", "a"])
        by_id = {s["id"]: s for s in snap["sessions"]}
        self.assertEqual(by_id["b"]["requests"], 1)
        self.assertEqual(by_id["a"]["tokens_input"], 1)
        self.assertEqual(snap["cost"], 0.0)

    def test_delta_sums_the_observed_window(self):
        conn = self._db()
        self._session(conn, "s1", "s", self._now())
        self._message(conn, "s1", "m1", self._now(), "assistant", "big-pickle", 10, 10)
        self._message(conn, "s1", "m2", self._now(), "assistant", "big-pickle", 10, 10)
        before = usage.snapshot(conn)
        self._message(conn, "s1", "m3", self._now(), "assistant", "big-pickle", 7, 9)
        self._message(conn, "s1", "m4", self._now(), "user", "big-pickle", 50, 0)
        diff = usage.delta(before, usage.snapshot(conn))
        self.assertEqual(diff["requests"], 1)
        self.assertEqual(diff["tokens_input"], 7)
        self.assertEqual(diff["tokens_output"], 9)
        self.assertEqual(diff["by_model"], {"big-pickle": 1})
        self.assertTrue(usage.has_usage(diff))
        self.assertFalse(usage.has_usage({k: 0 for k in usage.ZERO}))

    def test_unreadable_database_degrades_to_zero(self):
        self.assertEqual(usage.snapshot(None), usage.ZERO)
        reporter = usage.UsageReporter(path=os.path.join(
            TMP, "missing-opencode", "opencode.db"))
        self.assertEqual(reporter.snapshot(), usage.ZERO)

    def _run(self, root, worker=None, notifier=None, **kwargs):
        if worker is None:
            worker = StubWorker([])
        out = io.StringIO()
        kwargs["notifier"] = notifier or RecordingNotifier()
        code = Supervisor(
            root, worker_factory=lambda name: worker, out=out, **kwargs).run()
        return code, out.getvalue(), worker

    def test_supervisor_records_mission_and_run_usage(self):
        root = make_root(plan_containing([("EXECUTABLE", "do the thing")]))
        worker = StubWorker([(0, "", plugin_text("do the thing"))])
        s1 = dict(usage.ZERO, requests=3, day_requests=3)
        del s1["by_model"], s1["sessions"]
        s1["by_model"] = {"big-pickle": 1}
        s1["sessions"] = []
        reporter = ZeroUsage([dict(usage.ZERO), s1, dict(s1)])
        code, out, run_worker = self._run(
            root, worker=worker, usage_reporter=reporter,
            usage_warn_requests=100)
        self.assertEqual(code, STOP_OK)
        report = open(run_report_path(root), encoding="utf-8").read()
        self.assertIn("- usage start:", report)
        self.assertIn("- usage [cycle 1]: +3 requests", report)
        self.assertIn("- usage delta (run): +3 requests", report)
        self.assertNotIn("usage warning", out)

    def test_usage_warning_warns_once_and_notifies_commander(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "first task"),
            ("EXECUTABLE", "second task"),
        ]))
        worker = StubWorker([
            (0, "", plugin_done_text("first task")),
            (0, "", plugin_done_text("second task")),
        ])
        start = dict(usage.ZERO)
        del start["by_model"], start["sessions"]
        start["by_model"] = {}
        start["sessions"] = []
        cycle1 = dict(start, requests=3, day_requests=3)  # below threshold
        cycle2 = dict(start, requests=7, day_requests=7)  # crosses threshold
        cycle2["by_model"] = {"big-pickle": 4}
        reporter = ZeroUsage([start, cycle1, cycle2, cycle2])
        notifier = RecordingNotifier()
        code, out, run_worker = self._run(
            root, worker=worker, notifier=notifier,
            usage_reporter=reporter, usage_warn_requests=5)
        self.assertEqual(code, STOP_OK)
        self.assertIn("[usage] Observed OpenCode usage today reached 7 requests", out)
        report = open(run_report_path(root), encoding="utf-8").read()
        self.assertIn("- usage warning:", report)
        titles = [title for title, _, _ in notifier.calls]
        self.assertEqual(titles.count("Ine · usage warning"), 1)


class ExitCodeContractTests(unittest.TestCase):
    """Pin the documented exit-code mapping at the supervisor boundary for
    each stop class (Mission 29 documented these as intentional; Mission 50
    pins them so refactors cannot silently change the contract).

    Stop class        | exit code | STOP_* constant
    ------------------+-----------+----------------
    no-executable-work|     0     | STOP_OK
    bounded stop      |     1     | STOP_ERROR
    human-gate        |     2     | STOP_HUMAN
    """

    def _run(self, root, worker=None, factory=None, **kwargs):
        if worker is None and factory is None:
            worker = StubWorker([])
        if factory is None:
            factory = lambda name: worker
        out = io.StringIO()
        kwargs["usage_reporter"] = ZeroUsage()
        code = Supervisor(root, worker_factory=factory, out=out, **kwargs).run()
        calls = [] if worker is None else list(worker.calls)
        return code, out.getvalue(), calls, worker

    def _last_exit_code_in_report(self, root):
        report = open(run_report_path(root), encoding="utf-8").read()
        for line in reversed(report.splitlines()):
            if line.startswith("- exit:"):
                return int(line.split(":")[1].strip())
        return None

    # --- STOP_OK (exit 0) ---------------------------------------------------

    def test_no_executable_work_exits_zero(self):
        root = make_root(plan_containing([("BLOCKED", "blocked only")]))
        code, out, calls, _ = self._run(root)
        self.assertEqual(code, 0)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(calls, [])

    def test_dry_run_exits_zero(self):
        root = make_root(plan_containing([("EXECUTABLE", "would run")]))
        code, out, calls, _ = self._run(root, dry_run=True)
        self.assertEqual(code, 0)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(calls, [])

    def test_all_tasks_completed_exits_zero(self):
        root = make_root(plan_containing([("EXECUTABLE", "only task")]))
        worker = StubWorker([(0, "", plugin_text("only task"))])
        code, out, calls, _ = self._run(root, worker=worker)
        self.assertEqual(code, 0)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(self._last_exit_code_in_report(root), 0)

    # --- STOP_ERROR (exit 1) — bounded stop: attempts limit ------------------

    def test_attempts_limit_exits_one(self):
        root = make_root(plan_containing([("EXECUTABLE", "stuck task")]))
        worker = StubWorker([(0, "")] * 30)
        code, out, calls, _ = self._run(
            root, worker=worker, max_attempts=2, max_cycles=20)
        self.assertEqual(code, 1)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 2)
        self.assertIn("could not advance the plan", out)
        self.assertIn("2 attempt(s)", out)
        self.assertEqual(self._last_exit_code_in_report(root), 1)

    # --- STOP_ERROR (exit 1) — bounded stop: cycle limit ---------------------

    def test_cycle_limit_exits_one(self):
        root = make_root(plan_containing([("EXECUTABLE", "stays put")]))
        worker = StubWorker([(0, "")] * 30)
        code, out, calls, _ = self._run(
            root, worker=worker, max_cycles=3, max_attempts=20)
        self.assertEqual(code, 1)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 3)
        self.assertIn("maximum of 3 worker cycle", out)
        self.assertEqual(self._last_exit_code_in_report(root), 1)

    # --- STOP_ERROR (exit 1) — worker failure --------------------------------

    def test_worker_failure_exits_one(self):
        root = make_root(plan_containing([("EXECUTABLE", "fails")]))
        worker = StubWorker([(1, "boom")])
        code, out, calls, _ = self._run(
            root, worker=worker, max_attempts=2)
        self.assertEqual(code, 1)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 1)
        self.assertIn("mission failed (worker exit 1)", out)
        self.assertEqual(self._last_exit_code_in_report(root), 1)

    # --- STOP_HUMAN (exit 2) — worker output marker --------------------------

    def test_worker_human_marker_exits_two(self):
        root = make_root(plan_containing([("EXECUTABLE", "risky task")]))
        worker = StubWorker([(0, "HUMAN_DECISION_REQUIRED\nneeds a call")])
        code, out, calls, _ = self._run(root, worker=worker)
        self.assertEqual(code, 2)
        self.assertEqual(code, STOP_HUMAN)
        self.assertEqual(len(calls), 1)
        self.assertIn("HUMAN_DECISION_REQUIRED", out)
        self.assertEqual(self._last_exit_code_in_report(root), 2)

    # --- STOP_HUMAN (exit 2) — pre-existing state gate ----------------------

    def test_pre_existing_state_gate_exits_two(self):
        root = make_root(
            plan_containing([("EXECUTABLE", "anything")]),
            state_text="pending\nHUMAN_DECISION_REQUIRED\n",
        )
        worker = StubWorker([])
        code, out, calls, _ = self._run(root, worker=worker)
        self.assertEqual(code, 2)
        self.assertEqual(code, STOP_HUMAN)
        self.assertEqual(calls, [])
        self.assertIn("HUMAN_DECISION_REQUIRED", out)

    # --- STOP_HUMAN (exit 2) — mid-run gate appears --------------------------

    def test_mid_run_gate_exits_two(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "writes gate"),
            ("EXECUTABLE", "never runs"),
        ]))
        def _write_gate(root):
            with open(os.path.join(root, ".agent", "STATE.md"), "a",
                       encoding="utf-8") as fh:
                fh.write("\nHUMAN_DECISION_REQUIRED\n")
        worker = StubWorker([(0, "done", _write_gate)])
        code, out, calls, _ = self._run(
            root, worker=worker, max_attempts=10)
        self.assertEqual(code, 2)
        self.assertEqual(code, STOP_HUMAN)
        self.assertEqual(len(calls), 1)
        self.assertIn("HUMAN_DECISION_REQUIRED", out)
        self.assertIn("commander judgment required", out)
        self.assertEqual(self._last_exit_code_in_report(root), 2)


class CrashContinueTests(unittest.TestCase):
    """Mission 51: crash-then-continue resilience.

    The missing combined case from Mission 29(b): a worker exits nonzero BUT
    its side effect already advanced the plan — it marked its task DONE before
    failing. That identity change is a completion, not a failure and not a
    stuck attempt: the supervisor must detect it, reset `attempts`, continue
    to the NEXT EXECUTABLE task on the following cycle, and never bounded-stop
    on the crashed worker.
    """

    def _run(self, root, worker=None, factory=None, **kwargs):
        if worker is None and factory is None:
            worker = StubWorker([])
        if factory is None:
            factory = lambda name: worker
        out = io.StringIO()
        kwargs["usage_reporter"] = ZeroUsage()
        code = Supervisor(root, worker_factory=factory, out=out, **kwargs).run()
        calls = [] if worker is None else list(worker.calls)
        return code, out.getvalue(), calls, worker

    def test_crash_after_marking_done_continues_not_bounded_stop(self):
        # Worker 1 exits 1 but marks its own task DONE on disk first. The
        # supervisor must classify the advanced state as done (not failed, not
        # stuck) and run the next executable task to completion.
        root = make_root(plan_containing([
            ("EXECUTABLE", "crashes after committing"),
            ("EXECUTABLE", "still must run"),
        ]))
        worker = StubWorker([
            (1, "killed after committing",
             plugin_done_text("crashes after committing")),
            (0, "", plugin_done_text("still must run")),
        ])
        code, out, calls, _ = self._run(
            root, worker=worker, max_attempts=2, max_cycles=10)
        self.assertEqual(code, STOP_OK)       # a completion, not a failure
        self.assertEqual(len(calls), 2)       # the next task actually ran
        self.assertIn("crashes after committing", calls[0]["prompt"])
        self.assertIn("still must run", calls[1]["prompt"])
        self.assertNotIn("could not advance the plan", out)
        self.assertNotIn("mission failed", out)
        self.assertNotIn("deferred", out)
        self.assertIn("mission completed", out)
        # The crashed worker's on-disk progress is preserved, never re-picked.
        self.assertEqual(read_plan(root).items[0].tag, "DONE")

    def test_crash_after_advance_confers_a_full_attempt_budget(self):
        # If the crash-after-advance counted as a stuck attempt, a
        # max_attempts=1 supervisor would bounded-stop before the next task
        # ever ran. Advancement must reset attempts to 0.
        root = make_root(plan_containing([
            ("EXECUTABLE", "crash plus advance"),
            ("EXECUTABLE", "runner-up"),
        ]))
        worker = StubWorker([
            (1, "crashed", plugin_done_text("crash plus advance")),
            (0, "", plugin_done_text("runner-up")),
        ])
        code, out, calls, _ = self._run(
            root, worker=worker, max_attempts=1, max_cycles=10)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 2)
        self.assertIn("runner-up", calls[1]["prompt"])
        self.assertNotIn("could not advance the plan", out)

    def test_run_report_records_advanced_crash_as_done(self):
        # The durable record must match the classification: a crashed-but-
        # advanced cycle is DONE and the run closes clean (exit 0), not
        # deferred as a failure.
        root = make_root(plan_containing([
            ("EXECUTABLE", "crash then done"),
        ]))
        worker = StubWorker([
            (1, "bang", plugin_done_text("crash then done")),
        ])
        code, out, calls, _ = self._run(root, worker=worker)
        self.assertEqual(code, STOP_OK)
        report = open(run_report_path(root), encoding="utf-8").read()
        self.assertIn("- [cycle 1] DONE", report)
        self.assertIn("- exit: 0", report)


class AttemptResetTests(unittest.TestCase):
    """Mission 52: attempts reset on progress.

    Pins the attempts semantics behind the Mission 30 premature-stop fix: a
    cycle that makes NO plan progress increments `attempts`, but ANY cycle
    whose plan changed (DONE / BLOCKED / failed / human) resets it to 0 — so
    a worker alternating progress and no-progress runs until no work remains
    instead of bounded-stopping early, while the bounded-stop guard still
    fires whenever attempts genuinely accumulate.
    """

    def _run(self, root, worker=None, factory=None, **kwargs):
        if worker is None and factory is None:
            worker = StubWorker([])
        if factory is None:
            factory = lambda name: worker
        out = io.StringIO()
        kwargs["usage_reporter"] = ZeroUsage()
        code = Supervisor(root, worker_factory=factory, out=out, **kwargs).run()
        calls = [] if worker is None else list(worker.calls)
        return code, out.getvalue(), calls, worker

    def test_alternating_progress_and_stuck_runs_to_completion(self):
        # Stuck (no progress) increments attempts; the following progress
        # resets to 0. Without the reset the attempts would accumulate 1, 1,
        # 2 and the loop would bounded-stop before the last task — with it,
        # all work finishes (exit 0).
        root = make_root(plan_containing([
            ("EXECUTABLE", "first task"),
            ("EXECUTABLE", "second task"),
        ]))
        worker = StubWorker([
            (0, ""),                                   # cycle 1: stuck
            (0, "", plugin_done_text("first task")),   # cycle 2: progress
            (0, ""),                                   # cycle 3: stuck
            (0, "", plugin_done_text("second task")),  # cycle 4: progress
        ])
        code, out, calls, _ = self._run(
            root, worker=worker, max_attempts=2, max_cycles=10)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 4)
        self.assertNotIn("could not advance the plan", out)
        # Per-cycle classification is recorded durably and honestly.
        report = open(run_report_path(root), encoding="utf-8").read()
        self.assertIn("- [cycle 1] no plan progress", report)
        self.assertIn("- [cycle 2] DONE", report)
        self.assertIn("- [cycle 3] no plan progress", report)
        self.assertIn("- [cycle 4] DONE", report)
        self.assertIn("- exit: 0", report)

    def test_progress_after_stuck_gives_the_next_task_fresh_attempts(self):
        # A task that completes cleanly resets the counter before the next
        # task starts; the next task's own stuck phase then gets a full
        # `max_attempts` budget (here: one stuck cycle then completion).
        root = make_root(plan_containing([
            ("EXECUTABLE", "clean finish"),
            ("EXECUTABLE", "needs retry"),
        ]))
        worker = StubWorker([
            (0, "", plugin_done_text("clean finish")),
            (0, ""),                                    # stuck, attempt 1
            (0, "", plugin_done_text("needs retry")),    # progress, reset
        ])
        code, out, calls, _ = self._run(
            root, worker=worker, max_attempts=2, max_cycles=10)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 3)
        self.assertNotIn("could not advance the plan", out)

    def test_reset_does_not_disable_the_bounded_stop_guard(self):
        # A reset grants no immunity: genuine consecutive no-progress cycles
        # AFTER a reset still accumulate and bounded-stop at `max_attempts`.
        root = make_root(plan_containing([
            ("EXECUTABLE", "accomplished"),
            ("EXECUTABLE", "stuck forever"),
        ]))
        worker = StubWorker([
            (0, "", plugin_done_text("accomplished")),  # done, resets to 0
            (0, ""),                                    # stuck, attempt 1
            (0, ""),                                    # stuck, attempt 2
        ])
        code, out, calls, _ = self._run(
            root, worker=worker, max_attempts=2, max_cycles=10)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 3)
        self.assertIn("could not advance the plan after 2 attempt(s)", out)


class CliTests(unittest.TestCase):
    def test_entry_point_help_exits_zero(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "src", "ine_agent", "cli.py"),
             "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("ine-agent", proc.stdout)
        self.assertIn("run", proc.stdout)

    def test_project_scripts_registers_both_entry_points(self):
        pyproject = open(os.path.join(REPO_ROOT, "pyproject.toml"),
                         encoding="utf-8").read()
        self.assertIn('ine = "ine.cli:main"', pyproject)
        self.assertIn('ine-agent = "ine_agent.cli:main"', pyproject)

    def test_run_subcommand_help_shows_stream_flags(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "src", "ine_agent", "cli.py"),
             "run", "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--verbose", proc.stdout)
        self.assertIn("--quiet", proc.stdout)

    def test_cli_no_work_repo_stops_cleanly_without_agents(self):
        root = make_root(plan_containing([("BLOCKED", "nothing doable")]))
        proc = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "src", "ine_agent", "cli.py"),
             "run", "--root", root, "--worker", "opencode"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, STOP_OK)
        self.assertIn("No executable work remains.", proc.stdout)

    def test_cli_dry_run_on_the_real_repository(self):
        code = cli.main(["run", "--root", REPO_ROOT, "--dry-run"])
        self.assertEqual(code, STOP_OK)

    def test_usage_warn_requests_flag_wins_over_env(self):
        from ine_agent.cli import _usage_warn_requests
        args = mock.Mock(usage_warn_requests=7)
        with mock.patch.dict(
                os.environ, {"INE_AGENT_USAGE_WARN_REQUESTS": "3"},
                clear=False):
            self.assertEqual(_usage_warn_requests(args), 7)
        args = mock.Mock(usage_warn_requests=None)
        with mock.patch.dict(
                os.environ, {"INE_AGENT_USAGE_WARN_REQUESTS": "3"},
                clear=False):
            self.assertEqual(_usage_warn_requests(args), 3)
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(_usage_warn_requests(mock.Mock(usage_warn_requests=None)))
        with mock.patch.dict(
                os.environ, {"INE_AGENT_USAGE_WARN_REQUESTS": "not-a-number"},
                clear=False):
            self.assertIsNone(_usage_warn_requests(mock.Mock(usage_warn_requests=None)))

    def test_run_subcommand_help_shows_usage_warn_flag(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "src", "ine_agent", "cli.py"),
             "run", "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--usage-warn-requests", proc.stdout)

    def test_cli_rejects_a_missing_project_root(self):
        missing = os.path.join(TMP, "no-such-project")
        self.assertEqual(cli.main(["run", "--root", missing]), 1)

    def test_cli_run_accepts_stream_flags(self):
        root = make_root(plan_containing([("BLOCKED", "nothing doable")]))
        code = cli.main(["run", "--root", root, "--quiet"])
        self.assertEqual(code, STOP_OK)
        code = cli.main(["run", "--root", root, "--verbose"])
        self.assertEqual(code, STOP_OK)

    def test_cli_rejects_quiet_and_verbose_together(self):
        root = make_root(plan_containing([("BLOCKED", "nothing doable")]))
        code = cli.main(["run", "--root", root, "--quiet", "--verbose"])
        self.assertEqual(code, 1)

    def test_supervisor_rejects_an_unknown_worker_name(self):
        root = make_root(plan_containing([("EXECUTABLE", "x")]))
        from ine_agent.worker import build_worker
        with self.assertRaises(ValueError):
            Supervisor(
                root,
                worker_factory=build_worker,
                impl_worker="not-a-worker",
            )._worker("not-a-worker")


class WorkerEncodingTests(unittest.TestCase):
    """The worker subprocess boundary must survive UTF-8 output.

    Regression: `subprocess.run(..., text=True)` without an explicit
    encoding decoded with the locale codec (cp1252 on Windows), raising
    UnicodeDecodeError on bytes like 0x90.
    """

    def _probe_script(self, root):
        path = os.path.join(root, "probe_encoding.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(PROBE_SCRIPT)
        return path

    def _assert_utf8_preserved(self, result):
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.ok)
        # "caf\u00e9 \u0410 \u2510" is "café А ┐", whose bytes contain the
        # cp1252-undefined 0x90 that used to crash the decode.
        self.assertIn("caf\u00e9 \u0410 \u2510", result.output)
        self.assertIn("err: \u044f", result.output)

    def test_cli_worker_decodes_utf8_without_cp1252_crash(self):
        root = make_root(plan_containing([("EXECUTABLE", "probe")]))
        result = ProbeWorker(self._probe_script(root)).run(root, "probe")
        self._assert_utf8_preserved(result)

    def test_opencode_worker_decodes_utf8_without_cp1252_crash(self):
        root = make_root(plan_containing([("EXECUTABLE", "probe")]))
        result = ProbeOpenCodeWorker(self._probe_script(root)).run(root, "probe")
        self._assert_utf8_preserved(result)

    def test_lone_non_utf8_byte_is_preserved_not_dropped(self):
        root = make_root(plan_containing([("EXECUTABLE", "probe")]))
        result = ProbeWorker(self._probe_script(root)).run(root, "probe")
        # The lone trailing 0x90 decodes as surrogate U+DC90: the byte is
        # preserved losslessly, never discarded.
        self.assertIn("\udc90", result.output)


class WorkerStreamingTests(unittest.TestCase):
    """Live line relay over the worker subprocess boundary."""

    def _probe(self, root, script):
        path = os.path.join(root, "probe_stream.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(script)
        return path

    def test_stream_relays_lines_and_still_captures_output(self):
        root = make_root(plan_containing([("EXECUTABLE", "probe")]))
        seen = []
        result = ProbeWorker(self._probe(root, STREAM_PROBE)).run(
            root, "probe", on_line=seen.append)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("out line 0", result.output)
        self.assertIn("err line 4", result.output)
        relayed = "".join(seen)
        self.assertIn("out line 0", relayed)
        self.assertIn("err line 0", relayed)

    def test_stream_drains_large_pipes_without_deadlock(self):
        root = make_root(plan_containing([("EXECUTABLE", "probe")]))
        seen = []
        result = ProbeWorker(self._probe(root, BIG_PIPE_PROBE)).run(
            root, "probe", on_line=seen.append)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output.count("A"), 262144)
        self.assertEqual(result.output.count("B"), 262144)
        relayed = "".join(seen)
        self.assertEqual(relayed.count("A"), 262144)
        self.assertEqual(relayed.count("B"), 262144)

    def test_stream_keeps_utf8_surrogatesafe(self):
        root = make_root(plan_containing([("EXECUTABLE", "probe")]))
        seen = []
        result = ProbeWorker(self._probe(root, PROBE_SCRIPT)).run(
            root, "probe", on_line=seen.append)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("caf\u00e9 \u0410 \u2510", result.output)
        self.assertIn("caf\u00e9 \u0410 \u2510", "".join(seen))


class PlanHygieneTests(unittest.TestCase):
    """Read the REAL .agent/PLAN.md and assert structural invariants.

    This is the "the menu is well-formed" guarantee the autonomous loop
    depends on (Mission 49).
    """

    def _load_plan_items(self):
        """Parse numbered items from the Active section of the real PLAN.md.

        Returns list of (number, tag_or_None, headline_text).
        Parses independently of read_plan() to catch structural drift.
        """
        plan_path = os.path.join(REPO_ROOT, ".agent", "PLAN.md")
        with open(plan_path, encoding="utf-8") as f:
            lines = f.readlines()
        in_active = False
        items = []
        for line in lines:
            stripped = line.rstrip("\n")
            if stripped.startswith("## "):
                in_active = stripped[3:].strip().lower().startswith("active")
                continue
            if not in_active:
                continue
            match = re.match(r"^\s*(\d+)\.\s+", stripped)
            if match:
                number = int(match.group(1))
                body = stripped[match.end():]
                tag_match = re.search(
                    r"`(EXECUTABLE|BLOCKED|DONE|CLAUDE_REVIEW)`", body)
                tag = tag_match.group(1) if tag_match else None
                headline_match = re.search(r"\*\*(.+?)\*\*", body)
                headline = headline_match.group(1) if headline_match else ""
                items.append((number, tag, headline))
        return items

    def test_items_numbered_sequentially_without_gaps(self):
        items = self._load_plan_items()
        self.assertGreater(len(items), 0)
        for i, (num, _tag, _headline) in enumerate(items):
            self.assertEqual(num, i + 1,
                             "Item {} at position {} breaks sequential numbering"
                             .format(num, i))

    def test_tags_are_valid_convention_tags(self):
        valid = {"EXECUTABLE", "BLOCKED", "DONE", "CLAUDE_REVIEW"}
        items = self._load_plan_items()
        for num, tag, _headline in items:
            if tag is not None:
                self.assertIn(tag, valid,
                              "Item {} has invalid tag '{}'".format(num, tag))

    def test_blocked_items_cross_referenced_in_blockers(self):
        blockers_path = os.path.join(REPO_ROOT, ".agent", "BLOCKERS.md")
        with open(blockers_path, encoding="utf-8") as f:
            blockers_text = f.read()
        items = self._load_plan_items()
        blocked_numbers = [num for num, tag, _ in items if tag == "BLOCKED"]
        for num in blocked_numbers:
            self.assertIn(str(num), blockers_text,
                          "BLOCKED item {} not cross-referenced in BLOCKERS.md"
                          .format(num))

    def test_first_executable_returns_executable_when_one_exists(self):
        plan = read_plan(REPO_ROOT)
        has_executable = any(item.executable for item in plan.items)
        first = plan.first_executable()
        if has_executable:
            self.assertIsNotNone(first)
            self.assertTrue(first.executable)
        else:
            self.assertIsNone(first)


class RecordingNotifier:
    """Fake notifier: records every (title, body, report) call for
    assertions. Mirrors the real notifier's persistent-popup contract."""

    def __init__(self):
        self.calls = []

    def notify(self, title, body, report=None):
        self.calls.append((title, body, report))


class NotifierTests(unittest.TestCase):
    """Notifications are best-effort: selection is env/flag-driven and a
    failing child process must never surface into the loop."""

    def test_null_notifier_is_a_noop(self):
        self.assertIsNone(NullNotifier().notify("t", "b"))

    def test_create_notifier_disabled_returns_null(self):
        self.assertIsInstance(create_notifier(False), NullNotifier)

    def test_env_flag_enables_notifications(self):
        self.assertTrue(notifications_enabled("1"))
        self.assertTrue(notifications_enabled("true"))
        self.assertFalse(notifications_enabled(""))
        self.assertFalse(notifications_enabled(False))

    def test_create_notifier_on_non_windows_returns_null(self):
        with unittest.mock.patch("ine_agent.notifier.platform.system",
                                 return_value="Linux"):
            self.assertIsInstance(create_notifier(True), NullNotifier)

    def test_windows_notifier_never_raises_on_missing_powershell(self):
        notifier = WindowsPowerShellNotifier(powershell="does-not-exist.exe")
        notifier.notify("title", "body")  # must not raise

    def test_windows_notifier_popup_is_persistent_and_human(self):
        from ine_agent.notifier import _PS_TEMPLATE
        # The popup stays on screen until dismissed (no auto-close / balloon
        # `Start-Sleep`-and-die pattern) and renders prose, not raw paths.
        self.assertIn("Dismiss", _PS_TEMPLATE)
        self.assertIn("[System.Windows.Forms.Application]::Run", _PS_TEMPLATE)
        self.assertNotIn("Report: C:", _PS_TEMPLATE)

    def test_popup_plays_chime_and_uses_round_icon(self):
        from ine_agent.notifier import _PS_TEMPLATE
        # The popup plays the soft chime and uses the round-tile icon.
        self.assertIn("System.Media.SoundPlayer", _PS_TEMPLATE)
        self.assertIn(".Play()", _PS_TEMPLATE)
        self.assertIn("___ICON___", _PS_TEMPLATE)
        self.assertIn("___CHIME___", _PS_TEMPLATE)
        self.assertNotIn("FromHandle($img.GetHicon())", _PS_TEMPLATE)

    def test_default_chime_path_resolves_repo_asset(self):
        path = default_chime_path()
        self.assertTrue(path, "expected assets/chime.wav to exist")
        self.assertTrue(os.path.isfile(path), path)
        self.assertTrue(path.endswith("chime.wav"), path)

    def test_create_notifier_prefers_round_tile_next_to_logo(self):
        root = tempfile.mkdtemp(prefix="ineicon-", dir=TMP)
        logo = os.path.join(root, "logo.png")
        with open(logo, "w") as handle:
            handle.write("logo")
        notifier = create_notifier(True, logo_path=logo)
        if not isinstance(notifier, WindowsPowerShellNotifier):
            self.skipTest("this host does not resolve the Windows notifier")
        self.assertEqual(notifier.logo_path, logo)
        # No tile beside the logo yet: the window icon falls back to the
        # square brand image.
        self.assertEqual(notifier.icon_path, logo)
        icon = os.path.join(root, "icon.png")
        with open(icon, "w") as handle:
            handle.write("icon")
        tile = create_notifier(True, logo_path=logo)
        self.assertEqual(tile.icon_path, icon)


class Session41RecordingTests(unittest.TestCase):
    """Recorded remarks/tags/resolutions are append-only with respect to the
    original item text and the existing BLOCKERS.md content."""

    def _root(self):
        plan = plan_containing([
            ("EXECUTABLE", "first task"),
            ("BLOCKED", "blocked task"),
        ])
        return make_root(plan)

    def test_append_item_remark_preserves_original(self):
        root = self._root()
        identity = read_plan(root).items[0].identity
        self.assertTrue(append_item_remark(root, identity, "needs a look"))
        items = read_plan(root).items
        self.assertEqual(items[0].tag, "EXECUTABLE")
        self.assertIn("first task", items[0].text.splitlines()[0])
        self.assertIn("needs a look", items[0].text)
        self.assertNotIn("needs a look", items[1].text)

    def test_mark_blocked_preserves_original(self):
        root = self._root()
        identity = read_plan(root).items[0].identity
        self.assertTrue(mark_blocked(root, identity, "evidence wall"))
        items = read_plan(root).items
        self.assertEqual(items[0].tag, "BLOCKED")
        self.assertFalse(items[0].executable)
        self.assertIn("first task", items[0].text.splitlines()[0])
        self.assertIn("evidence wall", items[0].text)
        # Item 1 was not executable before, stays BLOCKED, untouched.
        self.assertEqual(items[1].tag, "BLOCKED")

    def test_mark_blocked_leaves_done_tag_alone(self):
        plan = plan_containing([("DONE", "finished task")])
        root = make_root(plan)
        identity = read_plan(root).items[0].identity
        self.assertTrue(mark_blocked(root, identity, "should not retag"))
        item = read_plan(root).items[0]
        self.assertEqual(item.tag, "DONE")
        self.assertIn("should not retag", item.text)

    def test_record_resolution_preserves_blocker(self):
        root = self._root()
        identity = read_plan(root).items[1].identity
        self.assertTrue(record_resolution(root, identity, "commander approved"))
        item = read_plan(root).items[1]
        self.assertEqual(item.tag, "BLOCKED")
        self.assertIn("blocked task", item.text.splitlines()[0])
        self.assertIn("> resolution (commander): commander approved", item.text)

    def test_missing_item_fails_cleanly(self):
        root = self._root()
        self.assertFalse(append_item_remark(root, "does-not-exist", "x"))
        self.assertFalse(mark_blocked(root, "does-not-exist", "x"))
        self.assertFalse(record_resolution(root, "does-not-exist", "x"))

    def test_append_blocker_keeps_existing_entries(self):
        root = self._root()
        before = open(os.path.join(root, ".agent", "BLOCKERS.md"),
                      encoding="utf-8").read()
        self.assertTrue(append_blocker(root, 1, "first task", "evidence wall"))
        blockers = open(os.path.join(root, ".agent", "BLOCKERS.md"),
                        encoding="utf-8").read()
        self.assertIn(before.strip(), blockers)  # original preserved
        self.assertIn("## Blocked during autonomous runs", blockers)
        self.assertIn("first task", blockers)
        self.assertIn("evidence wall", blockers)

    def test_run_report_roundtrip(self):
        root = self._root()
        self.assertFalse(os.path.isfile(run_report_path(root)))
        begin_run_report(root, "python -m ine_agent.cli run --root X")
        end_run_report(root, STOP_OK, "no executable work remains.")
        report = open(run_report_path(root), encoding="utf-8").read()
        self.assertIn("## run", report)
        self.assertIn("python -m ine_agent.cli run --root X", report)
        self.assertIn("- exit: 0", report)
        self.assertIn("no executable work remains.", report)


class Session41SupervisorTests(unittest.TestCase):
    """Session 41 contract: a blocked/failed/human-recorded mission is
    deferred (never retried or re-picked this run) so independent executable
    work continues, and the outcomes number the commander."""

    def _run(self, root, worker=None, factory=None, notifier=None, **kwargs):
        if worker is None and factory is None:
            worker = StubWorker([])
        if factory is None:
            factory = lambda name: worker
        out = io.StringIO()
        kwargs["notifier"] = notifier or RecordingNotifier()
        kwargs["usage_reporter"] = ZeroUsage()
        code = Supervisor(root, worker_factory=factory, out=out, **kwargs).run()
        calls = [] if worker is None else list(worker.calls)
        return code, out.getvalue(), calls, worker

    def test_blocked_mission_defers_so_independent_work_runs(self):
        # First task hits a wall (BLOCKED) and is deferred; second runs.
        root = make_root(plan_containing([
            ("EXECUTABLE", "predecessor"),
            ("EXECUTABLE", "independent"),
        ]))
        worker = StubWorker([
            (0, "", plugin_blocked_text("predecessor")),
            (0, "", plugin_done_text("independent")),
        ])
        notifier = RecordingNotifier()
        code, out, calls, _ = self._run(root, worker=worker, notifier=notifier)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 2)
        self.assertIn("predecessor", calls[0]["prompt"])
        self.assertIn("independent", calls[1]["prompt"])
        # Predecessor recorded BLOCKED, independent ended DONE (removed).
        items = read_plan(root).items
        self.assertEqual(items[0].tag, "BLOCKED")
        self.assertIn("independent", items[1].text)
        self.assertEqual(items[1].tag, "DONE")
        # Notification covered the start/block; run-complete fired with the
        # report. Bodies are one headline line, not "recorded and deferred…".
        titles = [t for t, _, _ in notifier.calls]
        self.assertIn("Ine · task started", titles)
        self.assertIn("Ine · task blocked", titles)
        self.assertIn("Ine · run complete", titles)
        blocked_body = notifier.calls[1][1]
        self.assertIn("predecessor", blocked_body)
        self.assertNotIn("recorded and", blocked_body)
        body = notifier.calls[-1][1]
        self.assertIn(run_report_path(root), notifier.calls[-1][2])

    def test_failed_mission_defers_so_independent_work_runs(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "fragile"),
            ("EXECUTABLE", "independent"),
        ]))
        worker = StubWorker([
            (1, "boom"),
            (0, "", plugin_done_text("independent")),
        ])
        notifier = RecordingNotifier()
        code, out, calls, _ = self._run(root, worker=worker, notifier=notifier)
        self.assertEqual(code, STOP_ERROR)  # a mission failed → exit 1
        self.assertEqual(len(calls), 2)
        self.assertIn("mission failed", out)
        titles = [t for t, _, _ in notifier.calls]
        self.assertIn("Ine · task failed", titles)
        self.assertIn("Ine · run complete", titles)

    def test_human_decision_defers_independent_work_and_ends_pending(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "needs decision"),
            ("EXECUTABLE", "independent"),
        ]))
        worker = StubWorker([
            (0, "HUMAN_DECISION_REQUIRED\nwhich option?"),
            (0, "", plugin_done_text("independent")),
        ])
        notifier = RecordingNotifier()
        code, out, calls, _ = self._run(root, worker=worker, max_attempts=5,
                                        notifier=notifier)
        self.assertEqual(code, STOP_HUMAN)  # pending gate → exit 2
        self.assertEqual(len(calls), 2)
        self.assertIn("mission recorded and deferred", out)
        titles = [t for t, _, _ in notifier.calls]
        self.assertIn("Ine · task started", titles)
        self.assertIn("Ine · decision required", titles)
        self.assertIn("Ine · run complete", titles)

    def test_done_run_fires_run_complete_and_writes_report(self):
        root = make_root(plan_containing([("EXECUTABLE", "do it")]))
        worker = StubWorker([(0, "", plugin_done_text("do it"))])
        notifier = RecordingNotifier()
        code, out, calls, _ = self._run(root, worker=worker, notifier=notifier)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 1)
        titles = [t for t, _, _ in notifier.calls]
        self.assertIn("Ine · task started", titles)
        self.assertIn("Ine · task done", titles)
        self.assertIn("Ine · run complete", titles)
        self.assertTrue(os.path.isfile(run_report_path(root)))
        report = open(run_report_path(root), encoding="utf-8").read()
        self.assertIn("- exit: 0", report)

    def test_stuck_mission_notifies_task_stuck(self):
        # A worker that exits 0 without moving the plan gets bounded retries.
        root = make_root(plan_containing([("EXECUTABLE", "stubborn task")]))
        worker = StubWorker([(0, ""), (0, "")])  # no plan progress either time
        notifier = RecordingNotifier()
        code, out, calls, _ = self._run(root, worker=worker, notifier=notifier)
        self.assertEqual(code, STOP_ERROR)  # bounded stop after max_attempts
        self.assertEqual(len(calls), 2)
        titles = [t for t, _, _ in notifier.calls]
        self.assertTrue(titles.count("Ine · task started") >= 1)
        self.assertTrue(titles.count("Ine · task stuck") >= 1)


class ResolveCliTests(unittest.TestCase):
    def test_resolve_records_blueprint_for_blocked_mission(self):
        root = make_root(plan_containing([
            ("BLOCKED", "blocked on scope"),
            ("EXECUTABLE", "next task"),
        ]))
        code = cli.main(["resolve", "--root", root, "blocked on scope",
                         "commander approves: implement option A"])
        self.assertEqual(code, 0)
        item = next(i for i in read_plan(root).items if "blocked on scope" in i.text)
        self.assertIn("commander approves: implement option A", item.text)

    def test_resolve_no_match_returns_error(self):
        root = make_root(plan_containing([("BLOCKED", "blocked on scope")]))
        code = cli.main(["resolve", "--root", root, "no-such-mission", "bp"])
        self.assertEqual(code, 1)


def _clean_temp_roots():
    """Remove every fixture root this module created under `.tmp/`."""
    for root in _CREATED_ROOTS:
        shutil.rmtree(root, ignore_errors=True)


def tearDownModule():
    """Unittest module hook — removes leftover fixture roots on
    `python -m unittest` runs."""
    _clean_temp_roots()


@pytest.fixture(autouse=True)
def _no_temp_root_leftovers():
    """Remove this module's fixture roots after each test. Autouse because
    pytest does not invoke the unittest `tearDownModule` hook for
    unittest.TestCase subclasses; without this, every `python -m pytest`
    run would leave `ineagent-*` directories behind in `.tmp/`."""
    yield
    _clean_temp_roots()


if __name__ == "__main__":
    unittest.main()