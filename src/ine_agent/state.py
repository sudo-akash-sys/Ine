"""Project-state reader and recorder for ine-agent.

Reads the persistent `.agent/` control-plane files and answers, in a
simple deterministic way, the one question the selection rule needs: does
executable work exist, and what is the first EXECUTABLE task?

The selection rule itself lives in `.agent/PLAN.md` (the menu); this
module only applies it. It never infers state — everything it reports is
read from disk on every cycle.

Since Session 41 the supervisor also RECORDS on this module's behalf
(per the commander's blocker discipline): appending remarks to PLAN items
without rewriting their original text, tagging a deferred mission BLOCKED,
recording commander resolutions as new remarks, appending blockers without
touching existing entries, and appending to the durable per-run report
`.agent/RUN_REPORTS.md`. Every write is append-only with respect to the
original records.
"""

import os
import re
import time

AGENT_DIR = ".agent"
PLAN_NAME = "PLAN.md"
STATE_NAME = "STATE.md"
HISTORY_NAME = "HISTORY.md"
BLOCKERS_NAME = "BLOCKERS.md"
REPORT_NAME = "RUN_REPORTS.md"
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
        self.tag = tag          # EXECUTABLE | BLOCKED | CLAUDE_REVIEW | DONE | None
        self.text = text.strip()
        self.raw = raw

    @property
    def executable(self):
        # PLAN.md rule: an item is executable unless it is tagged BLOCKED
        # or DONE; unmarked items stay executable. Excluding DONE keeps a
        # finished task from being re-picked on the next cycle.
        return self.tag not in ("BLOCKED", "DONE")

    @property
    def wants_claude_review(self):
        return self.tag == "CLAUDE_REVIEW"

    @property
    def identity(self):
        # The headword line, normalized, is the stable key used to detect
        # whether a worker cycle actually advanced the plan.
        return headline_key(self.text)


def headline_key(text):
    """A stable, tag-agnostic key for a mission's first line.

    The leading `TAG` token is stripped so a mission re-tagged by a worker
    (EXECUTABLE -> DONE/BLOCKED) still matches its pre-cycle snapshot.
    """
    lines = text.splitlines()
    first = lines[0] if lines else ""
    first = re.sub(r"^`[A-Z][A-Z0-9_]*`\s*", "", first)
    return re.sub(r"\s+", " ", first).strip().lower()


class Plan:
    """A parsed snapshot of .agent/PLAN.md taken on one read."""

    def __init__(self, path, items):
        self.path = path
        self.items = items

    def first_executable(self, skip=()):
        """First executable item, in list order, excluding `skip` identities.

        `skip` is the supervisor's per-run deferral set: a mission deferred
        once (blocked / failed / awaiting commander input) is passed over so
        independent executable work continues. The plan file's rule is
        unchanged — this just lets one run avoid immediately re-picking the
        mission it just deferred.
        """
        skip = set(skip) if skip else set()
        for item in self.items:
            if item.executable and item.identity not in skip:
                return item
        return None

    def has_executable(self, skip=()):
        return self.first_executable(skip) is not None

    def item(self, identity=None, number=None):
        """Look up an item by identity (tag-agnostic) or plan number."""
        for item in self.items:
            if number is not None and str(item.number) == str(number):
                return item
            if identity is not None and item.identity == identity:
                return item
        return None


_TAG_RE = re.compile(r"`([A-Z][A-Z0-9_]*)`")
_ITEM_RE = re.compile(r"^\s*(\d+)\.\s+")
_MARKER_LINE_RE = re.compile(r"^\s*" + re.escape(HUMAN_MARKER) + r"\b")


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


def _set_tag(line, number, tag):
    """Rewrite the leading tag token of an item line to `tag`.

    Returns the rewritten line, or None when the line is not the requested
    item. The rest of the line (headline, body) is never edited.
    """
    match = _ITEM_RE.match(line)
    if not match or match.group(1) != str(number):
        return None
    body = line[match.end():]
    tag_match = _TAG_RE.search(body)
    if tag_match:
        new_body = (body[:tag_match.start()] + "`" + tag + "`"
                    + body[tag_match.end():])
    else:
        new_body = "`" + tag + "` " + body
    return line[:match.end()] + new_body


def _rewrite_plan(root, number, expected_key, add_remark=None, tag=None):
    """Append a remark (and optionally set the tag) after an item's line.

    The original item line and text are preserved untouched — only a
    continuation remark line is inserted and/or the leading tag token is
    rewritten. Returns True when the item was found and edited.
    """
    path = os.path.join(root, AGENT_DIR, PLAN_NAME)
    try:
        lines = _read_text(path).splitlines()
    except OSError:
        return False
    out = []
    inserted = False
    for line in lines:
        out.append(line)
        match = _ITEM_RE.match(line)
        if not inserted and match and match.group(1) == str(number):
            body = line[match.end():]
            if headline_key(body) == expected_key:
                if tag is not None:
                    rewrite = _set_tag(line, number, tag)
                    if rewrite is not None:
                        out[-1] = rewrite
                if add_remark is not None:
                    out.append(add_remark)
                inserted = True
    if inserted:
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("\n".join(out) + "\n")
        except OSError:
            return False
    return inserted


def append_item_remark(root, identity, remark_text):
    """Append a `> remark:` continuation line under a mission.

    Preserves the original mission text and tag; the remark becomes part of
    the item's parsed text so workers can see prior run history.
    """
    plan = read_plan(root)
    item = plan.item(identity=identity)
    if item is None:
        return False
    return _rewrite_plan(root, item.number, headline_key(item.text),
                         add_remark=("> remark: {}".format(remark_text)))


def mark_blocked(root, identity, reason):
    """Tag a mission BLOCKED (original text preserved) with a remark.

    Returns True on success. A mission already BLOCKED or DONE is left
    tagged as-is but still gets the remark recording why.
    """
    plan = read_plan(root)
    item = plan.item(identity=identity)
    if item is None:
        return False
    tag = item.tag
    new_tag = tag if tag in ("BLOCKED", "DONE") else "BLOCKED"
    return _rewrite_plan(root, item.number, headline_key(item.text),
                         add_remark=("> remark: blocked — {}".format(reason)),
                         tag=new_tag)


def record_resolution(root, identity, resolution, source="commander"):
    """Record a commander resolution as a NEW remark under a mission.

    The original blocker text and tag are never rewritten: a resolution is
    an additional remark/decision, not an edit of history.
    """
    plan = read_plan(root)
    item = plan.item(identity=identity)
    if item is None:
        return False
    return _rewrite_plan(
        root, item.number, headline_key(item.text),
        add_remark=("> resolution ({}): {}".format(source, resolution)))


def append_blocker(root, number, headline, detail):
    """Record a newly-blocked mission in BLOCKERS.md without touching
    existing entries. Appends under a 'Blocked during autonomous runs'
    section (created once if absent)."""
    path = os.path.join(root, AGENT_DIR, BLOCKERS_NAME)
    text = _read_optional_text(root, BLOCKERS_NAME)
    if "## Blocked during autonomous runs" not in text:
        text = (text.rstrip("\n") + "\n\n"
                "## Blocked during autonomous runs\n\n") if text.strip() else (
                "# .agent/BLOCKERS.md\n\n"
                "## Blocked during autonomous runs\n\n")
    text += ("- **PLAN item {}: {}.** {}\n".format(number, headline, detail))
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    except OSError:
        return False
    return True


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


def output_marks_human_decision(text):
    """True when a worker transcript carries the stop marker on its own line.

    Same line-based convention as the .agent/ file check above: the marker
    is a stop signal only when it starts a line. A plain substring scan is
    NOT used, because the phrase also appears inside the workers' own
    instructions and in ordinary prose ("this task did not require
    HUMAN_DECISION_REQUIRED") — a substring scan there halted the loop on a
    mission that had already been completed (see Session 38).
    """
    for line in text.splitlines():
        if _MARKER_LINE_RE.match(line):
            return True
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


# --------------------------------------------------------------------------
# Durable per-run report (source of truth for the commander).
# --------------------------------------------------------------------------

def run_report_path(root):
    """Absolute path of the durable per-run report for `root`."""
    return os.path.join(os.path.abspath(root), AGENT_DIR, REPORT_NAME)


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _append_report(root, lines):
    path = run_report_path(root)
    try:
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            for line in lines:
                handle.write(line + "\n")
    except OSError:
        # The report is durable-but-not-critical; a write failure must never
        # stop the loop.
        pass


def begin_run_report(root, command_line):
    """Open a new `### run ...` section with a header on first use."""
    path = run_report_path(root)
    if not os.path.isfile(path):
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("# .agent/RUN_REPORTS.md\n\n"
                             "Durable per-run log written by ine-agent. The "
                             "commander's notifications point here;\n"
                             "STATE.md / HISTORY.md / PLAN.md remain the "
                             "long-term intelligence.\n")
        except OSError:
            pass
    _append_report(root, [
        "",
        "### run {} (pid {})".format(_now(), os.getpid()),
        "- command: {}".format(command_line),
    ])


def append_run_report(root, lines):
    _append_report(root, list(lines))


def end_run_report(root, exit_code, summary):
    _append_report(root, [
        "- exit: {}".format(exit_code),
        "- summary: {}".format(summary),
        "",
    ])