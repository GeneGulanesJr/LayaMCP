"""HTTP MCP server entry point.

Run with:

    uvicorn laya_mcp.server:app --host 127.0.0.1 --port 8765
    # or
    layamcp           # console script defined in pyproject.toml
    # or
    python -m laya_mcp.server

The MCP server is built on top of the official ``mcp[server]`` SDK and
exposes the registered tools from :mod:`laya_mcp.tools` over HTTP/SSE.

Error handling
--------------

Three error categories are handled distinctly:

1. **Unknown tool / invalid input** — protocol-level error returned to
   the caller. Doesn't log a traceback (just the message).
2. **Tool / bridge error** (any :class:`LayaMCPError`) — the call is
   returned as MCP content with ``isError=true``. Logged with full
   traceback so operators can debug.
3. **Unexpected error** (anything else) — returned as a generic MCP
   error block ("Internal error. Check server logs."). Full traceback
   logged but **never** returned to the caller — avoid leaking
   internals (file paths, library names, host info).
"""
from __future__ import annotations

import logging
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from pydantic import ValidationError

from .bridge import LayaBridge
from .config import settings
from .errors import LayaMCPError
from .tools import TOOLS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Single bridge instance — model loaded once per process.
# ---------------------------------------------------------------------------
bridge = LayaBridge(preload=settings.preload_models)


# ---------------------------------------------------------------------------
# MCP server with dynamic tool registration from the TOOLS registry.
# ---------------------------------------------------------------------------
server: Server = Server("layamcp")


@server.list_tools()
async def _list_tools():
    """Return all registered tools to MCP clients."""
    return [t.to_mcp_schema() for t in TOOLS]


@server.call_tool()
async def _call_tool(name: str, arguments: dict) -> list[dict]:
    """Dispatch an MCP tool call with full error handling.

    Errors are returned as MCP content blocks (not raised) so the
    server stays alive and clients get a structured error to react to.
    """
    tool = next((t for t in TOOLS if t.name == name), None)
    if tool is None:
        available = [t.name for t in TOOLS]
        logger.warning("Unknown tool requested: %r (available: %s)", name, available)
        return [_error_block(f"Unknown tool {name!r}. Available: {available}")]

    # Validate inputs against the tool's Pydantic schema.
    try:
        validated = tool.input_schema(**arguments)
    except ValidationError as e:
        logger.warning("Tool %s got invalid input: %s", name, e)
        return [_error_block(f"Invalid input for {name}: {e}")]

    # Run the tool. Any LayaMCPError is logged with traceback + returned
    # as MCP error block. Any other exception is treated as a bug —
    # logged with full traceback but a generic message returned.
    try:
        result = await tool.run(bridge, **validated.model_dump())
        return [_result_block(result)]
    except LayaMCPError as e:
        logger.error(
            "Tool %s failed (input_keys=%s): %s",
            name,
            sorted(arguments),
            e,
            exc_info=True,
        )
        return [_error_block(str(e))]
    except Exception:
        logger.exception("Unexpected error in tool %s", name)
        return [_error_block(f"Internal error in {name}. Check server logs.")]


# ---------------------------------------------------------------------------
# MCP wire-format helpers
# ---------------------------------------------------------------------------


def _result_block(result: Any) -> dict:
    """Format a successful Pydantic result as an MCP text content block."""
    if hasattr(result, "model_dump_json"):
        text = result.model_dump_json()
    else:
        text = str(result)
    return {"type": "text", "text": text}


def _error_block(message: str) -> dict:
    """Format an error message as an MCP text content block with ``isError``."""
    return {"type": "text", "text": message, "isError": True}


# ---------------------------------------------------------------------------
# Plain FastAPI app with MCP SSE transport mounted manually + /health.
#
# Spec §9 / research 2026-09-22: mcp.server.fastapi.create_fastapi_app was
# removed in mcp 1.x and is broken on every released SDK today. Use the
# SSE transport directly on a plain FastAPI app. The /health endpoint
# is auth-exempt so the Docker healthcheck can probe TCP port-open
# ≈ models-resident (per spec §9 + the Phase 4 infra/smoke.sh contract).
# ---------------------------------------------------------------------------
sse = SseServerTransport("/messages/")
app = FastAPI(title="layamcp")


@app.get("/health")
async def health() -> dict[str, Any]:
    """TCP-port-open ≈ models-resident (models loaded at module import).

    spec §9: 'TCP healthcheck (port-open ≈ models-resident)' — if we
    answered, the models are loaded. No internal state to expose.
    """
    return {"status": "ok", "tools": len(TOOLS)}


@app.get("/sse")
async def sse_endpoint(request: Request) -> None:
    """MCP SSE endpoint. Clients open this for the event stream."""
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


@app.post("/messages/")
async def messages_endpoint(request: Request) -> None:
    """MCP client → server POST endpoint (paired with /sse)."""
    await sse.handle_post_message(request.scope, request.receive, request._send)


def main() -> None:
    """Console-script entry point: ``layamcp``."""
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info(
        "Starting LayaMCP on http://%s:%d (tools=%d)",
        settings.host,
        settings.port,
        len(TOOLS),
    )
    uvicorn.run(
        "laya_mcp.server:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()