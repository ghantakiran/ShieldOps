"""Alert Risk Enrichment Engine
enrich alerts with risk context, compute enrichment
completeness, detect stale enrichment data."""

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
    ASSET_CONTEXT = "asset_context"
    USER_CONTEXT = "user_context"
    THREAT_INTEL = "threat_intel"
    HISTORY = "history"


class EnrichmentQuality(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class AlertFidelity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NOISE = "noise"


# --- Models ---


class AlertEnrichmentRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str = ""
    source: EnrichmentSource = EnrichmentSource.ASSET_CONTEXT
    quality: EnrichmentQuality = EnrichmentQuality.PARTIAL
    fidelity: AlertFidelity = AlertFidelity.MEDIUM
    enrichment_score: float = 0.0
    staleness_hours: float = 0.0
    entity_id: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertEnrichmentAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str = ""
    completeness_pct: float = 0.0
    fidelity: AlertFidelity = AlertFidelity.MEDIUM
    stale_sources: int = 0
    enrichment_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertEnrichmentReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_enrichment_score: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_quality: dict[str, int] = Field(default_factory=dict)
    by_fidelity: dict[str, int] = Field(default_factory=dict)
    stale_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertRiskEnrichmentEngine:
    """Enrich alerts with risk context, compute
    enrichment completeness, detect staleness."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[AlertEnrichmentRecord] = []
        self._analyses: dict[str, AlertEnrichmentAnalysis] = {}
        logger.info(
            "alert_risk_enrichment_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        alert_id: str = "",
        source: EnrichmentSource = (EnrichmentSource.ASSET_CONTEXT),
        quality: EnrichmentQuality = (EnrichmentQuality.PARTIAL),
        fidelity: AlertFidelity = AlertFidelity.MEDIUM,
        enrichment_score: float = 0.0,
        staleness_hours: float = 0.0,
        entity_id: str = "",
        description: str = "",
    ) -> AlertEnrichmentRecord:
        record = AlertEnrichmentRecord(
            alert_id=alert_id,
            source=source,
            quality=quality,
            fidelity=fidelity,
            enrichment_score=enrichment_score,
            staleness_hours=staleness_hours,
            entity_id=entity_id,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_risk_enrichment.record_added",
            record_id=record.id,
            alert_id=alert_id,
        )
        return record

    def process(self, key: str) -> AlertEnrichmentAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        alert_recs = [r for r in self._records if r.alert_id == rec.alert_id]
        all_sources = set(EnrichmentSource)
        covered = {r.source for r in alert_recs}
        completeness = round(len(covered) / len(all_sources) * 100, 2)
        stale = sum(1 for r in alert_recs if r.quality == EnrichmentQuality.STALE)
        analysis = AlertEnrichmentAnalysis(
            alert_id=rec.alert_id,
            completeness_pct=completeness,
            fidelity=rec.fidelity,
            stale_sources=stale,
            enrichment_score=round(rec.enrichment_score, 2),
            description=(f"Alert {rec.alert_id} {completeness}% enriched"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> AlertEnrichmentReport:
        by_src: dict[str, int] = {}
        by_q: dict[str, int] = {}
        by_f: dict[str, int] = {}
        scores: list[float] = []
        stale = 0
        for r in self._records:
            k = r.source.value
            by_src[k] = by_src.get(k, 0) + 1
            k2 = r.quality.value
            by_q[k2] = by_q.get(k2, 0) + 1
            k3 = r.fidelity.value
            by_f[k3] = by_f.get(k3, 0) + 1
            scores.append(r.enrichment_score)
            if r.quality == EnrichmentQuality.STALE:
                stale += 1
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        recs: list[str] = []
        if stale > 0:
            recs.append(f"{stale} enrichments are stale")
        if not recs:
            recs.append("Enrichment data is current")
        return AlertEnrichmentReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_enrichment_score=avg,
            by_source=by_src,
            by_quality=by_q,
            by_fidelity=by_f,
            stale_count=stale,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        src_dist: dict[str, int] = {}
        for r in self._records:
            k = r.source.value
            src_dist[k] = src_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "source_distribution": src_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("alert_risk_enrichment_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def enrich_alert_with_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Compute enrichment per alert."""
        alert_data: dict[str, list[AlertEnrichmentRecord]] = {}
        for r in self._records:
            alert_data.setdefault(r.alert_id, []).append(r)
        results: list[dict[str, Any]] = []
        all_sources = set(EnrichmentSource)
        for aid, recs in alert_data.items():
            covered = {r.source for r in recs}
            comp = round(
                len(covered) / len(all_sources) * 100,
                2,
            )
            avg_score = round(
                sum(r.enrichment_score for r in recs) / len(recs),
                2,
            )
            results.append(
                {
                    "alert_id": aid,
                    "completeness_pct": comp,
                    "avg_enrichment_score": avg_score,
                    "source_count": len(covered),
                }
            )
        return results

    def compute_enrichment_completeness(
        self,
    ) -> dict[str, Any]:
        """Overall enrichment completeness."""
        if not self._records:
            return {
                "overall_completeness": 0.0,
                "by_source": {},
            }
        src_counts: dict[str, int] = {}
        for r in self._records:
            k = r.source.value
            src_counts[k] = src_counts.get(k, 0) + 1
        all_sources = {s.value for s in EnrichmentSource}
        covered = set(src_counts.keys())
        overall = round(len(covered) / len(all_sources) * 100, 2)
        return {
            "overall_completeness": overall,
            "by_source": src_counts,
        }

    def detect_stale_enrichment(
        self,
    ) -> list[dict[str, Any]]:
        """Find stale enrichment records."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.quality == EnrichmentQuality.STALE:
                results.append(
                    {
                        "alert_id": r.alert_id,
                        "source": r.source.value,
                        "staleness_hours": (r.staleness_hours),
                        "quality": r.quality.value,
                    }
                )
        results.sort(
            key=lambda x: x["staleness_hours"],
            reverse=True,
        )
        return results
