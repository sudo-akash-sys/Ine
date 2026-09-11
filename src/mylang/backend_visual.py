"""Renders the semantic model as a native tkinter window.

This is an adapter/backend experiment: it consumes the SAME Model that
the HTML backend consumes and opens a real OS window. It does NOT add
any new language concepts. Rendering decisions (colors, row vs stack
layout, where a bar sits) come from the dictionary's machine-readable
hints -- the same class of backend detail as the `element` field.
"""

import json
import os
import tkinter as tk

DICTIONARY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dictionary"
)

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
    path = os.path.join(DICTIONARY_DIR, kind + ".json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _children_of(model, parent_id):
    """Return entity ids whose parent is parent_id, in declaration order."""
    return [
        child for child, parent in model.relationships.items()
        if parent == parent_id
    ]


def _kind_of(model, entity_id):
    return model.entities[entity_id].kind


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
    window_title = title_override or model.properties.get((page.id, "title"), "MyLanguage")

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
            side=tk.LEFT, padx=16, pady=8)
        return None

    if kind == "navigation":
        frame = tk.Frame(parent_widget, bg=bg)
        frame.pack(side=tk.RIGHT, padx=16)
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
                     font=("Arial", 22, "bold")).pack(pady=48, padx=24)
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