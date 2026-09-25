"""The worker's structured receipt.

Every worker invocation ends by printing one small JSON object after a fixed
marker line. The supervisor reads it to decide what happened, and the
recorder turns it into the PLAN / HISTORY / STATE / NOTES entries, so the
model spends its tokens on the mission rather than on prose bookkeeping.

The receipt is the machine-readable answer that replaced the free-form
`CLASSIFICATION:` / `REASON:` block the prompt used to ask for. The
classification parser is still there — a worker that prints one is still read
— but the receipt is what the current contract requires, and the two cannot
drift because the contract text and the parser live in this one module.

Nothing here raises on bad input: a receipt that cannot be read is
`None`, which the supervisor treats as "this worker did not report", not as a
reason to spend another request working out what it meant.
"""

import json

MARKER = "INE_RECEIPT_JSON"

DONE = "done"
NEEDS_COMMANDER = "needs_commander"
MISSING_PREREQUISITE = "missing_prerequisite"
FAILED = "failed"

STATUSES = (DONE, NEEDS_COMMANDER, MISSING_PREREQUISITE, FAILED)

SUMMARY_LIMIT = 2000
FOLLOW_UP_LIMIT = 1000
FINDING_LIMIT = 2000
ENTRY_LIMIT = 200
LIST_LIMIT = 50
AREA_LIMIT = 80

EXAMPLE = (
    '{"status": "' + DONE + '", "summary": "what happened", '
    '"changed_files": ["src/thing.py"], "verification": ["pytest -q: 12 '
    'passed"], "area": "ine-agent", "finding": "a durable fact", '
    '"follow_up": "a proposed next mission"}'
)


class Receipt:
    """One worker's account of one mission attempt.

    A plain value object: the fields are already bounded and typed, so the
    recorder never has to re-validate what it is handed.
    """

    __slots__ = ("status", "summary", "changed_files", "verification",
                 "area", "finding", "follow_up")

    def __init__(self, status, summary, changed_files=(), verification=(),
                 area=None, finding=None, follow_up=None):
        self.status = status
        self.summary = summary
        self.changed_files = list(changed_files)
        self.verification = list(verification)
        self.area = area
        self.finding = finding
        self.follow_up = follow_up

    @property
    def completed(self):
        return self.status == DONE

    def as_dict(self):
        return {
            "status": self.status,
            "summary": self.summary,
            "changed_files": list(self.changed_files),
            "verification": list(self.verification),
            "area": self.area,
            "finding": self.finding,
            "follow_up": self.follow_up,
        }

    def report_lines(self):
        """The receipt as the durable run-report lines that carry it."""
        lines = ["- receipt: {}".format(self.status),
                 "- summary: {}".format(_one_line(self.summary))]
        if self.area:
            lines.append("- area: {}".format(self.area))
        if self.changed_files:
            lines.append("- files: " + ", ".join(self.changed_files))
        for entry in self.verification:
            lines.append("- verified: {}".format(_one_line(entry)))
        if self.finding:
            lines.append("- finding: {}".format(_one_line(self.finding)))
        if self.follow_up:
            lines.append("- follow-up proposed (not executed): {}".format(
                _one_line(self.follow_up)))
        return lines


def _one_line(text, limit=200):
    """`text` collapsed to a single bounded line, for reports and records."""
    return " ".join(str(text or "").split())[:limit]


def contract():
    """The receipt instruction, in the exact shape `parse_receipt` reads.

    Built here rather than written into the prompt by hand so the wording a
    worker reads and the parser that reads its answer have one source.
    """
    meanings = [
        (DONE, "the mission is finished and its verification passed"),
        (NEEDS_COMMANDER,
         "the mission needs a product, syntax or semantic decision only "
         "the commander can make"),
        (MISSING_PREREQUISITE,
         "it cannot be built yet because something it depends on does not "
         "exist"),
        (FAILED, "the attempt itself went wrong"),
    ]
    described = "\n".join("- {}: {}".format(name, meaning)
                          for name, meaning in meanings)
    return (
        "End your final message with the marker line below, then one JSON\n"
        "object, and then stop. Write no other machine-readable block.\n"
        "\n"
        + MARKER + "\n"
        + EXAMPLE + "\n"
        "\n"
        "Fields:\n"
        "- status, one of " + " | ".join(STATUSES) + "\n"
        + described + "\n"
        "- summary: one or two sentences on what actually happened.\n"
        "- changed_files: repo-relative paths you edited.\n"
        "- verification: what you ran and what it said.\n"
        "- area: the subsystem this touched, so the next mission in the same\n"
        "  area can be given this receipt instead of the whole history.\n"
        "- finding: a durable fact worth NOTES.md, or omit it.\n"
        "- follow_up: a proposed next mission, or omit it. A proposal is\n"
        "  recorded; it is never executed automatically.\n"
    )


def _marker_payload(text):
    """The text after the LAST marker line, or None when there is none.

    The last one wins so a worker that restates the contract before
    complying still has its answer read, and a marker quoted in prose
    earlier in the message cannot shadow the real one.
    """
    lines = (text or "").splitlines()
    index = None
    for position, line in enumerate(lines):
        if line.strip() == MARKER:
            index = position
    if index is None:
        return None
    return "\n".join(lines[index + 1:]).strip()


def _first_object(payload):
    """The first JSON object in `payload`, tolerating trailing prose."""
    if not payload:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(payload)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _text(value, limit):
    """A stripped, bounded string, or None for anything that is not one."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned[:limit] if cleaned else None


def _entries(value, limit=LIST_LIMIT):
    """A bounded list of short strings; anything unreadable is dropped."""
    if not isinstance(value, list):
        return []
    kept = []
    for entry in value:
        item = _text(entry, ENTRY_LIMIT)
        if item is not None:
            kept.append(item)
        if len(kept) >= limit:
            break
    return kept


def parse_receipt(text):
    """The `Receipt` in a worker's final message, or None.

    None is a first-class answer, not an error: no marker, unparseable JSON,
    a non-object, an unknown status, or a missing summary all mean the same
    thing to the supervisor — this worker did not report — and each of them
    must be handled without spending another request.
    """
    data = _first_object(_marker_payload(text))
    if data is None:
        return None
    status = _text(data.get("status"), 40)
    if status not in STATUSES:
        return None
    summary = _text(data.get("summary"), SUMMARY_LIMIT)
    if summary is None:
        return None
    return Receipt(
        status=status,
        summary=summary,
        changed_files=_entries(data.get("changed_files")),
        verification=_entries(data.get("verification")),
        area=_text(data.get("area"), AREA_LIMIT),
        finding=_text(data.get("finding"), FINDING_LIMIT),
        follow_up=_text(data.get("follow_up"), FOLLOW_UP_LIMIT),
    )
