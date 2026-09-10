# Repository guide

DeepAgents Deep Research is a Python 3.12 / React project targeting Node 20+.
Start with `docs/PROJECT_SPEC.md`, `ARCHITECTURE.md`, and the active execution plan in
`docs/exec-plans/active/implementation-plan.md`.

## Working rules

- Preserve the orchestrator/worker boundary: the main agent delegates public,
  SQL, and knowledge-base work to the three named subagents.
- Keep all runtime paths inside the active `output/session_<thread_id>` and
  validate paths in Python, not only in prompts.
- Keep SQL read-only in code and reject multiple statements.
- Never log, commit, echo, or copy credentials. Real providers are configured
  only through environment variables; tests and CI use Demo Mode.
- Do not expose model reasoning. WebSocket monitoring carries only safe,
  user-facing execution events.
- Update the active execution plan as phases finish and run the relevant tests
  after every phase.

## Quality gates

Run `python -m pytest`, `python -m ruff check .`, and
`python -m mypy agent api tools utils`. In `ui/`, run `npm run lint`,
`npm run typecheck`, `npm test -- --run`, and `npm run build`.
