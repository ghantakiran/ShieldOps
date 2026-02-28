"""Prompt Cache Manager — intelligent prompt/response caching with semantic matching."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CacheStrategy(StrEnum):
    EXACT_MATCH = "exact_match"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    TEMPLATE_MATCH = "template_match"
    EMBEDDING_BASED = "embedding_based"
    HYBRID = "hybrid"


class CacheOutcome(StrEnum):
    HIT = "hit"
    MISS = "miss"
    PARTIAL_HIT = "partial_hit"
    STALE = "stale"
    EVICTED = "evicted"


class EvictionPolicy(StrEnum):
    LRU = "lru"
    LFU = "lfu"
    TTL_BASED = "ttl_based"
    SIZE_BASED = "size_based"
    PRIORITY = "priority"


# --- Models ---


class CacheEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    cache_key: str = ""
    cache_strategy: CacheStrategy = CacheStrategy.EXACT_MATCH
    cache_outcome: CacheOutcome = CacheOutcome.MISS
    eviction_policy: EvictionPolicy = EvictionPolicy.LRU
    entry_size_bytes: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CacheHitEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_label: str = ""
    cache_strategy: CacheStrategy = CacheStrategy.EXACT_MATCH
    cache_outcome: CacheOutcome = CacheOutcome.HIT
    latency_ms: float = 0.0
    created_at: float = Field(default_factory=time.time)


class PromptCacheReport(BaseModel):
    total_entries: int = 0
    total_events: int = 0
    hit_rate_pct: float = 0.0
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    eviction_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PromptCacheManager:
    """Manage prompt/response caching with semantic matching and eviction policies."""

    def __init__(
        self,
        max_records: int = 200000,
        ttl_seconds: int = 1800,
    ) -> None:
        self._max_records = max_records
        self._ttl_seconds = ttl_seconds
        self._records: list[CacheEntry] = []
        self._events: list[CacheHitEvent] = []
        logger.info(
            "prompt_cache.initialized",
            max_records=max_records,
            ttl_seconds=ttl_seconds,
        )

    # -- record / get / list ---------------------------------------------

    def record_entry(
        self,
        cache_key: str,
        cache_strategy: CacheStrategy = CacheStrategy.EXACT_MATCH,
        cache_outcome: CacheOutcome = CacheOutcome.MISS,
        eviction_policy: EvictionPolicy = EvictionPolicy.LRU,
        entry_size_bytes: int = 0,
        details: str = "",
    ) -> CacheEntry:
        record = CacheEntry(
            cache_key=cache_key,
            cache_strategy=cache_strategy,
            cache_outcome=cache_outcome,
            eviction_policy=eviction_policy,
            entry_size_bytes=entry_size_bytes,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "prompt_cache.entry_recorded",
            record_id=record.id,
            cache_key=cache_key,
            cache_strategy=cache_strategy.value,
        )
        return record

    def get_entry(self, record_id: str) -> CacheEntry | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_entries(
        self,
        cache_key: str | None = None,
        cache_strategy: CacheStrategy | None = None,
        limit: int = 50,
    ) -> list[CacheEntry]:
        results = list(self._records)
        if cache_key is not None:
            results = [r for r in results if r.cache_key == cache_key]
        if cache_strategy is not None:
            results = [r for r in results if r.cache_strategy == cache_strategy]
        return results[-limit:]

    def add_event(
        self,
        event_label: str,
        cache_strategy: CacheStrategy = CacheStrategy.EXACT_MATCH,
        cache_outcome: CacheOutcome = CacheOutcome.HIT,
        latency_ms: float = 0.0,
    ) -> CacheHitEvent:
        event = CacheHitEvent(
            event_label=event_label,
            cache_strategy=cache_strategy,
            cache_outcome=cache_outcome,
            latency_ms=latency_ms,
        )
        self._events.append(event)
        if len(self._events) > self._max_records:
            self._events = self._events[-self._max_records :]
        logger.info(
            "prompt_cache.event_added",
            event_label=event_label,
            cache_strategy=cache_strategy.value,
        )
        return event

    # -- domain operations -----------------------------------------------

    def analyze_cache_performance(self, cache_key: str) -> dict[str, Any]:
        records = [r for r in self._records if r.cache_key == cache_key]
        if not records:
            return {"cache_key": cache_key, "status": "no_data"}
        hit_count = sum(1 for r in records if r.cache_outcome == CacheOutcome.HIT)
        hit_rate = round(hit_count / len(records) * 100, 2)
        avg_size = round(sum(r.entry_size_bytes for r in records) / len(records), 2)
        return {
            "cache_key": cache_key,
            "total_entries": len(records),
            "hit_count": hit_count,
            "hit_rate_pct": hit_rate,
            "avg_entry_size_bytes": avg_size,
            "meets_threshold": hit_rate >= 50.0,
        }

    def identify_low_hit_keys(self) -> list[dict[str, Any]]:
        by_key: dict[str, int] = {}
        for r in self._records:
            if r.cache_outcome in (CacheOutcome.MISS, CacheOutcome.STALE):
                by_key[r.cache_key] = by_key.get(r.cache_key, 0) + 1
        results: list[dict[str, Any]] = []
        for key, count in by_key.items():
            if count > 1:
                results.append({"cache_key": key, "miss_stale_count": count})
        results.sort(key=lambda x: x["miss_stale_count"], reverse=True)
        return results

    def rank_by_hit_rate(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, int]] = {}
        for r in self._records:
            entry = by_key.setdefault(r.cache_key, {"hit": 0, "miss": 0})
            if r.cache_outcome == CacheOutcome.HIT:
                entry["hit"] += 1
            else:
                entry["miss"] += 1
        results: list[dict[str, Any]] = []
        for key, counts in by_key.items():
            total = counts["hit"] + counts["miss"]
            results.append(
                {
                    "cache_key": key,
                    "hit_count": counts["hit"],
                    "total": total,
                    "hit_rate_pct": round(counts["hit"] / total * 100, 2) if total else 0.0,
                }
            )
        results.sort(key=lambda x: x["hit_count"], reverse=True)
        return results

    def detect_cache_thrashing(self) -> list[dict[str, Any]]:
        by_key: dict[str, int] = {}
        for r in self._records:
            if r.cache_outcome == CacheOutcome.EVICTED:
                by_key[r.cache_key] = by_key.get(r.cache_key, 0) + 1
        results: list[dict[str, Any]] = []
        for key, count in by_key.items():
            if count > 3:
                results.append(
                    {
                        "cache_key": key,
                        "eviction_count": count,
                        "thrashing": True,
                    }
                )
        results.sort(key=lambda x: x["eviction_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> PromptCacheReport:
        by_strategy: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_strategy[r.cache_strategy.value] = by_strategy.get(r.cache_strategy.value, 0) + 1
            by_outcome[r.cache_outcome.value] = by_outcome.get(r.cache_outcome.value, 0) + 1
        hit_count = sum(1 for r in self._records if r.cache_outcome == CacheOutcome.HIT)
        hit_rate = round(hit_count / len(self._records) * 100, 2) if self._records else 0.0
        eviction_count = sum(1 for r in self._records if r.cache_outcome == CacheOutcome.EVICTED)
        recs: list[str] = []
        if eviction_count > 0:
            recs.append(f"{eviction_count} eviction(s) detected across cache entries")
        if hit_rate < 50.0 and self._records:
            recs.append(f"Hit rate {hit_rate}% is below 50% target")
        if not recs:
            recs.append("Prompt cache performance meets targets")
        return PromptCacheReport(
            total_entries=len(self._records),
            total_events=len(self._events),
            hit_rate_pct=hit_rate,
            by_strategy=by_strategy,
            by_outcome=by_outcome,
            eviction_count=eviction_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._events.clear()
        logger.info("prompt_cache.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        strategy_dist: dict[str, int] = {}
        for r in self._records:
            key = r.cache_strategy.value
            strategy_dist[key] = strategy_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_events": len(self._events),
            "ttl_seconds": self._ttl_seconds,
            "strategy_distribution": strategy_dist,
            "unique_keys": len({r.cache_key for r in self._records}),
        }
