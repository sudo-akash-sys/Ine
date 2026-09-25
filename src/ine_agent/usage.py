"""Read-only OpenCode usage telemetry for ine-agent.

Observability, not policy. This module reads the local OpenCode sqlite
database (`opencode.db`) so the supervisor can report how many model
requests and tokens OpenCode has recorded — at run start, at each mission
boundary, and at run end. Everything here is read-only and best-effort:

- the database is opened with `mode=ro` (never written, never locked);
- if it is absent, locked, or the `opencode` CLI cannot resolve it, every
  query degrades to a zero/empty snapshot so the supervisor loop never
  depends on telemetry.

Interpretation: a `message` row with `role == "assistant"` corresponds to
one model request, which is how the free tier is metered. The numbers
reported here are OBSERVED OpenCode usage recorded locally — NOT the
provider's actual quota (opencode cannot see that). Do not treat them as
an exact daily limit until verified against a real quota/rejection event.
"""

import datetime
import os
import shutil
import subprocess
import time

import sqlite3


ZERO = {
    "requests": 0,
    "tokens_input": 0,
    "tokens_output": 0,
    "tokens_reasoning": 0,
    "cost": 0.0,
    "by_model": {},
    "sessions": [],
    "day_requests": 0,
}


def default_db_path():
    """The well-known OpenCode data location (~/.local/share/opencode)."""
    return os.path.join(
        os.path.expanduser("~"), ".local", "share", "opencode", "opencode.db"
    )


def db_path():
    """Resolve the OpenCode database path, preferring `opencode db path`.

    Falls back to the well-known default location. Returns None when no
    database can be found so callers degrade to a zero snapshot.
    """
    exe = shutil.which("opencode")
    if exe:
        try:
            result = subprocess.run(
                [exe, "db", "path"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="surrogateescape",
                timeout=15,
            )
            candidate = result.stdout.strip()
            if candidate and os.path.isfile(candidate):
                return candidate
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    fallback = default_db_path()
    return fallback if os.path.isfile(fallback) else None


def open_db(path):
    """Open `path` read-only. Returns a connection or None on any failure."""
    if not path:
        return None
    try:
        return sqlite3.connect("file:{}?mode=ro".format(path), uri=True)
    except sqlite3.Error:
        return None


def _day_start_ms():
    """UTC midnight of today in epoch milliseconds (the DB stores UTC ms)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp() * 1000)


def _int(value):
    return int(value) if value is not None else 0


def snapshot(db):
    """One consistent usage snapshot of `db`, or ZERO when unreadable.

    `db` is an open sqlite3 connection (see open_db). A snapshot is a dict
    with aggregate request/token/cost totals plus a per-model and per-session
    breakdown, so callers can show "which model, which session" for a run.
    """
    if db is None:
        return dict(ZERO)
    # ZERO's `by_model`/`sessions` are mutable containers: each snapshot
    # needs its own so snapshots never bleed into each other.
    out = dict(ZERO)
    out["by_model"] = {}
    out["sessions"] = []
    try:
        row = db.execute(
            "select count(*), "
            "coalesce(sum(json_extract(data, '$.tokens.input')), 0), "
            "coalesce(sum(json_extract(data, '$.tokens.output')), 0), "
            "coalesce(sum(json_extract(data, '$.tokens.reasoning')), 0) "
            "from message where json_extract(data, '$.role') = 'assistant'"
        ).fetchone()
        out["requests"] = _int(row[0])
        out["tokens_input"] = _int(row[1])
        out["tokens_output"] = _int(row[2])
        out["tokens_reasoning"] = _int(row[3])

        cost = db.execute(
            "select coalesce(sum(cost), 0) from session"
        ).fetchone()
        out["cost"] = float(cost[0] if cost else 0)

        for model, count in db.execute(
            "select coalesce(json_extract(data, '$.modelID'), 'unknown') as m, "
            "count(*) from message "
            "where json_extract(data, '$.role') = 'assistant' "
            "group by m order by count(*) desc"
        ):
            out["by_model"][model] = _int(count)

        for session_id, title, count, tin, tout in db.execute(
            "select s.id, coalesce(s.title, ''), count(m.id), "
            "coalesce(sum(json_extract(m.data, '$.tokens.input')), 0), "
            "coalesce(sum(json_extract(m.data, '$.tokens.output')), 0) "
            "from session s "
            "left join message m on m.session_id = s.id "
            "and json_extract(m.data, '$.role') = 'assistant' "
            "group by s.id order by s.time_created desc"
        ):
            out["sessions"].append({
                "id": session_id,
                "title": title,
                "requests": _int(count),
                "tokens_input": _int(tin),
                "tokens_output": _int(tout),
            })

        day = db.execute(
            "select count(*) from message "
            "where json_extract(data, '$.role') = 'assistant' "
            "and time_created >= ?",
            (_day_start_ms(),),
        ).fetchone()
        out["day_requests"] = _int(day[0])
    except sqlite3.Error:
        return dict(ZERO)
    return out


def delta(before, after):
    """Difference between two snapshots, for the observers of one window.

    Returns only nonzero entries so a quiet mission / clean run produces an
    empty-looking report line rather than a wall of zeros.
    """
    out = {
        "requests": max(after["requests"] - before["requests"], 0),
        "tokens_input": max(after["tokens_input"] - before["tokens_input"], 0),
        "tokens_output": max(after["tokens_output"] - before["tokens_output"], 0),
        "tokens_reasoning": max(after["tokens_reasoning"] - before["tokens_reasoning"], 0),
        "cost": max(after["cost"] - before["cost"], 0.0),
    }
    models = set(before["by_model"]) | set(after["by_model"])
    by_model = {}
    for model in models:
        diff = after["by_model"].get(model, 0) - before["by_model"].get(model, 0)
        if diff > 0:
            by_model[model] = diff
    out["by_model"] = by_model
    return out


def has_usage(delta_dict):
    """True when a delta carries any nonzero observed usage."""
    return any(v != 0 for k, v in delta_dict.items() if k != "by_model") \
        or bool(delta_dict.get("by_model"))


def format_snapshot(snapshot_dict, scope="global"):
    """One-line human summary of a snapshot.

    `scope` says whose usage this is. The database is global — every request
    OpenCode has ever made on this machine, from any session — so it is
    labelled as such and never presented as this run's cost. Only a delta
    (`format_delta`) or the run's own local measurement is a per-run number.
    """
    label = "global" if scope == "global" else scope
    text = "{} requests, {:,} in / {:,} out / {:,} reasoning tokens, ${:.4f}".format(
        snapshot_dict["requests"],
        snapshot_dict["tokens_input"],
        snapshot_dict["tokens_output"],
        snapshot_dict["tokens_reasoning"],
        snapshot_dict["cost"],
    )
    if snapshot_dict["by_model"]:
        text += " by model: " + ", ".join(
            "{}={}".format(model, count)
            for model, count in sorted(snapshot_dict["by_model"].items())
        )
    if label == "global":
        text += " ({} total for this machine — not this run's cost)".format(
            label)
    return text


def format_local(cycles, elapsed_seconds=None):
    """This run's own measured cost, from numbers this process recorded.

    Provider-independent by construction: prompt characters, output
    characters and wall-clock, counted here. The request *count* is exact
    because the supervisor knows how many invocations it made — one per
    mission attempt — which is the number a run report should lead with.
    """
    if not cycles:
        return "no worker cycles this run"
    chars = sum(cycle.get("prompt_chars", 0) for cycle in cycles)
    out_chars = sum(cycle.get("output_chars", 0) for cycle in cycles)
    timed_out = sum(1 for cycle in cycles if cycle.get("timed_out"))
    text = "{} worker invocation(s) (1 per mission attempt), {:,} prompt " \
           "chars, {:,} output chars".format(len(cycles), chars, out_chars)
    if elapsed_seconds is not None:
        text += ", {:.1f}s wall clock".format(elapsed_seconds)
    if timed_out:
        text += ", {} timed out".format(timed_out)
    return text


def format_delta(delta_dict):
    """One-line human summary of a delta (e.g. a single mission's usage)."""
    text = "+{} requests".format(delta_dict["requests"])
    text += ", +{:,} in / +{:,} out tokens".format(
        delta_dict["tokens_input"], delta_dict["tokens_output"])
    if delta_dict["tokens_reasoning"]:
        text += " (+{:,} reasoning)".format(delta_dict["tokens_reasoning"])
    if delta_dict["cost"]:
        text += ", +${:.4f}".format(delta_dict["cost"])
    if delta_dict["by_model"]:
        text += " by model: " + ", ".join(
            "{}={}".format(model, count)
            for model, count in sorted(delta_dict["by_model"].items())
        )
    return text


class UsageReporter:
    """Resolves and retains the OpenCode database for a supervisor run.

    `snapshot()` re-reads the database each call, so the supervisor can take
    one snapshot per mission boundary without managing connections itself.
    Any failure (missing database, locked file, malformed schema) degrades to
    ZERO — telemetry never blocks the loop.
    """

    def __init__(self, path=None):
        self._path = path
        self._resolved = path is not None
        self._conn = None

    def _connect(self):
        if self._conn is None:
            if not self._resolved:
                self._path = db_path()
                self._resolved = True
            self._conn = open_db(self._path)
        return self._conn

    def snapshot(self):
        return snapshot(self._connect())

    def delta(self, before, after):
        return delta(before, after)

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            self._conn = None