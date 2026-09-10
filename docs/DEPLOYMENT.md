# Deployment Guide

## Demo Mode with Docker Compose

Requirements: Docker Engine with Compose 2.20 or newer. The version floor is
needed for the optional `depends_on.required` relationship.

```bash
docker compose up --build
```

This starts:

- frontend: `http://localhost:5173`
- backend/OpenAPI: `http://localhost:8000` and `/docs`

The default does not start MySQL and needs no provider credentials. Named
volumes persist generated reports, uploads, and logs.

## Real Mode

Copy `.env.example` to `.env`, set `DEMO_MODE=false`, and configure the
providers you intend to route to. Never commit `.env`.

For the bundled MySQL service, set non-empty `MYSQL_PASSWORD` and
`MYSQL_ROOT_PASSWORD`, leave `MYSQL_HOST=mysql`, then run:

```bash
docker compose --profile real up --build
```

The `real` profile starts MySQL 8.4, imports `sql/company_data.sql` on a fresh
volume, and waits for its healthcheck. For an external database, run the
default profile and point `MYSQL_HOST` at that service instead.

Real Mode requires an OpenAI-compatible chat endpoint:

```env
DEMO_MODE=false
LLM_MODEL=deepseek-v4-flash
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=<set-through-your-secret-manager>
```

Use `deepseek-v4-pro` instead when the higher-capability tier is preferred.

Tavily, MySQL, and RAGFlow are independently configured. Missing or offline
specialist providers produce structured tool errors; they do not stop the API
from starting.

## Reverse proxy and TLS

The frontend image serves the SPA through Nginx and proxies `/api/` and
`/ws/` to the backend service. In production, place the deployment behind TLS,
preserve WebSocket upgrade headers, and use one public origin. Configure
`CORS_ORIGINS` as a comma-separated allowlist if the API is exposed on a
different origin.

This repository does not provide end-user authentication. Put an authenticated
gateway in front of any untrusted or internet-facing deployment.

## Data and retention

- `research-output`: generated Markdown/PDF and copied session inputs
- `research-uploads`: pre-task upload staging
- `research-logs`: structured JSON logs
- `mysql-data`: optional Compose MySQL data

Back up or encrypt these volumes according to the sensitivity of user files.
Define a retention process for completed `session_*` directories. Do not mount
the Docker socket or the host source tree into the running API.

## Health and operations

Backend readiness is `GET /health`; frontend readiness is `/healthz`. The
health endpoint deliberately does not contact paid or optional providers.
Inspect structured logs with:

```bash
docker compose logs -f backend
```

Stop the Demo stack with `docker compose down`. Add `--profile real` when
stopping a stack that included MySQL. Add `--volumes` only when you explicitly
intend to erase all persisted project data.

## Non-Docker process deployment

Run `uvicorn api.server:app --host 0.0.0.0 --port 8000` under a service manager.
Build the UI with `npm ci && npm run build` and serve `ui/dist/` from a static
server that implements SPA fallback and WebSocket proxying equivalent to
`ui/nginx.conf`.
