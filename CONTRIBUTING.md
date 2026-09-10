# Contributing

Thanks for helping improve DeepAgents Deep Research. Keep changes focused,
testable, provider-neutral, and safe to publish.

## Development flow

1. Fork the repository and create a topic branch.
2. Install Python 3.12 and Node.js 20.19 or newer.
3. Run `python -m pip install -e ".[dev]"` and `cd ui && npm ci`.
4. Keep `DEMO_MODE=true` while developing unless a Real Mode integration is
   the explicit subject of the change.
5. Add or update tests for behavior and security boundaries.
6. Run the complete local gates before opening a pull request:

   ```bash
   python -m ruff check .
   python -m mypy agent api tools utils
   python -m pytest
   cd ui
   npm run lint
   npm run typecheck
   npm test -- --run
   npm run build
   ```

## Pull requests

- Explain the problem, approach, and validation performed.
- Preserve the main-agent/three-specialist boundary unless an architecture
  proposal is discussed first.
- Never add credentials, production data, private URLs, or model reasoning.
- Use environment variables for provider configuration.
- Avoid weakening path, upload, SQL, CORS, logging, or session-isolation checks.

Report vulnerabilities through the process in [SECURITY.md](SECURITY.md), not
through a public issue.
