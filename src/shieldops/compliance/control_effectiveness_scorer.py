"""Control Effectiveness Scorer — control test results and effectiveness index."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ControlType(StrEnum):
    PREVENTIVE = "preventive"
    DETECTIVE = "detective"
    CORRECTIVE = "corrective"
    COMPENSATING = "compensating"
    DIRECTIVE = "directive"


class TestResult(StrEnum):
    PASS = "pass"  # noqa: S105
    FAIL = "fail"
    PARTIAL = "partial"
    NOT_TESTED = "not_tested"
    EXEMPT = "exempt"


class ControlMaturity(StrEnum):
    OPTIMIZED = "optimized"
    MANAGED = "managed"
    DEFINED = "defined"
    DEVELOPING = "developing"
    INITIAL = "initial"


# --- Models ---


class ControlRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_name: str = ""
    control_type: ControlType = ControlType.PREVENTIVE
    test_result: TestResult = TestResult.PASS
    control_maturity: ControlMaturity = ControlMaturity.OPTIMIZED
    effectiveness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ControlAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_name: str = ""
    control_type: ControlType = ControlType.PREVENTIVE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ControlEffectivenessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_effectiveness_count: int = 0
    avg_effectiveness_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    by_maturity: dict[str, int] = Field(default_factory=dict)
    top_low_effectiveness: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ControlEffectivenessScorer:
    """Control test results tracking and effectiveness index scoring."""

    def __init__(
        self,
        max_records: int = 200000,
        control_effectiveness_threshold: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._control_effectiveness_threshold = control_effectiveness_threshold
        self._records: list[ControlRecord] = []
        self._analyses: list[ControlAnalysis] = []
        logger.info(
            "control_effectiveness_scorer.initialized",
            max_records=max_records,
            control_effectiveness_threshold=control_effectiveness_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_control(
        self,
        control_name: str,
        control_type: ControlType = ControlType.PREVENTIVE,
        test_result: TestResult = TestResult.PASS,
        control_maturity: ControlMaturity = ControlMaturity.OPTIMIZED,
        effectiveness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ControlRecord:
        record = ControlRecord(
            control_name=control_name,
            control_type=control_type,
            test_result=test_result,
            control_maturity=control_maturity,
            effectiveness_score=effectiveness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "control_effectiveness_scorer.control_recorded",
            record_id=record.id,
            control_name=control_name,
            control_type=control_type.value,
            test_result=test_result.value,
        )
        return record

    def get_control(self, record_id: str) -> ControlRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_controls(
        self,
        control_type: ControlType | None = None,
        test_result: TestResult | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ControlRecord]:
        results = list(self._records)
        if control_type is not None:
            results = [r for r in results if r.control_type == control_type]
        if test_result is not None:
            results = [r for r in results if r.test_result == test_result]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        control_name: str,
        control_type: ControlType = ControlType.PREVENTIVE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ControlAnalysis:
        analysis = ControlAnalysis(
            control_name=control_name,
            control_type=control_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "control_effectiveness_scorer.analysis_added",
            control_name=control_name,
            control_type=control_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_type_distribution(self) -> dict[str, Any]:
        """Group by control_type; return count and avg effectiveness_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.control_type.value
            type_data.setdefault(key, []).append(r.effectiveness_score)
        result: dict[str, Any] = {}
        for ctype, scores in type_data.items():
            result[ctype] = {
                "count": len(scores),
                "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_effectiveness_controls(self) -> list[dict[str, Any]]:
        """Return records where effectiveness_score < control_effectiveness_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.effectiveness_score < self._control_effectiveness_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "control_name": r.control_name,
                        "control_type": r.control_type.value,
                        "effectiveness_score": r.effectiveness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["effectiveness_score"])

    def rank_by_effectiveness_score(self) -> list[dict[str, Any]]:
        """Group by service, avg effectiveness_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.effectiveness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_effectiveness_score"])
        return results

    def detect_effectiveness_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ControlEffectivenessReport:
        by_type: dict[str, int] = {}
        by_result: dict[str, int] = {}
        by_maturity: dict[str, int] = {}
        for r in self._records:
            by_type[r.control_type.value] = by_type.get(r.control_type.value, 0) + 1
            by_result[r.test_result.value] = by_result.get(r.test_result.value, 0) + 1
            by_maturity[r.control_maturity.value] = by_maturity.get(r.control_maturity.value, 0) + 1
        low_effectiveness_count = sum(
            1
            for r in self._records
            if r.effectiveness_score < self._control_effectiveness_threshold
        )
        scores = [r.effectiveness_score for r in self._records]
        avg_effectiveness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_effectiveness_controls()
        top_low_effectiveness = [o["control_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_effectiveness_count > 0:
            recs.append(
                f"{low_effectiveness_count} control(s) below effectiveness threshold "
                f"({self._control_effectiveness_threshold})"
            )
        if self._records and avg_effectiveness_score < self._control_effectiveness_threshold:
            recs.append(
                f"Avg effectiveness score {avg_effectiveness_score} below threshold "
                f"({self._control_effectiveness_threshold})"
            )
        if not recs:
            recs.append("Control effectiveness posture is healthy")
        return ControlEffectivenessReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_effectiveness_count=low_effectiveness_count,
            avg_effectiveness_score=avg_effectiveness_score,
            by_type=by_type,
            by_result=by_result,
            by_maturity=by_maturity,
            top_low_effectiveness=top_low_effectiveness,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("control_effectiveness_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.control_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "control_effectiveness_threshold": self._control_effectiveness_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
