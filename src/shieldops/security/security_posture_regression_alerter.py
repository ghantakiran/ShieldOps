"""Security Posture Regression Alerter — detect posture regressions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RegressionType(StrEnum):
    CONFIGURATION = "configuration"
    ACCESS_CONTROL = "access_control"
    VULNERABILITY = "vulnerability"
    COMPLIANCE = "compliance"
    MONITORING = "monitoring"


class RegressionCause(StrEnum):
    DEPLOYMENT = "deployment"
    CONFIGURATION_CHANGE = "configuration_change"
    POLICY_UPDATE = "policy_update"
    INFRASTRUCTURE = "infrastructure"
    HUMAN_ERROR = "human_error"


class AlertAction(StrEnum):
    AUTO_REMEDIATE = "auto_remediate"
    ESCALATE = "escalate"
    MONITOR = "monitor"
    ROLLBACK = "rollback"
    ACCEPT = "accept"


# --- Models ---


class RegressionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    regression_id: str = ""
    regression_type: RegressionType = RegressionType.CONFIGURATION
    regression_cause: RegressionCause = RegressionCause.DEPLOYMENT
    alert_action: AlertAction = AlertAction.AUTO_REMEDIATE
    regression_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RegressionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    regression_id: str = ""
    regression_type: RegressionType = RegressionType.CONFIGURATION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SecurityPostureRegressionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_regression_score: float = 0.0
    by_regression_type: dict[str, int] = Field(default_factory=dict)
    by_regression_cause: dict[str, int] = Field(default_factory=dict)
    by_alert_action: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityPostureRegressionAlerter:
    """Detect and alert on security posture regressions."""

    def __init__(
        self,
        max_records: int = 200000,
        regression_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._regression_gap_threshold = regression_gap_threshold
        self._records: list[RegressionRecord] = []
        self._analyses: list[RegressionAnalysis] = []
        logger.info(
            "security_posture_regression_alerter.initialized",
            max_records=max_records,
            regression_gap_threshold=regression_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_regression(
        self,
        regression_id: str,
        regression_type: RegressionType = RegressionType.CONFIGURATION,
        regression_cause: RegressionCause = RegressionCause.DEPLOYMENT,
        alert_action: AlertAction = AlertAction.AUTO_REMEDIATE,
        regression_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RegressionRecord:
        record = RegressionRecord(
            regression_id=regression_id,
            regression_type=regression_type,
            regression_cause=regression_cause,
            alert_action=alert_action,
            regression_score=regression_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_posture_regression_alerter.recorded",
            record_id=record.id,
            regression_id=regression_id,
            regression_type=regression_type.value,
            regression_cause=regression_cause.value,
        )
        return record

    def get_regression(self, record_id: str) -> RegressionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_regressions(
        self,
        regression_type: RegressionType | None = None,
        regression_cause: RegressionCause | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RegressionRecord]:
        results = list(self._records)
        if regression_type is not None:
            results = [r for r in results if r.regression_type == regression_type]
        if regression_cause is not None:
            results = [r for r in results if r.regression_cause == regression_cause]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        regression_id: str,
        regression_type: RegressionType = RegressionType.CONFIGURATION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RegressionAnalysis:
        analysis = RegressionAnalysis(
            regression_id=regression_id,
            regression_type=regression_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "security_posture_regression_alerter.analysis_added",
            regression_id=regression_id,
            regression_type=regression_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_regression_distribution(self) -> dict[str, Any]:
        data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.regression_type.value
            data.setdefault(key, []).append(r.regression_score)
        result: dict[str, Any] = {}
        for k, scores in data.items():
            result[k] = {
                "count": len(scores),
                "avg_regression_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_regression_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.regression_score < self._regression_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "regression_id": r.regression_id,
                        "regression_type": r.regression_type.value,
                        "regression_score": r.regression_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["regression_score"])

    def rank_by_regression(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.regression_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_regression_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_regression_score"])
        return results

    def detect_regression_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> SecurityPostureRegressionReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.regression_type.value] = by_e1.get(r.regression_type.value, 0) + 1
            by_e2[r.regression_cause.value] = by_e2.get(r.regression_cause.value, 0) + 1
            by_e3[r.alert_action.value] = by_e3.get(r.alert_action.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.regression_score < self._regression_gap_threshold
        )
        scores = [r.regression_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_regression_gaps()
        top_gaps = [o["regression_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} record(s) below threshold ({self._regression_gap_threshold})")
        if self._records and avg_score < self._regression_gap_threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._regression_gap_threshold})")
        if not recs:
            recs.append("SecurityPostureRegressionAlerter metrics are healthy")
        return SecurityPostureRegressionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_regression_score=avg_score,
            by_regression_type=by_e1,
            by_regression_cause=by_e2,
            by_alert_action=by_e3,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_posture_regression_alerter.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            key = r.regression_type.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "regression_gap_threshold": self._regression_gap_threshold,
            "regression_type_distribution": dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
