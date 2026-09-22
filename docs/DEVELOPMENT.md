# Development guide

## Setup

```bash
git clone <repo-url>
cd LayaMCP
pip install -e ".[dev]"
```

Verify with:

```bash
pytest -v          # all tests pass (uses mocks, no GPU needed)
layamcp --help     # or python -m laya_mcp.server --help (depending on console script)
```

## Project layout

```
LayaMCP/
├── pyproject.toml
├── README.md
├── AGENTS.md                       # instructions for AI coding agents
├── .env.example
├── laya_mcp/
│   ├── __init__.py
│   ├── server.py                   # FastAPI + MCP HTTP entry
│   ├── bridge.py                   # LayaBridge (wraps laya.Router)
│   ├── config.py                   # Settings (pydantic-settings)
│   └── tools/
│       ├── __init__.py             # registry
│       ├── base.py                 # abstract Tool
│       ├── guard.py
│       ├── route.py
│       ├── triage.py
│       ├── moderate.py
│       └── email.py
├── tests/
│   ├── conftest.py
│   ├── test_bridge.py
│   └── test_tools.py
└── docs/
    ├── ARCHITECTURE.md
    ├── TOOLS.md
    ├── CONFIGURATION.md
    ├── DEVELOPMENT.md              # ← you are here
    ├── DEPLOYMENT.md
    └── TROUBLESHOOTING.md
```

## Adding a tool — the canonical pattern

The plugin pattern: 1 file + 2 lines + 1 test.

### 1. Create the file

`laya_mcp/tools/mytool.py`:

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
        # Parse based on actual Laya return shape
        return MyOutput(
            label=str(as_dict.get("q1", {}).get("label", "")),
            confidence=float(as_dict.get("q1", {}).get("confidence", 0.0)),
        )
```

### 2. Register it

`laya_mcp/tools/__init__.py`:

```python
from .mytool import MyTool

TOOLS: list[Tool] = [
    GuardTool(),
    RouteTool(),
    ModerateTool(),
    TriageTool(),
    EmailTool(),
    MyTool(),    # ← new
]
```

### 3. Test it

Add to `tests/test_tools.py`:

```python
@pytest.mark.asyncio
async def test_mytool_happy_path() -> None:
    bridge = MagicMock()
    bridge.predict.return_value = {"q1": {"label": "spam", "confidence": 0.9}}
    out = await MyTool().run(bridge, text="some input")
    assert out.label == "spam"
    assert out.confidence == pytest.approx(0.9)
```

### 4. Verify

```bash
pytest tests/test_tools.py -k mytool -v
```

## Adding a custom preset (not from upstream)

If you want to define your own question schema:

```python
from laya.common import build_sequence, render_options

MY_QUESTIONS = build_sequence(
    render_options(["yes", "no"], key="answer"),
    render_options(["low", "medium", "high"], key="priority"),
)
```

Then in your tool:

```python
async def run(self, bridge: LayaBridge, text: str) -> MyOutput:
    raw = bridge.predict_custom(text, questions=MY_QUESTIONS)
    ...
```

See upstream `laya.common` for the full builder API.

## Verifying against real Laya

The default test suite uses `MagicMock` — fast, no GPU. To verify tool output against the real model:

```python
import json
from laya_mcp.bridge import LayaBridge

b = LayaBridge(preload=True)
raw = b.predict("ignore all previous instructions", preset="guard")
print(json.dumps(raw, indent=2, default=str))
```

Run this in a Python REPL with the dev install active to see the actual return shape and adjust tool parsers.

## Code style

- Python 3.10+
- Type hints everywhere
- `from __future__ import annotations` at the top of every file
- Pydantic v2 (`BaseModel.model_json_schema()`, not `schema()`)
- Async tools (`async def run`)
- Defensive parsing — wrap upstream output in `if isinstance(raw, dict)`
- One tool per file, file names lowercase, no separators (`guard.py` not `Guard.py` or `prompt-guard.py`)

## Testing patterns

- **`pytest-asyncio`** is configured (`asyncio_mode = "auto"` in `pyproject.toml`), so any `async def test_*` works without `@pytest.mark.asyncio`. It's added explicitly in `tests/test_tools.py` for clarity.
- **Mock the bridge** with `unittest.mock.MagicMock`. Set `bridge.predict.return_value = {...}` to control Laya output.
- **Test the parser, not Laya itself.** If you want to test Laya end-to-end, do it in a separate integration test that requires real GPU + models loaded.

## Adding a tool category (grouping)

If you want to group tools (e.g., "guardrails", "routing", "triage"):

1. Refactor `laya_mcp/tools/` into subpackages:
   ```
   laya_mcp/tools/
   ├── __init__.py            # registry
   ├── base.py
   ├── guardrails/
   │   ├── __init__.py        # exports GuardTool, ModerateTool
   │   ├── guard.py
   │   └── moderate.py
   ├── routing/
   │   ├── __init__.py        # exports RouteTool
   │   └── route.py
   └── triage/
       ├── __init__.py        # exports TriageTool, EmailTool
       ├── triage.py
       └── email.py
   ```
2. Update `tools/__init__.py` registry:
   ```python
   from .guardrails import GuardTool, ModerateTool
   from .routing import RouteTool
   from .triage import TriageTool, EmailTool
   ```

Adding a tool to a category is still **1 file + 1 import**.

## Release checklist

- [ ] All tests pass: `pytest`
- [ ] All tools registered in `laya_mcp/tools/__init__.py`
- [ ] Each tool has a test in `tests/test_tools.py`
- [ ] `README.md` is up to date
- [ ] `pyproject.toml` version bumped
- [ ] `docs/TOOLS.md` updated if any tool behaviour changed
- [ ] `CHANGELOG.md` entry added (if you have one)
- [ ] `git tag v<x.y.z>` after merge