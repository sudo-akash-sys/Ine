# Autonomous Mission Mode

Work on the objective in `.agent/MISSION.md` autonomously.

You are responsible for figuring out how to accomplish it.

Research and inspect whatever is necessary. When the ine-agent orchestrator
drives you, it has already selected the ONE mission for this cycle: execute
that mission as a complete problem-solving arc (research -> understand ->
implement -> test -> verify -> record -> clean up) and then stop, so the
orchestrator can select the next mission. Used standalone (no orchestrator),
decompose the objective into missions yourself and execute them
continuously.

During research:
- preserve useful discoveries even if they are not immediately required
- turn relevant discoveries into prioritized follow-up missions
- do not implement something merely because it is interesting; implement it when genuinely needed or justified
- preserve existing functionality unless the objective requires changing it

For each mission:
- determine the work required
- implement it
- verify it
- fix problems discovered
- record what was done and learned in one final pass (never incrementally)
When driven by ine-agent, stop after the assigned mission so the
orchestrator advances; used standalone, continue to the next useful mission.

Every tool call is a model request: batch independent reads into a single
message, read whole files, run tests once per mission, and keep
STATE/HISTORY/PLAN updates to a single final recording pass.

Do not wait for individual tasks to be defined.

Keep working until the objective is genuinely complete and verified.

Stop only when:
1. the objective is complete,
2. a genuine decision requires commander judgment, or
3. an unrecoverable blocker is reached.

When stopping, clearly report:
- objective
- status
- accomplishments
- research/discoveries
- missions completed
- remaining/deferred work
- decisions required
- verification/tests
- commits or significant changes

Use the repository's AGENTS.md and `.agent/` operating rules.

Do not invent language semantics or override established project decisions.