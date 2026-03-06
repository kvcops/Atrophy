# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in atrophy, please report it responsibly.

**Do NOT open a public issue.** Instead, email the maintainers directly.

## Security Principles

atrophy follows these security principles:

1. **No shell injection** — All subprocess calls use `shell=False` with argument lists
2. **No secret leakage** — API keys are `SecretStr` and never logged, printed, or serialized
3. **No SQL injection** — All database access uses SQLAlchemy ORM with parameterized queries
4. **No pickle** — All serialization uses JSON + Pydantic
5. **No path traversal** — All user-supplied paths are resolved and bounds-checked
6. **No SSRF** — Ollama URL validated to localhost only; badge server binds to `127.0.0.1`
7. **No telemetry** — Zero data leaves the user's machine
8. **LLM output sanitized** — Markdown fences stripped, keys validated, types checked, fields truncated

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |
