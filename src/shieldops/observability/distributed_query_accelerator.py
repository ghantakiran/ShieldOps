"""DistributedQueryAccelerator — query acceleration."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class QueryComplexity(StrEnum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    EXTREME = "extreme"


class CacheStrategy(StrEnum):
    LRU = "lru"
    LFU = "lfu"
    ADAPTIVE = "adaptive"
    NONE = "none"


class DataLocality(StrEnum):
    LOCAL = "local"
    REGIONAL = "regional"
    GLOBAL = "global"


# --- Models ---


class QueryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    complexity: QueryComplexity = QueryComplexity.SIMPLE
    cache_strategy: CacheStrategy = CacheStrategy.LRU
    data_locality: DataLocality = DataLocality.LOCAL
    score: float = 0.0
    query_time_ms: float = 0.0
    cache_hit_rate: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class QueryAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    complexity: QueryComplexity = QueryComplexity.SIMPLE
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class QueryReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    avg_query_time_ms: float = 0.0
    by_complexity: dict[str, int] = Field(default_factory=dict)
    by_cache_strategy: dict[str, int] = Field(default_factory=dict)
    by_data_locality: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DistributedQueryAccelerator:
    """Distributed Query Accelerator.

    Analyzes and optimizes distributed query
    patterns for observability data.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[QueryRecord] = []
        self._analyses: list[QueryAnalysis] = []
        logger.info(
            "distributed_query_accelerator.init",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        complexity: QueryComplexity = (QueryComplexity.SIMPLE),
        cache_strategy: CacheStrategy = (CacheStrategy.LRU),
        data_locality: DataLocality = (DataLocality.LOCAL),
        score: float = 0.0,
        query_time_ms: float = 0.0,
        cache_hit_rate: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> QueryRecord:
        record = QueryRecord(
            name=name,
            complexity=complexity,
            cache_strategy=cache_strategy,
            data_locality=data_locality,
            score=score,
            query_time_ms=query_time_ms,
            cache_hit_rate=cache_hit_rate,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "distributed_query_accelerator.added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.name == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        scores = [r.score for r in matching]
        avg = round(sum(scores) / len(scores), 2)
        qtimes = [r.query_time_ms for r in matching]
        avg_qt = round(sum(qtimes) / len(qtimes), 2)
        return {
            "key": key,
            "record_count": len(matching),
            "avg_score": avg,
            "avg_query_time_ms": avg_qt,
        }

    def generate_report(self) -> QueryReport:
        by_c: dict[str, int] = {}
        by_cs: dict[str, int] = {}
        by_dl: dict[str, int] = {}
        for r in self._records:
            v1 = r.complexity.value
            by_c[v1] = by_c.get(v1, 0) + 1
            v2 = r.cache_strategy.value
            by_cs[v2] = by_cs.get(v2, 0) + 1
            v3 = r.data_locality.value
            by_dl[v3] = by_dl.get(v3, 0) + 1
        scores = [r.score for r in self._records]
        avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
        qtimes = [r.query_time_ms for r in self._records]
        avg_qt = round(sum(qtimes) / len(qtimes), 2) if qtimes else 0.0
        recs: list[str] = []
        slow = sum(1 for r in self._records if r.query_time_ms > 1000.0)
        if slow > 0:
            recs.append(f"{slow} query(ies) exceeding 1s")
        if avg_s < self._threshold and self._records:
            recs.append(f"Avg score {avg_s} below threshold {self._threshold}")
        if not recs:
            recs.append("Query performance healthy")
        return QueryReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg_s,
            avg_query_time_ms=avg_qt,
            by_complexity=by_c,
            by_cache_strategy=by_cs,
            by_data_locality=by_dl,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        c_dist: dict[str, int] = {}
        for r in self._records:
            k = r.complexity.value
            c_dist[k] = c_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "complexity_distribution": c_dist,
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("distributed_query_accelerator.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def analyze_query_patterns(
        self,
    ) -> dict[str, Any]:
        """Analyze query patterns by complexity."""
        groups: dict[str, list[float]] = {}
        for r in self._records:
            key = r.complexity.value
            groups.setdefault(key, []).append(r.query_time_ms)
        result: dict[str, Any] = {}
        for k, times in groups.items():
            avg = round(sum(times) / len(times), 2)
            result[k] = {
                "count": len(times),
                "avg_query_time_ms": avg,
                "max_query_time_ms": round(max(times), 2),
            }
        return result

    def compute_cache_efficiency(
        self,
    ) -> dict[str, Any]:
        """Compute cache efficiency by strategy."""
        if not self._records:
            return {"status": "no_data"}
        strat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.cache_strategy.value
            strat_data.setdefault(key, []).append(r.cache_hit_rate)
        result: dict[str, Any] = {}
        for strat, rates in strat_data.items():
            avg = round(sum(rates) / len(rates), 4)
            result[strat] = {
                "avg_hit_rate": avg,
                "sample_count": len(rates),
                "effective": avg >= 0.7,
            }
        overall = round(
            sum(r.cache_hit_rate for r in self._records) / len(self._records),
            4,
        )
        return {
            "overall_hit_rate": overall,
            "by_strategy": result,
        }

    def optimize_query_routing(
        self,
    ) -> list[dict[str, Any]]:
        """Optimize query routing by locality."""
        svc_data: dict[str, list[QueryRecord]] = {}
        for r in self._records:
            svc_data.setdefault(r.service, []).append(r)
        recommendations: list[dict[str, Any]] = []
        for svc, recs in svc_data.items():
            qtimes = [r.query_time_ms for r in recs]
            avg_qt = round(sum(qtimes) / len(qtimes), 2)
            localities = {r.data_locality.value for r in recs}
            rec: dict[str, Any] = {
                "service": svc,
                "avg_query_time_ms": avg_qt,
                "localities": sorted(localities),
            }
            if "global" in localities and avg_qt > 500:
                rec["suggestion"] = "Add regional cache layer"
            elif avg_qt > 200:
                rec["suggestion"] = "Enable adaptive caching"
            else:
                rec["suggestion"] = "Routing optimal"
            recommendations.append(rec)
        recommendations.sort(
            key=lambda x: x["avg_query_time_ms"],
            reverse=True,
        )
        return recommendations
