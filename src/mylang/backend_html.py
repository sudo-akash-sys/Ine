"""Renders the semantic model as an HTML document."""

import html as _html
import json
import os

DICTIONARY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dictionary"
)
DEFAULT_ELEMENT = "div"


class BackendError(Exception):
    def __init__(self, message, line=None):
        super().__init__(message)
        self.message = message
        self.line = line


def _read_entry(kind):
    path = os.path.join(DICTIONARY_DIR, kind + ".json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _element_for_kind(kind):
    entry = _read_entry(kind)
    if entry is None:
        return None
    return entry.get("element", DEFAULT_ELEMENT)


def _layout_for_kind(kind):
    entry = _read_entry(kind)
    if entry is None:
        return "stack"
    return entry.get("layout", "stack")


def render(model):
    pages = [entity for entity in model.entities.values() if entity.kind == "page"]
    if len(pages) != 1:
        raise BackendError(
            f"the html backend currently needs exactly one entity of kind 'page' (found {len(pages)})"
        )
    unsupported = [
        entity for entity in model.entities.values()
        if _element_for_kind(entity.kind) is None
    ]
    if unsupported:
        names = ", ".join(f"'{e.id}' ({e.kind})" for e in unsupported)
        raise BackendError(f"the html backend does not support this kind yet: {names}")

    page = pages[0]
    title = model.properties.get((page.id, "title"), "")
    escaped = _html.escape(str(title))

    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="UTF-8">',
        f"<title>{escaped}</title>",
        "</head>",
        "<body>",
    ]
    lines.append(f"<{_element_for_kind(page.kind)} class=\"{page.id}\">")
    if title:
        lines.append(f"<h1>{escaped}</h1>")
    lines.extend(_render_children(model, page.id, 2, "page"))
    lines.append(f"</{_element_for_kind(page.kind)}>")
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines) + "\n"


def _render_children(model, parent_id, indent, parent_kind):
    lines = []
    pad = " " * indent
    children = _children_of(model, parent_id)
    parent_layout = _layout_for_kind(parent_kind)
    for child_id in children:
        child = model.entities[child_id]
        element = _element_for_kind(child.kind)
        if element is None:
            names = f"'{child.id}' ({child.kind})"
            raise BackendError(f"the html backend does not support this kind yet: {names}")
        tag = _open_tag(element, child_id, child.kind, parent_layout)
        title_val = model.properties.get((child_id, "title"), "")
        text_val = model.properties.get((child_id, "text"), "")
        escaped_title = _html.escape(str(title_val)) if title_val else ""
        escaped_text = _html.escape(str(text_val)) if text_val else ""
        grand_children = _children_of(model, child_id)
        if not grand_children and escaped_title:
            lines.append(f"{pad}{tag}")
            lines.append(f"{pad}    <h3>{escaped_title}</h3>")
            if escaped_text:
                lines.append(f"{pad}    {escaped_text}")
            lines.append(f"{pad}</{element}>")
        elif not grand_children and escaped_text:
            lines.append(f"{pad}{tag}{escaped_text}</{element}>")
        elif not grand_children:
            lines.append(f"{pad}{tag}</{element}>")
        else:
            lines.append(f"{pad}{tag}")
            if escaped_title:
                lines.append(f"{pad}    <h3>{escaped_title}</h3>")
            if escaped_text:
                lines.append(f"{pad}    {escaped_text}")
            lines.extend(_render_children(model, child_id, indent + 2, child.kind))
            lines.append(f"{pad}</{element}>")
    return lines


def _open_tag(element, class_value, kind, parent_layout):
    attrs = [f'class="{class_value}"']
    node_layout = _layout_for_kind(kind)
    styles = []
    if parent_layout == "row":
        styles.append("flex:1")
    if node_layout == "row":
        styles.append("display:flex")
        styles.append("gap:20px")
    if styles:
        attrs.append(f'style="{";".join(styles)}"')
    return f"<{element} " + " ".join(attrs) + ">"


def _children_of(model, parent_id):
    return [
        child for child, parent in model.relationships.items() if parent == parent_id
    ]