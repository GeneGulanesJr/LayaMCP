"""Tool: detect leaked secrets / credentials in text."""
from __future__ import annotations

from pydantic import BaseModel, Field
from laya.common import build_sequence, render_options

from ..bridge import LayaBridge
from ._helpers import confidence_of, extract_decision, require_dict
from .base import Tool


_SECRET_QUESTIONS = build_sequence(
    render_options(
        ["none", "api_key", "password", "token", "cert", "ssh_key", "aws_creds", "other"],
        key="kind",
    ),
    render_options(
        ["none", "low", "medium", "high", "critical"],
        key="risk",
    ),
)


class SecretRiskInput(BaseModel):
    text: str = Field(..., description="Text to scan for secrets / API keys / credentials.")


class SecretRiskOutput(BaseModel):
    kind: str  # none | api_key | password | token | cert | ssh_key | aws_creds | other
    risk: str  # none | low | medium | high | critical
    confidence: float = Field(..., ge=0.0, le=1.0)
    details: dict = Field(default_factory=dict)


class SecretRiskTool(Tool):
    name = "laya_secret_risk"
    description = (
        "Scan text for leaked credentials (API keys, passwords, tokens, certs, SSH keys, "
        "AWS creds). Returns the kind of secret detected and a risk level. "
        "Use BEFORE saving any text to memory, posting to public channels, or "
        "including in commit messages."
    )
    input_schema = SecretRiskInput
    output_schema = SecretRiskOutput

    async def run(self, bridge: LayaBridge, text: str) -> SecretRiskOutput:
        raw = bridge.predict_custom(text, questions=_SECRET_QUESTIONS)
        require_dict(raw, self.name)
        kind_entry = extract_decision(raw, "kind", self.name)
        risk_entry = extract_decision(raw, "risk", self.name)
        return SecretRiskOutput(
            kind=str(kind_entry["label"]),
            risk=str(risk_entry["label"]),
            confidence=confidence_of(risk_entry),
            details=raw,
        )