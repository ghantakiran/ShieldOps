"""Continuous Control Validator — validate security controls continuously."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ControlFramework(StrEnum):
    NIST_CSF = "nist_csf"
    ISO_27001 = "iso_27001"
    CIS_CONTROLS = "cis_controls"
    COBIT = "cobit"
    SOC2_TSC = "soc2_tsc"


class ValidationFrequency(StrEnum):
    CONTINUOUS = "continuous"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ON_DEMAND = "on_demand"


class ControlEffectiveness(StrEnum):
    EFFECTIVE = "effective"
    PARTIALLY_EFFECTIVE = "partially_effective"
    INEFFECTIVE = "ineffective"
    NOT_IMPLEMENTED = "not_implemented"
    NOT_APPLICABLE = "not_applicable"


# --- Models ---


class ControlValidationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    validation_id: str = ""
    control_framework: ControlFramework = ControlFramework.NIST_CSF
    validation_frequency: ValidationFrequency = ValidationFrequency.CONTINUOUS
    control_effectiveness: ControlEffectiveness = ControlEffectiveness.EFFECTIVE
    validation_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ControlValidationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    validation_id: str = ""
    control_framework: ControlFramework = ControlFramework.NIST_CSF
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ContinuousControlValidationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_validation_score: float = 0.0
    by_control_framework: dict[str, int] = Field(default_factory=dict)
    by_validation_frequency: dict[str, int] = Field(default_factory=dict)
    by_control_effectiveness: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ContinuousControlValidator:
    """Continuously validate security control effectiveness."""

    def __init__(
        self,
        max_records: int = 200000,
        validation_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._validation_gap_threshold = validation_gap_threshold
        self._records: list[ControlValidationRecord] = []
        self._analyses: list[ControlValidationAnalysis] = []
        logger.info(
            "continuous_control_validator.initialized",
            max_records=max_records,
            validation_gap_threshold=validation_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_validation(
        self,
        validation_id: str,
        control_framework: ControlFramework = ControlFramework.NIST_CSF,
        validation_frequency: ValidationFrequency = ValidationFrequency.CONTINUOUS,
        control_effectiveness: ControlEffectiveness = ControlEffectiveness.EFFECTIVE,
        validation_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ControlValidationRecord:
        record = ControlValidationRecord(
            validation_id=validation_id,
            control_framework=control_framework,
            validation_frequency=validation_frequency,
            control_effectiveness=control_effectiveness,
            validation_score=validation_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "continuous_control_validator.recorded",
            record_id=record.id,
            validation_id=validation_id,
            control_framework=control_framework.value,
            validation_frequency=validation_frequency.value,
        )
        return record

    def get_validation(self, record_id: str) -> ControlValidationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_validations(
        self,
        control_framework: ControlFramework | None = None,
        validation_frequency: ValidationFrequency | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ControlValidationRecord]:
        results = list(self._records)
        if control_framework is not None:
            results = [r for r in results if r.control_framework == control_framework]
        if validation_frequency is not None:
            results = [r for r in results if r.validation_frequency == validation_frequency]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        validation_id: str,
        control_framework: ControlFramework = ControlFramework.NIST_CSF,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ControlValidationAnalysis:
        analysis = ControlValidationAnalysis(
            validation_id=validation_id,
            control_framework=control_framework,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "continuous_control_validator.analysis_added",
            validation_id=validation_id,
            control_framework=control_framework.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_validation_distribution(self) -> dict[str, Any]:
        data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.control_framework.value
            data.setdefault(key, []).append(r.validation_score)
        result: dict[str, Any] = {}
        for k, scores in data.items():
            result[k] = {
                "count": len(scores),
                "avg_validation_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_validation_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.validation_score < self._validation_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "validation_id": r.validation_id,
                        "control_framework": r.control_framework.value,
                        "validation_score": r.validation_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["validation_score"])

    def rank_by_validation(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.validation_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_validation_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_validation_score"])
        return results

    def detect_validation_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ContinuousControlValidationReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.control_framework.value] = by_e1.get(r.control_framework.value, 0) + 1
            by_e2[r.validation_frequency.value] = by_e2.get(r.validation_frequency.value, 0) + 1
            by_e3[r.control_effectiveness.value] = by_e3.get(r.control_effectiveness.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.validation_score < self._validation_gap_threshold
        )
        scores = [r.validation_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_validation_gaps()
        top_gaps = [o["validation_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} record(s) below threshold ({self._validation_gap_threshold})")
        if self._records and avg_score < self._validation_gap_threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._validation_gap_threshold})")
        if not recs:
            recs.append("ContinuousControlValidator metrics are healthy")
        return ContinuousControlValidationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_validation_score=avg_score,
            by_control_framework=by_e1,
            by_validation_frequency=by_e2,
            by_control_effectiveness=by_e3,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("continuous_control_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            key = r.control_framework.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "validation_gap_threshold": self._validation_gap_threshold,
            "control_framework_distribution": dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
