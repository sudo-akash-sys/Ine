# Project Authority

WORKBOOK.md contains the project's high-level vision and decisions.

LANGUAGE.md contains the current language specification.

The AI must distinguish between:
- DECIDED
- PROPOSED
- EXPERIMENTAL
- UNDECIDED

A user question or exploration is NOT automatically a design decision.

Do not convert a possibility discussed in conversation
into a mandatory architectural requirement.

Do not make major language-design decisions autonomously.

When an architectural choice has significant consequences,
present the options and trade-offs before implementing it.

# Temporary-File Policy (permanent rule)

Use the project's `.tmp/` directory for EVERY Intent Expression-generated
temporary probe, generated source, executable, object file, compiler
test, intermediate artifact, and disposable build output. This is a
permanent working rule, not just this session.

`.tmp/` is already in `.gitignore` — never commit it.

Keep generated FINAL project outputs (e.g. `output/*.html`) in their own
output directory, separate from `.tmp/`. Final outputs are the committed
deliverables; `.tmp/` is the scratch space for discovering the language.

Do not assume that external tools will never use the operating system's
%TEMP% directory. If a compiler, runtime, package manager, shell, or
other trusted build tool requires the system temp directory, allow it
rather than attempting to redirect all system temporary-file behavior.
