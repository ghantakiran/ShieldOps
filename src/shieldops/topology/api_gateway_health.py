"""API Gateway Health Monitor — monitor gateway performance, errors, and degradation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class GatewayMetric(StrEnum):
    ERROR_RATE = "error_rate"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    RATE_LIMIT_HITS = "rate_limit_hits"
    CONNECTION_POOL = "connection_pool"


class GatewayStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OVERLOADED = "overloaded"
    FAILING = "failing"
    OFFLINE = "offline"


class GatewayIssue(StrEnum):
    RATE_LIMITING = "rate_limiting"
    TIMEOUT = "timeout"
    BACKEND_ERROR = "backend_error"
    SSL_ERROR = "ssl_error"
    ROUTING_FAILURE = "routing_failure"


# --- Models ---


class GatewayHealthRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gateway_id: str = ""
    gateway_metric: GatewayMetric = GatewayMetric.ERROR_RATE
    gateway_status: GatewayStatus = GatewayStatus.HEALTHY
    gateway_issue: GatewayIssue = GatewayIssue.RATE_LIMITING
    error_rate_pct: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class GatewayAlert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str = ""
    gateway_metric: GatewayMetric = GatewayMetric.ERROR_RATE
    error_threshold: float = 0.0
    avg_error_rate: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class APIGatewayHealthReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_alerts: int = 0
    unhealthy_gateways: int = 0
    avg_error_rate: float = 0.0
    by_metric: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_issue: dict[str, int] = Field(default_factory=dict)
    top_items: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class APIGatewayHealthMonitor:
    """Monitor API gateway performance, errors, and degradation patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        max_error_rate_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_error_rate_pct = max_error_rate_pct
        self._records: list[GatewayHealthRecord] = []
        self._alerts: list[GatewayAlert] = []
        logger.info(
            "api_gateway_health.initialized",
            max_records=max_records,
            max_error_rate_pct=max_error_rate_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_health(
        self,
        gateway_id: str,
        gateway_metric: GatewayMetric = GatewayMetric.ERROR_RATE,
        gateway_status: GatewayStatus = GatewayStatus.HEALTHY,
        gateway_issue: GatewayIssue = GatewayIssue.RATE_LIMITING,
        error_rate_pct: float = 0.0,
        team: str = "",
    ) -> GatewayHealthRecord:
        record = GatewayHealthRecord(
            gateway_id=gateway_id,
            gateway_metric=gateway_metric,
            gateway_status=gateway_status,
            gateway_issue=gateway_issue,
            error_rate_pct=error_rate_pct,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "api_gateway_health.recorded",
            record_id=record.id,
            gateway_id=gateway_id,
            gateway_metric=gateway_metric.value,
            gateway_status=gateway_status.value,
        )
        return record

    def get_health(self, record_id: str) -> GatewayHealthRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_health_records(
        self,
        metric: GatewayMetric | None = None,
        status: GatewayStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[GatewayHealthRecord]:
        results = list(self._records)
        if metric is not None:
            results = [r for r in results if r.gateway_metric == metric]
        if status is not None:
            results = [r for r in results if r.gateway_status == status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_alert(
        self,
        alert_name: str,
        gateway_metric: GatewayMetric = GatewayMetric.ERROR_RATE,
        error_threshold: float = 0.0,
        avg_error_rate: float = 0.0,
        description: str = "",
    ) -> GatewayAlert:
        alert = GatewayAlert(
            alert_name=alert_name,
            gateway_metric=gateway_metric,
            error_threshold=error_threshold,
            avg_error_rate=avg_error_rate,
            description=description,
        )
        self._alerts.append(alert)
        if len(self._alerts) > self._max_records:
            self._alerts = self._alerts[-self._max_records :]
        logger.info(
            "api_gateway_health.alert_added",
            alert_name=alert_name,
            gateway_metric=gateway_metric.value,
            error_threshold=error_threshold,
        )
        return alert

    # -- domain operations --------------------------------------------------

    def analyze_gateway_performance(self) -> dict[str, Any]:
        """Group by metric; return count and avg error rate per metric type."""
        metric_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.gateway_metric.value
            metric_data.setdefault(key, []).append(r.error_rate_pct)
        result: dict[str, Any] = {}
        for metric, rates in metric_data.items():
            result[metric] = {
                "count": len(rates),
                "avg_error_rate": round(sum(rates) / len(rates), 2),
            }
        return result

    def identify_unhealthy_gateways(self) -> list[dict[str, Any]]:
        """Return records where status is FAILING or OFFLINE."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.gateway_status in (
                GatewayStatus.FAILING,
                GatewayStatus.OFFLINE,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "gateway_id": r.gateway_id,
                        "gateway_status": r.gateway_status.value,
                        "error_rate_pct": r.error_rate_pct,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_error_rate(self) -> list[dict[str, Any]]:
        """Group by team, avg error rate, sort descending."""
        team_rates: dict[str, list[float]] = {}
        for r in self._records:
            team_rates.setdefault(r.team, []).append(r.error_rate_pct)
        results: list[dict[str, Any]] = []
        for team, rates in team_rates.items():
            results.append(
                {
                    "team": team,
                    "avg_error_rate": round(sum(rates) / len(rates), 2),
                    "count": len(rates),
                }
            )
        results.sort(key=lambda x: x["avg_error_rate"], reverse=True)
        return results

    def detect_gateway_degradation(self) -> dict[str, Any]:
        """Split-half on avg_error_rate; delta threshold 5.0."""
        if len(self._alerts) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        rates = [a.avg_error_rate for a in self._alerts]
        mid = len(rates) // 2
        first_half = rates[:mid]
        second_half = rates[mid:]
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

    def generate_report(self) -> APIGatewayHealthReport:
        by_metric: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_issue: dict[str, int] = {}
        for r in self._records:
            by_metric[r.gateway_metric.value] = by_metric.get(r.gateway_metric.value, 0) + 1
            by_status[r.gateway_status.value] = by_status.get(r.gateway_status.value, 0) + 1
            by_issue[r.gateway_issue.value] = by_issue.get(r.gateway_issue.value, 0) + 1
        unhealthy_count = sum(
            1
            for r in self._records
            if r.gateway_status in (GatewayStatus.FAILING, GatewayStatus.OFFLINE)
        )
        avg_rate = (
            round(sum(r.error_rate_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_error_rate()
        top_items = [rk["team"] for rk in rankings[:5]]
        recs: list[str] = []
        if avg_rate > self._max_error_rate_pct:
            recs.append(
                f"Avg error rate {avg_rate}% exceeds threshold ({self._max_error_rate_pct}%)"
            )
        if unhealthy_count > 0:
            recs.append(f"{unhealthy_count} unhealthy gateway(s) detected — review status")
        if not recs:
            recs.append("API gateway health is within acceptable limits")
        return APIGatewayHealthReport(
            total_records=len(self._records),
            total_alerts=len(self._alerts),
            unhealthy_gateways=unhealthy_count,
            avg_error_rate=avg_rate,
            by_metric=by_metric,
            by_status=by_status,
            by_issue=by_issue,
            top_items=top_items,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._alerts.clear()
        logger.info("api_gateway_health.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        metric_dist: dict[str, int] = {}
        for r in self._records:
            key = r.gateway_metric.value
            metric_dist[key] = metric_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_alerts": len(self._alerts),
            "max_error_rate_pct": self._max_error_rate_pct,
            "metric_distribution": metric_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_gateways": len({r.gateway_id for r in self._records}),
        }
