# Intent Expression — A Language for Describing What, Not How

<div align="center">

**Write what you want. Let the machine figure out how.**

```ine
make page
page title "Company Name"
make header
make footer
header inside page
footer position "bottom"
```

**One source. Three targets.** HTML. Native machine code. Visual windows.

[Quick Start](#quick-start) &middot; [Documentation](#documentation) &middot; [Contributing](#contributing)

</div>

---

## What Is Intent Expression?

Intent Expression (`.ine`) is a tiny language that lets you describe software by *what it should be*, not *how to build it*. You express intent — the meaning of what you want — and multiple backends translate that intent into working implementations.

**The core philosophy:**

> Describe WHAT the software should do before describing HOW it should do it.

Traditional programming forces you to write implementation code directly. Intent Expression moves you up in abstraction:

| Implementation-Level | Intent-Level |
|---------------------|--------------|
| `display: flex; justify-content: space-between` | `logo left, navigation right` |
| `position: fixed; bottom: 0` | `footer stay at bottom` |
| `border-radius: 8px; box-shadow: 0 4px 12px` | `card with subtle shadow` |

The language is small enough to learn in an afternoon, yet powerful enough to describe real interfaces.

---

## One Source, Multiple Targets

The same `.ine` program produces different outputs depending on the backend:

### HTML Backend

```bash
python mylang.py homepage.ine -o homepage.html
```

Generates semantic HTML with proper structure and accessible markup.

### Native Backend

```bash
python mylang.py program.ine --native
```

Compiles to C, then to a native Windows executable that runs on the CPU.

### Visual Backend

```bash
python mylang.py interface.ine --visual
```

Opens a real OS window showing your interface layout.

---

## Why This Project?

### The Problem

Every programming language forces you to think about implementation: CSS requires knowing flexbox/grid, HTML requires knowing DOM structure, native code requires knowing C and memory management. Each platform has its own paradigm.

### The Solution

Intent Expression provides a semantic layer between you and the implementation. You describe entities, their properties, and relationships. The backends decide how to translate that into working code.

### What Makes It Different

1. **Semantic First** — the language expresses meaning, not syntax
2. **Target-Agnostic** — same source maps to HTML, native code, visual rendering
3. **Extensible Dictionary** — concepts live in a dictionary, not the language core
4. **Gradual Complexity** — start simple, add sophistication only when needed
5. **AI-Native** — designed for AI agents to generate and understand

---

## Quick Start

### Installation

```bash
git clone https://github.com/justforfundg350-boop/intent-language.git
cd intent-language
```

### Your First Program

Create `hello.ine`:

```ine
make page
page title "Hello, Intent Expression"
```

### Run It

No installation needed — just run from the repo root:

```bash
# Generate HTML
python mylang.py hello.ine -o hello.html

# Compile to native executable
python mylang.py hello.ine --native

# Visual preview
python mylang.py hello.ine --visual
```

---

## The Language

Intent Expression is intentionally tiny:

```ine
# Declare entities
make page
make header
make logo
make navigation
make footer

# Set properties
page title "Company Name"
logo text "Company Logo"
footer text "© 2026"

# Define relationships (containment)
logo inside header
navigation inside header
header inside page
footer inside page

# Execute actions
say page title
```

### Statements

| Statement | Purpose |
|-----------|---------|
| `make <name>` | Declare an entity |
| `make <name> <kind>` | Declare an entity with explicit kind |
| `<name> <property> <value>` | Set a property |
| `<child> inside <parent>` | Declare containment relationship |
| `say <value>` | Print to stdout |
| `say <entity> <property>` | Print a property value |

### Values

- **Strings** — `"Hello, world"` (quoted text)
- **Numbers** — `42`, `3.14`, `1e6` (integers and decimals)
- **Properties** — references resolved at compile time

---

## The Dictionary System

The **dictionary** is central to Intent Expression. It maps human-friendly concepts to semantic meaning and implementation hints:

```json
{
  "card": {
    "element": "article",
    "description": "A content container with title and description",
    "properties": ["title", "description", "image"]
  },
  "card-group": {
    "element": "section",
    "layout": "row",
    "description": "Container for side-by-side cards"
  }
}
```

The dictionary contains:

- **Semantic meaning** — what a concept *means*
- **Default values** — sensible starting points
- **Implementation hints** — element mapping, layout rules
- **Constraints** — valid properties, relationships

This separation means:

- New concepts can be added without changing the language
- Different backends can interpret concepts differently
- The language stays small; the vocabulary grows

See [dictionary/](dictionary/) for the full vocabulary.

---

## Architecture

```
.ine source file
        |
        v
  +-----------+  Text -> Tokens
  |   Lexer   |
  +-----------+
        |
        v
  +-----------+  Tokens -> Syntax Statements
  |  Parser   |
  +-----------+
        |
        v
  +------------------+  Statements -> Model
  | Semantic Analyzer|  (Entities, Properties, Relationships)
  +------------------+
        |
        v
  +----------------+  Resolve references
  |    Resolver    |
  +----------------+
        |
        v
      Model ---+---+------------+
               |   |            |
               v   v            v
          +--------+ +--------+ +--------+
          |  HTML  | | Native | | Visual |
          |Backend | |Backend | |Backend |
          +--------+ +--------+ +--------+
               |       |            |
               v       v            v
             HTML    .exe      OS Window
```

Each backend is an **adapter** that translates the same semantic model into its target technology. One language, many implementations.

---

## Status

Currently implemented:

- Entity declaration and properties
- Containment relationships (`inside`)
- String and numeric values
- Property reference resolution
- HTML backend
- Native C backend (via Zig / clang / gcc)
- Visual tkinter backend
- Dictionary-driven element mapping
- Row layout hints & bottom position hints

On the roadmap:

- Multiplicity (groups of similar entities)
- More relationship types (`beside`, `contains`)
- State and conditions
- Events and actions
- Additional backends (React, Flutter)

---

## Documentation

| Resource | Description |
|----------|-------------|
| [LANGUAGE.md](LANGUAGE.md) | Complete language specification |
| [WORKBOOK.md](WORKBOOK.md) | Design philosophy and workbook |
| [examples/](examples/) | Example programs for each feature |
| [dictionary/](dictionary/) | Built-in concept definitions |

---

## Contributing

Contributions are welcome! We're looking for help with:

- **Backend development** — new targets (React, Flutter, mobile)
- **Language features** — multiplicity, state, events
- **Dictionary expansion** — new concepts and templates
- **Documentation** — tutorials, examples, guides
- **Testing** — comprehensive test coverage

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Community

- Use **Discussions** for questions and ideas
- Use **Issues** to report bugs or request features
- All contributors are expected to follow our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

---

## Monetization & Sustainability

Intent Expression is open source, but sustainable development requires funding. Planned paths:

1. **Hosted Services** — online playground, CI integration, private dictionary hosting
2. **Enterprise Extensions** — custom backends, team collaboration, template libraries
3. **Consulting & Training** — workshops, custom dictionary development
4. **Sponsorships** — GitHub Sponsors, Patreon, corporate sponsorships

The core language and dictionary will remain open. Commercial offerings build on top.

---

## License

MIT — see [LICENSE](LICENSE) for details. Use it freely for personal and commercial projects.

---

<div align="center">

**Built with intent.**

</div>
