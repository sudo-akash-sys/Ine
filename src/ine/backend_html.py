"""Renders the semantic model as an HTML document.

Styling is dictionary-driven, never invented here. Every kind that declares
a `style` block in the dictionary contributes a rule to the document's
stylesheet, and the kind's name rides along as a class on each element so
those rules can reach it.

A value a program writes for one entity (`card-1 padding 32`) lands on that
element as an inline `style` attribute rather than as a rule. Inline wins
over the kind's rule, and it keeps working when the entity is named after
its kind — `make card` names it `card`, so a `.card` rule could not tell
that entity from the kind.

Two document-level facts stay hard-coded, in the same class as the doctype
and the charset: the viewport meta, without which a page renders at desktop
width on a phone, and a minimal `body` baseline. Neither is vocabulary.

Responsiveness is one rule, and it is dictionary-gated: a kind whose entry
declares `narrow-class` and `narrow-layout` in `defaults` while its `layout`
is `row` (today: card-group only) gets a single
`@media (max-width: 768px) { .<kind> { flex-direction: column; } }` rule —
the Missions 22/56 "row stacks on narrow" recommendation. `narrow-layout`
"stack members" reads as `flex-direction: column`; the `narrow-class`
condition expression is not evaluated (conditions/state are UNDECIDED; its
presence is what gates the rule). 768px is the platform narrow breakpoint, a
document-level fact in the same class as the viewport meta. Members keep
their `flex:1` from the row layout: in a column stack the container is
content-sized, so there is no free space to grow into and each member keeps
its natural height.
"""

import html as _html

from . import dictionary

DEFAULT_ELEMENT = "div"

# The document baseline: not vocabulary, the same class of backend detail as
# the doctype and the charset.
BODY_BASELINE = (
    "margin: 0",
    "font-family: system-ui, -apple-system, 'Segoe UI', sans-serif",
    "line-height: 1.5",
    "color: #1a202c",
)


class BackendError(Exception):
    def __init__(self, message, line=None):
        super().__init__(message)
        self.message = message
        self.line = line


def _element_for_kind(kind):
    entry = dictionary.find(kind)
    if entry is None:
        return None
    return entry.get("element", DEFAULT_ELEMENT)


def _layout_for_kind(kind):
    entry = dictionary.find(kind)
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
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{escaped}</title>",
    ]
    lines.extend(_stylesheet(model))
    lines.append("</head>")
    lines.append("<body>")
    lines.append(f"<{_element_for_kind(page.kind)} {_attrs(page.id, page.kind, _written(model, page.id))}>")
    if title:
        lines.append(f"<h1>{escaped}</h1>")
    lines.extend(_render_children(model, page.id, 2, "page"))
    lines.append(f"</{_element_for_kind(page.kind)}>")
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines) + "\n"


def _stylesheet(model):
    """The document's rules, built from the dictionary — nothing else.

    One rule per kind the program actually uses. Values an entity writes
    for itself are not here: they ride on the element as a `style`
    attribute, which beats any rule and cannot collide with the kind's.
    Kinds that declare narrow behavior under a row layout contribute one
    `@media` rule (see `_narrow_rule`).
    """
    rules = [f"body {{ {'; '.join(BODY_BASELINE)}; }}"]
    used_kinds = sorted({entity.kind for entity in model.entities.values()})
    for kind in used_kinds:
        declarations = dictionary.style_declarations(kind)
        if declarations:
            rules.append(f".{kind} {{ {'; '.join(declarations)}; }}")
    for kind in used_kinds:
        narrow = _narrow_rule(kind)
        if narrow is not None:
            rules.append(narrow)
    return ["<style>", *rules, "</style>"]


NARROW_BREAKPOINT = "(max-width: 768px)"


def _narrow_rule(kind):
    """The kind's one narrow rule, or None when it declares no narrow
    behavior. A kind stacks its members below the narrow breakpoint when its
    `defaults` declare both `narrow-class` (the gating condition; its content
    is not evaluated — conditions/state are UNDECIDED) and `narrow-layout`
    ("stack members" reads as a column direction) while its `layout` is
    `row`. All three facts come from the dictionary entry, not the kind's
    name."""
    entry = dictionary.find(kind)
    if entry is None:
        return None
    defaults = entry.get("defaults")
    if not isinstance(defaults, dict):
        return None
    if not defaults.get("narrow-class") or not defaults.get("narrow-layout"):
        return None
    if _layout_for_kind(kind) != "row":
        return None
    return f"@media {NARROW_BREAKPOINT} {{ .{kind} {{ flex-direction: column; }} }}"


def _written(model, entity_id):
    """The properties a program wrote for one entity."""
    return {
        name: value for (owner, name), value in model.properties.items()
        if owner == entity_id
    }


def _classes(entity_id, kind):
    """An element carries its kind, so the dictionary's rule reaches it,
    and its own name, which the program uses to talk about it."""
    if entity_id == kind:
        return entity_id
    return f"{kind} {entity_id}"


def _attrs(entity_id, kind, written, parent_layout="stack"):
    """An element's attributes: its classes, then a `style` attribute
    holding the declarations the kind's own rule does not already state.

    Two sources land here — the row/stack layout a dictionary `layout`
    costs its children, and any physical value the program wrote for this
    entity. Inline wins over the kind's rule, which is the point.
    """
    attrs = [f'class="{_classes(entity_id, kind)}"']
    styles = []
    if parent_layout == "row":
        styles.append("flex:1")
    if _layout_for_kind(kind) == "row":
        styles.append("display:flex")
        styles.append("gap:20px")
    styles.extend(dictionary.style_overrides(kind, written))
    if styles:
        attrs.append(f'style="{"; ".join(styles)}"')
    return " ".join(attrs)


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
        tag = f"<{element} {_attrs(child_id, child.kind, _written(model, child_id), parent_layout)}>"
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


def _children_of(model, parent_id):
    return [
        child for child, parent in model.relationships.items() if parent == parent_id
    ]