"""Security Data Lake Engine
data ingestion, normalization, enrichment, retention, query optimization."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DataSourceType(StrEnum):
    SIEM = "siem"
    EDR = "edr"
    NETWORK = "network"
    CLOUD_TRAIL = "cloud_trail"
    IDENTITY = "identity"


class NormalizationStatus(StrEnum):
    RAW = "raw"
    NORMALIZED = "normalized"
    ENRICHED = "enriched"
    ARCHIVED = "archived"
    FAILED = "failed"


class RetentionTier(StrEnum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    FROZEN = "frozen"
    DELETED = "deleted"


# --- Models ---


class DataLakeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_name: str = ""
    source_type: DataSourceType = DataSourceType.SIEM
    normalization_status: NormalizationStatus = NormalizationStatus.RAW
    retention_tier: RetentionTier = RetentionTier.HOT
    volume_gb: float = 0.0
    events_per_sec: float = 0.0
    query_latency_ms: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DataLakeAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_name: str = ""
    source_type: DataSourceType = DataSourceType.SIEM
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DataLakeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    total_volume_gb: float = 0.0
    avg_query_latency_ms: float = 0.0
    avg_events_per_sec: float = 0.0
    by_source_type: dict[str, int] = Field(default_factory=dict)
    by_normalization: dict[str, int] = Field(default_factory=dict)
    by_retention: dict[str, int] = Field(default_factory=dict)
    top_volume_sources: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityDataLakeEngine:
    """Security data ingestion, normalization, enrichment, retention policy, query optimization."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 500.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[DataLakeRecord] = []
        self._analyses: list[DataLakeAnalysis] = []
        logger.info(
            "security_data_lake_engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def add_record(
        self,
        source_name: str,
        source_type: DataSourceType = DataSourceType.SIEM,
        normalization_status: NormalizationStatus = NormalizationStatus.RAW,
        retention_tier: RetentionTier = RetentionTier.HOT,
        volume_gb: float = 0.0,
        events_per_sec: float = 0.0,
        query_latency_ms: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DataLakeRecord:
        record = DataLakeRecord(
            source_name=source_name,
            source_type=source_type,
            normalization_status=normalization_status,
            retention_tier=retention_tier,
            volume_gb=volume_gb,
            events_per_sec=events_per_sec,
            query_latency_ms=query_latency_ms,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_data_lake_engine.record_added",
            record_id=record.id,
            source_name=source_name,
            source_type=source_type.value,
        )
        return record

    def get_record(self, record_id: str) -> DataLakeRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        source_type: DataSourceType | None = None,
        normalization_status: NormalizationStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DataLakeRecord]:
        results = list(self._records)
        if source_type is not None:
            results = [r for r in results if r.source_type == source_type]
        if normalization_status is not None:
            results = [r for r in results if r.normalization_status == normalization_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        source_name: str,
        source_type: DataSourceType = DataSourceType.SIEM,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DataLakeAnalysis:
        analysis = DataLakeAnalysis(
            source_name=source_name,
            source_type=source_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "security_data_lake_engine.analysis_added",
            source_name=source_name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_ingestion_volume(self) -> dict[str, Any]:
        source_volumes: dict[str, float] = {}
        for r in self._records:
            source_volumes[r.source_name] = source_volumes.get(r.source_name, 0.0) + r.volume_gb
        total_vol = sum(source_volumes.values())
        top_sources = sorted(
            [{"source": s, "volume_gb": round(v, 2)} for s, v in source_volumes.items()],
            key=lambda x: x.get("volume_gb", 0.0),  # type: ignore[arg-type,return-value]
            reverse=True,
        )
        return {
            "total_volume_gb": round(total_vol, 2),
            "source_count": len(source_volumes),
            "top_sources": top_sources[:10],
        }

    def evaluate_query_performance(self) -> list[dict[str, Any]]:
        source_latencies: dict[str, list[float]] = {}
        for r in self._records:
            source_latencies.setdefault(r.source_name, []).append(r.query_latency_ms)
        results: list[dict[str, Any]] = []
        for src, latencies in source_latencies.items():
            avg_lat = sum(latencies) / len(latencies)
            results.append(
                {
                    "source_name": src,
                    "avg_latency_ms": round(avg_lat, 2),
                    "max_latency_ms": round(max(latencies), 2),
                    "needs_optimization": avg_lat > self._threshold,
                }
            )
        return sorted(results, key=lambda x: x["avg_latency_ms"], reverse=True)

    def compute_retention_summary(self) -> dict[str, Any]:
        tier_volume: dict[str, float] = {}
        tier_count: dict[str, int] = {}
        for r in self._records:
            key = r.retention_tier.value
            tier_volume[key] = tier_volume.get(key, 0.0) + r.volume_gb
            tier_count[key] = tier_count.get(key, 0) + 1
        return {
            "tier_volumes_gb": {k: round(v, 2) for k, v in tier_volume.items()},
            "tier_counts": tier_count,
            "hot_pct": round(
                tier_volume.get("hot", 0.0) / sum(tier_volume.values()) * 100,
                2,
            )
            if tier_volume
            else 0.0,
        }

    def detect_trends(self) -> dict[str, Any]:
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
            trend = "growing"
        else:
            trend = "shrinking"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def process(self, source_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.source_name == source_name]
        if not matching:
            return {"source_name": source_name, "status": "no_data"}
        vols = [r.volume_gb for r in matching]
        lats = [r.query_latency_ms for r in matching]
        return {
            "source_name": source_name,
            "record_count": len(matching),
            "total_volume_gb": round(sum(vols), 2),
            "avg_query_latency_ms": round(sum(lats) / len(lats), 2),
        }

    def generate_report(self) -> DataLakeReport:
        by_src: dict[str, int] = {}
        by_norm: dict[str, int] = {}
        by_ret: dict[str, int] = {}
        for r in self._records:
            by_src[r.source_type.value] = by_src.get(r.source_type.value, 0) + 1
            by_norm[r.normalization_status.value] = by_norm.get(r.normalization_status.value, 0) + 1
            by_ret[r.retention_tier.value] = by_ret.get(r.retention_tier.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.query_latency_ms > self._threshold)
        vols = [r.volume_gb for r in self._records]
        total_vol = round(sum(vols), 2) if vols else 0.0
        lats = [r.query_latency_ms for r in self._records]
        avg_lat = round(sum(lats) / len(lats), 2) if lats else 0.0
        eps = [r.events_per_sec for r in self._records]
        avg_eps = round(sum(eps) / len(eps), 2) if eps else 0.0
        vol_info = self.analyze_ingestion_volume()
        top_vol = [s["source"] for s in vol_info.get("top_sources", [])[:5]]
        recs: list[str] = []
        if gap_count > 0:
            recs.append(
                f"{gap_count} source(s) exceeding query latency threshold ({self._threshold}ms)"
            )
        raw_count = by_norm.get("raw", 0)
        if raw_count > 0:
            recs.append(f"{raw_count} source(s) still in raw state — normalize for search")
        if avg_lat > self._threshold:
            recs.append(f"Avg query latency {avg_lat}ms exceeds threshold")
        if not recs:
            recs.append("Security data lake is healthy")
        return DataLakeReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            total_volume_gb=total_vol,
            avg_query_latency_ms=avg_lat,
            avg_events_per_sec=avg_eps,
            by_source_type=by_src,
            by_normalization=by_norm,
            by_retention=by_ret,
            top_volume_sources=top_vol,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        src_dist: dict[str, int] = {}
        for r in self._records:
            key = r.source_type.value
            src_dist[key] = src_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "source_type_distribution": src_dist,
            "unique_sources": len({r.source_name for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_data_lake_engine.cleared")
        return {"status": "cleared"}
