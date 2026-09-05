"""Command-line entry point for the mylang tool."""

import argparse
import os
import sys

from .backend_html import BackendError, render
from .interpreter import execute
from .lexer import LexError, lex
from .parser import SyntaxError, parse
from .semantic import SemanticError, analyze


def build(source_path, out_path):
    with open(source_path, "r", encoding="utf-8") as handle:
        source = handle.read()
    tokens = lex(source)
    statements = parse(tokens)
    model = analyze(statements)
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
    if line is not None:
        message = f"{message} (line {line})"
    print(f"error: {message}", file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="mylang",
        description="Process a MyLanguage (.int) program",
    )
    parser.add_argument("source", help="path to a .int program")
    parser.add_argument(
        "-o", "--out", default=None,
        help="output file path for the html target (default: output/<name>.html)",
    )
    args = parser.parse_args(argv)

    if args.out is None:
        name = os.path.splitext(os.path.basename(args.source))[0]
        args.out = os.path.join("output", name + ".html")

    try:
        model, outputs, html = build(args.source, args.out)
    except (LexError, SyntaxError, SemanticError, BackendError) as error:
        _report_error(error)
        return 1

    for output in outputs:
        print(output)
    print(f"read:       {args.source}")
    print(f"entities:   {len(model.entities)}")
    print(f"properties: {len(model.properties)}")
    if html is not None:
        print(f"wrote:      {args.out}")
    else:
        print("target:     the program does not describe a page")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())