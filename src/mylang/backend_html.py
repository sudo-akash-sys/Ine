"""Renders the semantic model as an HTML document."""

import html as _html

SUPPORTED_KINDS = {"page"}


class BackendError(Exception):
    def __init__(self, message, line=None):
        super().__init__(message)
        self.message = message
        self.line = line


def render(model):
    pages = [entity for entity in model.entities.values() if entity.kind == "page"]
    unsupported = [entity for entity in model.entities.values() if entity.kind not in SUPPORTED_KINDS]
    if len(pages) != 1:
        raise BackendError(
            f"the html backend currently needs exactly one entity of kind 'page' (found {len(pages)})"
        )
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
        f'<div class="{page.id}">',
    ]
    if title:
        lines.append(f"<h1>{escaped}</h1>")
    lines.append("</div>")
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines) + "\n"