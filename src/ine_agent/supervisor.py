"""The ine-agent supervisor loop.

A dumb coordinator. It reads `.agent/` on every cycle, applies the PLAN
selection rule deterministically, runs exactly one worker per cycle
(sequentially — never concurrent), and stops on the defined conditions:

- no executable work        -> normal stop (exit 0)
- HUMAN_DECISION_REQUIRED   -> commander-judgment gate (exit 2)
- worker cannot advance     -> bounded-stop after `max_attempts` (exit 1)
- cycle-limit reached       -> hard bound (exit 1)

The supervisor loads MISSION_PROMPT.md and MISSION.md once per cycle and
embeds them in the worker prompt, so the worker never needs to read them
from disk. It never writes `.agent/` files, never infers state, never
unblocks evidence-gated work, and never invents semantics.
"""

import os
import sys

from . import state
from .worker import WorkerResult, build_worker

STOP_OK = 0
STOP_ERROR = 1
STOP_HUMAN = 2


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


def impl_prompt(root, task):
    """The prompt handed to the implementation worker (OpenCode by default).

    The autonomous mission preamble (MISSION_PROMPT.md) and project
    context (MISSION.md) are embedded at the top so the worker never
    needs to read them from disk. The remaining .agent/ files are still
    read by the worker on each cycle.
    """
    return (
        _mission_block(root)
        + "You are the autonomous implementation worker for the Ine repository.\n"
        "\n"
        "1. Read AGENTS.md in full, then .agent/STATE.md, .agent/PLAN.md,\n"
        "   .agent/DECISIONS.md, .agent/BLOCKERS.md, and .agent/HISTORY.md.\n"
        "   (MISSION.md and MISSION_PROMPT.md are already provided above.)\n"
        "2. Follow the autonomous task-selection rule in .agent/PLAN.md:\n"
        "   take the first EXECUTABLE task, in list order.\n"
        "3. Implement the current first EXECUTABLE task:\n"
        "\n"
        "   {task}\n"
        "\n"
        "4. Run focused tests, review your changes, run broader regression\n"
        "   when appropriate, and update .agent/STATE.md and\n"
        "   .agent/HISTORY.md per the AGENTS.md workflow.\n"
        "5. Continue to the next safe EXECUTABLE task; stop when none\n"
        "   remain.\n"
        "\n"
        "Guardrails (never violated): do not invent language semantics, do\n"
        "not unblock evidence-gated work, do not modify DECISIONS.md, do\n"
        "not change parser/semantic/backend behavior except when the task\n"
        "explicitly requires it, and keep temporary artifacts under .tmp/.\n"
        "If the task genuinely requires commander judgment, print\n"
        "HUMAN_DECISION_REQUIRED and stop. If you completely finish every\n"
        "executable task, stop quietly.\n"
    ).format(task=task.raw.strip())


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
                 max_cycles=20, max_attempts=2, dry_run=False, out=None):
        self.root = root
        self.worker_factory = worker_factory or build_worker
        self.impl_worker = impl_worker
        self.max_cycles = max_cycles
        self.max_attempts = max_attempts
        self.dry_run = dry_run
        self.out = out if out is not None else sys.stdout

    def _print(self, message):
        print(message, file=self.out)

    def _worker(self, name):
        return self.worker_factory(name)

    def _no_work(self):
        self._print("No executable work remains.")
        self._print("ine-agent stopped normally.")

    def _human_stop(self, task=None):
        self._print("HUMAN_DECISION_REQUIRED")
        self._print(
            "ine-agent stopped: commander judgment is required"
            + (" for: " + task.text.splitlines()[0] if task else "") + "."
        )

    def _run_task(self, task):
        """Run optional review (CLAUDE_REVIEW tag) then the implementation
        worker, sequentially. Never concurrent."""
        if task.wants_claude_review:
            review = self._worker("claude").run(self.root, review_prompt(self.root, task))
            if state.HUMAN_MARKER in review.output:
                return review
        return self._worker(self.impl_worker).run(
            self.root, impl_prompt(self.root, task)
        )

    def run(self):
        plan = state.read_plan(self.root)
        task = plan.first_executable()
        self._print("project: {}".format(self.root))
        if state.human_decision_indicated(self.root):
            self._human_stop()
            return STOP_HUMAN
        if task is None:
            self._no_work()
            return STOP_OK

        attempts = 0
        cycles = 0
        while True:
            if task is None:
                self._no_work()
                return STOP_OK
            if state.human_decision_indicated(self.root):
                self._human_stop(task)
                return STOP_HUMAN
            if cycles >= self.max_cycles:
                self._print(
                    "Reached the maximum of {} worker cycle(s); execution stopped."
                    .format(self.max_cycles)
                )
                return STOP_ERROR
            if attempts >= self.max_attempts:
                self._print(
                    "Worker could not advance the plan after {} attempt(s); "
                    "execution stopped.".format(self.max_attempts)
                )
                return STOP_ERROR

            headline = task.text.splitlines()[0]
            if self.dry_run:
                self._print("[dry-run] worker '{}' would run for: {}".format(
                    self.impl_worker, headline))
                return STOP_OK

            worker_name = self.impl_worker if not task.wants_claude_review else "claude+opencode"
            self._print("[cycle {}] worker '{}' <- {}".format(cycles + 1, worker_name, headline))
            result = self._run_task(task)
            self._print("[cycle {}] exit code {}".format(cycles + 1, result.exit_code))
            if result.exit_code != 0 and result.output:
                self._print("[cycle {}] worker output (first 20 lines):".format(cycles + 1))
                for line in result.output.splitlines()[:20]:
                    self._print("  " + line)

            cycles += 1
            plan = state.read_plan(self.root)
            if state.HUMAN_MARKER in result.output or state.human_decision_indicated(self.root):
                self._human_stop(task)
                return STOP_HUMAN

            next_task = plan.first_executable()
            if next_task is not None:
                if next_task.identity == task.identity:
                    attempts += 1
                else:
                    attempts = 0
            task = next_task