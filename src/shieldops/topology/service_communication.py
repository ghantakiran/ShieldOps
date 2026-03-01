"""Service Communication Analyzer — analyze communication patterns, health, and anomalies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CommunicationPattern(StrEnum):
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    EVENT_DRIVEN = "event_driven"
    BATCH = "batch"
    STREAMING = "streaming"


class CommunicationHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    TIMEOUT = "timeout"
    CIRCUIT_OPEN = "circuit_open"


class CommunicationIssue(StrEnum):
    HIGH_LATENCY = "high_latency"
    RETRY_STORM = "retry_storm"
    CIRCULAR_DEPENDENCY = "circular_dependency"
    TIGHT_COUPLING = "tight_coupling"
    VERSION_MISMATCH = "version_mismatch"


# --- Models ---


class CommunicationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    communication_pattern: CommunicationPattern = CommunicationPattern.SYNCHRONOUS
    communication_health: CommunicationHealth = CommunicationHealth.HEALTHY
    communication_issue: CommunicationIssue = CommunicationIssue.HIGH_LATENCY
    anomaly_rate: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CommunicationLink(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    link_name: str = ""
    communication_pattern: CommunicationPattern = CommunicationPattern.SYNCHRONOUS
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ServiceCommunicationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_links: int = 0
    unhealthy_communications: int = 0
    avg_anomaly_rate: float = 0.0
    by_pattern: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    by_issue: dict[str, int] = Field(default_factory=dict)
    top_items: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceCommunicationAnalyzer:
    """Analyze service communication patterns, health, and anomalies."""

    def __init__(
        self,
        max_records: int = 200000,
        max_anomaly_rate_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_anomaly_rate_pct = max_anomaly_rate_pct
        self._records: list[CommunicationRecord] = []
        self._links: list[CommunicationLink] = []
        logger.info(
            "service_communication.initialized",
            max_records=max_records,
            max_anomaly_rate_pct=max_anomaly_rate_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_communication(
        self,
        service_name: str,
        communication_pattern: CommunicationPattern = CommunicationPattern.SYNCHRONOUS,
        communication_health: CommunicationHealth = CommunicationHealth.HEALTHY,
        communication_issue: CommunicationIssue = CommunicationIssue.HIGH_LATENCY,
        anomaly_rate: float = 0.0,
        team: str = "",
    ) -> CommunicationRecord:
        record = CommunicationRecord(
            service_name=service_name,
            communication_pattern=communication_pattern,
            communication_health=communication_health,
            communication_issue=communication_issue,
            anomaly_rate=anomaly_rate,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "service_communication.recorded",
            record_id=record.id,
            service_name=service_name,
            communication_pattern=communication_pattern.value,
            communication_health=communication_health.value,
        )
        return record

    def get_communication(self, record_id: str) -> CommunicationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_communications(
        self,
        pattern: CommunicationPattern | None = None,
        health: CommunicationHealth | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CommunicationRecord]:
        results = list(self._records)
        if pattern is not None:
            results = [r for r in results if r.communication_pattern == pattern]
        if health is not None:
            results = [r for r in results if r.communication_health == health]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_link(
        self,
        link_name: str,
        communication_pattern: CommunicationPattern = CommunicationPattern.SYNCHRONOUS,
        error_rate: float = 0.0,
        avg_latency_ms: float = 0.0,
        description: str = "",
    ) -> CommunicationLink:
        link = CommunicationLink(
            link_name=link_name,
            communication_pattern=communication_pattern,
            error_rate=error_rate,
            avg_latency_ms=avg_latency_ms,
            description=description,
        )
        self._links.append(link)
        if len(self._links) > self._max_records:
            self._links = self._links[-self._max_records :]
        logger.info(
            "service_communication.link_added",
            link_name=link_name,
            communication_pattern=communication_pattern.value,
            error_rate=error_rate,
        )
        return link

    # -- domain operations --------------------------------------------------

    def analyze_communication_patterns(self) -> dict[str, Any]:
        """Group by pattern; return count and avg anomaly rate per pattern."""
        pattern_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.communication_pattern.value
            pattern_data.setdefault(key, []).append(r.anomaly_rate)
        result: dict[str, Any] = {}
        for pattern, rates in pattern_data.items():
            result[pattern] = {
                "count": len(rates),
                "avg_anomaly_rate": round(sum(rates) / len(rates), 2),
            }
        return result

    def identify_unhealthy_links(self) -> list[dict[str, Any]]:
        """Return records where health is FAILING or CIRCUIT_OPEN."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.communication_health in (
                CommunicationHealth.FAILING,
                CommunicationHealth.CIRCUIT_OPEN,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "service_name": r.service_name,
                        "communication_health": r.communication_health.value,
                        "anomaly_rate": r.anomaly_rate,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_reliability(self) -> list[dict[str, Any]]:
        """Group by team, avg anomaly rate, sort descending."""
        team_rates: dict[str, list[float]] = {}
        for r in self._records:
            team_rates.setdefault(r.team, []).append(r.anomaly_rate)
        results: list[dict[str, Any]] = []
        for team, rates in team_rates.items():
            results.append(
                {
                    "team": team,
                    "avg_anomaly_rate": round(sum(rates) / len(rates), 2),
                    "count": len(rates),
                }
            )
        results.sort(key=lambda x: x["avg_anomaly_rate"], reverse=True)
        return results

    def detect_communication_anomalies(self) -> dict[str, Any]:
        """Split-half on avg_latency_ms; delta threshold 5.0."""
        if len(self._links) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [lk.avg_latency_ms for lk in self._links]
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

    def generate_report(self) -> ServiceCommunicationReport:
        by_pattern: dict[str, int] = {}
        by_health: dict[str, int] = {}
        by_issue: dict[str, int] = {}
        for r in self._records:
            by_pattern[r.communication_pattern.value] = (
                by_pattern.get(r.communication_pattern.value, 0) + 1
            )
            by_health[r.communication_health.value] = (
                by_health.get(r.communication_health.value, 0) + 1
            )
            by_issue[r.communication_issue.value] = by_issue.get(r.communication_issue.value, 0) + 1
        unhealthy_count = sum(
            1
            for r in self._records
            if r.communication_health
            in (CommunicationHealth.FAILING, CommunicationHealth.CIRCUIT_OPEN)
        )
        avg_rate = (
            round(sum(r.anomaly_rate for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_reliability()
        top_items = [rk["team"] for rk in rankings[:5]]
        recs: list[str] = []
        if avg_rate > self._max_anomaly_rate_pct:
            recs.append(
                f"Avg anomaly rate {avg_rate} exceeds threshold ({self._max_anomaly_rate_pct})"
            )
        if unhealthy_count > 0:
            recs.append(f"{unhealthy_count} unhealthy communication(s) detected — review links")
        if not recs:
            recs.append("Service communication is within acceptable limits")
        return ServiceCommunicationReport(
            total_records=len(self._records),
            total_links=len(self._links),
            unhealthy_communications=unhealthy_count,
            avg_anomaly_rate=avg_rate,
            by_pattern=by_pattern,
            by_health=by_health,
            by_issue=by_issue,
            top_items=top_items,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._links.clear()
        logger.info("service_communication.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        pattern_dist: dict[str, int] = {}
        for r in self._records:
            key = r.communication_pattern.value
            pattern_dist[key] = pattern_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_links": len(self._links),
            "max_anomaly_rate_pct": self._max_anomaly_rate_pct,
            "pattern_distribution": pattern_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service_name for r in self._records}),
        }
