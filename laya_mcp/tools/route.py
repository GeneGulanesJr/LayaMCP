"""Tool: cheap-vs-frontier model routing decision."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..bridge import LayaBridge
from ._helpers import confidence_of, extract_decision, label_is, require_dict
from .base import Tool


class RouteInput(BaseModel):
    prompt: str = Field(..., description="The prompt that needs a model.")


class RouteOutput(BaseModel):
    tier: str = Field(..., description="'low or 'frontier' (lowercase).")
    confidence: float = Field(..., ge=0.0, le=1.0)
    details: dict = Field(default_factory=dict)


class RouteTool(Tool):
    name = "laya_route"
    description = "Decide whether a prompt needs a small/cheap model or a frontier/smart model."
    input_schema = RouteInput
    output_schema = RouteOutput

    async def run(self, bridge: LayaBridge, prompt: str) -> RouteOutput:
        raw = bridge.predict(prompt, preset="route")
        require_dict(raw, self.name)
        first = extract_decision(raw, "q1", self.name)
        # Normalise to a two-tier vocabulary. Upstream labels vary.
        tier = "frontier" if (
            label_is(first, "frontier")
            or label_is(first, "large")
            or label_is(first, "smart")
            or label_is(first, "complex")
        ) else "small"
        return RouteOutput(
            tier=tier,
            confidence=confidence_of(first),
            details=raw,
        )