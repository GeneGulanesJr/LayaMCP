"""Tool: content moderation (toxicity / harassment / threats)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..bridge import LayaBridge
from ._helpers import extract_decision, label_is, max_confidence, require_dict
from .base import Tool


class ModerateInput(BaseModel):
    text: str = Field(..., description="Text to moderate.")


class ModerateOutput(BaseModel):
    is_toxic: bool
    is_harassment: bool
    is_threat: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    details: dict = Field(default_factory=dict)


class ModerateTool(Tool):
    name = "laya_moderate"
    description = "Check text for toxicity, harassment, and threats."
    input_schema = ModerateInput
    output_schema = ModerateOutput

    async def run(self, bridge: LayaBridge, text: str) -> ModerateOutput:
        raw = bridge.predict(text, preset="moderate")
        require_dict(raw, self.name)
        toxicity = extract_decision(raw, "toxicity", self.name)
        harassment = extract_decision(raw, "harassment", self.name)
        threat = extract_decision(raw, "threat", self.name)
        return ModerateOutput(
            is_toxic=label_is(toxicity, "toxic"),
            is_harassment=label_is(harassment, "harassment"),
            is_threat=label_is(threat, "threat"),
            confidence=max_confidence(raw),
            details=raw,
        )