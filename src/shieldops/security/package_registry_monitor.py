"""Package Registry Monitor — monitor package registry events and security advisories."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RegistryEvent(StrEnum):
    PUBLISH = "publish"
    UNPUBLISH = "unpublish"
    DEPRECATE = "deprecate"
    SECURITY_ADVISORY = "security_advisory"
    OWNERSHIP_CHANGE = "ownership_change"


class MonitorScope(StrEnum):
    DIRECT = "direct"
    TRANSITIVE = "transitive"
    ALL = "all"
    CRITICAL = "critical"
    CUSTOM = "custom"


class AlertLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# --- Models ---


class RegistryMonitorRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    package_name: str = ""
    registry_event: RegistryEvent = RegistryEvent.PUBLISH
    monitor_scope: MonitorScope = MonitorScope.ALL
    alert_level: AlertLevel = AlertLevel.INFO
    monitor_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RegistryMonitorAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    package_name: str = ""
    registry_event: RegistryEvent = RegistryEvent.PUBLISH
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PackageRegistryReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_monitor_score: float = 0.0
    by_event: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_alert_level: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PackageRegistryMonitor:
    """Monitor package registry events including publishes, advisories, and ownership changes."""

    def __init__(
        self,
        max_records: int = 200000,
        monitor_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._monitor_gap_threshold = monitor_gap_threshold
        self._records: list[RegistryMonitorRecord] = []
        self._analyses: list[RegistryMonitorAnalysis] = []
        logger.info(
            "package_registry_monitor.initialized",
            max_records=max_records,
            monitor_gap_threshold=monitor_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_event(
        self,
        package_name: str,
        registry_event: RegistryEvent = RegistryEvent.PUBLISH,
        monitor_scope: MonitorScope = MonitorScope.ALL,
        alert_level: AlertLevel = AlertLevel.INFO,
        monitor_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RegistryMonitorRecord:
        record = RegistryMonitorRecord(
            package_name=package_name,
            registry_event=registry_event,
            monitor_scope=monitor_scope,
            alert_level=alert_level,
            monitor_score=monitor_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "package_registry_monitor.event_recorded",
            record_id=record.id,
            package_name=package_name,
            registry_event=registry_event.value,
            alert_level=alert_level.value,
        )
        return record

    def get_event(self, record_id: str) -> RegistryMonitorRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_events(
        self,
        registry_event: RegistryEvent | None = None,
        alert_level: AlertLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RegistryMonitorRecord]:
        results = list(self._records)
        if registry_event is not None:
            results = [r for r in results if r.registry_event == registry_event]
        if alert_level is not None:
            results = [r for r in results if r.alert_level == alert_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        package_name: str,
        registry_event: RegistryEvent = RegistryEvent.PUBLISH,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RegistryMonitorAnalysis:
        analysis = RegistryMonitorAnalysis(
            package_name=package_name,
            registry_event=registry_event,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "package_registry_monitor.analysis_added",
            package_name=package_name,
            registry_event=registry_event.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_event_distribution(self) -> dict[str, Any]:
        """Group by registry_event; return count and avg monitor_score."""
        event_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.registry_event.value
            event_data.setdefault(key, []).append(r.monitor_score)
        result: dict[str, Any] = {}
        for event, scores in event_data.items():
            result[event] = {
                "count": len(scores),
                "avg_monitor_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_monitor_gaps(self) -> list[dict[str, Any]]:
        """Return records where monitor_score < monitor_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.monitor_score < self._monitor_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "package_name": r.package_name,
                        "registry_event": r.registry_event.value,
                        "monitor_score": r.monitor_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["monitor_score"])

    def rank_by_monitor_score(self) -> list[dict[str, Any]]:
        """Group by service, avg monitor_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.monitor_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_monitor_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_monitor_score"])
        return results

    def detect_monitor_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
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
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> PackageRegistryReport:
        by_event: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        by_alert_level: dict[str, int] = {}
        for r in self._records:
            by_event[r.registry_event.value] = by_event.get(r.registry_event.value, 0) + 1
            by_scope[r.monitor_scope.value] = by_scope.get(r.monitor_scope.value, 0) + 1
            by_alert_level[r.alert_level.value] = by_alert_level.get(r.alert_level.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.monitor_score < self._monitor_gap_threshold)
        scores = [r.monitor_score for r in self._records]
        avg_monitor_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_monitor_gaps()
        top_gaps = [o["package_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} package(s) below monitor threshold ({self._monitor_gap_threshold})"
            )
        if self._records and avg_monitor_score < self._monitor_gap_threshold:
            recs.append(
                f"Avg monitor score {avg_monitor_score} below threshold "
                f"({self._monitor_gap_threshold})"
            )
        if not recs:
            recs.append("Package registry monitoring is healthy")
        return PackageRegistryReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_monitor_score=avg_monitor_score,
            by_event=by_event,
            by_scope=by_scope,
            by_alert_level=by_alert_level,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("package_registry_monitor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        event_dist: dict[str, int] = {}
        for r in self._records:
            key = r.registry_event.value
            event_dist[key] = event_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "monitor_gap_threshold": self._monitor_gap_threshold,
            "event_distribution": event_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
