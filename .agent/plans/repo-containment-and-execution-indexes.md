# Repo containment, mission execution indexes, and the control-plane cost fix

## Context

Three problems, one change set.

**1. Work leaked outside the repository.** A 36 KB `ine-project-analysis.html`
was written to `~/.claude/projects/…` instead of the repo. Separately, `.tmp/`
holds 561+ leftover entries — `ineagent-*` (36), `ineicon-*` (100), `usage-*`
(24), plus a full `venv63/` — from test fixtures that were never cleaned up, and
from research artifacts that are now gone (STATE.md still points at
`.tmp/native-expansion/` for Mission 76, and that directory no longer exists).
Durable work sitting in gitignored scratch is work that can vanish.

**2. The worker is told to think.** `supervisor.impl_prompt` embeds
`MISSION_PROMPT.md`, which says *"You are responsible for figuring out how to
accomplish it"*, *"Research and inspect whatever is necessary"*, *"decompose the
objective into missions yourself and execute them continuously"* — while the
same prompt says *"do NOT continue to further missions"*. Two contradictory
instructions, reconciled by the model on every cycle. That is the token burn:
the planner's job is being re-done by the executor, badly and expensively.

**3. The recording pass is enormous.** The worker is asked to update
`.agent/STATE.md` (98 KB) and `.agent/HISTORY.md` (77 KB) every mission — roughly
30k+ tokens of reading per cycle, before any work happens.

Outcome: everything project-related lives in the repo, the planner writes a
concrete execution index, the worker only executes, and the recording pass gets
cheap.

## Decisions taken (commander)

- A mission with **no execution index is refused** — recorded `BLOCKED` via the
  existing `missing_prerequisite` machinery, deferred, loop continues. No worker
  call is spent.
- **STATE.md becomes bounded** (position only); per-session detail moves to the
  append-only HISTORY.md.
- `ine-project-analysis.html` is **moved into the repo**.
- All of it lands in **one pass**.

---

## A. Repository containment rule

**`AGENTS.md`** — add a `## Repository containment` section:

- Every project artifact is written **inside this repository**. No project file
  goes to the user profile (`~/.claude/…`), the OS temp dir, or any path outside
  the repo.
- `.agent/` holds **durable** records (`STATE` `HISTORY` `PLAN` `DECISIONS`
  `BLOCKERS` `NOTES` `MISSION_PROMPT` `WORKER_PROMPT` `RUN_REPORTS`
  `missions/`). If a finding or artifact matters, it goes here — not `.tmp/`.
- `.tmp/` is **scratch only** (gitignored). Nothing in `.tmp/` may be referenced
  as the location of a durable result; a path in STATE/HISTORY/NOTES pointing
  into `.tmp/` is a defect.
- Document the two sanctioned exceptions, so the rule is not read as absolute
  and then ignored: (i) Claude Code's own session/`file-history` stores are
  harness-internal, not agent output, and cannot be relocated — the agent must
  never treat them as project storage; (ii) a test fixture that must not sit
  inside a git work tree may use the OS temp dir, and must register for cleanup.
- Note that orchestrator sessions are recorded in `.agent/RUN_REPORTS.md`;
  interactive Claude Code sessions are harness-internal and are not.

Also fix `AGENTS.md`'s recording step (currently STATE + HISTORY + PLAN only) to
name **NOTES.md** and **MISSION_PROMPT.md / WORKER_PROMPT.md** — those files
exist and are currently never updated.

**`CLAUDE.md`** — one line only, no restatement (it deliberately defers to
AGENTS.md): mention the containment rule in "the two steps easiest to miss".

**Memory** — write `project-repo-containment.md` (type `project`) recording the
rule and the reason, plus a one-line pointer in `MEMORY.md`.

**Move** `~/.claude/projects/E--VS-Code-Projects-MyLanguage/ine-project-analysis.html`
→ `docs/ine-project-analysis.html` (new `docs/`), and delete the original.

---

## B. Mission execution indexes (the core change)

### B1. New artifact: `.agent/missions/<NNN>.md`

One file per PLAN item, keyed on the **item number** (already stable, already
parsed by `state._ITEM_RE`) — so no new PLAN syntax and no way for the pointer
to drift.

```markdown
# Mission 115 — <headline, must match the PLAN.md first line>

Goal: <one sentence — the end state, not the activity>

Files:
  - src/ine_agent/supervisor.py   (edit)
  - tests/test_ine_agent.py       (edit)

Steps:
  1. [ ] <concrete edit, naming the function/symbol>
  2. [ ] <concrete edit>
  3. [ ] <add/extend the named test>

Verify: `python -m pytest tests/test_ine_agent.py -q` — all pass.
Done when: <observable end state>.
Do not: <mission-specific guardrails>.
```

The contract: **steps name the change, not the investigation.** If a step needs
research, the planner does that research, not the worker.

### B2. `.agent/WORKER_PROMPT.md` (new) — execution-only

Replaces `MISSION_PROMPT.md` in the orchestrator prompt. Content: execute the
index in order; do not research, re-plan, re-scope, or decompose; do not read
`PLAN.md`/`STATE.md`/`HISTORY.md` whole; stop when `Done when` holds or a step
is impossible; end with the `CLASSIFICATION:` / `REASON:` block (contract
unchanged — the parser in `supervisor.py` depends on it); print
`HUMAN_DECISION_REQUIRED` if a step needs commander judgment.

### B3. `state.py`

Add `MISSION_DIR = "missions"`, `mission_index_path(root, number)` and
`read_mission_index(root, number)` — returns the text or `None`. Same
read-optional pattern as `_read_optional_text`.

### B4. `supervisor.py`

- `impl_prompt(root, task)` becomes: **WORKER_PROMPT.md** + MISSION.md project
  context + `_distill_state` snapshot + **the mission index** + the headline.
  `MISSION_PROMPT.md` is no longer embedded. Drop the "read AGENTS.md in full"
  instruction (WORKER_PROMPT carries the rules that matter; AGENTS.md stays the
  human/planner entry point).
- **Missing index → refuse, spending no worker call.** New guard in the
  `run()` loop before `_run_task`: if `read_mission_index(root, task.number)`
  is `None`, classify `missing_prerequisite` with reason
  `no execution index at .agent/missions/NNN.md — the planner must write one`
  and take the existing `blocked` path.
- **Reuse, not duplication:** factor the `blocked` branch of
  `_diagnosis_outcome` into `_record_blocked(task, detail, cycles)` and call it
  from both the refusal guard and the diagnosis path.
- `MISSION_PROMPT.md` is retargeted as the **planner's** prompt (it already
  reads that way), with a header stating it is not the execution worker's prompt.
- No new CLI flags.

### B5. Worked examples

Write indexes for the first two or three EXECUTABLE items so the loop has real
work and the format has a reference implementation, and document the planning
workflow in AGENTS.md.

> **Consequence to accept deliberately:** on the next real `run`, every
> un-indexed EXECUTABLE item (~37) is refused and marked `BLOCKED` with a
> remark. That is the intended behaviour and is reversible by writing indexes —
> but it should be a choice, not a surprise.

---

## C. Bounded STATE.md, append-only HISTORY.md

STATE.md currently duplicates per-session narratives that HISTORY.md also
carries. Split it by line range, moving content **verbatim**, no editorial
merging:

- **Stays in STATE.md** (position only, bounded): header session pointer,
  `Current focus`, `Health`, `Pipeline & entry points`, `Dictionaries`,
  `Editor prototype`, `ine-agent`, `Known caveats`, `Coverage`, `Records`
  (currently lines 1–276 and 1481–end).
- **Moves to HISTORY.md** (appended in file order under a clearly labelled
  section): every `## Session …` / `## Mission 111 — …` block, lines 277–1480.

Result: STATE.md ~98 KB → ~10 KB, so both `_distill_state` (per cycle) and the
worker's recording pass get cheap. HISTORY.md is append-only — the recording
pass appends a session block and never reads the file.

Update in the same pass:
- `AGENTS.md` recording step: append to HISTORY.md; rewrite only STATE.md's
  bounded head sections; tag the PLAN item; consider NOTES.md.
- `WORKER_PROMPT.md` and MISSION_PROMPT.md: same wording.
- `tests/test_ine_agent.py::ControlPlaneHealthTests` — the STATE-header ↔
  latest-HISTORY-heading assertion must survive the move; adjust to the new
  layout and pin the bounds (e.g. STATE.md stays under a size ceiling) so a
  future session cannot silently re-bloat it.

---

## D. `.tmp/` repair and cleanup

**Fix the leak, then clean it.**

- `tests/test_ine_agent.py:2893` — `tempfile.mkdtemp(prefix="ineicon-", dir=TMP)`
  is never registered in `_CREATED_ROOTS` and never removed. Replace the ad-hoc
  `mkdtemp` calls in this module with one registered helper
  `make_tmp_dir(prefix)` that appends to `_CREATED_ROOTS`.
- `_clean_temp_roots()` uses `shutil.rmtree(root, ignore_errors=True)`, which
  **silently swallows** the Windows failure on git's read-only object files —
  that is why the `ineagent-*` leftovers contain nothing but `.git`. Pass an
  `onerror` handler that clears the read-only bit and retries, and stop
  discarding the error silently.
- `usage-*` fixtures (`_db`, line 696) rely on `addCleanup(rmtree, …, True)` —
  same silent-failure shape; route them through the same helper.
- Extend the autouse `_no_temp_root_leftovers` fixture to fail loudly if any
  `ineagent-*` / `ineicon-*` / `usage-*` directory survives a test.
- **Cleanup pass:** delete the leaked test fixtures only (`ineagent-*`,
  `ineicon-*`, `usage-*`). Leave `venv63/`, `wheels/`, `m57_*`, `pricing.html`,
  `settings.html`, `backend_html_patched.py`, `.tmp/native-expansion` (absent)
  alone and report them — several are real artifacts from past sessions whose
  fate is the commander's call, not a cleanup script's.

---

## Verification

1. `python -m pytest tests/test_ine_agent.py -q` then `python -m pytest tests -q`
   — full suite green, with the new tests:
   - `MissionIndexTests` — index read; absent index refused **with zero worker
     calls** (assert `StubWorker.calls == []`); a refusal writes the PLAN remark,
     the BLOCKERS entry and one run-report line and defers only that mission.
   - `PromptContractTests` — `impl_prompt` embeds the index and WORKER_PROMPT.md,
     does **not** embed MISSION_PROMPT.md's planning language, and still ends on
     the `CLASSIFICATION:` / `REASON:` contract the parser reads.
   - `TempHygieneTests` — no fixture directories survive a test run.
   - updated `ControlPlaneHealthTests` — STATE/HISTORY contract + STATE size ceiling.
2. `python -m ine_agent.cli run --root . --dry-run` against the repo — confirms
   selection and prompt assembly without spending a worker call or touching PLAN.md.
3. **Live-run verification happens on a throwaway fixture root**, never the
   repo, precisely because the first real repo run now refuses un-indexed
   missions and marks them BLOCKED.
4. `python -m ine_agent.measure` before and after, to show the recording path's
   cost moved — the Phase 4 baseline is 17 runs, 20 cycles, 2 completions.

## Risks

- **Volume of moved text.** The STATE→HISTORY move is ~90 KB of verbatim
  relocation; verified by checking the byte delta and that no `## Session`
  heading is lost from either file.
- **Mass-BLOCK on the next real run** (see B5) — intended, but it is a live
  change to PLAN.md and should be a conscious decision.
- `.tmp/venv63/` and the other non-fixture leftovers are deliberately **not**
  deleted.
