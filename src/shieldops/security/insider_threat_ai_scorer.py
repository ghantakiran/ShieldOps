"""Insider Threat AI Scorer — multi-signal insider threat scoring."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ThreatIndicator(StrEnum):
    DATA_HOARDING = "data_hoarding"
    UNUSUAL_ACCESS = "unusual_access"
    RESIGNATION_SIGNAL = "resignation_signal"
    PRIVILEGE_ABUSE = "privilege_abuse"
    POLICY_VIOLATION = "policy_violation"


class RiskTier(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    ELEVATED = "elevated"
    MODERATE = "moderate"
    LOW = "low"


class BehaviorPattern(StrEnum):
    CONSISTENT = "consistent"
    ESCALATING = "escalating"
    SPORADIC = "sporadic"
    DECLINING = "declining"
    NEW = "new"


# --- Models ---


class InsiderThreatRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subject_name: str = ""
    threat_indicator: ThreatIndicator = ThreatIndicator.DATA_HOARDING
    risk_tier: RiskTier = RiskTier.CRITICAL
    behavior_pattern: BehaviorPattern = BehaviorPattern.CONSISTENT
    threat_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class InsiderThreatAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subject_name: str = ""
    threat_indicator: ThreatIndicator = ThreatIndicator.DATA_HOARDING
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class InsiderThreatReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_threat_count: int = 0
    avg_threat_score: float = 0.0
    by_indicator: dict[str, int] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_pattern: dict[str, int] = Field(default_factory=dict)
    top_high_threat: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class InsiderThreatAIScorer:
    """Multi-signal insider threat scoring using behavioral analytics."""

    def __init__(
        self,
        max_records: int = 200000,
        insider_threat_threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._insider_threat_threshold = insider_threat_threshold
        self._records: list[InsiderThreatRecord] = []
        self._analyses: list[InsiderThreatAnalysis] = []
        logger.info(
            "insider_threat_ai_scorer.initialized",
            max_records=max_records,
            insider_threat_threshold=insider_threat_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_threat(
        self,
        subject_name: str,
        threat_indicator: ThreatIndicator = ThreatIndicator.DATA_HOARDING,
        risk_tier: RiskTier = RiskTier.CRITICAL,
        behavior_pattern: BehaviorPattern = BehaviorPattern.CONSISTENT,
        threat_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> InsiderThreatRecord:
        record = InsiderThreatRecord(
            subject_name=subject_name,
            threat_indicator=threat_indicator,
            risk_tier=risk_tier,
            behavior_pattern=behavior_pattern,
            threat_score=threat_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "insider_threat_ai_scorer.threat_recorded",
            record_id=record.id,
            subject_name=subject_name,
            threat_indicator=threat_indicator.value,
            risk_tier=risk_tier.value,
        )
        return record

    def get_threat(self, record_id: str) -> InsiderThreatRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_threats(
        self,
        threat_indicator: ThreatIndicator | None = None,
        risk_tier: RiskTier | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[InsiderThreatRecord]:
        results = list(self._records)
        if threat_indicator is not None:
            results = [r for r in results if r.threat_indicator == threat_indicator]
        if risk_tier is not None:
            results = [r for r in results if r.risk_tier == risk_tier]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        subject_name: str,
        threat_indicator: ThreatIndicator = ThreatIndicator.DATA_HOARDING,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> InsiderThreatAnalysis:
        analysis = InsiderThreatAnalysis(
            subject_name=subject_name,
            threat_indicator=threat_indicator,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "insider_threat_ai_scorer.analysis_added",
            subject_name=subject_name,
            threat_indicator=threat_indicator.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_threat_distribution(self) -> dict[str, Any]:
        """Group by threat_indicator; return count and avg threat_score."""
        ind_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.threat_indicator.value
            ind_data.setdefault(key, []).append(r.threat_score)
        result: dict[str, Any] = {}
        for ind, scores in ind_data.items():
            result[ind] = {
                "count": len(scores),
                "avg_threat_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_threat_subjects(self) -> list[dict[str, Any]]:
        """Return records where threat_score > insider_threat_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.threat_score > self._insider_threat_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "subject_name": r.subject_name,
                        "threat_indicator": r.threat_indicator.value,
                        "threat_score": r.threat_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["threat_score"], reverse=True)

    def rank_by_threat_score(self) -> list[dict[str, Any]]:
        """Group by service, avg threat_score, sort descending (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.threat_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_threat_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_threat_score"], reverse=True)
        return results

    def detect_threat_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> InsiderThreatReport:
        by_indicator: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        by_pattern: dict[str, int] = {}
        for r in self._records:
            by_indicator[r.threat_indicator.value] = (
                by_indicator.get(r.threat_indicator.value, 0) + 1
            )
            by_tier[r.risk_tier.value] = by_tier.get(r.risk_tier.value, 0) + 1
            by_pattern[r.behavior_pattern.value] = by_pattern.get(r.behavior_pattern.value, 0) + 1
        high_threat_count = sum(
            1 for r in self._records if r.threat_score > self._insider_threat_threshold
        )
        scores = [r.threat_score for r in self._records]
        avg_threat_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_threat_subjects()
        top_high_threat = [o["subject_name"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_threat_count > 0:
            recs.append(
                f"{high_threat_count} subject(s) above threat threshold "
                f"({self._insider_threat_threshold})"
            )
        if self._records and avg_threat_score > self._insider_threat_threshold:
            recs.append(
                f"Avg threat score {avg_threat_score} above threshold "
                f"({self._insider_threat_threshold})"
            )
        if not recs:
            recs.append("Insider threat posture is healthy")
        return InsiderThreatReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_threat_count=high_threat_count,
            avg_threat_score=avg_threat_score,
            by_indicator=by_indicator,
            by_tier=by_tier,
            by_pattern=by_pattern,
            top_high_threat=top_high_threat,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("insider_threat_ai_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        indicator_dist: dict[str, int] = {}
        for r in self._records:
            key = r.threat_indicator.value
            indicator_dist[key] = indicator_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "insider_threat_threshold": self._insider_threat_threshold,
            "indicator_distribution": indicator_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
