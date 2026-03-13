"""Alert Dedup Intelligence
compute dedup fingerprints, identify duplicate clusters,
measure dedup effectiveness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DedupStrategy(StrEnum):
    FINGERPRINT = "fingerprint"
    SEMANTIC = "semantic"
    TEMPORAL = "temporal"
    HYBRID = "hybrid"


class ClusterStatus(StrEnum):
    ACTIVE = "active"
    MERGED = "merged"
    RESOLVED = "resolved"
    STALE = "stale"


class SimilarityLevel(StrEnum):
    EXACT = "exact"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


# --- Models ---


class AlertDedupRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str = ""
    fingerprint: str = ""
    dedup_strategy: DedupStrategy = DedupStrategy.FINGERPRINT
    cluster_status: ClusterStatus = ClusterStatus.ACTIVE
    similarity_level: SimilarityLevel = SimilarityLevel.LOW
    cluster_id: str = ""
    source: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertDedupAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str = ""
    cluster_id: str = ""
    duplicate_count: int = 0
    similarity_score: float = 0.0
    dedup_strategy: DedupStrategy = DedupStrategy.FINGERPRINT
    is_duplicate: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertDedupReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    dedup_rate: float = 0.0
    by_dedup_strategy: dict[str, int] = Field(default_factory=dict)
    by_cluster_status: dict[str, int] = Field(default_factory=dict)
    by_similarity_level: dict[str, int] = Field(default_factory=dict)
    top_clusters: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertDedupIntelligence:
    """Compute dedup fingerprints, identify duplicate
    clusters, measure dedup effectiveness."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[AlertDedupRecord] = []
        self._analyses: dict[str, AlertDedupAnalysis] = {}
        logger.info(
            "alert_dedup_intelligence.init",
            max_records=max_records,
        )

    def add_record(
        self,
        alert_id: str = "",
        fingerprint: str = "",
        dedup_strategy: DedupStrategy = (DedupStrategy.FINGERPRINT),
        cluster_status: ClusterStatus = (ClusterStatus.ACTIVE),
        similarity_level: SimilarityLevel = (SimilarityLevel.LOW),
        cluster_id: str = "",
        source: str = "",
        description: str = "",
    ) -> AlertDedupRecord:
        record = AlertDedupRecord(
            alert_id=alert_id,
            fingerprint=fingerprint,
            dedup_strategy=dedup_strategy,
            cluster_status=cluster_status,
            similarity_level=similarity_level,
            cluster_id=cluster_id,
            source=source,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_dedup.record_added",
            record_id=record.id,
            alert_id=alert_id,
        )
        return record

    def process(self, key: str) -> AlertDedupAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        dupes = sum(1 for r in self._records if r.fingerprint == rec.fingerprint)
        is_dup = dupes > 1
        sim = min(dupes / 5.0, 1.0) if dupes > 1 else 0.0
        analysis = AlertDedupAnalysis(
            alert_id=rec.alert_id,
            cluster_id=rec.cluster_id,
            duplicate_count=dupes,
            similarity_score=round(sim, 2),
            dedup_strategy=rec.dedup_strategy,
            is_duplicate=is_dup,
            description=(f"Alert {rec.alert_id} has {dupes} duplicates"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> AlertDedupReport:
        by_ds: dict[str, int] = {}
        by_cs: dict[str, int] = {}
        by_sl: dict[str, int] = {}
        for r in self._records:
            k = r.dedup_strategy.value
            by_ds[k] = by_ds.get(k, 0) + 1
            k2 = r.cluster_status.value
            by_cs[k2] = by_cs.get(k2, 0) + 1
            k3 = r.similarity_level.value
            by_sl[k3] = by_sl.get(k3, 0) + 1
        fp_counts: dict[str, int] = {}
        for r in self._records:
            fp_counts[r.fingerprint] = fp_counts.get(r.fingerprint, 0) + 1
        dup_count = sum(v for v in fp_counts.values() if v > 1)
        total = len(self._records)
        dedup_rate = round(dup_count / total, 2) if total else 0.0
        top = sorted(
            fp_counts,
            key=lambda x: fp_counts[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        if dedup_rate > 0.3:
            recs.append(f"High dedup rate {dedup_rate:.0%}")
        if not recs:
            recs.append("Dedup rates within norms")
        return AlertDedupReport(
            total_records=total,
            total_analyses=len(self._analyses),
            dedup_rate=dedup_rate,
            by_dedup_strategy=by_ds,
            by_cluster_status=by_cs,
            by_similarity_level=by_sl,
            top_clusters=top,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ds_dist: dict[str, int] = {}
        for r in self._records:
            k = r.dedup_strategy.value
            ds_dist[k] = ds_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "dedup_strategy_distribution": ds_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("alert_dedup_intelligence.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_dedup_fingerprints(
        self,
    ) -> list[dict[str, Any]]:
        """Compute dedup fingerprints for alerts."""
        fp_groups: dict[str, list[str]] = {}
        for r in self._records:
            fp_groups.setdefault(r.fingerprint, []).append(r.alert_id)
        results: list[dict[str, Any]] = []
        for fp, aids in fp_groups.items():
            results.append(
                {
                    "fingerprint": fp,
                    "alert_count": len(aids),
                    "alert_ids": aids[:10],
                    "is_cluster": len(aids) > 1,
                }
            )
        results.sort(
            key=lambda x: x["alert_count"],
            reverse=True,
        )
        return results

    def identify_duplicate_clusters(
        self,
    ) -> list[dict[str, Any]]:
        """Identify clusters of duplicate alerts."""
        cluster_data: dict[str, list[str]] = {}
        for r in self._records:
            if r.cluster_id:
                cluster_data.setdefault(r.cluster_id, []).append(r.alert_id)
        results: list[dict[str, Any]] = []
        for cid, aids in cluster_data.items():
            results.append(
                {
                    "cluster_id": cid,
                    "member_count": len(aids),
                    "alert_ids": aids[:10],
                    "status": "active" if len(aids) > 1 else "single",
                }
            )
        results.sort(
            key=lambda x: x["member_count"],
            reverse=True,
        )
        return results

    def measure_dedup_effectiveness(
        self,
    ) -> list[dict[str, Any]]:
        """Measure dedup effectiveness by strategy."""
        strat_data: dict[str, dict[str, int]] = {}
        for r in self._records:
            s = r.dedup_strategy.value
            if s not in strat_data:
                strat_data[s] = {
                    "total": 0,
                    "duplicates": 0,
                }
            strat_data[s]["total"] += 1
            if r.similarity_level in (
                SimilarityLevel.EXACT,
                SimilarityLevel.HIGH,
            ):
                strat_data[s]["duplicates"] += 1
        results: list[dict[str, Any]] = []
        for strat, data in strat_data.items():
            rate = data["duplicates"] / data["total"] if data["total"] else 0.0
            results.append(
                {
                    "strategy": strat,
                    "total_alerts": data["total"],
                    "duplicates_found": (data["duplicates"]),
                    "effectiveness_rate": round(rate, 2),
                }
            )
        results.sort(
            key=lambda x: x["effectiveness_rate"],
            reverse=True,
        )
        return results
