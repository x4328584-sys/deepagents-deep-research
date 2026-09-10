# Development Guide

## Prerequisites

- Python 3.12
- Node.js 20.19 or newer; CI uses Node.js 22
- npm 11-compatible lockfile support
- Docker Compose 2.20+ only for container validation/deployment

## Setup

```bash
python -m venv .venv
```

Activate the virtual environment, then install the pinned project and test
dependencies:

```bash
python -m pip install -e ".[dev]"
cd ui
npm ci
```

Copy `.env.example` to `.env` only when you need overrides. The committed
defaults use credential-free Demo Mode. The frontend's optional `ui/.env`
uses `VITE_API_BASE_URL` and `VITE_WS_BASE_URL`; Vite embeds these values at
build time.

## Run locally

Terminal one:

```bash
python -m uvicorn api.server:app --reload --host 127.0.0.1 --port 8000
```

Terminal two:

```bash
cd ui
npm run dev
```

Open `http://localhost:5173`. FastAPI OpenAPI is at
`http://localhost:8000/docs`.

## Quality gates

```bash
python -m ruff check .
python -m mypy agent api tools utils
python -m pytest
python -m pytest --cov=agent --cov=api --cov=tools --cov=utils --cov-report=term-missing

cd ui
npm run lint
npm run typecheck
npm test -- --run
npm run build
```

The backend tests never require paid providers. They use Demo Mode, fake SDK
clients, temporary directories, and an in-process FastAPI/WebSocket client.

## Architecture constraints

- Real Mode must remain a native DeepAgents `create_deep_agent` orchestrator,
  not a fixed DAG or group chat.
- The main agent owns only uploaded-file and report tools. Tavily, MySQL, and
  RAGFlow tools remain with their three named specialist agents.
- Any model-supplied file path is relative to the current ContextVar session.
- SQL authorization is enforced in Python and must not be delegated to a
  prompt alone.
- WebSocket activity is public execution metadata, never hidden reasoning.

See [ARCHITECTURE.md](../ARCHITECTURE.md) and
[PROJECT_SPEC.md](PROJECT_SPEC.md) before changing these boundaries.

## Adding a provider or file type

Keep external SDK calls behind a service adapter with explicit timeout,
bounded output, normalized failure objects, and injected clients for tests.
For a file type, update both the extension allowlist and parser, then add
valid, malformed, oversized, traversal, and session-isolation cases.

## Dependency updates

Python runtime versions are pinned in both `pyproject.toml` and
`requirements.txt`; keep them synchronized. Frontend dependency versions and
the npm lockfile must change together. Run all gates after any update because
DeepAgents, LangChain, provider SDKs, TypeScript, and Vite have coupled API and
runtime constraints.
