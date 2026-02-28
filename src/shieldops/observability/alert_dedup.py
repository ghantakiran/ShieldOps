"""Alert Deduplication Engine — detect and suppress duplicate alerts across sources."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DedupStrategy(StrEnum):
    EXACT_MATCH = "exact_match"
    FUZZY_MATCH = "fuzzy_match"
    TIME_WINDOW = "time_window"
    FINGERPRINT = "fingerprint"
    CONTENT_HASH = "content_hash"


class DedupResult(StrEnum):
    DUPLICATE = "duplicate"
    UNIQUE = "unique"
    NEAR_DUPLICATE = "near_duplicate"
    SUPERSEDED = "superseded"
    MERGED = "merged"


class AlertPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# --- Models ---


class DedupRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    alert_name: str = ""
    source: str = ""
    fingerprint: str = ""
    strategy: DedupStrategy = DedupStrategy.EXACT_MATCH
    result: DedupResult = DedupResult.UNIQUE
    priority: AlertPriority = AlertPriority.MEDIUM
    duplicate_count: int = 0
    suppressed: bool = False
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class DedupRule(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    rule_name: str = ""
    strategy: DedupStrategy = DedupStrategy.EXACT_MATCH
    time_window_seconds: float = 300.0
    match_fields: list[str] = Field(default_factory=list)
    enabled: bool = True
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertDedupReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_records: int = 0
    total_rules: int = 0
    duplicate_count: int = 0
    unique_count: int = 0
    suppression_rate_pct: float = 0.0
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    top_duplicate_sources: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertDeduplicationEngine:
    """Detect and suppress duplicate alerts to reduce noise and operator fatigue."""

    def __init__(
        self,
        max_records: int = 200000,
        min_dedup_ratio_pct: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._min_dedup_ratio_pct = min_dedup_ratio_pct
        self._records: list[DedupRecord] = []
        self._rules: list[DedupRule] = []
        logger.info(
            "alert_dedup.initialized",
            max_records=max_records,
            min_dedup_ratio_pct=min_dedup_ratio_pct,
        )

    # -- CRUD --

    def record_dedup(
        self,
        alert_name: str,
        source: str = "",
        fingerprint: str = "",
        strategy: DedupStrategy = DedupStrategy.EXACT_MATCH,
        result: DedupResult = DedupResult.UNIQUE,
        priority: AlertPriority = AlertPriority.MEDIUM,
        duplicate_count: int = 0,
        suppressed: bool = False,
        details: str = "",
    ) -> DedupRecord:
        record = DedupRecord(
            alert_name=alert_name,
            source=source,
            fingerprint=fingerprint,
            strategy=strategy,
            result=result,
            priority=priority,
            duplicate_count=duplicate_count,
            suppressed=suppressed,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_dedup.recorded",
            record_id=record.id,
            alert_name=alert_name,
            result=result.value,
        )
        return record

    def get_dedup(self, record_id: str) -> DedupRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_dedups(
        self,
        strategy: DedupStrategy | None = None,
        result: DedupResult | None = None,
        priority: AlertPriority | None = None,
        limit: int = 50,
    ) -> list[DedupRecord]:
        results = list(self._records)
        if strategy is not None:
            results = [r for r in results if r.strategy == strategy]
        if result is not None:
            results = [r for r in results if r.result == result]
        if priority is not None:
            results = [r for r in results if r.priority == priority]
        return results[-limit:]

    def add_rule(
        self,
        rule_name: str,
        strategy: DedupStrategy = DedupStrategy.EXACT_MATCH,
        time_window_seconds: float = 300.0,
        match_fields: list[str] | None = None,
        enabled: bool = True,
        description: str = "",
    ) -> DedupRule:
        rule = DedupRule(
            rule_name=rule_name,
            strategy=strategy,
            time_window_seconds=time_window_seconds,
            match_fields=match_fields or [],
            enabled=enabled,
            description=description,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "alert_dedup.rule_added",
            rule_id=rule.id,
            rule_name=rule_name,
            strategy=strategy.value,
        )
        return rule

    # -- Domain operations --

    def analyze_dedup_effectiveness(self) -> dict[str, Any]:
        """Compute overall deduplication effectiveness metrics."""
        if not self._records:
            return {"total": 0, "dedup_ratio_pct": 0.0, "suppressed_count": 0}
        total = len(self._records)
        duplicates = sum(
            1 for r in self._records if r.result in (DedupResult.DUPLICATE, DedupResult.MERGED)
        )
        suppressed = sum(1 for r in self._records if r.suppressed)
        dedup_ratio = round(duplicates / total * 100, 2) if total else 0.0
        meets_threshold = dedup_ratio >= self._min_dedup_ratio_pct
        by_strategy: dict[str, int] = {}
        for r in self._records:
            by_strategy[r.strategy.value] = by_strategy.get(r.strategy.value, 0) + 1
        return {
            "total": total,
            "duplicates": duplicates,
            "suppressed_count": suppressed,
            "dedup_ratio_pct": dedup_ratio,
            "meets_threshold": meets_threshold,
            "min_dedup_ratio_pct": self._min_dedup_ratio_pct,
            "by_strategy": by_strategy,
        }

    def identify_high_duplicate_sources(self) -> list[dict[str, Any]]:
        """Find sources generating the most duplicate alerts."""
        source_dupes: dict[str, int] = {}
        source_total: dict[str, int] = {}
        for r in self._records:
            if not r.source:
                continue
            source_total[r.source] = source_total.get(r.source, 0) + 1
            if r.result in (DedupResult.DUPLICATE, DedupResult.MERGED):
                source_dupes[r.source] = source_dupes.get(r.source, 0) + 1
        results: list[dict[str, Any]] = []
        for source, dupe_count in source_dupes.items():
            total = source_total.get(source, 1)
            ratio = round(dupe_count / total * 100, 2)
            results.append(
                {
                    "source": source,
                    "duplicate_count": dupe_count,
                    "total_alerts": total,
                    "duplicate_ratio_pct": ratio,
                }
            )
        results.sort(key=lambda x: x["duplicate_count"], reverse=True)
        return results

    def rank_by_dedup_ratio(self) -> list[dict[str, Any]]:
        """Rank alert names by their deduplication ratio."""
        name_dupes: dict[str, int] = {}
        name_total: dict[str, int] = {}
        for r in self._records:
            if not r.alert_name:
                continue
            name_total[r.alert_name] = name_total.get(r.alert_name, 0) + 1
            if r.result in (DedupResult.DUPLICATE, DedupResult.NEAR_DUPLICATE, DedupResult.MERGED):
                name_dupes[r.alert_name] = name_dupes.get(r.alert_name, 0) + 1
        results: list[dict[str, Any]] = []
        for name, total in name_total.items():
            dupes = name_dupes.get(name, 0)
            ratio = round(dupes / total * 100, 2) if total else 0.0
            results.append(
                {
                    "alert_name": name,
                    "total": total,
                    "duplicates": dupes,
                    "dedup_ratio_pct": ratio,
                }
            )
        results.sort(key=lambda x: x["dedup_ratio_pct"], reverse=True)
        return results

    def detect_dedup_trends(self) -> dict[str, Any]:
        """Detect whether deduplication rates are improving or worsening over time."""
        if len(self._records) < 4:
            return {"trend": "insufficient_data", "sample_count": len(self._records)}
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]

        def _ratio(records: list[DedupRecord]) -> float:
            if not records:
                return 0.0
            dupes = sum(
                1 for r in records if r.result in (DedupResult.DUPLICATE, DedupResult.MERGED)
            )
            return round(dupes / len(records) * 100, 2)

        first_ratio = _ratio(first_half)
        second_ratio = _ratio(second_half)
        delta = round(second_ratio - first_ratio, 2)
        if delta > 5.0:
            trend = "worsening"
        elif delta < -5.0:
            trend = "improving"
        else:
            trend = "stable"
        return {
            "trend": trend,
            "first_half_ratio_pct": first_ratio,
            "second_half_ratio_pct": second_ratio,
            "delta_pct": delta,
            "total_records": len(self._records),
        }

    # -- Report --

    def generate_report(self) -> AlertDedupReport:
        by_strategy: dict[str, int] = {}
        by_result: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for r in self._records:
            by_strategy[r.strategy.value] = by_strategy.get(r.strategy.value, 0) + 1
            by_result[r.result.value] = by_result.get(r.result.value, 0) + 1
            by_priority[r.priority.value] = by_priority.get(r.priority.value, 0) + 1
        total = len(self._records)
        duplicate_count = by_result.get(DedupResult.DUPLICATE.value, 0) + by_result.get(
            DedupResult.MERGED.value, 0
        )
        unique_count = by_result.get(DedupResult.UNIQUE.value, 0)
        suppression_rate = round(duplicate_count / total * 100, 2) if total else 0.0
        high_dupe_sources = self.identify_high_duplicate_sources()
        top_sources = [s["source"] for s in high_dupe_sources[:5]]
        recs: list[str] = []
        if suppression_rate < self._min_dedup_ratio_pct:
            recs.append(
                f"Dedup ratio {suppression_rate}% below target {self._min_dedup_ratio_pct}%"
                " — review fingerprinting rules"
            )
        if top_sources:
            recs.append(f"High duplicate source: {top_sources[0]} — consider alert tuning")
        if not self._rules:
            recs.append("No dedup rules configured — add rules to improve suppression")
        if not recs:
            recs.append("Deduplication performance is on target")
        return AlertDedupReport(
            total_records=total,
            total_rules=len(self._rules),
            duplicate_count=duplicate_count,
            unique_count=unique_count,
            suppression_rate_pct=suppression_rate,
            by_strategy=by_strategy,
            by_result=by_result,
            by_priority=by_priority,
            top_duplicate_sources=top_sources,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("alert_dedup.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        result_dist: dict[str, int] = {}
        for r in self._records:
            result_dist[r.result.value] = result_dist.get(r.result.value, 0) + 1
        suppressed = sum(1 for r in self._records if r.suppressed)
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "suppressed_count": suppressed,
            "min_dedup_ratio_pct": self._min_dedup_ratio_pct,
            "result_distribution": result_dist,
            "unique_sources": len({r.source for r in self._records if r.source}),
        }
