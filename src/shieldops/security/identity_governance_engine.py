"""Identity Governance Engine — govern identities and access lifecycle."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AccessLevel(StrEnum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    SERVICE_ACCOUNT = "service_account"


class ReviewDecision(StrEnum):
    APPROVED = "approved"
    REVOKED = "revoked"
    FLAGGED = "flagged"
    PENDING = "pending"
    EXPIRED = "expired"


class PrivilegeStatus(StrEnum):
    ACTIVE = "active"
    EXCESSIVE = "excessive"
    DORMANT = "dormant"
    COMPLIANT = "compliant"
    REVOKED = "revoked"


# --- Models ---


class AccessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    resource: str = ""
    access_level: AccessLevel = AccessLevel.READ
    decision: ReviewDecision = ReviewDecision.PENDING
    privilege_status: PrivilegeStatus = PrivilegeStatus.ACTIVE
    last_used_days: int = 0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class GovernanceMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class GovernanceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    excessive_count: int = 0
    dormant_count: int = 0
    by_access_level: dict[str, int] = Field(default_factory=dict)
    by_decision: dict[str, int] = Field(default_factory=dict)
    by_privilege: dict[str, int] = Field(default_factory=dict)
    top_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IdentityGovernanceEngine:
    """Govern identities and access lifecycle."""

    def __init__(
        self,
        max_records: int = 200000,
        dormant_threshold_days: int = 90,
    ) -> None:
        self._max_records = max_records
        self._dormant_threshold = dormant_threshold_days
        self._records: list[AccessRecord] = []
        self._metrics: list[GovernanceMetric] = []
        logger.info(
            "identity_governance_engine.initialized",
            max_records=max_records,
            dormant_threshold_days=dormant_threshold_days,
        )

    def review_access(
        self,
        user_id: str,
        resource: str,
        access_level: AccessLevel = AccessLevel.READ,
        last_used_days: int = 0,
        service: str = "",
        team: str = "",
    ) -> AccessRecord:
        """Review an access grant and record it."""
        if last_used_days > self._dormant_threshold:
            privilege_status = PrivilegeStatus.DORMANT
            decision = ReviewDecision.FLAGGED
        elif access_level in (AccessLevel.ADMIN, AccessLevel.SUPER_ADMIN):
            privilege_status = PrivilegeStatus.EXCESSIVE
            decision = ReviewDecision.FLAGGED
        else:
            privilege_status = PrivilegeStatus.ACTIVE
            decision = ReviewDecision.APPROVED
        record = AccessRecord(
            user_id=user_id,
            resource=resource,
            access_level=access_level,
            decision=decision,
            privilege_status=privilege_status,
            last_used_days=last_used_days,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "identity_governance_engine.access_reviewed",
            record_id=record.id,
            user_id=user_id,
            decision=decision.value,
        )
        return record

    def detect_privilege_creep(self) -> list[dict[str, Any]]:
        """Detect users with excessive or dormant privileges."""
        results: list[dict[str, Any]] = []
        user_access: dict[str, list[AccessRecord]] = {}
        for r in self._records:
            user_access.setdefault(r.user_id, []).append(r)
        for user_id, records in user_access.items():
            excessive = sum(1 for r in records if r.privilege_status == PrivilegeStatus.EXCESSIVE)
            dormant = sum(1 for r in records if r.privilege_status == PrivilegeStatus.DORMANT)
            if excessive > 0 or dormant > 0:
                results.append(
                    {
                        "user_id": user_id,
                        "total_access": len(records),
                        "excessive": excessive,
                        "dormant": dormant,
                    }
                )
        return sorted(results, key=lambda x: x["excessive"] + x["dormant"], reverse=True)

    def enforce_least_privilege(self) -> list[dict[str, Any]]:
        """Identify and flag access that violates least privilege."""
        revoked: list[dict[str, Any]] = []
        for r in self._records:
            if r.privilege_status in (PrivilegeStatus.EXCESSIVE, PrivilegeStatus.DORMANT):
                r.decision = ReviewDecision.REVOKED
                r.privilege_status = PrivilegeStatus.REVOKED
                revoked.append(
                    {
                        "record_id": r.id,
                        "user_id": r.user_id,
                        "resource": r.resource,
                        "previous_level": r.access_level.value,
                    }
                )
        logger.info(
            "identity_governance_engine.least_privilege_enforced",
            revoked_count=len(revoked),
        )
        return revoked

    def certify_access(self, record_id: str, approve: bool = True) -> dict[str, Any]:
        """Certify or revoke a specific access record."""
        for r in self._records:
            if r.id == record_id:
                if approve:
                    r.decision = ReviewDecision.APPROVED
                    r.privilege_status = PrivilegeStatus.COMPLIANT
                else:
                    r.decision = ReviewDecision.REVOKED
                    r.privilege_status = PrivilegeStatus.REVOKED
                return {
                    "record_id": record_id,
                    "decision": r.decision.value,
                    "status": r.privilege_status.value,
                }
        return {"record_id": record_id, "error": "not_found"}

    def get_governance_metrics(self) -> dict[str, Any]:
        """Compute governance metrics across all access records."""
        if not self._records:
            return {"total": 0, "excessive_rate": 0.0, "dormant_rate": 0.0}
        excessive = sum(1 for r in self._records if r.privilege_status == PrivilegeStatus.EXCESSIVE)
        dormant = sum(1 for r in self._records if r.privilege_status == PrivilegeStatus.DORMANT)
        total = len(self._records)
        by_level: dict[str, int] = {}
        for r in self._records:
            by_level[r.access_level.value] = by_level.get(r.access_level.value, 0) + 1
        return {
            "total": total,
            "excessive_rate": round(excessive / total * 100, 2),
            "dormant_rate": round(dormant / total * 100, 2),
            "by_access_level": by_level,
        }

    def list_records(
        self,
        access_level: AccessLevel | None = None,
        decision: ReviewDecision | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AccessRecord]:
        """List access records with optional filters."""
        results = list(self._records)
        if access_level is not None:
            results = [r for r in results if r.access_level == access_level]
        if decision is not None:
            results = [r for r in results if r.decision == decision]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def generate_report(self) -> GovernanceReport:
        """Generate a comprehensive governance report."""
        by_level: dict[str, int] = {}
        by_dec: dict[str, int] = {}
        by_priv: dict[str, int] = {}
        for r in self._records:
            by_level[r.access_level.value] = by_level.get(r.access_level.value, 0) + 1
            by_dec[r.decision.value] = by_dec.get(r.decision.value, 0) + 1
            by_priv[r.privilege_status.value] = by_priv.get(r.privilege_status.value, 0) + 1
        excessive = sum(1 for r in self._records if r.privilege_status == PrivilegeStatus.EXCESSIVE)
        dormant = sum(1 for r in self._records if r.privilege_status == PrivilegeStatus.DORMANT)
        issues = [
            f"{r.user_id}:{r.resource}"
            for r in self._records
            if r.privilege_status in (PrivilegeStatus.EXCESSIVE, PrivilegeStatus.DORMANT)
        ][:5]
        recs: list[str] = []
        if excessive:
            recs.append(f"{excessive} excessive privilege(s) detected")
        if dormant:
            recs.append(f"{dormant} dormant access(es) detected")
        if not recs:
            recs.append("Identity governance within healthy range")
        return GovernanceReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            excessive_count=excessive,
            dormant_count=dormant,
            by_access_level=by_level,
            by_decision=by_dec,
            by_privilege=by_priv,
            top_issues=issues,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        dist: dict[str, int] = {}
        for r in self._records:
            key = r.access_level.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "dormant_threshold": self._dormant_threshold,
            "access_level_distribution": dist,
            "unique_users": len({r.user_id for r in self._records}),
            "unique_resources": len({r.resource for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        """Clear all stored data."""
        self._records.clear()
        self._metrics.clear()
        logger.info("identity_governance_engine.cleared")
        return {"status": "cleared"}
