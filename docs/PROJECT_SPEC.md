# Project specification

## Goal and scope

Build a production-shaped, publicly releasable implementation of **DeepAgents
Deep Research**: a main DeepAgents orchestrator that can iteratively search,
read, reflect, search again, and synthesize by delegating to Network Search,
Database Query, and RAGFlow Knowledge Base subagents. The product includes a
FastAPI service, thread-scoped WebSocket monitoring, safe upload/report
storage, an original responsive React UI, Docker deployment, tests, and public
repository documentation.

Supported generated report formats are Markdown and PDF only. Uploaded inputs
support TXT, Markdown, JSON, JSONL, CSV, DOCX, PDF, XLSX, and XLS. The system
must start and demonstrate its workflow without external services in Demo
Mode, while Real Mode must use the official stable DeepAgents API.

## Required repository layout

The repository contains root project metadata; `agent/`, `api/`, `tools/`, and
`utils/` Python packages; YAML prompts; sample SQL; a Vite React application;
unit/integration/e2e tests; reference and operator documentation; and ignored
`output/` and `updated/` runtime roots. Detailed final structure is kept in the
active implementation plan and README.

## Functional requirements

### Orchestration

- Construct the Real Mode main agent using `create_deep_agent`.
- Register exactly the three required specialist subagents with their own
  prompts and tool allowlists.
- Give only uploaded-file and report-generation tools to the main agent.
- Route public information to Network Search, internal structured data to
  Database Query, private unstructured knowledge to RAGFlow, and uploaded
  documents to the file reader.
- Permit iterative delegation and reflection; do not replace autonomous
  routing with a fixed graph or group chat.
- Acquire information before writing a report; PDF generation always follows
  Markdown generation. The streaming runtime rejects conflicting parallel
  tool calls rather than relying on the prompt alone.

### Integrations

- Tavily search supports `general`, `news`, and `finance`, preserves source
  metadata, caps a research assignment at five calls, and returns structured
  failures.
- MySQL exposes table discovery, schema/preview, and guarded query execution.
  Demo Mode uses an in-process read-only sample repository.
- RAGFlow exposes assistant listing plus create/ask/delete lifecycle behavior,
  selects by name/description, and gracefully handles missing credentials,
  offline services, and timeouts.
- All external providers are lazy: unavailable configuration must never prevent
  FastAPI from starting.

### REST API

| Method | Path | Contract |
|---|---|---|
| POST | `/api/task` | `{query, thread_id?}`; immediately returns `{status:"started", thread_id}` |
| POST | `/api/upload` | multipart `files` and required `thread_id`; stores sanitized names under the upload session |
| GET | `/api/files?path=...` | recursively lists files only beneath `output/`, newest first |
| GET | `/api/download?path=...` | returns a file beneath `output/` with `FileResponse`; violations are 4xx |
| GET | `/health` | reports process readiness without requiring external providers |

Requests never wait for an agent run. Duplicate active use of the same
`thread_id` is rejected to avoid output races.

### WebSocket protocol

`/ws/{thread_id}` binds connections to one validated ID and supports multiple
browser connections per thread without cross-thread broadcast. Client text
`ping` receives `{ "type": "pong", "message": "服务端已收到: ping" }`.

Monitor messages have this envelope:

```json
{
  "type": "monitor_event",
  "event": "session_created",
  "message": "Session workspace created",
  "data": {},
  "timestamp": "2026-09-09T08:00:00Z"
}
```

Required events and data are `session_created {path}`, `tool_start
{tool_name,args}`, `assistant_call {assistant_name,args}`, `task_result
{result}`, and `error {error}`. Arguments are redacted and bounded. No model
chain-of-thought or hidden reasoning is sent.

### Frontend

The React/TypeScript/Vite UI has a compact task rail, central Markdown answer
view, activity/file rail, and bottom composer with multi-file upload. It
persists thread IDs locally, connects before task submission, reconnects with
bounded exponential backoff, sends heartbeat pings, renders all loading/error/
empty states, refreshes files after session/result events, and downloads via
the configured API base URL. HTTP and WebSocket origins can be overridden by
`VITE_API_BASE_URL` and `VITE_WS_BASE_URL`; development defaults to the local
API and the production container uses same-origin Nginx proxies.

## Filesystem model

- Upload: `updated/session_<thread_id>/<sanitized-name>`.
- Run: `output/session_<thread_id>/`; matching uploads are copied here before
  tools run.
- `ContextVar[str] thread_id` and `ContextVar[Path] session_dir` are bound for
  one task and reset in `finally`.
- The task registry rejects simultaneous runs with the same ID; WebSocket
  routing is keyed by thread ID.
- Maximum upload size and permitted extensions are settings with secure
  defaults.

## Configuration and dependencies

Settings are loaded from environment variables through Pydantic Settings.
Real Mode uses an OpenAI-compatible LangChain chat model, including providers
such as DeepSeek when `OPENAI_BASE_URL` points to their compatible endpoint.
Other variables configure Tavily, MySQL, RAGFlow, CORS, timeouts, and file-size
limits. No value in `.env.example` is a credential.

The target runtimes are Python 3.12 and Node 20+. Package versions are chosen
against the installed stable DeepAgents release and locked after validation.

## Security requirements

- Reject malformed thread IDs, dangerous filenames, unknown extensions,
  oversized bodies, non-files, missing sessions, symlinks, absolute paths,
  Windows drives, `..`, and percent-encoded traversal.
- Apply output-root checks independently to list/download APIs.
- Validate SQL in executable Python code; reject mutations, DDL, comments that
  conceal statements, and multiple statements.
- Do not log authorization values, API keys, database passwords, uploaded
  document contents, or hidden model reasoning.
- Provider calls use timeouts and return typed errors. Client-facing messages
  contain no stack trace or secret.
- Keep runtime artifacts, local env files, logs, caches, and build output out of
  Git.

## Quality and acceptance

Backend coverage includes API contracts, WebSockets and every event, context
isolation, file readers and generators, SQL safety, provider mocks and failure
degradation, three complete integration flows, and explicit traversal/size/
timeout attacks. Frontend gates are ESLint, TypeScript, Vitest for critical
hooks/components, and a production build. Docker Compose must parse and build
where Docker is available. A pattern-based and history-aware secret scan is
required before release.
