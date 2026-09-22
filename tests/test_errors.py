"""Tests for error handling: bridge errors, tool parsing errors, server errors."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from laya_mcp.bridge import LayaBridge
from laya_mcp.errors import (
    BridgeError,
    LayaMCPError,
    ModelLoadError,
    ToolError,
    UnknownPresetError,
)
from laya_mcp.tools.email import EmailTool
from laya_mcp.tools.guard import GuardTool
from laya_mcp.tools.moderate import ModerateTool
from laya_mcp.tools.route import RouteTool
from laya_mcp.tools.triage import TriageTool


# ===========================================================================
# Bridge-level error tests
# ===========================================================================


def test_unknown_preset_raises_typed_error() -> None:
    """UnknownPresetError is a subclass of BridgeError and LayaMCPError."""
    bridge = LayaBridge(preload=False)
    with pytest.raises(UnknownPresetError) as exc_info:
        bridge.predict("hello", preset="bogus")
    # UnknownPresetError should be catchable as BridgeError too
    assert isinstance(exc_info.value, BridgeError)
    assert isinstance(exc_info.value, LayaMCPError)


def test_predict_wraps_upstream_runtime_error() -> None:
    """Any exception from Laya is wrapped as BridgeError."""
    bridge = LayaBridge(preload=False)
    bridge._default_agent = lambda: MagicMock(
        predict=MagicMock(side_effect=RuntimeError("GPU out of memory"))
    )
    with pytest.raises(BridgeError) as exc_info:
        bridge.predict("hello", preset="guard")
    # Original exception is chained
    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert "GPU out of memory" in str(exc_info.value.__cause__)


def test_predict_custom_wraps_upstream_error() -> None:
    bridge = LayaBridge(preload=False)
    bridge._default_agent = lambda: MagicMock(
        predict=MagicMock(side_effect=ValueError("bad input"))
    )
    with pytest.raises(BridgeError) as exc_info:
        bridge.predict_custom("hello", questions=None)
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_default_agent_failure_wrapped() -> None:
    """Failing to access the default agent is wrapped, not propagated raw."""
    bridge = LayaBridge(preload=False)
    # Force agent access to fail
    type(bridge.router).agents = property(MagicMock(side_effect=KeyError("english")))
    with pytest.raises(BridgeError):
        bridge.predict("hello", preset="guard")


# ===========================================================================
# Tool-level error tests
# ===========================================================================


@pytest.mark.asyncio
async def test_guard_raises_on_non_dict_raw() -> None:
    bridge = MagicMock()
    bridge.predict.return_value = "not a dict"
    with pytest.raises(ToolError, match="Expected dict"):
        await GuardTool().run(bridge, prompt="test")


@pytest.mark.asyncio
async def test_guard_raises_on_empty_dict() -> None:
    bridge = MagicMock()
    bridge.predict.return_value = {}
    with pytest.raises(ToolError, match="empty result"):
        await GuardTool().run(bridge, prompt="test")


@pytest.mark.asyncio
async def test_guard_raises_on_missing_label() -> None:
    bridge = MagicMock()
    bridge.predict.return_value = {"q1": {"confidence": 0.9}}
    with pytest.raises(ToolError, match="label"):
        await GuardTool().run(bridge, prompt="test")


@pytest.mark.asyncio
async def test_guard_raises_on_missing_confidence() -> None:
    bridge = MagicMock()
    bridge.predict.return_value = {"q1": {"label": "injection"}}
    with pytest.raises(ToolError, match="confidence"):
        await GuardTool().run(bridge, prompt="test")


@pytest.mark.asyncio
async def test_guard_raises_on_non_numeric_confidence() -> None:
    bridge = MagicMock()
    bridge.predict.return_value = {"q1": {"label": "injection", "confidence": "not-a-number"}}
    with pytest.raises(ToolError, match="not numeric"):
        await GuardTool().run(bridge, prompt="test")


@pytest.mark.asyncio
async def test_guard_propagates_bridge_error() -> None:
    """BridgeError from upstream propagates through the tool unchanged."""
    bridge = MagicMock()
    bridge.predict.side_effect = BridgeError("upstream Laya failed")
    with pytest.raises(BridgeError, match="upstream Laya failed"):
        await GuardTool().run(bridge, prompt="test")


@pytest.mark.asyncio
async def test_triage_raises_on_missing_dimension() -> None:
    bridge = MagicMock()
    bridge.predict.return_value = {
        "intent": {"label": "billing", "confidence": 0.9},
        # urgency missing!
        "churn": {"label": "low", "confidence": 0.7},
        "frustration": {"label": "low", "confidence": 0.6},
    }
    with pytest.raises(ToolError, match="urgency"):
        await TriageTool().run(bridge, text="...")


@pytest.mark.asyncio
async def test_moderate_raises_on_missing_dimension() -> None:
    bridge = MagicMock()
    bridge.predict.return_value = {
        "toxicity": {"label": "toxic", "confidence": 0.9},
        "harassment": {"label": "none", "confidence": 0.9},
        # threat missing!
    }
    with pytest.raises(ToolError, match="threat"):
        await ModerateTool().run(bridge, text="...")


@pytest.mark.asyncio
async def test_email_raises_on_non_dict_at_key() -> None:
    bridge = MagicMock()
    bridge.predict.return_value = {
        "intent": {"label": "fyi", "confidence": 0.9},
        "urgency": "not-a-dict",  # malformed!
        "needs_reply": {"label": "no", "confidence": 0.9},
    }
    with pytest.raises(ToolError, match="urgency"):
        await EmailTool().run(bridge, body="...")


@pytest.mark.asyncio
async def test_route_raises_on_bad_preset() -> None:
    """Bridge rejects unknown presets; tool propagates the error."""
    bridge = MagicMock()
    bridge.predict.side_effect = UnknownPresetError("nope")
    with pytest.raises(UnknownPresetError):
        await RouteTool().run(bridge, prompt="...")


# ===========================================================================
# Exception hierarchy sanity check
# ===========================================================================


def test_all_custom_errors_inherit_from_layamcperror() -> None:
    """Catch LayaMCPError to handle any project-specific failure."""
    for cls in [BridgeError, ModelLoadError, UnknownPresetError, ToolError]:
        assert issubclass(cls, LayaMCPError), f"{cls.__name__} must inherit from LayaMCPError"


def test_tool_error_carries_tool_name() -> None:
    err = ToolError("my_tool", "something went wrong")
    assert err.tool_name == "my_tool"
    assert "my_tool" in str(err)
    assert "something went wrong" in str(err)


def test_tool_error_chains_cause() -> None:
    original = ValueError("original problem")
    err = ToolError("my_tool", "wrapped", cause=original)
    assert err.cause is original
    assert err.__cause__ is original
    assert "original problem" in str(err)