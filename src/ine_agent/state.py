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

It also reads the per-mission EXECUTION INDEXES under
`.agent/missions/<item-number>.md` — the planner's concrete step list for
one plan item. The supervisor refuses to launch a worker for a mission
with no index, so `read_mission_index` returning None is a decision, not a
missing-file incident.
"""

import os
import re
import time

from . import receipt as receipt_format

AGENT_DIR = ".agent"
PLAN_NAME = "PLAN.md"
STATE_NAME = "STATE.md"
HISTORY_NAME = "HISTORY.md"
NOTES_NAME = "NOTES.md"
BLOCKERS_NAME = "BLOCKERS.md"
REPORT_NAME = "RUN_REPORTS.md"
MISSION_PROMPT_NAME = "MISSION_PROMPT.md"
WORKER_PROMPT_NAME = "WORKER_PROMPT.md"
MISSION_NAME = "MISSION.md"
MISSION_DIR = "missions"
HUMAN_MARKER = "HUMAN_DECISION_REQUIRED"

#: Appended to every plan item `propose_follow_up` writes. It is the marker
#: the plan is parsed by, not decoration: an item carrying it is never
#: executable, so a worker can file a suggestion without being able to turn
#: it into work the loop performs.
PROPOSAL_MARKER = "(proposed by a worker"

#: Words that carry no identity, so "finish the thing" and "`EXECUTABLE` —
#: **finish the thing.**" compare equal. Kept short on purpose: a proposal
#: that merely sounds like its mission is dropped, and a false drop costs a
#: line in the run report rather than work.
PROPOSAL_STOPWORDS = frozenset((
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "is", "it", "its", "of", "on", "or", "that", "the", "then", "this",
    "to", "with",
))


def content_words(text):
    """The identity-bearing words of `text`, lowercased and unordered.

    The comparison key for "is this proposal the same work as that mission?":
    it ignores the PLAN tag, the bold markers and the function words, so two
    phrasings of one job produce the same key.
    """
    return frozenset(
        word for word in re.findall(r"[a-z0-9]+", (text or "").lower())
        if word not in PROPOSAL_STOPWORDS)


class ProjectError(Exception):
    """Raised when a usable Ine project root cannot be established."""


_BOLD_ITEM_RE = re.compile(r"\*\*(.+?)\*\*")


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
        # finished task from being re-picked on the next cycle. A proposal
        # (see `propose_follow_up`) is excluded whatever its tag, because a
        # worker's suggestion is not an instruction to the loop.
        if self.proposed:
            return False
        return self.tag not in ("BLOCKED", "DONE")

    @property
    def proposed(self):
        """True when this item was filed by `propose_follow_up`."""
        return PROPOSAL_MARKER in self.text

    @property
    def proposed_text(self):
        """The proposal itself, or None when this item is not a proposal.

        Read back out of the bolded span `propose_follow_up` writes, so a
        later run can recognise its own earlier proposal without depending on
        the wording of the surrounding annotation.
        """
        if not self.proposed:
            return None
        match = _BOLD_ITEM_RE.search(self.text)
        return match.group(1) if match else None

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


def _append_file(root, filename, lines):
    """Append `lines` to a file under .agent/, creating it if absent.

    The generic form of `_append_report`, for the records the receipt
    recorder writes. Append-only by construction, and a write failure is
    swallowed: a record that could not be saved must never fail a mission
    whose work is already done.
    """
    path = os.path.join(root, AGENT_DIR, filename)
    try:
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            for line in lines:
                handle.write(line + "\n")
    except OSError:
        return False
    return True


def mission_index_relpath(number):
    """The index path as a message should name it: repo-relative, `/`-joined.

    Messages are written with forward slashes on every platform so the same
    record reads the same everywhere (the rest of the .agent/ records name
    paths that way too).
    """
    return "{}/{}/{}.md".format(AGENT_DIR, MISSION_DIR, number)


def mission_index_path(root, number):
    """Absolute path of the execution index for PLAN item `number`.

    The index is keyed on the item NUMBER, which PLAN.md already carries
    and `_ITEM_RE` already parses, so there is no new plan syntax and no
    separate pointer that could drift out of step with the plan. A plan
    item is renumbered only when the plan itself is rewritten, and the
    index travels with it.
    """
    return os.path.join(
        os.path.abspath(root), AGENT_DIR, MISSION_DIR, "{}.md".format(number))


def read_mission_index(root, number):
    """The execution index a planner wrote for PLAN item `number`.

    Returns the index text, or None when no index exists — or when the
    file exists but is empty. None is a first-class answer: it is what
    makes the planner write the steps BEFORE a worker is launched, instead
    of the worker inventing them at execution time.
    """
    try:
        with open(mission_index_path(root, number), "r",
                  encoding="utf-8") as handle:
            text = handle.read().strip()
    except OSError:
        return None
    return text or None


def write_mission_index(root, number, text):
    """Write the execution index for PLAN item `number`. Returns True on
    success. Creates `.agent/missions/` on first use."""
    path = mission_index_path(root, number)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text.rstrip("\n") + "\n")
    except OSError:
        return False
    return True


_AREA_RE = re.compile(r"^Area:[ \t]*(.+?)[ \t]*$", re.M)
_DEPS_RE = re.compile(r"^Depends on:[ \t]*(.+?)[ \t]*$", re.M)
_FILES_HEADING_RE = re.compile(r"^##[ \t]+Files[ \t]*$", re.M)
_FRONTSECTION_END_RE = re.compile(r"^##[ \t]", re.M)
_BACKTICK_RE = re.compile(r"`([^`\n]+)`")


def _looks_like_path(token):
    """Whether a backticked token in a Files list names a file.

    `src/ine_agent/state.py` and `state.py` do; `new`, `(optional)` and a
    bare `EXECUTABLE` do not. A slash or a dot is the discriminator, which
    keeps the metadata optional and free of a new convention to get wrong.
    """
    if " " in token or "\t" in token:
        return False
    if token.isupper():
        return False
    return "/" in token or "." in token


def read_mission_metadata(root, number):
    """`{area, depends_on, files}` for one execution index, or None.

    All three are OPTIONAL. An index that does not declare them loads with
    empty values, so the hundreds of existing indexes keep working and a
    planner is never blocked from writing a mission for want of metadata.
    The values are how a mission says which earlier work is relevant to it —
    the only basis on which a compact snippet is offered rather than sent.
    """
    text = read_mission_index(root, number)
    if text is None:
        return None
    front_end = _FRONTSECTION_END_RE.search(text)
    front = text[:front_end.start()] if front_end else text
    area_match = _AREA_RE.search(front)
    deps_match = _DEPS_RE.search(front)
    depends_on = []
    if deps_match:
        depends_on = [int(n) for n in re.findall(r"\d+", deps_match.group(1))]
    files = []
    files_heading = _FILES_HEADING_RE.search(text)
    if files_heading:
        tail = text[files_heading.end():]
        next_heading = _FRONTSECTION_END_RE.search(tail)
        section = tail[:next_heading.start()] if next_heading else tail
        files = [token for token in _BACKTICK_RE.findall(section)
                 if _looks_like_path(token)]
    return {
        "area": area_match.group(1).strip() if area_match else "",
        "depends_on": depends_on,
        "files": files,
    }


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


def propose_follow_up(root, proposal, origin=None):
    """Append a PROPOSED next mission to the plan as a `CLAUDE_REVIEW` item.

    A worker's follow-up is a suggestion, and it is filed as one: the tag is
    `CLAUDE_REVIEW`, which the selection rule never treats as executable, so
    the proposal cannot be picked up by this run or any later one until a
    human reads it and re-tags it. A worker therefore cannot create
    executable work by writing one — the strongest form of the rule, because
    it is enforced by the plan's own parsing rather than by trusting the
    worker's intent.

    Returns the new item's number, or None when the proposal is empty or the
    plan already proposes the identical text.
    """
    text = " ".join(str(proposal or "").split())
    if not text:
        return None
    plan = read_plan(root)
    key = content_words(text)
    for item in plan.items:
        if item.proposed and content_words(item.proposed_text or "") == key:
            return None
    numbers = [int(item.number) for item in plan.items
               if str(item.number).isdigit()]
    number = (max(numbers) + 1) if numbers else 1
    line = "{}. `CLAUDE_REVIEW` — **{}.** {}not executable until a human " \
           "reads it{}\n".format(
               number, text, PROPOSAL_MARKER,
               " (after mission {})".format(origin) if origin else "")
    with open(os.path.join(root, AGENT_DIR, PLAN_NAME), "a",
              encoding="utf-8") as handle:
        handle.write("\n" + line)
    return number


def mark_done(root, identity):
    """Tag a mission DONE, preserving its original text.

    The completion counterpart of `mark_blocked`, and idempotent: a mission
    the worker already tagged itself is left exactly as it is. Returns True
    when the mission exists and carries the DONE tag afterwards.
    """
    plan = read_plan(root)
    item = plan.item(identity=identity)
    if item is None:
        return False
    if item.tag == "DONE":
        return True
    return _rewrite_plan(root, item.number, headline_key(item.text),
                         tag="DONE")


# --------------------------------------------------------------------------
# Deterministic recording from a worker receipt.
#
# The worker states four things (status, summary, files, verification) in one
# machine-readable block, and this module turns that into the durable records.
# It is the reason a worker no longer spends a mission's worth of tokens
# rewriting PLAN, HISTORY, STATE and NOTES by hand — and the reason those
# records are written the same way whether the worker was thorough or terse.
# --------------------------------------------------------------------------

_SESSION_HEADING_RE = re.compile(r"^#{2,3} Session (\d+)")
_STATE_SESSION_RE = re.compile(r"(Current ground truth as of Session )(\d+)")


def latest_session(root):
    """The highest session number HISTORY.md already carries, or 0."""
    latest = 0
    for line in _read_optional_text(root, HISTORY_NAME).splitlines():
        match = _SESSION_HEADING_RE.match(line)
        if match:
            latest = max(latest, int(match.group(1)))
    return latest


def next_session_number(root):
    """The session number one recorded mission would carry.

    Derived from HISTORY.md rather than a counter in this module, so the
    history stays the single source of truth for how far the project has got
    and a restored or hand-edited log cannot desynchronise the two.
    """
    return latest_session(root) + 1


def _one_line(text, limit=200):
    return " ".join(str(text or "").split())[:limit]


def _history_heading(session, number, headline):
    return "## Session {} - ine-agent mission {}: {}".format(
        session, number, _one_line(headline, 90))


def _history_has_mission(root, session, number):
    """Whether this run's block for this mission is already in HISTORY.md.

    The heading carries both the session and the mission number, so a repeat
    of the same recording is recognised and skipped rather than duplicated.
    """
    pattern = re.compile(
        r"^## Session {} - ine-agent mission {}\b".format(
            int(session), int(number)))
    return any(pattern.match(line)
               for line in _read_optional_text(root, HISTORY_NAME).splitlines())


def _notes_has_mission(root, number):
    pattern = re.compile(r"^## Mission {}\b".format(int(number)))
    return any(pattern.match(line)
               for line in _read_optional_text(root, NOTES_NAME).splitlines())


def _append_history(root, session, number, task, receipt):
    """Append one mission's block to HISTORY.md (append-only)."""
    headline = task.text.splitlines()[0] if task.text else "mission"
    lines = [
        "",
        _history_heading(session, number, headline),
        "",
        "- outcome: {}".format(receipt.status),
        "- summary: {}".format(_one_line(receipt.summary, 600)),
        "- files: {}".format(
            ", ".join(receipt.changed_files) or "(none reported)"),
    ]
    for entry in receipt.verification:
        lines.append("- verified: {}".format(_one_line(entry, 200)))
    if receipt.area:
        lines.append("- area: {}".format(_one_line(receipt.area, 80)))
    if receipt.finding:
        lines.append("- finding: {}".format(_one_line(receipt.finding, 600)))
    if receipt.follow_up:
        lines.append(
            "- follow-up proposed (recorded, not executed): {}".format(
                _one_line(receipt.follow_up, 400)))
    lines.append("- recorded by: state.record_mission_outcome from the "
                 "worker receipt")
    _append_file(root, HISTORY_NAME, lines)
    return True


def _append_note(root, number, receipt):
    """Append this mission's durable finding to NOTES.md, once."""
    if _notes_has_mission(root, number):
        return False
    if not _read_optional_text(root, NOTES_NAME).strip():
        _append_file(root, NOTES_NAME, ["# .agent/NOTES.md", ""])
    _append_file(root, NOTES_NAME, [
        "## Mission {}".format(number),
        "",
        "Area: {}".format(receipt.area or "(not stated)"),
        "",
        receipt.finding,
        "",
    ])
    return True


def _replace_section(text, name, body):
    """The file with one `## name` section's body replaced, or None.

    Only the named section's lines are touched: STATE.md carries durable
    reference sections the recorder has no opinion about, and a mission must
    never be able to delete them by reporting.
    """
    lines = text.splitlines()
    start = None
    for position, line in enumerate(lines):
        if line.startswith("## ") and line[3:].strip().lower() == name:
            start = position
            break
    if start is None:
        return None
    end = len(lines)
    for position in range(start + 1, len(lines)):
        if lines[position].startswith("## "):
            end = position
            break
    return "\n".join(lines[:start + 1] + ["", body.rstrip(), ""] + lines[end:])


def _next_headline(root):
    plan = read_plan(root)
    item = plan.first_executable()
    if item is None:
        return "none — nothing is EXECUTABLE in PLAN.md"
    return "{} (item {})".format(_one_line(item.text.splitlines()[0], 90),
                                 item.number)


def _rewrite_state_head(root, session, number, task, receipt):
    """Rewrite STATE.md's head sections to where the project stands NOW.

    Bounded on purpose: the position summary and the health note are replaced
    whole, and everything below them — the reference sections and the
    session preamble — is left exactly as it was.
    """
    text = _read_optional_text(root, STATE_NAME)
    if not text:
        return False
    headline = task.text.splitlines()[0] if task.text else "mission"
    verified = receipt.verification or ["(the worker reported none)"]
    focus = "\n".join([
        "- Session {} recorded mission {} (`{}`) as {}: {}".format(
            session, number, _one_line(headline, 80), receipt.status,
            _one_line(receipt.summary, 400)),
        "- Next executable work: {}.".format(_next_headline(root)),
        "- This file is position-only: the per-mission detail is the receipt "
        "in `.agent/RUN_REPORTS.md`, the block in `.agent/HISTORY.md`, and "
        "the index at `{}`.".format(mission_index_relpath(number)),
    ])
    health = "\n".join([
        "- Recording is deterministic: PLAN tags, this head, HISTORY and "
        "NOTES are written by `state.record_mission_outcome` from the worker's "
        "structured receipt, not by the model in prose.",
        "- Last recorded verification for mission {}: {}".format(
            number, _one_line(verified[0], 200)),
        "- Known caveats and the rest of the project's position are in the "
        "sections below and are not rewritten by a mission.",
    ])
    updated = _replace_section(text, "current focus", focus)
    if updated is None:
        return False
    updated = _replace_section(updated, "health", health)
    if updated is None:
        return False
    updated = _STATE_SESSION_RE.sub(
        r"\g<1>" + str(session) + r"\g<2>", updated, count=1)
    try:
        with open(os.path.join(root, AGENT_DIR, STATE_NAME), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write(updated.rstrip("\n") + "\n")
    except OSError:
        return False
    return True


def record_mission_outcome(root, task, receipt, status, session=None):
    """Record one mission attempt from its receipt, deterministically.

    Writes exactly what the receipt states: the plan tag for a completed
    mission, one HISTORY block, the bounded head of STATE.md, and a NOTES
    section only when the receipt carries a durable finding. A receipt that
    reports anything other than completion is recorded by the caller through
    the blocked / failure paths instead, which already carry the reason.

    Returns what was written. Never raises: a mission that finished must not
    be reported as failed because a record could not be saved.
    """
    number = getattr(task, "number", None)
    identity = getattr(task, "identity", None)
    written = {"plan": False, "history": False, "state": False, "notes": False}
    if number is None or receipt is None:
        return written
    if status != receipt_format.DONE:
        return written
    if identity:
        written["plan"] = mark_done(root, identity)
    if session is None:
        session = next_session_number(root)
    if not _history_has_mission(root, session, number):
        written["history"] = _append_history(root, session, number, task,
                                             receipt)
    if receipt.finding:
        written["notes"] = _append_note(root, number, receipt)
    written["state"] = _rewrite_state_head(root, session, number, task,
                                           receipt)
    return written


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