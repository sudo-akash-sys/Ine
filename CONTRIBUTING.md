# Contributing to Intent Expression

Thank you for wanting to help! This project is intentionally small, so even a tiny improvement matters.

## Quick start for contributors

```bash
git clone https://github.com/justforfundg350-boop/intent-language.git
cd intent-language
python -m venv .venv
# Windows: .venv\Scripts\activate  |  macOS/Linux: source .venv/bin/activate
pip install -e .
python mylang.py examples/hello/hello.ine
```

Run tests before opening a PR:

```bash
pytest -q
python mylang.py examples/hello/hello.ine -o .tmp/preview.html
```

## How to contribute

### 1. Good first issues

Look for issues labeled `good first issue` or `help wanted`. Typical starter tasks:

- Add or improve a `dictionary/*.json` entry (new kind, better defaults)
- Add an example in `examples/`
- Improve error messages in `src/mylang/`
- Fix or extend a backend (`backend_html`, `backend_visual`, `backend_c`)

### 2. The Dictionary is a first-class contribution

The dictionary (`dictionary/*.json`) is not an afterthought — it is how vocabulary grows without changing the language core. A dictionary PR should include:

- `element` (which HTML element the kind maps to)
- Optional `layout: "row"` or `position: "bottom"` hints if the kind needs them
- `defaults` / human-readable `meaning` if relevant
- A tiny example `.ine` file that exercises the new kind

See existing entries like `dictionary/card.json` and `dictionary/card-group.json` as templates.

### 3. Language changes need a real program first

We add language concepts only when a real `.ine` program demonstrates the need (see `WORKBOOK.md` §22 and `LANGUAGE.md`). If you want a new syntax or semantic concept, open an issue with:

- A concrete `.ine` program that cannot be written today
- What you expected vs. what happens now
- Why a dictionary/template change alone is not enough

### 4. Pull request checklist

- [ ] One focused change per PR
- [ ] Tests pass (`pytest`)
- [ ] New behavior has a test or a golden file in `tests/expected/`
- [ ] If you touched a backend, the other backends still render the same model
- [ ] Generated artifacts stay in `.tmp/` (never commit `.c`, `.exe`, or `.tmp/` contents)
- [ ] Updated `LANGUAGE.md` if semantics changed, or `dictionary/` docs if vocabulary changed

## Project structure

```
src/mylang/        # lexer -> parser -> semantic -> backends -> CLI
dictionary/        # kind -> { element, layout, position, defaults, meaning }
examples/          # small real .ine programs (hello, homepage slices, native)
tests/             # pytest suite + golden HTML expectations
output/            # committed HTML outputs (the durable artifacts)
.tmp/              # gitignored scratch space for generated files
LANGUAGE.md        # what is ACTUALLY IMPLEMENTED (grows with code)
WORKBOOK.md        # design philosophy and roadmap
```

## Code style

- Keep the language surface tiny and readable — one statement per line.
- Prefer explicit errors with line numbers over silent fallbacks.
- Backends are adapters: they read the shared `Model`, they don't change it.

## Getting help

Open a Discussion if you are unsure whether an idea belongs in the language, the dictionary, a template, or a backend — that question is part of the design process.

By contributing you agree that your contributions will be licensed under the same [LICENSE](LICENSE) as the project.