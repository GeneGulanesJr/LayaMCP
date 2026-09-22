# Architecture

## Layer diagram

```
┌──────────────────────────────────────────────┐
│  MCP clients                                 │
│  • Pi (TUI / chat)                          │
│  • Future web UI / IDE / Slack bot / etc.   │
└────────────────┬─────────────────────────────┘
                 │ HTTP MCP (JSON-RPC 2.0)
                 ▼
┌──────────────────────────────────────────────┐
│  FastAPI app  (laya_mcp.server:app)          │
│  ┌────────────────────────────────────────┐  │
│  │  POST /mcp  (JSON-RPC 2.0 endpoint)  │  │
│  │  - initialize                        │  │
│  │  - tools/list                        │  │
│  │  - tools/call                        │  │
│  └────────────────────────────────────────┘  │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│  Tool registry  (laya_mcp.tools.TOOLS)       │
│  • GuardTool                                 │
│  • RouteTool                                 │
│  • TriageTool                                │
│  • ModerateTool                              │
│  • EmailTool                                 │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│  LayaBridge  (laya_mcp.bridge)               │
│  • Single Router instance                   │
│  • Holds loaded model weights               │
│  • predict(state, preset)        → dict      │
│  • predict_custom(state, qs)     → dict      │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────┐
│  Laya library  (NandhaKishorM/laya)          │
│  • Router picks English / Multilingual /    │
│    typed-decisions based on script detect   │
│  • 5 preset question schemas                │
│  • ~33 ms / call on T4                      │
└──────────────────────────────────────────────┘
```

## Component responsibilities

### `laya_mcp/server.py` — HTTP transport

- Owns the single `LayaBridge` instance (loaded at import time).
- Mounts MCP routes via the `mcp[server]` SDK.
- Translates JSON-RPC 2.0 requests to Python calls.
- Returns tool results as MCP `content` blocks.

### `laya_mcp/bridge.py` — upstream Laya wrapper

- Owns the `laya.Router` (which owns all loaded agents).
- Exposes `predict(state, preset)` for the 5 upstream presets.
- Exposes `predict_custom(state, questions)` for custom question schemas.
- Centralizes model lifecycle so weights load **exactly once per process**.

### `laya_mcp/config.py` — settings

- `Settings` via `pydantic-settings`.
- Env-overridable via `LAYAMCP_*` prefix.
- Defaults: `127.0.0.1:8765`, `preload=True`, `INFO` logs.

### `laya_mcp/tools/base.py` — `Tool` ABC

- Defines the contract for any tool:
  - `name` (str)
  - `description` (str)
  - `input_schema` (Pydantic model)
  - `output_schema` (Pydantic model)
  - `async run(bridge, **kwargs)`
  - `to_mcp_schema()`

### `laya_mcp/tools/*.py` — tool implementations

- One file per tool.
- Each parses Laya's raw dict output into its own `*Output` Pydantic schema.
- Pure plugins — easy to add, easy to remove, easy to test in isolation.

### `laya_mcp/tools/__init__.py` — registry

- A single `TOOLS: list[Tool]` of instantiated tool objects.
- Order = display order in MCP `tools/list`.
- **The only file to edit when adding or removing a tool.**

## Data flow per tool call

1. **Pi** sends `tools/call` JSON-RPC request → FastAPI route.
2. **Server** dispatches to `Tool.run(bridge, **arguments)`.
3. **Tool** calls `bridge.predict(state, preset)` or `bridge.predict_custom(state, questions)`.
4. **Bridge** picks the right agent via `laya.Router` (script-detection-based).
5. **Agent** runs in ~33 ms, returns a dict shaped roughly like:
   ```python
   {
       "<question_key>": {"label": "...", "confidence": 0.x, ...},
       ...
   }
   ```
6. **Tool** parses the dict into its `*Output` Pydantic model.
7. **Server** serializes the result back as MCP `content` blocks.

## Adding new tools

See `AGENTS.md` → "Common tasks → Add a new tool" for the canonical pattern.

The pattern is:
- **One file** in `laya_mcp/tools/`.
- **Two lines** in `laya_mcp/tools/__init__.py` (import + register).
- **One test** in `tests/test_tools.py`.

No other changes. Schema, route, and dispatch all derive from the class.

## Performance characteristics

| Operation                | Latency (T4) | Notes                                  |
| ------------------------ | ------------ | -------------------------------------- |
| First call (cold start)  | 2–5 s        | Model load from disk                   |
| Subsequent calls         | ~33 ms       | Single forward pass                    |
| Multilingual input       | ~33 ms       | Router picks `mmBERT-base` checkpoint  |
| Typed-decisions input    | ~33 ms       | Router picks `typed-decisions` fine-tune |
| Concurrent requests      | serialized   | Single forward pass at a time (MPS/CUDA queue) |

The model load happens **once per process** at `LayaBridge(preload=True)` in `server.py`. To defer load until first call, set `LAYAMCP_PRELOAD_MODELS=false`.

To cap memory if multiple checkpoints would exceed VRAM:

```python
# laya_mcp/bridge.py
self.router = Router(preload=preload, max_loaded=1)  # keep one loaded at a time
```

## Security

- **No built-in auth.** Don't bind to `0.0.0.0` without putting a reverse proxy with auth in front (see `docs/DEPLOYMENT.md`).
- **No rate limiting.** Add at the reverse-proxy layer.
- **Tool inputs are arbitrary text.** Laya's prompts can be adversarial. The `laya_guard` tool is meant to detect this — consider running it on any text that originated from outside your system.

## Extensibility points

| To add... | Touch this file |
|---|---|
| A new tool | `laya_mcp/tools/mytool.py` + register in `__init__.py` |
| A new upstream preset | `laya_mcp/bridge.py` (`PRESETS` dict) |
| A custom question schema (not from upstream) | `bridge.predict_custom(state, questions)` |
| A new FastAPI route outside MCP | `laya_mcp/server.py` |
| New settings | `laya_mcp/config.py` |
| New tool categories (e.g., group "guardrails" vs "routing") | Refactor `tools/` into subpackages |

The plugin pattern means most extensions are **1 file + 2 lines**.