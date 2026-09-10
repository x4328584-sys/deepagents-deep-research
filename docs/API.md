# API Reference

The development base URL is `http://localhost:8000`. FastAPI also exposes the
interactive OpenAPI page at `/docs` while the service is running.

## Conventions

- JSON endpoints use UTF-8.
- A `thread_id` is 1–64 characters, begins with an ASCII letter or number, and
  then contains only letters, numbers, `_`, or `-`.
- Validation failures return FastAPI's standard JSON `detail` response and a
  4xx status. File-scope violations return 403; missing output paths return
  404; an already-running thread returns 409.
- `POST /api/task` schedules work and returns immediately. Results arrive over
  the thread WebSocket.

## Health

### `GET /health`

```json
{"status":"ok","mode":"demo"}
```

`mode` is either `demo` or `real`. This is a process-readiness endpoint, not a
deep check of optional external providers.

## Tasks

### `POST /api/task`

Request:

```json
{
  "query": "Research recent agent-system developments and create a Markdown report",
  "thread_id": "optional-client-id"
}
```

Omit `thread_id` to receive a UUID. Success (`200`):

```json
{
  "status": "started",
  "thread_id": "b3b2786d-377e-4c9b-87a4-f87ce45b5058"
}
```

### `GET /api/task/{thread_id}`

Returns the in-memory process status: `running`, `completed`, `failed`, or
`cancelled`. Unknown tasks return 404. This endpoint is supplementary; the
WebSocket `task_result` or `error` event is the authoritative task outcome.

## Uploads

### `POST /api/upload`

Send `multipart/form-data` before starting work for the same thread:

```bash
curl -X POST http://localhost:8000/api/upload \
  -F "thread_id=research-001" \
  -F "files=@notes.md" \
  -F "files=@metrics.xlsx"
```

Success:

```json
{
  "status": "uploaded",
  "files": ["notes.md", "metrics.xlsx"]
}
```

Supported extensions are `.txt`, `.md`, `.json`, `.jsonl`, `.csv`, `.docx`,
`.pdf`, `.xlsx`, and `.xls`. The defaults allow ten files per request and 10
MiB per file. Filenames are normalized; traversal, hidden/reserved names, and
unsupported extensions are rejected. Uploading to an active thread returns
409.

## Generated files

### `GET /api/files?path=session_research-001`

Lists regular files recursively under an output-relative path, newest first:

```json
[
  {
    "name": "deep-research-report.md",
    "type": "file",
    "path": "session_research-001/deep-research-report.md",
    "size": 4096,
    "mtime": 1788940800.0
  }
]
```

### `GET /api/download?path=session_research-001/deep-research-report.md`

Returns a `FileResponse` attachment. Only existing regular files canonically
contained by `output/` are accessible.

## WebSocket

Connect to `ws://localhost:8000/ws/{thread_id}` before starting the task. A
bounded history is replayed on reconnect.

All monitor events share this envelope:

```json
{
  "type": "monitor_event",
  "event": "tool_start",
  "message": "Running tool: internet_search",
  "data": {},
  "timestamp": "2026-09-09T08:00:00+00:00"
}
```

| Event | Data fields | Meaning |
|---|---|---|
| `session_created` | `path` | Output session is ready. |
| `assistant_call` | `assistant_name`, `args` | Main Agent delegated to a specialist. |
| `tool_start` | `tool_name`, `args` | A public tool action began. |
| `task_result` | `result` | Final Markdown-compatible answer. |
| `error` | `error` | Safe task-level failure message. |

Monitor events intentionally exclude hidden model reasoning, credentials, and
authorization metadata.

Send the text frame `ping` to receive:

```json
{"type":"pong","message":"服务端已收到: ping"}
```

## Minimal browser flow

1. Generate a `thread_id` and open its WebSocket.
2. Upload optional files using that ID.
3. Submit `POST /api/task` using the same ID.
4. Render safe execution events until `task_result` or `error`.
5. Save the `session_created.data.path`, call `/api/files`, then use each
   returned output-relative path with `/api/download`.
