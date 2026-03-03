"""Shadow Data Discovery Engine — discover shadow data across unauthorized storage locations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ShadowSource(StrEnum):
    PERSONAL_CLOUD = "personal_cloud"
    SAAS_APP = "saas_app"
    LOCAL_STORAGE = "local_storage"
    EMAIL = "email"
    REMOVABLE_MEDIA = "removable_media"


class DataRisk(StrEnum):
    REGULATED = "regulated"
    SENSITIVE = "sensitive"
    INTERNAL = "internal"
    LOW_RISK = "low_risk"
    UNKNOWN = "unknown"


class DiscoveryStatus(StrEnum):
    DISCOVERED = "discovered"
    CONFIRMED = "confirmed"
    REMEDIATED = "remediated"
    ACCEPTED = "accepted"
    MONITORING = "monitoring"


# --- Models ---


class ShadowDataRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    shadow_id: str = ""
    shadow_source: ShadowSource = ShadowSource.PERSONAL_CLOUD
    data_risk: DataRisk = DataRisk.UNKNOWN
    discovery_status: DiscoveryStatus = DiscoveryStatus.DISCOVERED
    discovery_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ShadowDataAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    shadow_id: str = ""
    shadow_source: ShadowSource = ShadowSource.PERSONAL_CLOUD
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ShadowDataReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_discovery_score: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ShadowDataDiscoveryEngine:
    """Discover shadow data across unauthorized storage locations and assess risk."""

    def __init__(
        self,
        max_records: int = 200000,
        discovery_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._discovery_threshold = discovery_threshold
        self._records: list[ShadowDataRecord] = []
        self._analyses: list[ShadowDataAnalysis] = []
        logger.info(
            "shadow_data_discovery_engine.initialized",
            max_records=max_records,
            discovery_threshold=discovery_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_shadow(
        self,
        shadow_id: str,
        shadow_source: ShadowSource = ShadowSource.PERSONAL_CLOUD,
        data_risk: DataRisk = DataRisk.UNKNOWN,
        discovery_status: DiscoveryStatus = DiscoveryStatus.DISCOVERED,
        discovery_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ShadowDataRecord:
        record = ShadowDataRecord(
            shadow_id=shadow_id,
            shadow_source=shadow_source,
            data_risk=data_risk,
            discovery_status=discovery_status,
            discovery_score=discovery_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "shadow_data_discovery_engine.shadow_recorded",
            record_id=record.id,
            shadow_id=shadow_id,
            shadow_source=shadow_source.value,
            data_risk=data_risk.value,
        )
        return record

    def get_shadow(self, record_id: str) -> ShadowDataRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_shadows(
        self,
        shadow_source: ShadowSource | None = None,
        data_risk: DataRisk | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ShadowDataRecord]:
        results = list(self._records)
        if shadow_source is not None:
            results = [r for r in results if r.shadow_source == shadow_source]
        if data_risk is not None:
            results = [r for r in results if r.data_risk == data_risk]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        shadow_id: str,
        shadow_source: ShadowSource = ShadowSource.PERSONAL_CLOUD,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ShadowDataAnalysis:
        analysis = ShadowDataAnalysis(
            shadow_id=shadow_id,
            shadow_source=shadow_source,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "shadow_data_discovery_engine.analysis_added",
            shadow_id=shadow_id,
            shadow_source=shadow_source.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_source_distribution(self) -> dict[str, Any]:
        source_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.shadow_source.value
            source_data.setdefault(key, []).append(r.discovery_score)
        result: dict[str, Any] = {}
        for source, scores in source_data.items():
            result[source] = {
                "count": len(scores),
                "avg_discovery_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_shadow_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.discovery_score < self._discovery_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "shadow_id": r.shadow_id,
                        "shadow_source": r.shadow_source.value,
                        "discovery_score": r.discovery_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["discovery_score"])

    def rank_by_shadow(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.discovery_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_discovery_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_discovery_score"])
        return results

    def detect_shadow_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ShadowDataReport:
        by_source: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_source[r.shadow_source.value] = by_source.get(r.shadow_source.value, 0) + 1
            by_risk[r.data_risk.value] = by_risk.get(r.data_risk.value, 0) + 1
            by_status[r.discovery_status.value] = by_status.get(r.discovery_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.discovery_score < self._discovery_threshold)
        scores = [r.discovery_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_shadow_gaps()
        top_gaps = [o["shadow_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} shadow data instance(s) below threshold ({self._discovery_threshold})"
            )
        if self._records and avg_score < self._discovery_threshold:
            recs.append(
                f"Avg discovery score {avg_score} below threshold ({self._discovery_threshold})"
            )
        if not recs:
            recs.append("Shadow data discovery is healthy")
        return ShadowDataReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_discovery_score=avg_score,
            by_source=by_source,
            by_risk=by_risk,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("shadow_data_discovery_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        source_dist: dict[str, int] = {}
        for r in self._records:
            key = r.shadow_source.value
            source_dist[key] = source_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "discovery_threshold": self._discovery_threshold,
            "source_distribution": source_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
