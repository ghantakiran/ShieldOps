"""Configuration Baseline Enforcer — enforce configuration baselines."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BaselineSource(StrEnum):
    CIS_BENCHMARK = "cis_benchmark"
    VENDOR_HARDENING = "vendor_hardening"
    CUSTOM = "custom"
    INDUSTRY_STANDARD = "industry_standard"
    REGULATORY = "regulatory"


class DeviationType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    MISSING = "missing"
    UNAUTHORIZED = "unauthorized"


class EnforcementResult(StrEnum):
    COMPLIANT = "compliant"
    REMEDIATED = "remediated"
    EXCEPTION = "exception"
    FAILED = "failed"
    PENDING = "pending"


# --- Models ---


class BaselineRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    baseline_id: str = ""
    baseline_source: BaselineSource = BaselineSource.CIS_BENCHMARK
    deviation_type: DeviationType = DeviationType.ADDED
    enforcement_result: EnforcementResult = EnforcementResult.COMPLIANT
    compliance_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class BaselineAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    baseline_id: str = ""
    baseline_source: BaselineSource = BaselineSource.CIS_BENCHMARK
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ConfigurationBaselineReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_compliance_score: float = 0.0
    by_baseline_source: dict[str, int] = Field(default_factory=dict)
    by_deviation_type: dict[str, int] = Field(default_factory=dict)
    by_enforcement_result: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ConfigurationBaselineEnforcer:
    """Enforce configuration baselines and detect deviations."""

    def __init__(
        self,
        max_records: int = 200000,
        compliance_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._compliance_gap_threshold = compliance_gap_threshold
        self._records: list[BaselineRecord] = []
        self._analyses: list[BaselineAnalysis] = []
        logger.info(
            "configuration_baseline_enforcer.initialized",
            max_records=max_records,
            compliance_gap_threshold=compliance_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_baseline(
        self,
        baseline_id: str,
        baseline_source: BaselineSource = BaselineSource.CIS_BENCHMARK,
        deviation_type: DeviationType = DeviationType.ADDED,
        enforcement_result: EnforcementResult = EnforcementResult.COMPLIANT,
        compliance_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> BaselineRecord:
        record = BaselineRecord(
            baseline_id=baseline_id,
            baseline_source=baseline_source,
            deviation_type=deviation_type,
            enforcement_result=enforcement_result,
            compliance_score=compliance_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "configuration_baseline_enforcer.recorded",
            record_id=record.id,
            baseline_id=baseline_id,
            baseline_source=baseline_source.value,
            deviation_type=deviation_type.value,
        )
        return record

    def get_baseline(self, record_id: str) -> BaselineRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_baselines(
        self,
        baseline_source: BaselineSource | None = None,
        deviation_type: DeviationType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[BaselineRecord]:
        results = list(self._records)
        if baseline_source is not None:
            results = [r for r in results if r.baseline_source == baseline_source]
        if deviation_type is not None:
            results = [r for r in results if r.deviation_type == deviation_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        baseline_id: str,
        baseline_source: BaselineSource = BaselineSource.CIS_BENCHMARK,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> BaselineAnalysis:
        analysis = BaselineAnalysis(
            baseline_id=baseline_id,
            baseline_source=baseline_source,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "configuration_baseline_enforcer.analysis_added",
            baseline_id=baseline_id,
            baseline_source=baseline_source.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_baseline_distribution(self) -> dict[str, Any]:
        data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.baseline_source.value
            data.setdefault(key, []).append(r.compliance_score)
        result: dict[str, Any] = {}
        for k, scores in data.items():
            result[k] = {
                "count": len(scores),
                "avg_compliance_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_baseline_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_score < self._compliance_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "baseline_id": r.baseline_id,
                        "baseline_source": r.baseline_source.value,
                        "compliance_score": r.compliance_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["compliance_score"])

    def rank_by_baseline(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.compliance_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_compliance_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_compliance_score"])
        return results

    def detect_baseline_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
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

    def generate_report(self) -> ConfigurationBaselineReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.baseline_source.value] = by_e1.get(r.baseline_source.value, 0) + 1
            by_e2[r.deviation_type.value] = by_e2.get(r.deviation_type.value, 0) + 1
            by_e3[r.enforcement_result.value] = by_e3.get(r.enforcement_result.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.compliance_score < self._compliance_gap_threshold
        )
        scores = [r.compliance_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_baseline_gaps()
        top_gaps = [o["baseline_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} record(s) below threshold ({self._compliance_gap_threshold})")
        if self._records and avg_score < self._compliance_gap_threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._compliance_gap_threshold})")
        if not recs:
            recs.append("ConfigurationBaselineEnforcer metrics are healthy")
        return ConfigurationBaselineReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_compliance_score=avg_score,
            by_baseline_source=by_e1,
            by_deviation_type=by_e2,
            by_enforcement_result=by_e3,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("configuration_baseline_enforcer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            key = r.baseline_source.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "compliance_gap_threshold": self._compliance_gap_threshold,
            "baseline_source_distribution": dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
