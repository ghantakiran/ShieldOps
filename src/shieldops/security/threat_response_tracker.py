"""Threat Response Tracker — track threat response activities and effectiveness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ThreatCategory(StrEnum):
    MALWARE = "malware"
    PHISHING = "phishing"
    INTRUSION = "intrusion"
    DATA_EXFILTRATION = "data_exfiltration"
    INSIDER_THREAT = "insider_threat"


class ResponseStatus(StrEnum):
    CONTAINED = "contained"
    INVESTIGATING = "investigating"
    ERADICATING = "eradicating"
    RECOVERING = "recovering"
    CLOSED = "closed"


class ResponseEffectiveness(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    POOR = "poor"
    FAILED = "failed"


# --- Models ---


class ThreatResponseRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_id: str = ""
    threat_category: ThreatCategory = ThreatCategory.MALWARE
    response_status: ResponseStatus = ResponseStatus.INVESTIGATING
    response_effectiveness: ResponseEffectiveness = ResponseEffectiveness.ADEQUATE
    response_time_hours: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ResponseAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_id: str = ""
    threat_category: ThreatCategory = ThreatCategory.MALWARE
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ThreatResponseReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    active_threats: int = 0
    avg_response_time_hours: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_effectiveness: dict[str, int] = Field(default_factory=dict)
    top_slow_responses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThreatResponseTracker:
    """Track threat response activities, measure effectiveness, detect gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        max_response_time_hours: float = 4.0,
    ) -> None:
        self._max_records = max_records
        self._max_response_time_hours = max_response_time_hours
        self._records: list[ThreatResponseRecord] = []
        self._assessments: list[ResponseAssessment] = []
        logger.info(
            "threat_response_tracker.initialized",
            max_records=max_records,
            max_response_time_hours=max_response_time_hours,
        )

    # -- record / get / list ------------------------------------------------

    def record_response(
        self,
        threat_id: str,
        threat_category: ThreatCategory = ThreatCategory.MALWARE,
        response_status: ResponseStatus = ResponseStatus.INVESTIGATING,
        response_effectiveness: ResponseEffectiveness = (ResponseEffectiveness.ADEQUATE),
        response_time_hours: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ThreatResponseRecord:
        record = ThreatResponseRecord(
            threat_id=threat_id,
            threat_category=threat_category,
            response_status=response_status,
            response_effectiveness=response_effectiveness,
            response_time_hours=response_time_hours,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "threat_response_tracker.response_recorded",
            record_id=record.id,
            threat_id=threat_id,
            threat_category=threat_category.value,
            response_status=response_status.value,
        )
        return record

    def get_response(self, record_id: str) -> ThreatResponseRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_responses(
        self,
        threat_category: ThreatCategory | None = None,
        response_status: ResponseStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ThreatResponseRecord]:
        results = list(self._records)
        if threat_category is not None:
            results = [r for r in results if r.threat_category == threat_category]
        if response_status is not None:
            results = [r for r in results if r.response_status == response_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        threat_id: str,
        threat_category: ThreatCategory = ThreatCategory.MALWARE,
        assessment_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ResponseAssessment:
        assessment = ResponseAssessment(
            threat_id=threat_id,
            threat_category=threat_category,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "threat_response_tracker.assessment_added",
            threat_id=threat_id,
            threat_category=threat_category.value,
            assessment_score=assessment_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_response_distribution(self) -> dict[str, Any]:
        """Group by threat_category; return count and avg response time."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.threat_category.value
            cat_data.setdefault(key, []).append(r.response_time_hours)
        result: dict[str, Any] = {}
        for cat, times in cat_data.items():
            result[cat] = {
                "count": len(times),
                "avg_response_time": round(sum(times) / len(times), 2),
            }
        return result

    def identify_slow_responses(self) -> list[dict[str, Any]]:
        """Return responses where response_time_hours > max."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.response_time_hours > self._max_response_time_hours:
                results.append(
                    {
                        "record_id": r.id,
                        "threat_id": r.threat_id,
                        "threat_category": r.threat_category.value,
                        "response_status": r.response_status.value,
                        "response_effectiveness": (r.response_effectiveness.value),
                        "response_time_hours": r.response_time_hours,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["response_time_hours"], reverse=True)
        return results

    def rank_by_response_time(self) -> list[dict[str, Any]]:
        """Group by service, avg response_time_hours, sort desc."""
        svc_times: dict[str, list[float]] = {}
        for r in self._records:
            svc_times.setdefault(r.service, []).append(r.response_time_hours)
        results: list[dict[str, Any]] = []
        for svc, times in svc_times.items():
            results.append(
                {
                    "service": svc,
                    "avg_response_time": round(sum(times) / len(times), 2),
                    "response_count": len(times),
                }
            )
        results.sort(key=lambda x: x["avg_response_time"], reverse=True)
        return results

    def detect_response_trends(self) -> dict[str, Any]:
        """Split-half comparison on assessment_score; delta threshold 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [a.assessment_score for a in self._assessments]
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

    def generate_report(self) -> ThreatResponseReport:
        by_category: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_effectiveness: dict[str, int] = {}
        for r in self._records:
            by_category[r.threat_category.value] = by_category.get(r.threat_category.value, 0) + 1
            by_status[r.response_status.value] = by_status.get(r.response_status.value, 0) + 1
            by_effectiveness[r.response_effectiveness.value] = (
                by_effectiveness.get(r.response_effectiveness.value, 0) + 1
            )
        active_threats = sum(
            1
            for r in self._records
            if r.response_status not in {ResponseStatus.CLOSED, ResponseStatus.CONTAINED}
        )
        avg_time = (
            round(
                sum(r.response_time_hours for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        slow = self.identify_slow_responses()
        top_slow_responses = [s["threat_id"] for s in slow]
        recs: list[str] = []
        if slow:
            recs.append(
                f"{len(slow)} slow response(s) detected"
                f" — exceeded {self._max_response_time_hours}h threshold"
            )
        if active_threats > 0:
            recs.append(f"{active_threats} active threat(s) require attention")
        if not recs:
            recs.append("Threat response levels are acceptable")
        return ThreatResponseReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            active_threats=active_threats,
            avg_response_time_hours=avg_time,
            by_category=by_category,
            by_status=by_status,
            by_effectiveness=by_effectiveness,
            top_slow_responses=top_slow_responses,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("threat_response_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.threat_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "max_response_time_hours": self._max_response_time_hours,
            "category_distribution": cat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_threats": len({r.threat_id for r in self._records}),
        }
