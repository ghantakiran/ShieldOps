"""API Exposure Analyzer — analyze API endpoints for security exposures."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class APIType(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"
    GRPC = "grpc"
    WEBSOCKET = "websocket"
    SOAP = "soap"


class ExposureLevel(StrEnum):
    PUBLIC = "public"
    PARTNER = "partner"
    INTERNAL = "internal"
    DEPRECATED = "deprecated"
    SHADOW = "shadow"


class APIRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


# --- Models ---


class APIExposureRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    endpoint_name: str = ""
    api_type: APIType = APIType.REST
    exposure_level: ExposureLevel = ExposureLevel.PUBLIC
    api_risk: APIRisk = APIRisk.MEDIUM
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class APIExposureAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    endpoint_name: str = ""
    api_type: APIType = APIType.REST
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class APIExposureReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_risk_score: float = 0.0
    by_api_type: dict[str, int] = Field(default_factory=dict)
    by_exposure_level: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class APIExposureAnalyzer:
    """Analyze API endpoints for security exposures, shadow APIs, and misconfigurations."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._risk_threshold = risk_threshold
        self._records: list[APIExposureRecord] = []
        self._analyses: list[APIExposureAnalysis] = []
        logger.info(
            "api_exposure_analyzer.initialized",
            max_records=max_records,
            risk_threshold=risk_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_exposure(
        self,
        endpoint_name: str,
        api_type: APIType = APIType.REST,
        exposure_level: ExposureLevel = ExposureLevel.PUBLIC,
        api_risk: APIRisk = APIRisk.MEDIUM,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> APIExposureRecord:
        record = APIExposureRecord(
            endpoint_name=endpoint_name,
            api_type=api_type,
            exposure_level=exposure_level,
            api_risk=api_risk,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "api_exposure_analyzer.exposure_recorded",
            record_id=record.id,
            endpoint_name=endpoint_name,
            api_type=api_type.value,
            exposure_level=exposure_level.value,
        )
        return record

    def get_exposure(self, record_id: str) -> APIExposureRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_exposures(
        self,
        api_type: APIType | None = None,
        exposure_level: ExposureLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[APIExposureRecord]:
        results = list(self._records)
        if api_type is not None:
            results = [r for r in results if r.api_type == api_type]
        if exposure_level is not None:
            results = [r for r in results if r.exposure_level == exposure_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        endpoint_name: str,
        api_type: APIType = APIType.REST,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> APIExposureAnalysis:
        analysis = APIExposureAnalysis(
            endpoint_name=endpoint_name,
            api_type=api_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "api_exposure_analyzer.analysis_added",
            endpoint_name=endpoint_name,
            api_type=api_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by api_type; return count and avg risk_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.api_type.value
            type_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for api_type, scores in type_data.items():
            result[api_type] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where risk_score < risk_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score < self._risk_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "endpoint_name": r.endpoint_name,
                        "api_type": r.api_type.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"])
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

    def generate_report(self) -> APIExposureReport:
        by_api_type: dict[str, int] = {}
        by_exposure_level: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_api_type[r.api_type.value] = by_api_type.get(r.api_type.value, 0) + 1
            by_exposure_level[r.exposure_level.value] = (
                by_exposure_level.get(r.exposure_level.value, 0) + 1
            )
            by_risk[r.api_risk.value] = by_risk.get(r.api_risk.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.risk_score < self._risk_threshold)
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["endpoint_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} API exposure(s) below risk threshold ({self._risk_threshold})"
            )
        if self._records and avg_risk_score < self._risk_threshold:
            recs.append(f"Avg risk score {avg_risk_score} below threshold ({self._risk_threshold})")
        if not recs:
            recs.append("API exposure analysis is healthy")
        return APIExposureReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_risk_score=avg_risk_score,
            by_api_type=by_api_type,
            by_exposure_level=by_exposure_level,
            by_risk=by_risk,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("api_exposure_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.api_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "risk_threshold": self._risk_threshold,
            "api_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
