# Troubleshooting

## Server won't start

### `Address already in use`

Port 8765 is taken. Either:
- Stop the conflicting process, or
- `LAYAMCP_PORT=9000 layamcp`

Find what's using the port:

```bash
# Linux / macOS
lsof -i :8765
ss -tlnp | grep 8765

# Windows
netstat -ano | findstr :8765
```

### `ModuleNotFoundError: No module named 'laya'`

Laya isn't installed. `[dev]` extra doesn't include it. Install:

```bash
pip install laya>=0.3.5
```

Or include it in `pyproject.toml` `dependencies` (it already is — confirm the install succeeded):

```bash
pip install -e ".[dev]"
pip show laya    # verify
```

### `ModuleNotFoundError: No module named 'mcp'`

The MCP SDK isn't installed:

```bash
pip install "mcp[server]>=1.0"
```

### Model fails to download on first run

First run downloads model weights from HuggingFace (~500 MB–1 GB). Requires:
- Network access to `huggingface.co`
- ~2 GB free disk space in your HF cache (`~/.cache/huggingface/` on Linux/Mac, `%USERPROFILE%\.cache\huggingface\` on Windows)

If behind a firewall, pre-download on a connected machine:

```bash
pip install huggingface_hub
huggingface-cli download convaiinnovations/laya
huggingface-cli download convaiinnovations/laya-multilingual
huggingface-cli download convaiinnovations/laya-typed-decisions
```

Then copy `~/.cache/huggingface/` to the target machine.

### `ImportError: cannot import name 'create_fastapi_app' from 'mcp.server.fastapi'`

The `mcp[server]` SDK API may have changed between versions. Check your installed version:

```bash
pip show mcp
```

Then check the actual exports:

```python
python -c "import mcp.server.fastapi; print(dir(mcp.server.fastapi))"
```

Adjust the imports in `laya_mcp/server.py` to match.

## Tool returns wrong shape

Laya's return format may have changed (or differ from what your parser expects). Run a real call and inspect:

```python
import json
from laya_mcp.bridge import LayaBridge

b = LayaBridge(preload=True)
raw = b.predict("test input", preset="guard")
print(json.dumps(raw, indent=2, default=str))
```

Then adjust the parser in the relevant tool file (e.g. `laya_mcp/tools/guard.py`).

The tool parsers are intentionally defensive (`if isinstance(raw, dict)`) so they don't crash on unexpected shapes — they just return empty/default values. That means **silent wrong results**, not crashes. If a tool seems to always return `is_injection=False` or similar, inspect the raw output.

## Tests fail

### `pytest` says no tests collected

Make sure you're in the project root and `tests/` is reachable. Pytest config in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### Import errors in tests

Reinstall in editable mode:

```bash
pip install -e ".[dev]"
```

### `RuntimeWarning: coroutine '...' was never awaited`

You forgot `await` on an async tool call. Tool `run()` methods are async — always `await tool.run(...)`.

## Pi can't connect

### Check the server is up

```bash
curl http://127.0.0.1:8765/health
```

Should return `{"status": "ok"}` or similar.

### Check Pi's MCP config

```json
{
  "mcpServers": {
    "layamcp": {
      "type": "http",
      "url": "http://127.0.0.1:8765"
    }
  }
}
```

Common mistakes:
- Wrong port
- `type` should be `"http"` (not `"stdio"` or `"sse"` for the standard MCP HTTP transport)
- URL must be reachable from Pi's environment
- Trailing slash in URL (`8765/` vs `8765`) — both usually work but check

### Check the firewall

On localhost binds (`127.0.0.1`), firewall usually isn't an issue. If you bind to `0.0.0.0`:

```bash
# Linux (ufw)
sudo ufw allow 8765/tcp

# Linux (firewalld)
sudo firewall-cmd --permanent --add-port=8765/tcp
sudo firewall-cmd --reload
```

## Slow first call

First call loads model weights from disk (~2–5 seconds). Subsequent calls are ~33 ms.

To pre-load at boot:

```bash
LAYAMCP_PRELOAD_MODELS=true layamcp    # default
```

If pre-loading is slow, you may be on a slow disk or the model cache isn't warm. Check:

```bash
du -sh ~/.cache/huggingface/
```

## High memory usage

Each loaded checkpoint is ~500 MB–1 GB. The Router holds them in VRAM. To cap:

```python
# laya_mcp/bridge.py — keep only one loaded at a time
self.router = Router(preload=preload, max_loaded=1)
```

Or run with `LAYAMCP_PRELOAD_MODELS=false` so weights load on demand and can be evicted.

## OOM / CUDA out of memory

The checkpoint is too big for your GPU. Options:
- Use a smaller checkpoint (English-only, not multilingual)
- Reduce `max_loaded`
- Run on CPU (`CUDA_VISIBLE_DEVICES="" layamcp`) — slower but no VRAM cap

## Tool registry empty / new tool not appearing

If you added a tool but it's not in `tools/list`:

1. **Did you register it?** Check `laya_mcp/tools/__init__.py`:
   ```python
   TOOLS = [..., MyTool()]
   ```
2. **Did you restart the server?** The registry is read at import time, not per-request.
3. **Are there import errors?** Check the server logs. A broken tool file can fail the whole `__init__.py` import, leaving the registry broken.

```bash
LAYAMCP_LOG_LEVEL=DEBUG layamcp
```

Look for tracebacks on startup.

## Getting help

- Check the upstream [Laya repo](https://github.com/NandhaKishorM/laya) for upstream API questions.
- Check the [MCP spec](https://modelcontextprotocol.io) for protocol questions.
- File an issue in this repo for project-specific questions.

---

## Tool returns an error instead of a result

Tools raise `ToolError` on any malformed Laya output. The server returns these as MCP error content blocks. To diagnose:

### 1. Read the error message

The error includes context:

```
[laya_guard] Missing expected key 'q1' in Laya result. Got keys: ['injection_check']
```

This tells you Laya's actual question key is `injection_check`, not the assumed `q1`.

### 2. Inspect the raw Laya output

```python
import json
from laya_mcp.bridge import LayaBridge

b = LayaBridge(preload=True)
raw = b.predict("test input", preset="guard")
print(json.dumps(raw, indent=2, default=str))
```

### 3. Fix the parser

Either:
- Update the key name in the tool file (e.g., change `"q1"` to `"injection_check"` in `laya_mcp/tools/guard.py`).
- Or accept multiple shapes with a fallback:

  ```python
  first = extract_decision(raw, "q1", self.name)
  if first is None:
      first = extract_decision(raw, "injection_check", self.name)
  ```

### 4. Add a regression test

Add the new key name to `tests/test_tools.py` so the fix sticks:

```python
@pytest.mark.asyncio
async def test_guard_with_alternate_key():
    bridge = MagicMock()
    bridge.predict.return_value = {"injection_check": {"label": "injection", "confidence": 0.9}}
    out = await GuardTool().run(bridge, prompt="...")
    assert out.is_injection is True
```

---

## Server keeps running but every tool call fails

If all tool calls return errors but the server itself is up:

### 1. Check the bridge loaded successfully

Look at startup logs for `ModelLoadError`:

```
ModelLoadError: Failed to initialize Laya Router (preload=true): ...
```

If you see this, the model weights couldn't load — see "Model fails to download on first run" above.

### 2. Run with `DEBUG` logging

```bash
LAYAMCP_LOG_LEVEL=DEBUG layamcp
```

Look for tracebacks on the failed calls.

### 3. Verify Laya works outside the server

```python
from laya_mcp.bridge import LayaBridge
b = LayaBridge(preload=True)
print(b.predict("test", preset="guard"))
```

If this fails, the problem is upstream (Laya itself), not the server.

---

## Pydantic ValidationError on tool call

Means the inputs you sent don't match the tool's input schema. The error message tells you which field is wrong:

```
Invalid input for laya_guard: 1 validation error for GuardInput
prompt
  Input should be a valid string [type=string_type, input_value=None, input_type=None]
```

Fix the client (Pi) to pass the right argument name and type. Each tool's input schema is in `laya_mcp/tools/<tool>.py`:

- `laya_guard`: `{"prompt": str}`
- `laya_route`: `{"prompt": str}`
- `laya_triage`: `{"text": str}`
- `laya_moderate`: `{"text": str}`
- `laya_email`: `{"body": str}`

---

## Server logs are too noisy / too quiet

Adjust `LAYAMCP_LOG_LEVEL`:

- `DEBUG` — verbose, includes every event
- `INFO` — startup, tool calls (default)
- `WARNING` — only invalid input, unknown tools
- `ERROR` — only failures (recommended for production)

```bash
LAYAMCP_LOG_LEVEL=ERROR layamcp
```