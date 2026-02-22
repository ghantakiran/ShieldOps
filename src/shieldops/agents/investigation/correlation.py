"""Incident correlation engine — groups related alerts into unified incidents."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class CorrelatedIncident(BaseModel):
    """A group of related investigations correlated into a single incident."""

    id: str = Field(default_factory=lambda: f"cid-{uuid4().hex[:12]}")
    title: str = ""
    severity: str = "warning"
    status: str = "open"  # open, investigating, resolved, merged
    investigation_ids: list[str] = Field(default_factory=list)
    correlation_score: float = 0.0
    correlation_reasons: list[str] = Field(default_factory=list)
    service: str = ""
    environment: str = ""
    first_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    merged_into: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CorrelationEngine:
    """Groups related investigations into correlated incidents."""

    def __init__(
        self,
        time_window_minutes: int = 30,
        similarity_threshold: float = 0.5,
    ) -> None:
        self._time_window = timedelta(minutes=time_window_minutes)
        self._similarity_threshold = similarity_threshold
        self._incidents: dict[str, CorrelatedIncident] = {}
        self._investigation_to_incident: dict[str, str] = {}

    def correlate(self, investigation: dict[str, Any]) -> CorrelatedIncident:
        """Correlate an investigation with existing incidents or create new one.

        Correlation strategy:
        1. Time-window: alerts within time_window_minutes are candidates
        2. Service-graph: same service/resource get high score
        3. Alert-type: same alert_name/type get medium score
        4. Dedup: exact same alert_id is a duplicate
        """
        inv_id = investigation.get("investigation_id", "")

        # Check if already correlated
        if inv_id in self._investigation_to_incident:
            return self._incidents[self._investigation_to_incident[inv_id]]

        best_match: CorrelatedIncident | None = None
        best_score = 0.0
        best_reasons: list[str] = []

        inv_time = self._parse_time(investigation.get("created_at"))
        inv_alert = investigation.get("alert_name", "")
        inv_service = self._extract_service(investigation)
        inv_env = self._extract_environment(investigation)
        inv_alert_id = investigation.get("alert_id", "")

        for incident in self._incidents.values():
            if incident.status in ("resolved", "merged"):
                continue

            score = 0.0
            reasons: list[str] = []

            # Time-window check
            if inv_time and incident.last_seen:
                delta = abs((inv_time - incident.last_seen).total_seconds())
                if delta <= self._time_window.total_seconds():
                    time_score = max(0, 1.0 - (delta / self._time_window.total_seconds()))
                    score += time_score * 0.3
                    reasons.append(f"time_proximity:{time_score:.2f}")
                else:
                    continue  # Outside time window, skip

            # Service-graph linking
            if inv_service and inv_service == incident.service:
                score += 0.35
                reasons.append("same_service")

            # Alert-type matching
            if inv_alert and inv_alert == incident.title:
                score += 0.25
                reasons.append("same_alert_type")

            # Environment matching
            if inv_env and inv_env == incident.environment:
                score += 0.1
                reasons.append("same_environment")

            # Dedup check — exact alert_id match
            for existing_inv_id in incident.investigation_ids:
                existing = self._get_investigation_data(existing_inv_id)
                if existing and existing.get("alert_id") == inv_alert_id and inv_alert_id:
                    score = 1.0
                    reasons = ["exact_alert_dedup"]
                    break

            if score > best_score and score >= self._similarity_threshold:
                best_score = score
                best_match = incident
                best_reasons = reasons

        if best_match:
            # Add to existing incident
            best_match.investigation_ids.append(inv_id)
            best_match.correlation_score = max(best_match.correlation_score, best_score)
            best_match.correlation_reasons = list(
                set(best_match.correlation_reasons + best_reasons)
            )
            best_match.last_seen = inv_time or datetime.now(UTC)
            # Escalate severity
            best_match.severity = self._max_severity(
                best_match.severity,
                investigation.get("severity", "warning"),
            )
            self._investigation_to_incident[inv_id] = best_match.id
            logger.info(
                "investigation_correlated",
                investigation_id=inv_id,
                incident_id=best_match.id,
                score=best_score,
            )
            return best_match

        # Create new incident
        incident = CorrelatedIncident(
            title=inv_alert or f"Incident from {inv_id}",
            severity=investigation.get("severity", "warning"),
            investigation_ids=[inv_id],
            correlation_score=1.0,
            correlation_reasons=["initial"],
            service=inv_service,
            environment=inv_env,
            first_seen=inv_time or datetime.now(UTC),
            last_seen=inv_time or datetime.now(UTC),
        )
        self._incidents[incident.id] = incident
        self._investigation_to_incident[inv_id] = incident.id
        logger.info("incident_created", incident_id=incident.id, investigation_id=inv_id)
        return incident

    def merge(self, source_id: str, target_id: str) -> CorrelatedIncident | None:
        """Merge source incident into target incident."""
        source = self._incidents.get(source_id)
        target = self._incidents.get(target_id)
        if not source or not target:
            return None
        if source_id == target_id:
            return None

        # Move all investigations from source to target
        for inv_id in source.investigation_ids:
            if inv_id not in target.investigation_ids:
                target.investigation_ids.append(inv_id)
            self._investigation_to_incident[inv_id] = target_id

        target.correlation_reasons.append(f"merged_from:{source_id}")
        target.severity = self._max_severity(target.severity, source.severity)
        target.first_seen = min(target.first_seen, source.first_seen)
        target.last_seen = max(target.last_seen, source.last_seen)

        source.status = "merged"
        source.merged_into = target_id
        source.investigation_ids = []

        logger.info("incidents_merged", source=source_id, target=target_id)
        return target

    def get_incident(self, incident_id: str) -> CorrelatedIncident | None:
        return self._incidents.get(incident_id)

    def get_incident_for_investigation(self, investigation_id: str) -> CorrelatedIncident | None:
        iid = self._investigation_to_incident.get(investigation_id)
        return self._incidents.get(iid) if iid else None

    def list_incidents(
        self,
        status: str | None = None,
        service: str | None = None,
        environment: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CorrelatedIncident]:
        incidents = list(self._incidents.values())
        if status:
            incidents = [i for i in incidents if i.status == status]
        if service:
            incidents = [i for i in incidents if i.service == service]
        if environment:
            incidents = [i for i in incidents if i.environment == environment]
        # Sort by last_seen descending
        incidents.sort(key=lambda i: i.last_seen, reverse=True)
        return incidents[offset : offset + limit]

    def update_status(self, incident_id: str, status: str) -> bool:
        incident = self._incidents.get(incident_id)
        if not incident:
            return False
        incident.status = status
        return True

    # Private helpers
    _investigation_data: dict[str, dict[str, Any]] = {}

    def _get_investigation_data(self, inv_id: str) -> dict[str, Any] | None:
        return self._investigation_data.get(inv_id)

    def _store_investigation_data(self, inv_id: str, data: dict[str, Any]) -> None:
        self._investigation_data[inv_id] = data

    @staticmethod
    def _parse_time(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except (ValueError, TypeError):
                pass
        return datetime.now(UTC)

    @staticmethod
    def _extract_service(investigation: dict[str, Any]) -> str:
        ctx = investigation.get("alert_context", {})
        if isinstance(ctx, dict):
            return ctx.get("service", "") or ctx.get("resource_type", "") or ""
        return ""

    @staticmethod
    def _extract_environment(investigation: dict[str, Any]) -> str:
        ctx = investigation.get("alert_context", {})
        if isinstance(ctx, dict):
            return ctx.get("environment", "") or ""
        return ""

    @staticmethod
    def _max_severity(a: str, b: str) -> str:
        order = {"critical": 4, "high": 3, "warning": 2, "low": 1, "info": 0}
        return a if order.get(a, 0) >= order.get(b, 0) else b

    def _fingerprint(self, investigation: dict[str, Any]) -> str:
        parts = [
            self._extract_service(investigation),
            investigation.get("alert_name", ""),
            self._extract_environment(investigation),
        ]
        return hashlib.md5(  # noqa: S324
            "|".join(parts).encode(), usedforsecurity=False
        ).hexdigest()[:16]
