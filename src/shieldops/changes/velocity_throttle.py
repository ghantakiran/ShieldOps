"""Change Velocity Throttle — monitor change velocity and enforce throttling."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ThrottleAction(StrEnum):
    ALLOW = "allow"
    WARN = "warn"
    DELAY = "delay"
    REQUIRE_APPROVAL = "require_approval"
    BLOCK = "block"


class VelocityZone(StrEnum):
    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"
    LOCKDOWN = "lockdown"


class ChangeScope(StrEnum):
    SERVICE = "service"
    TEAM = "team"
    ENVIRONMENT = "environment"
    REGION = "region"
    GLOBAL = "global"


# --- Models ---


class ChangeVelocityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    team: str = ""
    environment: str = "production"
    change_type: str = ""
    action_taken: ThrottleAction = ThrottleAction.ALLOW
    zone: VelocityZone = VelocityZone.GREEN
    velocity_per_hour: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ThrottlePolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    scope: ChangeScope = ChangeScope.SERVICE
    max_changes_per_hour: int = 10
    warn_at: int = 6
    delay_at: int = 8
    block_at: int = 12
    created_at: float = Field(default_factory=time.time)


class VelocityThrottleReport(BaseModel):
    total_records: int = 0
    total_policies: int = 0
    by_action: dict[str, int] = Field(default_factory=dict)
    by_zone: dict[str, int] = Field(default_factory=dict)
    spike_count: int = 0
    avg_velocity_per_hour: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeVelocityThrottle:
    """Monitor real-time change velocity and enforce throttling."""

    def __init__(
        self,
        max_records: int = 200000,
        max_changes_per_hour: int = 10,
    ) -> None:
        self._max_records = max_records
        self._max_changes_per_hour = max_changes_per_hour
        self._records: list[ChangeVelocityRecord] = []
        self._policies: list[ThrottlePolicy] = []
        logger.info(
            "velocity_throttle.initialized",
            max_records=max_records,
            max_changes_per_hour=max_changes_per_hour,
        )

    # -- internal helpers ------------------------------------------------

    def _velocity_to_zone(self, velocity: float) -> VelocityZone:
        ratio = velocity / self._max_changes_per_hour if self._max_changes_per_hour > 0 else 0
        if ratio < 0.5:
            return VelocityZone.GREEN
        if ratio < 0.75:
            return VelocityZone.YELLOW
        if ratio < 1.0:
            return VelocityZone.ORANGE
        if ratio < 1.5:
            return VelocityZone.RED
        return VelocityZone.LOCKDOWN

    def _zone_to_action(self, zone: VelocityZone) -> ThrottleAction:
        return {
            VelocityZone.GREEN: ThrottleAction.ALLOW,
            VelocityZone.YELLOW: ThrottleAction.WARN,
            VelocityZone.ORANGE: ThrottleAction.DELAY,
            VelocityZone.RED: ThrottleAction.REQUIRE_APPROVAL,
            VelocityZone.LOCKDOWN: ThrottleAction.BLOCK,
        }.get(zone, ThrottleAction.ALLOW)

    # -- register / get / list policies -----------------------------------

    def register_policy(
        self,
        name: str,
        scope: ChangeScope = ChangeScope.SERVICE,
        max_changes_per_hour: int = 10,
        warn_at: int = 6,
        delay_at: int = 8,
        block_at: int = 12,
    ) -> ThrottlePolicy:
        policy = ThrottlePolicy(
            name=name,
            scope=scope,
            max_changes_per_hour=max_changes_per_hour,
            warn_at=warn_at,
            delay_at=delay_at,
            block_at=block_at,
        )
        self._policies.append(policy)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "velocity_throttle.policy_registered",
            policy_id=policy.id,
            name=name,
            scope=scope.value,
        )
        return policy

    def get_policy(self, policy_id: str) -> ThrottlePolicy | None:
        for p in self._policies:
            if p.id == policy_id:
                return p
        return None

    def list_policies(
        self,
        scope: ChangeScope | None = None,
        limit: int = 50,
    ) -> list[ThrottlePolicy]:
        results = list(self._policies)
        if scope is not None:
            results = [p for p in results if p.scope == scope]
        return results[-limit:]

    # -- domain operations -----------------------------------------------

    def evaluate_change(
        self,
        service: str,
        team: str = "",
        environment: str = "production",
        change_type: str = "",
    ) -> ChangeVelocityRecord:
        """Evaluate whether a change should be allowed based on current velocity."""
        # Calculate current velocity for this service in last hour
        now = time.time()
        hour_ago = now - 3600
        recent = [r for r in self._records if r.service == service and r.created_at > hour_ago]
        velocity = len(recent) + 1  # +1 for the current change
        zone = self._velocity_to_zone(float(velocity))
        action = self._zone_to_action(zone)

        record = ChangeVelocityRecord(
            service=service,
            team=team,
            environment=environment,
            change_type=change_type,
            action_taken=action,
            zone=zone,
            velocity_per_hour=float(velocity),
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "velocity_throttle.change_evaluated",
            record_id=record.id,
            service=service,
            velocity=velocity,
            zone=zone.value,
            action=action.value,
        )
        return record

    def get_current_velocity(self, service: str) -> dict[str, Any]:
        """Get current velocity for a service."""
        now = time.time()
        hour_ago = now - 3600
        recent = [r for r in self._records if r.service == service and r.created_at > hour_ago]
        velocity = len(recent)
        zone = self._velocity_to_zone(float(velocity))
        return {
            "service": service,
            "velocity_per_hour": velocity,
            "zone": zone.value,
            "max_per_hour": self._max_changes_per_hour,
            "utilization_pct": (
                round(velocity / self._max_changes_per_hour * 100, 2)
                if self._max_changes_per_hour > 0
                else 0.0
            ),
        }

    def get_current_zone(self, service: str) -> dict[str, Any]:
        """Get current throttle zone for a service."""
        velocity_info = self.get_current_velocity(service)
        zone = VelocityZone(velocity_info["zone"])
        action = self._zone_to_action(zone)
        return {
            "service": service,
            "zone": zone.value,
            "action": action.value,
            "velocity_per_hour": velocity_info["velocity_per_hour"],
        }

    def list_records(
        self,
        service: str | None = None,
        zone: VelocityZone | None = None,
        limit: int = 50,
    ) -> list[ChangeVelocityRecord]:
        results = list(self._records)
        if service is not None:
            results = [r for r in results if r.service == service]
        if zone is not None:
            results = [r for r in results if r.zone == zone]
        return results[-limit:]

    def identify_velocity_spikes(self) -> list[dict[str, Any]]:
        """Find services with velocity spikes (above max_changes_per_hour)."""
        service_velocity: dict[str, int] = {}
        now = time.time()
        hour_ago = now - 3600
        for r in self._records:
            if r.created_at > hour_ago:
                service_velocity[r.service] = service_velocity.get(r.service, 0) + 1
        spikes: list[dict[str, Any]] = []
        for svc, vel in service_velocity.items():
            if vel > self._max_changes_per_hour:
                spikes.append(
                    {
                        "service": svc,
                        "velocity_per_hour": vel,
                        "excess": vel - self._max_changes_per_hour,
                        "zone": self._velocity_to_zone(float(vel)).value,
                    }
                )
        spikes.sort(key=lambda x: x["velocity_per_hour"], reverse=True)
        return spikes

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> VelocityThrottleReport:
        by_action: dict[str, int] = {}
        by_zone: dict[str, int] = {}
        total_vel = 0.0
        for r in self._records:
            by_action[r.action_taken.value] = by_action.get(r.action_taken.value, 0) + 1
            by_zone[r.zone.value] = by_zone.get(r.zone.value, 0) + 1
            total_vel += r.velocity_per_hour
        avg_vel = round(total_vel / len(self._records), 2) if self._records else 0.0
        spikes = self.identify_velocity_spikes()
        recs: list[str] = []
        blocked = by_action.get(ThrottleAction.BLOCK.value, 0)
        if blocked > 0:
            recs.append(f"{blocked} change(s) blocked due to velocity")
        if spikes:
            recs.append(f"{len(spikes)} service(s) experiencing velocity spikes")
        lockdown = by_zone.get(VelocityZone.LOCKDOWN.value, 0)
        if lockdown > 0:
            recs.append(f"{lockdown} lockdown event(s) triggered")
        if not recs:
            recs.append("Change velocity within normal parameters")
        return VelocityThrottleReport(
            total_records=len(self._records),
            total_policies=len(self._policies),
            by_action=by_action,
            by_zone=by_zone,
            spike_count=len(spikes),
            avg_velocity_per_hour=avg_vel,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._policies.clear()
        logger.info("velocity_throttle.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        zone_dist: dict[str, int] = {}
        for r in self._records:
            key = r.zone.value
            zone_dist[key] = zone_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_policies": len(self._policies),
            "max_changes_per_hour": self._max_changes_per_hour,
            "zone_distribution": zone_dist,
            "unique_services": len({r.service for r in self._records}),
        }
