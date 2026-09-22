# Tools reference

All tools run through `LayaBridge.predict(state, preset)` or `LayaBridge.predict_custom(state, questions)`. Each tool wraps a specific upstream Laya preset and parses the result into a typed Pydantic output schema.

## laya_guard

Detect prompt-injection / jailbreak attempts.

**Input:**
```python
class GuardInput(BaseModel):
    prompt: str
```

**Output:**
```python
class GuardOutput(BaseModel):
    is_injection: bool
    confidence: float    # 0.0–1.0
    details: dict        # raw Laya response
```

**When to use:** Before sending any untrusted text to the LLM. Run on:
- User-submitted prompts
- Email content from external senders
- Document content fetched from the web
- Tool return values containing user-controlled data

**Cost:** ~33 ms (T4). Much cheaper than asking a frontier model to check.

**Limitations:**
- Trained on a specific distribution of injection attacks. Novel attack vectors may evade it.
- Use as **one signal among many**, not the only signal.
- Pair with input length limits, output filtering, and privilege boundaries.

**Where the parser lives:** `laya_mcp/tools/guard.py`

---

## laya_route

Decide whether a prompt needs a small/cheap model or a frontier/smart model.

**Input:**
```python
class RouteInput(BaseModel):
    prompt: str
```

**Output:**
```python
class RouteOutput(BaseModel):
    tier: str            # "small" | "frontier"
    confidence: float    # 0.0–1.0
    details: dict
```

**When to use:** At the start of every agent turn, to pick a model. Saves API spend dramatically for trivial prompts ("hi", "thanks", "yes/no questions").

**Label normalisation:** Laya may return any of `frontier`/`large`/`smart`/`complex` (normalised to `frontier`) or anything else (normalised to `small`). Edit the `tier = ...` line in `laya_mcp/tools/route.py` if you observe a different vocabulary.

**Cost:** ~33 ms (T4). Saves potentially hundreds of milliseconds + dollars per call when routing to a small model.

**Where the parser lives:** `laya_mcp/tools/route.py`

---

## laya_triage

Classify a support ticket along four dimensions.

**Input:**
```python
class TriageInput(BaseModel):
    text: str
```

**Output:**
```python
class TriageOutput(BaseModel):
    intent: str          # billing, technical, account, ...
    urgency: str         # low, medium, high, critical
    churn_risk: str      # low, medium, high
    frustration: str     # low, medium, high
    confidence: float
    details: dict
```

**When to use:** First step in any support-ticket-handling workflow. After classifying, route to the right subagent based on `intent`.

**Cost:** ~33 ms.

**Label assumptions:** Tool parser assumes question keys are `"intent"`, `"urgency"`, `"churn"`, `"frustration"`. Verify against `tests/test_tools.py::test_triage_extracts_all_dimensions` and adjust if upstream uses different keys.

**Where the parser lives:** `laya_mcp/tools/triage.py`

---

## laya_moderate

Check text for toxicity, harassment, and threats.

**Input:**
```python
class ModerateInput(BaseModel):
    text: str
```

**Output:**
```python
class ModerateOutput(BaseModel):
    is_toxic: bool
    is_harassment: bool
    is_threat: bool
    confidence: float
    details: dict
```

**When to use:** Before any user-facing output is shown. Run on:
- Agent responses that get posted to public channels
- User-submitted content in community spaces
- Inbound messages from unknown senders

**Limitations:**
- Not a substitute for human moderation.
- False positives possible (sarcasm, reclaimed slurs, in-group speech).
- False negatives possible (especially for novel attacks or coded language).

**Where the parser lives:** `laya_mcp/tools/moderate.py`

---

## laya_email

Email-specific triage: intent, urgency, needs-reply.

**Input:**
```python
class EmailInput(BaseModel):
    body: str
```

**Output:**
```python
class EmailOutput(BaseModel):
    intent: str
    urgency: str
    needs_reply: bool
    confidence: float
    details: dict
```

**When to use:** First step in any inbox-management workflow. Run on each new email to decide if it needs attention.

**Label normalisation:** `needs_reply` is `True` when Laya's label is `yes` / `true` / `1`. Adjust in `laya_mcp/tools/email.py` if you observe different labels.

**Cost:** ~33 ms.

**Where the parser lives:** `laya_mcp/tools/email.py`

---

## Error handling

Tools **raise on any unexpected Laya output** rather than returning silent defaults. The server catches these and returns them as MCP error content blocks (with `isError=true`).

### Exception hierarchy

```
LayaMCPError            (catch this for any project-specific failure)
├── ModelLoadError       (Laya weights couldn't load)
├── UnknownPresetError  (tool requested a preset that doesn't exist)
└── BridgeError         (upstream Laya call failed: GPU OOM, runtime error, etc.)
```

`ToolError` (also extends `LayaMCPError`) is raised when a tool's parser can't extract what it needs from Laya's response. It carries the tool name and an optional `cause`.

### When a tool raises

| Failure                                        | Raised by      | Server response to client                  |
| ---------------------------------------------- | -------------- | ------------------------------------------ |
| Upstream Laya raises (GPU OOM, runtime error)  | `BridgeError`  | MCP error block: `"[laya_guard] Laya predict failed (preset='guard', state_len=12)"` |
| Tool requested a preset not in `LayaBridge.PRESETS` | `UnknownPresetError` | MCP error block: `"[laya_guard] Unknown preset 'bogus'. Choose from [...]"` |
| Laya returned a non-dict                       | `ToolError`    | MCP error block: `"[laya_guard] Expected dict from Laya, got str: 'oops'"` |
| Laya returned an empty dict                    | `ToolError`    | MCP error block: `"[laya_guard] Laya returned an empty result."` |
| Expected key missing in Laya output            | `ToolError`    | MCP error block: `"[laya_guard] Missing expected key 'q1' in Laya result. Got keys: []"` |
| Confidence isn't numeric                       | `ToolError`    | MCP error block: `"[laya_guard] Confidence at 'q1' is not numeric: 'NaN'"` |
| Tool input fails schema validation             | `ValidationError` (Pydantic) | MCP error block: `"Invalid input for laya_guard: ..."` |
| Unknown tool name                              | (server-side)  | MCP error block: `"Unknown tool 'foo'. Available: ['laya_guard', ...]"` |

### What the server logs

All `LayaMCPError`s are logged with **full traceback** at `ERROR` level, including the input keys (never values — to avoid leaking prompts):

```
2024-01-15 12:34:56 ERROR laya_mcp.server Tool laya_guard failed (input_keys=['prompt']): [laya_guard] Expected dict from Laya, got str: 'oops'
Traceback (most recent call last):
  ...
```

Unexpected exceptions (not `LayaMCPError`) are also logged with traceback, but the **caller sees only** `"Internal error in laya_guard. Check server logs."` to prevent leaking internals.

### Why strict parsing?

The defensive parser in earlier versions returned `is_injection=False` / `confidence=0.0` on any malformed shape — which silently produced false negatives. A prompt-injection detector that always says "no injection" is worse than one that errors out, because the caller can react to an error (retry, log, escalate) but can't react to silent false negatives.

If you see a `ToolError` in production, that means Laya's output drifted from the assumed schema. Fix the parser in the relevant tool file.

### Adjusting parser strictness

If you'd rather have lenient defaults for a specific tool (e.g., you trust Laya's output for that preset), edit the tool file in `laya_mcp/tools/` and replace `extract_decision(...)` with manual extraction that returns defaults on missing keys. The shared helpers in `laya_mcp/tools/_helpers.py` are convenient but not mandatory.

---

## Adding a new tool

See `AGENTS.md` → "Common tasks → Add a new tool" for the canonical pattern. The summary:

1. Create `laya_mcp/tools/mytool.py` with `MyInput`, `MyOutput`, `MyTool(Tool)`.
2. Register in `laya_mcp/tools/__init__.py`.
3. Add a test in `tests/test_tools.py`.

That's it. Schema, route, and dispatch derive from the class.

## Adding a new upstream preset

If Laya ships a new preset you want to expose:

1. Add it to `LayaBridge.PRESETS` in `laya_mcp/bridge.py`:
   ```python
   from laya.presets import my_new_questions
   PRESETS["my_new_preset"] = my_new_questions
   ```
2. Create a tool file + register.

## Verifying tool output against real Laya

```python
import json
from laya_mcp.bridge import LayaBridge

b = LayaBridge(preload=True)
raw = b.predict("some test input", preset="guard")
print(json.dumps(raw, indent=2, default=str))
```

Use this to see the actual shape and adjust tool parsers. No mocks — runs against the real model.