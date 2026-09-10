# Release checklist

Audit date: 2026-09-10  
Roles: Principal Engineer, Security Reviewer, QA Lead  
Method: source-first review, executable tests, static security review, and
documentation-to-code comparison. README claims were not treated as evidence.

Status meanings:

- **PASS** — verified by source inspection and/or an executed automated gate.
- **WARNING** — no confirmed release-blocking code defect, but verification is
  incomplete because required external state or a runtime was unavailable.
- **FAIL** — a confirmed release blocker remains.

## Required checks

| # | Status | Check | Verification |
|---:|:---:|---|---|
| 1 | **PASS** | Genuine DeepAgents main agent plus three SubAgents | `create_main_agent` calls `create_deep_agent`; closure and real compiled-graph tests prove exactly `network_search_agent`, `database_query_agent`, and `knowledge_base_agent`. The general-purpose agent is disabled, and DeepAgents filesystem/shell tools are excluded from model-visible tools. |
| 2 | **PASS** | Tavily, MySQL, and RAGFlow are callable Agent tools | Specialist tool allowlists are exact. Tests invoke each agent-facing wrapper and exercise the Real adapter path with injected/mocked provider clients, including timeout and failure behavior. Demo adapters remain an explicit `DEMO_MODE` path, not a silent Real Mode fallback. |
| 3 | **PASS** | `/api/task`, `/api/upload`, `/api/files`, `/api/download` contract | FastAPI integration tests cover validation, immediate task start, uploads, collision handling, listings, downloads, busy-thread conflicts, invalid paths, and error status codes. |
| 4 | **PASS** | `/ws/{thread_id}` connection isolation | Tests cover invalid IDs, cross-thread isolation, same-thread multiple clients, disconnect isolation, history replay, and replay-versus-live ordering. Per-socket send locks prevent interleaved sends. |
| 5 | **PASS** | Real required monitor events | Runtime/monitor and integration tests verify genuine `session_created`, `tool_start`, `assistant_call`, `task_result`, and `error` production. The real compiled DeepAgents delegation test observes actual assistant/tool events. |
| 6 | **PASS** | WebSocket ping/pong | Integration test verifies text `ping` returns exactly `{\"type\":\"pong\",\"message\":\"服务端已收到: ping\"}`. |
| 7 | **PASS** | ContextVar reset on all exits | Tests verify normal completion, raised exceptions, async cancellation, and concurrent task isolation; binding uses `finally` resets. |
| 8 | **PASS** | Concurrent thread message/file isolation | Per-thread canonical directories, ContextVars, independent search budgets, keyed task/upload reservations, and WebSocket maps are tested under concurrent execution. Upload/task and replay/broadcast races have regression tests. |
| 9 | **PASS** | `output/session_*` and `updated/session_*` behavior | Validated thread IDs map to the specified roots. Uploads remain under `updated`; session creation atomically copies them into `output` via a temporary file plus `os.replace`. |
| 10 | **PASS** | File-tool directory traversal defense | Canonical resolution, URL decoding, drive/absolute path rejection, filename sanitization, containment checks, and symlink rejection are tested, including encoded and double-encoded traversal. |
| 11 | **PASS** | Download/files cannot escape output | Root listing and direct listing/download reject paths and symlinks outside `output`; API regression tests expect 403/4xx and confirm external files are omitted. |
| 12 | **PASS** | Destructive SQL prevention | `sqlglot` AST validation permits one read-only statement and rejects DML, DDL, multi-statements, comments, file output, destructive `EXPLAIN`, and unsafe functions. Row limits and timeouts are enforced. Production documentation still requires a DB account with SELECT-only grants for defense in depth. |
| 13 | **PASS** | Safe CORS configuration | Origins accept JSON/CSV environment forms, reject credentials/path/query/invalid ports, and reject mixed wildcard allowlists. Wildcard mode does not enable credentials. Production allowlisting is documented. |
| 14 | **PASS** | Logs do not record API keys | Structured logging redacts secrets in strings, mappings, headers, URLs, exceptions, and monitor payloads. No configuration path logs `SecretStr` plaintext; regression tests cover redaction. |
| 15 | **PASS** | Secrets in code, Git history, README, tests, and docs | The scanner passed across 99 release files and two Git commits with no token/private-key/non-placeholder credential findings. GitHub Actions independently ran the same history-aware scan. |
| 16 | **PASS** | `.env` is gitignored | `git check-ignore .env` passes and `.env` is untracked. The local file was never printed or copied by the audit. |
| 17 | **PASS** | `.env.example` contains placeholders only | Automated packaging test proves all credential variables are empty; the secret scanner independently accepts the file. |
| 18 | **PASS** | Demo Mode requires no third-party service | Full backend tests and E2E Demo workflow passed with LLM/Tavily/RAGFlow keys explicitly blank. Demo covers research events, report generation, listing, and download. |
| 19 | **PASS** | Cross-platform PDF | ReportLab/CID-font PDF creation and text extraction pass on local Windows and on the Ubuntu GitHub Actions runner without an OS-specific office binary. |
| 20 | **PASS** | Frontend WebSocket reconnect/error/ping | Hook tests verify heartbeat, pong handling, malformed-event errors, reconnect behavior, and capped exponential backoff. |
| 21 | **PASS** | Frontend Generated Files | Component and App integration tests verify refresh, rendering, encoded download URLs, and update after `task_result`. |
| 22 | **PASS** | No chain-of-thought exposure | Backend emits only allowlisted, user-facing event fields. Frontend regression test supplies `chain_of_thought` and proves it is not rendered. Production source contains no rendering path for private reasoning. |
| 23 | **PASS** | Docker Compose buildability | Compose structure, Dockerfiles, healthchecks, Nginx proxying, and ignore rules pass static tests. GitHub Actions executed `docker compose config --quiet` and successfully built both backend and frontend images on Linux. |
| 24 | **PASS** | README commands match code | Python, npm, endpoint, environment, Demo/Real Mode, event, proxy, Compose, and Docker build commands were compared to source and executed locally or in GitHub Actions. |
| 25 | **PASS** | CI passes without real API keys | The GitHub Actions workflow passed with `DEMO_MODE=true` and no real provider keys: backend/frontend quality gates, secret scan, Compose validation, and both Docker builds all succeeded. [Successful run](https://github.com/x4328584-sys/deepagents-deep-research/actions/runs/34432771847). |
| 26 | **PASS** | No incomplete/mock success path in production | Static scan found no production TODO/FIXME/NotImplemented/hard-coded-success path. The one `pass` is the intentional `WebSocketDisconnect` handler. Mock/fake references are confined to tests; Demo Mode is an explicit supported runtime. Agent execution has a bounded recursion limit. |
| 27 | **PASS** | No release-blocking unused/duplicate/cyclic code | Ruff reports no unused imports or lint findings, strict mypy passes, imports/compileall pass, and manual dependency review found no circular runtime imports or material duplicate implementation. Runtime dependency manifests are tested for exact synchronization. |
| 28 | **WARNING** | Documentation claims match implementation | Maintained README, architecture, API, deployment, security, and execution-plan claims were reconciled with source and corrected where necessary. The two requested reference documents are zero-byte files, so their intended external contract cannot be compared or reconstructed without inventing content. |

## Executed release gates

| Gate | Result |
|---|---|
| Backend lint (`ruff check .`) | **PASS** |
| Backend typecheck (`mypy agent api tools utils`) | **PASS**, 28 source files |
| Backend tests, integration, E2E, and security tests | **PASS**, 109/109, 88% statement coverage |
| Python dependency check and bytecode compilation | **PASS** |
| Frontend lint | **PASS** |
| Frontend typecheck | **PASS** |
| Frontend tests | **PASS**, 7/7 in 5 files |
| Frontend production build | **PASS**, Vite output generated |
| Frontend dependency audit | **PASS**, 0 vulnerabilities |
| Secret scan | **PASS**, 99 release files and 2 Git commits; `.env` ignored |
| Docker Compose config/build | **PASS** in GitHub Actions; local Docker remains unavailable |

Automated tests: **116 passed / 116 total**. There are **0 FAIL** items.

## Remaining warnings and release decision

1. The two supplied reference Markdown files are empty; obtain their intended
   contents if they are authoritative release inputs.
2. Production remains a single-process, in-memory service without built-in
   authentication. Deploy only behind the documented authenticated gateway,
   TLS, request-size/rate controls, and a SELECT-only MySQL account.
3. One third-party Starlette/AnyIO deprecation warning is emitted by the test
   client; it does not affect runtime behavior but should be watched on the
   next dependency upgrade.

**GitHub release readiness: READY.** The repository is uploaded, the release
candidate has no known blocking implementation defect, all local gates are
green, and the keyless GitHub Actions workflow—including Compose validation and
both Docker image builds—has passed. The remaining warnings above are explicit
deployment/reference limitations, not release blockers.
