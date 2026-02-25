"""Config Change Tracker — track configuration changes with diff, approval, and rollback."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ChangeScope(StrEnum):
    APPLICATION = "application"
    INFRASTRUCTURE = "infrastructure"
    DATABASE = "database"
    NETWORK = "network"
    SECURITY = "security"


class ChangeApproval(StrEnum):
    AUTO_APPROVED = "auto_approved"
    PEER_REVIEWED = "peer_reviewed"
    MANAGER_APPROVED = "manager_approved"
    EMERGENCY_BYPASS = "emergency_bypass"
    PENDING = "pending"


class ChangeImpact(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# --- Models ---


class ConfigChange(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    scope: ChangeScope = ChangeScope.APPLICATION
    key: str = ""
    old_value: str = ""
    new_value: str = ""
    author: str = ""
    approval: ChangeApproval = ChangeApproval.PENDING
    impact: ChangeImpact = ChangeImpact.NONE
    is_rolled_back: bool = False
    changed_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class ChangeAuditTrail(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_id: str = ""
    action: str = ""
    actor: str = ""
    reason: str = ""
    performed_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class ChangeTrackerReport(BaseModel):
    total_changes: int = 0
    total_rollbacks: int = 0
    rollback_rate_pct: float = 0.0
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_approval: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    high_impact_changes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ConfigChangeTracker:
    """Track all configuration changes across services."""

    def __init__(
        self,
        max_changes: int = 500000,
        high_impact_alert_enabled: bool = True,
    ) -> None:
        self._max_changes = max_changes
        self._high_impact_alert_enabled = high_impact_alert_enabled
        self._items: list[ConfigChange] = []
        self._audit_trails: list[ChangeAuditTrail] = []
        logger.info(
            "config_change_tracker.initialized",
            max_changes=max_changes,
            high_impact_alert_enabled=high_impact_alert_enabled,
        )

    def record_change(
        self,
        service_name: str,
        scope: ChangeScope,
        key: str,
        old_value: str,
        new_value: str,
        author: str = "",
        approval: ChangeApproval = ChangeApproval.PENDING,
        impact: ChangeImpact = ChangeImpact.NONE,
        **kw: Any,
    ) -> ConfigChange:
        """Record a configuration change."""
        change = ConfigChange(
            service_name=service_name,
            scope=scope,
            key=key,
            old_value=old_value,
            new_value=new_value,
            author=author,
            approval=approval,
            impact=impact,
            **kw,
        )
        self._items.append(change)
        if len(self._items) > self._max_changes:
            self._items = self._items[-self._max_changes :]
        logger.info(
            "config_change_tracker.change_recorded",
            change_id=change.id,
            service_name=service_name,
            key=key,
            impact=impact,
        )
        return change

    def get_change(self, change_id: str) -> ConfigChange | None:
        """Retrieve a single change by ID."""
        for c in self._items:
            if c.id == change_id:
                return c
        return None

    def list_changes(
        self,
        service_name: str | None = None,
        scope: ChangeScope | None = None,
        limit: int = 50,
    ) -> list[ConfigChange]:
        """List changes with optional filtering."""
        results = list(self._items)
        if service_name is not None:
            results = [c for c in results if c.service_name == service_name]
        if scope is not None:
            results = [c for c in results if c.scope == scope]
        return results[-limit:]

    def rollback_change(
        self,
        change_id: str,
        actor: str,
        reason: str,
    ) -> ConfigChange | None:
        """Rollback a change and record audit trail."""
        change = self.get_change(change_id)
        if change is None:
            return None
        change.is_rolled_back = True
        self.audit_change(
            change_id=change_id,
            action="rollback",
            actor=actor,
            reason=reason,
        )
        logger.info(
            "config_change_tracker.change_rolled_back",
            change_id=change_id,
            actor=actor,
        )
        return change

    def audit_change(
        self,
        change_id: str,
        action: str,
        actor: str,
        reason: str,
    ) -> ChangeAuditTrail:
        """Record an audit trail entry for a change."""
        trail = ChangeAuditTrail(
            change_id=change_id,
            action=action,
            actor=actor,
            reason=reason,
        )
        self._audit_trails.append(trail)
        if len(self._audit_trails) > self._max_changes:
            self._audit_trails = self._audit_trails[-self._max_changes :]
        logger.info(
            "config_change_tracker.audit_recorded",
            change_id=change_id,
            action=action,
            actor=actor,
        )
        return trail

    def calculate_rollback_rate(self) -> float:
        """Calculate the percentage of changes that were rolled back."""
        if not self._items:
            return 0.0
        rolled = sum(1 for c in self._items if c.is_rolled_back)
        return round(rolled / len(self._items) * 100, 2)

    def detect_unauthorized_changes(self) -> list[ConfigChange]:
        """Find changes with EMERGENCY_BYPASS or PENDING approval."""
        return [
            c
            for c in self._items
            if c.approval
            in (
                ChangeApproval.EMERGENCY_BYPASS,
                ChangeApproval.PENDING,
            )
        ]

    def find_correlated_changes(
        self,
        time_window_minutes: int = 30,
    ) -> list[list[ConfigChange]]:
        """Group changes that occurred within the time window.

        Returns clusters of changes with overlapping time ranges.
        """
        if not self._items:
            return []

        window_seconds = time_window_minutes * 60
        sorted_items = sorted(self._items, key=lambda c: c.changed_at)

        clusters: list[list[ConfigChange]] = []
        current_cluster: list[ConfigChange] = [sorted_items[0]]

        for change in sorted_items[1:]:
            last = current_cluster[-1]
            if change.changed_at - last.changed_at <= window_seconds:
                current_cluster.append(change)
            else:
                if len(current_cluster) > 1:
                    clusters.append(current_cluster)
                current_cluster = [change]

        if len(current_cluster) > 1:
            clusters.append(current_cluster)

        logger.info(
            "config_change_tracker.correlations_found",
            cluster_count=len(clusters),
            window_minutes=time_window_minutes,
        )
        return clusters

    def generate_tracker_report(self) -> ChangeTrackerReport:
        """Generate a comprehensive tracker report."""
        total = len(self._items)
        rolled = sum(1 for c in self._items if c.is_rolled_back)
        rate = round(rolled / total * 100, 2) if total else 0.0

        by_scope: dict[str, int] = {}
        by_approval: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        high_ids: list[str] = []

        for c in self._items:
            by_scope[c.scope.value] = by_scope.get(c.scope.value, 0) + 1
            by_approval[c.approval.value] = by_approval.get(c.approval.value, 0) + 1
            by_impact[c.impact.value] = by_impact.get(c.impact.value, 0) + 1
            if c.impact in (ChangeImpact.HIGH, ChangeImpact.CRITICAL):
                high_ids.append(c.id)

        recommendations: list[str] = []
        if rate > 10:
            recommendations.append(
                f"Rollback rate {rate:.1f}% exceeds 10% threshold"
                " — review change validation processes"
            )
        unauthorized = len(self.detect_unauthorized_changes())
        if unauthorized > 0:
            recommendations.append(
                f"{unauthorized} change(s) lack proper approval — enforce approval workflow"
            )
        if high_ids:
            recommendations.append(
                f"{len(high_ids)} high/critical impact change(s) detected — ensure peer review"
            )

        report = ChangeTrackerReport(
            total_changes=total,
            total_rollbacks=rolled,
            rollback_rate_pct=rate,
            by_scope=by_scope,
            by_approval=by_approval,
            by_impact=by_impact,
            high_impact_changes=high_ids,
            recommendations=recommendations,
        )
        logger.info(
            "config_change_tracker.report_generated",
            total_changes=total,
            total_rollbacks=rolled,
            rollback_rate_pct=rate,
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored changes and audit trails."""
        self._items.clear()
        self._audit_trails.clear()
        logger.info("config_change_tracker.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        scope_counts: dict[str, int] = {}
        impact_counts: dict[str, int] = {}
        approval_counts: dict[str, int] = {}
        for c in self._items:
            scope_counts[c.scope.value] = scope_counts.get(c.scope.value, 0) + 1
            impact_counts[c.impact.value] = impact_counts.get(c.impact.value, 0) + 1
            approval_counts[c.approval.value] = approval_counts.get(c.approval.value, 0) + 1
        return {
            "total_changes": len(self._items),
            "total_audit_trails": len(self._audit_trails),
            "scope_distribution": scope_counts,
            "impact_distribution": impact_counts,
            "approval_distribution": approval_counts,
            "max_changes": self._max_changes,
            "high_impact_alert_enabled": (self._high_impact_alert_enabled),
        }
