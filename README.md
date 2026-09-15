# Ine — A Language for Describing What, Not How

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

> **Early stage / experimental.** Ine is a real, working
> prototype — you can build and run the examples today — but the language
> is still evolving and behavior may change. [LANGUAGE.md](LANGUAGE.md)
> states exactly what is implemented; [WORKBOOK.md](WORKBOOK.md) is the
> design notebook of what is planned and what is still just an idea.

---

## What Is Ine?

Ine (`.ine`) is a tiny language that lets you describe software by *what it should be*, not *how to build it*. You express intent — the meaning of what you want — and multiple backends translate that intent into working implementations.

**The core philosophy:**

> Describe WHAT the software should do before describing HOW it should do it.

Traditional programming forces you to write implementation code directly. Ine moves you up in abstraction:

| Implementation-Level | Intent-Level |
|---------------------|--------------|
| `display: flex; justify-content: space-between` | `logo left, navigation right` |
| `position: fixed; bottom: 0` | `footer stay at bottom` |
| `border-radius: 8px; box-shadow: 0 4px 12px` | `card with subtle shadow` |

The language is kept deliberately small — a handful of statements — so a
first program takes minutes, and the dictionary grows the vocabulary
without changing the core.

---

## One Source, Multiple Targets

The same `.ine` program produces different outputs depending on the backend.
Pick any example in `examples/` and run all three commands to see the
difference.

### HTML Backend

```bash
ine homepage.ine -o homepage.html
```

Emits semantic HTML: each kind maps to an element from the dictionary, and
`inside` nests children. See `examples/homepage-cards/cards.ine` for the
rendered result. 

### Native Backend

```bash
ine program.ine --native
```

Emits C, then a C compiler produces a native executable that runs on the CPU
(Windows PE on Windows). Needs Zig, clang, or gcc.

### Visual Backend

```bash
ine interface.ine --visual
```

Opens a real OS window showing your interface layout (tkinter). Needs a
desktop environment.

---

## Why This Project?

### The Problem

Every programming language forces you to think about implementation: CSS requires knowing flexbox/grid, HTML requires knowing DOM structure, native code requires knowing C and memory management. Each platform has its own paradigm.

### The Solution

Ine provides a semantic layer between you and the implementation. You describe entities, their properties, and relationships. The backends decide how to translate that into working code.

### What Makes It Different

1. **Semantic First** — the language expresses meaning, not syntax
2. **Target-Agnostic** — same source maps to HTML, native code, visual rendering
3. **Extensible Dictionary** — concepts live in a dictionary, not the language core
4. **Gradual Complexity** — start simple, add sophistication only when needed
5. **AI-friendly** — structured enough for AI agents to generate reliably; see the working examples in [examples/](examples/) and the test suite in [tests/](tests/)

---

## Quick Start

### Installation

Open a terminal in the folder where you want the project to live
(for example, `cd ~/Documents` on macOS/Linux, or open the desired folder
in PowerShell on Windows), then run:

```bash
git clone https://github.com/sudo-akash-sys/Ine.git
cd Ine
```

This creates an `Ine/` folder and puts the project inside it.

### Your First Program

Create `hello.ine`:

```ine
make page
page title "Hello, Ine"
```

### Run It

From the repo root, generate the HTML target (requires Python 3):

```bash
ine hello.ine -o hello.html
```

If the `ine` command is not on PATH yet, use the Python fallback —
identical behavior:

```bash
python -m ine hello.ine -o hello.html
```

The terminal prints a short summary:

```
read:       hello.ine
entities:   1
properties: 1
wrote:      hello.html
```

Open `hello.html` — the browser tab says "Hello, Ine", with
the same text as the page heading.

The other two targets work the same way from the same file:

```bash
ine hello.ine --native   # compiles to a runnable executable
ine hello.ine --visual   # opens a real window with the layout
```

`--native` needs a C compiler (Zig recommended); `--visual` needs a desktop
environment.

---

## The Language

Ine is intentionally tiny:

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
| `make <count> <kind>` | Declare `<count>` entities (`make 3 card` → `card-1`, `card-2`, `card-3`) |
| `group <name> = <m1> <m2> ...` | Name a collection of existing entities |
| `<group> inside <parent>` | Containment for every member of the group |
| `<group> <property> <value>` | Apply a property to every member of the group |
| `<child> inside <parent>` | Declare containment relationship |
| `say <value>` | Print to stdout |
| `say <entity> <property>` | Print a property value |

### Values

- **Strings** — `"Hello, world"` (quoted text)
- **Numbers** — `42`, `3.14`, `1e6` (integers and decimals)
- **Properties** — references resolved at compile time

---

## The Dictionary System

The **dictionary** is central to Ine. It maps human-friendly concepts to semantic meaning and implementation hints:

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

## What Works Today

Everything below is implemented and covered by the test suite
(`python -m unittest discover -s tests`, 151 passing):

- Entity declaration and properties (`make`, `<name> <prop> <value>`)
- Multiplicity (`make <count> <kind>` — e.g. `make 3 card` creates `card-1/2/3`)
- Collections (`group cards = card-1 card-2 card-3`; a group targets `inside`
  and properties collectively, expanding to one statement per member)
- Containment relationships (`inside`)
- String and numeric values
- Property references, resolved at compile time (`say page title`)
- HTML backend (writes a `.html` file)
- Native backend (emits C, compiles to a runnable executable via Zig / clang / gcc)
- Visual backend (opens a real window with tkinter)
- Dictionary-driven element mapping, row layout, and bottom-position hints
- Deterministic dictionary discovery (`ine --dict [kind | file.ine]`): which
  kinds follow `make`, a kind's properties and members, and what to write
  next in a real program — from `dictionary/*.json` alone, no AI
- Real working programs in [examples/](examples/)

## Not Implemented Yet

Designed and on the roadmap, but does not work today:

- Multiplicity ("three cards") is solved as creation sugar: `make 3 card`
  creates `card-1/2/3`, and `group cards = card-1 card-2 card-3` names the
  collection (`cards inside card-group` and `cards text "..."` expand per
  member). There is no `every` keyword and no way to say "all members of
  every group"
- More relationship types (`beside`, `contains`, `opens`)
- State, conditions, events, and actions
- Booleans, lists, expressions, runtime variables (today: strings and numbers only)
- Additional backends (React, Flutter) and a separate CSS stylesheet
- Engine-applied templates (`guess` is declared in the dictionary but not yet
  read; `defaults` now drive the discovery suggestions)
- Image/multimodal input and AI interpretation layers

See [WORKBOOK.md](WORKBOOK.md) §15 for the roadmap and [LANGUAGE.md](LANGUAGE.md) §7 for known limits.

---

## Documentation

| Resource | Description |
|----------|-------------|
| [LANGUAGE.md](LANGUAGE.md) | What is actually implemented (exact spec, grows with the code) |
| [WORKBOOK.md](WORKBOOK.md) | Design notebook: philosophy, proposals, open questions, roadmap |
| [examples/](examples/) | Small working programs for each feature |
| [dictionary/](dictionary/) | Concept vocabulary (kind → element, layout, meaning) |

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

Ine is open source, but sustainable development requires funding. Planned paths:

1. **Hosted Services** — online playground, CI integration, private dictionary hosting
2. **Enterprise Extensions** — custom backends, team collaboration, template libraries
3. **Consulting & Training** — workshops, custom dictionary development
4. **Sponsorships** — GitHub Sponsors, Patreon, corporate sponsorships

The core language and dictionary will remain open. Commercial offerings build on top.

---

## License

Apache-2.0 — see [LICENSE](LICENSE) for details. Use it freely for personal and commercial projects. The Ine name and logo remain trademarks; see [TRADEMARKS.md](TRADEMARKS.md).

---

<div align="center">

**Built with intent.**

</div>
