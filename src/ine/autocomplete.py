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
        "diagnostics": [{"line", "column", "message"}, ...]}

Diagnostics are parse-level only (lex + parse), never semantic, so the
dictionary never red-underlines — advisory stays advisory. Lines and
columns are 0-based, matching the completion protocol; `column` is
omitted when the parser cannot know one (syntax errors point at a line).

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
from ine.lexer import LexError, lex
from ine.parser import SyntaxError, parse


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
        shape = dictionary.value_shape(kind, ctx["prop"])
        if shape.type == "text":
            hint = dictionary.value_hint(kind, ctx["prop"]) or "quoted text"
            return [
                {
                    "label": '""',
                    "insert": '""',
                    "detail": hint,
                    "type": "value",
                }
            ]
        if shape.type == "number":
            hint = dictionary.value_hint(kind, ctx["prop"]) or "a number"
            return [
                {
                    "label": "123",
                    "insert": "123",
                    "detail": hint,
                    "type": "value",
                }
            ]
        if shape.type == "choice":
            hint = dictionary.value_hint(kind, ctx["prop"]) or "one of the listed values"
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


def complete(payload: dict) -> dict:
    """Answer one editor query: a validation or a completion query."""
    buffer = payload.get("buffer", "")
    if payload.get("validate"):
        result = {"validate": True, "diagnostics": _validate(buffer)}
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