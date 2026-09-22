"""Wrapper around the upstream Laya library.

Holds a single ``Router`` instance so model weights are loaded exactly once
per process. Every tool in :mod:`laya_mcp.tools` calls ``bridge.predict(...)``.

Failures are surfaced as :class:`BridgeError` subclasses. The original
exception (if any) is attached via ``__cause__`` for traceback chaining.
The message includes context (preset name, input length) but **never**
the raw input — to avoid leaking user data into logs.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from laya import Router
from laya.presets import (
    email_questions,
    guard_questions,
    moderation_questions,
    router_questions,
    triage_questions,
)

from .errors import BridgeError, ModelLoadError, UnknownPresetError

logger = logging.getLogger(__name__)


class LayaBridge:
    """Thin in-process wrapper around Laya.

    The :class:`laya.Router` picks the right checkpoint (English /
    multilingual / typed-decisions) per call based on script detection.
    Tools don't need to know about that — they just call ``predict``.
    """

    PRESETS: dict[str, Callable] = {
        "guard": guard_questions,
        "route": router_questions,
        "moderate": moderation_questions,
        "triage": triage_questions,
        "email": email_questions,
    }

    def __init__(self, preload: bool = True) -> None:
        try:
            self.router = Router(preload=preload)
        except Exception as e:
            raise ModelLoadError(
                f"Failed to initialize Laya Router (preload={preload}): {e}"
            ) from e

    # ------------------------------------------------------------------
    # High-level API used by every tool
    # ------------------------------------------------------------------

    def predict(self, state: str, preset: str) -> Any:
        """Run a named preset against ``state``.

        Args:
            state: Input text (prompt, email body, JSON, ticket, etc.).
            preset: Key from :attr:`PRESETS`.

        Returns:
            Whatever Laya's ``agent.predict()`` returns.

        Raises:
            UnknownPresetError: if ``preset`` isn't in :attr:`PRESETS`.
            BridgeError: if the upstream Laya call fails for any reason
                (GPU OOM, runtime error, model evicted, etc.).
        """
        if preset not in self.PRESETS:
            raise UnknownPresetError(
                f"Unknown preset {preset!r}. Choose from {sorted(self.PRESETS)}."
            )
        agent = self._default_agent()
        try:
            return agent.predict(state, self.PRESETS[preset]())
        except Exception as e:
            logger.exception("Laya predict failed (preset=%s, state_len=%d)", preset, len(state))
            raise BridgeError(
                f"Laya predict failed (preset={preset!r}, state_len={len(state)})"
            ) from e

    def predict_custom(self, state: str, questions: Any) -> Any:
        """Run a custom questions schema (not from upstream presets).

        Raises:
            BridgeError: if the upstream Laya call fails.
        """
        agent = self._default_agent()
        try:
            return agent.predict(state, questions)
        except Exception as e:
            logger.exception("Laya predict_custom failed (state_len=%d)", len(state))
            raise BridgeError(
                f"Laya predict_custom failed (state_len={len(state)})"
            ) from e

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _default_agent(self) -> Any:
        """Return the default agent. Wrapped to convert key/index issues into BridgeError."""
        try:
            return self.router.agents["english"]
        except Exception as e:
            raise BridgeError(
                f"Could not access default 'english' agent: {e}"
            ) from e