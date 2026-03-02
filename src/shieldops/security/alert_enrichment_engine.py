"""Alert Enrichment Engine — enrich alerts with asset context, geo-IP, reputation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EnrichmentSource(StrEnum):
    ASSET_DB = "asset_db"
    GEO_IP = "geo_ip"
    REPUTATION = "reputation"
    THREAT_INTEL = "threat_intel"
    WHOIS = "whois"


class EnrichmentType(StrEnum):
    IP_CONTEXT = "ip_context"
    DOMAIN_CONTEXT = "domain_context"
    USER_CONTEXT = "user_context"
    FILE_CONTEXT = "file_context"
    NETWORK_CONTEXT = "network_context"


class EnrichmentQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    POOR = "poor"
    MISSING = "missing"


# --- Models ---


class EnrichmentRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str = ""
    enrichment_source: EnrichmentSource = EnrichmentSource.ASSET_DB
    enrichment_type: EnrichmentType = EnrichmentType.IP_CONTEXT
    enrichment_quality: EnrichmentQuality = EnrichmentQuality.EXCELLENT
    enrichment_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EnrichmentAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str = ""
    enrichment_source: EnrichmentSource = EnrichmentSource.ASSET_DB
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EnrichmentReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_quality_count: int = 0
    avg_enrichment_score: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    by_quality: dict[str, int] = Field(default_factory=dict)
    top_low_quality: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertEnrichmentEngine:
    """Enrich alerts with asset context, geo-IP, reputation data."""

    def __init__(
        self,
        max_records: int = 200000,
        enrichment_quality_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._enrichment_quality_threshold = enrichment_quality_threshold
        self._records: list[EnrichmentRecord] = []
        self._analyses: list[EnrichmentAnalysis] = []
        logger.info(
            "alert_enrichment_engine.initialized",
            max_records=max_records,
            enrichment_quality_threshold=enrichment_quality_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_enrichment(
        self,
        alert_id: str,
        enrichment_source: EnrichmentSource = EnrichmentSource.ASSET_DB,
        enrichment_type: EnrichmentType = EnrichmentType.IP_CONTEXT,
        enrichment_quality: EnrichmentQuality = EnrichmentQuality.EXCELLENT,
        enrichment_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> EnrichmentRecord:
        record = EnrichmentRecord(
            alert_id=alert_id,
            enrichment_source=enrichment_source,
            enrichment_type=enrichment_type,
            enrichment_quality=enrichment_quality,
            enrichment_score=enrichment_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_enrichment_engine.enrichment_recorded",
            record_id=record.id,
            alert_id=alert_id,
            enrichment_source=enrichment_source.value,
            enrichment_type=enrichment_type.value,
        )
        return record

    def get_enrichment(self, record_id: str) -> EnrichmentRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_enrichments(
        self,
        enrichment_source: EnrichmentSource | None = None,
        enrichment_type: EnrichmentType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EnrichmentRecord]:
        results = list(self._records)
        if enrichment_source is not None:
            results = [r for r in results if r.enrichment_source == enrichment_source]
        if enrichment_type is not None:
            results = [r for r in results if r.enrichment_type == enrichment_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        alert_id: str,
        enrichment_source: EnrichmentSource = EnrichmentSource.ASSET_DB,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> EnrichmentAnalysis:
        analysis = EnrichmentAnalysis(
            alert_id=alert_id,
            enrichment_source=enrichment_source,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "alert_enrichment_engine.analysis_added",
            alert_id=alert_id,
            enrichment_source=enrichment_source.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_enrichment_distribution(self) -> dict[str, Any]:
        """Group by enrichment_source; return count and avg enrichment_score."""
        src_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.enrichment_source.value
            src_data.setdefault(key, []).append(r.enrichment_score)
        result: dict[str, Any] = {}
        for src, scores in src_data.items():
            result[src] = {
                "count": len(scores),
                "avg_enrichment_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_quality_enrichments(self) -> list[dict[str, Any]]:
        """Return records where enrichment_score < enrichment_quality_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.enrichment_score < self._enrichment_quality_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "alert_id": r.alert_id,
                        "enrichment_source": r.enrichment_source.value,
                        "enrichment_score": r.enrichment_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["enrichment_score"])

    def rank_by_enrichment(self) -> list[dict[str, Any]]:
        """Group by service, avg enrichment_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.enrichment_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_enrichment_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_enrichment_score"])
        return results

    def detect_enrichment_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> EnrichmentReport:
        by_source: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_quality: dict[str, int] = {}
        for r in self._records:
            by_source[r.enrichment_source.value] = by_source.get(r.enrichment_source.value, 0) + 1
            by_type[r.enrichment_type.value] = by_type.get(r.enrichment_type.value, 0) + 1
            by_quality[r.enrichment_quality.value] = (
                by_quality.get(r.enrichment_quality.value, 0) + 1
            )
        low_quality_count = sum(
            1 for r in self._records if r.enrichment_score < self._enrichment_quality_threshold
        )
        scores = [r.enrichment_score for r in self._records]
        avg_enrichment_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_quality_enrichments()
        top_low_quality = [o["alert_id"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_quality_count > 0:
            recs.append(
                f"{low_quality_count} enrichment(s) below quality threshold "
                f"({self._enrichment_quality_threshold})"
            )
        if self._records and avg_enrichment_score < self._enrichment_quality_threshold:
            recs.append(
                f"Avg enrichment score {avg_enrichment_score} below threshold "
                f"({self._enrichment_quality_threshold})"
            )
        if not recs:
            recs.append("Alert enrichment quality is healthy")
        return EnrichmentReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_quality_count=low_quality_count,
            avg_enrichment_score=avg_enrichment_score,
            by_source=by_source,
            by_type=by_type,
            by_quality=by_quality,
            top_low_quality=top_low_quality,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("alert_enrichment_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        source_dist: dict[str, int] = {}
        for r in self._records:
            key = r.enrichment_source.value
            source_dist[key] = source_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "enrichment_quality_threshold": self._enrichment_quality_threshold,
            "source_distribution": source_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
