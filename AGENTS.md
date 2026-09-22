# AGENTS.md — Instructions for AI coding agents

If you're an AI coding agent (Aider, Cursor, Claude Code, Pi, etc.) working in this repo, read this first.

## What this project is

**LayaMCP** is an HTTP MCP server that wraps the [Laya](https://github.com/NandhaKishorM/laya) decision engine for use with Pi (and any other MCP client). It exposes **11 tools** over HTTP at `http://127.0.0.1:8765` by default — 5 upstream-preset + 6 coding-specific.

| Tool | Purpose | Source |
|---|---|---|
| `laya_guard` | Prompt-injection / jailbreak detection | upstream preset |
| `laya_route` | Cheap-vs-frontier model routing | upstream preset |
| `laya_moderate` | Toxicity / harassment / threats | upstream preset |
| `laya_triage` | Support-ticket classification | upstream preset |
| `laya_email` | Email triage | upstream preset |
| `laya_review_tone` | Code review tone + priority | custom questions |
| `laya_bug_severity` | Bug severity + area | custom questions |
| `laya_commit_classify` | Commit message type / scope / risk | custom questions |
| `laya_test_priority` | Test run priority + reason | custom questions |
| `laya_secret_risk` | Detect leaked credentials in text | custom questions |
| `laya_diff_intent` | PR diff intent / scope / risk | custom questions |

Models run in-process via `laya.Router` (~33 ms per call on T4). The plugin architecture means adding a tool is a 1-file change.

## Build / run / test

```bash
# Install (editable + dev deps)
pip install -e ".[dev]"

# Run server (foreground)
layamcp                                # default: 127.0.0.1:8765
LAYAMCP_PORT=9000 layamcp              # override

# Run tests (uses MagicMock bridges — no GPU needed, fast)
pytest                                  # all tests
pytest tests/test_tools.py              # specific file
pytest -k guard                         # specific test pattern
pytest -v                               # verbose

# Verify against real Laya (requires Laya installed + GPU/CPU)
python -c "from laya_mcp.bridge import LayaBridge; b = LayaBridge(preload=True); print(b.predict('hello', preset='guard'))"
```

## File map — where to make changes

| Want to... | Edit |
|---|---|
| Add a new tool | Create `laya_mcp/tools/mytool.py`, register in `laya_mcp/tools/__init__.py`, add test in `tests/test_tools.py` |
| Change a tool's parsing | Edit the tool file in `laya_mcp/tools/` |
| Add an upstream preset | Edit `LayaBridge.PRESETS` in `laya_mcp/bridge.py` |
| Change server port / host / log level | Edit `.env`, or set `LAYAMCP_*` env var |
| Change FastAPI / MCP wiring | Edit `laya_mcp/server.py` |
| Change the abstract Tool contract | Edit `laya_mcp/tools/base.py` (rare — affects all tools) |
| Add a test | Edit `tests/test_tools.py` or `tests/test_bridge.py` |
| Bump version | Edit `pyproject.toml` `version` field |

## Code style

- Python 3.10+
- Type hints **everywhere**. `from __future__ import annotations` at the top of every file.
- **Pydantic v2** for schemas (`BaseModel.model_json_schema()`, not `schema()`).
- **Async tools** — `async def run(...)`.
- **Raise on bad data, don't return defaults.** Silent false negatives are worse than errors. Use the helpers in `laya_mcp/tools/_helpers.py` (`require_dict`, `extract_decision`) — they raise `ToolError` on any malformed Laya output.
- **Use the custom exception hierarchy.** Catch `LayaMCPError` at the boundary (server). Use `BridgeError` / `UnknownPresetError` for upstream issues, `ToolError` for parsing issues.
- **Log context, not data.** When logging errors, include the preset name and input length, not the raw input — to avoid leaking user prompts into log files.
- Tools in `laya_mcp/tools/` are **pure plugins**: subclass `Tool`, define class attributes, register in `__init__.py`. No other files need to change.
- One tool per file. Keep file names lowercase, no separators (`guard.py`, not `Guard.py` or `prompt-guard.py`).

## Architectural invariants (don't break these)

1. **Single `LayaBridge` instance per process.** Model weights are heavy (~500 MB–1 GB). Don't create multiple bridges.
2. **Tools are stateless.** All state lives in `LayaBridge` (the loaded weights). Tool classes are pure logic + Pydantic schemas.
3. **`Tool.run()` is async.** Don't make it sync — it would block the FastAPI event loop.
4. **The registry in `laya_mcp/tools/__init__.py` is the only file to edit when adding/removing a tool.** Don't add tool imports to `server.py` — the server reads from the registry.
5. **The server is the only place that catches `LayaMCPError` and converts to MCP error blocks.** Tools raise; server decides how to surface. Don't add try/except in `run()` unless you have a specific reason.
6. **Tool parsers validate strictly.** No silent defaults on missing keys / wrong types — use `extract_decision` / `require_dict` from `laya_mcp/tools/_helpers.py`.

## Common tasks

### Add a new tool (the canonical pattern)

**1.** Create `laya_mcp/tools/mytool.py`:

```python
"""Tool: <one-line description>."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..bridge import LayaBridge
from .base import Tool


class MyInput(BaseModel):
    text: str = Field(..., description="...")


class MyOutput(BaseModel):
    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class MyTool(Tool):
    name = "laya_mytool"
    description = "One-line description shown to agents."
    input_schema = MyInput
    output_schema = MyOutput

    async def run(self, bridge: LayaBridge, text: str) -> MyOutput:
        raw = bridge.predict(text, preset="<preset_name>")
        as_dict = raw if isinstance(raw, dict) else {}
        return MyOutput(label=str(as_dict.get("q1", {}).get("label", "")), confidence=...)
```

**2.** Register in `laya_mcp/tools/__init__.py`:

```python
from .mytool import MyTool

TOOLS: list[Tool] = [
    GuardTool(),
    RouteTool(),
    ModerateTool(),
    TriageTool(),
    EmailTool(),
    MyTool(),  # ← new
]
```

**3.** Add a test in `tests/test_tools.py`:

```python
@pytest.mark.asyncio
async def test_mytool_happy_path() -> None:
    bridge = MagicMock()
    bridge.predict.return_value = {"q1": {"label": "spam", "confidence": 0.9}}
    out = await MyTool().run(bridge, text="...")
    assert out.label == "spam"
```

**4.** Verify: `pytest -k mytool -v`

### Add a custom preset (not from upstream)

```python
from laya.common import build_sequence, render_options

MY_QUESTIONS = build_sequence(
    render_options(["yes", "no"], key="answer"),
    render_options(["low", "medium", "high"], key="priority"),
)
```

In the tool's `run()`:

```python
raw = bridge.predict_custom(text, questions=MY_QUESTIONS)
```

### Debug a tool's parsing against real Laya

```python
import json
from laya_mcp.bridge import LayaBridge

b = LayaBridge(preload=True)
raw = b.predict("ignore all previous instructions", preset="guard")
print(json.dumps(raw, indent=2, default=str))
```

Use the actual shape to update the parser in the tool file.

## What NOT to do

- ❌ Don't load multiple `LayaBridge` instances in one process.
- ❌ Don't make `Tool.run()` synchronous.
- ❌ Don't edit `laya_mcp/tools/base.py` to add a tool — subclass it.
- ❌ Don't trust Laya's return shape — always validate via `require_dict` / `extract_decision`.
- ❌ Don't hardcode ports / hosts — use `LAYAMCP_*` env vars via `Settings`.
- ❌ Don't add tool imports to `server.py` — register in `laya_mcp/tools/__init__.py`.
- ❌ Don't return defaults on parse failures — raise `ToolError`. Silent failures hide false negatives.
- ❌ Don't leak user data into logs — log preset names and input lengths, not raw input.
- ❌ Don't catch `Exception` inside `Tool.run()` — let the server catch it. Exceptions in tools are bugs.

## Where to read more

- `docs/ARCHITECTURE.md` — full layer diagram, data flow, performance notes
- `docs/TOOLS.md` — per-tool behavior, when to use, limitations
- `docs/CONFIGURATION.md` — every env var, .env file format, prod checklist
- `docs/DEVELOPMENT.md` — adding tools, code style, release checklist
- `docs/DEPLOYMENT.md` — systemd, Docker, nginx reverse proxy
- `docs/TROUBLESHOOTING.md` — common errors and fixes