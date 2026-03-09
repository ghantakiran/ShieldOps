"""Intelligent Log Routing — ML-driven log routing and tier assignment."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LogTier(StrEnum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    ARCHIVE = "archive"
    DROP = "drop"


class LogCategory(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"
    AUDIT = "audit"


class RoutingStrategy(StrEnum):
    CONTENT_BASED = "content_based"
    VOLUME_BASED = "volume_based"
    COST_BASED = "cost_based"
    COMPLIANCE_BASED = "compliance_based"


# --- Models ---


class LogRoutingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""
    category: LogCategory = LogCategory.INFO
    tier: LogTier = LogTier.WARM
    strategy: RoutingStrategy = RoutingStrategy.CONTENT_BASED
    volume_bytes: int = 0
    cost_per_gb: float = 0.0
    created_at: float = Field(default_factory=time.time)


class RoutingRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    pattern: str = ""
    target_tier: LogTier = LogTier.WARM
    priority: int = 0
    enabled: bool = True
    created_at: float = Field(default_factory=time.time)


class LogRoutingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_rules: int = 0
    total_volume_bytes: int = 0
    estimated_cost: float = 0.0
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IntelligentLogRouting:
    """ML-driven log routing and tier assignment."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[LogRoutingRecord] = []
        self._rules: list[RoutingRule] = []
        logger.info("intelligent_log_routing.initialized", max_records=max_records)

    def add_rule(
        self,
        name: str,
        pattern: str = "",
        target_tier: LogTier = LogTier.WARM,
        priority: int = 0,
    ) -> RoutingRule:
        """Add a routing rule."""
        rule = RoutingRule(name=name, pattern=pattern, target_tier=target_tier, priority=priority)
        self._rules.append(rule)
        logger.info("intelligent_log_routing.rule_added", name=name)
        return rule

    def classify_log(
        self,
        source: str,
        message: str = "",
        volume_bytes: int = 0,
    ) -> LogRoutingRecord:
        """Classify a log entry and assign category."""
        msg_lower = message.lower()
        if "error" in msg_lower or "exception" in msg_lower:
            category = LogCategory.ERROR
        elif "warn" in msg_lower:
            category = LogCategory.WARNING
        elif "audit" in msg_lower:
            category = LogCategory.AUDIT
        elif "debug" in msg_lower:
            category = LogCategory.DEBUG
        else:
            category = LogCategory.INFO
        tier = self._determine_tier(category, volume_bytes)
        cost = self._tier_cost(tier)
        record = LogRoutingRecord(
            source=source,
            category=category,
            tier=tier,
            volume_bytes=volume_bytes,
            cost_per_gb=cost,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        return record

    def _determine_tier(self, category: LogCategory, volume: int) -> LogTier:
        if category in (LogCategory.ERROR, LogCategory.AUDIT):
            return LogTier.HOT
        if category == LogCategory.WARNING:
            return LogTier.WARM
        if category == LogCategory.DEBUG:
            return LogTier.COLD if volume > 10000 else LogTier.ARCHIVE
        return LogTier.WARM

    def _tier_cost(self, tier: LogTier) -> float:
        costs = {
            LogTier.HOT: 3.50,
            LogTier.WARM: 1.50,
            LogTier.COLD: 0.50,
            LogTier.ARCHIVE: 0.10,
            LogTier.DROP: 0.0,
        }
        return costs.get(tier, 1.0)

    def route_to_tier(self, source: str, message: str = "") -> dict[str, Any]:
        """Route a log to the appropriate tier."""
        record = self.classify_log(source, message)
        # Apply rule overrides
        for rule in sorted(self._rules, key=lambda r: r.priority, reverse=True):
            if rule.enabled and rule.pattern and rule.pattern in message:
                record.tier = rule.target_tier
                break
        return {
            "source": source,
            "tier": record.tier.value,
            "category": record.category.value,
            "cost_per_gb": record.cost_per_gb,
        }

    def optimize_routing_rules(self) -> list[dict[str, Any]]:
        """Suggest optimizations for routing rules."""
        suggestions: list[dict[str, Any]] = []
        tier_volumes: dict[str, int] = {}
        for r in self._records:
            tier_volumes[r.tier.value] = tier_volumes.get(r.tier.value, 0) + r.volume_bytes
        hot_vol = tier_volumes.get("hot", 0)
        if hot_vol > 1_000_000:
            suggestions.append(
                {
                    "type": "downgrade",
                    "message": "High volume in hot tier — consider moving older data to warm",
                    "potential_savings_pct": 40,
                }
            )
        debug_count = sum(1 for r in self._records if r.category == LogCategory.DEBUG)
        if debug_count > len(self._records) * 0.5:
            suggestions.append(
                {
                    "type": "filter",
                    "message": "Over 50% debug logs — consider dropping or archiving",
                    "potential_savings_pct": 30,
                }
            )
        if not suggestions:
            suggestions.append(
                {
                    "type": "none",
                    "message": "Routing rules are optimized",
                    "potential_savings_pct": 0,
                }
            )
        return suggestions

    def estimate_storage_impact(self) -> dict[str, Any]:
        """Estimate storage cost impact of current routing."""
        tier_data: dict[str, dict[str, float]] = {}
        for r in self._records:
            key = r.tier.value
            if key not in tier_data:
                tier_data[key] = {"volume_gb": 0.0, "cost": 0.0}
            vol_gb = r.volume_bytes / (1024**3)
            tier_data[key]["volume_gb"] += vol_gb
            tier_data[key]["cost"] += vol_gb * r.cost_per_gb
        total_cost = sum(v["cost"] for v in tier_data.values())
        return {
            "by_tier": {
                k: {kk: round(vv, 4) for kk, vv in v.items()} for k, v in tier_data.items()
            },
            "total_cost": round(total_cost, 4),
        }

    def get_routing_stats(self) -> dict[str, Any]:
        """Return routing statistics."""
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "unique_sources": len({r.source for r in self._records}),
            "enabled_rules": sum(1 for r in self._rules if r.enabled),
        }

    def generate_report(self) -> LogRoutingReport:
        """Generate log routing report."""
        by_tier: dict[str, int] = {}
        by_cat: dict[str, int] = {}
        total_vol = 0
        for r in self._records:
            by_tier[r.tier.value] = by_tier.get(r.tier.value, 0) + 1
            by_cat[r.category.value] = by_cat.get(r.category.value, 0) + 1
            total_vol += r.volume_bytes
        impact = self.estimate_storage_impact()
        recs: list[str] = []
        if by_tier.get("hot", 0) > len(self._records) * 0.5:
            recs.append("Over 50% logs in hot tier — review tier assignment")
        if not recs:
            recs.append("Log routing is healthy")
        return LogRoutingReport(
            total_records=len(self._records),
            total_rules=len(self._rules),
            total_volume_bytes=total_vol,
            estimated_cost=impact["total_cost"],
            by_tier=by_tier,
            by_category=by_cat,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        """Clear all records and rules."""
        self._records.clear()
        self._rules.clear()
        logger.info("intelligent_log_routing.cleared")
        return {"status": "cleared"}
