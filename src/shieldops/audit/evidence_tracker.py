"""Audit Evidence Tracker — track evidence collection, identify gaps."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EvidenceType(StrEnum):
    SCREENSHOT = "screenshot"
    LOG_EXPORT = "log_export"
    CONFIG_SNAPSHOT = "config_snapshot"
    APPROVAL_RECORD = "approval_record"
    TEST_RESULT = "test_result"


class EvidenceStatus(StrEnum):
    COLLECTED = "collected"
    VERIFIED = "verified"
    EXPIRED = "expired"
    MISSING = "missing"
    DISPUTED = "disputed"


class AuditFramework(StrEnum):
    SOC2 = "soc2"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    ISO_27001 = "iso_27001"
    GDPR = "gdpr"


# --- Models ---


class EvidenceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    evidence_type: EvidenceType = EvidenceType.SCREENSHOT
    evidence_status: EvidenceStatus = EvidenceStatus.MISSING
    audit_framework: AuditFramework = AuditFramework.SOC2
    completeness_pct: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EvidenceRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    framework_pattern: str = ""
    audit_framework: AuditFramework = AuditFramework.SOC2
    required_count: int = 0
    max_age_days: int = 365
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EvidenceTrackerReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_rules: int = 0
    verified_count: int = 0
    avg_completeness: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_framework: dict[str, int] = Field(default_factory=dict)
    missing_evidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuditEvidenceTracker:
    """Track audit evidence collection, identify missing evidence, detect trends."""

    def __init__(
        self,
        max_records: int = 200000,
        min_completeness_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._min_completeness_pct = min_completeness_pct
        self._records: list[EvidenceRecord] = []
        self._rules: list[EvidenceRule] = []
        logger.info(
            "evidence_tracker.initialized",
            max_records=max_records,
            min_completeness_pct=min_completeness_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_evidence(
        self,
        control_id: str,
        evidence_type: EvidenceType = EvidenceType.SCREENSHOT,
        evidence_status: EvidenceStatus = EvidenceStatus.MISSING,
        audit_framework: AuditFramework = AuditFramework.SOC2,
        completeness_pct: float = 0.0,
        team: str = "",
    ) -> EvidenceRecord:
        record = EvidenceRecord(
            control_id=control_id,
            evidence_type=evidence_type,
            evidence_status=evidence_status,
            audit_framework=audit_framework,
            completeness_pct=completeness_pct,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "evidence_tracker.evidence_recorded",
            record_id=record.id,
            control_id=control_id,
            evidence_type=evidence_type.value,
            evidence_status=evidence_status.value,
        )
        return record

    def get_evidence(self, record_id: str) -> EvidenceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_evidence(
        self,
        evidence_type: EvidenceType | None = None,
        evidence_status: EvidenceStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EvidenceRecord]:
        results = list(self._records)
        if evidence_type is not None:
            results = [r for r in results if r.evidence_type == evidence_type]
        if evidence_status is not None:
            results = [r for r in results if r.evidence_status == evidence_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_rule(
        self,
        framework_pattern: str,
        audit_framework: AuditFramework = AuditFramework.SOC2,
        required_count: int = 0,
        max_age_days: int = 365,
        description: str = "",
    ) -> EvidenceRule:
        rule = EvidenceRule(
            framework_pattern=framework_pattern,
            audit_framework=audit_framework,
            required_count=required_count,
            max_age_days=max_age_days,
            description=description,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "evidence_tracker.rule_added",
            framework_pattern=framework_pattern,
            audit_framework=audit_framework.value,
            required_count=required_count,
        )
        return rule

    # -- domain operations --------------------------------------------------

    def analyze_evidence_coverage(self) -> dict[str, Any]:
        """Group by evidence_type; return count and avg completeness per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.evidence_type.value
            type_data.setdefault(key, []).append(r.completeness_pct)
        result: dict[str, Any] = {}
        for etype, pcts in type_data.items():
            result[etype] = {
                "count": len(pcts),
                "avg_completeness": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_missing_evidence(self) -> list[dict[str, Any]]:
        """Return records where evidence_status is MISSING or EXPIRED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.evidence_status in (EvidenceStatus.MISSING, EvidenceStatus.EXPIRED):
                results.append(
                    {
                        "record_id": r.id,
                        "control_id": r.control_id,
                        "evidence_status": r.evidence_status.value,
                        "completeness_pct": r.completeness_pct,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_completeness(self) -> list[dict[str, Any]]:
        """Group by team, avg completeness_pct, sort ascending (worst first)."""
        team_pcts: dict[str, list[float]] = {}
        for r in self._records:
            team_pcts.setdefault(r.team, []).append(r.completeness_pct)
        results: list[dict[str, Any]] = []
        for team, pcts in team_pcts.items():
            results.append(
                {
                    "team": team,
                    "avg_completeness": round(sum(pcts) / len(pcts), 2),
                    "count": len(pcts),
                }
            )
        results.sort(key=lambda x: x["avg_completeness"])
        return results

    def detect_evidence_trends(self) -> dict[str, Any]:
        """Split-half on completeness_pct; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        pcts = [r.completeness_pct for r in self._records]
        mid = len(pcts) // 2
        first_half = pcts[:mid]
        second_half = pcts[mid:]
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

    def generate_report(self) -> EvidenceTrackerReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_framework: dict[str, int] = {}
        for r in self._records:
            by_type[r.evidence_type.value] = by_type.get(r.evidence_type.value, 0) + 1
            by_status[r.evidence_status.value] = by_status.get(r.evidence_status.value, 0) + 1
            by_framework[r.audit_framework.value] = by_framework.get(r.audit_framework.value, 0) + 1
        verified_count = sum(
            1 for r in self._records if r.evidence_status == EvidenceStatus.VERIFIED
        )
        avg_completeness = (
            round(sum(r.completeness_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        missing_ids = [
            r.control_id for r in self._records if r.evidence_status == EvidenceStatus.MISSING
        ][:5]
        recs: list[str] = []
        if self._records and avg_completeness < self._min_completeness_pct:
            recs.append(
                f"Average completeness {avg_completeness}% is below "
                f"threshold ({self._min_completeness_pct}%)"
            )
        missing_count = sum(1 for r in self._records if r.evidence_status == EvidenceStatus.MISSING)
        if missing_count > 0:
            recs.append(f"{missing_count} missing evidence item(s) — collect evidence")
        if not recs:
            recs.append("Evidence collection is on track")
        return EvidenceTrackerReport(
            total_records=len(self._records),
            total_rules=len(self._rules),
            verified_count=verified_count,
            avg_completeness=avg_completeness,
            by_type=by_type,
            by_status=by_status,
            by_framework=by_framework,
            missing_evidence=missing_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("evidence_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.evidence_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "min_completeness_pct": self._min_completeness_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_controls": len({r.control_id for r in self._records}),
        }
