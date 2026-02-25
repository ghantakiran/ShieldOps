"""Compliance Evidence Freshness Monitor — monitor staleness of collected compliance evidence."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FreshnessStatus(StrEnum):
    CURRENT = "current"
    AGING = "aging"
    STALE = "stale"
    EXPIRED = "expired"
    MISSING = "missing"


class EvidenceCategory(StrEnum):
    ACCESS_REVIEW = "access_review"
    VULNERABILITY_SCAN = "vulnerability_scan"
    POLICY_ATTESTATION = "policy_attestation"
    CONFIGURATION_AUDIT = "configuration_audit"
    PENETRATION_TEST = "penetration_test"


class AuditUrgency(StrEnum):
    ROUTINE = "routine"
    UPCOMING = "upcoming"
    IMMINENT = "imminent"
    OVERDUE = "overdue"
    BLOCKED = "blocked"


# --- Models ---


class FreshnessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evidence_id: str = ""
    category: EvidenceCategory = EvidenceCategory.ACCESS_REVIEW
    control_id: str = ""
    status: FreshnessStatus = FreshnessStatus.CURRENT
    urgency: AuditUrgency = AuditUrgency.ROUTINE
    collected_at: float = 0.0
    expires_at: float = 0.0
    days_until_expiry: int = 0
    framework: str = ""
    owner: str = ""
    created_at: float = Field(default_factory=time.time)


class FreshnessGap(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: EvidenceCategory = EvidenceCategory.ACCESS_REVIEW
    control_id: str = ""
    expected_frequency_days: int = 90
    actual_gap_days: int = 0
    severity: str = "low"
    created_at: float = Field(default_factory=time.time)


class FreshnessReport(BaseModel):
    total_evidence: int = 0
    current_count: int = 0
    stale_count: int = 0
    expired_count: int = 0
    freshness_score_pct: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EvidenceFreshnessMonitor:
    """Monitor staleness of collected compliance evidence."""

    def __init__(
        self,
        max_records: int = 200000,
        stale_days: int = 90,
    ) -> None:
        self._max_records = max_records
        self._stale_days = stale_days
        self._records: list[FreshnessRecord] = []
        self._gaps: list[FreshnessGap] = []
        logger.info(
            "evidence_freshness.initialized",
            max_records=max_records,
            stale_days=stale_days,
        )

    # -- internal helpers ------------------------------------------------

    def _compute_status(self, days_until_expiry: int, expires_at: float) -> FreshnessStatus:
        if expires_at == 0.0:
            return FreshnessStatus.MISSING
        if days_until_expiry <= 0:
            return FreshnessStatus.EXPIRED
        if days_until_expiry > self._stale_days:
            return FreshnessStatus.CURRENT
        if days_until_expiry > self._stale_days // 2:
            return FreshnessStatus.AGING
        return FreshnessStatus.STALE

    def _status_to_urgency(self, status: FreshnessStatus) -> AuditUrgency:
        mapping = {
            FreshnessStatus.CURRENT: AuditUrgency.ROUTINE,
            FreshnessStatus.AGING: AuditUrgency.UPCOMING,
            FreshnessStatus.STALE: AuditUrgency.IMMINENT,
            FreshnessStatus.EXPIRED: AuditUrgency.OVERDUE,
            FreshnessStatus.MISSING: AuditUrgency.BLOCKED,
        }
        return mapping.get(status, AuditUrgency.ROUTINE)

    # -- record / get / list ---------------------------------------------

    def record_evidence(
        self,
        evidence_id: str,
        category: EvidenceCategory,
        control_id: str,
        collected_at: float,
        expires_at: float,
        framework: str = "",
        owner: str = "",
    ) -> FreshnessRecord:
        now = time.time()
        days_until_expiry = int((expires_at - now) / 86400) if expires_at > 0 else 0
        status = self._compute_status(days_until_expiry, expires_at)
        urgency = self._status_to_urgency(status)
        record = FreshnessRecord(
            evidence_id=evidence_id,
            category=category,
            control_id=control_id,
            status=status,
            urgency=urgency,
            collected_at=collected_at,
            expires_at=expires_at,
            days_until_expiry=days_until_expiry,
            framework=framework,
            owner=owner,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "evidence_freshness.evidence_recorded",
            record_id=record.id,
            evidence_id=evidence_id,
            status=status.value,
        )
        return record

    def get_evidence(self, record_id: str) -> FreshnessRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_evidence(
        self,
        category: EvidenceCategory | None = None,
        status: FreshnessStatus | None = None,
        limit: int = 50,
    ) -> list[FreshnessRecord]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.category == category]
        if status is not None:
            results = [r for r in results if r.status == status]
        return results[-limit:]

    # -- domain operations -----------------------------------------------

    def assess_freshness(self, record_id: str) -> dict[str, Any]:
        """Re-assess a specific record's freshness status."""
        record = self.get_evidence(record_id)
        if record is None:
            return {"found": False, "record_id": record_id}
        now = time.time()
        days_until_expiry = int((record.expires_at - now) / 86400) if record.expires_at > 0 else 0
        new_status = self._compute_status(days_until_expiry, record.expires_at)
        new_urgency = self._status_to_urgency(new_status)
        previous_status = record.status.value
        record.days_until_expiry = days_until_expiry
        record.status = new_status
        record.urgency = new_urgency
        logger.info(
            "evidence_freshness.freshness_assessed",
            record_id=record_id,
            previous=previous_status,
            new_status=new_status.value,
        )
        return {
            "found": True,
            "record_id": record_id,
            "evidence_id": record.evidence_id,
            "previous_status": previous_status,
            "new_status": new_status.value,
            "urgency": new_urgency.value,
            "days_until_expiry": days_until_expiry,
        }

    def detect_gaps(self) -> list[FreshnessGap]:
        """Find controls missing evidence or with freshness gaps."""
        control_records: dict[str, list[FreshnessRecord]] = {}
        for r in self._records:
            control_records.setdefault(r.control_id, []).append(r)
        gaps: list[FreshnessGap] = []
        for control_id, records in control_records.items():
            missing = [r for r in records if r.status == FreshnessStatus.MISSING]
            expired = [r for r in records if r.status == FreshnessStatus.EXPIRED]
            stale = [r for r in records if r.status == FreshnessStatus.STALE]
            if missing:
                sev, gap_days = "critical", 0
                cat = missing[0].category
            elif expired:
                gap_days = abs(min(r.days_until_expiry for r in expired))
                sev = "high" if gap_days > self._stale_days else "medium"
                cat = expired[0].category
            elif stale:
                gap_days = self._stale_days - min(r.days_until_expiry for r in stale)
                sev, cat = "low", stale[0].category
            else:
                continue
            gaps.append(
                FreshnessGap(
                    category=cat,
                    control_id=control_id,
                    expected_frequency_days=self._stale_days,
                    actual_gap_days=gap_days,
                    severity=sev,
                )
            )
        self._gaps = gaps
        logger.info(
            "evidence_freshness.gaps_detected",
            gap_count=len(gaps),
        )
        return gaps

    def calculate_freshness_score(self) -> dict[str, Any]:
        """Percentage of evidence that is CURRENT."""
        if not self._records:
            return {
                "score_pct": 0.0,
                "total": 0,
                "current": 0,
            }
        current_count = sum(1 for r in self._records if r.status == FreshnessStatus.CURRENT)
        score = round(current_count / len(self._records) * 100, 2)
        return {
            "score_pct": score,
            "total": len(self._records),
            "current": current_count,
            "non_current": len(self._records) - current_count,
        }

    def identify_expiring_soon(self, days: int = 30) -> list[dict[str, Any]]:
        """Evidence expiring within N days."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if 0 < r.days_until_expiry <= days:
                results.append(
                    {
                        "record_id": r.id,
                        "evidence_id": r.evidence_id,
                        "control_id": r.control_id,
                        "category": r.category.value,
                        "days_until_expiry": r.days_until_expiry,
                        "status": r.status.value,
                        "owner": r.owner,
                    }
                )
        results.sort(key=lambda x: x["days_until_expiry"])
        return results

    def rank_by_urgency(self) -> list[dict[str, Any]]:
        """Sort records by urgency (BLOCKED first)."""
        urgency_order = {
            AuditUrgency.BLOCKED: 0,
            AuditUrgency.OVERDUE: 1,
            AuditUrgency.IMMINENT: 2,
            AuditUrgency.UPCOMING: 3,
            AuditUrgency.ROUTINE: 4,
        }
        sorted_records = sorted(
            self._records,
            key=lambda r: urgency_order.get(r.urgency, 5),
        )
        return [
            {
                "record_id": r.id,
                "evidence_id": r.evidence_id,
                "control_id": r.control_id,
                "category": r.category.value,
                "urgency": r.urgency.value,
                "status": r.status.value,
                "days_until_expiry": r.days_until_expiry,
            }
            for r in sorted_records
        ]

    # -- report / stats --------------------------------------------------

    def generate_freshness_report(self) -> FreshnessReport:
        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
        current_count = by_status.get(FreshnessStatus.CURRENT.value, 0)
        stale_count = by_status.get(FreshnessStatus.STALE.value, 0)
        expired_count = by_status.get(FreshnessStatus.EXPIRED.value, 0)
        score = self.calculate_freshness_score()
        detected_gaps = self.detect_gaps()
        gap_descriptions = [
            f"{g.control_id} ({g.category.value}): {g.severity}" for g in detected_gaps[:10]
        ]
        recs: list[str] = []
        if expired_count > 0:
            recs.append(f"{expired_count} evidence item(s) have expired")
        if stale_count > 0:
            recs.append(f"{stale_count} evidence item(s) are stale")
        missing_count = by_status.get(FreshnessStatus.MISSING.value, 0)
        if missing_count > 0:
            recs.append(f"{missing_count} evidence item(s) are missing")
        if not recs:
            recs.append("All compliance evidence is current")
        return FreshnessReport(
            total_evidence=len(self._records),
            current_count=current_count,
            stale_count=stale_count,
            expired_count=expired_count,
            freshness_score_pct=score["score_pct"],
            by_status=by_status,
            by_category=by_category,
            gaps=gap_descriptions,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._gaps.clear()
        logger.info("evidence_freshness.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_gaps": len(self._gaps),
            "stale_days": self._stale_days,
            "status_distribution": status_dist,
            "unique_controls": len({r.control_id for r in self._records}),
        }
