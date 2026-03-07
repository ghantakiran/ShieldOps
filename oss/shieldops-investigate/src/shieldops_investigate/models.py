"""Pydantic models for investigation results, hypotheses, and evidence."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EvidenceSource(StrEnum):
    """Source system that produced a piece of evidence."""

    PROMETHEUS = "prometheus"
    KUBERNETES = "kubernetes"
    CLAUDE = "claude"
    CORRELATOR = "correlator"


class Confidence(StrEnum):
    """Human-readable confidence levels for hypotheses."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @classmethod
    def from_score(cls, score: float) -> Confidence:
        """Map a numeric score (0-1) to a confidence level."""
        if score >= 0.7:
            return cls.HIGH
        if score >= 0.4:
            return cls.MEDIUM
        return cls.LOW


class Evidence(BaseModel):
    """A single piece of evidence collected during investigation.

    Evidence is an observable fact — a metric value, a Kubernetes event,
    or a deployment timestamp — that supports or refutes a hypothesis.
    """

    source: EvidenceSource
    query: str = Field(description="The query or API call that produced this evidence.")
    value: str = Field(description="Human-readable value or summary.")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    anomaly_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How anomalous this value is (0 = normal, 1 = extreme outlier).",
    )
    raw: dict | None = Field(
        default=None,
        description="Raw response data for programmatic consumption.",
        exclude=True,
    )


class Hypothesis(BaseModel):
    """A ranked hypothesis about the root cause of an incident.

    Each hypothesis includes a human-readable description, a confidence
    score, supporting evidence, and a suggested next action.
    """

    title: str = Field(description="Short title, e.g. 'Deployment Regression'.")
    description: str = Field(description="Detailed explanation of what likely happened.")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score from 0 (wild guess) to 1 (near certain).",
    )
    evidence: list[Evidence] = Field(default_factory=list)
    suggested_action: str = Field(
        default="",
        description="Recommended next step to confirm or mitigate.",
    )

    @property
    def confidence_level(self) -> Confidence:
        """Return the human-readable confidence level."""
        return Confidence.from_score(self.confidence)


class InvestigationResult(BaseModel):
    """Complete result of an investigation run.

    Contains ranked hypotheses, all collected evidence, a plain-language
    summary, and timing metadata.
    """

    alert_name: str
    namespace: str
    service: str | None = None
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    summary: str = Field(
        default="",
        description="Plain-language summary of the investigation.",
    )
    duration_seconds: float = Field(
        default=0.0,
        description="Wall-clock time the investigation took.",
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def top_hypothesis(self) -> Hypothesis | None:
        """Return the highest-confidence hypothesis, if any."""
        if not self.hypotheses:
            return None
        return max(self.hypotheses, key=lambda h: h.confidence)
