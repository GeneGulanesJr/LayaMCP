"""Helpers shared across tools for validating and extracting Laya output.

Laya returns dicts whose exact shape can drift between versions. These
helpers validate the parts we depend on and raise :class:`ToolError`
with context on failure — instead of letting bad data silently produce
empty/default results.
"""
from __future__ import annotations

from ..errors import ToolError


def require_dict(raw, tool_name: str) -> dict:
    """Validate that ``raw`` is a non-empty dict.

    Raises:
        ToolError: if ``raw`` is not a dict, or is empty.
    """
    if not isinstance(raw, dict):
        raise ToolError(
            tool_name,
            f"Expected dict from Laya, got {type(raw).__name__}: {raw!r}",
        )
    if not raw:
        raise ToolError(tool_name, "Laya returned an empty result.")
    return raw


def extract_decision(raw: dict, key: str, tool_name: str) -> dict:
    """Extract and validate a single question's decision dict.

    Validates that:
    - ``key`` exists in ``raw``
    - ``raw[key]`` is a dict
    - ``raw[key]`` has a ``label`` field
    - ``raw[key]`` has a numeric ``confidence`` field

    Raises:
        ToolError: on any of the above.

    Returns:
        The validated entry dict (callers can index ``["label"]`` / ``["confidence"]`` safely).
    """
    if key not in raw:
        raise ToolError(
            tool_name,
            f"Missing expected key {key!r} in Laya result. Got keys: {sorted(raw)}",
        )
    entry = raw[key]
    if not isinstance(entry, dict):
        raise ToolError(
            tool_name,
            f"Expected dict at {key!r}, got {type(entry).__name__}: {entry!r}",
        )
    if "label" not in entry:
        raise ToolError(tool_name, f"Missing 'label' at {key!r}: {entry!r}")
    if "confidence" not in entry:
        raise ToolError(tool_name, f"Missing 'confidence' at {key!r}: {entry!r}")
    try:
        float(entry["confidence"])
    except (TypeError, ValueError) as e:
        raise ToolError(
            tool_name,
            f"Confidence at {key!r} is not numeric: {entry['confidence']!r}",
        ) from e
    return entry


def label_is(entry: dict, positive_value: str) -> bool:
    """Case-insensitive equality check on ``entry['label']``."""
    return str(entry.get("label", "")).lower() == positive_value.lower()


def label_is_yes(entry: dict) -> bool:
    """True if ``entry['label']`` is one of ``yes``/``true``/``1``."""
    return str(entry.get("label", "")).lower() in {"yes", "true", "1"}


def confidence_of(entry: dict) -> float:
    """Get the numeric confidence from a validated entry."""
    return float(entry["confidence"])


def max_confidence(raw: dict) -> float:
    """Max confidence across all decision dicts in ``raw``.

    Skips entries that aren't dicts or have non-numeric confidence.
    Returns ``0.0`` if nothing usable is found.
    """
    confs: list[float] = []
    for v in raw.values():
        if isinstance(v, dict) and "confidence" in v:
            try:
                confs.append(float(v["confidence"]))
            except (TypeError, ValueError):
                pass
    return max(confs) if confs else 0.0