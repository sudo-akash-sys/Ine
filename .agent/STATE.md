# .agent/STATE.md

Current ground truth as of Session 32. Update this file as work proceeds.

## Current focus

The dictionary is the single source of truth and the editor prototype
milestone is complete (Sessions 27–30). Session 31 added the `value`
completion context (property-value completion) and completed a full
dictionary coverage reconciliation of every real program. Session 32 built
the `ine-agent` autonomous supervisor (developer tooling): it reads
`.agent/`, picks the first EXECUTABLE task, drives one worker at a time,
and stops cleanly on the defined conditions. No feature work is in
flight; nothing in `.agent/PLAN.md` is EXECUTABLE right now. The next real
change is evidence unblocking the enumerated `choice` value (see
`.agent/BLOCKERS.md`) — otherwise an agent stops and records state rather
than inventing work.

## Health

- Test suite: **234 passing** (`python -m pytest tests`) — lexer, parser,
  semantic, dictionary, CLI, autocomplete, extension protocol, ine-agent.
- Goldens (hello, topbar, hero, cards) **byte-identical**; `dictionary-demo.ine`
  renders.
- Environment: Windows / PowerShell 5.1, Python 3.13.14, node v24.17.0.
  Repo-root `ine.py` is a tracked shim that inserts `src/` into `sys.path`
  (it shadows the `ine` package — engine run as a script self-prepends `src/`).

## Pipeline & entry points

- `src/ine/lexer.py` → `parser.py` → `semantic.py` → `backend_*.py`.
- `src/ine/cli.py`: `ine run <file>`, `ine render <file> -o out.html`,
  `ine visual <file>`, `ine --dict [kind|file]`.
- `src/ine/autocomplete.py`: stdin JSON-lines `{buffer, line, column, id?}`
  → stdout `{id?, line, column, context, items[]}` per line; 4 contexts
  (`make`→makeable, kind→members/properties, `value`→shape options,
  inside→parents). One-shot and streaming both work; worker persists across
  requests.

## Dictionaries (15 files)

- Base kinds: page, header, section, hero, container, card-group, card,
  card-1, copy, footer.
- Concepts: universal (content properties `title`/`text`, both shaped
  `"text"` in a `properties` block), ambient (viewport `width`/`height` →
  `"length"`), entity (the run), misc (logo, link, thumbnail), wizard.
- Reader API: `makeable`, `find`, `properties_for`, `value_hint`,
  `suggest` (`Suggestion(text, source, note)`), `for_model`, `members`
  (structural children), `parents` (reverse containment),
  `ValueShape(type, choices)` + `value_shape(kind, prop)`.

## Editor prototype

- `editor/vscode-ine/`: extension.js is a pure proxy (zero Ine vocab);
  DictionaryWorker spawns `python <root>/src/ine/autocomplete.py`, FIFO
  queue, 4 s timeout, respawn on death, `" "` + ASCII-letter triggers,
  snippets: `value_shape == "text"` → `SnippetString('title "${1}"')`.

## ine-agent (developer tooling, Session 32)

- `python src/ine_agent/cli.py run` (or `ine-agent run` once installed):
  reads `.agent/`, applies the PLAN selection rule (first EXECUTABLE item,
  in list order), launches exactly one worker per cycle (sequential, never
  concurrent), rereads `.agent/` state after each cycle, and stops on the
  defined conditions. Exit codes: 0 = normal/no-work, 1 = error/bounded
  stop, 2 = HUMAN_DECISION_REQUIRED gate.
- Routing is deterministic: OpenCode is the implementation worker
  (`opencode run <prompt> --pure --dir <root>`); Claude is used only for
  `CLAUDE_REVIEW`-tagged tasks (review step, never implementation). No AI
  task classifier. Optional `--dry-run` prints the first executable task
  without launching anything.
- Files: `src/ine_agent/` — `state.py` (PLAN/STATE/HISTORY/BLOCKERS
  readers, Task/Plan), `supervisor.py` (loop, stop conditions, prompt
  builders), `worker.py` (OpenCode/Claude subprocess workers + stubs),
  `cli.py` (argparse entry, `--root`, `--worker`, `--dry-run`,
  `--cycle-limit`, `--max-attempts`). Guardrails hard-coded in prompts:
  never invent semantics, never unblock evidence-gated work, never modify
  DECISIONS.md, keep temp artifacts under `.tmp/`.

## Known caveats

- `ine --dict universal` (pseudo-entry) shows `a text` for title/text since
  universal.json now owns a `properties` block — valid, intended side
  effect.
- No value kinds beyond `text` (and ambient `length`) are declared — no
  evidence supports more.
- `button label` is dictionary-suggested, but renderers surface `text`.

## Coverage (reconciled, Session 31)

All property and containment usage across every real program (hello, topbar,
hero, cards, dictionary-demo) is fully covered by the dictionary. Entity
aliases (`main` → `container`, `hero` → `banner`) resolve cleanly. `search`,
`subtitle`/`description`, and the WORKBOOK `button inside header` layout
are evidence-gated proposals that remain correctly undeclared — see
`.agent/BLOCKERS.md`. Custom domain vocabulary (`person`/`name`/`age` in
alice.ine) is a scope boundary of the advisory dictionary, not a gap.

## Records

- WORKBOOK.md §1–§41 (decisions/architecture).
- SESSION_STATE.md Sessions 1–30 (§12 tracks DONE bullets; Session 30 DONE).
- RESEARCH_LOG.md, LANGUAGE.md (spec), README.md.