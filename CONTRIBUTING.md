# Contributing to Ine

Thank you for your interest in contributing to Ine! This document provides
guidelines for contributing to the project.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Repository layout

```
src/ine/               pipeline: lexer.py → parser.py → semantic.py → backend_*.py
src/ine/autocomplete.py   JSON-lines editor engine (standalone)
src/ine_agent/            autonomous development supervisor (loop, workers, CLI)
src/ine/dictionary/*.json   the single vocabulary source (15 files)
editor/vscode-ine/        thin VS Code extension (pure proxy to the Python dictionary)
tests/                    pytest suite: lexer, parser, semantic, dictionary, CLI,
                          autocomplete, extension protocol, ine-agent
.agent/                   autonomous control plane (PLAN/STATE/HISTORY/BLOCKERS)
```

## The language pipeline

`.ine` → `lexer.py` → `parser.py` → `semantic.py` → `backend_html.py` /
`backend_visual.py` / `backend_c.py`. Each stage is documented in
`LANGUAGE.md`. `src/ine/dictionary.py` reads `src/ine/dictionary/*.json` and
answers discovery questions; it is the only vocabulary source.

## The dictionary

The dictionary is **advisory, never a validator**. It guides autocomplete
and renderer hints but never rejects a program. A kind with no dictionary
entry has no suggestions (this is intentional — see
`examples/alice/alice.ine`).

New vocabulary is added as a `.json` file under `src/ine/dictionary/` and verified
with `ine --dict <kind>` and `python -m pytest tests/test_ine.py -k integrity`.
See `dictionary/README.md` for the JSON schema.

## Running the CLI

Three ways, all equivalent:

```bash
# 1. From the repo root (shim: adds src/ to sys.path)
python ine.py <file> -o out.html

# 2. As a module (recommended for development)
python -m ine <file> -o out.html

# 3. After pip install (installed entry point)
ine <file> -o out.html
```

Same for `ine-agent` (installed) or `python -m src.ine_agent.cli` (development).

## Running tests

```bash
python -m pytest tests          # canonical runner
python -m pytest tests -k integrity   # dictionary integrity only
```

The suite is fully hermetic (stdlib only, no network). Native tests auto-skip
without a C compiler. The tkinter visual tests may emit a transient `TclError`
under full-suite load; the class passes in isolation and on rerun (pre-existing
flake).

## Session 25 freeze

There is no code freeze. The four-construct spine and golden-output
discipline are architectural commitments (see `.agent/DECISIONS.md`), but
backend and main changes are welcome provided they do not break existing
behavior and stay aligned with the project's larger goals — deviations from
original intent are acceptable when the implementation requires it
(commander clarification, Session 41).

## How to contribute

### Reporting issues

- Check existing issues before creating a new one
- Provide a clear description of the problem
- Include steps to reproduce the issue
- Share your environment details (OS, Python version, etc.)

### Submitting changes

1. Fork the repository
2. Create a new branch for your feature or fix
3. Make your changes following the project's coding standards
4. Write or update tests as needed
5. Run `python -m pytest tests` and confirm all tests pass
6. Submit a pull request

### Pull request guidelines

- Keep changes focused and atomic
- Write clear commit messages
- Reference related issues in your PR description
- Add tests for new features; update documentation as needed

## Working with the autonomous control plane (`.agent/`)

`.agent/` tracks the development plan (PLAN.md), state (STATE.md), history
(HISTORY.md), and blockers (BLOCKERS.md). Key conventions:

- **PLAN selection rule:** the first `EXECUTABLE` item in list order is the
  next task; `BLOCKED` / `DONE` items are never picked.
- **STATE / HISTORY updates:** every completed session updates both files.
- **`.tmp/`** is the only location for temporary artifacts (gitignored);
  never commit generated files outside this directory.
- **Dictionary is advisory:** the autonomous agent never unblocks
  evidence-gated work by guessing — evidence-gated means evidence is needed.

## License and Copyright

By contributing to Ine, you agree that your contributions will be licensed under
the Apache License, Version 2.0.

### Developer Certificate of Origin

By making a contribution to this project, you certify that:

- You created the contribution entirely yourself, or you have the right to
  submit it under the project's license
- You understand and agree that your contribution is public and that a record
  of the contribution is maintained indefinitely
- You grant sudo-akash-sys and the project a perpetual, worldwide, non-exclusive,
  royalty-free, irrevocable license to use, modify, and distribute your
  contribution under the Apache-2.0 license

## Trademark Usage

Note that while your code contributions are licensed under Apache-2.0, the Ine
name and logos remain trademarks of sudo-akash-sys. See [TRADEMARKS.md](TRADEMARKS.md)
for details.

## Questions?

If you have questions about contributing, feel free to open an issue for
discussion.