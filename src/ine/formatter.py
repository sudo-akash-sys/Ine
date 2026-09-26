"""Re-emits .ine source in its one canonical form.

The grammar is four constructs wide, so formatting is a parse-to-text
re-emit and nothing else: lex the source, parse it, write the statements
back out. No line of the input is matched, trimmed or reused, which is
what makes the result deterministic — the same program formats to the
same bytes however it was typed, and formatting a formatted file changes
nothing.

Canonical form:

    make brand logo
        brand text "Northwind"
        brand inside header

    make badge card
        badge title "New"

    say page title

One statement per line. The statements about one subject stay together
in a group, with a blank line between groups; the body of a `make` — the
properties it carries and the `inside` line that places it — is indented
4 spaces under it. The file ends with exactly one newline, and no line
ends in a space.

Two consequences of re-emitting rather than rewriting, both deliberate.
`make 3 card` is written out as the three entities it declares: the
parser expands it, so the count is not in the tree either. And a file
that carries a comment is handed back untouched: the lexer drops
comments, no statement holds one, and re-emitting would therefore delete
the note the user wrote. The editor formats on save, so that refusal is
the difference between a formatter and a silent eraser.

Formatting never destroys a file. Source that does not lex and parse
comes back unchanged, and so does any emission that does not read back
as the same statements — that second check is cheap, and it makes
"formatting cannot change meaning" a property of the code instead of a
hope.
"""

import math
from dataclasses import fields, is_dataclass, replace
from decimal import Decimal

from .lexer import LexError, lex
from .parser import (
    GroupStatement,
    InsideStatement,
    MakeStatement,
    PropertyRef,
    PropertyStatement,
    SayStatement,
    SyntaxError,
    parse,
)

# The body of a `make` sits one step in from it. Four spaces, like every
# other Ine artifact (the examples, the dictionary JSON, the editor's own
# snippets) and unlike a tab, which the lexer accepts but no reader can
# see the width of.
INDENT = "    "

# What the parse pipeline raises on source it cannot read. `ValueError` is
# the odd one: a number token is any run of digits and letters, so
# `1.2.3` lexes as one and only fails when the parser converts it.
UNREADABLE = (LexError, SyntaxError, ValueError)


def format_program(source: str) -> str:
    """`source` in canonical form, or `source` untouched.

    Deterministic: the output depends on the parsed statements alone, so
    formatting twice is formatting once. Meaning-preserving: the input is
    left alone unless the canonical text parses back to the very same
    statements. A file that does not parse is never reformatted — a
    half-typed buffer that the editor formats on save stays exactly as
    the user left it.
    """
    try:
        statements = parse(lex(source))
    except UNREADABLE:
        return source
    if not statements:
        # An empty file, or one that is all comments and blank lines.
        # There is no canonical layout for nothing; writing "" over it
        # would delete what is there, so hand it back.
        return source
    if _commented(source):
        # A comment is text the statement tree has no place for, so the
        # canonical form cannot hold it and re-emitting would drop it.
        # The file is handed back whole rather than quietly losing the
        # note the user wrote.
        return source
    try:
        text = _emit(statements)
        if _bare(parse(lex(text))) != _bare(statements):
            return source
    except UNREADABLE:
        return source
    return text


def _bare(statements) -> list:
    """The statements with their line numbers cleared, at every depth.

    A statement records the line it was typed on, and canonical form
    moves statements to other lines on purpose: that is what the blank
    line between groups and the indent under a `make` do. Comparing the
    field would therefore read every successful reflow as a change of
    meaning, and the formatter would refuse the very layouts it exists to
    produce. Line numbers are not meaning, so they are dropped before the
    comparison — and at every depth, because `say card.title` carries its
    line inside a PropertyRef rather than on the statement.
    """
    if is_dataclass(statements) and not isinstance(statements, type):
        return replace(
            statements,
            **{
                field.name: (
                    0
                    if field.name == "line"
                    else _bare(getattr(statements, field.name))
                )
                for field in fields(statements)
            },
        )
    if isinstance(statements, list):
        return [_bare(item) for item in statements]
    if isinstance(statements, tuple):
        return tuple(_bare(item) for item in statements)
    return statements


def _commented(source: str) -> bool:
    """True when `source` holds a `#` outside a string.

    A `#` inside a quoted string is text, not a comment, so the scan
    tracks the quotes it is between. It runs only on source that has
    already lexed, where every quote is closed and the last one cannot
    leave the scan inside a string it never exits.
    """
    in_string = False
    for character in source:
        if character == '"':
            in_string = not in_string
        elif character == "#" and not in_string:
            return True
    return False


def _emit(statements) -> str:
    """The canonical text of already-parsed statements."""
    blocks = []
    for group in _groups(statements):
        body = isinstance(group[0], MakeStatement)
        blocks.append(
            "\n".join(
                (INDENT if body and position else "") + _line(statement)
                for position, statement in enumerate(group)
            )
        )
    return "\n\n".join(blocks) + "\n"


def _groups(statements) -> list[list]:
    """The statements split into groups: one run per subject, in order.

    A group is every statement in a row about the same subject — the
    `make` line, the properties it carries, and the `inside` line that
    places it; or a run of lines about one card. Read back, a group is a
    paragraph, and the blank line between them is the only section
    marker the format has.
    """
    groups = []
    for statement in statements:
        subject = _subject(statement)
        if groups and subject is not None and groups[-1][0] == subject:
            groups[-1][1].append(statement)
        else:
            groups.append((subject, [statement]))
    return [members for _, members in groups]


def _subject(statement):
    """The name a statement is about, or None when it is about nothing.

    A `say` prints and declares nothing, so it never joins a group: it
    stands on its own line, and two `say` lines are two statements rather
    than one paragraph.
    """
    if isinstance(statement, (MakeStatement, PropertyStatement)):
        return statement.target
    if isinstance(statement, InsideStatement):
        return statement.child
    if isinstance(statement, GroupStatement):
        return statement.name
    return None


def _line(statement) -> str:
    """One statement as one line, without indentation."""
    if isinstance(statement, MakeStatement):
        # `make card` declares card as its own kind; `make f1 card` names
        # the kind after the name. The short form is written back for the
        # first, so a file that never mentioned a kind twice grows no
        # second word.
        if statement.kind == statement.target:
            return f"make {statement.target}"
        return f"make {statement.target} {statement.kind}"
    if isinstance(statement, PropertyStatement):
        return f"{statement.target} {statement.name} {_value(statement.value)}"
    if isinstance(statement, SayStatement):
        return f"say {_value(statement.value)}"
    if isinstance(statement, InsideStatement):
        return f"{statement.child} inside {statement.parent}"
    if isinstance(statement, GroupStatement):
        return f"group {statement.name} = {' '.join(statement.members)}"
    # A construct the parser learned after this module did. Refusing beats
    # guessing: `format_program` hands the source back rather than drop a
    # statement it cannot write.
    raise ValueError(f"cannot format {statement!r}")


def _value(value) -> str:
    """One parsed value as source text."""
    if isinstance(value, PropertyRef):
        return f"{value.target} {value.name}"
    if isinstance(value, str):
        # The lexer reads a string to its closing quote, so a parsed
        # string never contains one and never spans a line: quoting it
        # back is enough.
        return f'"{value}"'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _decimal(value)
    raise ValueError(f"cannot format the value {value!r}")


def _decimal(value: float) -> str:
    """A float as source text that reads back as the same number.

    `repr` is the shortest text that round-trips, but it may reach for an
    exponent, and an Ine number token continues over letters, `.` and `_`
    only — no sign — so `1e+20` and `1e-05` would not lex back as one
    number. The exponent is spelled out in positional digits instead, and
    a float keeps a `.` so it reads back as a float rather than as the
    whole number beside it.
    """
    if not math.isfinite(value):
        # No number token spells an infinity or a NaN, so there is
        # nothing that reads back as this value; the round-trip check in
        # `format_program` leaves the source alone.
        return repr(value)
    text = format(Decimal(repr(value)), "f")
    return text if "." in text else text + ".0"
