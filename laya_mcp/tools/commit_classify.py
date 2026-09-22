"""Tool: commit message classifier — type, scope, risk."""
from __future__ import annotations

from pydantic import BaseModel, Field
from laya.common import build_sequence, render_options

from ..bridge import LayaBridge
from ._helpers import confidence_of, extract_decision, require_dict
from .base import Tool


_COMMIT_QUESTIONS = build_sequence(
    render_options(
        ["feat", "fix", "refactor", "chore", "docs", "test", "perf", "build", "ci", "revert"],
        key="type",
    ),
    render_options(
        ["api", "ui", "db", "infra", "deps", "auth", "none"],
        key="scope",
    ),
    render_options(
        ["low", "medium", "high"],
        key="risk",
    ),
)


class CommitClassifyInput(BaseModel):
    message: str = Field(..., description="A commit message to classify.")


class CommitClassifyOutput(BaseModel):
    type: str
    scope: str
    risk: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    details: dict = Field(default_factory=dict)


class CommitClassifyTool(Tool):
    name = "laya_commit_classify"
    description = (
        "Classify a commit message: type (feat / fix / refactor / chore / docs / test / "
        "perf / build / ci / revert), scope (api / ui / db / infra / deps / auth / none), "
        "and risk (low / medium / high)."
    )
    input_schema = CommitClassifyInput
    output_schema = CommitClassifyOutput

    async def run(self, bridge: LayaBridge, message: str) -> CommitClassifyOutput:
        raw = bridge.predict_custom(message, questions=_COMMIT_QUESTIONS)
        require_dict(raw, self.name)
        type_entry = extract_decision(raw, "type", self.name)
        scope_entry = extract_decision(raw, "scope", self.name)
        risk_entry = extract_decision(raw, "risk", self.name)
        return CommitClassifyOutput(
            type=str(type_entry["label"]),
            scope=str(scope_entry["label"]),
            risk=str(risk_entry["label"]),
            confidence=confidence_of(type_entry),
            details=raw,
        )