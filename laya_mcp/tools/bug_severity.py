"""Tool: bug report severity + area classifier."""
from __future__ import annotations

from pydantic import BaseModel, Field
from laya.common import build_sequence, render_options

from ..bridge import LayaBridge
from ._helpers import confidence_of, extract_decision, require_dict
from .base import Tool


_BUG_QUESTIONS = build_sequence(
    render_options(
        ["S0_critical", "S1_high", "S2_medium", "S3_low"],
        key="severity",
    ),
    render_options(
        ["frontend", "backend", "infra", "docs", "tests", "deps", "auth", "unknown"],
        key="area",
    ),
)


class BugSeverityInput(BaseModel):
    text: str = Field(..., description="A bug report or issue text to classify.")


class BugSeverityOutput(BaseModel):
    severity: str  # S0_critical | S1_high | S2_medium | S3_low
    area: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    details: dict = Field(default_factory=dict)


class BugSeverityTool(Tool):
    name = "laya_bug_severity"
    description = (
        "Classify a bug report's severity (S0_critical / S1_high / S2_medium / S3_low) "
        "and area (frontend / backend / infra / docs / tests / deps / auth / unknown)."
    )
    input_schema = BugSeverityInput
    output_schema = BugSeverityOutput

    async def run(self, bridge: LayaBridge, text: str) -> BugSeverityOutput:
        raw = bridge.predict_custom(text, questions=_BUG_QUESTIONS)
        require_dict(raw, self.name)
        severity_entry = extract_decision(raw, "severity", self.name)
        area_entry = extract_decision(raw, "area", self.name)
        return BugSeverityOutput(
            severity=str(severity_entry["label"]),
            area=str(area_entry["label"]),
            confidence=confidence_of(severity_entry),
            details=raw,
        )