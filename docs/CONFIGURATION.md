# Configuration

All settings are env-overridable via the `LAYAMCP_` prefix. Defaults are defined in `laya_mcp/config.py`.

## Settings reference

| Setting                    | Env var                       | Default       | Description                                                                                  |
| -------------------------- | ----------------------------- | ------------- | -------------------------------------------------------------------------------------------- |
| `host`                     | `LAYAMCP_HOST`                | `127.0.0.1`   | Bind address. Use `0.0.0.0` for network access (behind a reverse proxy with auth).          |
| `port`                     | `LAYAMCP_PORT`                | `8765`        | HTTP port. Avoid conflicts with common services (5432 Postgres, 6379 Redis, 8080 alt-http). |
| `preload_models`           | `LAYAMCP_PRELOAD_MODELS`      | `true`        | Load model weights at startup. `false` defers to first call (slower first request).         |
| `log_level`                | `LAYAMCP_LOG_LEVEL`           | `INFO`        | Python logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`.                                 |

## `.env` file

Create `.env` in the project root:

```bash
LAYAMCP_HOST=127.0.0.1
LAYAMCP_PORT=8765
LAYAMCP_PRELOAD_MODELS=true
LAYAMCP_LOG_LEVEL=INFO
```

Pydantic-settings auto-loads it. The `.env` file is gitignored — safe for local overrides.

See `.env.example` for the canonical template.

## Override at runtime

```bash
LAYAMCP_PORT=9000 layamcp
LAYAMCP_LOG_LEVEL=DEBUG layamcp
LAYAMCP_HOST=0.0.0.0 LAYAMCP_PORT=8765 layamcp
```

## Network access (multi-client)

By default, the server binds to `127.0.0.1` (localhost only). To expose to other machines on your network:

```bash
LAYAMCP_HOST=0.0.0.0 layamcp
```

⚠️ **No built-in auth.** Don't expose to the public internet without putting a reverse proxy with auth in front (see `docs/DEPLOYMENT.md`).

## Pre-loading vs lazy-loading models

| `LAYAMCP_PRELOAD_MODELS` | Behaviour                                                              | Trade-off                                                                                    |
| ------------------------ | ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `true` (default)         | Model weights load at process start                                    | First user request is fast (~33 ms). Process startup is slow (~2–5 s).                      |
| `false`                  | Model weights load on first tool call                                  | Process startup is fast. First tool call is slow (~2–5 s). Better for dev / batch jobs.    |

## Production checklist

- [ ] Bind to `127.0.0.1` unless you need network access.
- [ ] Put behind reverse proxy with auth if exposing externally.
- [ ] Set `LAYAMCP_LOG_LEVEL=WARNING` (or `ERROR`) for production.
- [ ] Use a process manager (systemd / Docker / supervisord) so it restarts on crash.
- [ ] Pre-load models (`LAYAMCP_PRELOAD_MODELS=true`) so the first user request is fast.
- [ ] Monitor `/health` endpoint (see `docs/DEPLOYMENT.md`).
- [ ] Send logs to a log aggregator (Vector, Loki, Datadog).

## Adding new settings

1. Add a field to `Settings` in `laya_mcp/config.py`.
2. Use it via `settings.<field>` anywhere.
3. Document it here.

Pydantic-settings will pick up the matching `LAYAMCP_<FIELD_UPPER>` env var automatically.