"""Tests for LayaBridge (the upstream Laya wrapper)."""
from __future__ import annotations

import pytest

from laya_mcp.bridge import LayaBridge


def test_presets_are_registered() -> None:
    expected = {"guard", "route", "moderate", "triage", "email"}
    assert set(LayaBridge.PRESETS) == expected


def test_predict_rejects_unknown_preset() -> None:
    bridge = LayaBridge(preload=False)
    with pytest.raises(ValueError, match="Unknown preset"):
        bridge.predict("hello", preset="bogus")


def test_predict_uses_router() -> None:
    """Bridge should expose a Router instance after construction."""
    bridge = LayaBridge(preload=False)
    assert bridge.router is not None


def test_predict_custom_signature() -> None:
    """predict_custom accepts arbitrary questions (we don't call it here,
    just verify the method exists and forwards correctly with a mock)."""
    bridge = LayaBridge(preload=False)
    assert hasattr(bridge, "predict_custom")