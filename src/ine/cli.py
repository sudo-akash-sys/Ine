"""Command-line entry point for the ine tool."""

import argparse
import os
import sys

from . import dictionary
from .backend_html import BackendError, render
from .backend_visual import VisualError, show as visual_show
from .interpreter import execute
from .lexer import LexError, lex
from .native import NativeError, compile_c, run_native
from .parser import SyntaxError, parse
from .semantic import SemanticError, advisory_warnings, analyze, resolve


def _report_advisories(model):
    """Print dictionary-backed advisory warnings to stderr. Never fatal:
    the build proceeds and the exit status is unchanged."""
    for warning in advisory_warnings(model):
        print(f"warning: {warning}", file=sys.stderr)


def build(source_path, out_path):
    with open(source_path, "r", encoding="utf-8") as handle:
        source = handle.read()
    tokens = lex(source)
    raw_statements = parse(tokens)
    model = analyze(raw_statements)
    _report_advisories(model)
    statements = resolve(raw_statements, model)
    outputs = execute(statements)
    html = None
    if model.entities:
        html = render(model)
    if html is not None and out_path:
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(html)
    return model, outputs, html


def _report_error(error):
    message = error.message
    line = getattr(error, "line", None)
    column = getattr(error, "column", None)
    if column is not None:
        message = f"{message} (line {line}, column {column})"
    elif line is not None:
        message = f"{message} (line {line})"
    print(f"error: {message}", file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ine",
        description="Process an Ine (.ine) program",
    )
    parser.add_argument(
        "source", nargs="?", default=None,
        help="path to a .ine program (or a dictionary query with --dict)",
    )
    parser.add_argument(
        "-o", "--out", default=None,
        help="output file path for the html target (default: output/<name>.html)",
    )
    parser.add_argument(
        "--native", action="store_true",
        help="compile the program to a native executable and run it",
    )
    parser.add_argument(
        "--visual", action="store_true",
        help="open a native window showing the program's visual layout",
    )
    parser.add_argument(
        "--dict", action="store_true",
        help="query the dictionary: a kind name, an .ine program, or the whole vocabulary",
    )
    args = parser.parse_args(argv)

    if args.source is None and not args.dict:
        parser.error("the following arguments are required: source")

    try:
        if args.dict:
            return _dict(args.source)
        if args.native:
            return _native(args.source)
        if args.visual:
            return _visual(args.source)
        return _html(args.source, args.out)
    except (LexError, SyntaxError, SemanticError, BackendError, NativeError, VisualError) as error:
        _report_error(error)
        return 1


def _html(source_path, out_path):
    if out_path is None:
        name = os.path.splitext(os.path.basename(source_path))[0]
        out_path = os.path.join("output", name + ".html")

    model, outputs, html = build(source_path, out_path)

    for output in outputs:
        print(output)
    print(f"read:       {source_path}")
    print(f"entities:   {len(model.entities)}")
    print(f"properties: {len(model.properties)}")
    if html is not None:
        print(f"wrote:      {out_path}")
    else:
        print("target:     the program does not describe a page")
    return 0


def _native(source_path):
    with open(source_path, "r", encoding="utf-8") as handle:
        source = handle.read()
    tokens = lex(source)
    raw_statements = parse(tokens)
    model = analyze(raw_statements)
    _report_advisories(model)
    statements = resolve(raw_statements, model)
    outputs = execute(statements)
    name = os.path.splitext(os.path.basename(source_path))[0]
    c_path, exe_path = compile_c(statements, name)
    stdout = run_native(exe_path)

    for line in stdout.splitlines():
        print(line)
    print(f"read:       {source_path}")
    print(f"emitted:    {c_path}")
    print(f"executable: {exe_path}")
    print(f"run:        exit 0")
    if not outputs:
        print("target:     no executable statements (nothing to compile)", file=sys.stderr)
    return 0


def _visual(source_path):
    with open(source_path, "r", encoding="utf-8") as handle:
        source = handle.read()
    tokens = lex(source)
    raw_statements = parse(tokens)
    model = analyze(raw_statements)
    _report_advisories(model)
    statements = resolve(raw_statements, model)
    outputs = execute(statements)

    for output in outputs:
        print(output)
    print(f"read:       {source_path}")
    print(f"entities:   {len(model.entities)}")
    print(f"properties: {len(model.properties)}")
    print("opening visual window...")
    visual_show(model)
    return 0


def _print_kind_entry(source, entry):
    """Print one dictionary entry as its full structured body.

    The shaped body is what `make <kind>` should surface — the dictionary
    "knows its format". Whole-entry output only; the flat suggestion list
    stays behind plain `--dict`.
    """
    print(f"{source} ({entry.get('kind', '?')}):")
    for field in ("element", "meaning"):
        value = entry.get(field)
        if isinstance(value, str):
            print(f"  {field}: {value}")

    defaults = entry.get("defaults")
    if isinstance(defaults, dict):
        print("  defaults:")
        for name, value in sorted(defaults.items()):
            if isinstance(value, list):
                print(f"    {name:<18} {', '.join(str(v) for v in value)}")
            else:
                print(f"    {name:<18} {value}")

    declared = entry.get("properties")
    if isinstance(declared, dict):
        print("  properties:")
        for name in sorted(declared):
            shape = dictionary.value_shape(source, name)
            if shape.type == "choice" and shape.choices:
                print(f"    {name:<18} choice: " + ", ".join(shape.choices))
            else:
                print(f"    {name:<18} {shape.type}")

    style = entry.get("style")
    if isinstance(style, dict):
        base = style.get("base")
        if isinstance(base, list) and base:
            print("  style:")
            for declaration in base:
                print(f"    {declaration}")
        properties = style.get("properties")
        if isinstance(properties, dict):
            if not isinstance(base, list) or not base:
                print("  style:")
            for name, spec in sorted(properties.items()):
                if not isinstance(spec, dict):
                    continue
                css = spec.get("css")
                values = spec.get("values")
                suffix = f" (css: {css}, values: {', '.join(str(v) for v in values)})" \
                    if isinstance(css, str) and isinstance(values, dict) else ""
                print(f"    {name}{suffix}")

    child_kinds = dictionary.members(source)
    if child_kinds:
        print(f"  contains: {', '.join(child_kinds)}")

    parent_kinds = dictionary.parents(source)
    if parent_kinds:
        print(f"  belongs inside: {', '.join(parent_kinds)}")

    implementation = entry.get("implementation")
    if isinstance(implementation, dict):
        html = implementation.get("html")
        if isinstance(html, str):
            print(f"  implementation.html: {html}")


def _dict(source):
    if source is None:
        items = dictionary.suggest()
        print("what can follow 'make':")
        for item in items:
            print(f"  {item.text:20s} {item.note}")
        print(f"\n{len(items)} kinds declared in the dictionary")
        return 0

    if os.path.isfile(source):
        with open(source, "r", encoding="utf-8") as handle:
            program = handle.read()
        model = analyze(parse(lex(program)))
        print(f"context: {os.path.basename(source)} ({len(model.entities)} entities)")
        empty = True
        for entity_id in sorted(model.entities):
            kind = model.entities[entity_id].kind
            items = dictionary.suggest(kind)
            if not items:
                continue
            empty = False
            print(f"\n{entity_id} ({kind}):")
            for item in items:
                print(f"  {item.text:30s} {item.note}")
        if empty:
            print("  (no dictionary-suggested statements)")
        return 0

    entry = dictionary.find(source)
    if entry is not None:
        _print_kind_entry(source, entry)
        return 0

    if os.path.splitext(source)[1] or os.sep in source:
        print(f"error: '{source}' is not a readable .ine file", file=sys.stderr)
        return 1

    print(f"error: unknown kind '{source}'", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())