"""Tool: PR diff intent classifier — what is this diff trying to do?"""
from __future__ import annotations

from pydantic import BaseModel, Field
from laya.common import build_sequence, render_options

from ..bridge import LayaBridge
from ._helpers import confidence_of, extract_decision, require_dict
from .base import Tool


_DIFF_QUESTIONS = build_sequence(
    render_options(
        [
            "add_feature",
            "fix_bug",
            "refactor",
            "perf",
            "docs",
            "test",
            "build",
            "chore",
            "revert",
        ],
        key="intent",
    ),
    render_options(
        ["single_file", "module", "cross_cutting"],
        key="scope",
    ),
    render_options(
        ["low", "medium", "high"],
        key="risk",
    ),
)


class DiffIntentInput(BaseModel):
    diff: str = Field(..., description="A unified diff to classify.")


class DiffIntentOutput(BaseModel):
    intent: str
    scope: str
    risk: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    details: dict = Field(default_factory=dict)


class DiffIntentTool(Tool):
    name = "laya_diff_intent"
    description = (
        "Classify a PR diff: intent (add_feature / fix_bug / refactor / perf / docs / "
        "test / build / chore / revert), scope (single_file / module / cross_cutting), "
        "and risk (low / medium / high)."
    )
    input_schema = DiffIntentInput
    output_schema = DiffIntentOutput

    async def run(self, bridge: LayaBridge, diff: str) -> DiffIntentOutput:
        raw = bridge.predict_custom(diff, questions=_DIFF_QUESTIONS)
        require_dict(raw, self.name)
        intent_entry = extract_decision(raw, "intent", self.name)
        scope_entry = extract_decision(raw, "scope", self.name)
        risk_entry = extract_decision(raw, "risk", self.name)
        return DiffIntentOutput(
            intent=str(intent_entry["label"]),
            scope=str(scope_entry["label"]),
            risk=str(risk_entry["label"]),
            confidence=confidence_of(intent_entry),
            details=raw,
        )