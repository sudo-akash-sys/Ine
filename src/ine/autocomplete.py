"""Editor completion engine for Ine.

This module is the query backend behind the VS Code autocomplete prototype
(editor/vscode-ine). It consumes the existing `ine.dictionary` module as the
single source of truth; it only decides which dictionary query a cursor
position maps to:

    make <..>           -> dictionary.makeable()
    <kind> <..>         -> dictionary.suggest(kind)   (properties + members)
    <kind> <property>   -> dictionary.value_shape(kind, property)  (value)
    <child> inside <..> -> dictionary.parents(child_kind)  (reverse containment)
    validate            -> lex + parse the buffer          (diagnostics)
    hover               -> the meaning of the word under the cursor
    format              -> lex + parse, re-emit            (canonical text)

No AI, synonyms, fuzzy matching, or hardcoded vocabulary.

Protocol: reads JSON objects from stdin, one per line, and prints one
JSON object per line on stdout. One request

    {"buffer": <full program text>,
     "line":   <0-based line index>,
     "column": <character offset into the line>,
     "id":     <optional request id, echoed back>}

produces one response:

    {"id": ..., "line": ..., "column": ..., "context": ...,
     "items": [{"label", "insert", "detail", "type", "snippet"?}, ...]}

    type in "kind" | "property" | "concept" | "parent" | "value"

A kind item carries an optional `snippet`: the starting-point body built
from the dictionary entry (declared members as `make`/`inside` lines,
style/default properties as `<kind> <property> "<default>"` statements)
that the editor inserts with cursor position in the first default. It is
editable starting material, never a rule — the editor substitutes
`insert` when `snippet` is absent.

A validation query is distinguished by the `validate` key instead:

    {"validate": true, "buffer": <full program text>, "id"?}

    -> {"validate": true,
        "diagnostics": [{"line", "column", "message"}, ...],
        "advisory":    [{"line", "message"}, ...]}

Diagnostics are parse-level only (lex + parse), never semantic, so the
dictionary never red-underlines — advisory stays advisory. Lines and
columns are 0-based, matching the completion protocol; `column` is
omitted when the parser cannot know one (syntax errors point at a line).

`advisory` is a second, separate list in the same response: the one
semantic finding `analyze` raises (undeclared entity, double parent,
containment cycle), 0-based, no column — semantics has no column to
point at. It rides beside `diagnostics` under its own key so a caller
can render it as a warning rather than an error, and it degrades to []
for any buffer that does not reach a semantic model.

A hover query asks about one cursor position:

    {"hover": true, "buffer": ..., "line": <0-based>, "column": <offset>, "id"?}

    -> {"hover": true, "label": <dictionary term>,
        "meaning": <the entry's `meaning`>, "items": [<completion item>, ...]}

A position that resolves to nothing — a blank, a comment, a string, a
value, or a word the dictionary does not know — answers
{"hover": true, "label": None, "items": []}. A bad position is never an
error.

A format query asks for the buffer back in canonical form:

    {"format": true, "buffer": <full program text>, "id"?}

    -> {"format": true, "text": <canonical text>}

`text` is the whole document, not a patch: the caller replaces the
buffer with it. It equals the buffer whenever the formatter has nothing
to say — source that does not lex and parse comes back untouched — so an
editor can format a half-typed file without losing it. This module only
carries the query; the rules live in `ine.formatter`.

The loop keeps running until stdin closes, so an editor can hold one
long-lived process and stream queries without paying Python startup per
keystroke. A single request is still answered one-for-one (stdin EOF
after it ends the process). Errors never break the loop: a bad line is
answered with {"error": ..., "items": []} and the next line is read.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ine import dictionary
from ine.formatter import format_program
from ine.lexer import LexError, lex
from ine.parser import SyntaxError, parse
from ine.semantic import SemanticError, analyze


def context(line: str, column: int) -> dict | None:
    """The completion context at `column` in `line`, or None.

    Returns one of:
        {"type": "kind"}                                          after `make `
        {"type": "properties", "kind_word", "partial"}            after one ident
        {"type": "value", "kind_word", "prop"}                    after `kind property `
        {"type": "inside", "child", "partial"}                    after `inside `
    """
    before = line[:column]
    if "#" in before:
        before = before.split("#", 1)[0]
    if not before.strip():
        return None
    trailing_space = before.endswith(" ")
    words = before.split()
    partial = ""
    if not trailing_space and words:
        partial = words.pop()
    if words == ["make"] or (words == [] and partial in ("make", "m", "ma", "mak")):
        return {"type": "kind"}
    if words and words[0] == "make" and len(words) > 1:
        return None
    if words and words[0] in ("group", "say"):
        return None
    if "inside" in words:
        index = words.index("inside")
        if index < 1:
            return None
        return {"type": "inside", "child": words[index - 1], "partial": partial}
    if len(words) == 2 and trailing_space:
        return {"type": "value", "kind_word": words[0], "prop": words[1]}
    if len(words) == 1:
        return {"type": "properties", "kind_word": words[0], "partial": partial}
    return None


def resolve_kind(buffer: str, name: str) -> str | None:
    """The dictionary kind behind a name in the buffer.

    Resolution (lenient, no full parse): the name is a declared dictionary
    kind; an entity declared by `make name [kind]`; a numbered entity from
    `make <count> <kind>`; or a group whose members share a kind.
    Returns None when the name maps to nothing.
    """
    if dictionary.find(name) is not None:
        return name
    for raw in buffer.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        made = re.match(r"make\s+(\S+)\s+(\S+)\s*$", line)
        if made:
            first, second = made.group(1), made.group(2)
            if first.isdigit():
                if re.fullmatch(re.escape(second) + r"-\d+", name):
                    return second
                continue
            if first == name:
                return second
            continue
        made = re.match(r"make\s+(\S+)\s*$", line)
        if made and made.group(1) == name and not name.isdigit():
            return name
        group = re.match(r"group\s+(\S+)\s*=\s*(.+)$", line)
        if group and group.group(1) == name:
            for member in group.group(2).split():
                kind = resolve_kind(buffer, member)
                if kind is not None:
                    return kind
    return None


def _known_shape(shape) -> str | None:
    """The protocol value for a dictionary ValueShape: its type when the
    dictionary declares one, else None."""
    return shape.type if shape.type != "unknown" else None


def kind_snippet(kind: str) -> str | None:
    """A starting-point snippet for accepting `make <kind>`, or None.

    Built from the dictionary entry alone, never from the grammar: each
    declared member becomes `make <member>` + `<member> inside <kind>`, and
    each property the entry defaults or styles becomes
    `<kind> <property> "<default>"`. A property's value resolves from the
    entry's `defaults` block, then a style spec's own `value` (none declare
    one today), else the property contributes nothing — defaults are shown,
    nothing is invented. The snippet returns None for a kind whose entry
    contributes nothing (e.g. `title`), so the bare `make <kind>` stands.
    """
    entry = dictionary.find(kind)
    if entry is None:
        return None
    defaults = entry.get("defaults")
    defaults = defaults if isinstance(defaults, dict) else {}
    style = entry.get("style")
    style = style if isinstance(style, dict) else {}
    style_props = style.get("properties")
    style_props = style_props if isinstance(style_props, dict) else {}

    tab = 1
    lines = []
    for name in sorted(set(defaults) | set(style_props)):
        if name == "contains":
            continue
        value = defaults.get(name)
        if value is None:
            spec = style_props.get(name)
            if isinstance(spec, dict):
                value = spec.get("value")
        if not isinstance(value, str):
            continue
        shape = dictionary.value_shape(kind, name)
        if shape.type == "choice" and shape.choices:
            options = ",".join(shape.choices)
            lines.append(f'{kind} {name} "${{{tab}|{options}|}}"')
        else:
            lines.append(f'{kind} {name} "${{{tab}:{value}}}"')
        tab += 1
    for member in dictionary.members(kind):
        lines.append(f"make {member}")
        lines.append(f"{member} inside {kind}")
    if not lines:
        return None
    return f"{kind}\n" + "\n".join(lines) + "\n$0"


def _suggestion_items(kind: str) -> list[dict]:
    """Completion items for an already-resolved kind: the properties it
    accepts and the structural children that belong inside it."""
    return [
        {
            "label": item.text,
            "insert": item.text,
            "detail": item.note,
            "type": item.source,
            "value_shape": (
                _known_shape(dictionary.value_shape(kind, item.text))
                if item.source == "property"
                else None
            ),
        }
        for item in dictionary.suggest(kind)
    ]


def _value_items(kind: str, prop: str) -> list[dict]:
    """Completion items for the value of `prop` on an already-resolved
    kind: what the dictionary says the property accepts, or [] when it
    does not say."""
    shape = dictionary.value_shape(kind, prop)
    if shape.type == "text":
        hint = dictionary.value_hint(kind, prop) or "quoted text"
        return [
            {
                "label": '""',
                "insert": '""',
                "detail": hint,
                "type": "value",
            }
        ]
    if shape.type == "number":
        hint = dictionary.value_hint(kind, prop) or "a number"
        return [
            {
                "label": "123",
                "insert": "123",
                "detail": hint,
                "type": "value",
            }
        ]
    if shape.type == "choice":
        hint = dictionary.value_hint(kind, prop) or "one of the listed values"
        return [
            {
                "label": option,
                "insert": option,
                "detail": hint,
                "type": "value",
            }
            for option in shape.choices
        ]
    return []


def _items(ctx, buffer) -> list[dict]:
    if ctx is None:
        return []
    if ctx["type"] == "kind":
        items = []
        for kind in dictionary.makeable():
            item = {
                "label": kind,
                "insert": kind,
                "detail": (dictionary.find(kind) or {}).get("meaning", ""),
                "type": "kind",
            }
            snippet = kind_snippet(kind)
            if snippet is not None:
                item["snippet"] = snippet
            items.append(item)
        return items
    if ctx["type"] == "properties":
        kind = resolve_kind(buffer, ctx["kind_word"])
        if kind is None:
            return []
        return _suggestion_items(kind)
    if ctx["type"] == "inside":
        kind = resolve_kind(buffer, ctx["child"])
        if kind is None:
            return []
        return [
            {
                "label": parent,
                "insert": parent,
                "detail": "{} inside {}".format(ctx["child"], parent),
                "type": "parent",
            }
            for parent in dictionary.parents(kind)
        ]
    if ctx["type"] == "value":
        kind = resolve_kind(buffer, ctx["kind_word"])
        if kind is None:
            return []
        return _value_items(kind, ctx["prop"])
    return []


def _validate(buffer: str) -> list[dict]:
    """Parse-level diagnostics for `buffer`: lex + parse only.

    Returns one entry per error:
        {"line", "column", "message"} for lex errors (0-based line/column)
        {"line", "message"}           for syntax errors (parser has no column)
    A buffer that lexes and parses cleanly returns [].
    """
    try:
        tokens = lex(buffer)
        parse(tokens)
    except LexError as error:
        return [
            {
                "line": error.line - 1,
                "column": error.column - 1,
                "message": error.message,
            }
        ]
    except SyntaxError as error:
        return [{"line": error.line - 1, "message": error.message}]
    return []


def _advisory(buffer: str) -> list[dict]:
    """Semantic findings for `buffer`, as advisory diagnostics.

    Runs the whole pipeline — lex, parse, analyze — and reports the one
    semantic error `analyze` raises (an undeclared entity, a double
    parent, a containment cycle) as {"line", "message"}, 0-based. No
    column: semantics points at a statement, not a character, exactly as
    a syntax error does above.

    `analyze` stops at the first error, so this is one finding or none.
    It never raises: a buffer that does not lex or parse has no semantic
    model to check, and any other failure degrades to [] rather than
    breaking the protocol loop. Findings are advisory by construction —
    the dictionary advises and never validates — so callers render them
    as warnings, never as errors.
    """
    try:
        analyze(parse(lex(buffer)))
    except SemanticError as error:
        line = error.line - 1 if isinstance(error.line, int) else 0
        return [{"line": line, "message": error.message}]
    except Exception:
        return []
    return []


def _format(buffer) -> str:
    """`buffer` in canonical form, or `buffer` unchanged.

    Guarded, because the caller writes this straight over the document:
    any other answer — a half-formatted text, an empty string — loses
    the user's file. A non-string is not a buffer, so it formats to the
    empty text it is, and a formatter that somehow fails hands back what
    it was given rather than an error the editor would have to interpret.
    """
    if not isinstance(buffer, str):
        return ""
    try:
        return format_program(buffer)
    except Exception:
        return buffer


def _strip_comment(line: str) -> str:
    """`line` up to its comment marker, ignoring a `#` inside a string."""
    in_string = False
    for index, ch in enumerate(line):
        if ch == '"':
            in_string = not in_string
        elif ch == "#" and not in_string:
            return line[:index]
    return line


def _line_words(text: str) -> list[dict]:
    """The word tokens of an already comment-stripped line, as
    {"text", "start", "end"} with 0-based columns. Quoted strings are not
    words — nothing in them is a kind or a property."""
    words = []
    index = 0
    while index < len(text):
        ch = text[index]
        if ch == '"':
            index += 1
            while index < len(text) and text[index] != '"':
                index += 1
            index += 1
            continue
        if ch.isspace():
            index += 1
            continue
        start = index
        while index < len(text) and not text[index].isspace() and text[index] != '"':
            index += 1
        words.append({"text": text[start:index], "start": start, "end": index})
    return words


def _word_at(words: list[dict], text: str, column: int) -> dict | None:
    """The word token the cursor sits on, or None.

    A cursor is on a word when it falls inside it, or — the editor's
    end-of-line case — when it sits one past the line's last character
    and that character ends a word. Whitespace is not a word: a cursor
    between two words, or in a line's trailing space, hovers nothing.
    """
    for word in words:
        if word["start"] <= column < word["end"]:
            return word
    if column >= len(text) and words and words[-1]["end"] == column:
        return words[-1]
    return None


def _segments(text: str) -> list[dict]:
    """The dot-separated segments of a word (`page.title`), with offsets."""
    segments = []
    start = 0
    for part in text.split("."):
        segments.append({"text": part, "start": start, "end": start + len(part)})
        start += len(part) + 1
    return segments


def _segment_at(segments: list[dict], offset: int) -> dict | None:
    """The segment of a dotted word at `offset`: the one containing it, else
    the last one (an offset at the very end of the word, where a cursor one
    past the final character sits)."""
    for segment in segments:
        if segment["start"] <= offset <= segment["end"]:
            return segment
    return segments[-1] if segments else None


def _kind_hover(kind: str | None) -> dict | None:
    """The hover for a resolved kind, or None when the dictionary does
    not know it (an entity whose kind was never declared)."""
    if kind is None:
        return None
    entry = dictionary.find(kind)
    if entry is None:
        return None
    return {
        "label": kind,
        "meaning": entry.get("meaning"),
        "items": _suggestion_items(kind),
    }


def _property_hover(kind: str, prop: str) -> dict | None:
    """The hover for a property of `kind`, or None when the dictionary
    says nothing about that property — nothing is invented."""
    meaning = dictionary.value_hint(kind, prop)
    if meaning is None:
        return None
    return {
        "label": prop,
        "meaning": meaning,
        "items": _value_items(kind, prop),
    }


def _hover(buffer: str, line_index: int, column: int) -> dict:
    """The dictionary meaning of the kind or property under the cursor.

    Reads the word under `column` and decides what it stands for from its
    place in the statement: a kind word (`make card`, the target of
    `card padding "x"`, either side of `inside`, a group member name), a
    property (`card padding`), or the property half of a `say card.title`
    reference. Anything else — a keyword, a value, a string, a blank, a
    word the dictionary does not know — answers with an empty hover.

    Never raises: a bad position is an empty hover, not an error.
    """
    empty = {"hover": True, "label": None, "items": []}
    try:
        lines = buffer.splitlines()
        if line_index < 0 or line_index >= len(lines):
            return empty
        text = _strip_comment(lines[line_index])
        words = _line_words(text)
        word = _word_at(words, text, column)
        if word is None:
            return empty
        index = words.index(word)
        before = [other["text"] for other in words[:index]]
        segments = _segments(word["text"])
        segment = _segment_at(segments, column - word["start"])
        if segment is None or not segment["text"]:
            return empty

        found = None
        if len(segments) > 1:
            # A dotted reference: `say card.title`.
            if segment is segments[0]:
                found = _kind_hover(resolve_kind(buffer, segment["text"]))
            else:
                kind = resolve_kind(buffer, segments[0]["text"])
                if kind is not None:
                    found = _property_hover(kind, segment["text"])
        elif before and before[0] == "make":
            # `make card` / `make 2 card`: every word but the count is a kind.
            if not word["text"].isdigit():
                found = _kind_hover(resolve_kind(buffer, word["text"]))
        elif "inside" in before:
            # Both sides of `inside` name a kind, the child and the parent.
            if word["text"] != "inside":
                found = _kind_hover(resolve_kind(buffer, word["text"]))
        elif before and before[0] == "group":
            if word["text"] not in ("group", "="):
                found = _kind_hover(resolve_kind(buffer, word["text"]))
        elif not before:
            # The first word of a statement is the entity (or bare kind) the
            # rest of the line talks about.
            if word["text"] not in ("make", "group", "say", "inside"):
                found = _kind_hover(resolve_kind(buffer, word["text"]))
        elif before[0] == "say":
            found = _kind_hover(resolve_kind(buffer, word["text"]))
        elif len(before) == 1:
            # `<kind> <property> ...`: the second word is a property of the
            # first. A third word is that property's value — not ours.
            kind = resolve_kind(buffer, before[0])
            if kind is not None:
                found = _property_hover(kind, word["text"])
    except Exception:
        return empty
    if found is None:
        return empty
    return {
        "hover": True,
        "label": found["label"],
        "meaning": found["meaning"],
        "items": found["items"],
    }


def complete(payload: dict) -> dict:
    """Answer one editor query: a validation, a hover, a format, or a
    completion."""
    buffer = payload.get("buffer", "")
    if payload.get("validate"):
        result = {
            "validate": True,
            "diagnostics": _validate(buffer),
            "advisory": _advisory(buffer),
        }
        if "id" in payload:
            result["id"] = payload["id"]
        return result
    if payload.get("format"):
        result = {"format": True, "text": _format(buffer)}
        if "id" in payload:
            result["id"] = payload["id"]
        return result
    if payload.get("hover"):
        result = _hover(buffer, payload.get("line", 0), payload.get("column", 0))
        if "id" in payload:
            result["id"] = payload["id"]
        return result
    line_index = payload.get("line", 0)
    column = payload.get("column", 0)
    lines = buffer.splitlines()
    if line_index < 0 or line_index >= len(lines):
        result = {"line": line_index, "column": column, "items": []}
    else:
        ctx = context(lines[line_index], column)
        result = {
            "line": line_index,
            "column": column,
            "context": ctx,
            "items": _items(ctx, buffer),
        }
    if "id" in payload:
        result["id"] = payload["id"]
    return result


def _respond(payload) -> dict:
    try:
        return complete(payload)
    except Exception as exc:  # keep the protocol alive for any input
        result = {"error": str(exc), "items": []}
        if isinstance(payload, dict) and "id" in payload:
            result["id"] = payload["id"]
        return result


def main() -> None:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            payload = None
        json.dump(_respond(payload), sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()