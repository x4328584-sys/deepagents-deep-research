# Active implementation plan

Date: 2026-09-10

## 1. Original objective

Deliver a runnable, tested, Docker-deployable, GitHub-ready DeepAgents deep
research system with a real hierarchical main-agent/three-worker architecture,
safe per-thread files, real-time monitoring, an original React interface,
credential-free Demo Mode, and environment-configured Real Mode.

## 2. Target directory

```text
.
├── agent/                 LLM, prompts, main and specialist agents
├── api/                   FastAPI, context, monitor, logging, WebSockets
├── tools/                 Tavily, MySQL, RAGFlow, file and report tools
├── utils/                 settings, path and SQL/security primitives
├── prompt/                YAML prompt source
├── sql/                   reproducible sample company data
├── ui/                    React + TypeScript + Vite application
├── tests/{unit,integration,e2e}/
├── docs/{reference,exec-plans}/
├── output/                ignored run sessions
└── updated/               ignored upload sessions
```

Root files provide packaging, dependency locks, Docker/Compose, CI, licensing,
contribution/security policy, and operator documentation.

## 3. Agent architecture

- Main: `create_deep_agent`, three named subagent specifications, and only
  upload/report tools.
- Network: one DeepAgents subagent with `internet_search`; prompt enforces
  3-5 bounded angles and source retention.
- Database: one subagent with list/schema-preview/query tools; Python validates
  SQL before either demo or MySQL execution.
- Knowledge Base: one subagent with assistant-list and ask lifecycle tools;
  prompt enforces progressive, three-angle retrieval.
- Demo runtime: credential-free coordinator mirrors routing and emitted public
  actions, while the actual DeepAgents graph remains directly constructible
  and is tested with a fake chat model.

## 4. API contract

- `POST /api/task`: validate optional ID, schedule an async background task,
  immediately return status and canonical thread ID.
- `POST /api/upload`: required ID, one or more bounded supported files,
  sanitized collision-safe storage.
- `GET /api/files`: safe output-relative root, recursive file metadata sorted
  by `mtime` descending.
- `GET /api/download`: safe existing regular file under output, `FileResponse`,
  explicit 4xx on invalid/missing paths.
- `GET /health`: local readiness only.

## 5. WebSocket events

Route `/ws/{thread_id}`. Standard monitor envelope contains `type`, `event`,
human-safe `message`, `data`, and UTC ISO timestamp. Required events are
`session_created`, `tool_start`, `assistant_call`, `task_result`, and `error`.
Incoming `ping` returns the specified Chinese `pong` message. Disconnect and
broadcast failures remove only affected sockets.

## 6. Filesystem model

Validated IDs map to `updated/session_<id>` and `output/session_<id>`.
Session creation and upload copy precede agent execution. ContextVars bind the
current ID/directory, all model-provided paths are treated as relative, and
canonical resolution plus symlink checks enforce containment. API paths have a
separate output-root guard.

## 7. Frontend functions

Persistent task history/thread IDs, task composer, multi-file upload, API
submission, reconnecting/heartbeat WebSocket, safe activity timeline, Markdown
answer rendering, generated file refresh/download, accessible responsive
layout, and complete pending/empty/error states. Base URLs are build-time env
variables with localhost development defaults.

## 8. External dependencies

Python 3.12; DeepAgents and its LangGraph/LangChain constraints; LangChain
OpenAI-compatible chat client; FastAPI/Uvicorn/Pydantic Settings; HTTPX;
Tavily; PyMySQL; document/PDF/spreadsheet libraries; YAML; multipart/aiofiles;
pytest/asyncio/httpx/WebSocket test support; Ruff and mypy. Frontend targets
Node 20+ with React, Vite, TypeScript, ESLint, React Markdown, and Vitest.
Exact versions are pinned after compatibility inspection.

## 9. Security constraints

No committed credential; allowlisted file types; filename/ID/size validation;
canonical and URL-decoded traversal defense; output/session containment;
read-only single-statement SQL; provider timeout/degradation; CORS allowlist;
log and monitor redaction; no chain-of-thought; escaped/sanitized rendering;
ignored runtime artifacts; active secret scan.

## 10. Test strategy

Unit tests cover settings, IDs, filenames, resolvers, ContextVars, SQL guard,
provider adapters, readers, Markdown/PDF, monitor translation, and agent
construction. API/WebSocket integration tests cover all contracts and five
events. E2E backend tests cover network-to-Markdown/download, DOCX upload/read,
database discovery/query, parallel thread isolation, disconnect, and provider
failure/timeout. Frontend gates include lint/typecheck/unit/build. Final checks
include server smoke tests, Compose parse/build when available, and secret
patterns plus Git tracked-file inspection.

## 11. Phases and gates

| Phase | Deliverable | Gate | Status |
|---|---|---|---|
| 1 | references, specification, architecture, notes, plan, AGENTS | files reviewed for contract coverage | complete |
| 2 | Python package/config/dependencies | import and settings tests | complete |
| 3 | context/path/security/logging/monitor | focused unit and concurrency tests | complete |
| 4 | Tavily/MySQL/RAGFlow/file/report tools | tool and failure tests | complete |
| 5 | three specialist agents | tool-boundary construction tests | complete |
| 6 | DeepAgents main orchestrator and demo runner | construction/routing tests | complete |
| 7 | FastAPI/WebSocket | API and socket integration tests | complete |
| 8 | backend test suite | pytest, Ruff, mypy | complete |
| 9 | responsive React frontend | npm ci, lint, typecheck, Vitest, build | complete |
| 10 | frontend/backend integration | live local smoke flow | complete |
| 11 | Docker packaging | Compose validation/build if runtime exists | static complete; local runtime unavailable |
| 12 | public docs, policies, CI, hygiene | docs review and secret scan | complete |
| 13 | full acceptance | all available gates green, limitations recorded | complete with release warnings |

## Final verification

- Backend: 109 tests passed with 88% statement coverage; Ruff and strict mypy
  passed; `pip check` found no broken requirements.
- Frontend: clean `npm ci`, ESLint, TypeScript, seven Vitest tests, and the
  Vite production build passed; `npm audit` reported zero vulnerabilities.
- Live smoke: separate backend/frontend processes served successfully; REST,
  WebSocket ping/pong, task events, Markdown generation, file listing, and
  download completed in Demo Mode.
- Packaging: editable Python package build/install passed and packaged prompts
  loaded successfully.
- Docker: Compose YAML, required service/profile/dependency structure, both
  Dockerfiles, and healthcheck presence passed static validation. Docker is not
  installed on the execution host, so an image build could not be run locally.
- Hygiene: local `.env` is ignored and untracked, runtime data is ignored,
  token-pattern and non-empty credential-assignment scans are clean, and the
  newly initialized repository has no commits or remote history to audit.
- Release audit: the final source-first results, 28 item dispositions, executed
  gates, and remaining operational warnings are recorded in
  `RELEASE_CHECKLIST.md`.

## 12. Reference conflicts, errors, and obsolete details

Both requested reference documents are empty and were originally misplaced;
there is no reference code or API text to compare. The task deliberately
rejects Word output and pixel-copy claims. Current-package API behavior will
override remembered/tutorial syntax. RAGFlow and PDF implementations are kept
behind adapters because SDK/native-runtime details are version-sensitive.
Docker and Node were not initially present on the host PATH; bundled workspace
runtimes are checked before declaring those gates unavailable. Full decisions
and any later discoveries are maintained in `docs/REFERENCE_NOTES.md`.
