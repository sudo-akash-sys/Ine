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

# Temporary-File Policy

Use the project's `.tmp/` directory for MyLanguage-generated temporary
files, experiments, intermediate project artifacts, and disposable
build outputs whenever practical.

Do not assume that external tools will never use the operating system's
%TEMP% directory. If a compiler, runtime, package manager, shell, or
other trusted build tool requires the system temp directory, allow it
rather than attempting to redirect all system temporary-file behavior.
