"""Renders the semantic model as a native tkinter window.

This is an adapter/backend experiment: it consumes the SAME Model that
the HTML backend consumes and opens a real OS window. It does NOT add
any new language concepts. Rendering decisions (colors, row vs stack
layout, where a bar sits) come from the dictionary's machine-readable
hints -- the same class of backend detail as the `element` field.
"""

import re
import tkinter as tk

from . import dictionary

# Local kind -> visual color defaults. The dictionary may annotate kinds
# later; these are the renderer's own choices (backend detail, not language).
KIND_COLORS = {
    "page":        "#ffffff",
    "header":      "#2d2d2d",
    "logo":        None,       # inherits parent
    "navigation":  None,       # inherits parent
    "container":   "#f0f0f0",
    "banner":      "#1a73e8",
    "card":        "#ffffff",
    "card-group":  None,
    "footer":      "#333333",
    "viewport":    None,
}

KIND_TEXT_COLORS = {
    "page":        "#000000",
    "header":      "#ffffff",
    "logo":        "#ffffff",
    "navigation":  "#cccccc",
    "container":   "#333333",
    "banner":      "#ffffff",
    "card":        "#333333",
    "card-group":  "#333333",
    "footer":      "#ffffff",
    "viewport":    "#000000",
}


def _dictionary_entry(kind):
    return dictionary.find(kind)


def _children_of(model, parent_id):
    """Return entity ids whose parent is parent_id, in declaration order."""
    return [
        child for child, parent in model.relationships.items()
        if parent == parent_id
    ]


def _kind_of(model, entity_id):
    return model.entities[entity_id].kind


# tkinter wants pixels; the dictionary writes CSS. 1rem reads as 16px.
_REM_PX = 16

# (pady, padx) for a kind that declares no `padding` hint -- the literals the
# logo branch packed with before the hints were read (padx=16, pady=8).
_FALLBACK_PADDING = (8, 16)


def _hint_lengths(kind, name):
    """Every pixel length the kind's named hint word carries, in order.

    Reads `style.properties.<name>.values[<defaults hint word>]` and pulls
    the lengths out of the CSS value: `1.25rem` is one, `3.5rem 1.5rem` is
    two, `none` is none. An unknown kind, a kind that declares no such hint,
    or a hint word the `values` table does not know gives an empty list --
    the dictionary advises, and we only read what it has evidence for.

    Where a hint mixes a length with something else (`border` is
    `1px solid #e2e8f0`), only the length is kept.
    """
    entry = _dictionary_entry(kind)
    if not isinstance(entry, dict):
        return []
    defaults = entry.get("defaults")
    style = entry.get("style")
    if not isinstance(defaults, dict) or not isinstance(style, dict):
        return []
    word = defaults.get(name)
    properties = style.get("properties")
    if not isinstance(word, str) or not isinstance(properties, dict):
        return []
    spec = properties.get(name)
    if not isinstance(spec, dict):
        return []
    values = spec.get("values")
    if not isinstance(values, dict):
        return []
    raw = values.get(word)
    if not isinstance(raw, str):
        return []

    lengths = []
    for token in raw.split():
        match = re.fullmatch(r"(\d+(?:\.\d+)?)(rem|px)?", token)
        if match is None:
            continue
        number = float(match.group(1))
        if match.group(2) == "rem":
            number *= _REM_PX
        lengths.append(int(round(number)))
    return lengths


def _hint_px(kind, name):
    """The kind's named hint as one integer pixel value, or None.

    The leading length of the hint word's CSS value: `comfortable` ->
    `1.25rem` -> 20. None when the kind or the hint is absent.
    """
    lengths = _hint_lengths(kind, name)
    return lengths[0] if lengths else None


def _padding_of(model, entity_id):
    """The (pady, padx) an entity's kind asks for, in pixels.

    Comes from the kind's `padding` hint when the dictionary declares one
    (`banner` declares `generous` -> `3.5rem 1.5rem` -> vertical 56,
    horizontal 24). A CSS shorthand with a single length pads all four
    sides, so that one length serves both axes. A kind with no `padding`
    hint (`logo`, `navigation`) keeps the renderer's earlier literals.
    """
    lengths = _hint_lengths(_kind_of(model, entity_id), "padding")
    if not lengths:
        return _FALLBACK_PADDING
    pady = lengths[0]
    padx = lengths[1] if len(lengths) > 1 else pady
    return (pady, padx)


def _layout_of(model, entity_id):
    """How an entity's children are arranged: 'row' or 'stack' (default)."""
    entry = _dictionary_entry(_kind_of(model, entity_id))
    if entry:
        return entry.get("layout", "stack")
    return "stack"


def _position_of(model, entity_id):
    """Where a bar sits in its parent: 'bottom' or 'flow' (default)."""
    entry = _dictionary_entry(_kind_of(model, entity_id))
    if entry:
        return entry.get("position", "flow")
    return "flow"


def _bg(model, entity_id):
    kind = _kind_of(model, entity_id)
    color = KIND_COLORS.get(kind, "#dddddd")
    if color is None:
        # inherit from parent -- walk up
        parent = model.relationships.get(entity_id)
        if parent is not None:
            return _bg(model, parent)
        return "#dddddd"
    return color


def _fg(model, entity_id):
    kind = _kind_of(model, entity_id)
    return KIND_TEXT_COLORS.get(kind, "#000000")


def _is_leaf(model, entity_id):
    return len(_children_of(model, entity_id)) == 0


def _has_text(model, entity_id):
    return (entity_id, "text") in model.properties


def render(model, title_override=None):
    """Build and display a tkinter window from the semantic model.

    Returns the root window so callers (tests) can inspect or destroy it
    without running mainloop.
    """
    pages = [e for e in model.entities.values() if e.kind == "page"]
    if len(pages) != 1:
        raise VisualError(
            f"the visual backend needs exactly one entity of kind 'page' "
            f"(found {len(pages)})"
        )
    page = pages[0]
    window_title = title_override or model.properties.get((page.id, "title"), "Ine")

    root = tk.Tk()
    root.title(str(window_title))
    root.geometry("800x600")
    root.configure(bg="#cccccc")

    _render_entity(root, model, page.id, side="top")
    return root


def _render_entity(parent_widget, model, entity_id, side="top"):
    """Recursively render an entity and its children into parent_widget.

    `side` is how this entity's own frame is placed inside its parent:
    'top' (in-flow), 'bottom' (pinned to the bottom edge), or 'left'
    (one slot in a row layout).
    """
    children_ids = _children_of(model, entity_id)
    bg = _bg(model, entity_id)
    fg = _fg(model, entity_id)
    text = model.properties.get((entity_id, "text"))
    title = model.properties.get((entity_id, "title"))
    kind = _kind_of(model, entity_id)
    pady, padx = _padding_of(model, entity_id)

    if kind == "page":
        frame = tk.Frame(parent_widget, bg=bg)
        frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        if text:
            tk.Label(frame, text=str(text), bg=bg, fg=fg,
                     font=("Arial", 18, "bold")).pack(pady=(12, 4))
        _pack_children(frame, model, entity_id, "stack")
        return frame

    if kind == "header":
        frame = tk.Frame(parent_widget, bg=bg, height=60)
        if side == "bottom":
            frame.pack(side=tk.BOTTOM, fill=tk.X)
        else:
            frame.pack(side=tk.TOP, fill=tk.X)
        frame.pack_propagate(False)
        for child_id in children_ids:
            _render_entity(frame, model, child_id)
        return frame

    if kind == "logo":
        tk.Label(parent_widget, text=str(text or ""), bg=bg, fg=fg,
                 font=("Arial", 14, "bold")).pack(
            side=tk.LEFT, padx=padx, pady=pady)
        return None

    if kind == "navigation":
        frame = tk.Frame(parent_widget, bg=bg)
        frame.pack(side=tk.RIGHT, padx=padx)
        if text:
            tk.Label(frame, text=str(text), bg=bg, fg=fg,
                     font=("Arial", 11)).pack(side=tk.LEFT, padx=8)
        for child_id in children_ids:
            _render_entity(frame, model, child_id)
        return frame

    if kind == "banner":
        frame = tk.Frame(parent_widget, bg=bg)
        if side == "bottom":
            frame.pack(side=tk.BOTTOM, fill=tk.X)
        else:
            frame.pack(side=tk.TOP, fill=tk.X)
        if text:
            tk.Label(frame, text=str(text), bg=bg, fg=fg,
                     font=("Arial", 22, "bold")).pack(pady=pady, padx=padx)
        for child_id in children_ids:
            _render_entity(frame, model, child_id)
        return frame

    if kind == "card":
        frame = tk.Frame(parent_widget, bg=bg, highlightthickness=1,
                         highlightbackground="#dddddd")
        if side == "bottom":
            frame.pack(side=tk.BOTTOM, fill=tk.X)
        elif side == "left":
            frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        else:
            frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=6)
        if title:
            tk.Label(frame, text=str(title), bg=bg, fg=fg,
                     font=("Arial", 13, "bold"), anchor="w").pack(
                fill=tk.X, padx=10, pady=(10, 2))
        if text:
            tk.Label(frame, text=str(text), bg=bg, fg=fg,
                     font=("Arial", 10), justify="left", wraplength=200,
                     anchor="w").pack(fill=tk.X, padx=10, pady=(2, 10))
        for child_id in children_ids:
            _render_entity(frame, model, child_id)
        return frame

    if kind == "container":
        frame = tk.Frame(parent_widget, bg=bg)
        if side == "bottom":
            frame.pack(side=tk.BOTTOM, fill=tk.X)
        else:
            frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        if text:
            tk.Label(frame, text=str(text), bg=bg, fg=fg,
                     font=("Arial", 12)).pack(pady=8)
        _pack_children(frame, model, entity_id, _layout_of(model, entity_id))
        return frame

    # Generic fallback (covers card-group, viewport, and future kinds)
    frame = tk.Frame(parent_widget, bg=bg)
    if side == "bottom":
        frame.pack(side=tk.BOTTOM, fill=tk.X)
    else:
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=4)
    if title:
        tk.Label(frame, text=str(title), bg=bg, fg=fg,
                 font=("Arial", 13, "bold"), anchor="w").pack(
            fill=tk.X, padx=10, pady=(10, 2))
    if text:
        tk.Label(frame, text=str(text), bg=bg, fg=fg,
                 font=("Arial", 11)).pack(pady=8)
    _pack_children(frame, model, entity_id, _layout_of(model, entity_id))
    return frame


def _pack_children(frame, model, entity_id, layout):
    """Place an entity's children: side-by-side (row) or stacked."""
    children = _children_of(model, entity_id)
    if layout == "row":
        for child_id in children:
            _render_entity(frame, model, child_id, side="left")
        return
    for child_id in children:
        if _position_of(model, child_id) == "bottom":
            _render_entity(frame, model, child_id, side="bottom")
        else:
            _render_entity(frame, model, child_id, side="top")


def show(model, title_override=None):
    """Build the window and run mainloop (blocking)."""
    root = render(model, title_override)
    root.mainloop()


class VisualError(Exception):
    def __init__(self, message, line=None):
        super().__init__(message)
        self.message = message
        self.line = line