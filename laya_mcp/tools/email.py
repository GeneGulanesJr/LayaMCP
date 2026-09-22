"""Tool: email-specific triage."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..bridge import LayaBridge
from ._helpers import (
    confidence_of,
    extract_decision,
    label_is_yes,
    require_dict,
)
from .base import Tool


class EmailInput(BaseModel):
    body: str = Field(..., description="Raw email body to triage.")


class EmailOutput(BaseModel):
    intent: str
    urgency: str
    needs_reply: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    details: dict = Field(default_factory=dict)


class EmailTool(Tool):
    name = "laya_email"
    description = "Classify an email's intent, urgency, and whether it needs a reply."
    input_schema = EmailInput
    output_schema = EmailOutput

    async def run(self, bridge: LayaBridge, body: str) -> EmailOutput:
        raw = bridge.predict(body, preset="email")
        require_dict(raw, self.name)
        intent = extract_decision(raw, "intent", self.name)
        urgency = extract_decision(raw, "urgency", self.name)
        needs_reply = extract_decision(raw, "needs_reply", self.name)
        return EmailOutput(
            intent=str(intent["label"]),
            urgency=str(urgency["label"]),
            needs_reply=label_is_yes(needs_reply),
            confidence=confidence_of(intent),
            details=raw,
        )