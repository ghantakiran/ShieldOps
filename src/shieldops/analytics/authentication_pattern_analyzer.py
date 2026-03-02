"""Authentication Pattern Analyzer — analyze authentication patterns and detect anomalies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AuthMethod(StrEnum):
    PASSWORD = "password"  # noqa: S105
    MFA = "mfa"
    SSO = "sso"
    CERTIFICATE = "certificate"
    BIOMETRIC = "biometric"


class PatternType(StrEnum):
    LOGIN_TIME = "login_time"
    LOCATION = "location"
    DEVICE = "device"
    FAILURE_RATE = "failure_rate"
    SESSION_DURATION = "session_duration"


class PatternStatus(StrEnum):
    NORMAL = "normal"
    UNUSUAL = "unusual"
    SUSPICIOUS = "suspicious"
    ANOMALOUS = "anomalous"
    BLOCKED = "blocked"


# --- Models ---


class AuthPatternRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_name: str = ""
    auth_method: AuthMethod = AuthMethod.PASSWORD
    pattern_type: PatternType = PatternType.LOGIN_TIME
    pattern_status: PatternStatus = PatternStatus.NORMAL
    pattern_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AuthPatternAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_name: str = ""
    auth_method: AuthMethod = AuthMethod.PASSWORD
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuthPatternReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_pattern_score: float = 0.0
    by_auth_method: dict[str, int] = Field(default_factory=dict)
    by_pattern_type: dict[str, int] = Field(default_factory=dict)
    by_pattern_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuthenticationPatternAnalyzer:
    """Analyze authentication patterns, detect anomalies, and track login behaviors."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[AuthPatternRecord] = []
        self._analyses: list[AuthPatternAnalysis] = []
        logger.info(
            "authentication_pattern_analyzer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_pattern(
        self,
        user_name: str,
        auth_method: AuthMethod = AuthMethod.PASSWORD,
        pattern_type: PatternType = PatternType.LOGIN_TIME,
        pattern_status: PatternStatus = PatternStatus.NORMAL,
        pattern_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AuthPatternRecord:
        record = AuthPatternRecord(
            user_name=user_name,
            auth_method=auth_method,
            pattern_type=pattern_type,
            pattern_status=pattern_status,
            pattern_score=pattern_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "authentication_pattern_analyzer.pattern_recorded",
            record_id=record.id,
            user_name=user_name,
            auth_method=auth_method.value,
            pattern_type=pattern_type.value,
        )
        return record

    def get_record(self, record_id: str) -> AuthPatternRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        auth_method: AuthMethod | None = None,
        pattern_type: PatternType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AuthPatternRecord]:
        results = list(self._records)
        if auth_method is not None:
            results = [r for r in results if r.auth_method == auth_method]
        if pattern_type is not None:
            results = [r for r in results if r.pattern_type == pattern_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        user_name: str,
        auth_method: AuthMethod = AuthMethod.PASSWORD,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AuthPatternAnalysis:
        analysis = AuthPatternAnalysis(
            user_name=user_name,
            auth_method=auth_method,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "authentication_pattern_analyzer.analysis_added",
            user_name=user_name,
            auth_method=auth_method.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by auth_method; return count and avg pattern_score."""
        method_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.auth_method.value
            method_data.setdefault(key, []).append(r.pattern_score)
        result: dict[str, Any] = {}
        for method, scores in method_data.items():
            result[method] = {
                "count": len(scores),
                "avg_pattern_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where pattern_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.pattern_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "user_name": r.user_name,
                        "auth_method": r.auth_method.value,
                        "pattern_score": r.pattern_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["pattern_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg pattern_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.pattern_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_pattern_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_pattern_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
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

    def generate_report(self) -> AuthPatternReport:
        by_auth_method: dict[str, int] = {}
        by_pattern_type: dict[str, int] = {}
        by_pattern_status: dict[str, int] = {}
        for r in self._records:
            by_auth_method[r.auth_method.value] = by_auth_method.get(r.auth_method.value, 0) + 1
            by_pattern_type[r.pattern_type.value] = by_pattern_type.get(r.pattern_type.value, 0) + 1
            by_pattern_status[r.pattern_status.value] = (
                by_pattern_status.get(r.pattern_status.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.pattern_score < self._threshold)
        scores = [r.pattern_score for r in self._records]
        avg_pattern_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["user_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} pattern(s) below threshold ({self._threshold})")
        if self._records and avg_pattern_score < self._threshold:
            recs.append(
                f"Avg pattern score {avg_pattern_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Authentication pattern analysis is healthy")
        return AuthPatternReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_pattern_score=avg_pattern_score,
            by_auth_method=by_auth_method,
            by_pattern_type=by_pattern_type,
            by_pattern_status=by_pattern_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("authentication_pattern_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        auth_method_dist: dict[str, int] = {}
        for r in self._records:
            key = r.auth_method.value
            auth_method_dist[key] = auth_method_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "auth_method_distribution": auth_method_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
