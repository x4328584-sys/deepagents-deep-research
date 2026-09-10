# Security Policy

## Supported version

Security fixes target the latest revision of the default branch.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting feature for this repository. If
that feature is unavailable, contact the repository maintainers privately.
Do not open a public issue containing exploit details, credentials, private
documents, or user data.

Include the affected endpoint or component, reproduction steps, impact, and a
minimal proof of concept. Maintainers should acknowledge a report within seven
days and coordinate disclosure after a fix is available.

## Deployment responsibilities

- Rotate any credential that has ever been pasted into chat, logs, tickets, or
  commits before using it with this project.
- Keep `.env` untracked and inject production secrets through a secret manager.
- Run the API behind TLS and an authenticated gateway before exposing it to
  untrusted users; this repository does not implement end-user authentication.
- Restrict egress and database privileges. The SQL tool enforces read-only
  syntax, and the database account should independently be read-only.
- Treat generated reports and uploaded files as potentially sensitive data;
  configure retention and volume encryption for production deployments.

The safeguards in this repository reduce risk but do not replace deployment
hardening, access control, audit policy, or provider-specific controls.
