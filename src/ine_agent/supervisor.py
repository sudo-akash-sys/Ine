"""The ine-agent supervisor loop.

A dumb coordinator. It reads `.agent/` on every cycle, applies the PLAN
selection rule deterministically, runs exactly one worker per cycle
(sequentially — never concurrent), and stops on the defined conditions:

- no executable work        -> normal stop (exit 0)
- HUMAN_DECISION_REQUIRED   -> commander-judgment flag (exit 2)
- work deferred, none left  -> exit 1 (nothing could be finished)
- cycle-limit reached       -> hard bound (exit 1)

Since Session 41 the loop is also a RECORDING loop (commander directive):
a mission that becomes blocked, fails, or requires commander judgment is
recorded durably (PLAN remark / BLOCKERS entry / run report — original
text preserved), deferred for the rest of the run, and the loop continues
with the next independent executable task instead of halting.

Since the Phase 1 diagnostic work a cycle that stops WITHOUT completing
is also DIAGNOSED, so "skip it and move on" is an informed decision
rather than a blind one. The worker is asked to end every cycle with a
`CLASSIFICATION:` line (needs_commander / missing_prerequisite /
transient / agent_error) plus a one-line reason; when a cycle produced
none — typically a crash — the supervisor spends one short tool-free
follow-up call asking why. The classification then picks the response:

- needs_commander      -> BLOCKERS entry, deferred, run ends pending (2)
- missing_prerequisite -> BLOCKED + reason recorded, deferred, continue
- transient/agent_error-> retried, with the reason attached to the prompt,
                          bounded by `max_attempts`, then deferred
- unclassifiable       -> deferred with the diagnosis recorded

Since the Phase 2 work the vocabulary is a SCHEMA (`Classification`), and
every answer the supervisor reads is normalised onto it before it can reach
a report or a decision: a value is folded onto its class only by an exact
canonical match or by whole-token alias ("transient_error", "agent-error",
"missing prereq"), never by a substring that happens to appear. Anything
else is recorded verbatim and read as `unknown` — never upgraded to a class
the loop would act on, because acting on a guess is the token burn this
path exists to stop. How each class was obtained (verbatim, by alias, from
the follow-up call, or not at all) is part of the durable run report, since
a class that cost a second request or a synonym fold is weaker evidence
than one the worker printed itself.

`max_attempts` therefore no longer stops the run: exhausting it defers
that ONE mission so independent work still proceeds. Termination stays
guaranteed (a deferred mission is never re-picked this run, and
`max_cycles` is a hard bound). Every
mission and run end also fires an optional Windows notification (a
task-started banner, an outcome banner per mission, and a run-complete /
decision / usage event), each pointing at the durable run report
(.agent/RUN_REPORTS.md); notifications are best-effort, streamed to one
headline line, and never stop or delay execution.

Since the Phase 3 work the deferral also SURVIVES THE RUN. A run-local
deferral set dies with the process, so the next run used to start blind
and re-select the mission that had just failed — measurably the loop's
worst behaviour (thirteen consecutive runs re-picking one mission, hours
of provider requests, nothing finished). Every non-completing cycle now
records itself in a durable ledger (`.agent/attempts.json`, keyed on the
mission's identity), and a mission that has failed in `max_failures`
different RUNS is PARKED: not re-picked, reported with its last reason,
and escalated to the commander rather than retried forever. Runs, not
attempts, decide parking — several failures inside one run are what
`max_attempts` already governs. A mission that completes clears its own
entry, and rewriting the mission's headline creates a new identity with a
fresh budget — so the ledger never becomes a wall the commander has to
edit JSON to climb over.

A cycle that neither completes nor blocks anything and leaves no file
changed outside `.agent/` is no progress, and `stall_limit` of those in a
row ends the run early with that stated, instead of grinding through the
cycle budget. `.agent/` is excluded from that evidence on purpose: the
supervisor writes failure remarks and the ledger there itself, so counting
them would report progress for exactly the spinning the guard is for.
Where git cannot answer (no repository, no git) the signature is unknown
and the guard stays silent — silence is never read as a stall.

The supervisor loads MISSION_PROMPT.md and MISSION.md once per cycle and
embeds them in the worker prompt, so the worker never needs to read them
from disk. It never unblocks evidence-gated work and never invents
semantics.
"""

import collections
import datetime
import enum
import json
import os
import re
import subprocess
import sys
import time

from . import compaction
from . import profiles
from . import receipt as receipt_format
from . import state, usage
from .notifier import create_notifier
from .worker import WorkerResult, build_worker, effective_command

STOP_OK = 0
STOP_ERROR = 1
STOP_HUMAN = 2


# CSI sequences (colors, cursor moves) are stripped from the default live
# relay so a cp1252 Windows console never receives raw control sequences.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _strip_ansi(text):
    return _ANSI_RE.sub("", text)


# --- failure classification: the schema -------------------------------------
#
# One schema, five classes, and every parser pathway normalises onto it.
# `Classification` is the schema; `.value` is the wire form that reaches
# reports, PLAN remarks, BLOCKERS entries, notification bodies and the
# prompts themselves — which are built FROM this schema, so the worker's
# instructions and the parser that reads its answer cannot drift apart.
#
# Deliberately a plain `enum.Enum` over string values rather than a str-mixin:
# the declared floor is Python 3.10, where `str()`/`format()` on a mixin
# member still prints `Classification.TRANSIENT`. Nothing formats a member
# into text; every text surface goes through `canonical()` or `.value`.
class Classification(enum.Enum):
    """The closed vocabulary of failure classes."""

    NEEDS_COMMANDER = "needs_commander"
    MISSING_PREREQUISITE = "missing_prerequisite"
    TRANSIENT = "transient"
    AGENT_ERROR = "agent_error"
    UNKNOWN = "unknown"

    @classmethod
    def of(cls, value, default=None):
        """The member equal to `value` — a member, or its string form."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            text = value.strip().lower()
            for member in cls:
                if member.value == text:
                    return member
        return default


class Match(enum.Enum):
    """How a CLASSIFICATION line was read — the audit-trail axis."""

    EXACT = "exact"        # the canonical value, verbatim
    ALIAS = "alias"        # a synonym or misspelling folded onto one
    EXPLICIT = "explicit"  # the worker said, plainly, that it cannot say
    NONE = "none"          # off-vocabulary text: recorded as UNKNOWN
    ABSENT = "absent"      # no CLASSIFICATION line at all


class Source(enum.Enum):
    """Where one cycle's classification came from."""

    WORKER = "worker-output"  # the cycle's own CLASSIFICATION line
    RECEIPT = "receipt"       # the structured receipt's status field
    IN_BAND = "in-band"       # nothing usable in-band: recorded as unknown
    FOLLOW_UP = "follow-up"   # a follow-up call: no longer made by the loop
    GATE = "gate"             # a human-decision marker: no call spent
    ERROR = "error"           # a call could not run


# One cycle's classification plus how it was obtained. `classification` is a
# canonical value string, or None when nothing was printed at all; `reason`
# is the bounded one-line explanation; `raw` is the CLASSIFICATION text
# exactly as written; `match` and `source` are the audit trail saying whether
# the recorded class is the worker's own answer and whether it was read
# verbatim.
Diagnosis = collections.namedtuple(
    "Diagnosis", "classification reason raw match source")

# The schema's public projection: the four classes a worker may choose, plus
# the value that stands in for "could not be read".
CLASSIFICATIONS = tuple(c.value for c in Classification
                        if c is not Classification.UNKNOWN)
RETRYABLE = (Classification.TRANSIENT.value, Classification.AGENT_ERROR.value)
UNCLASSIFIED = Classification.UNKNOWN.value
_VOCABULARY = " | ".join(CLASSIFICATIONS)
_REASON_LIMIT = 200
_REASON_LINES = 4

# What the audit trail calls out. An on-vocabulary class read verbatim out of
# the cycle's own output is the happy path and says nothing extra; everything
# else is drift, fallback or failure — each of which means the recorded class
# may not be the worker's own answer, which the commander reading the run
# report needs to know before trusting it.
_WARNING_MATCHES = (Match.NONE,)
_NOTE_MATCHES = (Match.ALIAS,)
_WARNING_SOURCES = (Source.FOLLOW_UP, Source.ERROR)


def canonical(classification, default=UNCLASSIFIED):
    """`classification` as a canonical value string.

    The single coercion the rest of this module applies, so a class arriving
    from anywhere — a worker, a follow-up call, a caller, a test — reaches a
    report, a remark or a decision already normalised to the schema.
    """
    member = Classification.of(classification)
    return member.value if member is not None else default


def _tokens(text):
    return tuple(re.findall(r"[a-z0-9]+", text.lower()))


def _token_matches(alias_token, token):
    """Same token, or one is an abbreviation of the other.

    Abbreviation tolerance only from four characters up: "prereq" counts for
    "prerequisite" and "trans" for "transient", while "err" for "error" is
    treated as noise rather than folded onto a class.
    """
    if alias_token == token:
        return True
    shorter, longer = sorted((alias_token, token), key=len)
    return len(shorter) >= 4 and longer.startswith(shorter)


def _covers(alias, tokens):
    """Whether every token of `alias` is present in `tokens`."""
    return all(any(_token_matches(alias_token, token) for token in tokens)
               for alias_token in alias)


# What a worker may print instead of a canonical value. Matched by TOKEN, not
# by substring: "transient_error" folds onto `transient`, while "server
# error" stays out of `agent_error` because an alias only counts when every
# one of its own tokens is present. Where two aliases both fit, the longer
# (more specific) one wins.
_ALIASES = (
    (Classification.NEEDS_COMMANDER, (
        "needs commander", "needs commander decision", "commander decision",
        "commander decision required", "commander", "commander approval",
        "requires commander", "human decision", "human decision required",
        "needs human decision", "decision required", "needs approval",
        "approval required", "product decision", "syntax decision",
        "semantic decision", "design decision", "needs sign off")),
    (Classification.MISSING_PREREQUISITE, (
        "missing prerequisite", "prerequisite missing", "missing dependency",
        "dependency missing", "missing feature", "cannot be built yet",
        "not implemented yet", "not built yet", "blocked", "blocked on",
        "waiting on", "missing evidence")),
    (Classification.TRANSIENT, (
        "transient", "transient error", "transient failure", "temporary",
        "temporary failure", "flaky", "retryable", "network error",
        "connection error", "connection refused", "timeout", "timed out",
        "rate limit", "rate limited", "server error", "service unavailable",
        "external failure", "tooling failure", "infrastructure failure")),
    (Classification.AGENT_ERROR, (
        "agent error", "agent mistake", "my mistake", "model error",
        "misread the mission", "misunderstood the mission", "lost the thread",
        "implementation error", "broke the test", "incorrect change")),
)

_ALIAS_INDEX = tuple(
    (member, _tokens(alias))
    for member, aliases in _ALIASES
    for alias in aliases
)

# Spelled-out ways of saying "I cannot classify this". Read as UNKNOWN
# cleanly, because the worker was explicit — that is an answer, not drift.
# The canonical value itself ("unknown") is deliberately NOT here: it is in
# the vocabulary, so it is read verbatim as EXACT by the same path that
# reads the other four.
_EXPLICIT_UNKNOWN = frozenset((
    "none", "n/a", "na", "nil", "unclear", "unclassified", "undetermined",
    "indeterminate", "unsure", "not applicable", "cannot classify",
    "no classification", "?",
))

# A label that denies its own tokens ("not a commander issue") must never be
# folded onto the class it names, and neither must a hedge ("maybe
# transient?"): both name a class while declining to commit to it, and
# committing on the worker's behalf is how a guess becomes a spent retry. A
# phrase that owns the word is unaffected — "not implemented yet" is a
# `missing_prerequisite` label, and the guard is applied per alias below so
# it can tell the two apart.
_NEGATIONS = frozenset((
    "not", "no", "non", "never", "neither", "nor", "without", "cannot",
    "cant", "isnt", "dont", "unable"))
_HEDGES = frozenset((
    "maybe", "perhaps", "possibly", "probably", "might", "could", "seems",
    "seem", "appears", "unclear", "unsure", "guess"))

_LABEL_TRIM = "*`'\"#>[]() \t"
_PLACEHOLDER_CHARS = "<>|"

# The block a worker is asked to end on: `CLASSIFICATION:` / `REASON:`, each
# anchored at line start — leading blanks, a list bullet or markdown emphasis
# may precede the tag — so prose that merely mentions the word never
# classifies a cycle, and case-insensitive so a worker restating the marker
# in lower case is still read.
_TAG_PREFIX = r"^[ \t]*(?:[-*>][ \t]+)?(?:\*\*)?[`'\"]*"
_CLASSIFICATION_RE = re.compile(
    _TAG_PREFIX + r"CLASSIFICATION[`'\"]*(?:\*\*)?[ \t]*[:=][ \t]*([^\n]*)",
    re.MULTILINE | re.IGNORECASE)
_REASON_RE = re.compile(
    _TAG_PREFIX + r"REASON[`'\"]*(?:\*\*)?[ \t]*[:=][ \t]*",
    re.MULTILINE | re.IGNORECASE)
_TAG_LINE_RE = re.compile(
    _TAG_PREFIX + r"(?:CLASSIFICATION|REASON)[`'\"]*(?:\*\*)?[ \t]*[:=]",
    re.IGNORECASE)


def _same_work_as(task, text):
    """True when a proposed follow-up just restates the mission it came from.

    Compared on the words a headline is made of (`state.content_words`), so a
    proposal that would add nothing to the plan is not filed as one. Used only
    to avoid writing a line of noise; a false drop is visible in the run
    report, and a false file is a proposal a human can ignore.
    """
    mission = state.content_words(task.text)
    proposal = state.content_words(text)
    return bool(mission) and bool(proposal) and proposal <= mission


def _truncate_text(text, limit=_REASON_LIMIT):
    """One whitespace-collapsed line, bounded — reasons flow into PLAN
    remarks, BLOCKERS entries and notification bodies, none of which want
    a paragraph."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _match_label(raw):
    """`(member or None, Match)` for the text after a CLASSIFICATION tag.

    Normalisation runs in one direction here: a label becomes a schema member
    or it becomes nothing. It is never "close enough" to a class the loop
    would then act on, because acting on a guess is what spends the tokens
    this path exists to save.
    """
    text = " ".join((raw or "").split()).strip(_LABEL_TRIM)
    if not text:
        return None, Match.NONE
    if any(char in text for char in _PLACEHOLDER_CHARS):
        # The prompt's own "<a | b | c>" menu, echoed back instead of chosen
        # from. Picking one of the listed words would be reading the prompt,
        # not the worker.
        return None, Match.NONE
    if text.strip(" .,;:!?").lower() in _EXPLICIT_UNKNOWN or \
            text.lower() in _EXPLICIT_UNKNOWN:
        # Checked before the canonical values so "none"/"?" read as an
        # explicit refusal rather than as drift; "unknown" is itself
        # canonical and is read verbatim by the test below.
        return Classification.UNKNOWN, Match.EXPLICIT
    tokens = _tokens(text)
    if not tokens:
        return None, Match.NONE
    member = Classification.of("_".join(tokens))
    if member is not None:
        return member, Match.EXACT
    best = None
    for alias_member, alias in _ALIAS_INDEX:
        if not _covers(alias, tokens):
            continue
        # A negation or hedge that the matched phrase does not contain itself
        # refuses the fold: "not a commander issue" must never become
        # `needs_commander`, while "not implemented yet" is exactly the
        # phrase it says it is — the guard is about tokens the alias does
        # not own.
        if any(token in _NEGATIONS or token in _HEDGES
               for token in tokens if token not in alias):
            continue
        if best is None or len(alias) > len(best[1]):
            best = (alias_member, alias)
    if best is None:
        return None, Match.NONE
    return best[0], Match.ALIAS


def _last_reason(text):
    """The reason text following the LAST `REASON:` marker.

    Multi-line by design: a worker that wraps its explanation onto the next
    line, or indents a continuation, is saying one thing, so following
    non-blank lines are joined until a blank line or another tag — bounded by
    `_REASON_LIMIT` at the end, never mid-collection.
    """
    matches = list(_REASON_RE.finditer(text))
    if not matches:
        return ""
    lines = []
    for raw in text[matches[-1].end():].splitlines():
        line = raw.strip()
        if not line:
            if lines:
                break        # a blank line ends the reason...
            continue         # ...but not before it has started
        if _TAG_LINE_RE.match(raw):
            break
        lines.append(line)
        if len(lines) >= _REASON_LINES:
            break
    return _truncate_text(" ".join(lines))


def diagnose_output(text):
    """The `Diagnosis` for one cycle's output.

    `classification` is None only when the cycle printed no CLASSIFICATION
    line at all — the one case that justifies the follow-up call. A line that
    is present but unreadable is reported as `UNKNOWN` with `Match.NONE`, so
    the off-vocabulary text is recorded verbatim WITHOUT spending a second
    request on a worker that already answered badly once.
    """
    if not text:
        return Diagnosis(None, "", "", Match.ABSENT, Source.WORKER)
    matches = list(_CLASSIFICATION_RE.finditer(text))
    if not matches:
        return Diagnosis(None, "", "", Match.ABSENT, Source.WORKER)
    raw = matches[-1].group(1).strip()
    reason = _last_reason(text)
    member, how = _match_label(raw)
    if member is None:
        # Off-vocabulary: recorded as written, read as UNKNOWN, and never
        # upgraded to a class the loop would act on. UNKNOWN is the safe
        # default here rather than AGENT_ERROR, which is unconditionally
        # retryable — retrying on gibberish is precisely the token burn this
        # phase exists to stop. UNKNOWN still defers a crash and still allows
        # the bounded retry after a clean no-progress exit, so nothing the
        # earlier missions pinned is lost.
        return Diagnosis(UNCLASSIFIED, reason or _truncate_text(raw),
                         _truncate_text(raw), Match.NONE, Source.WORKER)
    return Diagnosis(member.value, reason, _truncate_text(raw), how,
                     Source.WORKER)


def parse_classification(text):
    """`(classification, reason)` from a cycle's output.

    The two-value view of `diagnose_output`, kept because that is how callers
    and tests read it. Returns `(None, None)` when the cycle printed no
    CLASSIFICATION line at all — the caller then falls back to asking the
    worker directly. An unrecognised value is reported as `UNCLASSIFIED` with
    the raw value as the reason, so an off-vocabulary answer is still
    recorded verbatim instead of being silently discarded.

    The LAST marker wins: the prompt asks for the block as the final two
    lines, so a worker that quoted or echoed the instruction before
    answering must be read by its answer, not by the quotation.
    """
    diagnosis = diagnose_output(text)
    if diagnosis.classification is None:
        return None, None
    return diagnosis.classification, diagnosis.reason


def diagnosis_trace(cycles, diagnosis):
    """`[(level, message)]` — how one cycle's classification was obtained.

    Empty on the happy path. Anything else is drift, fallback or failure, and
    the level says which the commander should care about: a warning means the
    loop could not read the worker's own answer (or had to spend an extra
    call to get one), a note means it read it by synonym rather than verbatim.
    """
    trace = []
    if diagnosis.match in _WARNING_MATCHES:
        trace.append((
            "warning",
            "unrecognised classification '{}' — recorded as '{}'".format(
                diagnosis.raw or "(empty)", diagnosis.classification)))
    elif diagnosis.match in _NOTE_MATCHES:
        trace.append((
            "note",
            "off-vocabulary classification '{}' matched '{}' by alias".format(
                diagnosis.raw, diagnosis.classification)))
    if diagnosis.source is Source.FOLLOW_UP:
        trace.append((
            "warning",
            "the cycle printed no CLASSIFICATION line; the class came from a "
            "follow-up diagnosis call"))
    elif diagnosis.source is Source.ERROR:
        trace.append((
            "warning",
            "the diagnosis call could not run ({}); recorded as '{}'".format(
                diagnosis.reason, diagnosis.classification)))
    return trace


def retryable(classification, outcome):
    """Whether a bounded retry could plausibly clear this classification.

    `transient` and `agent_error` say so explicitly. An unclassifiable
    cycle is judged by how it ended, which preserves two earlier
    decisions that silence alone cannot overrule:

    - a worker that exited 0 without advancing the plan (stuck) gets the
      bounded retry it always got — a mission that hiccupped once must not
      be skipped for the rest of the run on no evidence; and
    - a worker that crashed (failed) is deferred rather than retried, as
      since Session 41 — re-running a crash that nobody could explain is
      re-burning the same tokens against the same wall.
    """
    classification = canonical(classification)
    if classification in RETRYABLE:
        return True
    return classification == UNCLASSIFIED and outcome == "stuck"


def classify_action(classification, outcome, attempts, max_attempts):
    """What the loop does about one cycle that stopped without completing.

    `attempts` is the number of non-progress cycles already spent on this
    mission, so the cycle just finished is attempt `attempts + 1`; that
    keeps `max_attempts` meaning what it always meant — the total number of
    cycles one mission gets before it is deferred.

    'retry'    one more attempt, with the reason attached to the prompt
    'human'    needs commander judgment: blocker + defer, run ends pending
    'blocked'  cannot be built yet: BLOCKED with the reason, defer, continue
    'deferred' unclassifiable or out of retries: record the reason, defer

    Only a classification that says the mission should be SKIPPED is acted
    on immediately; everything else spends the retry budget first, so a
    hard mission costs at most `max_attempts` cycles before the run moves
    on to independent work.
    """
    classification = canonical(classification)
    if classification == Classification.NEEDS_COMMANDER.value:
        return "human"
    if classification == Classification.MISSING_PREREQUISITE.value:
        return "blocked"
    if retryable(classification, outcome) and attempts + 1 < max_attempts:
        return "retry"
    return "deferred"


def retry_block(classification, reason):
    """The note appended to a retried mission's prompt.

    A retry that repeats the previous attempt verbatim is just a re-burn of
    the same tokens, so the failure is placed at the end of the prompt
    (where it is read last) with an explicit instruction not to repeat the
    approach that already failed.
    """
    lead = ("A previous attempt at this exact mission did not complete "
            "({}). What stopped it, in that attempt's own words:\n\n"
            "  {}\n\n"
            "Do not simply repeat the approach that failed. If the reason "
            "above is still true, say so in your CLASSIFICATION line and "
            "stop — the orchestrator will record it and move on rather than "
            "spend another attempt.").format(
                canonical(classification), reason or "(no reason given)")
    return "\n\nFAILED PREVIOUS ATTEMPT:\n\n" + lead + "\n"


# --- cross-run attempt ledger -------------------------------------------
#
# The deferral Phase 1 added is per RUN: it lives in one process's memory, so
# the next run cannot know that this mission has already failed three times.
# That is the loop's most expensive behaviour on record — thirteen
# consecutive runs re-selecting one mission, hours of provider requests, no
# mission finished. This file is the durable half: one entry per mission
# identity, updated on every cycle that does not complete, cleared when the
# mission completes.

ATTEMPTS_NAME = "attempts.json"
DEFAULT_MAX_FAILURES = 3
DEFAULT_STALL_LIMIT = 3


def attempts_path(root):
    """Where the cross-run attempt ledger lives (`.agent/attempts.json`)."""
    return os.path.join(root, state.AGENT_DIR, ATTEMPTS_NAME)


def read_attempts(root):
    """The recorded failure history, keyed on mission identity.

    A missing, unreadable or malformed ledger reads as "no history" rather
    than raising: losing this file must cost the loop its memory, never its
    ability to run.
    """
    try:
        with open(attempts_path(root), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    missions = data.get("missions") if isinstance(data, dict) else None
    if not isinstance(missions, dict):
        return {}
    return {key: value for key, value in missions.items()
            if isinstance(value, dict)}


def write_attempts(root, missions):
    """Persist the ledger. Best effort: an unwritable file is not fatal."""
    path = attempts_path(root)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({"missions": missions}, handle, indent=2,
                      sort_keys=True)
            handle.write("\n")
    except OSError:
        return False
    return True


def record_failure(root, identity, classification, reason, outcome,
                   run_id=None):
    """Add one non-completing attempt to `identity`; returns the entry.

    `run_id` identifies the run making the call, and it is what keeps the
    two failure budgets separate: several failures in the SAME run are one
    failed run (that is `max_attempts`' business), while a failure in a
    later run raises `runs` — the count parking is decided on. Omit it and
    every call counts as its own run.
    """
    missions = read_attempts(root)
    entry = dict(missions.get(identity) or {})
    entry["attempts"] = int(entry.get("attempts") or 0) + 1
    same_run = run_id is not None and entry.get("run") == run_id
    entry["runs"] = int(entry.get("runs") or 0) + (0 if same_run else 1)
    if run_id is not None:
        entry["run"] = run_id
    entry["classification"] = canonical(classification)
    entry["reason"] = _truncate_text(reason or "(no reason given)")
    entry["outcome"] = outcome
    entry["updated"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    missions[identity] = entry
    write_attempts(root, missions)
    return entry


def clear_mission_attempts(root, identity):
    """Forget a mission's failures — called when the mission completes."""
    missions = read_attempts(root)
    if identity not in missions:
        return False
    del missions[identity]
    write_attempts(root, missions)
    return True


def prune_attempts(root, identities):
    """Drop entries for missions that are no longer executable.

    The ledger exists to remember missions still IN the loop. A mission that
    was rewritten (new identity), removed, completed or blocked leaves an
    entry nothing can be selected for, and a lingering one is not harmless:
    it would be reported as parked in every later run, and once no executable
    work was left it would turn an honest "no work remains" (exit 0) into a
    false "everything is parked" (exit 1). Returns how many were dropped.
    """
    missions = read_attempts(root)
    keep = set(identities)
    stale = [key for key in missions if key not in keep]
    if not stale:
        return 0
    for key in stale:
        del missions[key]
    write_attempts(root, missions)
    return len(stale)


def parked_missions(root, limit):
    """Missions that failed in `limit` or more runs, with their entries."""
    if not limit:
        return {}
    return {identity: entry for identity, entry in read_attempts(root).items()
            if int(entry.get("runs") or 0) >= limit}


_RUN_SEQ = 0


def _new_run_id():
    """A run label that differs between runs, including in one process."""
    global _RUN_SEQ
    _RUN_SEQ += 1
    return "{}-{}".format(
        datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), _RUN_SEQ)


def worktree_signature(root):
    """A fingerprint of uncommitted work outside `.agent/`, or None.

    `git status --porcelain` is the cheapest honest evidence that a cycle
    produced something: text a worker printed cannot move it, an edited file
    can. The `.agent/` records are excluded on purpose — the supervisor
    itself rewrites them on every non-completing cycle (the failure remark in
    PLAN.md, the attempt ledger, this run's report), so counting them would
    report "progress" for exactly the spinning this guard exists to catch.
    None (git missing, `root` not a repository, a timeout) means "unknown" —
    the loop then falls back to the plan as its only progress signal and
    never invents either progress or a stall from silence.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    prefix = state.AGENT_DIR + "/"
    kept = []
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        # Porcelain v1: two status letters, a space, then the path.
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if path.startswith(prefix) or path == state.AGENT_DIR:
            continue
        kept.append(line.strip())
    return "\n".join(kept)


def _planner_block(root):
    """Load MISSION_PROMPT.md and MISSION.md — the PLANNER's preamble.

    The counterpart to the execution contract: MISSION_PROMPT.md tells a
    planner to work out how a mission should be done and to write the
    resulting index. The design-review step (`review_prompt`) is planning, so
    it gets this one; the execution worker gets the index and the small
    contract below instead, and pays for neither of these documents.
    """
    mission_prompt = state._read_optional_text(
        root, state.MISSION_PROMPT_NAME).strip()
    mission = state._read_optional_text(
        root, state.MISSION_NAME).strip()
    block = ""
    if mission_prompt:
        block += (
            "MISSION (follow this as your planning rules):\n\n"
            + mission_prompt + "\n\n"
        )
    if mission:
        block += "PROJECT CONTEXT:\n\n" + mission + "\n\n"
    return block


def impl_prompt(root, task):
    """The prompt handed to the implementation worker (OpenCode by default).

    A fixed contract and the mission's own execution index, and nothing else.
    The control-plane documents the loop used to embed here — WORKER_PROMPT,
    MISSION, the distilled STATE snapshot, the plan body, the history and the
    usage totals — are deliberately NOT sent:

    - they were re-sent in full on every cycle, so their cost was paid once
      per mission for context the index already states;
    - the state snapshot went stale between the read and the worker's first
      step, and a stale position is worse than none;
    - and the worker could read any of them itself, for the one it actually
      needed, at the point it needed it.

    What remains is the mission (written once by the planner), the rules for
    carrying it out, the receipt the recorder parses, and — only when an
    earlier mission actually worked on the same thing — that mission's
    compact receipt.
    """
    index = state.read_mission_index(root, task.number)
    if index is None:
        index = (
            "(None — there is no index at `{}`. The supervisor refuses to run "
            "a mission without one; if you are reading this, report "
            "`needs_commander` in your receipt and stop.)"
            .format(state.mission_index_relpath(task.number))
        )
    related = compaction.render(compaction.select_snippets(
        root, task.number, **_related_signals(root, task.number)))
    related = (related + "\n") if related else (
        "(no related earlier mission in this area yet)\n")
    return (
        "You are the EXECUTION worker for the Ine repository. One mission, "
        "one pass.\n"
        "\n"
        "1. Carry out the mission below, in order. It is the whole scope. Do\n"
        "   not research it, re-plan it, re-scope it or decompose it — a\n"
        "   planner has already done that, once.\n"
        "2. Read what the mission needs and no more: locate before you read\n"
        "   (grep for the symbol, then read the matching region), read one\n"
        "   representative example of a pattern rather than every instance,\n"
        "   and batch independent lookups into a single message.\n"
        "3. Run focused tests for the surface you changed as you work,\n"
        "   and the full suite once at the end — not after every edit.\n"
        "4. Do not edit the `.agent/` control-plane files. Your receipt is\n"
        "   recorded for you; the plan, history, state and notes entries are\n"
        "   written from it.\n"
        "5. Do not delegate, browse, or ask questions. If a step is not\n"
        "   concrete enough to execute, that is a planning defect: say so in\n"
        "   the receipt and stop rather than inventing the missing scope.\n"
        "6. Stay inside the index's Files list unless the change genuinely\n"
        "   requires otherwise, and say why in the receipt if it does.\n"
        "7. Guardrails, never violated: do not invent language semantics, do\n"
        "   not unblock evidence-gated work, do not modify DECISIONS.md, do\n"
        "   not change language behaviour unless the index explicitly says\n"
        "   so, and keep temporary artifacts under `.tmp/`.\n"
        "\n"
        "PRIOR WORK IN THIS AREA\n"
        "\n"
        "{related}"
        "\n"
        "MISSION (PLAN item {number}): {headline}\n"
        "\n"
        "{index}\n"
        "\n"
        "REPORT\n"
        "\n"
        "{contract}"
    ).format(
        related=related,
        number=task.number,
        headline=task.text.splitlines()[0],
        index=index,
        contract=receipt_format.contract(),
    )


def _related_signals(root, number):
    """The signals `select_snippets` matches on, read from the index itself.

    A mission that declares no area, no dependencies and no files is offered
    nothing: sending something to be safe is the history this replaces.
    """
    metadata = state.read_mission_metadata(root, number) or {}
    return {
        "area": metadata.get("area", ""),
        "depends_on": metadata.get("depends_on", ()),
        "files": metadata.get("files", ()),
    }


def diagnosis_prompt(root, task, outcome, result):
    """A short follow-up asking the worker WHY one cycle did not complete.

    This is the fallback, not the normal path: every mission prompt already
    asks for a CLASSIFICATION line in the cycle's own output, and the worker
    that just ran the mission knows why it stopped. This is for a cycle
    that produced no classification — a crash, usually — where the only
    witness left is the tail of what the worker printed.

    Deliberately tiny and tool-free. The point is one classification line,
    not a second attempt at the mission: a diagnosis that goes exploring is
    just the failed mission again with a different prompt.
    """
    tail = _truncate_tail(result.output, 1200)
    return (
        "You are diagnosing ONE failed autonomous cycle in the Ine\n"
        "repository. Do NOT use any tools. Do NOT attempt the mission. Do\n"
        "NOT read or modify any file. Answer from what is below.\n"
        "\n"
        "The mission was:\n\n"
        "{task}\n"
        "\n"
        "The cycle ended as '{outcome}' with worker exit code {code}.\n"
        "\n"
        "The last thing the worker printed:\n\n"
        "{tail}\n"
        "\n"
        "Answer in at most four lines. Print these two, each on its own\n"
        "line, and nothing else:\n"
        "\n"
        "CLASSIFICATION: <" + _VOCABULARY + ">\n"
        "REASON: <one line saying what actually stopped it>\n"
        "\n"
        "needs_commander       a product, syntax or semantic decision only\n"
        "                      the commander can make\n"
        "missing_prerequisite  it cannot be built yet: a supporting\n"
        "                      feature, evidence or decision it depends on\n"
        "                      does not exist\n"
        "transient             an external, server or tooling failure that\n"
        "                      would likely clear on a retry\n"
        "agent_error           the attempt itself went wrong — misread the\n"
        "                      mission, broke a test, lost the thread\n"
    ).format(task=task.raw.strip()[:1200], outcome=outcome,
             code=result.exit_code, tail=tail or "(nothing)")


def _truncate_tail(text, limit):
    """The last `limit` characters of a worker's output.

    The END of the output is what says why a cycle stopped; the beginning is
    the setup. Returns '' for empty text; the caller substitutes a note.
    """
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return "...\n" + text[-limit:].lstrip()


def review_prompt(root, task):
    """The optional Claude review prompt (only for CLAUDE_REVIEW tasks).

    This step DECOMPOSES, so it is planning and gets the planner's
    preamble (MISSION_PROMPT.md), not the executor's execution contract.
    Project context is included so the reviewer understands the project
    constraints without reading from disk.
    """
    return (
        _planner_block(root)
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
                 max_cycles=None, max_attempts=1, dry_run=False, out=None,
                 quiet=False, verbose=False, notify=False, notifier=None,
                 usage_warn_requests=None, usage_reporter=None,
                 max_failures=DEFAULT_MAX_FAILURES,
                 stall_limit=DEFAULT_STALL_LIMIT, model=None):
        self.root = root
        self.model = model
        self.worker_factory = worker_factory or (
            lambda name: build_worker(name, root=self.root, model=self.model))
        self.impl_worker = impl_worker
        #: Optional bound on how many MISSIONS this run may attempt. None
        #: means "run the executable queue to exhaustion", which terminates
        #: because a mission is attempted at most `max_attempts` times and is
        #: then DONE, BLOCKED or DEFERRED — never re-picked in the same run.
        #: Counted in missions, not cycles, so a mission given two attempts
        #: still counts once.
        self.max_missions = max_cycles
        self.max_attempts = max_attempts
        self.max_failures = max_failures
        self.stall_limit = stall_limit
        self.dry_run = dry_run
        self.quiet = quiet
        self.verbose = verbose
        self.notify = notify
        self.out = out if out is not None else sys.stdout
        self._notifier = notifier
        self.usage_warn_requests = usage_warn_requests
        self._usage = usage_reporter or usage.UsageReporter()
        self._report_path = state.run_report_path(root)
        # Parked missions already reported in THIS run, so the start-of-run
        # report and a mid-run parking never say the same thing twice.
        self._parked_reported = set()
        self._run_id = _new_run_id()
        # Run-level tally of what happened to the QUEUE, counted once per
        # mission. It lives here rather than in the run loop so a path that
        # ends before the loop still has something honest to report: all
        # zeros means nothing was attempted, which is then literally true.
        self._tally = {}
        self._refused = []

    def _print(self, message, end="\n"):
        print(message, end=end, file=self.out)

    def _cycle_metrics(self, task, result, cycles):
        """One line of locally measured facts about this cycle.

        Every number here is measured by this process — prompt size, output
        size, wall-clock — because the alternative, a provider's own usage
        database, is not this run's cost for any provider other than the one
        that happens to write it. The run report and the console print the
        same line, so the two can never disagree.
        """
        metrics = getattr(result, "metrics", None) or {}
        return ("- [cycle {}] mission {}: exit {}, prompt {} chars/{} lines, "
                "output {} chars, {}s, timed_out={}".format(
                    cycles, task.number, result.exit_code,
                    metrics.get("prompt_chars", 0),
                    metrics.get("prompt_lines", 0),
                    metrics.get("output_chars", len(result.output or "")),
                    metrics.get("elapsed_seconds", 0),
                    bool(getattr(result, "timed_out", False))))

    def _print_cycle_metrics(self, task, result, cycles):
        """The same facts, without the report's leading dash."""
        self._print(self._cycle_metrics(task, result, cycles)[2:])

    def _dry_run_report(self, task):
        """Answer, without launching anything: what would run, for what.

        Everything here is already decided by the time the loop starts — the
        profile, the command line, the queue in selection order, the budget
        per mission — so a dry run that has to guess is not a dry run. A
        profile that will not resolve is reported as an error the same way
        `doctor` reports it, because that is the question being asked.
        """
        self._print("[dry-run] no worker was launched.")
        try:
            profile = profiles.resolve(
                self.root, self.impl_worker, model=self.model)
            command = [*effective_command(profile), *profile.argv()[1:]]
        except profiles.ProfileError as exc:
            self._print("[dry-run] worker '{}' does not resolve: {}".format(
                self.impl_worker, exc))
            return STOP_ERROR
        self._print("[dry-run] profile    : {}".format(self.impl_worker))
        self._print("[dry-run] command    : {}".format(profiles.display_command(
            command + (["<prompt on stdin>"] if profile.prompt_transport
                       == "stdin" else ["<prompt>"]))))
        self._print("[dry-run] budget     : {}, {} attempt(s) "
                    "per mission".format(
                        "the whole executable queue"
                        if self.max_missions is None
                        else "up to {} mission(s)".format(self.max_missions),
                        self.max_attempts))
        self._print("[dry-run] next       : PLAN item {} — {}".format(
            task.number, task.text.splitlines()[0]))
        relpath = state.mission_index_relpath(task.number)
        if state.read_mission_index(self.root, task.number) is None:
            self._print("[dry-run] REFUSED: no execution index at {} — the "
                        "planner must write one.".format(relpath))
        else:
            self._print("[dry-run] index      : {}".format(relpath))
        queue = [item.number for item in state.read_plan(self.root).items
                 if item.tag == "EXECUTABLE" and item.number != task.number]
        self._print("[dry-run] queue      : {} further EXECUTABLE item(s) "
                    "after this one: {}".format(
                        len(queue),
                        ", ".join(str(number) for number in queue[:10]) or "none"))
        return STOP_OK

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
        worker, sequentially. Never concurrent.

        A mission being retried after a transient or agent-error
        classification carries the previous failure's reason into its
        prompt (see `retry_block`). The note is keyed on the mission
        identity and consumed here, so it can never leak into a different
        mission that the plan advanced to in the meantime.
        """

        if task.wants_claude_review:
            review = self._worker("claude").run(
                self.root, review_prompt(self.root, task), on_line=on_line)
            if state.output_marks_human_decision(review.output):
                return review
        prompt = impl_prompt(self.root, task)
        note = getattr(self, "_retry_note", None)
        if note is not None and note[0] == task.identity:
            prompt += retry_block(note[1], note[2])
        self._retry_note = None
        return self._worker(self.impl_worker).run(
            self.root, prompt, on_line=on_line
        )

    def _diagnose(self, task, result, outcome, cycles, receipt=None):
        """The `Diagnosis` for a cycle that stopped uncompleted.

        The receipt comes first: it is the structured answer the contract
        asks for, and reading it costs nothing. The CLASSIFICATION line is
        kept as a compatibility fallback for a worker that still prints one.
        When neither is present the answer is UNCLASSIFIED, recorded with the
        worker's own text — and no second call is made to find out why.

        That last part is deliberate. A diagnosis call cost a model request
        exactly when a mission was already in trouble, and a mission that
        cannot classify itself is a fact the commander should see, not a gap
        for the loop to spend requests filling. `diagnosis_prompt` remains
        available for the planner and for humans.
        """
        if receipt is not None and receipt.status != receipt_format.DONE:
            return Diagnosis(
                receipt.status,
                _truncate_text(receipt.summary),
                "", Match.EXACT, Source.RECEIPT)
        diagnosis = diagnose_output(result.output)
        if diagnosis.classification is not None:
            return diagnosis
        return Diagnosis(
            UNCLASSIFIED,
            _truncate_text(diagnosis.reason
                           or "the worker gave no classification"),
            diagnosis.raw, diagnosis.match, Source.IN_BAND)

    def _diagnosis_outcome(self, task, result, outcome, attempts, cycles,
                           deferred, receipt=None):
        """Act on one non-completing cycle.

        The single place that decides retry-vs-defer, so `max_attempts`
        keeps one meaning. Every deferral records its reason durably (PLAN
        remark, BLOCKERS entry, run report); a retry leaves the mission
        executable with the failure's reason attached to its next prompt.

        Every non-completing cycle is also added to the mission's durable
        attempt ledger, so a mission that keeps failing across runs is
        parked instead of re-picked forever (see `record_failure`). A
        mission that reaches the parking threshold is deferred for the rest
        of THIS run as well — the ledger exists to stop spending cycles on
        it, and waiting for the next run to act on it would spend one more.

        Returns `(attempts, pending_human, failed)`: the retry budget for
        this mission, plus the run-level flags this outcome contributes —
        the caller owns the loop's state, so nothing is smuggled through
        `self`.
        """
        if state.human_decision_indicated(self.root):
            # A gate opened on disk during this cycle (the `human` outcome
            # catches the marker in the worker's OUTPUT; this catches the
            # one it wrote to a .agent/ file). The mission stopped because
            # of the gate, so there is nothing to diagnose and no point
            # spending a call to ask: record it as the judgment case it is.
            diagnosis = Diagnosis(
                Classification.NEEDS_COMMANDER.value,
                "a HUMAN_DECISION_REQUIRED gate is open", "",
                Match.EXACT, Source.GATE)
        else:
            diagnosis = self._diagnose(task, result, outcome, cycles, receipt)
        classification = diagnosis.classification
        action = classify_action(
            classification, outcome, attempts, self.max_attempts)
        headline = task.text.splitlines()[0]
        detail = diagnosis.reason or "(no reason given)"
        self._print("[cycle {}] diagnosis: {} — {}".format(
            cycles, classification, detail))
        # How the class was obtained, durably: drift, a fallback call and a
        # failed diagnosis all mean the recorded class is weaker evidence
        # than a clean in-band answer, and the run report is where that
        # distinction has to survive.
        trace = diagnosis_trace(cycles, diagnosis)
        if trace:
            state.append_run_report(self.root, [
                "- [cycle {}] {}: {}".format(cycles, level.upper(), message)
                for level, message in trace])
            for level, message in trace:
                if level == "warning":
                    self._print(
                        "[cycle {}] warning: {}".format(cycles, message))

        if action == "retry":
            state.append_run_report(self.root, [
                "- [cycle {}] {} ({}): {} — retrying with the reason "
                "attached".format(cycles, action.upper(), classification,
                                  detail)])
            state.append_item_remark(
                self.root, task.identity,
                "attempt {} did not complete ({}: {}); retrying with that "
                "reason attached".format(attempts + 1, classification, detail))
            self._notify(
                "Ine · retrying task",
                self._truncate("{} — {}".format(headline, detail)))
            self._print(
                "[cycle {}] retrying this mission with the failure's reason "
                "attached to its prompt.".format(cycles))
            self._retry_note = (task.identity, classification, detail)
            if self._record_failure(task, classification, detail, outcome,
                                    cycles):
                # Parked as of this cycle: stop picking it in this run too.
                deferred.add(task.identity)
                self._count_tally("deferred")
            return attempts + 1, False, False

        if action == "human":
            state.append_run_report(self.root, [
                "- [cycle {}] needs commander judgment ({}): {} — recorded "
                "and deferred".format(cycles, classification, detail)])
            item = state.read_plan(self.root).item(identity=task.identity)
            if item is not None and item.executable:
                state.mark_blocked(
                    self.root, task.identity,
                    "needs commander judgment: {}; original text "
                    "preserved".format(detail))
                state.append_blocker(
                    self.root, item.number, self._truncate(headline, 90),
                    "The worker stopped this mission and reported it needs a "
                    "decision only the commander can make. Reason given: "
                    + detail + ". Mission tagged BLOCKED (original text "
                    "preserved) and deferred so independent work continues. "
                    "Awaiting a commander resolution.")
            deferred.add(task.identity)
            # Counted here, once, and counted as blocked as well as
            # human-gated: the mission really is tagged BLOCKED in the plan,
            # and a summary that said "0 blocked" while the plan said BLOCKED
            # would be wrong in the direction that costs the commander time.
            self._count_tally("human")
            self._count_tally("blocked")
            self._print(
                "[cycle {}] needs commander judgment — mission recorded and "
                "deferred; independent work continues.".format(cycles))
            self._notify(
                "Ine · decision required",
                self._truncate("{} — {}".format(headline, detail)))
            return 0, True, False

        if action == "blocked":
            self._record_blocked(task, detail, cycles, classification)
            deferred.add(task.identity)
            self._count_tally("blocked")
            self._print(
                "[cycle {}] missing prerequisite — mission recorded and "
                "deferred; independent work continues.".format(cycles))
            return 0, False, False

        # deferred: unclassifiable, or out of retries
        exhausted = retryable(classification, outcome)
        state.append_run_report(self.root, [
            "- [cycle {}] {} ({}): {} — recorded and deferred".format(
                cycles, "RETRIES EXHAUSTED" if exhausted else "DEFERRED",
                classification, detail)])
        state.append_item_remark(
            self.root, task.identity,
            "{} after {} attempt(s) ({}: {}); recorded and deferred so "
            "independent work continues".format(
                "retries exhausted" if exhausted else "did not complete",
                attempts + 1, classification, detail))
        deferred.add(task.identity)
        # One mission, one bucket. A mission that failed is reported as
        # failed; `deferred` is reserved for one that was held without a
        # failure to report, so the four counts sum to the missions this
        # run touched instead of counting a single mission twice.
        self._count_tally("failed" if outcome == "failed" else "deferred")
        if exhausted:
            self._print(
                "[cycle {}] retries exhausted — mission not completed; "
                "recorded and deferred so independent work "
                "continues.".format(cycles))
        else:
            self._print(
                "[cycle {}] mission not completed — recorded and deferred; "
                "independent work continues.".format(cycles))
        self._notify(
            "Ine · task failed" if outcome == "failed" else "Ine · task stuck",
            self._truncate("{} — {}".format(headline, detail)))
        self._record_failure(task, classification, detail, outcome, cycles)
        return 0, False, True

    def _record_blocked(self, task, detail, cycles=None, classification=None,
                        reported_by="The worker reported"):
        """Record one mission BLOCKED on a missing prerequisite, and defer it.

        Two distinct causes reach this record, and they leave the same
        durable trace so the commander reads one shape in PLAN.md,
        BLOCKERS.md and RUN_REPORTS.md:

        - the worker ran and reported a missing prerequisite
          (`_diagnosis_outcome` — `cycles` and `classification` given), or
        - no execution index existed, so no worker was launched at all
          (`_refuse_missing_index` — no cycle happened).

        The mission's original PLAN.md text and tag are always preserved;
        only a `> remark:` line is appended and the tag becomes BLOCKED.
        The caller owns the deferral set and the console line, because only
        it knows which of the two causes it is reporting.
        """
        marker = ("[cycle {}]".format(cycles) if cycles is not None
                  else "[refused]")
        label = " ({})".format(classification) if classification else ""
        headline = task.text.splitlines()[0]
        state.append_run_report(self.root, [
            "- {} cannot be built yet{}: {} — recorded and deferred".format(
                marker, label, detail)])
        item = state.read_plan(self.root).item(identity=task.identity)
        if item is not None and item.executable:
            state.mark_blocked(
                self.root, task.identity,
                "missing prerequisite: {}; original text "
                "preserved".format(detail))
            state.append_blocker(
                self.root, item.number, self._truncate(headline, 90),
                "{} this mission cannot be implemented yet because something "
                "it depends on does not exist. Reason given: {}. Mission "
                "tagged BLOCKED (original text preserved) and deferred so "
                "independent work continues.".format(reported_by, detail))
        self._notify(
            "Ine · task blocked",
            self._truncate("{} — {}".format(headline, detail)))

    def _refuse_missing_index(self, task, deferred, refused):
        """Refuse to run a mission the planner has not indexed.

        The worker is never launched. Asking a worker to work out how to do
        an unindexed mission is precisely the expensive behaviour the
        execution index exists to remove, and the answer would be research
        the planner owes once rather than every cycle. The mission is
        recorded through the same path as a missing prerequisite, so the
        commander sees the same shape whichever way it was found, and the
        run continues with whatever independent indexed work remains.
        """
        relpath = state.mission_index_relpath(task.number)
        detail = ("no execution index at {} — the planner must "
                  "write one".format(relpath))
        headline = task.text.splitlines()[0]
        self._print(
            "[refused] no execution index at {}: {} — the planner must "
            "write one before this mission can run.".format(
                relpath, self._truncate(headline, 70)))
        self._record_blocked(task, detail,
                             reported_by="The supervisor found")
        deferred.add(task.identity)
        refused.append(task.identity)

    def _record_failure(self, task, classification, detail, outcome, cycles):
        """Add this cycle to the mission's cross-run attempt ledger.

        Returns True when the mission has now failed often enough to be
        PARKED (never re-picked until the commander acts). Parking is
        reported once, at the moment it happens, because it changes what
        the commander sees: the mission is no longer merely deferred, it is
        out of the loop until someone rewrites or clears it.
        """
        count = record_failure(self.root, task.identity, classification,
                               detail, outcome, run_id=self._run_id)
        limit = self.max_failures
        if not limit or count["runs"] < limit:
            return False
        self._parked_reported.add(task.identity)
        headline = task.text.splitlines()[0]
        self._print(
            "[cycle {}] parked: {} failed run(s) ({} attempts recorded); this "
            "mission will not be picked again until it is rewritten or its "
            "entry is removed from .agent/{}.".format(
                cycles, count["runs"], count["attempts"], ATTEMPTS_NAME))
        state.append_run_report(self.root, [
            "- [cycle {}] PARKED after {} failed run(s) ({}: {})".format(
                cycles, count["runs"], canonical(classification),
                self._truncate(detail, 110))])
        self._notify(
            "Ine · task parked",
            self._truncate("{} — failed in {} run(s); parked".format(
                headline, count["runs"])))
        return True

    def _outcome(self, result, task, plan, receipt=None):
        """Classify what one worker cycle did to `task`.

        Returns 'done', 'human', 'blocked', 'failed', or 'stuck'.

        A receipt reporting completion is decisive on its own, provided the
        worker actually exited cleanly: that is what lets a worker leave the
        plan alone and still be recorded as having finished the mission. The
        plan is re-read AFTER the cycle as the fallback, so a worker that
        marks the item DONE or BLOCKED itself, or removes it, is still read
        correctly. The HUMAN_DECISION_REQUIRED marker is checked FIRST
        (line-based, own-line only) because a decision gate dominates any
        incidental re-tag the worker performed.
        """
        if state.output_marks_human_decision(result.output):
            return "human"
        if (receipt is not None and receipt.completed
                and result.exit_code == 0):
            return "done"
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

    def _record_receipt(self, task, receipt, outcome):
        """Record one completed mission from its receipt, and report it.

        The recording belongs to the supervisor, not the worker: a mission
        that finished is tagged DONE and given its history block, its bounded
        state head and — when it carried one — its notes section, all from a
        few fields of JSON rather than from a session's worth of prose.

        A cycle that finished WITHOUT a receipt is still a completed mission
        (the worker's own plan edit says so) but the run report says the
        receipt is missing, because the gap is what a commander would
        otherwise have to guess at later.
        """
        if receipt is None:
            state.append_run_report(self.root, [
                "- [receipt] none printed by the worker; the plan's own tag "
                "is the only record of this outcome"])
            return []
        state.record_mission_outcome(
            self.root, task, receipt, outcome, session=self._session)
        lines = receipt.report_lines()
        proposal = self._propose_follow_up(task, receipt)
        if proposal:
            lines.append(proposal)
        return lines

    def _propose_follow_up(self, task, receipt):
        """File a receipt's follow-up as a proposal, or say why not.

        A follow-up is a suggestion about what to do NEXT, so it is appended
        to the plan under `CLAUDE_REVIEW` — a tag the selection rule never
        treats as executable. That is the whole safety property: a worker
        cannot turn its own suggestion into work the loop will do, because
        the plan's parsing, not the worker's intent, decides what is
        executable. A run that merely restated the mission adds nothing, so
        that case records that it was dropped instead of writing a line of
        noise.
        """
        text = (receipt.follow_up or "").strip()
        if not text:
            return ""
        if _same_work_as(task, text):
            return ("- follow-up dropped: it restates this mission "
                    "({}), which the plan already carries".format(
                        _truncate_text(text)))
        number = state.propose_follow_up(self.root, text, origin=task.number)
        if number is None:
            return ("- follow-up already proposed by an earlier mission: "
                    "{}".format(_truncate_text(text)))
        self._count_tally("proposed")
        return ("- follow-up filed as PLAN item {} (`CLAUDE_REVIEW`): {} — a "
                "proposal only; no run executes it until a human re-tags "
                "it".format(number, _truncate_text(text)))

    def _open_queue_count(self):
        """How many EXECUTABLE missions are still selectable right now.

        Read from the plan rather than guessed: after the run stopped at a
        bound, the honest statement of what is left is what the plan still
        offers, not a subtraction that assumes nothing changed.
        """
        return len([item for item in state.read_plan(self.root).items
                    if item.executable])

    def _count_tally(self, key, by=1):
        """Count one mission under key in this run's tally."""
        tally = self._tally
        tally[key] = tally.get(key, 0) + by
        return tally[key]

    def _run_tally(self):
        """This run's outcome, counted once per mission.

        The completion summary reports what happened to the QUEUE, so it is
        built from missions rather than cycles: a mission given two attempts
        is one mission that failed, not two failures.
        """
        return dict(self._tally)

    def _completion_summary(self):
        """The one line the commander is notified with at the end of a run.

        Counts plus the things that need a decision, and nothing else: the
        per-mission started/done banners are gone because a long queue would
        spend a notification per mission, which is noise rather than
        information.
        """
        tally = self._run_tally()
        parts = [
            "{} completed".format(tally.get("done", 0)),
            "{} failed".format(tally.get("failed", 0)),
            "{} blocked".format(tally.get("blocked", 0)),
            "{} deferred".format(tally.get("deferred", 0)),
        ]
        if self._refused:
            parts.append("{} refused (no execution index)".format(
                len(self._refused)))
        if tally.get("proposed"):
            parts.append("{} follow-up(s) proposed".format(
                tally["proposed"]))
        summary = ", ".join(parts)
        pending = self._tally.get("human", 0)
        if pending:
            summary += ("; {} waiting on your decision".format(pending))
        return summary

    def _completion_notification(self, code):
        """(title, body) for the run's single completion notification.

        One notification per run, carrying what happened to the queue. A run
        that completed nothing says so in its title, because a popup reading
        "run complete" is exactly how a run that achieved nothing gets
        mistaken for a successful one.
        """
        tally = self._run_tally()
        body = self._completion_summary()
        if tally.get("done"):
            return "Ine · run complete", body
        # `proposed` and `human` are not completions: a run whose only output
        # was a suggestion, or a question, completed nothing and says so.
        if any(tally.get(key) for key in ("failed", "blocked", "deferred")):
            return "Ine · run ended with nothing completed", body
        return "Ine · run complete", body

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
        summary = report_summary or message or "done"
        if self._tally or self._refused:
            # The queue's outcome, in the run report as well as the
            # notification: the report is the durable record, the
            # notification is what reaches the commander.
            summary = "{} ({})".format(summary, self._completion_summary())
            state.append_run_report(self.root, [
                "- missions: " + self._completion_summary()])
        state.end_run_report(self.root, code, summary)
        if message and print_message:
            self._print(message)
        if notify_title or notify_body is not None:
            self._notify(
                notify_title or "Ine · run complete",
                notify_body if notify_body is not None
                else self._run_summary(code))
        else:
            default_title, default_body = self._completion_notification(code)
            self._notify(default_title, default_body)
        return code

    def _parked(self):
        """Missions with enough recorded failures to stop being re-picked."""
        return parked_missions(self.root, self.max_failures)

    def _parked_headline(self, identity):
        """The mission's current headline, or its identity when it is gone."""
        item = state.read_plan(self.root).item(identity=identity)
        if item is None:
            return identity
        return item.text.splitlines()[0]

    def _report_parked(self, parked):
        """Say plainly which missions are out of the loop, and why.

        Reported once per run, in the run report and on the console, so the
        reason a mission stopped appearing is never a mystery. Missions
        already reported this run — at the start, or at the moment they were
        parked — are skipped, so the record never says the same thing twice.
        Nothing extra is notified: the run's own completion notification
        covers it.
        """
        for identity, entry in sorted(parked.items()):
            if identity in self._parked_reported:
                continue
            self._parked_reported.add(identity)
            runs = entry.get("runs")
            attempts = entry.get("attempts")
            classification = canonical(entry.get("classification"))
            reason = _truncate_text(entry.get("reason") or "(no reason given)")
            headline = self._parked_headline(identity)
            self._print(
                "[parked] {} (failed in {} run(s), {} attempt(s); last {}: {})"
                " — not re-picked; rewrite the mission or remove its entry "
                "from .agent/{} to retry it.".format(
                    self._truncate(headline, 90), runs, attempts,
                    classification, reason, ATTEMPTS_NAME))
            state.append_run_report(self.root, [
                "- parked: failed in {} run(s), {} attempt(s) (last: {}: {}) "
                "— {}".format(
                    runs, attempts, classification,
                    self._truncate(reason, 110),
                    self._truncate(headline, 110))])

    def run(self):
        plan = state.read_plan(self.root)
        # The ledger remembers missions still in the loop, so entries for
        # work that left it (rewritten, removed, completed, blocked) are
        # dropped here rather than accumulating as phantom parked missions.
        executable = [item.identity for item in plan.items if item.executable]
        prune_attempts(self.root, executable)
        # Missions that already failed often enough across earlier runs are
        # skipped from the start: re-picking them blindly is what turned one
        # hard mission into thirteen consecutive runs of nothing.
        self._parked_reported = set()
        self._run_id = _new_run_id()
        # One session per run: the history block a completed mission gets is
        # numbered from here, so an autonomous run reads as one session
        # rather than as a new session per mission.
        self._session = state.next_session_number(self.root)
        parked = self._parked()
        task = plan.first_executable(skip=parked)
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
            state.begin_run_report(self.root, self._command_line())
            if parked:
                # Nothing executable is left because everything that failed
                # has been parked: that is not "all work done".
                self._report_parked(parked)
                return self._finish(
                    STOP_ERROR,
                    "every remaining mission is parked after repeated "
                    "failures; commander action required.",
                    notify_body="Missions stopped being retried after "
                                "repeated failures and now need your review.")
            self._no_work()
            self._notify(
                "Ine · run complete",
                "All tasks done — nothing left to run.")
            return self._finish(
                STOP_OK, None, print_message=False,
                report_summary="no executable work remains.")

        if self.dry_run:
            return self._dry_run_report(task)

        state.begin_run_report(self.root, self._command_line())

        self._usage_before = self._usage.snapshot()
        self._usage_prev = dict(self._usage_before)
        self._warned_usage = False
        state.append_run_report(self.root, [
            "- usage start: " + usage.format_snapshot(self._usage_before)])
        if parked:
            self._report_parked(parked)

        attempts = 0
        cycles = 0
        missions = 0             # distinct missions attempted, for the bound
        self._counted = set()    # mission identities already counted
        measurements = []       # this run's own numbers, one entry per cycle
        run_started = time.monotonic()
        deferred = set(parked)  # mission identities deferred this run
        refused = []           # missions refused for want of an index
        pending_human = False  # a genuine decision gate is open
        had_failure = False    # at least one mission failed this run
        stalled = 0            # consecutive cycles that changed nothing
        worktree_before = worktree_signature(self.root)

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

            if self.max_missions is not None and missions >= self.max_missions:
                self._print(
                    "Reached the --max-missions bound of {}; stopping with "
                    "the rest of the queue still open.".format(
                        self.max_missions))
                return self._finish(
                    STOP_ERROR,
                    "stopped at the --max-missions bound of {}; {} mission(s) "
                    "still EXECUTABLE in the plan.".format(
                        self.max_missions, self._open_queue_count()))

            if self.stall_limit and stalled >= self.stall_limit:
                # Evidence guard: N cycles in a row that neither completed
                # nor blocked a mission AND left the tree (outside `.agent/`)
                # untouched. That is the measured failure mode — runs that
                # spend provider requests rewriting their own records — so
                # stop early and report, rather than spending the whole cycle
                # budget on it. Checked AFTER the cycle bound so a cycle
                # limit stays the hard, predictable stop.
                state.append_run_report(self.root, [
                    "- outcome: no progress for {} consecutive cycle(s)"
                    .format(stalled)])
                return self._finish(
                    STOP_ERROR,
                    "no progress for {} consecutive cycle(s) — nothing was "
                    "completed or blocked and no file changed outside "
                    ".agent/; execution stopped early.".format(stalled))

            # `max_attempts` is deliberately NOT a stop condition any more.
            # Exhausting it defers that ONE mission (see _diagnosis_outcome)
            # so a single hard mission can no longer end a run that still
            # has independent work in it. Termination remains guaranteed: a
            # deferred mission is never re-picked this run, and the optional
            # `--max-missions` bound above is a bound on the queue itself.

            headline = task.text.splitlines()[0]
            if state.read_mission_index(self.root, task.number) is None:
                # No index: the planner has not written the concrete steps
                # this mission needs, and the worker must never be asked to
                # invent them. Refusing costs the plan one BLOCKED item and
                # costs this run no worker call — and no cycle, because no
                # worker ran. `continue` re-picks, so one unindexed mission
                # cannot end a run that still has indexed work in it.
                self._refuse_missing_index(task, deferred, refused)
                self._refused = list(refused)
                task = plan.first_executable(skip=deferred)
                continue
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
            # A mission counts once against the bound, however many attempts
            # it was given: the bound is on the queue, not on requests.
            if task.identity not in self._counted:
                self._counted.add(task.identity)
                missions += 1
            plan = state.read_plan(self.root)
            state.append_run_report(self.root, [
                self._cycle_metrics(task, result, cycles)])
            self._print_cycle_metrics(task, result, cycles)
            measurements.append(dict(getattr(result, "metrics", None) or {},
                                     timed_out=bool(
                                         getattr(result, "timed_out", False))))
            receipt = receipt_format.parse_receipt(result.output)
            if receipt is not None:
                # Every receipt leaves a compact trace, whatever the outcome:
                # a blocked mission is exactly the one a later mission in the
                # same area most needs to know about.
                compaction.write_snippet(self.root, task.number, receipt)
            outcome = self._outcome(result, task, plan, receipt)
            task_id = task.identity

            if outcome == "done":
                state.append_run_report(self.root, [
                    "- [cycle {}] DONE".format(cycles)])
                self._print("[cycle {}] mission completed.".format(cycles))
                attempts = 0
                # Finishing is what clears a failure history: a mission that
                # finally completed on a later run starts clean if it is ever
                # re-opened.
                clear_mission_attempts(self.root, task_id)
                recorded = self._record_receipt(task, receipt, outcome)
                if recorded:
                    state.append_run_report(self.root, recorded)
                self._tally["done"] = self._tally.get("done", 0) + 1
            elif outcome == "human":
                pending_human = True
                self._tally["human"] = self._tally.get("human", 0) + 1
                self._tally["blocked"] = self._tally.get("blocked", 0) + 1
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
                self._tally["blocked"] = self._tally.get("blocked", 0) + 1
                deferred.add(task_id)
                attempts = 0
                self._print(
                    "[cycle {}] mission became blocked — recorded and "
                    "deferred; independent work continues.".format(cycles))
                self._notify(
                    "Ine · task blocked",
                    self._truncate(headline))

            elif outcome in ("failed", "stuck"):
                # The cycle stopped without completing the mission. The class
                # comes from the receipt, or from the worker's own
                # CLASSIFICATION line, and when it printed neither the cycle
                # is recorded as unknown rather than spending a second
                # request to ask why. Then act on the answer: retry with the
                # reason attached, hold it for the commander, record it blocked
                # on a missing prerequisite, or defer it with the reason
                # recorded. The run continues with independent work in every
                # one of those cases; only the whole run's exit code
                # remembers that something was left unfinished.
                # No tally here: `_diagnosis_outcome` owns the counts, and it
                # is the only place that knows which single bucket describes
                # this mission. Adding to the tally afterwards counted the
                # same mission twice (once as human, once as failed).
                attempts, human_flag, failed_flag = self._diagnosis_outcome(
                    task, result, outcome, attempts, cycles, deferred,
                    receipt)
                pending_human = pending_human or human_flag
                had_failure = had_failure or failed_flag

            signature = worktree_signature(self.root)
            # "Known" on both sides, so a repository git cannot describe
            # yields no evidence either way: silence must never be read as
            # a stall any more than as progress.
            known = worktree_before is not None and signature is not None
            changed = known and signature != worktree_before
            worktree_before = signature
            if outcome in ("failed", "stuck") and known and not changed:
                stalled += 1
                state.append_run_report(self.root, [
                    "- [cycle {}] no progress: no completed or blocked "
                    "mission and no file changed outside .agent/".format(
                        cycles)])
            else:
                stalled = 0

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
        # BLOCKED/DONE or deferred or parked or refused.
        # The run's own cost, measured here rather than read out of a
        # provider's global database: one invocation per mission attempt, and
        # the prompt/output sizes this process actually sent and received.
        self._print("this run: " + usage.format_local(
            measurements, time.monotonic() - run_started))
        state.append_run_report(self.root, [
            "- this run (local): " + usage.format_local(
                measurements, time.monotonic() - run_started)])
        parked_now = self._parked()
        if pending_human:
            return self._finish(
                STOP_HUMAN,
                "missions remain held for commander judgment; "
                "independent work completed.")
        if refused:
            # Nothing was executed for these. An unindexed mission is
            # outstanding PLANNER work, not finished work, so the run must
            # not report success — that is the one reading the commander
            # must never get from this path.
            if parked_now:
                self._report_parked(parked_now)
            return self._finish(
                STOP_ERROR,
                "{} mission(s) refused for want of an execution index "
                "(.agent/{}/<item-number>.md): the planner must write them "
                "before the loop can run them{}.".format(
                    len(refused), state.MISSION_DIR,
                    " Independent missions also remain deferred or parked."
                    if (had_failure or parked_now) else ""))
        if parked_now and not had_failure:
            self._report_parked(parked_now)
            return self._finish(
                STOP_ERROR,
                "independent work completed, but missions remain parked "
                "after repeated failures; commander action required.")
        if had_failure:
            if parked_now:
                return self._finish(
                    STOP_ERROR,
                    "missions deferred after failing and missions parked "
                    "after repeated failures; no executable work remains.")
            return self._finish(
                STOP_ERROR,
                "missions deferred after failing; "
                "no executable work remains.")
        self._no_work()
        return self._finish(
            STOP_OK, None, print_message=False,
            report_summary="no executable work remains.")