"""Project-state reader for ine-agent.

Reads the persistent `.agent/` control-plane files and answers, in a
simple deterministic way, the one question the selection rule needs: does
executable work exist, and what is the first EXECUTABLE task?

The selection rule itself lives in `.agent/PLAN.md` (the menu); this
module only applies it. It never writes `.agent/` files and it never
infers state — everything it reports is read from disk on every cycle.
"""

import os
import re

AGENT_DIR = ".agent"
PLAN_NAME = "PLAN.md"
STATE_NAME = "STATE.md"
HISTORY_NAME = "HISTORY.md"
BLOCKERS_NAME = "BLOCKERS.md"
MISSION_PROMPT_NAME = "MISSION_PROMPT.md"
MISSION_NAME = "MISSION.md"
HUMAN_MARKER = "HUMAN_DECISION_REQUIRED"


class ProjectError(Exception):
    """Raised when a usable Ine project root cannot be established."""


class Task:
    """One item under the 'Active' section of PLAN.md."""

    __slots__ = ("number", "tag", "text", "raw")

    def __init__(self, number, tag, text, raw):
        self.number = number
        self.tag = tag          # EXECUTABLE | BLOCKED | CLAUDE_REVIEW | None
        self.text = text.strip()
        self.raw = raw

    @property
    def executable(self):
        # PLAN.md rule: an item is executable unless it is tagged BLOCKED.
        return self.tag != "BLOCKED"

    @property
    def wants_claude_review(self):
        return self.tag == "CLAUDE_REVIEW"

    @property
    def identity(self):
        # The headword line, normalized, is the stable key used to detect
        # whether a worker cycle actually advanced the plan.
        head = self.text.splitlines()[0] if self.text else ""
        return re.sub(r"\s+", " ", head.strip()).lower()


class Plan:
    """A parsed snapshot of .agent/PLAN.md taken on one read."""

    def __init__(self, path, items):
        self.path = path
        self.items = items

    def first_executable(self):
        for item in self.items:
            if item.executable:
                return item
        return None

    def has_executable(self):
        return self.first_executable() is not None


_TAG_RE = re.compile(r"`([A-Z][A-Z0-9_]*)`")
_ITEM_RE = re.compile(r"^\s*(\d+)\.\s+")


def _read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _read_optional_text(root, filename):
    """Read a file under .agent/ if it exists, or return empty string."""
    path = os.path.join(root, AGENT_DIR, filename)
    try:
        return _read_text(path)
    except OSError:
        return ""


def read_plan(root):
    """Parse the 'Active' section of .agent/PLAN.md into Task items."""
    path = os.path.join(root, AGENT_DIR, PLAN_NAME)
    lines = _read_text(path).splitlines()
    in_active = False
    section = []
    for line in lines:
        if line.startswith("## "):
            in_active = line[3:].strip().lower().startswith("active")
            continue
        if in_active:
            section.append(line)
    items = []
    current = None
    for line in section:
        match = _ITEM_RE.match(line)
        if match:
            if current is not None:
                items.append(current)
            body = line[match.end():]
            tag_match = _TAG_RE.search(body)
            current = Task(
                number=match.group(1),
                tag=tag_match.group(1) if tag_match else None,
                text=body,
                raw=line,
            )
        elif current is not None:
            current.text += "\n" + line
            current.raw += "\n" + line
    if current is not None:
        items.append(current)
    return Plan(path, items)


_MARKER_LINE_RE = re.compile(r"^\s*" + re.escape(HUMAN_MARKER) + r"\b")


def human_decision_indicated(root):
    """True when .agent/ state plainly signals commander judgment is needed.

    The project convention is the literal marker HUMAN_DECISION_REQUIRED,
    written by a worker on its OWN line in STATE/BLOCKERS (or reported on
    worker output — handled separately). The check is line-based so that
    prose *documenting* the marker (e.g. this repo's own state notes) never
    trips the gate.
    """
    for name in (STATE_NAME, BLOCKERS_NAME):
        path = os.path.join(root, AGENT_DIR, name)
        try:
            for line in _read_text(path).splitlines():
                if _MARKER_LINE_RE.match(line):
                    return True
        except OSError:
            continue
    return False


def find_project_root(start=None):
    """Walk up from `start` to a directory holding .agent/PLAN.md + STATE.md."""
    start = os.path.abspath(start or os.getcwd())
    current = start
    while True:
        agent = os.path.join(current, AGENT_DIR)
        if (
            os.path.isdir(agent)
            and os.path.isfile(os.path.join(agent, PLAN_NAME))
            and os.path.isfile(os.path.join(agent, STATE_NAME))
        ):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            raise ProjectError(
                "not inside the Ine repository: no .agent/PLAN.md and "
                ".agent/STATE.md found above {}".format(start)
            )
        current = parent