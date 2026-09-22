"""Tool: prompt-injection / jailbreak detection."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..bridge import LayaBridge
from ..errors import ToolError
from ._helpers import confidence_of, extract_decision, label_is, require_dict
from .base import Tool


class GuardInput(BaseModel):
    prompt: str = Field(..., description="Text to check for prompt injection / jailbreak.")


class GuardOutput(BaseModel):
    is_injection: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    details: dict = Field(default_factory=dict)


class GuardTool(Tool):
    name = "laya_guard"
    description = "Check whether a prompt contains injection or jailbreak attempts. Returns is_injection + confidence."
    input_schema = GuardInput
    output_schema = GuardOutput

    async def run(self, bridge: LayaBridge, prompt: str) -> GuardOutput:
        raw = bridge.predict(prompt, preset="guard")
        require_dict(raw, self.name)
        # Guard uses the first question's decision as the canonical signal.
        first = extract_decision(raw, "q1", self.name)
        return GuardOutput(
            is_injection=label_is(first, "injection") or \
            label_is(first, "jailbreak") or \
            label_is(first, "attack"),
            confidence=confidence_of(first),
            details=raw,
        )