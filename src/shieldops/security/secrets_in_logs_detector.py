"""Secrets in Logs Detector — detect secrets and credentials exposed in log files."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SecretPattern(StrEnum):
    API_KEY = "api_key"
    PASSWORD = "password"  # noqa: S105
    TOKEN = "token"  # noqa: S105
    CERTIFICATE = "certificate"
    CONNECTION_STRING = "connection_string"


class LogSource(StrEnum):
    APPLICATION = "application"
    INFRASTRUCTURE = "infrastructure"
    CONTAINER = "container"
    CI_CD = "ci_cd"
    MONITORING = "monitoring"


class DetectionAction(StrEnum):
    REDACT = "redact"
    ALERT = "alert"
    QUARANTINE = "quarantine"
    ROTATE = "rotate"
    IGNORE = "ignore"


# --- Models ---


class SecretsLogRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    detection_id: str = ""
    secret_pattern: SecretPattern = SecretPattern.API_KEY
    log_source: LogSource = LogSource.APPLICATION
    detection_action: DetectionAction = DetectionAction.ALERT
    detection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SecretsLogAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    detection_id: str = ""
    secret_pattern: SecretPattern = SecretPattern.API_KEY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SecretsLogReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_detection_score: float = 0.0
    by_pattern: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecretsInLogsDetector:
    """Detect secrets and credentials exposed in log files across sources."""

    def __init__(
        self,
        max_records: int = 200000,
        detection_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._detection_threshold = detection_threshold
        self._records: list[SecretsLogRecord] = []
        self._analyses: list[SecretsLogAnalysis] = []
        logger.info(
            "secrets_in_logs_detector.initialized",
            max_records=max_records,
            detection_threshold=detection_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_secret(
        self,
        detection_id: str,
        secret_pattern: SecretPattern = SecretPattern.API_KEY,
        log_source: LogSource = LogSource.APPLICATION,
        detection_action: DetectionAction = DetectionAction.ALERT,
        detection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SecretsLogRecord:
        record = SecretsLogRecord(
            detection_id=detection_id,
            secret_pattern=secret_pattern,
            log_source=log_source,
            detection_action=detection_action,
            detection_score=detection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "secrets_in_logs_detector.secret_recorded",
            record_id=record.id,
            detection_id=detection_id,
            secret_pattern=secret_pattern.value,
            log_source=log_source.value,
        )
        return record

    def get_secret(self, record_id: str) -> SecretsLogRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_secrets(
        self,
        secret_pattern: SecretPattern | None = None,
        log_source: LogSource | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SecretsLogRecord]:
        results = list(self._records)
        if secret_pattern is not None:
            results = [r for r in results if r.secret_pattern == secret_pattern]
        if log_source is not None:
            results = [r for r in results if r.log_source == log_source]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        detection_id: str,
        secret_pattern: SecretPattern = SecretPattern.API_KEY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SecretsLogAnalysis:
        analysis = SecretsLogAnalysis(
            detection_id=detection_id,
            secret_pattern=secret_pattern,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "secrets_in_logs_detector.analysis_added",
            detection_id=detection_id,
            secret_pattern=secret_pattern.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_pattern_distribution(self) -> dict[str, Any]:
        pattern_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.secret_pattern.value
            pattern_data.setdefault(key, []).append(r.detection_score)
        result: dict[str, Any] = {}
        for pattern, scores in pattern_data.items():
            result[pattern] = {
                "count": len(scores),
                "avg_detection_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_detection_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.detection_score < self._detection_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "detection_id": r.detection_id,
                        "secret_pattern": r.secret_pattern.value,
                        "detection_score": r.detection_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["detection_score"])

    def rank_by_detection(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.detection_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_detection_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_detection_score"])
        return results

    def detect_secret_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> SecretsLogReport:
        by_pattern: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in self._records:
            by_pattern[r.secret_pattern.value] = by_pattern.get(r.secret_pattern.value, 0) + 1
            by_source[r.log_source.value] = by_source.get(r.log_source.value, 0) + 1
            by_action[r.detection_action.value] = by_action.get(r.detection_action.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.detection_score < self._detection_threshold)
        scores = [r.detection_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_detection_gaps()
        top_gaps = [o["detection_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} secret(s) below detection threshold ({self._detection_threshold})"
            )
        if self._records and avg_score < self._detection_threshold:
            recs.append(
                f"Avg detection score {avg_score} below threshold ({self._detection_threshold})"
            )
        if not recs:
            recs.append("Secrets in logs detection is healthy")
        return SecretsLogReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_detection_score=avg_score,
            by_pattern=by_pattern,
            by_source=by_source,
            by_action=by_action,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("secrets_in_logs_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        pattern_dist: dict[str, int] = {}
        for r in self._records:
            key = r.secret_pattern.value
            pattern_dist[key] = pattern_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "detection_threshold": self._detection_threshold,
            "pattern_distribution": pattern_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
