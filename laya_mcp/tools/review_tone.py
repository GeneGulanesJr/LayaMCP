"""Tool: code review comment tone classifier.

Uses a custom Laya question schema (not from upstream presets) to
classify review comments along two dimensions:

- tone: nit / suggestion / blocking / praise / question / off_topic
- priority: low / medium / high
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from laya.common import build_sequence, render_options

from ..bridge import LayaBridge
from ._helpers import confidence_of, extract_decision, require_dict
from .base import Tool


_REVIEW_QUESTIONS = build_sequence(
    render_options(
        ["nit", "suggestion", "blocking", "praise", "question", "off_topic"],
        key="tone",
    ),
    render_options(
        ["low", "medium", "high"],
        key="priority",
    ),
)


class ReviewToneInput(BaseModel):
    comment: str = Field(..., description="A code review comment to classify.")


class ReviewToneOutput(BaseModel):
    tone: str
    priority: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    details: dict = Field(default_factory=dict)


class ReviewToneTool(Tool):
    name = "laya_review_tone"
    description = (
        "Classify a code review comment's tone (nit / suggestion / blocking / "
        "praise / question / off-topic) and priority (low / medium / high)."
    )
    input_schema = ReviewToneInput
    output_schema = ReviewToneOutput

    async def run(self, bridge: LayaBridge, comment: str) -> ReviewToneOutput:
        raw = bridge.predict_custom(comment, questions=_REVIEW_QUESTIONS)
        require_dict(raw, self.name)
        tone_entry = extract_decision(raw, "tone", self.name)
        priority_entry = extract_decision(raw, "priority", self.name)
        return ReviewToneOutput(
            tone=str(tone_entry["label"]),
            priority=str(priority_entry["label"]),
            confidence=confidence_of(tone_entry),
            details=raw,
        )