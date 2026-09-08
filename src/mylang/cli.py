"""Command-line entry point for the mylang tool."""

import argparse
import os
import sys

from .backend_html import BackendError, render
from .interpreter import execute
from .lexer import LexError, lex
from .native import NativeError, compile_c, run_native
from .parser import SyntaxError, parse
from .semantic import SemanticError, analyze, resolve


def build(source_path, out_path):
    with open(source_path, "r", encoding="utf-8") as handle:
        source = handle.read()
    tokens = lex(source)
    raw_statements = parse(tokens)
    model = analyze(raw_statements)
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
    parser.add_argument(
        "--native", action="store_true",
        help="compile the program to a native executable and run it",
    )
    args = parser.parse_args(argv)

    try:
        if args.native:
            return _native(args.source)
        return _html(args.source, args.out)
    except (LexError, SyntaxError, SemanticError, BackendError, NativeError) as error:
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


if __name__ == "__main__":
    raise SystemExit(main())