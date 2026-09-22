"""Tool: test priority classifier — which tests to run first."""
from __future__ import annotations

from pydantic import BaseModel, Field
from laya.common import build_sequence, render_options

from ..bridge import LayaBridge
from ._helpers import confidence_of, extract_decision, require_dict
from .base import Tool


_TEST_QUESTIONS = build_sequence(
    render_options(
        ["skip", "low", "medium", "high", "critical"],
        key="priority",
    ),
    render_options(
        [
            "covers_new_code",
            "covers_bug_fix",
            "covers_regression",
            "smoke_test",
            "redundant",
            "flaky",
        ],
        key="reason",
    ),
)


class TestPriorityInput(BaseModel):
    description: str = Field(
        ...,
        description="A test name + description (or full test file content) to prioritize.",
    )


class TestPriorityOutput(BaseModel):
    priority: str  # skip | low | medium | high | critical
    reason: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    details: dict = Field(default_factory=dict)


class TestPriorityTool(Tool):
    name = "laya_test_priority"
    description = (
        "Classify a test's run priority (skip / low / medium / high / critical) and the "
        "reason (covers_new_code / covers_bug_fix / covers_regression / smoke_test / "
        "redundant / flaky)."
    )
    input_schema = TestPriorityInput
    output_schema = TestPriorityOutput

    async def run(self, bridge: LayaBridge, description: str) -> TestPriorityOutput:
        raw = bridge.predict_custom(description, questions=_TEST_QUESTIONS)
        require_dict(raw, self.name)
        priority_entry = extract_decision(raw, "priority", self.name)
        reason_entry = extract_decision(raw, "reason", self.name)
        return TestPriorityOutput(
            priority=str(priority_entry["label"]),
            reason=str(reason_entry["label"]),
            confidence=confidence_of(priority_entry),
            details=raw,
        )