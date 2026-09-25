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
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ine_agent import cli
from ine_agent import compaction
from ine_agent import measure
from ine_agent import profiles
from ine_agent import receipt as receipt_format
from ine_agent import usage
from ine_agent import worker
from ine_agent.notifier import (
    NOTIFY_ENV, NullNotifier, WindowsPowerShellNotifier, create_notifier,
    default_chime_path, notifications_enabled,
)
from ine_agent.receipt import Receipt, parse_receipt
from ine_agent.state import (
    ProjectError, append_blocker, append_item_remark, begin_run_report,
    end_run_report, find_project_root, human_decision_indicated, mark_blocked,
    mark_done, mission_index_path, mission_index_relpath,
    next_session_number, output_marks_human_decision, read_mission_index,
    read_mission_metadata, read_plan, record_mission_outcome,
    record_resolution, run_report_path, write_mission_index,
)
from ine_agent.supervisor import (
    CLASSIFICATIONS, DEFAULT_MAX_FAILURES, DEFAULT_STALL_LIMIT, RETRYABLE,
    STOP_ERROR, STOP_HUMAN, STOP_OK, UNCLASSIFIED, Classification, Diagnosis,
    Match, Source, Supervisor, _planner_block, attempts_path, canonical,
    classify_action, clear_mission_attempts, diagnose_output, diagnosis_prompt,
    diagnosis_trace, impl_prompt, parked_missions, parse_classification,
    read_attempts, record_failure, retry_block, review_prompt,
    worktree_signature,
)
from ine_agent.worker import (CliWorker, OpenCodeWorker, StubWorker,
                              _split_command, build_worker)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# `.tmp/` is gitignored scratch (see AGENTS.md, "Repository containment");
# every fixture root is stashed here and removed once the test finishes.
TMP = os.path.join(REPO_ROOT, ".tmp")

# Prefixes this module uses for its own scratch directories. They exist so
# leftover scratch can be told apart from the real artifacts that also live
# in `.tmp/` (venvs, wheels, captured pages), which are never deleted.
FIXTURE_PREFIXES = ("ineagent-", "ineicon-", "usage-")

_CREATED_ROOTS = []


def make_tmp_dir(prefix):
    """Create a scratch directory under `.tmp/` and register it for cleanup.

    Every directory this module creates goes through here, so cleanup
    cannot be forgotten by a new test. The `ineicon-*` leak (100
    directories) was exactly that: a `mkdtemp` no one registered.
    """
    os.makedirs(TMP, exist_ok=True)
    folder = tempfile.mkdtemp(prefix=prefix, dir=TMP)
    _CREATED_ROOTS.append(folder)
    return folder


def _force_writable(func, path, exc_info):
    """`shutil.rmtree` onerror: clear the read-only bit and retry once.

    Windows marks git's object files read-only, and rmtree refuses them.
    Ignoring that failure is what left dozens of `ineagent-*` directories
    in `.tmp/` containing nothing but `.git` — a partially deleted tree
    that looked like a successful cleanup. Only the read-only case is
    retried; anything else is re-raised, so a real failure is never lost
    silently again.
    """
    if not isinstance(exc_info[1], PermissionError):
        raise exc_info[1]
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _remove_root(root):
    """Remove one scratch tree, clearing read-only files on the way."""
    if not os.path.exists(root):
        return
    shutil.rmtree(root, onerror=_force_writable)


def _close_and_remove(conn, folder):
    """Close a sqlite handle, then remove the directory that held it."""
    try:
        conn.close()
    except Exception:
        pass
    _remove_root(folder)


def _leftover_fixture_dirs():
    """This module's scratch directories still present under `.tmp/`."""
    if not os.path.isdir(TMP):
        return []
    return sorted(name for name in os.listdir(TMP)
                  if name.startswith(FIXTURE_PREFIXES))


def make_root(plan, state_text="state", history_text="history",
              blockers_text="blockers", mission_prompt_text=None,
              worker_prompt_text=None, mission_text=None, indexes=True):
    root = make_tmp_dir("ineagent-")
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
    if worker_prompt_text is not None:
        with open(os.path.join(agent, "WORKER_PROMPT.md"), "w",
                  encoding="utf-8") as handle:
            handle.write(worker_prompt_text)
    if mission_text is not None:
        with open(os.path.join(agent, "MISSION.md"), "w",
                  encoding="utf-8") as handle:
            handle.write(mission_text)
    if indexes:
        write_indexes(root, plan)
    return root


def write_indexes(root, plan_text):
    """Give every numbered PLAN item the execution index a planner owes it.

    The supervisor refuses to launch a worker for a mission with no index,
    so a fixture root whose loop is meant to RUN has to be indexed the way
    a real one is. Tests that exercise the refusal pass `indexes=False`;
    tests that assert what the prompt carries write their own index.
    """
    folder = os.path.join(root, ".agent", "missions")
    os.makedirs(folder, exist_ok=True)
    for match in re.finditer(r"(?m)^\s*(\d+)\.\s+(.*)$", plan_text):
        number, line = match.group(1), match.group(2).strip()
        with open(os.path.join(folder, number + ".md"), "w",
                  encoding="utf-8") as handle:
            handle.write("# Mission {}\n\nGoal: {}.\n".format(number, line))


def write_index(root, number, text):
    """Write one execution index, creating `.agent/missions/` as needed."""
    folder = os.path.join(root, ".agent", "missions")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "{}.md".format(number)), "w",
              encoding="utf-8") as handle:
        handle.write(text)


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


# A stuck cycle from a cooperating worker: exit 0, no plan progress, and the
# CLASSIFICATION/REASON block every mission prompt asks for. Because the
# block is in-band the supervisor acts on it directly and does NOT spend a
# follow-up diagnosis call — which is what keeps these fixtures at one
# worker call per cycle.
STUCK_UNKNOWN_TEXT = (
    "Tried the task and did not advance the plan.\n"
    "CLASSIFICATION: unknown\n"
    "REASON: no clear blocker — stopped without finishing\n"
)


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

# A worker that says something useful and then never exits. This is the case
# a wall-clock bound exists for: without it the run waits forever and the
# commander's queue never advances.
HANGING_PROBE = (
    "import sys, time\n"
    "sys.stdout.write('starting up\\n')\n"
    "sys.stdout.write('still thinking\\n')\n"
    "sys.stdout.flush()\n"
    "time.sleep(120)\n"
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


def receipt_text(status="done", summary="did what the index asked", files=(),
                 verification=(), area=None, finding=None, follow_up=None,
                 prose=""):
    """A worker final message that ends in the structured receipt block.

    Shaped by the same module the prompt tells workers to follow, so a test
    that asserts on what the supervisor records is asserting on the real
    wire format rather than on a hand-written imitation of it.
    """
    body = {"status": status, "summary": summary}
    if files:
        body["changed_files"] = list(files)
    if verification:
        body["verification"] = list(verification)
    if area:
        body["area"] = area
    if finding:
        body["finding"] = finding
    if follow_up:
        body["follow_up"] = follow_up
    head = (prose + "\n\n") if prose else ""
    return "{}{}\n{}\n".format(
        head, receipt_format.MARKER,
        json.dumps(body, indent=2, ensure_ascii=False))


class MissionTests(unittest.TestCase):
    """What the execution prompt is made of — and what it must never contain."""

    def test_planner_block_ignores_the_execution_contract(self):
        # The design-review step is planning, so it keeps MISSION_PROMPT.md
        # and MISSION.md. The executor's contract is not its business.
        root = make_root(
            plan_containing([("EXECUTABLE", "x")]),
            worker_prompt_text="Autonomous rules for this project.\n",
        )
        self.assertNotIn("Autonomous rules for this project.",
                         _planner_block(root))

    def test_planner_block_carries_its_own_prompt_and_context(self):
        root = make_root(
            plan_containing([("EXECUTABLE", "x")]),
            mission_prompt_text="Work out how to do this yourself.\n",
            mission_text="Ine is a language for describing what, not how.\n",
        )
        block = _planner_block(root)
        self.assertIn("Work out how to do this yourself.", block)
        self.assertIn("Ine is a language for describing what, not how.", block)
        self.assertIn("MISSION (follow this as your planning rules):", block)

    def test_impl_prompt_carries_the_mission_and_nothing_else(self):
        root = make_root(
            plan_containing([("EXECUTABLE", "do the thing")]),
            worker_prompt_text="Always read before writing.\n",
            mission_text="Ine is a language.\n",
        )
        prompt = impl_prompt(root, read_plan(root).first_executable())
        self.assertIn("do the thing", prompt)
        self.assertIn("MISSION (PLAN item 1)", prompt)
        self.assertIn("Goal:", prompt)
        # The two documents the loop used to re-send in full every cycle.
        self.assertNotIn("Always read before writing.", prompt)
        self.assertNotIn("Ine is a language.", prompt)

    def test_impl_prompt_omits_every_control_plane_document(self):
        # STATE, HISTORY, BLOCKERS and the plan body were embedded whole (or
        # distilled) and re-sent on every cycle. None of it may reach the
        # worker: the index states the scope, and a snapshot sent once goes
        # stale the moment the worker starts changing things.
        root = make_root(
            plan_containing([("EXECUTABLE", "do the thing")]),
            state_text=("## Current focus\n\nSTATE-ONLY-SENTINEL working on "
                        "the thing.\n"),
            history_text=("## Session 7 - long ago\n\nHISTORY-ONLY-SENTINEL "
                          "about something else.\n"),
            blockers_text="BLOCKERS-ONLY-SENTINEL about a decision.\n",
            worker_prompt_text="WORKER-PROMPT-ONLY-SENTINEL rules.\n",
            mission_text="MISSION-ONLY-SENTINEL context.\n",
            mission_prompt_text="PLANNER-ONLY-SENTINEL planning rules.\n",
        )
        prompt = impl_prompt(root, read_plan(root).first_executable())
        for sentinel in ("STATE-ONLY-SENTINEL", "HISTORY-ONLY-SENTINEL",
                         "BLOCKERS-ONLY-SENTINEL", "WORKER-PROMPT-ONLY-SENTINEL",
                         "MISSION-ONLY-SENTINEL", "PLANNER-ONLY-SENTINEL"):
            self.assertNotIn(sentinel, prompt)

    def test_impl_prompt_does_not_scale_with_the_control_plane(self):
        # The measurement that matters: the same mission, in a repository
        # whose records are large, must cost the same prompt as in one whose
        # records are small. This is the whole point of the handoff.
        plan = plan_containing([("EXECUTABLE", "do the thing")])
        lean = make_root(plan)
        fat = make_root(
            plan,
            state_text="## Current focus\n\n" + ("fat state " * 4000),
            history_text="## Session 1\n\n" + ("fat history " * 4000),
            worker_prompt_text="fat contract\n" * 2000,
            mission_text="fat context\n" * 2000,
            mission_prompt_text="fat planning\n" * 2000,
        )
        self.assertEqual(
            len(impl_prompt(lean, read_plan(lean).first_executable())),
            len(impl_prompt(fat, read_plan(fat).first_executable())),
        )

    def test_impl_prompt_teaches_locate_before_read(self):
        # Whatever a read returns is re-sent on every later step, so the
        # prompt must ask for the smallest sufficient region instead of a
        # whole file.
        root = make_root(plan_containing([("EXECUTABLE", "do the thing")]))
        prompt = impl_prompt(root, read_plan(root).first_executable())
        self.assertIn("locate before you read", prompt)

    def test_impl_prompt_bounds_the_full_suite_to_the_end(self):
        root = make_root(plan_containing([("EXECUTABLE", "do the thing")]))
        prompt = impl_prompt(root, read_plan(root).first_executable())
        self.assertIn("the full suite once at the end", prompt)

    def test_impl_prompt_ends_with_the_receipt_contract(self):
        root = make_root(plan_containing([("EXECUTABLE", "do the thing")]))
        prompt = impl_prompt(root, read_plan(root).first_executable())
        self.assertLess(prompt.index("Goal:"), prompt.index(
            receipt_format.MARKER))
        for status in receipt_format.STATUSES:
            self.assertIn(status, prompt)
        self.assertIn("never executed automatically", prompt)

    def test_impl_prompt_tells_the_worker_not_to_edit_the_control_plane(self):
        # Recording is the supervisor's job now, so the worker must not spend
        # a mission rewriting PLAN, HISTORY, STATE and NOTES by hand.
        root = make_root(plan_containing([("EXECUTABLE", "do the thing")]))
        prompt = impl_prompt(root, read_plan(root).first_executable())
        self.assertIn("Do not edit the `.agent/` control-plane files", prompt)
        self.assertNotIn("append a session block", prompt)

    def test_impl_prompt_says_a_missing_index_is_a_planning_defect(self):
        root = make_root(plan_containing([("EXECUTABLE", "x")]), indexes=False)
        prompt = impl_prompt(root, read_plan(root).first_executable())
        self.assertIn("there is no index at", prompt)
        self.assertIn("needs_commander", prompt)

    def test_review_prompt_still_embeds_the_planner_context(self):
        root = make_root(
            plan_containing([("CLAUDE_REVIEW", "review this")]),
            mission_prompt_text="Operate carefully.\n",
            mission_text="Project context here.\n",
        )
        task = read_plan(root).first_executable()
        prompt = review_prompt(root, task)
        self.assertIn("Operate carefully.", prompt)
        self.assertIn("Project context here.", prompt)
        self.assertIn("review this", prompt)


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
        # A crashing worker is not retried against the same wall. It costs
        # exactly one invocation, the crash is unclassifiable, and it is
        # deferred rather than re-run. Recorded on the PLAN item, and when it
        # is the only task the run ends with the documented error code
        # (exit 1) — reporting the deferred mission, not a bogus
        # bounded-stop.
        root = make_root(plan_containing([("EXECUTABLE", "always fails")]))
        worker = StubWorker([(1, "boom")] * 10)
        code, out, calls, _ = self._run(root, worker=worker, max_attempts=2)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 1)          # one mission, one request
        self.assertIn("diagnosis: unknown", out)
        self.assertIn("mission not completed — recorded and deferred", out)
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

    def test_the_mission_bound_is_a_hard_bound(self):
        # A worker that never advances but never fails must be bounded. The
        # bound counts MISSIONS, and a mission is attempted at most
        # `max_attempts` times, so with one attempt per mission a bound of 3
        # is three invocations on three missions — not three invocations on
        # one.
        root = make_root(plan_containing([
            ("EXECUTABLE", "stays put"),
            ("EXECUTABLE", "also stuck"),
            ("EXECUTABLE", "never reached"),
        ]))
        worker = StubWorker([(0, "")] * 30)
        code, out, calls, _ = self._run(
            root, worker=worker, max_cycles=2, max_attempts=1)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 2)          # 2 missions, 2 invocations
        self.assertIn("--max-missions bound of 2", out)
        self.assertIn("3 mission(s) still EXECUTABLE in the plan", out)


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
        folder = make_tmp_dir("usage-")
        conn = sqlite3.connect(os.path.join(folder, "opencode.db"))
        # Windows will not delete a file with an open handle, so the sqlite
        # connection has to be closed before the directory is removed. This
        # is why 400+ `usage-*` directories used to accumulate: the old
        # `addCleanup(rmtree, ..., True)` ran while the connection was still
        # open and swallowed the resulting failure.
        self.addCleanup(_close_and_remove, conn, folder)
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

    # --- STOP_ERROR (exit 1) — retry budget exhausted, mission deferred ------

    def test_attempts_limit_exits_one(self):
        # Phase 1: exhausting `max_attempts` no longer ends the run — it
        # defers that one mission. With nothing else to run the run still
        # ends honestly at exit 1, and the PLAN item carries the reason.
        root = make_root(plan_containing([("EXECUTABLE", "stuck task")]))
        worker = StubWorker([(0, "")] * 30)
        code, out, calls, _ = self._run(
            root, worker=worker, max_attempts=2, max_cycles=20)
        self.assertEqual(code, 1)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 2)          # 2 attempts, 2 invocations
        self.assertNotIn("could not advance the plan", out)
        self.assertIn("retries exhausted", out)
        self.assertIn("missions deferred after failing", out)
        self.assertEqual(self._last_exit_code_in_report(root), 1)
        plan = read_plan(root)
        self.assertIn("retries exhausted after 2 attempt(s)", plan.items[0].text)

    # --- STOP_ERROR (exit 1) — bounded stop: cycle limit ---------------------

    def test_mission_bound_exits_one(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "stays put"),
            ("EXECUTABLE", "also stuck"),
            ("EXECUTABLE", "never reached"),
        ]))
        worker = StubWorker([(0, "")] * 30)
        code, out, calls, _ = self._run(
            root, worker=worker, max_cycles=2, max_attempts=1)
        self.assertEqual(code, 1)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 2)          # 2 missions, 2 invocations
        self.assertIn("--max-missions bound of 2", out)
        self.assertEqual(self._last_exit_code_in_report(root), 1)

    # --- STOP_ERROR (exit 1) — worker failure --------------------------------

    def test_worker_failure_exits_one(self):
        root = make_root(plan_containing([("EXECUTABLE", "fails")]))
        worker = StubWorker([(1, "boom")])
        code, out, calls, _ = self._run(
            root, worker=worker, max_attempts=2)
        self.assertEqual(code, 1)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 1)          # one mission, one invocation
        self.assertIn("missions deferred after failing", out)
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
        # 2 and the loop would run out of retries before the last task —
        # with it, all work finishes (exit 0).
        #
        # Each stuck step carries the CLASSIFICATION line a cooperating
        # worker prints, so no diagnosis follow-up is needed and the call
        # count stays one per cycle.
        root = make_root(plan_containing([
            ("EXECUTABLE", "first task"),
            ("EXECUTABLE", "second task"),
        ]))
        worker = StubWorker([
            (0, STUCK_UNKNOWN_TEXT),                   # cycle 1: stuck
            (0, "", plugin_done_text("first task")),   # cycle 2: progress
            (0, STUCK_UNKNOWN_TEXT),                   # cycle 3: stuck
            (0, "", plugin_done_text("second task")),  # cycle 4: progress
        ])
        code, out, calls, _ = self._run(
            root, worker=worker, max_attempts=2, max_cycles=10)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 4)
        self.assertNotIn("could not advance the plan", out)
        # Per-cycle classification is recorded durably and honestly.
        report = open(run_report_path(root), encoding="utf-8").read()
        self.assertIn("- [cycle 1] RETRY (unknown)", report)
        self.assertIn("- [cycle 2] DONE", report)
        self.assertIn("- [cycle 3] RETRY (unknown)", report)
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
            (0, STUCK_UNKNOWN_TEXT),                     # stuck, attempt 1
            (0, "", plugin_done_text("needs retry")),    # progress, reset
        ])
        code, out, calls, _ = self._run(
            root, worker=worker, max_attempts=2, max_cycles=10)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 3)
        self.assertNotIn("could not advance the plan", out)

    def test_retry_budget_defers_instead_of_stopping_the_run(self):
        # A reset grants no immunity: consecutive no-progress cycles after a
        # reset still exhaust `max_attempts` — but exhausting it now defers
        # that ONE mission (recorded with its reason) instead of ending the
        # run, and the run still reports honestly (exit 1, nothing finished).
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
        self.assertNotIn("could not advance the plan", out)
        self.assertIn("retries exhausted", out)
        self.assertIn("independent work continues", out)
        report = open(run_report_path(root), encoding="utf-8").read()
        self.assertIn("- [cycle 1] DONE", report)
        self.assertIn("- [cycle 3] RETRIES EXHAUSTED (unknown)", report)


class AttemptLedgerTests(unittest.TestCase):
    """Phase 3: the cross-run failure ledger (`.agent/attempts.json`).

    A run-local deferral dies with the process, which is how one mission got
    re-picked by thirteen consecutive runs. The ledger is the memory that
    replaces it: what it records, why a failed RUN is not a failed attempt,
    and that a missing or broken file costs memory, never a run.
    """

    def test_missing_ledger_is_no_history_not_an_error(self):
        root = make_root(plan_containing([("EXECUTABLE", "anything")]))
        self.assertEqual(read_attempts(root), {})
        self.assertEqual(parked_missions(root, DEFAULT_MAX_FAILURES), {})

    def test_broken_ledger_is_no_history_not_an_error(self):
        root = make_root(plan_containing([("EXECUTABLE", "anything")]))
        for body in ("{not json", '["a list"]', '{"missions": "nope"}',
                     '{"missions": {"an id": "not an entry"}}'):
            with open(attempts_path(root), "w", encoding="utf-8") as handle:
                handle.write(body)
            self.assertEqual(read_attempts(root), {}, body)

    def test_record_failure_counts_attempts_and_runs_separately(self):
        root = make_root(plan_containing([("EXECUTABLE", "anything")]))
        entry = record_failure(root, "an id", "transient", "flaky provider",
                               "failed", run_id="run-1")
        self.assertEqual((entry["attempts"], entry["runs"]), (1, 1))
        self.assertEqual(entry["classification"], "transient")
        self.assertEqual(entry["outcome"], "failed")
        self.assertEqual(entry["reason"], "flaky provider")
        self.assertTrue(entry["updated"])
        # Another cycle in the SAME run: another attempt, same failed run.
        entry = record_failure(root, "an id", "transient", "flaky provider",
                               "failed", run_id="run-1")
        self.assertEqual((entry["attempts"], entry["runs"]), (2, 1))
        # A later run is what parking counts.
        entry = record_failure(root, "an id", "transient", "flaky provider",
                               "failed", run_id="run-2")
        self.assertEqual((entry["attempts"], entry["runs"]), (3, 2))

    def test_record_failure_without_a_run_id_counts_every_call(self):
        root = make_root(plan_containing([("EXECUTABLE", "anything")]))
        record_failure(root, "an id", "transient", "flaky", "failed")
        entry = record_failure(root, "an id", "transient", "flaky", "failed")
        self.assertEqual((entry["attempts"], entry["runs"]), (2, 2))

    def test_parking_starts_at_the_threshold_and_zero_disables_it(self):
        root = make_root(plan_containing([("EXECUTABLE", "anything")]))
        for run in ("r1", "r2"):
            record_failure(root, "an id", "transient", "flaky", "failed",
                           run_id=run)
        self.assertEqual(parked_missions(root, 3), {})
        record_failure(root, "an id", "transient", "flaky", "failed",
                       run_id="r3")
        self.assertIn("an id", parked_missions(root, 3))
        self.assertEqual(parked_missions(root, 4), {})
        self.assertEqual(parked_missions(root, 0), {})

    def test_clear_forgets_one_mission_only(self):
        root = make_root(plan_containing([("EXECUTABLE", "anything")]))
        record_failure(root, "first id", "transient", "flaky", "failed")
        record_failure(root, "second id", "transient", "flaky", "failed")
        self.assertTrue(clear_mission_attempts(root, "first id"))
        self.assertEqual(sorted(read_attempts(root)), ["second id"])
        self.assertFalse(clear_mission_attempts(root, "first id"))

    def test_the_ledger_is_json_keyed_on_the_mission_identity(self):
        root = make_root(plan_containing([("EXECUTABLE", "anything")]))
        record_failure(root, "the identity", "unknown", "no idea", "stuck")
        path = attempts_path(root)
        self.assertEqual(os.path.basename(path), "attempts.json")
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(list(data["missions"]), ["the identity"])


class WorktreeSignatureTests(unittest.TestCase):
    """Phase 3: the evidence half of the stall guard.

    A signature is `git status --porcelain` with `.agent/` taken out: the
    supervisor rewrites its own records on every non-completing cycle
    (failure remark, ledger, run report), so counting those as a change
    would call the exact spinning the guard exists for "progress". A root
    git cannot describe yields None — unknown, which the loop may read as
    neither progress nor a stall.
    """

    def _git_root(self):
        root = make_root(plan_containing([("EXECUTABLE", "anything")]))
        subprocess.run(["git", "init", "-q"], cwd=root, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "add", "-A"], cwd=root, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(
            ["git", "-c", "user.email=test@example.com", "-c", "user.name=t",
             "commit", "-q", "-m", "base"], cwd=root, check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return root

    def test_a_root_without_git_is_unknown(self):
        # Outside the repository on purpose: a fixture root under `.tmp/`
        # would answer for the repository that CONTAINS it.
        root = tempfile.mkdtemp(prefix="ineagent-nogit-")
        _CREATED_ROOTS.append(root)
        self.assertIsNone(worktree_signature(root))

    def test_a_clean_tree_is_known_and_empty(self):
        self.assertEqual(worktree_signature(self._git_root()), "")

    def test_a_change_outside_the_agent_directory_moves_the_signature(self):
        root = self._git_root()
        before = worktree_signature(root)
        with open(os.path.join(root, "notes.md"), "w", encoding="utf-8") as f:
            f.write("worker output\n")
        after = worktree_signature(root)
        self.assertNotEqual(after, before)
        self.assertIn("notes.md", after)

    def test_the_supervisors_own_records_do_not_move_it(self):
        root = self._git_root()
        before = worktree_signature(root)
        with open(os.path.join(root, ".agent", "STATE.md"), "a",
                  encoding="utf-8") as handle:
            handle.write("\nmore records\n")
        record_failure(root, "an id", "transient", "flaky", "failed")
        self.assertEqual(worktree_signature(root), before)


class ParkedMissionTests(unittest.TestCase):
    """Phase 3: a mission that keeps failing stops being picked.

    The measured pathology was thirteen consecutive runs spending requests on
    the same mission and finishing nothing. `max_failures` counts failed RUNS
    (not attempts — several failures inside one run are `max_attempts`'
    business); at that count the mission is parked: out of the loop, reported
    with its last reason, until a human rewrites it or clears its entry.
    """

    def _run(self, root, worker, **kwargs):
        out = io.StringIO()
        kwargs["usage_reporter"] = ZeroUsage()
        code = Supervisor(root, worker_factory=lambda name: worker,
                          out=out, **kwargs).run()
        return code, out.getvalue(), list(worker.calls)

    def test_the_second_failing_run_parks_it_and_the_next_does_nothing(self):
        root = make_root(plan_containing([("EXECUTABLE", "stuck forever")]))
        # Run 1: attempted, failed, deferred — the history is not yet deep
        # enough to stop picking it.
        worker = StubWorker([(0, STUCK_UNKNOWN_TEXT)])
        code, out, calls = self._run(root, worker, max_attempts=1,
                                     max_failures=2, max_cycles=5)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("[parked]", out)
        identity = read_plan(root).items[0].identity
        self.assertEqual(read_attempts(root)[identity]["runs"], 1)
        # Run 2: the second failed run reaches the limit, so this run parks
        # it as soon as its failure is recorded.
        worker = StubWorker([(0, STUCK_UNKNOWN_TEXT)])
        code, out, calls = self._run(root, worker, max_attempts=1,
                                     max_failures=2, max_cycles=5)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 1)
        self.assertIn("parked: 2 failed run(s)", out)
        self.assertIn("attempts.json", out)
        self.assertEqual(read_attempts(root)[identity]["runs"], 2)
        # Run 3: nothing is attempted at all, and the reason is stated.
        worker = StubWorker([(0, "")])
        code, out, calls = self._run(root, worker, max_attempts=1,
                                     max_failures=2, max_cycles=5)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(calls, [])
        self.assertIn("[parked]", out)
        self.assertIn("stuck forever", out)
        self.assertIn("every remaining mission is parked", out)
        report = open(run_report_path(root), encoding="utf-8").read()
        self.assertIn("- parked: failed in 2 run(s)", report)

    def test_completing_the_mission_clears_its_history(self):
        root = make_root(plan_containing([("EXECUTABLE", "hard task")]))
        worker = StubWorker([(0, STUCK_UNKNOWN_TEXT)])
        code, _, calls = self._run(root, worker, max_attempts=1,
                                   max_failures=3)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(read_attempts(root)), 1)
        worker = StubWorker([(0, "", plugin_done_text("hard task"))])
        code, _, calls = self._run(root, worker, max_attempts=1,
                                   max_failures=3)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 1)
        self.assertEqual(read_attempts(root), {})

    def test_rewriting_the_headline_gets_a_fresh_budget(self):
        root = make_root(plan_containing([("EXECUTABLE", "stuck forever")]))
        worker = StubWorker([(0, STUCK_UNKNOWN_TEXT)])
        self._run(root, worker, max_attempts=1, max_failures=1)
        self.assertEqual(len(parked_missions(root, 1)), 1)
        # The commander rewrites the mission text: a new identity, so a new
        # budget — the ledger is never a wall that needs editing JSON.
        rewritten = plan_containing([("EXECUTABLE", "stuck forever, retried")])
        with open(os.path.join(root, ".agent", "PLAN.md"), "w",
                  encoding="utf-8") as handle:
            handle.write(rewritten)
        worker = StubWorker([(0, STUCK_UNKNOWN_TEXT)])
        code, out, calls = self._run(root, worker, max_attempts=1,
                                     max_failures=1)
        self.assertEqual(len(calls), 1, out)     # picked up again
        self.assertIn("[cycle 1] worker", out)
        self.assertNotIn("[parked]", out)
        # The abandoned identity is dropped, not left behind as a phantom.
        self.assertEqual(list(read_attempts(root)),
                         [read_plan(root).items[0].identity])

    def test_work_that_left_the_plan_leaves_no_phantom_parked_entry(self):
        # A parked mission the commander re-tagged DONE: with the entry left
        # behind, every later run would claim everything was parked (exit 1)
        # instead of reporting that no work remains (exit 0).
        root = make_root(plan_containing([("EXECUTABLE", "stuck forever")]))
        worker = StubWorker([(0, STUCK_UNKNOWN_TEXT)])
        self._run(root, worker, max_attempts=1, max_failures=1)
        self.assertEqual(len(parked_missions(root, 1)), 1)
        with open(os.path.join(root, ".agent", "PLAN.md"), "w",
                  encoding="utf-8") as handle:
            handle.write(plan_containing([("DONE", "stuck forever")]))
        worker = StubWorker([(0, "")])
        code, out, calls = self._run(root, worker, max_attempts=1,
                                     max_failures=1)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(calls, [])
        self.assertIn("No executable work remains.", out)
        self.assertEqual(read_attempts(root), {})

    def test_max_failures_zero_never_parks(self):
        root = make_root(plan_containing([("EXECUTABLE", "stuck forever")]))
        for attempt in (1, 2, 3):
            worker = StubWorker([(0, STUCK_UNKNOWN_TEXT)])
            code, out, calls = self._run(root, worker, max_attempts=1,
                                         max_failures=0, max_cycles=5)
            self.assertEqual(code, STOP_ERROR)
            self.assertEqual(len(calls), 1, "run %d" % attempt)
            self.assertNotIn("[parked]", out, "run %d" % attempt)
        self.assertEqual(parked_missions(root, 0), {})


class StallGuardTests(unittest.TestCase):
    """Phase 3: a run that changes nothing stops early.

    The other half of the measured waste — cycles that neither completed nor
    blocked anything and left no file changed outside `.agent/`. A few of
    those in a row end the run, because more cycles are more requests against
    the same wall. Where git cannot answer, the guard stays silent: silence
    is never read as a stall.
    """

    THREE_MISSIONS = [("EXECUTABLE", "one"), ("EXECUTABLE", "two"),
                      ("EXECUTABLE", "three")]

    def _run(self, root, worker, **kwargs):
        out = io.StringIO()
        kwargs["usage_reporter"] = ZeroUsage()
        code = Supervisor(root, worker_factory=lambda name: worker,
                          out=out, **kwargs).run()
        return code, out.getvalue(), list(worker.calls)

    def _root(self):
        return make_root(plan_containing(self.THREE_MISSIONS))

    def test_repeated_no_progress_cycles_stop_the_run_early(self):
        root = self._root()
        worker = StubWorker([(0, STUCK_UNKNOWN_TEXT)] * 6)
        with mock.patch("ine_agent.supervisor.worktree_signature",
                        return_value="clean tree"):
            code, out, calls = self._run(root, worker, max_attempts=1,
                                         stall_limit=2, max_cycles=10)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 2)          # the third never ran
        self.assertIn("no progress for 2 consecutive cycle(s)", out)
        report = open(run_report_path(root), encoding="utf-8").read()
        self.assertIn("- outcome: no progress for 2 consecutive cycle(s)",
                      report)

    def test_a_changed_file_keeps_the_run_going(self):
        root = self._root()
        worker = StubWorker([(0, STUCK_UNKNOWN_TEXT)] * 6)
        seen = {"n": 0}

        def moving(root_):
            seen["n"] += 1
            return "signature-%d" % seen["n"]

        with mock.patch("ine_agent.supervisor.worktree_signature",
                        side_effect=moving):
            code, out, calls = self._run(root, worker, max_attempts=1,
                                         stall_limit=2, max_cycles=10)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 3)          # all three were attempted
        self.assertNotIn("no progress for", out)

    def test_unknown_evidence_never_becomes_a_stall(self):
        root = self._root()
        worker = StubWorker([(0, STUCK_UNKNOWN_TEXT)] * 6)
        with mock.patch("ine_agent.supervisor.worktree_signature",
                        return_value=None):
            code, out, calls = self._run(root, worker, max_attempts=1,
                                         stall_limit=1, max_cycles=10)
        self.assertEqual(len(calls), 3)
        self.assertNotIn("no progress for", out)

    def test_the_guard_can_be_disabled(self):
        root = self._root()
        worker = StubWorker([(0, STUCK_UNKNOWN_TEXT)] * 6)
        with mock.patch("ine_agent.supervisor.worktree_signature",
                        return_value="clean tree"):
            code, out, calls = self._run(root, worker, max_attempts=1,
                                         stall_limit=0, max_cycles=10)
        self.assertEqual(len(calls), 3)
        self.assertNotIn("no progress for", out)

    def test_a_completed_mission_resets_the_counter(self):
        root = self._root()
        worker = StubWorker([
            (0, "", plugin_done_text("one")),   # progress: resets the count
            (0, STUCK_UNKNOWN_TEXT),            # no progress: 1
            (0, STUCK_UNKNOWN_TEXT),            # would be 2 — but stops first
        ])
        with mock.patch("ine_agent.supervisor.worktree_signature",
                        return_value="clean tree"):
            code, out, calls = self._run(root, worker, max_attempts=1,
                                         stall_limit=1, max_cycles=10)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 2)
        self.assertIn("no progress for 1 consecutive cycle(s)", out)

    def test_the_mission_bound_is_still_the_first_hard_stop(self):
        root = self._root()
        worker = StubWorker([(0, STUCK_UNKNOWN_TEXT)] * 6)
        with mock.patch("ine_agent.supervisor.worktree_signature",
                        return_value="clean tree"):
            code, out, calls = self._run(root, worker, max_attempts=1,
                                         stall_limit=2, max_cycles=2)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 2)
        self.assertIn("--max-missions bound of 2", out)
        self.assertNotIn("no progress for", out)


class ClassificationParseTests(unittest.TestCase):
    """Phase 1: reading the CLASSIFICATION block out of a cycle's output.

    The block is the cheap half of the diagnosis — the worker that just ran
    the mission is the best witness to why it stopped, and letting it say so
    in-band costs nothing. The parsing rules matter as much as the feature:
    a marker matched in prose would classify a cycle off a passing mention.
    """

    def test_own_line_marker_is_parsed(self):
        text = "Worked on it.\nCLASSIFICATION: transient\nREASON: gateway 502\n"
        self.assertEqual(parse_classification(text),
                         ("transient", "gateway 502"))

    def test_marker_is_case_insensitive_and_tolerates_indentation(self):
        text = "  classification:  Missing_Prerequisite  \n  reason: needs X  \n"
        self.assertEqual(parse_classification(text),
                         ("missing_prerequisite", "needs X"))

    def test_prose_mention_does_not_classify_anything(self):
        # Same rule as HUMAN_DECISION_REQUIRED: a mid-line mention is prose.
        text = ("I would print CLASSIFICATION: missing_prerequisite here if "
                "the feature existed, but it does not.\n")
        self.assertEqual(parse_classification(text), (None, None))

    def test_absent_marker_reports_nothing_rather_than_unknown(self):
        # (None, None) is what triggers the follow-up diagnosis call; a bare
        # "unknown" would silently skip it.
        self.assertEqual(parse_classification("just did some work\n"),
                         (None, None))
        self.assertEqual(parse_classification(""), (None, None))
        self.assertEqual(parse_classification(None), (None, None))

    def test_off_vocabulary_value_is_kept_verbatim_as_the_reason(self):
        # An answer outside the vocabulary is recorded as written, never
        # mistaken for a class the loop knows how to act on.
        classification, reason = parse_classification(
            "CLASSIFICATION: it is complicated\n")
        self.assertEqual(classification, UNCLASSIFIED)
        self.assertIn("complicated", reason)

    def test_unknown_word_with_a_reason_keeps_the_reason(self):
        classification, reason = parse_classification(
            "CLASSIFICATION: unknown\nREASON: stopped without finishing\n")
        self.assertEqual(classification, UNCLASSIFIED)
        self.assertEqual(reason, "stopped without finishing")

    def test_reason_is_collapsed_to_one_bounded_line(self):
        # Reasons flow into PLAN remarks, BLOCKERS entries and notification
        # bodies, none of which want a paragraph or a runaway line.
        text = "CLASSIFICATION: agent_error\nREASON: " + ("x " * 500) + "\n"
        _, reason = parse_classification(text)
        self.assertLessEqual(len(reason), 200)
        self.assertTrue(reason.endswith("..."))
        self.assertNotIn("\n", reason)

    def test_last_marker_wins_when_the_worker_printed_two(self):
        # The prompt asks for exactly one, but a worker that echoes the
        # instruction and then answers must be read by its answer.
        text = ("CLASSIFICATION: missing_prerequisite\n"
                "CLASSIFICATION: needs_commander\n"
                "REASON: syntax question\n")
        self.assertEqual(parse_classification(text)[0], "needs_commander")


class ClassificationSchemaTests(unittest.TestCase):
    """Phase 2: the vocabulary is a schema, not a bag of strings.

    The parser, the prompts and the records all read the vocabulary from
    `Classification`, so what these tests pin is the schema itself rather
    than one call site's idea of it.
    """

    def test_members_are_the_documented_vocabulary(self):
        self.assertEqual(
            sorted(member.value for member in Classification),
            ["agent_error", "missing_prerequisite", "needs_commander",
             "transient", "unknown"])

    def test_public_projection_matches_the_schema(self):
        # The four a worker may choose, in the prompts' order, plus the value
        # that stands in for "could not be read".
        self.assertEqual(
            CLASSIFICATIONS,
            (Classification.NEEDS_COMMANDER.value,
             Classification.MISSING_PREREQUISITE.value,
             Classification.TRANSIENT.value,
             Classification.AGENT_ERROR.value))
        self.assertEqual(UNCLASSIFIED, Classification.UNKNOWN.value)
        self.assertNotIn(UNCLASSIFIED, CLASSIFICATIONS)

    def test_retryable_pair_comes_from_the_schema(self):
        self.assertEqual(
            sorted(RETRYABLE),
            [Classification.AGENT_ERROR.value, Classification.TRANSIENT.value])
        for value in RETRYABLE:
            self.assertIn(value, CLASSIFICATIONS)

    def test_canonical_coerces_or_falls_back(self):
        self.assertEqual(canonical("TRANSIENT"), "transient")
        self.assertEqual(canonical("  Agent_Error "), "agent_error")
        self.assertEqual(canonical(Classification.NEEDS_COMMANDER),
                         "needs_commander")
        self.assertEqual(canonical("nonsense"), UNCLASSIFIED)
        self.assertEqual(canonical(None), UNCLASSIFIED)
        self.assertEqual(canonical("nonsense", default="transient"),
                         "transient")

    def test_canonical_returns_a_plain_string_not_a_member(self):
        # The declared floor is Python 3.10, where formatting a str-mixin
        # member prints "Classification.TRANSIENT". `canonical` is the
        # boundary that keeps that from reaching a report or a prompt.
        value = canonical(Classification.TRANSIENT)
        self.assertIsInstance(value, str)
        self.assertEqual(value, "transient")

    def test_classify_action_accepts_unnormalised_input(self):
        # Any caller's spelling of a class routes exactly as the canonical
        # one does — normalisation is not the caller's job.
        self.assertEqual(classify_action(" NEEDS_COMMANDER ", "stuck", 0, 2),
                         "human")
        self.assertEqual(classify_action("TRANSIENT", "stuck", 0, 2), "retry")
        self.assertEqual(classify_action("nonsense", "failed", 0, 2),
                         "deferred")

    def test_both_prompts_take_their_menu_from_one_source(self):
        # The instruction a worker reads and the vocabulary the parser
        # accepts are the same object, so they cannot drift apart. The
        # diagnosis prompt still offers the CLASSIFICATION menu; the mission
        # prompt now offers the receipt, from the module that parses it.
        menu = "CLASSIFICATION: <" + " | ".join(CLASSIFICATIONS) + ">"
        root = make_root(plan_containing([("EXECUTABLE", "do the thing")]))
        item = read_plan(root).first_executable()
        result = StubWorker([]).run(root, "x")
        self.assertIn(menu, diagnosis_prompt(root, item, "stuck", result))
        self.assertIn(" | ".join(receipt_format.STATUSES),
                      impl_prompt(root, item))
        self.assertIn(receipt_format.MARKER, impl_prompt(root, item))


class RobustParsingTests(unittest.TestCase):
    """Phase 2: malformed, misspelled and padded-out answers.

    A worker that answers badly is still answering, and the supervisor has to
    read it: fold what is recognisable onto the schema, keep the raw text
    verbatim, and refuse to guess at everything else.
    """

    def test_canonical_values_are_read_verbatim(self):
        for value in CLASSIFICATIONS + (UNCLASSIFIED,):
            diagnosis = diagnose_output(
                "CLASSIFICATION: {}\n".format(value))
            self.assertEqual(diagnosis.classification, value)
            self.assertEqual(diagnosis.match, Match.EXACT)
            self.assertEqual(diagnosis.source, Source.WORKER)
    def test_padding_and_markup_do_not_hide_the_value(self):
        cases = {
            "  CLASSIFICATION:   transient  \n": "transient",
            "**CLASSIFICATION:** agent_error\n": "agent_error",
            "- `CLASSIFICATION: needs_commander`\n": "needs_commander",
            "> CLASSIFICATION: missing_prerequisite\n":
                "missing_prerequisite",
            "CLASSIFICATION = transient\n": "transient",
            "classification:transient\n": "transient",
            "CLASSIFICATION: Transient.\n": "transient",
            "CLASSIFICATION: \"transient\"\n": "transient",
        }
        for text, expected in cases.items():
            diagnosis = diagnose_output(text)
            self.assertEqual(diagnosis.classification, expected, text)
            self.assertEqual(diagnosis.match, Match.EXACT, text)

    def test_synonyms_and_misspellings_fold_onto_the_schema(self):
        # `exact` where the label's own tokens ARE the canonical value
        # ("agent-error" -> agent_error); `alias` where a synonym had to be
        # folded onto a class whose value the label never spelled.
        cases = [
            ("agent-error", "agent_error", Match.EXACT),
            ("agent error", "agent_error", Match.EXACT),
            ("needs commander", "needs_commander", Match.EXACT),
            ("needs_commander", "needs_commander", Match.EXACT),
            ("missing prerequisite", "missing_prerequisite", Match.EXACT),
            ("Transient", "transient", Match.EXACT),
            ("transient_error", "transient", Match.ALIAS),
            ("transient failure", "transient", Match.ALIAS),
            ("Transient-Error", "transient", Match.ALIAS),
            ("flaky", "transient", Match.ALIAS),
            ("retryable", "transient", Match.ALIAS),
            ("timeout", "transient", Match.ALIAS),
            ("server error", "transient", Match.ALIAS),
            ("rate limited", "transient", Match.ALIAS),
            ("my mistake", "agent_error", Match.ALIAS),
            ("lost the thread", "agent_error", Match.ALIAS),
            ("commander decision required", "needs_commander", Match.ALIAS),
            ("human decision required", "needs_commander", Match.ALIAS),
            ("missing prereq", "missing_prerequisite", Match.ALIAS),
            ("not implemented yet", "missing_prerequisite", Match.ALIAS),
            ("blocked", "missing_prerequisite", Match.ALIAS),
        ]
        for label, expected, match in cases:
            diagnosis = diagnose_output(
                "CLASSIFICATION: {}\n".format(label))
            self.assertEqual(diagnosis.classification, expected, label)
            self.assertEqual(diagnosis.match, match, label)
            self.assertEqual(diagnosis.raw, label, label)

    def test_a_synonym_is_not_folded_onto_a_class_it_only_mentions(self):
        # "server error" must stay transient: substring matching would have
        # found "error" inside "agent_error" and retried the wrong thing.
        diagnosis = diagnose_output("CLASSIFICATION: server error\n")
        self.assertEqual(diagnosis.classification, "transient")
        self.assertNotEqual(diagnosis.classification, "agent_error")

    def test_off_vocabulary_text_is_recorded_but_never_upgraded(self):
        for label in ("it is complicated", "banana", "error",
                      "not a commander issue", "maybe transient?",
                      "gateway error"):
            diagnosis = diagnose_output(
                "CLASSIFICATION: {}\nREASON: something happened\n".format(
                    label))
            self.assertEqual(diagnosis.classification, UNCLASSIFIED, label)
            self.assertEqual(diagnosis.match, Match.NONE, label)
            self.assertEqual(diagnosis.raw, label, label)
            self.assertEqual(diagnosis.reason, "something happened", label)

    def test_the_raw_value_becomes_the_reason_when_none_was_given(self):
        diagnosis = diagnose_output("CLASSIFICATION: banana\n")
        self.assertEqual(diagnosis.classification, UNCLASSIFIED)
        self.assertIn("banana", diagnosis.reason)

    def test_explicit_unknown_is_an_answer_not_drift(self):
        # Ways of saying "I cannot say" that are not the canonical value.
        # Each is read as UNKNOWN cleanly, so it draws no drift warning.
        for label in ("none", "n/a", "unclear", "indeterminate", "?"):
            diagnosis = diagnose_output(
                "CLASSIFICATION: {}\n".format(label))
            self.assertEqual(diagnosis.classification, UNCLASSIFIED, label)
            self.assertEqual(diagnosis.match, Match.EXPLICIT, label)

    def test_empty_and_placeholder_values_cost_no_second_call(self):
        # The tag is present, so a follow-up call is not justified: the
        # worker already answered, badly. Recorded as unknown instead.
        for text in ("CLASSIFICATION:\n",
                     "CLASSIFICATION:   \n",
                     "CLASSIFICATION: <needs_commander | transient>\n"):
            diagnosis = diagnose_output(text)
            self.assertEqual(diagnosis.classification, UNCLASSIFIED, text)
            self.assertEqual(diagnosis.match, Match.NONE, text)
            self.assertIsNotNone(parse_classification(text)[0], text)

    def test_absent_tag_is_the_only_case_that_asks_again(self):
        for text in ("", None, "just prose\n",
                     "I would print CLASSIFICATION: transient if it worked"):
            diagnosis = diagnose_output(text)
            self.assertIsNone(diagnosis.classification, text)
            self.assertEqual(diagnosis.match, Match.ABSENT, text)
            self.assertEqual(parse_classification(text), (None, None), text)

    def test_reason_may_wrap_onto_following_lines(self):
        text = ("CLASSIFICATION: transient\n"
                "REASON: the gateway returned 502\n"
                "  and the retry also 502ed\n")
        self.assertEqual(parse_classification(text)[1],
                         "the gateway returned 502 and the retry also 502ed")

    def test_reason_survives_an_empty_marker_with_a_wrapped_answer(self):
        text = ("CLASSIFICATION: transient\n"
                "REASON:\n   wrapped onto the next line\n")
        self.assertEqual(parse_classification(text)[1],
                         "wrapped onto the next line")

    def test_reason_stops_at_the_next_tag_or_a_blank_line(self):
        text = ("CLASSIFICATION: transient\nREASON: one line\n"
                "CLASSIFICATION: agent_error\nREASON: the real one\n")
        self.assertEqual(parse_classification(text),
                         ("agent_error", "the real one"))
        text = ("CLASSIFICATION: transient\nREASON: first paragraph\n\n"
                "An unrelated paragraph follows.\n")
        self.assertEqual(parse_classification(text)[1], "first paragraph")

    def test_reason_is_still_bounded_to_one_line(self):
        text = "CLASSIFICATION: transient\nREASON: " + ("word " * 200) + "\n"
        reason = parse_classification(text)[1]
        self.assertLessEqual(len(reason), 200)
        self.assertTrue(reason.endswith("..."))
        self.assertNotIn("\n", reason)

    def test_inverted_order_is_read_by_tag_not_by_position(self):
        text = "REASON: answered out of order\nCLASSIFICATION: agent_error\n"
        self.assertEqual(parse_classification(text),
                         ("agent_error", "answered out of order"))

    def test_the_value_is_that_line_alone(self):
        text = ("CLASSIFICATION: transient\n"
                "The gateway 502ed twice, which is what I would have said.\n")
        diagnosis = diagnose_output(text)
        self.assertEqual(diagnosis.classification, "transient")
        self.assertEqual(diagnosis.raw, "transient")
        self.assertEqual(diagnosis.reason, "")

    def test_prose_mentioning_the_markers_is_still_prose(self):
        text = ("The CLASSIFICATION: line is what I print, and REASON: is\n"
                "what follows it.\n")
        self.assertEqual(parse_classification(text), (None, None))


class DiagnosisTraceTests(unittest.TestCase):
    """Phase 2: the audit trail saying HOW a class was obtained."""

    def test_verbatim_in_band_reading_says_nothing(self):
        diagnosis = diagnose_output(
            "CLASSIFICATION: transient\nREASON: 502\n")
        self.assertEqual(diagnosis_trace(3, diagnosis), [])

    def test_explicit_unknown_is_not_treated_as_drift(self):
        diagnosis = diagnose_output("CLASSIFICATION: unknown\n")
        self.assertEqual(diagnosis_trace(3, diagnosis), [])

    def test_alias_match_is_noted_not_warned(self):
        diagnosis = diagnose_output("CLASSIFICATION: transient_error\n")
        trace = diagnosis_trace(3, diagnosis)
        self.assertEqual([level for level, _ in trace], ["note"])
        self.assertIn("transient_error", trace[0][1])
        self.assertIn("alias", trace[0][1])

    def test_unrecognised_value_warns_and_names_the_default(self):
        diagnosis = diagnose_output("CLASSIFICATION: banana\n")
        trace = diagnosis_trace(3, diagnosis)
        self.assertEqual([level for level, _ in trace], ["warning"])
        self.assertIn("banana", trace[0][1])
        self.assertIn(UNCLASSIFIED, trace[0][1])

    def test_follow_up_call_is_reported_as_a_fallback(self):
        diagnosis = diagnose_output(
            "CLASSIFICATION: transient\n")._replace(source=Source.FOLLOW_UP)
        trace = diagnosis_trace(3, diagnosis)
        self.assertEqual([level for level, _ in trace], ["warning"])
        self.assertIn("follow-up", trace[0][1])

    def test_failed_diagnosis_call_warns_with_its_reason(self):
        diagnosis = Diagnosis(UNCLASSIFIED, "diagnosis call failed: nope", "",
                              Match.NONE, Source.ERROR)
        messages = " ".join(message for _, message
                            in diagnosis_trace(3, diagnosis))
        self.assertIn("could not run", messages)
        self.assertIn("nope", messages)

    def test_gate_source_is_not_warned_about(self):
        diagnosis = Diagnosis("needs_commander", "a gate is open", "",
                              Match.EXACT, Source.GATE)
        self.assertEqual(diagnosis_trace(3, diagnosis), [])


class DiagnosisTelemetryTests(unittest.TestCase):
    """Phase 2: drift, fallback and failure reach the durable run report."""

    def _run(self, root, worker, **kwargs):
        out = io.StringIO()
        kwargs.setdefault("notifier", RecordingNotifier())
        kwargs.setdefault("usage_reporter", ZeroUsage())
        code = Supervisor(root, worker_factory=lambda name: worker, out=out,
                          **kwargs).run()
        return code, out.getvalue(), worker

    @staticmethod
    def _report(root):
        return open(run_report_path(root), encoding="utf-8").read()

    def test_unrecognised_classification_warns_in_the_run_report(self):
        root = make_root(plan_containing([("EXECUTABLE", "hopeless")]))
        worker = StubWorker([
            (1, "Tried things.\nCLASSIFICATION: banana\n"
                "REASON: I am a teapot\n"),
        ])
        code, out, _ = self._run(root, worker)
        self.assertEqual(code, STOP_ERROR)
        report = self._report(root)
        self.assertIn("WARNING: unrecognised classification 'banana'", report)
        self.assertIn("recorded as '{}'".format(UNCLASSIFIED), report)
        # Handled as an unclassifiable cycle, never as a class it does not
        # name: a crash is deferred, not retried.
        self.assertIn("DEFERRED (unknown)", report)
        self.assertIn("I am a teapot", report)
        self.assertIn("warning: unrecognised classification", out)

    def test_alias_match_is_noted_and_routes_by_the_class_it_names(self):
        # Two attempts are asked for explicitly: one attempt per mission is
        # the default (mission 124), and a test about RETRY routing has to
        # buy the retry it needs rather than inherit it.
        root = make_root(plan_containing([("EXECUTABLE", "flaky one")]))
        worker = StubWorker([
            (0, "Hiccup.\nCLASSIFICATION: transient_error\n"
                "REASON: gateway 502\n"),
            (0, "", plugin_done_text("flaky one")),
        ])
        code, _, _ = self._run(root, worker, max_attempts=2)
        self.assertEqual(code, STOP_OK)
        report = self._report(root)
        self.assertIn("NOTE: off-vocabulary classification 'transient_error' "
                      "matched 'transient' by alias", report)
        self.assertNotIn("WARNING", report)

    def test_no_follow_up_call_is_ever_made(self):
        # A crash says nothing in-band, and that is the end of it: one
        # invocation, one request. The cycle is recorded as unknown with the
        # worker's own text, and the mission is deferred rather than re-run
        # against the same wall.
        root = make_root(plan_containing([("EXECUTABLE", "crashes once")]))
        worker = StubWorker([
            (1, "boom\n"),
            (0, "CLASSIFICATION: agent_error\nREASON: I misread it\n"),
            (0, "", plugin_done_text("crashes once")),
        ])
        code, out, worker = self._run(root, worker)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(worker.calls), 1)       # no second invocation
        report = self._report(root)
        self.assertIn("DEFERRED (unknown)", report)
        self.assertNotIn("follow-up diagnosis call", report)
        self.assertNotIn("asking the worker why", out)


class ClassifyActionTests(unittest.TestCase):
    """Phase 1: the retry-vs-defer decision, as a pure function."""

    def test_skip_classes_act_immediately_without_spending_the_budget(self):
        # "Cannot be done" must skip NOW, not after wasting the budget.
        self.assertEqual(
            classify_action("missing_prerequisite", "stuck", 0, 2), "blocked")
        self.assertEqual(
            classify_action("needs_commander", "stuck", 0, 2), "human")
        self.assertEqual(
            classify_action("missing_prerequisite", "failed", 0, 2), "blocked")

    def test_explicitly_retryable_classes_retry_then_defer(self):
        for classification in ("transient", "agent_error"):
            self.assertEqual(
                classify_action(classification, "failed", 0, 2), "retry")
            self.assertEqual(
                classify_action(classification, "failed", 1, 2), "deferred")
            self.assertEqual(
                classify_action(classification, "stuck", 1, 2), "deferred")

    def test_silence_after_a_clean_exit_retries_like_it_always_did(self):
        # A mission that hiccupped once must not be skipped for the rest of
        # the run on no evidence.
        self.assertEqual(
            classify_action(UNCLASSIFIED, "stuck", 0, 2), "retry")
        self.assertEqual(
            classify_action(UNCLASSIFIED, "stuck", 1, 2), "deferred")

    def test_silence_after_a_crash_defers_rather_than_re_burning(self):
        # Session 41 kept its meaning: nobody could explain the crash, so
        # running it again is the same tokens against the same wall.
        self.assertEqual(
            classify_action(UNCLASSIFIED, "failed", 0, 2), "deferred")

    def test_no_classification_extends_the_budget(self):
        # A worker cannot talk its way into more cycles than max_attempts.
        for classification in CLASSIFICATIONS:
            self.assertNotEqual(
                classify_action(classification, "stuck", 5, 2), "retry")
        self.assertNotEqual(
            classify_action(UNCLASSIFIED, "stuck", 5, 2), "retry")

    def test_a_single_attempt_budget_defers_rather_than_retrying(self):
        self.assertEqual(
            classify_action("transient", "failed", 0, 1), "deferred")


class Phase1DiagnosisTests(unittest.TestCase):
    """Phase 1 end to end: a mission that stops without completing is
    diagnosed, then retried, skipped-with-a-reason, or parked for the
    commander — and in every case the run keeps working on whatever else is
    independent instead of stopping at the first hard mission."""

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

    @staticmethod
    def _blockers(root):
        with open(os.path.join(root, ".agent", "BLOCKERS.md"),
                  encoding="utf-8") as handle:
            return handle.read()

    @staticmethod
    def _report(root):
        return open(run_report_path(root), encoding="utf-8").read()

    def test_in_band_classification_skips_the_follow_up_call(self):
        # The cheap path: the worker explained itself, so the supervisor must
        # not spend a second call asking.
        root = make_root(plan_containing([("EXECUTABLE", "hopeless")]))
        worker = StubWorker([
            (0, "Tried.\nCLASSIFICATION: missing_prerequisite\n"
                "REASON: the C backend has no struct support yet\n"),
        ])
        code, out, calls, _ = self._run(root, worker=worker)
        self.assertEqual(len(calls), 1)             # no diagnosis call
        self.assertIn("diagnosis: missing_prerequisite", out)

    def test_missing_prerequisite_blocks_records_and_continues(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "needs a missing feature"),
            ("EXECUTABLE", "independent"),
        ]))
        worker = StubWorker([
            (0, "Cannot build this.\nCLASSIFICATION: missing_prerequisite\n"
                "REASON: no OS syscall layer exists yet\n"),
            (0, "", plugin_done_text("independent")),
        ])
        notifier = RecordingNotifier()
        code, out, calls, _ = self._run(root, worker=worker, notifier=notifier)
        # The blocked mission is a wall, not a failure: the run reports the
        # same clean stop the worker-declared BLOCKED path always did.
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 2)
        self.assertIn("independent", calls[1]["prompt"])
        items = read_plan(root).items
        self.assertEqual(items[0].tag, "BLOCKED")
        self.assertIn("no OS syscall layer exists yet", self._blockers(root))
        self.assertIn("no OS syscall layer exists yet",
                      self._report(root) + items[0].text)
        titles = [t for t, _, _ in notifier.calls]
        self.assertIn("Ine · task blocked", titles)

    def test_needs_commander_records_a_blocker_and_ends_pending(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "needs a language decision"),
            ("EXECUTABLE", "independent"),
        ]))
        worker = StubWorker([
            (0, "Stopped.\nCLASSIFICATION: needs_commander\n"
                "REASON: two syntaxes are equally valid; pick one\n"),
            (0, "", plugin_done_text("independent")),
        ])
        notifier = RecordingNotifier()
        code, out, calls, _ = self._run(root, worker=worker, notifier=notifier)
        self.assertEqual(code, STOP_HUMAN)          # a real gate is open
        self.assertEqual(len(calls), 2)             # independent work still ran
        self.assertIn("independent", calls[1]["prompt"])
        self.assertEqual(read_plan(root).items[0].tag, "BLOCKED")
        blockers = self._blockers(root)
        self.assertIn("two syntaxes are equally valid", blockers)
        self.assertIn("Awaiting a commander resolution", blockers)
        titles = [t for t, _, _ in notifier.calls]
        self.assertIn("Ine · decision required", titles)

    def test_transient_retry_carries_the_reason_into_the_next_prompt(self):
        # A retry that repeats the failed attempt verbatim is just the same
        # tokens again, so the reason must reach the retried prompt.
        root = make_root(plan_containing([("EXECUTABLE", "flaky")]))
        worker = StubWorker([
            (1, "Crash.\nCLASSIFICATION: transient\nREASON: gateway returned 502\n"),
            (0, "", plugin_done_text("flaky")),      # the retry succeeds
        ])
        notifier = RecordingNotifier()
        code, out, calls, _ = self._run(
            root, worker=worker, max_attempts=2, notifier=notifier)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("FAILED PREVIOUS ATTEMPT", calls[0]["prompt"])
        retried = calls[1]["prompt"]
        self.assertIn("FAILED PREVIOUS ATTEMPT", retried)
        self.assertIn("gateway returned 502", retried)
        self.assertIn("transient", retried)
        titles = [t for t, _, _ in notifier.calls]
        self.assertIn("Ine · retrying task", titles)

    def test_exhausted_transient_defers_with_the_reason_recorded(self):
        root = make_root(plan_containing([("EXECUTABLE", "flaky forever")]))
        worker = StubWorker([
            (1, "Crash.\nCLASSIFICATION: transient\nREASON: gateway 502\n"),
            (1, "Crash.\nCLASSIFICATION: transient\nREASON: gateway 502\n"),
        ])
        code, out, calls, _ = self._run(
            root, worker=worker, max_attempts=2)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 2)
        self.assertIn("retries exhausted", out)
        report = self._report(root)
        self.assertIn("RETRIES EXHAUSTED (transient)", report)
        self.assertIn("- exit: 1", report)
        item = read_plan(root).items[0]
        self.assertIn("retries exhausted after 2 attempt(s)", item.text)
        self.assertIn("gateway 502", item.text)

    def test_a_skipped_mission_is_never_picked_again_in_the_same_run(self):
        # The point of deferral: the hard mission costs its budget ONCE.
        root = make_root(plan_containing([
            ("EXECUTABLE", "hopeless"),
            ("EXECUTABLE", "independent"),
        ]))
        worker = StubWorker([
            (0, "No.\nCLASSIFICATION: missing_prerequisite\nREASON: no layer\n"),
            (0, "", plugin_done_text("independent")),
        ])
        code, out, calls, _ = self._run(root, worker=worker, max_cycles=10)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("hopeless", calls[1]["prompt"])

    def test_a_crashing_worker_costs_exactly_one_invocation(self):
        root = make_root(plan_containing([("EXECUTABLE", "crashed")]))
        worker = StubWorker([(1, "boom")])
        code, out, calls, _ = self._run(root, worker=worker, max_attempts=2)
        self.assertEqual(len(calls), 1)             # no diagnosis call
        self.assertIn("diagnosis: unknown", out)
        self.assertIn("no classification", out)

    def test_the_diagnosis_prompt_still_exists_for_the_planner_and_humans(self):
        # The loop no longer spends a call on it; the prompt remains a
        # shipped tool for whoever wants to ask a worker the same question.
        root = make_root(plan_containing([("EXECUTABLE", "crashed")]))
        item = read_plan(root).first_executable()
        result = StubWorker([]).run(root, "x")
        result.output = "boom"
        result.exit_code = 1
        prompt = diagnosis_prompt(root, item, "failed", result)
        self.assertIn("Do NOT use any tools", prompt)
        self.assertIn("CLASSIFICATION:", prompt)
        self.assertIn("crashed", prompt)            # the mission it diagnoses
        self.assertIn("boom", prompt)               # the tail that witnessed it
        self.assertIn("exit code 1", prompt)

    def test_an_unclassifiable_cycle_reports_the_workers_own_text(self):
        root = make_root(plan_containing([("EXECUTABLE", "crashed")]))
        worker = StubWorker([(1, "boom")])
        code, out, calls, _ = self._run(root, worker=worker, max_attempts=2)
        self.assertIn("diagnosis: unknown", out)
        self.assertIn("boom", out + self._report(root))

    def test_diagnosis_prompt_carries_the_outcome_and_the_output_tail(self):
        root = make_root(plan_containing([("EXECUTABLE", "problem mission")]))
        item = read_plan(root).first_executable()
        result = StubWorker([]).run(root, "x")
        result.output = "beginning\n" + ("filler\n" * 400) + "THE END"
        prompt = diagnosis_prompt(root, item, "failed", result)
        self.assertIn("problem mission", prompt)
        self.assertIn("'failed'", prompt)
        self.assertIn("THE END", prompt)           # the tail, not the setup
        self.assertNotIn("beginning", prompt)

    def test_retry_block_states_the_failure_and_forbids_a_repeat(self):
        block = retry_block("transient", "gateway 502")
        self.assertIn("transient", block)
        self.assertIn("gateway 502", block)
        self.assertIn("Do not simply repeat the approach that failed", block)
        # A retry with no reason still has to send something honest.
        self.assertIn("(no reason given)", retry_block("transient", ""))

    def test_retry_block_is_not_leaked_into_a_different_mission(self):
        # The note is keyed on mission identity: if the plan advanced to the
        # next mission between the failure and the retry, it must not appear
        # in that mission's prompt.
        root = make_root(plan_containing([("EXECUTABLE", "first")]))
        supervisor = Supervisor(
            root, worker_factory=lambda name: StubWorker([]),
            notifier=RecordingNotifier(), usage_reporter=ZeroUsage())
        supervisor._retry_note = ("some-other-mission", "transient", "502")
        worker = StubWorker([(0, "done")])
        supervisor.worker_factory = lambda name: worker
        supervisor._run_task(read_plan(root).first_executable())
        self.assertNotIn("FAILED PREVIOUS ATTEMPT", worker.calls[0]["prompt"])
        self.assertIsNone(supervisor._retry_note)

    def test_impl_prompt_demands_the_receipt_not_prose_bookkeeping(self):
        root = make_root(plan_containing([("EXECUTABLE", "do the thing")]))
        prompt = impl_prompt(root, read_plan(root).first_executable())
        self.assertIn(receipt_format.MARKER, prompt)
        self.assertIn("Do not delegate, browse, or ask questions", prompt)
        for status in receipt_format.STATUSES:
            self.assertIn(status, prompt)

    def test_run_report_names_the_diagnosis_for_every_path(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "blocked one"),
        ]))
        worker = StubWorker([
            (0, "No.\nCLASSIFICATION: missing_prerequisite\nREASON: no layer\n"),
        ])
        self._run(root, worker=worker)
        report = self._report(root)
        self.assertIn("cannot be built yet (missing_prerequisite)", report)


class MeasureTests(unittest.TestCase):
    """Phase 3: re-measuring the loop from its own records.

    "Did it get better?" has to be a number. These pin the reading of
    `.agent/RUN_REPORTS.md` (cycles, outcomes, provider usage per run) and
    the aggregate, so the comparison after a change is mechanical rather
    than remembered.
    """

    REPORT = (
        "# .agent/RUN_REPORTS.md\n"
        "\n"
        "### run 2026-09-17 19:38:05 (pid 111)\n"
        "- command: ine-agent run\n"
        "- usage start: 10 requests, 1,000 in / 100 out tokens, $0.0000\n"
        "- mission [cycle 1]: the first mission\n"
        "- [cycle 1] RETRY (transient)\n"
        "- mission [cycle 2]: the second mission\n"
        "- [cycle 2] RETRIES EXHAUSTED (unknown)\n"
        "- usage [cycle 2]: +2 requests, +200 in / +20 out tokens\n"
        "- usage end: 12 requests, 1,200 in / 120 out tokens, $0.0000\n"
        "- usage delta (run): +2 requests, +200 in / +20 out tokens\n"
        "- exit: 1\n"
        "- summary: missions deferred after failing.\n"
        "\n"
        "### run 2026-09-17 20:35:26 (pid 222)\n"
        "- command: ine-agent run\n"
        "- mission [cycle 1]: the first mission\n"
        "- [cycle 1] DONE\n"
        "- mission [cycle 2]: the second mission\n"
        "- [cycle 2] PARKED after 2 failed run(s) (unknown)\n"
        "- [cycle 2] BLOCKED — recorded and deferred\n"
        "- usage delta (run): +1 requests, +10,885 in / +35 out tokens\n"
        "- exit: 0\n"
        "\n"
        "### run 2026-09-17 23:28:12 (pid 333)\n"
        "- command: ine-agent run\n"
        "- exit: 2\n"
        "\n"
        "### run 2026-09-18 00:05:51 (pid 444)\n"
        "- command: ine-agent run\n"
        "- mission [cycle 1]: the first mission\n"
    )

    def _root(self, report=None):
        root = make_root(plan_containing([("EXECUTABLE", "anything")]))
        if report is not None:
            with open(run_report_path(root), "w", encoding="utf-8") as handle:
                handle.write(report)
        return root

    def test_rows_carry_cycles_outcomes_and_usage(self):
        runs = measure.parse_report(self.REPORT)
        self.assertEqual(len(runs), 4)
        first, second, third, fourth = runs
        self.assertEqual(first["started"], "2026-09-17 19:38:05")
        self.assertEqual((first["cycles"], first["deferred"], first["exit"]),
                         (2, 1, 1))
        self.assertEqual((first["requests"], first["tokens_in"],
                          first["tokens_out"]), (2, 200, 20))
        self.assertEqual((second["cycles"], second["completed"],
                          second["parked"], second["blocked"],
                          second["exit"]), (2, 1, 1, 1, 0))
        self.assertEqual(second["tokens_in"], 10885)
        # A run that stopped at the gate: no cycles, exit 2.
        self.assertEqual((third["cycles"], third["exit"]), (0, 2))
        # An interrupted run (no exit line): unknown, never invented.
        self.assertEqual((fourth["cycles"], fourth["exit"]), (1, None))

    def test_an_empty_or_broken_report_reads_as_no_runs(self):
        self.assertEqual(measure.parse_report(""), [])
        self.assertEqual(measure.parse_report("junk\n- [cycle 1] DONE\n"), [])

    def test_aggregate_separates_barren_runs_from_productive_ones(self):
        root = self._root(self.REPORT)
        runs, totals = measure.summarize(root)
        self.assertEqual(totals["runs"], 4)
        self.assertEqual(totals["cycles"], 5)
        self.assertEqual(totals["completed"], 1)
        self.assertEqual(totals["deferred"], 1)
        self.assertEqual(totals["parked"], 1)
        self.assertEqual(totals["requests"], 3)
        self.assertEqual(totals["barren"], 2)      # two cycles, no result
        text = "\n".join(measure.format_totals(totals))
        self.assertIn("runs that completed nothing: 2 of 4", text)
        self.assertIn("cycles per completion: 5.00", text)

    def test_totals_report_parked_missions_from_the_ledger(self):
        root = self._root(self.REPORT)
        record_failure(root, "an id", "unknown", "no idea", "stuck")
        _, totals = measure.summarize(root)
        self.assertEqual(totals["parked_missions"], 1)
        self.assertIn("parked missions still in the ledger: 1",
                      "\n".join(measure.format_totals(totals)))

    def test_main_reads_a_project_root_and_refuses_a_non_project(self):
        root = self._root(self.REPORT)
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            code = measure.main(["--root", root])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("2026-09-17 19:38:05", text)
        self.assertIn("runs: 4", text)
        with mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(measure.main(["--root", TMP]), 1)


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

    def test_run_subcommand_help_shows_the_phase_3_flags(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "src", "ine_agent", "cli.py"),
             "run", "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--max-failures", proc.stdout)
        self.assertIn("--stall-limit", proc.stdout)

    def test_the_phase_3_flags_reach_the_supervisor(self):
        root = make_root(plan_containing([("EXECUTABLE", "anything")]))
        with mock.patch("ine_agent.cli.Supervisor") as patched:
            patched.return_value.run.return_value = STOP_OK
            code = cli.main(["run", "--root", root])
        self.assertEqual(code, STOP_OK)
        kwargs = patched.call_args.kwargs
        self.assertEqual(kwargs["max_failures"], DEFAULT_MAX_FAILURES)
        self.assertEqual(kwargs["stall_limit"], DEFAULT_STALL_LIMIT)
        with mock.patch("ine_agent.cli.Supervisor") as patched:
            patched.return_value.run.return_value = STOP_OK
            code = cli.main(["run", "--root", root, "--max-failures", "5",
                             "--stall-limit", "0"])
        self.assertEqual(code, STOP_OK)
        kwargs = patched.call_args.kwargs
        self.assertEqual(kwargs["max_failures"], 5)
        self.assertEqual(kwargs["stall_limit"], 0)

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
                worker_factory=lambda name: build_worker(name, root=root),
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


class WorkerCmdShellTests(unittest.TestCase):
    """A `.cmd`/`.bat` worker exe must launch through the shell.

    CreateProcess cannot start a batch file directly; CliWorker bridges
    that by passing shell=True on Windows for batch-style executables
    (e.g. an INE_AGENT_CLAUDE override pointing at a `.cmd` wrapper).
    """

    def _cmd_worker(self, root, body, args=()):
        path = os.path.join(root, "probe_worker.cmd")
        with open(path, "w", encoding="utf-8", newline="\r\n") as handle:
            handle.write("@echo off\r\n" + body)
        worker = CliWorker()
        worker.env_var = None
        worker.cmd_name = "probe_worker"
        worker.default_args = args
        worker._exe = lambda: path
        return worker, path

    def test_cmd_exe_runs_through_shell_with_args(self):
        root = make_root(plan_containing([("EXECUTABLE", "probe")]))
        worker, _ = self._cmd_worker(
            root, 'echo first=[%1] second=[%2]\r\nexit /b 0\r\n',
            args=("hello", "world"))
        result = worker.run(root, "probe")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("first=[hello]", result.output)
        self.assertIn("second=[world]", result.output)

    def test_cmd_exe_relays_utf8_without_cp1252_crash(self):
        root = make_root(plan_containing([("EXECUTABLE", "probe")]))
        worker, _ = self._cmd_worker(
            root, 'echo caf\u00e9 \u0410 \u2510\r\nexit /b 0\r\n')
        result = worker.run(root, "probe")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("caf\u00e9 \u0410 \u2510", result.output)


class WorkerOverrideCommandTests(unittest.TestCase):
    """An env override is a command line, not merely an executable name.

    `INE_AGENT_CLAUDE="python bridge.py"` must start the interpreter with
    the bridge as an argument: CreateProcess cannot run a `.py` itself, and
    the old single-token reading surfaced that as a bare "[WinError 2] …
    could not start claude" naming neither the override nor its cause.
    """

    ENV = "INE_AGENT_PROBE"

    def _worker(self):
        worker = CliWorker()
        worker.name = "probe"
        worker.cmd_name = "probe"
        worker.env_var = self.ENV
        worker.default_args = ()
        return worker

    def _script(self, directory, name="probe_override.py"):
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('import sys\n'
                         'print("argv=" + "|".join(sys.argv[1:]))\n')
        return path

    def test_override_carries_arguments_to_the_target(self):
        root = make_root(plan_containing([("EXECUTABLE", "probe")]))
        script = self._script(root)
        override = '"{}" "{}"'.format(sys.executable, script)
        with mock.patch.dict(os.environ, {self.ENV: override}):
            result = self._worker().run(root, "PROMPT")
        self.assertEqual(result.exit_code, 0)
        # The interpreter token survived the split AND the prompt still
        # lands after the worker's own arguments.
        self.assertIn("argv=PROMPT", result.output)

    def test_quoted_path_with_spaces_splits_into_one_token(self):
        tokens = _split_command('"/opt/bridge dir/bridge.exe" -p')
        self.assertEqual(tokens, ["/opt/bridge dir/bridge.exe", "-p"])

    def test_whitespace_only_override_falls_back_to_the_cli_name(self):
        with mock.patch.dict(os.environ, {self.ENV: "   "}):
            self.assertEqual(self._worker()._command(), ["probe"])

    def test_unstartable_override_names_the_command_and_env_var(self):
        root = make_root(plan_containing([("EXECUTABLE", "probe")]))
        missing = os.path.join(root, "nope", "missing-bridge.exe")
        with mock.patch.dict(os.environ, {self.ENV: missing}):
            result = self._worker().run(root, "PROMPT")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("could not start probe", result.output)
        self.assertIn(self.ENV, result.output)
        self.assertIn("missing-bridge.exe", result.output)

    @unittest.skipUnless(os.name == "nt", "Windows path splitting")
    def test_unquoted_path_with_spaces_stays_one_command(self):
        # The real-world shape on Windows: a repo checked out under
        # "E:\VS Code\..." sets the override to a path containing a space
        # with no quotes around it. Splitting it would break what works.
        root = make_root(plan_containing([("EXECUTABLE", "probe")]))
        spaced = os.path.join(root, "bridge dir")
        os.makedirs(spaced)
        path = os.path.join(spaced, "probe_worker.cmd")
        with open(path, "w", encoding="utf-8", newline="\r\n") as handle:
            handle.write("@echo off\r\necho bridge-ran=[%1]\r\nexit /b 0\r\n")
        with mock.patch.dict(os.environ, {self.ENV: path}):
            result = self._worker().run(root, "PROMPT")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("bridge-ran=[PROMPT]", result.output)

    @unittest.skipUnless(os.name == "nt", "Windows path splitting")
    def test_windows_override_keeps_backslashes(self):
        tokens = _split_command(r'"C:\tools\bridge.exe" --print')
        self.assertEqual(tokens, [r"C:\tools\bridge.exe", "--print"])


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
        # Nothing is lost from the live relay — that is the no-deadlock
        # property. The retained copy is bounded (see
        # `test_output_bound_keeps_head_and_tail`), because a runaway worker
        # must not be able to flood the run report.
        relayed = "".join(seen)
        self.assertEqual(relayed.count("A"), 262144)
        self.assertEqual(relayed.count("B"), 262144)
        self.assertLessEqual(len(result.output),
                             worker.OUTPUT_LIMIT + 200)

    def test_stream_keeps_utf8_surrogatesafe(self):
        root = make_root(plan_containing([("EXECUTABLE", "probe")]))
        seen = []
        result = ProbeWorker(self._probe(root, PROBE_SCRIPT)).run(
            root, "probe", on_line=seen.append)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("caf\u00e9 \u0410 \u2510", result.output)
        self.assertIn("caf\u00e9 \u0410 \u2510", "".join(seen))


class BoundedRuntimeTests(unittest.TestCase):
    """Mission 123: one invocation, a wall-clock bound, bounded output, and
    measurements taken here rather than read out of someone else's database."""

    def _probe(self, root, script):
        path = os.path.join(root, "probe_bounded.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(script)
        return path

    def test_output_bound_keeps_head_and_tail(self):
        text = "HEAD-MARKER\n" + ("filler " * 6000) + "\nTAIL-MARKER"
        bounded = worker.bound_output(text)
        self.assertLessEqual(len(bounded), worker.OUTPUT_LIMIT + 100)
        self.assertIn("HEAD-MARKER", bounded)
        self.assertIn("TAIL-MARKER", bounded)     # the receipt lives here
        self.assertIn("characters dropped by the", bounded)

    def test_output_bound_leaves_short_output_untouched(self):
        text = "short enough\n"
        self.assertEqual(worker.bound_output(text), text)

    def test_a_hanging_worker_is_killed_and_reported_as_a_timeout(self):
        root = make_root(plan_containing([("EXECUTABLE", "probe")]))
        wkr = ProbeWorker(self._probe(root, HANGING_PROBE))
        wkr.timeout = 1
        result = wkr.run(root, "probe")
        self.assertTrue(result.timed_out)
        self.assertEqual(result.exit_code, worker.TIMEOUT_EXIT_CODE)
        self.assertEqual(result.exit_code, 124)
        self.assertIn("exceeded its 1s timeout and was killed", result.output)
        # What the worker said before it hung is kept: a bare "timed out"
        # with no evidence is the least useful line in the report.
        self.assertIn("still thinking", result.output)
        self.assertTrue(result.metrics["timed_out"])

    def test_a_hanging_worker_is_killed_on_the_streaming_path_too(self):
        root = make_root(plan_containing([("EXECUTABLE", "probe")]))
        seen = []
        wkr = ProbeWorker(self._probe(root, HANGING_PROBE))
        wkr.timeout = 1
        result = wkr.run(root, "probe", on_line=seen.append)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.exit_code, 124)
        self.assertIn("still thinking", "".join(seen))
        self.assertIn("still thinking", result.output)

    def test_a_finished_worker_is_not_treated_as_a_timeout(self):
        root = make_root(plan_containing([("EXECUTABLE", "probe")]))
        wkr = ProbeWorker(self._probe(root, PROBE_SCRIPT))
        wkr.timeout = 60
        result = wkr.run(root, "probe")
        self.assertFalse(result.timed_out)
        self.assertEqual(result.exit_code, 0)
        self.assertNotIn("timeout", result.output)

    def test_every_invocation_reports_its_own_measurements(self):
        root = make_root(plan_containing([("EXECUTABLE", "probe")]))
        wkr = ProbeWorker(self._probe(root, STREAM_PROBE))
        wkr.timeout = 60
        result = wkr.run(root, "a prompt of a known size")
        metrics = result.metrics
        self.assertEqual(metrics["prompt_chars"],
                         len("a prompt of a known size"))
        self.assertEqual(metrics["prompt_lines"], 1)
        self.assertEqual(metrics["output_chars"], len(result.output))
        self.assertGreaterEqual(metrics["elapsed_seconds"], 0)
        self.assertFalse(metrics["timed_out"])

    def test_the_stub_worker_measures_too(self):
        # A test double that skipped measurement would make every supervisor
        # test report zeros, which is how a broken metric hides.
        result = StubWorker([(0, "hello")]).run(make_root(
            plan_containing([("EXECUTABLE", "x")])), "the prompt")
        self.assertEqual(result.metrics["prompt_chars"], len("the prompt"))
        self.assertEqual(result.metrics["output_chars"], len("hello"))

    def test_the_run_report_carries_one_metrics_line_per_cycle(self):
        root = make_root(plan_containing([("EXECUTABLE", "do it")]))
        wkr = StubWorker([(0, "", plugin_done_text("do it"))])
        out = io.StringIO()
        Supervisor(root, worker_factory=lambda name: wkr, out=out,
                   notifier=RecordingNotifier(),
                   usage_reporter=ZeroUsage()).run()
        report = open(run_report_path(root), encoding="utf-8").read()
        self.assertIn("- [cycle 1] mission 1: exit 0, prompt ", report)
        self.assertIn("timed_out=False", report)
        # The console says the same thing, so the two cannot disagree.
        self.assertIn("[cycle 1] mission 1: exit 0, prompt ", out.getvalue())

    def test_a_timeout_is_recorded_in_the_run_report(self):
        class TimesOut(StubWorker):
            def run(self, root, prompt, on_line=None):
                result = StubWorker.run(self, root, prompt, on_line=on_line)
                result.timed_out = True
                result.metrics["timed_out"] = True
                return result

        root = make_root(plan_containing([("EXECUTABLE", "hangs")]))
        out = io.StringIO()
        Supervisor(root, worker_factory=lambda name: TimesOut([(1, "boom")]),
                   out=out, notifier=RecordingNotifier(),
                   usage_reporter=ZeroUsage()).run()
        report = open(run_report_path(root), encoding="utf-8").read()
        self.assertIn("timed_out=True", report)

    def test_a_failed_cycle_spends_exactly_one_invocation(self):
        # The core cost property: no second call to ask why. A crash the
        # worker never classified is recorded as unknown, with its own text.
        root = make_root(plan_containing([("EXECUTABLE", "crashes")]))
        wkr = StubWorker([(1, "boom\n")])
        out = io.StringIO()
        code = Supervisor(root, worker_factory=lambda name: wkr, out=out,
                          notifier=RecordingNotifier(),
                          usage_reporter=ZeroUsage()).run()
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(wkr.calls), 1)
        self.assertIn("diagnosis: unknown", out.getvalue())

    def test_the_run_leads_with_its_own_invocation_count(self):
        root = make_root(plan_containing([("EXECUTABLE", "do it")]))
        wkr = StubWorker([(0, "", plugin_done_text("do it"))])
        out = io.StringIO()
        Supervisor(root, worker_factory=lambda name: wkr, out=out,
                   notifier=RecordingNotifier(),
                   usage_reporter=ZeroUsage()).run()
        report = open(run_report_path(root), encoding="utf-8").read()
        self.assertIn("- this run (local): 1 worker invocation(s)", report)
        self.assertIn("this run: 1 worker invocation(s)", out.getvalue())
        # The provider's total is labelled global, never presented as ours.
        self.assertIn("not this run's cost", report)

    def test_a_global_usage_snapshot_is_labelled_as_global(self):
        snapshot = dict(usage.ZERO, requests=1234, cost=5.0)
        text = usage.format_snapshot(snapshot)
        self.assertIn("1234 requests", text)
        self.assertIn("not this run's cost", text)

    def test_a_local_measurement_leads_with_the_invocation_count(self):
        cycles = [{"prompt_chars": 100, "output_chars": 40, "timed_out": False},
                  {"prompt_chars": 200, "output_chars": 60, "timed_out": True}]
        text = usage.format_local(cycles, elapsed_seconds=12.5)
        self.assertIn("2 worker invocation(s)", text)
        self.assertIn("300 prompt chars", text)
        self.assertIn("100 output chars", text)
        self.assertIn("1 timed out", text)
        self.assertIn("12.5s wall clock", text)

    def test_no_cycles_reads_as_no_cycles(self):
        self.assertEqual(usage.format_local([]), "no worker cycles this run")


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

    def test_item_numbers_are_unique(self):
        # The loop keys an execution index on the item number
        # (`.agent/missions/<number>.md`), so a number must appear exactly
        # once: two items sharing one would fight over the same index file.
        items = self._load_plan_items()
        self.assertGreater(len(items), 0)
        numbers = [num for num, _tag, _headline in items]
        duplicates = sorted(n for n in set(numbers) if numbers.count(n) > 1)
        self.assertEqual(duplicates, [],
                         "duplicate item number(s) in PLAN.md: {}".format(
                             duplicates))

    def test_item_numbers_ascend_within_each_section(self):
        # Numbers ascend inside a section, but need not run on across
        # sections: a commander-priority section is inserted above the
        # standing product work and takes the next free numbers, so the plan
        # reads 119-125 then 84-118. The loop reads list order, so the
        # priority section is selected first — which is the point of it.
        groups = self._load_plan_number_groups()
        self.assertGreater(len(groups), 0)
        for heading, numbers in groups:
            for previous, current in zip(numbers, numbers[1:]):
                self.assertLess(
                    previous, current,
                    "item {} follows {} inside {!r} — a section's numbers "
                    "must ascend in list order".format(current, previous,
                                                        heading))

    def _load_plan_number_groups(self):
        """`(section heading, [item numbers])` for the real PLAN.md."""
        plan_path = os.path.join(REPO_ROOT, ".agent", "PLAN.md")
        with open(plan_path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        in_active = False
        section = "(top of Active)"
        groups = []
        for line in lines:
            if line.startswith("## "):
                in_active = line[3:].strip().lower().startswith("active")
                section = line
                continue
            if not in_active:
                continue
            if line.startswith("### "):
                section = line[4:].strip()
                groups.append((section, []))
                continue
            match = re.match(r"^\s*(\d+)\.\s+", line)
            if match:
                if not groups:
                    groups.append((section, []))
                groups[-1][1].append(int(match.group(1)))
        return groups

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


class ControlPlaneHealthTests(unittest.TestCase):
    """Cross-file persistence contract the autonomous loop relies on
    (Mission 67).

    STATE.md's header session must match the latest HISTORY.md session
    heading, and every BLOCKED plan item must stay cross-referenced in
    BLOCKERS.md. A future session that forgets the 'record' step breaks
    these — the fix is a record correction, not a code change.

    Since Session 46 STATE.md is also BOUNDED: it states where the project
    stands, and per-session narrative lives in HISTORY.md. The two size
    assertions below are the guard against a future session silently
    re-bloating it, which is what made every supervisor cycle expensive.
    """

    # STATE.md is read by every cycle (via _distill_state) and by the worker
    # at recording time, so its size is a per-cycle cost. The ceiling is
    # generous against the ~20 KB the Session 46 split produced, and far
    # below the ~98 KB it had grown to.
    STATE_BYTE_CEILING = 40000
    STATE_LINE_CEILING = 600

    def _state_text(self):
        with open(os.path.join(REPO_ROOT, ".agent", "STATE.md"),
                  encoding="utf-8") as f:
            return f.read()

    def test_state_md_stays_bounded(self):
        text = self._state_text()
        size = len(text.encode("utf-8"))
        self.assertLess(
            size, self.STATE_BYTE_CEILING,
            "STATE.md has grown to {} bytes — per-session narrative belongs "
            "in HISTORY.md (append-only), not STATE.md".format(size))
        self.assertLess(
            len(text.splitlines()), self.STATE_LINE_CEILING,
            "STATE.md has grown past {} lines — see AGENTS.md, 'Recording'"
            .format(self.STATE_LINE_CEILING))

    def test_state_md_carries_position_not_session_narrative(self):
        for line in self._state_text().splitlines():
            self.assertFalse(
                re.match(r"^#{2,3} Session \d+", line),
                "STATE.md carries a per-session block heading ({!r}) — those "
                "live in HISTORY.md".format(line[:60]))

    def _state_session(self):
        state_path = os.path.join(REPO_ROOT, ".agent", "STATE.md")
        with open(state_path, encoding="utf-8") as f:
            head = "".join(f.readline() for _ in range(4))
        match = re.search(r"Session (\d+)", head)
        self.assertIsNotNone(
            match, "STATE.md's header line must name a session number")
        return int(match.group(1))

    def _latest_history_session(self):
        history_path = os.path.join(REPO_ROOT, ".agent", "HISTORY.md")
        latest = None
        with open(history_path, encoding="utf-8") as f:
            for line in f:
                match = re.match(r"^#{2,3} Session (\d+)", line)
                if match:
                    latest = int(match.group(1))
        self.assertIsNotNone(
            latest, "HISTORY.md must contain at least one 'Session N' heading")
        return latest

    def test_state_session_header_matches_latest_history_entry(self):
        self.assertEqual(self._state_session(), self._latest_history_session())

    def test_every_blocked_plan_item_cross_referenced_in_blockers(self):
        blockers_path = os.path.join(REPO_ROOT, ".agent", "BLOCKERS.md")
        with open(blockers_path, encoding="utf-8") as f:
            blockers_text = f.read()
        items = PlanHygieneTests()._load_plan_items()
        blocked = [num for num, tag, _ in items if tag == "BLOCKED"]
        self.assertGreaterEqual(
            len(blocked), 1, "plan should carry at least one BLOCKED item")
        for num in blocked:
            self.assertIn(
                str(num), blockers_text,
                "BLOCKED item {} not cross-referenced in BLOCKERS.md"
                .format(num))


class NotesPlanCrossReferenceTests(unittest.TestCase):
    """The research -> record half of the autonomous loop (Mission 68).

    Every plan finding mission (an item whose body promises a `## Mission N`
    section in NOTES.md) must actually have that section, and every
    `## Mission N` section must map back to a numbered plan item. A finding
    mission marked DONE without recording fails loudly here.
    """

    FINDING_MISSION_MARKER = re.compile(r'NOTES "## Mission (\d+)')

    def _notes_sections(self):
        notes_path = os.path.join(REPO_ROOT, ".agent", "NOTES.md")
        sections = set()
        with open(notes_path, encoding="utf-8") as f:
            for line in f:
                match = re.match(r"^## Mission (\d+)", line)
                if match:
                    sections.add(int(match.group(1)))
        return sections

    def _plan_numbers(self):
        plan_path = os.path.join(REPO_ROOT, ".agent", "PLAN.md")
        numbers = set()
        with open(plan_path, encoding="utf-8") as f:
            for line in f:
                match = re.match(r"^\s*(\d+)\.\s*`", line)
                if match:
                    numbers.add(int(match.group(1)))
        return numbers

    def _plan_finding_missions(self):
        plan_path = os.path.join(REPO_ROOT, ".agent", "PLAN.md")
        found = set()
        with open(plan_path, encoding="utf-8") as f:
            for line in f:
                for match in self.FINDING_MISSION_MARKER.finditer(line):
                    found.add(int(match.group(1)))
        return found

    def test_every_plan_finding_mission_is_recorded_in_notes(self):
        sections = self._notes_sections()
        missing = sorted(
            num for num in self._plan_finding_missions()
            if num not in sections
        )
        self.assertEqual(
            missing, [],
            "plan finding mission(s) promised in NOTES.md but never "
            "recorded: {}".format(missing))

    def test_every_notes_mission_maps_back_to_a_plan_item(self):
        plan_numbers = self._plan_numbers()
        orphan = sorted(num for num in self._notes_sections()
                        if num not in plan_numbers)
        self.assertEqual(
            orphan, [],
            "NOTES '## Mission {}' has no matching numbered PLAN item".format(
                orphan[0] if orphan else 0))


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
        root = make_tmp_dir("ineicon-")
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
        # One notification for the thing that needs attention (the block),
        # and one for the run. No per-mission started/done banner: a long
        # queue would spend a notification per mission, which is noise.
        # Bodies are one headline line, not "recorded and deferred…".
        titles = [t for t, _, _ in notifier.calls]
        self.assertNotIn("Ine · task started", titles)
        self.assertNotIn("Ine · task done", titles)
        self.assertIn("Ine · task blocked", titles)
        self.assertIn("Ine · run complete", titles)
        self.assertEqual(titles.count("Ine · run complete"), 1)
        blocked_body = notifier.calls[0][1]
        self.assertIn("predecessor", blocked_body)
        self.assertNotIn("recorded and", blocked_body)
        body = notifier.calls[-1][1]
        self.assertIn("1 completed", body)
        self.assertIn("1 blocked", body)
        self.assertIn(run_report_path(root), notifier.calls[-1][2])

    def test_failed_mission_defers_so_independent_work_runs(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "fragile"),
            ("EXECUTABLE", "independent"),
        ]))
        worker = StubWorker([
            (1, "boom"),                     # fragile: crashed, unexplained
            (0, "", plugin_done_text("independent")),
        ])
        notifier = RecordingNotifier()
        code, out, calls, _ = self._run(root, worker=worker, notifier=notifier)
        self.assertEqual(code, STOP_ERROR)  # a mission failed → exit 1
        self.assertEqual(len(calls), 2)     # failed mission + independent
        self.assertIn("mission not completed", out)
        self.assertIn("independent", calls[1]["prompt"])   # work continued
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
        self.assertNotIn("Ine · task started", titles)
        self.assertIn("Ine · decision required", titles)
        self.assertIn("Ine · run complete", titles)
        self.assertIn("waiting on your decision", notifier.calls[-1][1])

    def test_done_run_fires_one_completion_notification_and_writes_report(self):
        root = make_root(plan_containing([("EXECUTABLE", "do it")]))
        worker = StubWorker([(0, "", plugin_done_text("do it"))])
        notifier = RecordingNotifier()
        code, out, calls, _ = self._run(root, worker=worker, notifier=notifier)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 1)
        # Exactly one notification for the whole run, and it carries the
        # queue's outcome rather than a per-mission banner.
        titles = [t for t, _, _ in notifier.calls]
        self.assertEqual(titles, ["Ine · run complete"])
        body = notifier.calls[0][1]
        self.assertIn("1 completed", body)
        self.assertIn("0 failed", body)
        self.assertTrue(os.path.isfile(run_report_path(root)))
        report = open(run_report_path(root), encoding="utf-8").read()
        self.assertIn("- exit: 0", report)
        self.assertIn("- missions: 1 completed, 0 failed", report)

    def test_stuck_mission_notifies_task_stuck(self):
        # A worker that exits 0 without moving the plan, and says nothing
        # about why, is deferred after its attempts run out: one invocation
        # per attempt, no call spent asking why, and the mission is left
        # with a recorded reason. The run still ends honestly (exit 1) with
        # the commander told it was stuck. Two attempts are asked for
        # explicitly, because one attempt per mission is now the default.
        root = make_root(plan_containing([("EXECUTABLE", "stubborn task")]))
        worker = StubWorker([(0, ""), (0, "")])   # attempt 1, then attempt 2
        notifier = RecordingNotifier()
        code, out, calls, _ = self._run(root, worker=worker, notifier=notifier,
                                        max_attempts=2)
        self.assertEqual(code, STOP_ERROR)          # nothing could finish
        self.assertEqual(len(calls), 2)
        titles = [t for t, _, _ in notifier.calls]
        self.assertNotIn("Ine · task started", titles)
        self.assertTrue(titles.count("Ine · retrying task") >= 1)
        self.assertTrue(titles.count("Ine · task stuck") >= 1)


class QueueExhaustionTests(unittest.TestCase):
    """Mission 124: the queue runs to exhaustion, one attempt per mission."""

    def _run(self, root, worker, **kwargs):
        kwargs.setdefault("notifier", RecordingNotifier())
        kwargs.setdefault("usage_reporter", ZeroUsage())
        out = io.StringIO()
        code = Supervisor(root, worker_factory=lambda name: worker, out=out,
                          **kwargs).run()
        return code, out.getvalue(), list(worker.calls)

    @staticmethod
    def _report(root):
        return open(run_report_path(root), encoding="utf-8").read()

    def test_three_missions_run_to_the_end_with_one_request_each(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "first thing"),
            ("EXECUTABLE", "second thing"),
            ("EXECUTABLE", "third thing"),
        ]))
        worker = StubWorker([
            (0, "", plugin_done_text("first thing")),
            (0, "", plugin_done_text("second thing")),
            (0, "", plugin_done_text("third thing")),
        ])
        code, out, calls = self._run(root, worker)
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(calls), 3)          # one request per mission
        self.assertIn("first thing", calls[0]["prompt"])
        self.assertIn("second thing", calls[1]["prompt"])
        self.assertIn("third thing", calls[2]["prompt"])
        self.assertIn("- this run (local): 3 worker invocation(s)",
                      self._report(root))

    def test_a_failing_mission_does_not_stop_the_ones_after_it(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "fragile"),
            ("EXECUTABLE", "next one"),
            ("EXECUTABLE", "last one"),
        ]))
        worker = StubWorker([
            (1, "boom"),
            (0, "", plugin_done_text("next one")),
            (0, "", plugin_done_text("last one")),
        ])
        code, out, calls = self._run(root, worker)
        self.assertEqual(code, STOP_ERROR)      # something was left unfinished
        self.assertEqual(len(calls), 3)
        self.assertIn("next one", calls[1]["prompt"])
        self.assertIn("last one", calls[2]["prompt"])

    def test_one_attempt_per_mission_is_the_default(self):
        # A mission is not retried unless the commander asks for attempts: a
        # second request is a decision, not something the loop takes by
        # itself.
        parser = cli.build_parser()
        args = parser.parse_args(["run"])
        self.assertEqual(args.max_attempts, 1)
        self.assertIsNone(args.max_missions)

    def test_max_missions_stops_after_the_given_count(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "one"),
            ("EXECUTABLE", "two"),
            ("EXECUTABLE", "three"),
        ]))
        worker = StubWorker([(0, "", plugin_done_text("one")),
                             (0, "", plugin_done_text("two")),
                             (0, "", plugin_done_text("three"))])
        code, out, calls = self._run(root, worker, max_cycles=2)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("three", calls[1]["prompt"])
        self.assertIn("--max-missions bound of 2", out)

    def test_cycle_limit_is_still_accepted_as_an_alias(self):
        args = cli.build_parser().parse_args(["run", "--cycle-limit", "4"])
        self.assertEqual(args.max_missions, 4)
        aliased = cli.build_parser().parse_args(["run", "--max-missions", "4"])
        self.assertEqual(aliased.max_missions, args.max_missions)

    def test_exactly_one_completion_notification_names_the_outcome(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "one"),
            ("EXECUTABLE", "two"),
        ]))
        worker = StubWorker([
            (0, "", plugin_done_text("one")),
            (0, "", plugin_blocked_text("two")),
        ])
        notifier = RecordingNotifier()
        self._run(root, worker, notifier=notifier)
        titles = [t for t, _, _ in notifier.calls]
        self.assertEqual(titles.count("Ine · run complete"), 1)
        body = notifier.calls[-1][1]
        self.assertIn("1 completed", body)
        self.assertIn("1 blocked", body)

    def test_a_run_that_completed_nothing_says_so_in_the_title(self):
        # A popup reading "run complete" is how a run that achieved nothing
        # gets mistaken for a successful one.
        root = make_root(plan_containing([("EXECUTABLE", "hopeless")]))
        worker = StubWorker([(1, "boom")])
        notifier = RecordingNotifier()
        self._run(root, worker, notifier=notifier)
        titles = [t for t, _, _ in notifier.calls]
        self.assertIn("Ine · run ended with nothing completed", titles)
        self.assertIn("0 completed, 1 failed", notifier.calls[-1][1])

    def test_a_refused_mission_is_counted_in_the_summary(self):
        root = make_root(plan_containing([("EXECUTABLE", "no index here")]),
                         indexes=False)
        worker = StubWorker([])
        notifier = RecordingNotifier()
        self._run(root, worker, notifier=notifier)
        # A refused mission is outstanding planner work, so the summary says
        # so rather than reporting a clean queue.
        self.assertIn("1 refused (no execution index)",
                      open(run_report_path(root), encoding="utf-8").read())
        self.assertIn("1 refused (no execution index)", notifier.calls[-1][1])


class PilotRunTests(unittest.TestCase):
    """Mission 125: the whole flow end to end, over a stub worker.

    Three missions in one run — one completes, one fails, one needs the
    commander — which is the shape a real queue produces and the shape every
    earlier mission's unit test avoids. What is pinned here is the contract as
    a whole rather than one part of it: one request per mission, one
    completion summary, a lean prompt, no duplicated control-plane records,
    and a run that terminates.
    """

    def _pilot(self, **kwargs):
        root = make_root(plan_containing([
            ("EXECUTABLE", "measure the thing"),
            ("EXECUTABLE", "break the thing"),
            ("EXECUTABLE", "ask the commander"),
        ]))
        worker = StubWorker([
            (0, receipt_text(status="done", summary="measured it",
                              files=["src/ine/cli.py"],
                              verification=["pytest -q: 1 passed"],
                              area="ine-agent", finding="the handoff is small",
                              follow_up="then record the measured number"),
             plugin_done_text("measure the thing")),
            (1, receipt_text(status="failed", summary="the fixture is wrong")),
            (0, receipt_text(status="needs_commander",
                             summary="which of the two is correct?")),
        ])
        notifier = RecordingNotifier()
        out = io.StringIO()
        kwargs.setdefault("usage_reporter", ZeroUsage())
        started = time.monotonic()
        code = Supervisor(root, worker_factory=lambda name: worker, out=out,
                          notifier=notifier, **kwargs).run()
        return (root, code, out.getvalue(), list(worker.calls), notifier,
                time.monotonic() - started)

    def test_a_three_mission_queue_costs_one_request_per_mission(self):
        root, code, out, calls, notifier, _ = self._pilot()
        # One worker call per mission, each with its own mission and nothing
        # else: no diagnosis call, no automatic retry.
        self.assertEqual(len(calls), 3)
        for index, headline in enumerate(("measure the thing",
                                          "break the thing",
                                          "ask the commander")):
            self.assertIn(headline, calls[index]["prompt"])
        # A commander gate ends the run with the gate's exit code.
        self.assertEqual(code, STOP_HUMAN)
        self.assertIn("needs commander judgment", out)

    def test_the_pilot_pays_for_one_summary_not_three_missions(self):
        root, code, out, calls, notifier, _ = self._pilot()
        titles = [title for title, _, _ in notifier.calls]
        self.assertNotIn("Ine · task started", titles)
        self.assertNotIn("Ine · task done", titles)
        self.assertEqual(titles.count("Ine · run complete"), 1)
        self.assertEqual(titles.count("Ine · decision required"), 1)
        report = self._report(root)
        # Three missions, three buckets, no mission counted twice: a mission
        # that failed is not also "deferred", and a gated mission is counted
        # as blocked because the plan really does tag it BLOCKED.
        self.assertIn("- missions: 1 completed, 1 failed, 1 blocked, "
                      "0 deferred, 1 follow-up(s) proposed; "
                      "1 waiting on your decision", report)

    def test_the_prompt_is_the_mission_and_not_the_control_plane(self):
        root, code, out, calls, notifier, _ = self._pilot()
        prompt = calls[0]["prompt"]
        self.assertIn("measure the thing", prompt)
        self.assertIn("INE_RECEIPT_JSON", prompt)
        # The lean handoff: no plan body, no history, no state snapshot.
        for injected in ("Current ground truth", "## Current focus",
                         "Selection rule", "Session 1"):
            self.assertNotIn(injected, prompt)
        # ...and small enough to state as a number. Measured: 2,944 chars /
        # 64 lines for this mission; 3,111 / 68 with a related snippet.
        self.assertLess(len(prompt), 4000)

    def test_the_pilot_records_each_control_plane_file_exactly_once(self):
        root, code, out, calls, notifier, _ = self._pilot()
        items = read_plan(root).items
        self.assertEqual(len(items), 4)      # 3 missions + 1 filed proposal
        self.assertEqual([item.tag for item in items],
                         ["DONE", "EXECUTABLE", "BLOCKED", "CLAUDE_REVIEW"])
        self.assertTrue(items[3].proposed)
        self.assertIn("follow-up filed as PLAN item", self._report(root))
        report = self._report(root)
        self.assertEqual(report.count("### run "), 1)
        self.assertEqual(report.count("- receipt:"), 1)
        history = open(os.path.join(root, ".agent", "HISTORY.md"),
                       encoding="utf-8").read()
        self.assertEqual(history.count("ine-agent mission 1"), 1)

    def test_the_run_terminates_and_leaves_the_rest_of_the_queue_alone(self):
        root, code, out, calls, notifier, elapsed = self._pilot()
        self.assertLess(elapsed, 30)     # bounded work, no polling
        self.assertIn("missions remain held for commander judgment", out)
        # The failed mission is still EXECUTABLE for a later run: this run
        # deferred it, it did not retire it. The reason rides along as a
        # remark on the item, so only the headline is compared.
        remaining = [item.text.splitlines()[0] for item in read_plan(root).items
                     if item.executable]
        self.assertEqual(remaining, ["`EXECUTABLE` — **break the thing.**"])

    @staticmethod
    def _report(root):
        return open(run_report_path(root), encoding="utf-8").read()


class FollowUpProposalTests(unittest.TestCase):
    """A receipt's follow-up is a proposal, never executable work."""

    def _run(self, root, worker, **kwargs):
        kwargs.setdefault("notifier", RecordingNotifier())
        kwargs.setdefault("usage_reporter", ZeroUsage())
        out = io.StringIO()
        Supervisor(root, worker_factory=lambda name: worker, out=out,
                   **kwargs).run()
        return out.getvalue()

    @staticmethod
    def _report(root):
        return open(run_report_path(root), encoding="utf-8").read()

    def test_a_follow_up_is_filed_as_a_claude_review_item(self):
        root = make_root(plan_containing([("EXECUTABLE", "finish the thing")]))
        worker = StubWorker([(0, receipt_text(
            follow_up="then add the second half"), plugin_done_text(
                "finish the thing"))])
        self._run(root, worker)
        items = read_plan(root).items
        proposals = [i for i in items if i.tag == "CLAUDE_REVIEW"]
        self.assertEqual(len(proposals), 1)
        self.assertIn("then add the second half", proposals[0].text)
        self.assertTrue(proposals[0].proposed)
        self.assertIn("follow-up filed as PLAN item", self._report(root))

    def test_a_proposed_item_is_never_selected_by_a_later_run(self):
        root = make_root(plan_containing([("EXECUTABLE", "finish the thing")]))
        worker = StubWorker([(0, receipt_text(
            follow_up="then add the second half"), plugin_done_text(
                "finish the thing"))])
        self._run(root, worker)
        # The next run must not pick the proposal up: a filed proposal is
        # never executable, whatever tag it carries.
        second = StubWorker([])
        out = io.StringIO()
        code = Supervisor(root, worker_factory=lambda name: second, out=out,
                          notifier=RecordingNotifier(),
                          usage_reporter=ZeroUsage()).run()
        self.assertEqual(second.calls, [])   # nothing executable was left
        self.assertNotIn("[refused]", out.getvalue())
        self.assertEqual(code, STOP_OK)

    def test_the_same_proposal_is_not_filed_twice(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "first half"),
            ("EXECUTABLE", "second half"),
        ]))
        worker = StubWorker([
            (0, receipt_text(follow_up="then wire the two together"),
             plugin_done_text("first half")),
            (0, receipt_text(follow_up="then wire the two together"),
             plugin_done_text("second half")),
        ])
        self._run(root, worker)
        items = read_plan(root).items
        proposals = [i for i in items if i.proposed]
        self.assertEqual(len(proposals), 1)
        self.assertIn("already proposed by an earlier mission",
                      self._report(root))

    def test_a_follow_up_that_restates_the_mission_is_dropped(self):
        root = make_root(plan_containing([("EXECUTABLE", "finish the thing")]))
        worker = StubWorker([(0, receipt_text(
            follow_up="finish the thing"), plugin_done_text(
                "finish the thing"))])
        self._run(root, worker)
        proposals = [i for i in read_plan(root).items if i.proposed]
        self.assertEqual(proposals, [])
        self.assertIn("follow-up dropped: it restates this mission",
                      self._report(root))


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
    while _CREATED_ROOTS:
        _remove_root(_CREATED_ROOTS.pop())


def tearDownModule():
    """Unittest module hook — removes leftover fixture roots on
    `python -m unittest` runs."""
    _clean_temp_roots()


@pytest.fixture(autouse=True)
def _no_temp_root_leftovers():
    """Remove this module's fixture roots after each test, then fail loudly
    if any survived. Autouse because pytest does not invoke the unittest
    `tearDownModule` hook for unittest.TestCase subclasses; without this,
    every `python -m pytest` run would leave `ineagent-*` directories
    behind in `.tmp/`. The assertion is the part that makes a NEW leak
    impossible to miss — the old cleanup failed silently on Windows."""
    yield
    _clean_temp_roots()
    leftovers = _leftover_fixture_dirs()
    assert not leftovers, (
        "fixture directories survived cleanup in {}: {}".format(
            TMP, ", ".join(leftovers)))


class MissionIndexTests(unittest.TestCase):
    """The execution index: the artefact that lets the worker execute
    instead of plan.

    A mission with no index is REFUSED — no worker is launched at all, and
    no cycle is spent — and recorded exactly as a missing prerequisite, so
    the planner's omission shows up in PLAN.md, BLOCKERS.md and the run
    report without costing one provider request.
    """

    def _run(self, root, worker=None, **kwargs):
        worker = worker if worker is not None else StubWorker([])
        out = io.StringIO()
        kwargs.setdefault("usage_reporter", ZeroUsage())
        code = Supervisor(root, worker_factory=lambda name: worker,
                          out=out, **kwargs).run()
        return code, out.getvalue(), worker

    def _item(self, root, needle):
        return next(i for i in read_plan(root).items if needle in i.text)

    def test_index_paths_are_keyed_on_the_plan_item_number(self):
        root = make_root(plan_containing([("EXECUTABLE", "x")]),
                         indexes=False)
        self.assertEqual(
            mission_index_path(root, "7"),
            os.path.join(root, ".agent", "missions", "7.md"))
        self.assertEqual(mission_index_relpath("7"), ".agent/missions/7.md")

    def test_reader_returns_none_for_absent_or_empty_index(self):
        root = make_root(plan_containing([("EXECUTABLE", "x")]),
                         indexes=False)
        self.assertIsNone(read_mission_index(root, "1"))
        write_mission_index(root, "1", "   \n\n")
        self.assertIsNone(read_mission_index(root, "1"))

    def test_writer_creates_the_folder_and_round_trips(self):
        root = make_root(plan_containing([("EXECUTABLE", "x")]),
                         indexes=False)
        self.assertTrue(write_mission_index(root, "3", "Goal: do it."))
        self.assertEqual(read_mission_index(root, "3"), "Goal: do it.")

    def test_a_mission_without_an_index_is_refused_before_any_worker_call(self):
        root = make_root(plan_containing([("EXECUTABLE", "unplanned")]),
                         indexes=False)
        code, out, worker = self._run(root)
        self.assertEqual(worker.calls, [])
        self.assertEqual(code, STOP_ERROR)
        self.assertIn("[refused]", out)
        self.assertIn("no execution index", out)

    def test_a_refusal_is_recorded_as_a_missing_prerequisite(self):
        root = make_root(plan_containing([("EXECUTABLE", "unplanned")]),
                         indexes=False)
        self._run(root)
        item = self._item(root, "unplanned")
        self.assertEqual(item.tag, "BLOCKED")
        self.assertIn("missing prerequisite", item.text)
        self.assertIn("execution index", item.text)

    def test_a_refusal_writes_one_blockers_entry_and_one_report_line(self):
        root = make_root(plan_containing([("EXECUTABLE", "unplanned")]),
                         indexes=False)
        self._run(root)
        blockers = open(os.path.join(root, ".agent", "BLOCKERS.md"),
                        encoding="utf-8").read()
        self.assertIn("Blocked during autonomous runs", blockers)
        self.assertIn("no execution index", blockers)
        report = open(run_report_path(root), encoding="utf-8").read()
        self.assertEqual(
            len([line for line in report.splitlines()
                 if "cannot be built yet" in line]), 1)

    def test_a_refusal_defers_only_that_mission(self):
        root = make_root(plan_containing([
            ("EXECUTABLE", "unplanned"),
            ("EXECUTABLE", "planned"),
        ]), indexes=False)
        write_index(root, "2", "# Mission 2\n\nGoal: the planned one.\n")
        worker = StubWorker([(0, "", plugin_text("planned"))])
        code, out, worker = self._run(root, worker=worker)
        self.assertEqual(len(worker.calls), 1)
        self.assertIn("the planned one.", worker.calls[0]["prompt"])
        self.assertNotIn("unplanned", worker.calls[0]["prompt"])

    def test_a_refusal_does_not_spend_a_worker_cycle(self):
        root = make_root(plan_containing([("EXECUTABLE", "unplanned")]),
                         indexes=False)
        code, out, worker = self._run(root, max_cycles=1)
        self.assertEqual(code, STOP_ERROR)
        self.assertNotIn("Reached the maximum", out)
        self.assertEqual(worker.calls, [])

    def test_an_indexed_mission_still_runs(self):
        root = make_root(plan_containing([("EXECUTABLE", "planned")]))
        write_index(root, "1", "# Mission 1\n\nGoal: the planned one.\n"
                               "\nSteps:\n  1. [ ] do the planned thing\n")
        worker = StubWorker([(0, "", plugin_text("planned"))])
        out = io.StringIO()
        code = Supervisor(root, worker_factory=lambda name: worker, out=out,
                          usage_reporter=ZeroUsage()).run()
        self.assertEqual(code, STOP_OK)
        self.assertEqual(len(worker.calls), 1)
        self.assertIn("1. [ ] do the planned thing", worker.calls[0]["prompt"])

    def test_dry_run_reports_the_index_state_without_writing(self):
        root = make_root(plan_containing([("EXECUTABLE", "unplanned")]),
                         indexes=False)
        out = io.StringIO()
        code = Supervisor(root, out=out, dry_run=True,
                          usage_reporter=ZeroUsage()).run()
        self.assertEqual(code, STOP_OK)
        self.assertIn("[dry-run] REFUSED", out.getvalue())
        self.assertFalse(os.path.isdir(os.path.join(root, ".agent", "missions")))


class PromptContractTests(unittest.TestCase):
    """What the execution worker is told — and what it must never be told.

    Two contradictory instructions used to arrive in the same prompt: the
    planner's "work out how to accomplish it yourself" and the executor's
    "do not continue to further missions". The index system removes the
    first, so a cycle only ever executes.
    """

    def _root(self):
        return make_root(
            plan_containing([("EXECUTABLE", "wire the parser")]),
            worker_prompt_text="Only execute; never plan.\n",
        )

    def test_the_prompt_carries_the_missions_own_index(self):
        root = self._root()
        write_index(root, "1", "# Mission 1\n\nGoal: wire it.\n"
                               "\nSteps:\n  1. [ ] edit supervisor.py\n")
        prompt = impl_prompt(root, read_plan(root).first_executable())
        self.assertIn("Goal: wire it.", prompt)
        self.assertIn("1. [ ] edit supervisor.py", prompt)
        self.assertIn("wire the parser", prompt)

    def test_the_planners_language_never_reaches_the_executor(self):
        root = self._root()
        with open(os.path.join(root, ".agent", "MISSION_PROMPT.md"), "w",
                  encoding="utf-8") as handle:
            handle.write("Figure out how to accomplish it yourself.\n")
        prompt = impl_prompt(root, read_plan(root).first_executable())
        self.assertNotIn("Figure out how to accomplish it yourself.", prompt)
        self.assertNotIn("Only execute; never plan.", prompt)
        self.assertIn("not research it, re-plan it, re-scope it", prompt)

    def test_the_receipt_contract_ends_the_prompt(self):
        root = self._root()
        write_index(root, "1", "# Mission 1\n\nGoal: wire it.\n")
        prompt = impl_prompt(root, read_plan(root).first_executable())
        # Order is the whole contract: rules, then the mission, then the one
        # machine-readable answer the recorder reads.
        self.assertLess(prompt.index("You are the EXECUTION worker"),
                        prompt.index("Mission 1"))
        self.assertLess(prompt.index("Mission 1"),
                        prompt.index("REPORT"))
        self.assertLess(prompt.index("REPORT"),
                        prompt.index(receipt_format.MARKER))
        self.assertNotIn("CLASSIFICATION: <", prompt)

    def test_recording_is_not_the_workers_job(self):
        # The worker used to be told to rewrite STATE, HISTORY, PLAN and
        # NOTES by hand. That is now the recorder's job, done from the
        # receipt, so the instruction is gone rather than reworded.
        root = self._root()
        prompt = impl_prompt(root, read_plan(root).first_executable())
        self.assertNotIn(".agent/HISTORY.md", prompt)
        self.assertNotIn("APPEND a session block", prompt)
        self.assertIn("Do not edit the `.agent/` control-plane files", prompt)


class ReceiptTests(unittest.TestCase):
    """The machine-readable answer a worker ends with.

    A receipt the parser cannot read must be a plain `None` — the one
    condition that never spends another request to disambiguate.
    """

    def test_a_well_formed_receipt_is_read(self):
        receipt = parse_receipt(receipt_text(
            status="done", summary="wired the parser", files=["src/a.py"],
            verification=["pytest -q: 12 passed"], area="parser",
            finding="the front end re-parses on every keystroke",
            follow_up="cache the parse",
        ))
        self.assertIsNotNone(receipt)
        self.assertTrue(receipt.completed)
        self.assertEqual(receipt.status, "done")
        self.assertEqual(receipt.summary, "wired the parser")
        self.assertEqual(receipt.changed_files, ["src/a.py"])
        self.assertEqual(receipt.verification, ["pytest -q: 12 passed"])
        self.assertEqual(receipt.area, "parser")
        self.assertEqual(
            receipt.finding, "the front end re-parses on every keystroke")
        self.assertEqual(receipt.follow_up, "cache the parse")

    def test_optional_fields_may_be_absent(self):
        receipt = parse_receipt(receipt_text())
        self.assertIsNotNone(receipt)
        self.assertIsNone(receipt.area)
        self.assertIsNone(receipt.finding)
        self.assertIsNone(receipt.follow_up)
        self.assertEqual(receipt.changed_files, [])
        self.assertEqual(receipt.verification, [])

    def test_prose_before_the_receipt_is_ignored(self):
        receipt = parse_receipt(receipt_text(prose="Did the work.\nSummary:"))
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.summary, "did what the index asked")

    def test_the_last_marker_wins(self):
        # A worker that restates the contract before complying must still
        # have its answer read, and a marker quoted in prose earlier must not
        # shadow the real one.
        text = (receipt_format.MARKER + "\n"
                + json.dumps({"status": "failed", "summary": "the example"})
                + "\n\n" + receipt_text(status="done", summary="the real one"))
        self.assertEqual(parse_receipt(text).status, "done")

    def test_a_marker_inside_a_line_is_not_a_marker(self):
        self.assertIsNone(parse_receipt(
            "the format is {}\nlook\n".format(receipt_text())))

    def test_unreadable_receipts_are_none_not_guesses(self):
        cases = [
            "no receipt at all",
            receipt_format.MARKER + "\nnot json\n",
            receipt_format.MARKER + "\n[1, 2, 3]\n",
            receipt_format.MARKER + "\n{}\n",
            receipt_format.MARKER + '\n{"status": "done"}\n',   # no summary
            receipt_format.MARKER + '\n{"summary": "no status"}\n',
            receipt_format.MARKER + '\n{"status": "invented", '
                                    '"summary": "off vocabulary"}\n',
        ]
        for text in cases:
            self.assertIsNone(parse_receipt(text), text)

    def test_fields_are_bounded(self):
        receipt = parse_receipt(receipt_text(
            summary="s" * 5000,
            files=["f{}".format(n) for n in range(500)],
            verification=["v{}".format(n) for n in range(500)],
        ))
        self.assertEqual(len(receipt.summary), receipt_format.SUMMARY_LIMIT)
        self.assertEqual(len(receipt.changed_files), receipt_format.LIST_LIMIT)
        self.assertEqual(len(receipt.verification), receipt_format.LIST_LIMIT)

    def test_non_string_list_entries_are_dropped(self):
        text = (receipt_format.MARKER + "\n"
                + json.dumps({"status": "done", "summary": "ok",
                              "changed_files": ["good.py", 3, None, "b.py"]})
                + "\n")
        self.assertEqual(parse_receipt(text).changed_files,
                         ["good.py", "b.py"])

    def test_the_contract_documents_every_status_and_its_own_marker(self):
        contract = receipt_format.contract()
        self.assertIn(receipt_format.MARKER, contract)
        for status in receipt_format.STATUSES:
            self.assertIn(status, contract)
        self.assertIn("never executed automatically", contract)
        # The example in the contract must itself parse, or the prompt is
        # teaching a format the parser rejects.
        self.assertIsNotNone(parse_receipt(
            receipt_format.MARKER + "\n" + receipt_format.EXAMPLE + "\n"))


class DeterministicRecordingTests(unittest.TestCase):
    """A completed mission's records are written from its receipt, in Python.

    The worker used to be asked to append to HISTORY, rewrite STATE's head,
    tag PLAN and add a NOTES section in prose. This is the other half of that
    change: the same four records, written the same way every time, whether
    the worker was thorough or one word long.
    """

    def _root(self, plan=None):
        # A realistic control plane: the two head sections the recorder
        # rewrites, plus a reference section it must leave alone.
        return make_root(
            plan or plan_containing([
                ("EXECUTABLE", "do the thing"),
                ("EXECUTABLE", "the next thing"),
            ]),
            state_text=("Current ground truth as of Session 4\n\n"
                        "## Current focus\n\nold focus line\n\n"
                        "## Health\n\nold health line\n\n"
                        "## Records\n\nkeep this reference exactly\n"),
        )

    def _task(self, root):
        return read_plan(root).first_executable()

    def _receipt(self, **kwargs):
        defaults = dict(status="done", summary="wired the parser",
                        files=["src/parser.py"],
                        verification=["pytest -q: 12 passed"],
                        area="parser")
        defaults.update(kwargs)
        return parse_receipt(receipt_text(**defaults))

    def test_a_done_receipt_tags_the_plan_and_records_everything(self):
        root = self._root()
        task = self._task(root)
        written = record_mission_outcome(
            root, task, self._receipt(finding="a durable fact"), "done")
        self.assertTrue(written["plan"])
        self.assertTrue(written["history"])
        self.assertTrue(written["state"])
        self.assertTrue(written["notes"])
        self.assertIn("`DONE`", read_plan(root).items[0].text)
        history = open(os.path.join(root, ".agent", "HISTORY.md"),
                       encoding="utf-8").read()
        self.assertIn("ine-agent mission 1", history)
        self.assertIn("wired the parser", history)
        self.assertIn("src/parser.py", history)
        self.assertIn("pytest -q: 12 passed", history)
        notes = open(os.path.join(root, ".agent", "NOTES.md"),
                     encoding="utf-8").read()
        self.assertIn("## Mission 1", notes)
        self.assertIn("a durable fact", notes)

    def test_recording_twice_does_not_duplicate_the_history_block(self):
        root = self._root()
        task = self._task(root)
        receipt = self._receipt()
        first = record_mission_outcome(root, task, receipt, "done",
                                       session=7)
        second = record_mission_outcome(root, task, receipt, "done",
                                        session=7)
        self.assertTrue(first["history"])
        self.assertFalse(second["history"])
        history = open(os.path.join(root, ".agent", "HISTORY.md"),
                       encoding="utf-8").read()
        self.assertEqual(history.count("ine-agent mission 1"), 1)

    def test_a_non_done_receipt_records_nothing(self):
        root = self._root()
        task = self._task(root)
        written = record_mission_outcome(
            root, task, self._receipt(status="failed"), "failed")
        self.assertEqual(written, {"plan": False, "history": False,
                                   "state": False, "notes": False})
        self.assertIn("`EXECUTABLE`", read_plan(root).items[0].text)

    def test_notes_is_left_alone_without_a_durable_finding(self):
        root = self._root()
        record_mission_outcome(
            root, self._task(root), self._receipt(), "done")
        self.assertFalse(os.path.exists(
            os.path.join(root, ".agent", "NOTES.md")))

    def test_state_head_is_rewritten_and_the_rest_is_untouched(self):
        root = make_root(
            plan_containing([("EXECUTABLE", "do the thing")]),
            state_text=("Current ground truth as of Session 4\n\n"
                        "## Current focus\n\nold focus line\n\n"
                        "## Health\n\nold health line\n\n"
                        "## Records\n\nkeep this reference exactly\n"),
        )
        record_mission_outcome(root, self._task(root), self._receipt(), "done",
                               session=5)
        state = open(os.path.join(root, ".agent", "STATE.md"),
                     encoding="utf-8").read()
        self.assertIn("keep this reference exactly", state)
        self.assertNotIn("old focus line", state)
        self.assertNotIn("old health line", state)
        self.assertIn("Current ground truth as of Session 5", state)
        self.assertIn("do the thing", state)
        self.assertIn("pytest -q: 12 passed", state)

    def test_a_state_file_without_the_head_sections_is_not_rewritten(self):
        # A repository whose STATE.md the recorder cannot place a position in
        # keeps its file; the rest of the recording still happens.
        root = make_root(plan_containing([("EXECUTABLE", "x")]),
                         state_text="no sections here\n")
        before = open(os.path.join(root, ".agent", "STATE.md"),
                      encoding="utf-8").read()
        written = record_mission_outcome(
            root, self._task(root), self._receipt(), "done")
        self.assertFalse(written["state"])
        self.assertTrue(written["history"])
        self.assertEqual(
            open(os.path.join(root, ".agent", "STATE.md"),
                 encoding="utf-8").read(), before)

    def test_the_session_number_follows_the_history(self):
        root = make_root(
            plan_containing([("EXECUTABLE", "x")]),
            history_text="## Session 41 - a\n\n## Session 44 - b\n",
        )
        self.assertEqual(next_session_number(root), 45)
        record_mission_outcome(root, self._task(root), self._receipt(), "done")
        history = open(os.path.join(root, ".agent", "HISTORY.md"),
                       encoding="utf-8").read()
        self.assertIn("## Session 45 - ine-agent mission 1", history)

    def test_mark_done_is_idempotent_and_preserves_the_item_text(self):
        root = make_root(plan_containing([("EXECUTABLE", "keep this headline")]))
        identity = self._task(root).identity
        self.assertTrue(mark_done(root, identity))
        self.assertIn("keep this headline", read_plan(root).items[0].text)
        first = open(os.path.join(root, ".agent", "PLAN.md"),
                     encoding="utf-8").read()
        self.assertTrue(mark_done(root, identity))
        self.assertEqual(
            open(os.path.join(root, ".agent", "PLAN.md"),
                 encoding="utf-8").read(), first)

    def test_a_receipt_drives_completion_without_a_plan_edit(self):
        # The point of the receipt: a worker that left PLAN.md alone and
        # reported `done` is recorded as having finished the mission.
        root = make_root(plan_containing([("EXECUTABLE", "do the thing")]))
        worker = StubWorker([(0, receipt_text(
            status="done", summary="did it without touching the plan",
            files=["src/x.py"], verification=["pytest -q: 3 passed"]))])
        out = io.StringIO()
        code = Supervisor(root, worker_factory=lambda name: worker,
                          out=out, usage_reporter=ZeroUsage()).run()
        self.assertEqual(code, STOP_OK)
        self.assertIn("`DONE`", read_plan(root).items[0].text)
        report = open(os.path.join(root, ".agent", "RUN_REPORTS.md"),
                      encoding="utf-8").read()
        self.assertIn("- receipt: done", report)
        self.assertIn("- verified: pytest -q: 3 passed", report)
        self.assertIn("ine-agent mission 1", open(
            os.path.join(root, ".agent", "HISTORY.md"),
            encoding="utf-8").read())

    def test_a_failed_cycle_spends_no_second_call_when_the_receipt_says_why(self):
        root = make_root(plan_containing([("EXECUTABLE", "hard one")]))
        worker = StubWorker([(0, receipt_text(
            status="missing_prerequisite", summary="the layer does not "
                                                   "exist yet"))])
        out = io.StringIO()
        code = Supervisor(root, worker_factory=lambda name: worker,
                          out=out, usage_reporter=ZeroUsage()).run()
        # One worker call: the receipt already said why, so the loop never
        # spends a diagnosis request to find out.
        self.assertEqual(len(worker.calls), 1)
        self.assertIn("missing_prerequisite", out.getvalue())
        self.assertIn("the layer does not exist yet", out.getvalue())
        # A wall, not a failure: the existing blocked-mission contract.
        self.assertEqual(code, STOP_OK)
        self.assertEqual(read_plan(root).items[0].tag, "BLOCKED")

    def test_a_cycle_with_no_receipt_still_records_that_it_had_none(self):
        root = make_root(plan_containing([("EXECUTABLE", "quiet worker")]))
        worker = StubWorker([(0, "all done, no receipt printed",
                              plugin_done_text("quiet worker"))])
        Supervisor(root, worker_factory=lambda name: worker, out=io.StringIO(),
                   usage_reporter=ZeroUsage()).run()
        report = open(os.path.join(root, ".agent", "RUN_REPORTS.md"),
                      encoding="utf-8").read()
        self.assertIn("[receipt] none printed by the worker", report)


class ProfileTests(unittest.TestCase):
    """The command shape is data, resolved by name, and checkable in advance.

    The point of a profile is that switching tool is a command-line word
    rather than a Python edit — which is only true if resolution is total,
    reports what it would run, and refuses a broken config loudly instead
    of falling back to the built-in that happens to be handy.
    """

    def _root(self, profiles=None):
        root = make_root(plan_containing([("EXECUTABLE", "x")]))
        if profiles is not None:
            self._write_config(root, profiles)
        return root

    def _write_config(self, root, document):
        path = os.path.join(root, ".agent", "workers.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        return path

    def test_builtin_profiles_resolve_to_the_documented_commands(self):
        root = self._root()
        opencode = profiles.resolve(root, "opencode")
        self.assertEqual(opencode.command, [
            "opencode", "run", "--pure", "--agent", "ine-worker",
            "--dir", root])
        self.assertEqual(opencode.argv("P"), [
            "opencode", "run", "--pure", "--agent", "ine-worker", "--dir",
            root, "P"])
        self.assertEqual(opencode.prompt_transport, "argument")
        claude = profiles.resolve(root, "claude")
        self.assertEqual(claude.command, ["claude", "-p"])
        # The prompt travels on stdin, so it is not an argument.
        self.assertEqual(claude.argv("P"), ["claude", "-p"])
        self.assertEqual(claude.prompt_transport, "stdin")

    def test_root_and_model_are_substituted(self):
        root = self._root({"profiles": {"omni": {
            "command": ["python", "bridge.py", "--dir", "{root}"],
            "prompt_transport": "argument",
            "model_args": ["--model", "{model}"],
        }}})
        resolved = profiles.resolve(root, "omni", model="vendor/big")
        self.assertEqual(resolved.command,
                         ["python", "bridge.py", "--dir", root])
        self.assertEqual(resolved.model_args, ["--model", "vendor/big"])
        self.assertEqual(resolved.model, "")
        self.assertEqual(
            resolved.argv("P"),
            ["python", "bridge.py", "--dir", root, "--model", "vendor/big",
             "P"])

    def test_a_config_adds_and_overrides_built_ins(self):
        root = self._root({"profiles": {
            "claude": {"command": ["claude", "-p", "--verbose"]},
        }})
        # Merged field by field: the override changed the command only.
        claude = profiles.resolve(root, "claude")
        self.assertEqual(claude.command, ["claude", "-p", "--verbose"])
        self.assertEqual(claude.prompt_transport, "stdin")
        self.assertIn("opencode", profiles.available(root))

    def test_an_unknown_profile_names_itself_and_the_alternatives(self):
        root = self._root()
        with self.assertRaises(profiles.ProfileError) as caught:
            profiles.resolve(root, "nope")
        message = str(caught.exception)
        self.assertIn("nope", message)
        self.assertIn("opencode", message)

    def test_a_malformed_field_names_the_profile_and_the_field(self):
        cases = [
            ({"command": []}, "command"),
            ({"command": "opencode run"}, "command"),
            ({"command": ["x"], "prompt_transport": "carrier-pigeon"},
             "prompt_transport"),
            ({"command": ["x", "{modle}"]}, "command"),
            ({"command": ["x", 7]}, "command"),
            ({"command": ["x"], "timeout_seconds": "soon"},
             "timeout_seconds"),
            ({"command": ["x"], "timeout_seconds": -1}, "timeout_seconds"),
            ({"command": ["x"], "env": ["OK_NAME", "value-here"]}, "env"),
            ({"command": ["x"], "env_var": "not a name"}, "env_var"),
        ]
        for fields, expected in cases:
            root = self._root({"profiles": {"bad": dict(fields)}})
            with self.assertRaises(profiles.ProfileError) as caught:
                profiles.resolve(root, "bad", model="m")
            message = str(caught.exception)
            self.assertIn("'bad'", message)
            self.assertIn(expected, message)

    def test_a_model_is_a_refinement_not_a_requirement(self):
        # No model given: the tool's own default is used and the profile's
        # model args are dropped whole, so a clean checkout still resolves.
        root = self._root({"profiles": {"omni": {
            "command": [sys.executable, "bridge.py"],
            "model_args": ["--model", "{model}"]}}})
        resolved = profiles.resolve(root, "omni")
        self.assertEqual(resolved.model_args, [])
        self.assertEqual(resolved.model, "")
        given = profiles.resolve(root, "omni", model="vendor/big")
        self.assertEqual(given.model_args, ["--model", "vendor/big"])

    def test_a_command_that_needs_a_model_says_so_when_none_is_given(self):
        root = self._root({"profiles": {"bad": {
            "command": ["x", "--model={model}"]}}})
        with self.assertRaises(profiles.ProfileError) as caught:
            profiles.resolve(root, "bad")
        message = str(caught.exception)
        self.assertIn("'bad'", message)
        self.assertIn("command", message)
        self.assertIn("--model", message)

    def test_a_missing_command_is_named_too(self):
        root = self._root({"profiles": {"bad": {
            "prompt_transport": "stdin"}}})
        with self.assertRaises(profiles.ProfileError) as caught:
            profiles.resolve(root, "bad")
        self.assertIn("'bad'", str(caught.exception))
        self.assertIn("command", str(caught.exception))

    def test_a_broken_config_is_an_error_not_a_silent_built_in(self):
        # The whole point of a config is that it was read. Falling back to
        # the built-in would run the wrong tool and say nothing.
        root = self._root()
        with open(os.path.join(root, ".agent", "workers.json"), "w",
                  encoding="utf-8") as handle:
            handle.write("{not json")
        with self.assertRaises(profiles.ProfileError):
            profiles.resolve(root, "opencode")
        root = self._root({"profiles": {"x": {"command": ["a"],
                                              "cmd": ["b"]}}})
        with self.assertRaises(profiles.ProfileError) as caught:
            profiles.resolve(root, "x")
        self.assertIn("cmd", str(caught.exception))

    def test_no_profile_field_can_hold_a_credential(self):
        # A profile declares which variable to use, never what is in it: a
        # value pasted into the config must fail by name, not be committed.
        root = self._root({"profiles": {"leaky": {
            "command": ["x"], "env": ["OMNI_API_KEY=secret-value"]}}})
        with self.assertRaises(profiles.ProfileError) as caught:
            profiles.resolve(root, "leaky")
        message = str(caught.exception)
        self.assertIn("'env'", message)
        self.assertIn("OMNI_API_KEY=secret-value", message)
        # Declared properly, the profile holds the name and nothing else.
        root = self._root({"profiles": {"leaky": {
            "command": ["x"], "env": ["OMNI_API_KEY"]}}})
        resolved = profiles.resolve(root, "leaky")
        self.assertEqual(resolved.env, ["OMNI_API_KEY"])
        self.assertNotIn("secret-value", " ".join(resolved.argv()))

    def test_build_worker_runs_the_resolved_command(self):
        root = self._root({"profiles": {"probe": {
            "command": [sys.executable, "-c",
                        "import sys;print(sys.argv[1])"],
            "prompt_transport": "argument"}}})
        worker = build_worker("probe", root=root)
        result = worker.run(root, "hello")
        self.assertTrue(result.ok)
        self.assertIn("hello", result.output)

    def test_a_profile_worker_still_honours_the_env_override(self):
        root = self._root({"profiles": {"probe": {
            "command": ["ignored"], "prompt_transport": "argument"}}})
        script = os.path.join(root, "echo_argv.py")
        with open(script, "w", encoding="utf-8") as handle:
            handle.write("import sys\nprint('|'.join(sys.argv[1:]))\n")
        # A path passed as an argument still has to be quoted by hand: no
        # splitter can tell a spaced path from a name plus arguments.
        override = '"{}" "{}"'.format(sys.executable, script)
        with mock.patch.dict(
                os.environ, {"INE_AGENT_PROBE": override}, clear=False):
            worker = build_worker("probe", root=root)
            result = worker.run(root, "P")
        self.assertTrue(result.ok, result.output)
        self.assertIn("P", result.output)
        self.assertNotIn("ignored", result.output)

    def test_a_profile_timeout_kills_the_child_and_says_so(self):
        root = self._root({"profiles": {"slow": {
            "command": [sys.executable, "-c", "import time;time.sleep(30)"],
            "prompt_transport": "argument", "timeout_seconds": 1}}})
        result = build_worker("slow", root=root).run(root, "P")
        self.assertFalse(result.ok)
        self.assertIn("timeout", result.output)
        self.assertIn("slow", result.output)


class DoctorTests(unittest.TestCase):
    """`doctor` answers "what would run?" without running anything."""

    def _root(self, config=None):
        root = make_root(plan_containing([("EXECUTABLE", "x")]))
        if config is not None:
            path = os.path.join(root, ".agent", "workers.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(config, handle)
        return root

    def test_doctor_reports_the_resolved_command(self):
        root = self._root()
        fake = os.path.join(root, "fake-opencode")
        open(fake, "w").close()
        buffer = io.StringIO()
        with mock.patch.dict(os.environ, {"INE_AGENT_OPENCODE": fake},
                             clear=False):
            code, profile = cli._describe_worker(
                root, "opencode", "", out=buffer)
        text = buffer.getvalue()
        self.assertEqual(code, 0)
        # The override is the executable; the rest of the profile is the
        # command's own shape, and the prompt is not part of it. Paths with
        # a space are quoted so the printed line is copy-pasteable.
        self.assertIn(profiles.display_command(
            [fake, "run", "--pure", "--agent", "ine-worker", "--dir", root]),
            text)
        self.assertIn("the final argument", text)
        self.assertEqual(profile.name, "opencode")

    def test_doctor_substitutes_the_model_it_is_given(self):
        root = self._root({"profiles": {"omni": {
            "command": [sys.executable, "bridge.py"],
            "model_args": ["--model={model}"]}}})
        buffer = io.StringIO()
        code, profile = cli._describe_worker(
            root, "omni", "vendor/big", out=buffer)
        self.assertEqual(code, 0)
        self.assertIn("--model=vendor/big", buffer.getvalue())
        self.assertEqual(profile.model, "vendor/big")
    def test_doctor_fails_with_a_remedy_for_a_missing_tool(self):
        root = self._root({"profiles": {"absent": {
            "command": ["ine-agent-no-such-tool"]}}})
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            code, profile = cli._describe_worker(root, "absent", "")
        self.assertEqual(code, 1)
        self.assertIsNone(profile)
        message = stderr.getvalue()
        self.assertIn("absent", message)
        self.assertIn("INE_AGENT_ABSENT", message)

    def test_doctor_accepts_a_fake_executable_without_running_it(self):
        root = self._root()
        fake = os.path.join(root, "fake-tool")
        with open(fake, "w", encoding="utf-8") as handle:
            handle.write("this would be a real tool\n")
        with open(os.path.join(root, ".agent", "workers.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({"profiles": {"fake": {"command": [fake]}}}, handle)
        buffer = io.StringIO()
        code, _ = cli._describe_worker(root, "fake", "", out=buffer)
        self.assertEqual(code, 0)
        self.assertIn(fake, buffer.getvalue())
        # Resolution found the file; nothing was started, so nothing was
        # written by it.
        self.assertEqual(open(fake, encoding="utf-8").read(),
                         "this would be a real tool\n")

    def test_doctor_warns_about_a_missing_variable_without_reading_it(self):
        root = self._root({"profiles": {"omni": {
            "command": [sys.executable, "bridge.py"],
            "env": ["OMNI_TOKEN_XYZ"]}}})
        buffer = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=True):
            code, _ = cli._describe_worker(root, "omni", "", out=buffer)
        self.assertEqual(code, 0)
        self.assertIn("OMNI_TOKEN_XYZ", buffer.getvalue())

    def test_doctor_says_which_profile_field_is_wrong(self):
        root = self._root({"profiles": {"omni": {
            "command": ["x", "{modle}"]}}})
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            code, _ = cli._describe_worker(root, "omni", "")
        self.assertEqual(code, 1)
        self.assertIn("command", stderr.getvalue())
        self.assertIn("{modle}", stderr.getvalue())

    def test_doctor_says_when_a_command_needs_a_model_and_has_none(self):
        root = self._root({"profiles": {"omni": {
            "command": ["x", "--model={model}"]}}})
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            code, _ = cli._describe_worker(root, "omni", "")
        self.assertEqual(code, 1)
        self.assertIn("--model", stderr.getvalue())


class DryRunReportTests(unittest.TestCase):
    """A dry run prints the whole decision, not just the first task."""

    def _root(self):
        return make_root(plan_containing([
            ("EXECUTABLE", "first thing"),
            ("EXECUTABLE", "second thing"),
            ("DONE", "already done"),
        ]))

    def _out(self, root, worker="opencode"):
        buffer = io.StringIO()
        code = Supervisor(
            root, worker_factory=lambda name: (_ for _ in ()).throw(
                AssertionError("no worker may be built in a dry run")),
            impl_worker=worker, dry_run=True, out=buffer,
            usage_reporter=ZeroUsage()).run()
        return code, buffer.getvalue()

    def test_the_profile_command_and_budget_are_printed(self):
        root = self._root()
        fake = os.path.join(root, "fake-opencode")
        open(fake, "w").close()
        with mock.patch.dict(os.environ, {"INE_AGENT_OPENCODE": fake},
                             clear=False):
            code, out = self._out(root)
        self.assertEqual(code, STOP_OK)
        self.assertIn("profile    : opencode", out)
        self.assertIn(profiles.display_command(
            [fake, "run", "--pure", "--agent", "ine-worker", "--dir", root,
             "<prompt>"]), out)
        self.assertIn("budget     :", out)
        self.assertIn("attempt(s) per mission", out)

    def test_the_queue_after_the_next_mission_is_printed(self):
        root = self._root()
        code, out = self._out(root)
        self.assertIn("PLAN item 1", out)
        self.assertIn("1 further EXECUTABLE item(s)", out)
        self.assertIn("2", out)
        # A DONE item is not work and is not offered.
        self.assertNotIn("already done", out)

    def test_a_dry_run_writes_no_run_report(self):
        root = self._root()
        self._out(root)
        self.assertFalse(os.path.exists(run_report_path(root)))

    def test_an_unresolvable_profile_is_reported_not_raised(self):
        root = self._root()
        code, out = self._out(root, worker="no-such-profile")
        self.assertEqual(code, STOP_ERROR)
        self.assertIn("does not resolve", out)
        self.assertIn("no-such-profile", out)


class WorkerAgentDefinitionTests(unittest.TestCase):
    """The agent definition is the worker's budget, and it is load-bearing.

    OpenCode silently ignores a malformed agent file, so "the worker has no
    step budget and no denials" would look exactly like success from the
    loop's side. These tests read the file that will actually be loaded and
    assert the parts the loop depends on.
    """

    PATH = os.path.join(REPO_ROOT, ".opencode", "agents", "ine-worker.md")
    DENIED = ("webfetch", "websearch", "task", "question", "skill",
              "external_directory", "doom_loop", "todowrite")
    ALLOWED = ("read", "glob", "grep", "list", "edit", "bash")

    def _front_matter(self):
        with open(self.PATH, encoding="utf-8") as handle:
            text = handle.read()
        self.assertTrue(text.startswith("---\n"), "front matter must open")
        end = text.index("\n---\n", 3)
        return text[3:end], text[end + 5:]

    def _yaml(self, block, indent=0):
        """Parse the small YAML subset the file uses, with the stdlib.

        A front-matter block that needs a real YAML parser is a sign it has
        grown beyond what this file should contain.
        """
        values = {}
        for line in block.splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if indent == 0 and not line.startswith(" "):
                key, _, value = line.partition(":")
                values[key.strip()] = value.strip()
        return values

    def test_the_agent_file_is_where_opencode_looks_for_it(self):
        self.assertTrue(os.path.isfile(self.PATH))
        self.assertEqual(os.path.basename(self.PATH), "ine-worker.md")

    def test_the_front_matter_declares_a_bounded_primary_agent(self):
        front, _ = self._front_matter()
        values = self._yaml(front)
        self.assertEqual(values.get("mode"), "primary")
        self.assertIn("description", values)
        self.assertTrue(values.get("description"),
                        "description is required by the OpenCode schema")
        steps = values.get("steps", "")
        self.assertTrue(steps.isdigit(), "steps must be a finite number")
        self.assertGreater(int(steps), 0)
        # A bound nobody bounded is not a bound.
        self.assertLessEqual(int(steps), 200)
        self.assertNotIn("model", values,
                         "the worker profile owns model selection")
        self.assertNotIn("maxSteps", values, "maxSteps is deprecated")

    def test_the_denied_tools_are_named(self):
        front, _ = self._front_matter()
        for tool in self.DENIED:
            self.assertRegex(front, r"(?m)^\s+%s:\s*deny\s*$" % tool)

    def test_the_allowed_tools_are_named(self):
        front, _ = self._front_matter()
        for tool in self.ALLOWED:
            self.assertRegex(front, r"(?m)^\s+%s:\s*allow\s*$" % tool)

    def test_nothing_is_left_to_an_implicit_default(self):
        # Anything not listed is allowed by default, so a tool the loop cares
        # about that is missing from the file is a hole, not a neutral.
        front, _ = self._front_matter()
        listed = set(re.findall(r"(?m)^\s+([a-z_]+):\s*(?:allow|deny)\s*$",
                                front))
        expected = set(self.DENIED) | set(self.ALLOWED)
        self.assertEqual(listed, expected)

    def test_the_body_is_short_and_says_what_the_prompt_says(self):
        _, body = self._front_matter()
        self.assertLessEqual(len(body.strip().splitlines()), 40)
        # Line wrapping is not what is being asserted, so compare on
        # whitespace-normalized text.
        flat = " ".join(body.split())
        for phrase in ("index is the whole scope",
                       "Do not re-plan",
                       "receipt"):
            self.assertIn(phrase, flat)

    def test_the_builtin_profile_selects_this_agent(self):
        command = profiles.resolve(REPO_ROOT, "opencode").command
        index = command.index("--agent")
        self.assertEqual(command[index + 1], "ine-worker")


class CompactionTests(unittest.TestCase):
    """Bounded, selective memory: only what this mission is actually about.

    The loop stopped sending the history, so the one thing it used to get out
    of it — whether the last mission in this area already did this — has to
    come from somewhere bounded. An unfiltered list is the thing being
    replaced, so "nothing related" has to be a real, reachable answer.
    """

    def _root(self):
        return make_root(plan_containing([
            ("EXECUTABLE", "first mission"),
            ("EXECUTABLE", "second mission"),
        ]))

    def _receipt(self, **kwargs):
        defaults = dict(status="done", summary="wired the parser",
                        files=["src/ine_agent/compaction.py"],
                        verification=["pytest -q: 5 passed"], area="parser")
        defaults.update(kwargs)
        return parse_receipt(receipt_text(**defaults))

    def _index(self, root, number, text):
        write_index(root, str(number), text)

    def test_metadata_is_optional_and_defaults_to_empty(self):
        root = self._root()
        self._index(root, 1, "# Mission 1\n\nGoal: do it.\n")
        metadata = read_mission_metadata(root, 1)
        self.assertEqual(metadata["area"], "")
        self.assertEqual(metadata["depends_on"], [])
        self.assertEqual(metadata["files"], [])

    def test_metadata_reads_area_dependencies_and_files(self):
        root = self._root()
        self._index(root, 2, (
            "# Mission 2\n\nArea: ine-agent\nDepends on: 119, 120\n"
            "Goal: do it.\n\n"
            "## Files\n\n"
            "- `src/ine_agent/compaction.py` (new) — the module.\n"
            "- `src/ine_agent/supervisor.py` — the caller.\n"
            "- `tests/test_ine_agent.py` — the tests.\n"
            "\n## Steps\n\n1. Do it.\n"))
        metadata = read_mission_metadata(root, 2)
        self.assertEqual(metadata["area"], "ine-agent")
        self.assertEqual(metadata["depends_on"], [119, 120])
        self.assertEqual(metadata["files"], [
            "src/ine_agent/compaction.py",
            "src/ine_agent/supervisor.py",
            "tests/test_ine_agent.py",
        ])

    def test_a_snippet_holds_the_outcome_and_not_the_prompt(self):
        root = self._root()
        self.assertTrue(compaction.write_snippet(root, 1, self._receipt(
            finding="the front end re-parses on every keystroke",
            follow_up="cache the parse")))
        text = open(compaction.snippet_path(root, 1), encoding="utf-8").read()
        self.assertIn("wired the parser", text)
        self.assertIn("src/ine_agent/compaction.py", text)
        self.assertIn("pytest -q: 5 passed", text)
        self.assertIn("the front end re-parses", text)
        self.assertIn("cache the parse", text)
        # The failure mode this module is guarding against: a snippet that
        # carries the prompt back into the next mission.
        self.assertNotIn("EXECUTION worker", text)
        self.assertNotIn("Carry out the mission below", text)

    def test_a_snippet_is_bounded(self):
        root = self._root()
        compaction.write_snippet(root, 1, self._receipt(
            summary="s" * 9000, finding="f" * 9000))
        size = os.path.getsize(compaction.snippet_path(root, 1))
        self.assertLessEqual(size, compaction.SNIPPET_LIMIT)

    def test_selection_matches_area_dependencies_and_files(self):
        root = self._root()
        compaction.write_snippet(root, 1, self._receipt(area="parser"))
        compaction.write_snippet(root, 2, self._receipt(
            area="editor", files=["editor/vscode-ine/src/extension.ts"]))
        self._index(root, 3, "# Mission 3\n\nArea: PARSER\nGoal: x.\n")
        by_area = compaction.select_snippets(root, 3, area="parser")
        self.assertEqual([e["number"] for e in by_area], [1])
        by_file = compaction.select_snippets(
            root, 3, files=["editor/vscode-ine/src/extension.ts"])
        self.assertEqual([e["number"] for e in by_file], [2])
        by_dep = compaction.select_snippets(root, 3, depends_on=[2])
        self.assertEqual([e["number"] for e in by_dep], [2])
        # Newest first when several match.
        compaction.write_snippet(root, 4, self._receipt(area="parser"))
        self.assertEqual(
            [e["number"] for e in compaction.select_snippets(root, 5,
                                                             area="parser")],
            [4, 1])

    def test_selection_is_empty_without_a_declared_relation(self):
        root = self._root()
        compaction.write_snippet(root, 1, self._receipt(area="parser"))
        self.assertEqual(compaction.select_snippets(root, 2), [])
        self.assertEqual(compaction.select_snippets(root, 2, area="editor"),
                         [])

    def test_a_mission_never_receives_its_own_snippet(self):
        root = self._root()
        compaction.write_snippet(root, 1, self._receipt(area="parser"))
        self.assertEqual(compaction.select_snippets(root, 1, area="parser"),
                         [])

    def test_the_caps_hold(self):
        root = self._root()
        for number in range(1, 12):
            compaction.write_snippet(root, number, self._receipt(
                area="parser", summary="summary number {}".format(number)))
        chosen = compaction.select_snippets(
            root, 99, area="parser", max_snippets=3, limit_chars=200000)
        self.assertEqual(len(chosen), 3)
        self.assertEqual([e["number"] for e in chosen], [11, 10, 9])
        tight = compaction.select_snippets(
            root, 99, area="parser", max_snippets=10, limit_chars=120)
        self.assertLessEqual(len(compaction.render(tight, 120)), 120)
        self.assertLess(len(tight), 10)

    def test_an_unreadable_snippet_is_skipped_not_guessed(self):
        root = self._root()
        compaction.write_snippet(root, 1, self._receipt(area="parser"))
        with open(compaction.snippet_path(root, 2), "w",
                  encoding="utf-8") as handle:
            handle.write("hand-edited nonsense\n")
        self.assertEqual(
            [e["number"] for e in compaction.select_snippets(
                root, 9, area="parser")], [1])

    def test_the_prompt_carries_a_related_snippet_as_data(self):
        root = self._root()
        compaction.write_snippet(root, 1, self._receipt(area="parser"))
        self._index(root, 2, "# Mission 2\n\nArea: parser\nGoal: go on.\n")
        prompt = impl_prompt(root, read_plan(root).items[1])
        self.assertIn("PRIOR WORK IN THIS AREA", prompt)
        self.assertIn("Mission 1", prompt)
        self.assertIn("wired the parser", prompt)
        self.assertIn("a record, not a task", prompt)
        # Before the mission, and clearly subordinate to it.
        self.assertLess(prompt.index("PRIOR WORK IN THIS AREA"),
                        prompt.index("MISSION (PLAN item 2)"))

    def test_the_prompt_says_so_when_there_is_nothing_related(self):
        root = self._root()
        self._index(root, 1, "# Mission 1\n\nGoal: go.\n")
        prompt = impl_prompt(root, read_plan(root).first_executable())
        self.assertIn("no related earlier mission in this area yet", prompt)

    def test_a_recorded_receipt_leaves_a_snippet_behind(self):
        root = self._root()
        worker = StubWorker([
            (0, receipt_text(status="done", summary="did the first",
                             area="parser", files=["src/a.py"])),
        ])
        Supervisor(root, worker_factory=lambda name: worker, out=io.StringIO(),
                   usage_reporter=ZeroUsage()).run()
        self.assertTrue(os.path.exists(compaction.snippet_path(root, 1)))
        self.assertIn("did the first", open(
            compaction.snippet_path(root, 1), encoding="utf-8").read())

    def test_a_blocked_receipt_leaves_a_snippet_too(self):
        # A wall is the thing a later mission in the same area most needs.
        root = make_root(plan_containing([("EXECUTABLE", "hard one")]))
        worker = StubWorker([(0, receipt_text(
            status="missing_prerequisite", summary="the layer is missing",
            area="parser"))])
        Supervisor(root, worker_factory=lambda name: worker, out=io.StringIO(),
                   usage_reporter=ZeroUsage()).run()
        text = open(compaction.snippet_path(root, 1), encoding="utf-8").read()
        self.assertIn("missing_prerequisite", text)
        self.assertIn("the layer is missing", text)


class TempHygieneTests(unittest.TestCase):
    """`.tmp/` is scratch, and a test that leaks scratch is a defect.

    The old cleanup swallowed the Windows failure on git's read-only object
    files, so a partially deleted `ineagent-*` (containing nothing but
    `.git`) survived every run, and one test never registered its directory
    at all. Both are pinned here.
    """

    def test_a_created_directory_is_registered_for_cleanup(self):
        folder = make_tmp_dir("ineagent-hygiene-")
        self.assertIn(folder, _CREATED_ROOTS)
        self.assertTrue(os.path.isdir(folder))

    def test_removal_clears_a_read_only_file(self):
        folder = make_tmp_dir("ineagent-hygiene-")
        target = os.path.join(folder, "obj")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("x")
        os.chmod(target, stat.S_IREAD)
        _remove_root(folder)
        self.assertFalse(os.path.exists(folder))

    def test_cleanup_removes_every_registered_root(self):
        folder = make_tmp_dir("ineicon-hygiene-")
        _clean_temp_roots()
        self.assertFalse(os.path.exists(folder))
        self.assertEqual(_leftover_fixture_dirs(), [])


if __name__ == "__main__":
    unittest.main()