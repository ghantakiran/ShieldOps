"""Hunt Hypothesis Generator — generate hunt hypotheses from TI and detection gaps."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HypothesisSource(StrEnum):
    THREAT_INTEL = "threat_intel"
    DETECTION_GAP = "detection_gap"
    ANOMALY = "anomaly"
    INCIDENT_PATTERN = "incident_pattern"
    EXTERNAL_REPORT = "external_report"


class HypothesisStatus(StrEnum):
    ACTIVE = "active"
    VALIDATED = "validated"
    DISPROVEN = "disproven"
    PENDING = "pending"
    ARCHIVED = "archived"


class ConfidenceLevel(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SPECULATIVE = "speculative"


# --- Models ---


class HypothesisRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hypothesis_name: str = ""
    hypothesis_source: HypothesisSource = HypothesisSource.THREAT_INTEL
    hypothesis_status: HypothesisStatus = HypothesisStatus.ACTIVE
    confidence_level: ConfidenceLevel = ConfidenceLevel.VERY_HIGH
    quality_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class HypothesisAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hypothesis_name: str = ""
    hypothesis_source: HypothesisSource = HypothesisSource.THREAT_INTEL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class HypothesisReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_quality_count: int = 0
    avg_quality_score: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    top_low_quality: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class HuntHypothesisGenerator:
    """Generate hunt hypotheses from threat intelligence and detection gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        hypothesis_quality_threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._hypothesis_quality_threshold = hypothesis_quality_threshold
        self._records: list[HypothesisRecord] = []
        self._analyses: list[HypothesisAnalysis] = []
        logger.info(
            "hunt_hypothesis_generator.initialized",
            max_records=max_records,
            hypothesis_quality_threshold=hypothesis_quality_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_hypothesis(
        self,
        hypothesis_name: str,
        hypothesis_source: HypothesisSource = HypothesisSource.THREAT_INTEL,
        hypothesis_status: HypothesisStatus = HypothesisStatus.ACTIVE,
        confidence_level: ConfidenceLevel = ConfidenceLevel.VERY_HIGH,
        quality_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> HypothesisRecord:
        record = HypothesisRecord(
            hypothesis_name=hypothesis_name,
            hypothesis_source=hypothesis_source,
            hypothesis_status=hypothesis_status,
            confidence_level=confidence_level,
            quality_score=quality_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "hunt_hypothesis_generator.hypothesis_recorded",
            record_id=record.id,
            hypothesis_name=hypothesis_name,
            hypothesis_source=hypothesis_source.value,
            hypothesis_status=hypothesis_status.value,
        )
        return record

    def get_hypothesis(self, record_id: str) -> HypothesisRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_hypotheses(
        self,
        hypothesis_source: HypothesisSource | None = None,
        hypothesis_status: HypothesisStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[HypothesisRecord]:
        results = list(self._records)
        if hypothesis_source is not None:
            results = [r for r in results if r.hypothesis_source == hypothesis_source]
        if hypothesis_status is not None:
            results = [r for r in results if r.hypothesis_status == hypothesis_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        hypothesis_name: str,
        hypothesis_source: HypothesisSource = HypothesisSource.THREAT_INTEL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> HypothesisAnalysis:
        analysis = HypothesisAnalysis(
            hypothesis_name=hypothesis_name,
            hypothesis_source=hypothesis_source,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "hunt_hypothesis_generator.analysis_added",
            hypothesis_name=hypothesis_name,
            hypothesis_source=hypothesis_source.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_hypothesis_distribution(self) -> dict[str, Any]:
        """Group by hypothesis_source; return count and avg quality_score."""
        src_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.hypothesis_source.value
            src_data.setdefault(key, []).append(r.quality_score)
        result: dict[str, Any] = {}
        for src, scores in src_data.items():
            result[src] = {
                "count": len(scores),
                "avg_quality_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_quality_hypotheses(self) -> list[dict[str, Any]]:
        """Return records where quality_score < hypothesis_quality_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.quality_score < self._hypothesis_quality_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "hypothesis_name": r.hypothesis_name,
                        "hypothesis_source": r.hypothesis_source.value,
                        "quality_score": r.quality_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["quality_score"])

    def rank_by_quality(self) -> list[dict[str, Any]]:
        """Group by service, avg quality_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.quality_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_quality_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_quality_score"])
        return results

    def detect_hypothesis_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> HypothesisReport:
        by_source: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for r in self._records:
            by_source[r.hypothesis_source.value] = by_source.get(r.hypothesis_source.value, 0) + 1
            by_status[r.hypothesis_status.value] = by_status.get(r.hypothesis_status.value, 0) + 1
            by_confidence[r.confidence_level.value] = (
                by_confidence.get(r.confidence_level.value, 0) + 1
            )
        low_quality_count = sum(
            1 for r in self._records if r.quality_score < self._hypothesis_quality_threshold
        )
        scores = [r.quality_score for r in self._records]
        avg_quality_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_quality_hypotheses()
        top_low_quality = [o["hypothesis_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_quality_count > 0:
            recs.append(
                f"{low_quality_count} hypothesis(es) below quality threshold "
                f"({self._hypothesis_quality_threshold})"
            )
        if self._records and avg_quality_score < self._hypothesis_quality_threshold:
            recs.append(
                f"Avg quality score {avg_quality_score} below threshold "
                f"({self._hypothesis_quality_threshold})"
            )
        if not recs:
            recs.append("Hunt hypothesis quality is healthy")
        return HypothesisReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_quality_count=low_quality_count,
            avg_quality_score=avg_quality_score,
            by_source=by_source,
            by_status=by_status,
            by_confidence=by_confidence,
            top_low_quality=top_low_quality,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("hunt_hypothesis_generator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        source_dist: dict[str, int] = {}
        for r in self._records:
            key = r.hypothesis_source.value
            source_dist[key] = source_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "hypothesis_quality_threshold": self._hypothesis_quality_threshold,
            "source_distribution": source_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
