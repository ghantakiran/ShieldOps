"""Alert grouping engine for correlating related alerts into actionable groups.

Groups related alerts by fingerprint, time window, service affinity, or
label matching to reduce alert fatigue and surface correlated incidents.
"""

from __future__ import annotations

import enum
import hashlib
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class GroupStatus(enum.StrEnum):
    OPEN = "open"
    MERGED = "merged"
    RESOLVED = "resolved"


class GroupingStrategy(enum.StrEnum):
    FINGERPRINT = "fingerprint"
    TIME_WINDOW = "time_window"
    SERVICE_AFFINITY = "service_affinity"
    LABEL_MATCH = "label_match"


# -- Models --------------------------------------------------------------------


class AlertFingerprint(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    alert_name: str
    service: str = ""
    labels: dict[str, str] = Field(default_factory=dict)
    fingerprint: str
    received_at: float = Field(default_factory=time.time)


class AlertGroup(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    strategy: GroupingStrategy
    fingerprint: str = ""
    alerts: list[str] = Field(default_factory=list)
    status: GroupStatus = GroupStatus.OPEN
    service: str = ""
    created_at: float = Field(default_factory=time.time)
    resolved_at: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GroupingRule(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    strategy: GroupingStrategy
    match_labels: dict[str, str] = Field(default_factory=dict)
    service_pattern: str = ""
    window_seconds: int = 300
    priority: int = 0
    created_at: float = Field(default_factory=time.time)


# -- Engine --------------------------------------------------------------------


class AlertGroupingEngine:
    """Group related alerts to reduce noise and surface correlated incidents.

    Parameters
    ----------
    window_seconds:
        Default time window for grouping related alerts.
    max_groups:
        Maximum alert groups to retain.
    """

    def __init__(
        self,
        window_seconds: int = 300,
        max_groups: int = 5000,
    ) -> None:
        self._alerts: dict[str, AlertFingerprint] = {}
        self._groups: dict[str, AlertGroup] = {}
        self._rules: dict[str, GroupingRule] = {}
        self._window_seconds = window_seconds
        self._max_groups = max_groups

    def ingest_alert(
        self,
        alert_name: str,
        service: str = "",
        labels: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        alert_labels = labels or {}
        fingerprint = self._compute_fingerprint(alert_name, service, alert_labels)

        alert = AlertFingerprint(
            alert_name=alert_name,
            service=service,
            labels=alert_labels,
            fingerprint=fingerprint,
        )
        self._alerts[alert.id] = alert

        # Find existing open group with same fingerprint within window
        now = time.time()
        matched_group: AlertGroup | None = None
        for group in self._groups.values():
            if group.status != GroupStatus.OPEN:
                continue
            if group.fingerprint == fingerprint and (
                (now - group.created_at) <= self._window_seconds
            ):
                matched_group = group
                break

        new_group = False
        if matched_group is not None:
            matched_group.alerts.append(alert.id)
            group_id = matched_group.id
        else:
            if len(self._groups) >= self._max_groups:
                raise ValueError(f"Maximum groups limit reached: {self._max_groups}")
            group = AlertGroup(
                name=f"Group: {alert_name}",
                strategy=GroupingStrategy.FINGERPRINT,
                fingerprint=fingerprint,
                alerts=[alert.id],
                service=service,
            )
            self._groups[group.id] = group
            group_id = group.id
            new_group = True

        logger.info(
            "alert_ingested",
            alert_id=alert.id,
            group_id=group_id,
            new_group=new_group,
        )
        return {
            "alert_id": alert.id,
            "group_id": group_id,
            "new_group": new_group,
        }

    def create_rule(
        self,
        name: str,
        strategy: GroupingStrategy,
        match_labels: dict[str, str] | None = None,
        service_pattern: str = "",
        window_seconds: int = 300,
        priority: int = 0,
    ) -> GroupingRule:
        rule = GroupingRule(
            name=name,
            strategy=strategy,
            match_labels=match_labels or {},
            service_pattern=service_pattern,
            window_seconds=window_seconds,
            priority=priority,
        )
        self._rules[rule.id] = rule
        logger.info("grouping_rule_created", rule_id=rule.id, name=name)
        return rule

    def get_group(self, group_id: str) -> AlertGroup | None:
        return self._groups.get(group_id)

    def list_groups(
        self,
        status: GroupStatus | None = None,
    ) -> list[AlertGroup]:
        groups = list(self._groups.values())
        if status:
            groups = [g for g in groups if g.status == status]
        return groups

    def merge_groups(self, group_ids: list[str]) -> AlertGroup | None:
        if len(group_ids) < 2:
            raise ValueError("At least 2 group IDs required for merge")
        groups = [self._groups.get(gid) for gid in group_ids]
        valid_groups = [g for g in groups if g is not None]
        if len(valid_groups) < 2:
            return None

        primary = valid_groups[0]
        for secondary in valid_groups[1:]:
            primary.alerts.extend(secondary.alerts)
            secondary.status = GroupStatus.MERGED
            secondary.metadata["merged_into"] = primary.id

        logger.info(
            "groups_merged",
            primary_id=primary.id,
            merged_count=len(valid_groups) - 1,
        )
        return primary

    def resolve_group(self, group_id: str) -> AlertGroup | None:
        group = self._groups.get(group_id)
        if group is None:
            return None
        group.status = GroupStatus.RESOLVED
        group.resolved_at = time.time()
        logger.info("group_resolved", group_id=group_id)
        return group

    def list_rules(self) -> list[GroupingRule]:
        return list(self._rules.values())

    def delete_rule(self, rule_id: str) -> bool:
        return self._rules.pop(rule_id, None) is not None

    def get_stats(self) -> dict[str, Any]:
        open_groups = sum(1 for g in self._groups.values() if g.status == GroupStatus.OPEN)
        merged_groups = sum(1 for g in self._groups.values() if g.status == GroupStatus.MERGED)
        resolved_groups = sum(1 for g in self._groups.values() if g.status == GroupStatus.RESOLVED)
        return {
            "total_alerts": len(self._alerts),
            "total_groups": len(self._groups),
            "open_groups": open_groups,
            "merged_groups": merged_groups,
            "resolved_groups": resolved_groups,
            "total_rules": len(self._rules),
        }

    @staticmethod
    def _compute_fingerprint(
        alert_name: str,
        service: str,
        labels: dict[str, str],
    ) -> str:
        sorted_labels = sorted(labels.items())
        raw = f"{alert_name}|{service}|{sorted_labels}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
