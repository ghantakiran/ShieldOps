"""Identity Federation Monitor — monitor identity federation protocols and health."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FederationProtocol(StrEnum):
    SAML = "saml"
    OIDC = "oidc"
    OAUTH2 = "oauth2"
    SCIM = "scim"
    LDAP = "ldap"


class MonitoringEvent(StrEnum):
    TOKEN_ISSUE = "token_issue"  # noqa: S105
    TOKEN_REFRESH = "token_refresh"  # noqa: S105
    TOKEN_REVOKE = "token_revoke"  # noqa: S105
    FEDERATION_SYNC = "federation_sync"
    FEDERATION_ERROR = "federation_error"


class FederationHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    IMPAIRED = "impaired"
    DOWN = "down"
    UNKNOWN = "unknown"


# --- Models ---


class FederationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    federation_id: str = ""
    federation_protocol: FederationProtocol = FederationProtocol.SAML
    monitoring_event: MonitoringEvent = MonitoringEvent.TOKEN_ISSUE
    federation_health: FederationHealth = FederationHealth.HEALTHY
    health_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class FederationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    federation_id: str = ""
    federation_protocol: FederationProtocol = FederationProtocol.SAML
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IdentityFederationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_health_score: float = 0.0
    by_federation_protocol: dict[str, int] = Field(default_factory=dict)
    by_monitoring_event: dict[str, int] = Field(default_factory=dict)
    by_federation_health: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IdentityFederationMonitor:
    """Monitor identity federation protocols, track health, and analyze federation patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        federation_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._federation_gap_threshold = federation_gap_threshold
        self._records: list[FederationRecord] = []
        self._analyses: list[FederationAnalysis] = []
        logger.info(
            "identity_federation_monitor.initialized",
            max_records=max_records,
            federation_gap_threshold=federation_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_federation(
        self,
        federation_id: str,
        federation_protocol: FederationProtocol = FederationProtocol.SAML,
        monitoring_event: MonitoringEvent = MonitoringEvent.TOKEN_ISSUE,
        federation_health: FederationHealth = FederationHealth.HEALTHY,
        health_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> FederationRecord:
        record = FederationRecord(
            federation_id=federation_id,
            federation_protocol=federation_protocol,
            monitoring_event=monitoring_event,
            federation_health=federation_health,
            health_score=health_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "identity_federation_monitor.federation_recorded",
            record_id=record.id,
            federation_id=federation_id,
            federation_protocol=federation_protocol.value,
            monitoring_event=monitoring_event.value,
        )
        return record

    def get_federation(self, record_id: str) -> FederationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_federations(
        self,
        federation_protocol: FederationProtocol | None = None,
        monitoring_event: MonitoringEvent | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FederationRecord]:
        results = list(self._records)
        if federation_protocol is not None:
            results = [r for r in results if r.federation_protocol == federation_protocol]
        if monitoring_event is not None:
            results = [r for r in results if r.monitoring_event == monitoring_event]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        federation_id: str,
        federation_protocol: FederationProtocol = FederationProtocol.SAML,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> FederationAnalysis:
        analysis = FederationAnalysis(
            federation_id=federation_id,
            federation_protocol=federation_protocol,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "identity_federation_monitor.analysis_added",
            federation_id=federation_id,
            federation_protocol=federation_protocol.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_federation_distribution(self) -> dict[str, Any]:
        """Group by federation_protocol; return count and avg health_score."""
        protocol_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.federation_protocol.value
            protocol_data.setdefault(key, []).append(r.health_score)
        result: dict[str, Any] = {}
        for protocol, scores in protocol_data.items():
            result[protocol] = {
                "count": len(scores),
                "avg_health_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_federation_gaps(self) -> list[dict[str, Any]]:
        """Return records where health_score < federation_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.health_score < self._federation_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "federation_id": r.federation_id,
                        "federation_protocol": r.federation_protocol.value,
                        "health_score": r.health_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["health_score"])

    def rank_by_federation(self) -> list[dict[str, Any]]:
        """Group by service, avg health_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.health_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_health_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_health_score"])
        return results

    def detect_federation_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> IdentityFederationReport:
        by_federation_protocol: dict[str, int] = {}
        by_monitoring_event: dict[str, int] = {}
        by_federation_health: dict[str, int] = {}
        for r in self._records:
            by_federation_protocol[r.federation_protocol.value] = (
                by_federation_protocol.get(r.federation_protocol.value, 0) + 1
            )
            by_monitoring_event[r.monitoring_event.value] = (
                by_monitoring_event.get(r.monitoring_event.value, 0) + 1
            )
            by_federation_health[r.federation_health.value] = (
                by_federation_health.get(r.federation_health.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.health_score < self._federation_gap_threshold)
        scores = [r.health_score for r in self._records]
        avg_health_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_federation_gaps()
        top_gaps = [o["federation_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} federation(s) below health threshold "
                f"({self._federation_gap_threshold})"
            )
        if self._records and avg_health_score < self._federation_gap_threshold:
            recs.append(
                f"Avg health score {avg_health_score} below threshold "
                f"({self._federation_gap_threshold})"
            )
        if not recs:
            recs.append("Identity federation monitoring is healthy")
        return IdentityFederationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_health_score=avg_health_score,
            by_federation_protocol=by_federation_protocol,
            by_monitoring_event=by_monitoring_event,
            by_federation_health=by_federation_health,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("identity_federation_monitor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        protocol_dist: dict[str, int] = {}
        for r in self._records:
            key = r.federation_protocol.value
            protocol_dist[key] = protocol_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "federation_gap_threshold": self._federation_gap_threshold,
            "federation_protocol_distribution": protocol_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
