"""Shared fixtures for tests."""
from __future__ import annotations

import pytest


@pytest.fixture
def fake_bridge():
    """A bridge stand-in for tests.

    Tests use ``unittest.mock.MagicMock`` directly rather than this fixture
    when they want to control ``predict.return_value``. This fixture exists
    in case future tests need a real bridge with ``preload=False``.
    """
    from laya_mcp.bridge import LayaBridge

    return LayaBridge(preload=False)