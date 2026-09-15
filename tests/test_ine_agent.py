"""Focused tests for the ine-agent supervisor.

These tests never launch a real AI agent: the worker boundary is replaced
with a scripted stub, and CLI-level tests run with --dry-run or against
plan fixtures with no executable work.
"""

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ine_agent import cli
from ine_agent.state import (
    ProjectError, find_project_root, human_decision_indicated, read_plan,
)
from ine_agent.supervisor import (
    STOP_ERROR, STOP_HUMAN, STOP_OK, Supervisor, _mission_block,
)
from ine_agent.worker import StubWorker

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(REPO_ROOT, ".tmp")


def make_root(plan, state_text="state", history_text="history",
              blockers_text="blockers", mission_prompt_text=None,
              mission_text=None):
    os.makedirs(TMP, exist_ok=True)
    root = tempfile.mkdtemp(prefix="ineagent-", dir=TMP)
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


class TrackingStub(StubWorker):
    def __init__(self, steps):
        super().__init__(steps)
        self.depth = 0
        self.overlaps = 0

    def run(self, root, prompt):
        self.depth += 1
        if self.depth > 1:
            self.overlaps += 1
        try:
            return super().run(root, prompt)
        finally:
            self.depth -= 1


class StateReadingTests(unittest.TestCase):
    def test_plan_parses_tags_and_executability(self):
        plan = plan_containing([
            ("BLOCKED", "first enumerated choice value (no evidence)"),
            ("EXECUTABLE", "property-value completion"),
            ("CLAUDE_REVIEW", "design review of a risky rewrite"),
            (None, "unmarked item is executable"),
        ])
        parsed = read_plan(make_root(plan)).items
        self.assertEqual(len(parsed), 4)
        self.assertEqual(parsed[0].tag, "BLOCKED")
        self.assertFalse(parsed[0].executable)
        self.assertTrue(parsed[1].executable)
        self.assertTrue(parsed[2].wants_claude_review)
        self.assertTrue(parsed[3].executable)
        self.assertIn("property-value completion", parsed[1].text)

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

    def test_worker_failure_does_not_retry_forever(self):
        root = make_root(plan_containing([("EXECUTABLE", "always fails")]))
        worker = StubWorker([(1, "boom")] * 10)
        code, out, calls, _ = self._run(root, worker=worker, max_attempts=2)
        self.assertEqual(code, STOP_ERROR)
        self.assertEqual(len(calls), 2)
        self.assertIn("could not advance", out)
        self.assertNotIn("No executable work remains.", out)

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

    def test_cli_rejects_a_missing_project_root(self):
        missing = os.path.join(TMP, "no-such-project")
        self.assertEqual(cli.main(["run", "--root", missing]), 1)

    def test_supervisor_rejects_an_unknown_worker_name(self):
        root = make_root(plan_containing([("EXECUTABLE", "x")]))
        from ine_agent.worker import build_worker
        with self.assertRaises(ValueError):
            Supervisor(
                root,
                worker_factory=build_worker,
                impl_worker="not-a-worker",
            )._worker("not-a-worker")


if __name__ == "__main__":
    unittest.main()