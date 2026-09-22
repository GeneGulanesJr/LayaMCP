"""Tool: support ticket triage (intent / urgency / churn / frustration)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..bridge import LayaBridge
from ._helpers import confidence_of, extract_decision, require_dict
from .base import Tool


class TriageInput(BaseModel):
    text: str = Field(..., description="Ticket text to triage.")


class TriageOutput(BaseModel):
    intent: str
    urgency: str
    churn_risk: str
    frustration: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    details: dict = Field(default_factory=dict)


class TriageTool(Tool):
    name = "laya_triage"
    description = "Classify a support ticket's intent, urgency, churn risk, and frustration."
    input_schema = TriageInput
    output_schema = TriageOutput

    async def run(self, bridge: LayaBridge, text: str) -> TriageOutput:
        raw = bridge.predict(text, preset="triage")
        require_dict(raw, self.name)
        intent = extract_decision(raw, "intent", self.name)
        urgency = extract_decision(raw, "urgency", self.name)
        churn = extract_decision(raw, "churn", self.name)
        frustration = extract_decision(raw, "frustration", self.name)
        return TriageOutput(
            intent=str(intent["label"]),
            urgency=str(urgency["label"]),
            churn_risk=str(churn["label"]),
            frustration=str(frustration["label"]),
            confidence=confidence_of(intent),  # intent is the primary signal
            details=raw,
        )