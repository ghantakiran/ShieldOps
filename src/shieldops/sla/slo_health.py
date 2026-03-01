"""SLO Health Dashboard — monitor SLO health, trends, and risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    AT_RISK = "at_risk"
    BREACHING = "breaching"
    UNKNOWN = "unknown"


class SLOCategory(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    SATURATION = "saturation"


class TrendDirection(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class SLOHealthRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    health_status: HealthStatus = HealthStatus.UNKNOWN
    slo_category: SLOCategory = SLOCategory.AVAILABILITY
    trend_direction: TrendDirection = TrendDirection.STABLE
    health_score: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SLOHealthRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_pattern: str = ""
    slo_category: SLOCategory = SLOCategory.AVAILABILITY
    min_score: float = 0.0
    alert_on_breach: bool = True
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SLOHealthReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_rules: int = 0
    healthy_count: int = 0
    avg_health_score: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    at_risk_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLOHealthDashboard:
    """Monitor SLO health, identify at-risk services, and detect trends."""

    def __init__(
        self,
        max_records: int = 200000,
        min_health_score: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_health_score = min_health_score
        self._records: list[SLOHealthRecord] = []
        self._rules: list[SLOHealthRule] = []
        logger.info(
            "slo_health.initialized",
            max_records=max_records,
            min_health_score=min_health_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_health(
        self,
        service_name: str,
        health_status: HealthStatus = HealthStatus.UNKNOWN,
        slo_category: SLOCategory = SLOCategory.AVAILABILITY,
        trend_direction: TrendDirection = TrendDirection.STABLE,
        health_score: float = 0.0,
        team: str = "",
    ) -> SLOHealthRecord:
        record = SLOHealthRecord(
            service_name=service_name,
            health_status=health_status,
            slo_category=slo_category,
            trend_direction=trend_direction,
            health_score=health_score,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "slo_health.health_recorded",
            record_id=record.id,
            service_name=service_name,
            health_status=health_status.value,
            health_score=health_score,
        )
        return record

    def get_health(self, record_id: str) -> SLOHealthRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_health_records(
        self,
        status: HealthStatus | None = None,
        category: SLOCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SLOHealthRecord]:
        results = list(self._records)
        if status is not None:
            results = [r for r in results if r.health_status == status]
        if category is not None:
            results = [r for r in results if r.slo_category == category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_rule(
        self,
        service_pattern: str,
        slo_category: SLOCategory = SLOCategory.AVAILABILITY,
        min_score: float = 0.0,
        alert_on_breach: bool = True,
        description: str = "",
    ) -> SLOHealthRule:
        rule = SLOHealthRule(
            service_pattern=service_pattern,
            slo_category=slo_category,
            min_score=min_score,
            alert_on_breach=alert_on_breach,
            description=description,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "slo_health.rule_added",
            service_pattern=service_pattern,
            slo_category=slo_category.value,
            min_score=min_score,
        )
        return rule

    # -- domain operations --------------------------------------------------

    def analyze_health_distribution(self) -> dict[str, Any]:
        """Group by status; return count and avg health_score per status."""
        status_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.health_status.value
            status_data.setdefault(key, []).append(r.health_score)
        result: dict[str, Any] = {}
        for status, scores in status_data.items():
            result[status] = {
                "count": len(scores),
                "avg_health_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_at_risk(self) -> list[dict[str, Any]]:
        """Return records where status is AT_RISK or BREACHING."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.health_status in (HealthStatus.AT_RISK, HealthStatus.BREACHING):
                results.append(
                    {
                        "record_id": r.id,
                        "service_name": r.service_name,
                        "health_status": r.health_status.value,
                        "health_score": r.health_score,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_health_score(self) -> list[dict[str, Any]]:
        """Group by team, avg health_score, sort ascending (worst first)."""
        team_data: dict[str, list[float]] = {}
        for r in self._records:
            team_data.setdefault(r.team, []).append(r.health_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_data.items():
            results.append(
                {
                    "team": team,
                    "record_count": len(scores),
                    "avg_health_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_health_score"])
        return results

    def detect_health_trends(self) -> dict[str, Any]:
        """Split-half on min_score; delta threshold 5.0."""
        if len(self._rules) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [ru.min_score for ru in self._rules]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> SLOHealthReport:
        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_trend: dict[str, int] = {}
        for r in self._records:
            by_status[r.health_status.value] = by_status.get(r.health_status.value, 0) + 1
            by_category[r.slo_category.value] = by_category.get(r.slo_category.value, 0) + 1
            by_trend[r.trend_direction.value] = by_trend.get(r.trend_direction.value, 0) + 1
        healthy_count = sum(1 for r in self._records if r.health_status == HealthStatus.HEALTHY)
        scores = [r.health_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        at_risk = self.identify_at_risk()
        at_risk_names = [a["service_name"] for a in at_risk[:5]]
        recs: list[str] = []
        if avg_score < self._min_health_score and self._records:
            recs.append(
                f"Average health score {avg_score} is below threshold ({self._min_health_score})"
            )
        if at_risk:
            recs.append(f"{len(at_risk)} service(s) at risk or breaching — review SLO targets")
        if not recs:
            recs.append("SLO health levels are acceptable")
        return SLOHealthReport(
            total_records=len(self._records),
            total_rules=len(self._rules),
            healthy_count=healthy_count,
            avg_health_score=avg_score,
            by_status=by_status,
            by_category=by_category,
            by_trend=by_trend,
            at_risk_services=at_risk_names,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("slo_health.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.health_status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "min_health_score": self._min_health_score,
            "status_distribution": status_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service_name for r in self._records}),
        }
