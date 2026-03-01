"""Cost Variance Analyzer — analyze cost variances and detect anomalies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VarianceType(StrEnum):
    FAVORABLE = "favorable"
    UNFAVORABLE = "unfavorable"
    NEUTRAL = "neutral"
    SPIKE = "spike"
    SEASONAL = "seasonal"


class VarianceSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class VarianceSource(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    LICENSING = "licensing"
    SUPPORT = "support"


# --- Models ---


class VarianceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    variance_id: str = ""
    variance_type: VarianceType = VarianceType.NEUTRAL
    variance_severity: VarianceSeverity = VarianceSeverity.NEGLIGIBLE
    variance_source: VarianceSource = VarianceSource.COMPUTE
    variance_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class VarianceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    variance_id: str = ""
    variance_type: VarianceType = VarianceType.NEUTRAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CostVarianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_variance_count: int = 0
    avg_variance_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    top_variances: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostVarianceAnalyzer:
    """Analyze cost variances between budgeted and actual spend."""

    def __init__(
        self,
        max_records: int = 200000,
        max_variance_pct: float = 20.0,
    ) -> None:
        self._max_records = max_records
        self._max_variance_pct = max_variance_pct
        self._records: list[VarianceRecord] = []
        self._analyses: list[VarianceAnalysis] = []
        logger.info(
            "cost_variance_analyzer.initialized",
            max_records=max_records,
            max_variance_pct=max_variance_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_variance(
        self,
        variance_id: str,
        variance_type: VarianceType = VarianceType.NEUTRAL,
        variance_severity: VarianceSeverity = VarianceSeverity.NEGLIGIBLE,
        variance_source: VarianceSource = VarianceSource.COMPUTE,
        variance_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> VarianceRecord:
        record = VarianceRecord(
            variance_id=variance_id,
            variance_type=variance_type,
            variance_severity=variance_severity,
            variance_source=variance_source,
            variance_pct=variance_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cost_variance_analyzer.variance_recorded",
            record_id=record.id,
            variance_id=variance_id,
            variance_type=variance_type.value,
            variance_severity=variance_severity.value,
        )
        return record

    def get_variance(self, record_id: str) -> VarianceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_variances(
        self,
        variance_type: VarianceType | None = None,
        variance_severity: VarianceSeverity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[VarianceRecord]:
        results = list(self._records)
        if variance_type is not None:
            results = [r for r in results if r.variance_type == variance_type]
        if variance_severity is not None:
            results = [r for r in results if r.variance_severity == variance_severity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        variance_id: str,
        variance_type: VarianceType = VarianceType.NEUTRAL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> VarianceAnalysis:
        analysis = VarianceAnalysis(
            variance_id=variance_id,
            variance_type=variance_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "cost_variance_analyzer.analysis_added",
            variance_id=variance_id,
            variance_type=variance_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_variance_distribution(self) -> dict[str, Any]:
        """Group by variance_type; return count and avg variance_pct."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.variance_type.value
            type_data.setdefault(key, []).append(r.variance_pct)
        result: dict[str, Any] = {}
        for vtype, pcts in type_data.items():
            result[vtype] = {
                "count": len(pcts),
                "avg_variance_pct": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_high_variances(self) -> list[dict[str, Any]]:
        """Return variances where severity is CRITICAL or HIGH."""
        high_severities = {
            VarianceSeverity.CRITICAL,
            VarianceSeverity.HIGH,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.variance_severity in high_severities:
                results.append(
                    {
                        "record_id": r.id,
                        "variance_id": r.variance_id,
                        "variance_type": r.variance_type.value,
                        "variance_severity": r.variance_severity.value,
                        "variance_pct": r.variance_pct,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["variance_pct"], reverse=True)
        return results

    def rank_by_variance(self) -> list[dict[str, Any]]:
        """Group by service, avg variance_pct, sort desc."""
        service_pcts: dict[str, list[float]] = {}
        for r in self._records:
            service_pcts.setdefault(r.service, []).append(r.variance_pct)
        results: list[dict[str, Any]] = []
        for svc, pcts in service_pcts.items():
            results.append(
                {
                    "service": svc,
                    "avg_variance_pct": round(sum(pcts) / len(pcts), 2),
                    "record_count": len(pcts),
                }
            )
        results.sort(key=lambda x: x["avg_variance_pct"], reverse=True)
        return results

    def detect_variance_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [a.analysis_score for a in self._analyses]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> CostVarianceReport:
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for r in self._records:
            by_type[r.variance_type.value] = by_type.get(r.variance_type.value, 0) + 1
            by_severity[r.variance_severity.value] = (
                by_severity.get(r.variance_severity.value, 0) + 1
            )
            by_source[r.variance_source.value] = by_source.get(r.variance_source.value, 0) + 1
        high_variance_count = len(self.identify_high_variances())
        avg_var = (
            round(
                sum(r.variance_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        high_list = self.identify_high_variances()
        top_variances = list(dict.fromkeys(h["service"] for h in high_list))
        recs: list[str] = []
        if high_variance_count > 0:
            recs.append(
                f"{high_variance_count} high-variance record(s) detected — review cost allocations"
            )
        over_threshold = sum(1 for r in self._records if r.variance_pct > self._max_variance_pct)
        if over_threshold > 0:
            recs.append(f"{over_threshold} variance(s) above threshold ({self._max_variance_pct}%)")
        if not recs:
            recs.append("Variance levels are acceptable")
        return CostVarianceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_variance_count=high_variance_count,
            avg_variance_pct=avg_var,
            by_type=by_type,
            by_severity=by_severity,
            by_source=by_source,
            top_variances=top_variances,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("cost_variance_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.variance_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "max_variance_pct": self._max_variance_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
