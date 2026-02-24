"""Deployment Cadence Analyzer — deployment frequency, timing patterns, velocity trends."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DeploymentFrequency(StrEnum):
    MULTIPLE_DAILY = "multiple_daily"
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class CadenceHealth(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    STALLED = "stalled"


class TimeSlot(StrEnum):
    BUSINESS_HOURS = "business_hours"
    AFTER_HOURS = "after_hours"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"
    MAINTENANCE_WINDOW = "maintenance_window"


# --- Models ---


class DeploymentEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    team: str = ""
    deployed_at: float = Field(default_factory=time.time)
    time_slot: TimeSlot = TimeSlot.BUSINESS_HOURS
    frequency: DeploymentFrequency = DeploymentFrequency.WEEKLY
    environment: str = "production"
    is_success: bool = True
    rollback: bool = False
    created_at: float = Field(default_factory=time.time)


class CadenceScore(BaseModel):
    service_name: str = ""
    team: str = ""
    frequency: DeploymentFrequency = DeploymentFrequency.WEEKLY
    health: CadenceHealth = CadenceHealth.FAIR
    deploy_count: int = 0
    success_rate: float = 0.0
    avg_interval_hours: float = 0.0
    score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class CadenceReport(BaseModel):
    total_deployments: int = 0
    total_services: int = 0
    avg_frequency_score: float = 0.0
    by_frequency: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeploymentCadenceAnalyzer:
    """Analyze deployment frequency, timing patterns, and velocity
    trends per service/team."""

    def __init__(
        self,
        max_deployments: int = 200000,
    ) -> None:
        self._max_deployments = max_deployments
        self._items: list[DeploymentEvent] = []
        self._scores: dict[str, CadenceScore] = {}
        logger.info(
            "deployment_cadence.initialized",
            max_deployments=max_deployments,
        )

    # -- CRUD -------------------------------------------------------

    def record_deployment(
        self,
        service_name: str,
        team: str = "",
        time_slot: TimeSlot = TimeSlot.BUSINESS_HOURS,
        frequency: DeploymentFrequency = DeploymentFrequency.WEEKLY,
        environment: str = "production",
        is_success: bool = True,
        rollback: bool = False,
        **kw: Any,
    ) -> DeploymentEvent:
        """Record a deployment event."""
        event = DeploymentEvent(
            service_name=service_name,
            team=team,
            time_slot=time_slot,
            frequency=frequency,
            environment=environment,
            is_success=is_success,
            rollback=rollback,
            **kw,
        )
        self._items.append(event)
        if len(self._items) > self._max_deployments:
            self._items = self._items[-self._max_deployments :]
        logger.info(
            "deployment_cadence.recorded",
            event_id=event.id,
            service_name=service_name,
            team=team,
        )
        return event

    def get_deployment(self, event_id: str) -> DeploymentEvent | None:
        """Retrieve a deployment event by ID."""
        for item in self._items:
            if item.id == event_id:
                return item
        return None

    def list_deployments(
        self,
        service_name: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DeploymentEvent]:
        """List deployments with optional filters."""
        results = list(self._items)
        if service_name is not None:
            results = [e for e in results if e.service_name == service_name]
        if team is not None:
            results = [e for e in results if e.team == team]
        return results[-limit:]

    # -- Domain operations ------------------------------------------

    def calculate_cadence(
        self,
        service_name: str,
    ) -> CadenceScore:
        """Calculate cadence score for a service."""
        deps = [e for e in self._items if e.service_name == service_name]
        total = len(deps)
        if total == 0:
            return CadenceScore(service_name=service_name)

        success_count = sum(1 for e in deps if e.is_success)
        success_rate = round(success_count / total, 4)

        # Calculate average interval hours
        sorted_deps = sorted(deps, key=lambda e: e.deployed_at)
        intervals: list[float] = []
        for i in range(1, len(sorted_deps)):
            diff = sorted_deps[i].deployed_at - sorted_deps[i - 1].deployed_at
            intervals.append(diff / 3600.0)
        avg_interval = round(sum(intervals) / len(intervals), 2) if intervals else 0.0

        # Determine frequency from interval
        frequency = self._interval_to_frequency(avg_interval)
        health = self._calculate_health(
            success_rate,
            avg_interval,
            total,
        )
        score = self._compute_score(
            success_rate,
            avg_interval,
            total,
        )

        cadence = CadenceScore(
            service_name=service_name,
            team=deps[0].team if deps else "",
            frequency=frequency,
            health=health,
            deploy_count=total,
            success_rate=success_rate,
            avg_interval_hours=avg_interval,
            score=score,
        )
        self._scores[service_name] = cadence
        logger.info(
            "deployment_cadence.cadence_calculated",
            service_name=service_name,
            frequency=frequency,
            health=health,
            score=score,
        )
        return cadence

    @staticmethod
    def _interval_to_frequency(
        avg_hours: float,
    ) -> DeploymentFrequency:
        """Map average interval hours to frequency category."""
        if avg_hours <= 0 or avg_hours < 12:
            return DeploymentFrequency.MULTIPLE_DAILY
        if avg_hours < 36:
            return DeploymentFrequency.DAILY
        if avg_hours < 168:
            return DeploymentFrequency.WEEKLY
        if avg_hours < 336:
            return DeploymentFrequency.BIWEEKLY
        return DeploymentFrequency.MONTHLY

    @staticmethod
    def _calculate_health(
        success_rate: float,
        avg_interval: float,
        total: int,
    ) -> CadenceHealth:
        """Determine cadence health from metrics."""
        if total == 0:
            return CadenceHealth.STALLED
        if success_rate >= 0.95 and avg_interval < 48:
            return CadenceHealth.EXCELLENT
        if success_rate >= 0.85 and avg_interval < 168:
            return CadenceHealth.GOOD
        if success_rate >= 0.70:
            return CadenceHealth.FAIR
        if success_rate >= 0.50:
            return CadenceHealth.POOR
        return CadenceHealth.STALLED

    @staticmethod
    def _compute_score(
        success_rate: float,
        avg_interval: float,
        total: int,
    ) -> float:
        """Compute a 0-100 cadence score."""
        if total == 0:
            return 0.0
        freq_score = max(0.0, 100.0 - avg_interval * 0.1)
        combined = (success_rate * 60) + (freq_score * 0.4)
        return round(min(100.0, combined), 2)

    def detect_cadence_health(self) -> list[CadenceScore]:
        """Detect cadence health for all services."""
        services: set[str] = {e.service_name for e in self._items}
        results: list[CadenceScore] = []
        for svc in sorted(services):
            score = self.calculate_cadence(svc)
            results.append(score)
        return results

    def identify_bottlenecks(self) -> list[dict[str, Any]]:
        """Identify deployment bottlenecks by time slot."""
        slot_data: dict[str, dict[str, int]] = {}
        for e in self._items:
            slot = e.time_slot.value
            if slot not in slot_data:
                slot_data[slot] = {
                    "total": 0,
                    "failures": 0,
                    "rollbacks": 0,
                }
            slot_data[slot]["total"] += 1
            if not e.is_success:
                slot_data[slot]["failures"] += 1
            if e.rollback:
                slot_data[slot]["rollbacks"] += 1

        bottlenecks: list[dict[str, Any]] = []
        for slot, data in slot_data.items():
            total = data["total"]
            fail_rate = round(data["failures"] / total, 4) if total else 0.0
            bottlenecks.append(
                {
                    "time_slot": slot,
                    "total_deployments": total,
                    "failure_count": data["failures"],
                    "rollback_count": data["rollbacks"],
                    "failure_rate": fail_rate,
                }
            )
        bottlenecks.sort(
            key=lambda b: b["failure_rate"],
            reverse=True,
        )
        return bottlenecks

    def analyze_time_distribution(self) -> dict[str, int]:
        """Analyze deployment distribution across time slots."""
        dist: dict[str, int] = {}
        for e in self._items:
            key = e.time_slot.value
            dist[key] = dist.get(key, 0) + 1
        return dist

    def compare_teams(self) -> list[dict[str, Any]]:
        """Compare deployment cadence across teams."""
        teams: set[str] = {e.team for e in self._items if e.team}
        comparisons: list[dict[str, Any]] = []
        for team in sorted(teams):
            team_deps = [e for e in self._items if e.team == team]
            total = len(team_deps)
            success = sum(1 for e in team_deps if e.is_success)
            rate = round(success / total, 4) if total else 0.0
            comparisons.append(
                {
                    "team": team,
                    "total_deployments": total,
                    "success_rate": rate,
                    "rollback_count": sum(1 for e in team_deps if e.rollback),
                }
            )
        return comparisons

    # -- Report / stats --------------------------------------------

    def generate_cadence_report(self) -> CadenceReport:
        """Generate a comprehensive cadence report."""
        total = len(self._items)
        services: set[str] = {e.service_name for e in self._items}
        total_services = len(services)

        # Frequency distribution
        by_freq: dict[str, int] = {}
        for e in self._items:
            key = e.frequency.value
            by_freq[key] = by_freq.get(key, 0) + 1

        # Health distribution
        scores = self.detect_cadence_health()
        by_health: dict[str, int] = {}
        total_score = 0.0
        for s in scores:
            key = s.health.value
            by_health[key] = by_health.get(key, 0) + 1
            total_score += s.score
        avg_score = round(total_score / len(scores), 2) if scores else 0.0

        # Recommendations
        recs: list[str] = []
        stalled = by_health.get(
            CadenceHealth.STALLED.value,
            0,
        )
        poor = by_health.get(CadenceHealth.POOR.value, 0)
        if stalled > 0:
            recs.append(
                f"{stalled} service(s) have stalled cadence — investigate deployment blockers"
            )
        if poor > 0:
            recs.append(f"{poor} service(s) have poor cadence — review CI/CD pipeline health")

        rollback_count = sum(1 for e in self._items if e.rollback)
        if rollback_count > 0 and total > 0:
            rb_rate = round(rollback_count / total * 100, 1)
            recs.append(f"Rollback rate is {rb_rate}% — analyze root causes")

        weekend = sum(1 for e in self._items if e.time_slot == TimeSlot.WEEKEND)
        if weekend > total * 0.2 and total > 0:
            recs.append("High weekend deployment rate — consider shifting to business hours")

        return CadenceReport(
            total_deployments=total,
            total_services=total_services,
            avg_frequency_score=avg_score,
            by_frequency=by_freq,
            by_health=by_health,
            recommendations=recs,
        )

    def clear_data(self) -> None:
        """Clear all stored data."""
        self._items.clear()
        self._scores.clear()
        logger.info("deployment_cadence.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        services: set[str] = set()
        teams: set[str] = set()
        envs: dict[str, int] = {}
        success_count = 0
        for e in self._items:
            services.add(e.service_name)
            if e.team:
                teams.add(e.team)
            envs[e.environment] = envs.get(e.environment, 0) + 1
            if e.is_success:
                success_count += 1
        total = len(self._items)
        return {
            "total_deployments": total,
            "unique_services": len(services),
            "unique_teams": len(teams),
            "success_rate": (round(success_count / total, 4) if total else 0.0),
            "environment_distribution": envs,
        }
