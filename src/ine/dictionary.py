"""Deterministic vocabulary and discovery layer for Ine.

The dictionary maps human-friendly concepts (page, header, card, ...) to
semantic meaning and implementation hints. This module is the single
reader of dictionary/*.json. It answers discovery questions from that
data alone — no AI, no hardcoded lists:

    what can follow `make`?                       (kinds)
    what property values can a kind accept?       (properties)
    what value shape does a property expect?      (value_shape)
    which children belong inside a kind?          (structural members)
    what is valid in the current program?

The dictionary keeps three distinct categories separate:

- kinds            — entities a program can declare with `make`
- properties       — `<name> <property> <value>` statements; `title` and
                     `text` are universal content properties available on
                     every declared kind, the rest are kind-specific hints
- structural members — child kinds that belong inside this kind, stated
                     in Ine's own direction: `<child> inside <parent>`

Containment is discoverable in both directions: `members` lists the
children of a kind, and `parents` reverses `contains` to report the kinds
a child can live inside.

Everything is derived from the JSON data. A kind with no dictionary
entry simply has no suggestions (the dictionary is advisory, never a
validator — see examples/alice/alice.ine).

## dictionary/*.json schema

Each file declares one kind in JSON:

- `term`         — unique identifier for the kind (the file's key).
- `kind`         — category the concept belongs to (container, bar,
                   surface, ambient, ...); informational only.
- `element`      — HTML element tag the backend renders it with.
- `meaning`      — human-readable description (shown as completion detail).
- `defaults`     — property hints and the `contains` list; each value is a
                   hint string (`"compact"`) shown in completions, except
                   `contains`, which lists structural child kinds.
- `properties`   — typed property declarations: property -> `"text"` (a
                   quoted string) or `"length"` (a measurement), or a list
                   of allowed choices (a `"choice"` value). Drives
                   `value_shape()` / `value_hint()`.
- `provided-by`  — present on ambient entries (viewport): the kind is
                   supplied by the host, so it is excluded from `makeable()`.
- `universal`    — marks the universal-properties pseudo-entry: its
                   `properties` block defines `title`/`text`, available on
                   every declared kind; never in `makeable()`.
"""

import json
import os
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .semantic import Model

DICTIONARY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dictionary"
)


@dataclass(frozen=True)
class Suggestion:
    """One deterministic suggestion: a word plus why it belongs."""

    text: str
    source: str  # "kind" | "property" | "concept"
    note: str = ""


@dataclass(frozen=True)
class ValueShape:
    """The declared shape of a property's value.

    `type` is the machine-readable value kind: "text" for quoted string
    content (title/text), "choice" for a known set of bare-word options,
    other declared kinds (e.g. "length"), or "unknown" when the
    dictionary does not say. `choices` carries the allowed options for a
    "choice" shape.
    """

    type: str = "unknown"
    choices: tuple = ()


def _load() -> dict[str, dict]:
    found = {}
    if not os.path.isdir(DICTIONARY_DIR):
        return found
    for name in sorted(os.listdir(DICTIONARY_DIR)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(DICTIONARY_DIR, name)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                entry = json.load(handle)
        except OSError as exc:
            warnings.warn(
                f"dictionary: skipping {name}: cannot read file ({exc})"
            )
            continue
        except ValueError:
            warnings.warn(
                f"dictionary: skipping {name}: invalid JSON"
            )
            continue
        if not isinstance(entry, dict):
            warnings.warn(
                f"dictionary: skipping {name}: not a JSON object"
            )
            continue
        if not entry.get("term"):
            warnings.warn(
                f"dictionary: skipping {name}: missing 'term'"
            )
            continue
        found[entry["term"]] = entry
    return found


_ENTRIES: dict[str, dict] | None = None


def entries() -> dict[str, dict]:
    """All dictionary entries, keyed by term (loaded once)."""
    global _ENTRIES
    if _ENTRIES is None:
        _ENTRIES = _load()
    return _ENTRIES


def find(kind: str) -> dict | None:
    """The dictionary entry for a kind, or None if it is not declared."""
    return entries().get(kind)


def _is_regular_kind(entry: dict | None) -> bool:
    """True for kinds a program can name with `make` (not ambient, not the
    universal-properties pseudo-entry)."""
    return (
        entry is not None
        and "provided-by" not in entry
        and not entry.get("universal")
    )


def _universal_defaults() -> dict:
    """The `defaults` block of the universal-properties entry, if any."""
    entry = entries().get("universal")
    if not isinstance(entry, dict):
        return {}
    defaults = entry.get("defaults")
    if not isinstance(defaults, dict):
        return {}
    return defaults


def makeable() -> list[str]:
    """Kinds a program can declare with `make` (ambient and pseudo-entries
    excluded)."""
    return sorted(
        term for term, entry in entries().items() if _is_regular_kind(entry)
    )


def properties_for(kind: str) -> list[str]:
    """Property names a kind can be given: its declared property hints plus
    the universal `title`/`text` content properties."""
    entry = find(kind)
    if entry is None:
        return []
    names = set()
    defaults = entry.get("defaults")
    if isinstance(defaults, dict):
        names.update(name for name in defaults if name != "contains")
    declared = entry.get("properties")
    if isinstance(declared, dict):
        names.update(declared.keys())
    if _is_regular_kind(entry):
        names.update(_universal_defaults().keys())
    return sorted(names)


def value_hint(kind: str, property: str) -> str | None:
    """What a property expects, or None if the dictionary does not say."""
    entry = find(kind)
    if entry is None:
        return None
    declared = entry.get("properties")
    if isinstance(declared, dict) and property in declared:
        return "a " + _label(declared[property])
    defaults = entry.get("defaults")
    if isinstance(defaults, dict) and property in defaults:
        return _label(defaults[property])
    if _is_regular_kind(entry) and property in _universal_defaults():
        return _label(_universal_defaults()[property])
    return None


def _shape_from(raw) -> ValueShape:
    """Normalize one raw `properties`-block value into a ValueShape.

    A plain string names a value kind ("text", "length", ...); a list of
    strings declares the allowed bare-word options of a "choice". Anything
    else yields the "unknown" shape.
    """
    if isinstance(raw, str) and raw.strip():
        # Only recognize standard value kinds, not arbitrary strings
        if raw in ("text", "length"):
            return ValueShape(raw)
        return ValueShape()
    if isinstance(raw, list) and raw and all(isinstance(v, str) for v in raw):
        return ValueShape("choice", tuple(raw))
    return ValueShape()


def value_shape(kind: str, prop: str) -> ValueShape:
    """The value shape a property accepts on a kind, or ValueShape()
    (type "unknown") when the dictionary does not say.

    Consults the kind's own `properties` block first, then the universal
    entry's `properties` block (the content properties available on every
    declared kind). Read from metadata only — never inferred or invented.
    """
    entry = find(kind)
    if entry is not None:
        declared = entry.get("properties")
        if isinstance(declared, dict):
            shape = _shape_from(declared.get(prop))
            if shape.type != "unknown":
                return shape
    if _is_regular_kind(entry):
        universal = entries().get("universal") or {}
        declared = universal.get("properties")
        if isinstance(declared, dict):
            shape = _shape_from(declared.get(prop))
            if shape.type != "unknown":
                return shape
    return ValueShape()


def members(kind: str) -> list[str]:
    """Linguistic children a kind's entry says belong inside it (structural
    members; e.g. header -> logo, navigation)."""
    entry = find(kind)
    if entry is None:
        return []
    defaults = entry.get("defaults")
    if not isinstance(defaults, dict):
        return []
    concepts = defaults.get("contains")
    if not isinstance(concepts, list):
        return []
    return sorted(concepts)


def parents(kind: str) -> list[str]:
    """Kinds a child of this kind can live inside — the reverse of
    `members`. Derived from `contains` data alone (e.g. card-group ->
    container, section -> page). Returns [] for undeclared kinds and for
    kinds nothing declares as a child."""
    if find(kind) is None:
        return []
    return sorted(
        term for term, entry in entries().items()
        if _is_regular_kind(entry) and kind in members(term)
    )


def suggest(kind: str | None = None) -> list[Suggestion]:
    """What could sensibly follow `make [kind]` right now.

    With no kind: every kind a program can declare. With a kind: the
    properties it accepts and the structural children that belong inside
    it (stated as `<child> inside <kind>`).
    """
    if kind is None:
        return [
            Suggestion(term, "kind", entry.get("meaning", ""))
            for term in makeable() for entry in [find(term)]
        ]
    entry = find(kind)
    if entry is None:
        return []
    items = [Suggestion(name, "property", value_hint(kind, name))
             for name in properties_for(kind)]
    taken = {item.text for item in items}
    items += [Suggestion(name, "concept", f"{name} inside {kind}")
              for name in members(kind) if name not in taken]
    return items


def for_model(model: "Model") -> list[Suggestion]:
    """Suggestions valid in the context of a parsed program.

    For every declared entity, its entity-prefixed property statements.
    Entities whose kind the dictionary does not know contribute nothing.
    """
    results = []
    for entity_id in sorted(model.entities):
        kind = model.entities[entity_id].kind
        for item in suggest(kind):
            if item.source == "property":
                results.append(
                    Suggestion(f"{entity_id} {item.text}", "property", item.note)
                )
            elif item.source == "concept":
                results.append(
                    Suggestion(f"make {item.text}", "concept", item.note)
                )
            else:
                results.append(Suggestion(item.text, item.source, item.note))
    return results


def _label(value) -> str:
    if isinstance(value, list):
        return "one of " + ", ".join(str(v) for v in value)
    return str(value)