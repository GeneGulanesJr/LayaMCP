# LayaMCP

HTTP MCP server that wraps the [Laya](https://github.com/NandhaKishorM/laya) decision engine for use with [Pi](https://pi.dev) (and any other MCP client).

## What it does

Exposes 11 tools to your agent — 5 upstream-preset + 6 coding-specific (custom question schemas):

| Tool                  | Purpose                                              | Latency  | Source     |
| --------------------- | ---------------------------------------------------- | -------- | ---------- |
| `laya_guard`          | Prompt-injection / jailbreak detection               | ~33 ms   | preset     |
| `laya_route`          | Decide "small model" vs "frontier model" per prompt  | ~33 ms   | preset     |
| `laya_moderate`       | Toxicity / harassment / threats                      | ~33 ms   | preset     |
| `laya_triage`         | Intent / urgency / churn / frustration (support)       | ~33 ms   | preset     |
| `laya_email`          | Email-specific intent / urgency / needs-reply        | ~33 ms   | preset     |
| `laya_review_tone`    | Code review tone + priority                           | ~33 ms   | custom     |
| `laya_bug_severity`   | Bug severity + area                                  | ~33 ms   | custom     |
| `laya_commit_classify`| Commit message type / scope / risk                    | ~33 ms   | custom     |
| `laya_test_priority`  | Test run priority + reason                            | ~33 ms   | custom     |
| `laya_secret_risk`    | Detect leaked credentials in text                    | ~33 ms   | custom     |
| `laya_diff_intent`    | PR diff intent / scope / risk                         | ~33 ms   | custom     |

All tools run in-process via Laya's encoder checkpoints (ModernBERT-large / mmBERT-base). One HTTP endpoint, single model load per process.

## Install

```bash
cd LayaMCP
pip install -e ".[dev]"
```

## Run

```bash
# Default: 127.0.0.1:8765
layamcp

# Or override via env:
LAYAMCP_PORT=9000 layamcp
```

## Configure Pi

Add to your Pi MCP config:

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

Pi will then see `laya_guard`, `laya_route`, `laya_moderate`, `laya_triage`, `laya_email` as native tools.

## Documentation

- **[AGENTS.md](AGENTS.md)** — instructions for AI coding agents working in this repo
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — layer diagram, data flow, performance
- **[docs/TOOLS.md](docs/TOOLS.md)** — per-tool behaviour, when to use, limitations
- **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)** — every env var, .env format, prod checklist
- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** — adding tools, code style, release checklist
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** — systemd, Docker, nginx reverse proxy
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** — common errors and fixes

## Adding a new tool

The architecture is plugin-style. To add a tool:

**1. Create `laya_mcp/tools/mytool.py`:**

```python
from pydantic import BaseModel, Field

from .base import Tool


class MyInput(BaseModel):
    text: str = Field(..., description="Input text.")


class MyOutput(BaseModel):
    label: str
    confidence: float


class MyTool(Tool):
    name = "laya_mytool"
    description = "One-line description shown to the agent."
    input_schema = MyInput
    output_schema = MyOutput

    async def run(self, bridge, text: str) -> MyOutput:
        raw = bridge.predict(text, preset="...")  # or build your own questions
        return MyOutput(label=..., confidence=...)
```

**2. Register it in `laya_mcp/tools/__init__.py`:**

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

That's it. The MCP wire schema, FastAPI route, dispatch table — all derive from the class. No other files need to change.

### Adding a custom preset (not from upstream)

If you want a tool that uses questions you defined yourself (not from `laya.presets`):

```python
from laya.common import build_sequence, render_options

MY_QUESTIONS = build_sequence(
    render_options(["yes", "no"], key="answer"),
    render_options(["low", "medium", "high"], key="priority"),
)

class MyTool(Tool):
    ...
    async def run(self, bridge, text: str) -> MyOutput:
        raw = bridge.predict_custom(text, questions=MY_QUESTIONS)
        ...
```

Add `predict_custom()` to `LayaBridge` (one method, see `bridge.py`).

## Tests

```bash
pytest
```

Tests use mocked bridges — no model loading required. Fast.

## License

Apache-2.0