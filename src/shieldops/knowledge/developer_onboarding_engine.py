"""Developer onboarding intelligence engine.

Tracks onboarding journeys, computes time-to-productivity,
and identifies bottlenecks in developer ramp-up.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class OnboardingPhase(StrEnum):
    """Phase of the onboarding journey."""

    orientation = "orientation"
    environment_setup = "environment_setup"
    first_commit = "first_commit"
    first_deploy = "first_deploy"
    fully_productive = "fully_productive"


class BottleneckType(StrEnum):
    """Type of onboarding bottleneck."""

    tooling = "tooling"
    documentation = "documentation"
    access = "access"
    mentorship = "mentorship"
    complexity = "complexity"


class OnboardingOutcome(StrEnum):
    """Outcome of an onboarding journey."""

    completed = "completed"
    in_progress = "in_progress"
    stalled = "stalled"
    abandoned = "abandoned"


class OnboardingRecord(BaseModel):
    """Record of a developer onboarding event."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    developer_id: str = ""
    team: str = ""
    phase: OnboardingPhase = OnboardingPhase.orientation
    days_elapsed: int = 0
    bottleneck_type: BottleneckType = BottleneckType.tooling
    outcome: OnboardingOutcome = OnboardingOutcome.in_progress
    articles_consumed: int = 0
    mentor_sessions: int = 0
    created_at: float = Field(default_factory=time.time)


class OnboardingAnalysis(BaseModel):
    """Analysis of an onboarding record."""

    record_id: str = ""
    productivity_score: float = 0.0
    bottleneck_severity: float = 0.0
    recommended_paths: list[str] = Field(default_factory=list)


class OnboardingReport(BaseModel):
    """Aggregated onboarding report."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_time_to_productivity: float = 0.0
    completion_rate: float = 0.0
    top_bottlenecks: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


class DeveloperOnboardingEngine:
    """Engine for developer onboarding analytics."""

    def __init__(
        self,
        max_records: int = 200000,
        productivity_threshold_days: int = 30,
    ) -> None:
        self._max_records = max_records
        self._productivity_threshold = productivity_threshold_days
        self._records: list[OnboardingRecord] = []
        self._analyses: list[OnboardingAnalysis] = []
        logger.info(
            "developer_onboarding_engine.init",
            max_records=max_records,
            productivity_threshold_days=(productivity_threshold_days),
        )

    def add_record(self, **kwargs: Any) -> OnboardingRecord:
        """Add an onboarding record."""
        record = OnboardingRecord(**kwargs)
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "developer_onboarding_engine.add_record",
            record_id=record.id,
            developer_id=record.developer_id,
        )
        return record

    def process(self, key: str) -> OnboardingAnalysis:
        """Process a record by ID."""
        record = next(
            (r for r in self._records if r.id == key),
            None,
        )
        if not record:
            return OnboardingAnalysis()
        prod_score = self._score_productivity(record)
        severity = self._bottleneck_severity(record)
        paths = self._suggest_paths(record)
        analysis = OnboardingAnalysis(
            record_id=record.id,
            productivity_score=prod_score,
            bottleneck_severity=severity,
            recommended_paths=paths,
        )
        self._analyses.append(analysis)
        return analysis

    def generate_report(self) -> OnboardingReport:
        """Generate aggregated onboarding report."""
        completed = [r for r in self._records if r.outcome == OnboardingOutcome.completed]
        avg_time = 0.0
        if completed:
            avg_time = sum(r.days_elapsed for r in completed) / len(completed)
        comp_rate = 0.0
        if self._records:
            comp_rate = len(completed) / len(self._records)
        bottlenecks: dict[str, int] = {}
        for r in self._records:
            b = r.bottleneck_type.value
            bottlenecks[b] = bottlenecks.get(b, 0) + 1
        recs: list[str] = []
        if avg_time > self._productivity_threshold:
            recs.append("Reduce time-to-productivity")
        if comp_rate < 0.8:
            recs.append("Improve onboarding completion rate")
        top = sorted(
            bottlenecks.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        if top:
            recs.append(f"Address top bottleneck: {top[0][0]}")
        return OnboardingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_time_to_productivity=round(avg_time, 2),
            completion_rate=round(comp_rate, 3),
            top_bottlenecks=bottlenecks,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        """Return engine statistics."""
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "max_records": self._max_records,
            "productivity_threshold": (self._productivity_threshold),
        }

    def clear_data(self) -> None:
        """Clear all records and analyses."""
        self._records.clear()
        self._analyses.clear()
        logger.info(
            "developer_onboarding_engine.clear_data",
        )

    def compute_time_to_productivity(
        self,
    ) -> dict[str, float]:
        """Compute avg time-to-productivity by team."""
        team_days: dict[str, list[int]] = {}
        for r in self._records:
            if r.outcome == OnboardingOutcome.completed:
                team_days.setdefault(r.team, []).append(r.days_elapsed)
        return {t: round(sum(v) / len(v), 2) for t, v in team_days.items() if v}

    def identify_bottlenecks(
        self,
    ) -> dict[str, int]:
        """Identify top bottlenecks across teams."""
        counts: dict[str, int] = {}
        stalled = [
            r
            for r in self._records
            if r.outcome
            in (
                OnboardingOutcome.stalled,
                OnboardingOutcome.abandoned,
            )
        ]
        for r in stalled:
            b = r.bottleneck_type.value
            counts[b] = counts.get(b, 0) + 1
        return dict(
            sorted(
                counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        )

    def recommend_knowledge_paths(self, developer_id: str) -> list[str]:
        """Recommend knowledge paths for a dev."""
        dev_records = [r for r in self._records if r.developer_id == developer_id]
        if not dev_records:
            return []
        latest = max(dev_records, key=lambda r: r.created_at)
        paths: list[str] = []
        if latest.articles_consumed < 5:
            paths.append("Complete core documentation reading")
        if latest.mentor_sessions < 2:
            paths.append("Schedule mentorship sessions")
        if latest.phase == OnboardingPhase.environment_setup:
            paths.append("Follow environment setup guide")
        if latest.phase == OnboardingPhase.first_commit:
            paths.append("Review contribution guidelines")
        return paths

    def _score_productivity(self, record: OnboardingRecord) -> float:
        """Score productivity for a record."""
        phase_scores = {
            OnboardingPhase.orientation: 0.1,
            OnboardingPhase.environment_setup: 0.3,
            OnboardingPhase.first_commit: 0.5,
            OnboardingPhase.first_deploy: 0.7,
            OnboardingPhase.fully_productive: 1.0,
        }
        base = phase_scores.get(record.phase, 0.0)
        if record.days_elapsed > self._productivity_threshold:
            penalty = min(
                (record.days_elapsed - self._productivity_threshold) / self._productivity_threshold,
                0.5,
            )
            base -= penalty
        return round(max(base, 0.0), 3)

    def _bottleneck_severity(self, record: OnboardingRecord) -> float:
        """Compute bottleneck severity."""
        if record.outcome == OnboardingOutcome.completed:
            return 0.0
        severity = 0.3
        if record.outcome == OnboardingOutcome.stalled:
            severity = 0.7
        if record.outcome == OnboardingOutcome.abandoned:
            severity = 1.0
        if record.days_elapsed > self._productivity_threshold:
            severity = min(severity + 0.2, 1.0)
        return round(severity, 3)

    def _suggest_paths(self, record: OnboardingRecord) -> list[str]:
        """Suggest paths based on record."""
        paths: list[str] = []
        if record.bottleneck_type == BottleneckType.documentation:
            paths.append("Improve team docs")
        if record.bottleneck_type == BottleneckType.tooling:
            paths.append("Automate env setup")
        if record.bottleneck_type == BottleneckType.access:
            paths.append("Streamline access grants")
        if record.mentor_sessions < 2:
            paths.append("Pair with a mentor")
        return paths
