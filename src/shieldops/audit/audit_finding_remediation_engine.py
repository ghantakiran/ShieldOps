"""Audit Finding Remediation Engine
compute remediation velocity, detect overdue findings,
rank findings by risk exposure."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FindingSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RemediationStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    REMEDIATED = "remediated"
    ACCEPTED_RISK = "accepted_risk"


class FindingCategory(StrEnum):
    CONTROL_GAP = "control_gap"
    PROCESS_DEFICIENCY = "process_deficiency"
    TECHNICAL_DEBT = "technical_debt"
    POLICY_VIOLATION = "policy_violation"


# --- Models ---


class AuditFindingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    finding_id: str = ""
    finding_severity: FindingSeverity = FindingSeverity.LOW
    remediation_status: RemediationStatus = RemediationStatus.OPEN
    finding_category: FindingCategory = FindingCategory.CONTROL_GAP
    risk_score: float = 0.0
    days_open: float = 0.0
    due_date_days: float = 30.0
    owner: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditFindingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    finding_id: str = ""
    finding_severity: FindingSeverity = FindingSeverity.LOW
    computed_velocity: float = 0.0
    is_overdue: bool = False
    risk_exposure: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditFindingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_finding_severity: dict[str, int] = Field(default_factory=dict)
    by_remediation_status: dict[str, int] = Field(default_factory=dict)
    by_finding_category: dict[str, int] = Field(default_factory=dict)
    overdue_findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuditFindingRemediationEngine:
    """Compute remediation velocity, detect overdue
    findings, rank findings by risk exposure."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[AuditFindingRecord] = []
        self._analyses: dict[str, AuditFindingAnalysis] = {}
        logger.info(
            "audit_finding_remediation_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        finding_id: str = "",
        finding_severity: FindingSeverity = FindingSeverity.LOW,
        remediation_status: RemediationStatus = RemediationStatus.OPEN,
        finding_category: FindingCategory = FindingCategory.CONTROL_GAP,
        risk_score: float = 0.0,
        days_open: float = 0.0,
        due_date_days: float = 30.0,
        owner: str = "",
        description: str = "",
    ) -> AuditFindingRecord:
        record = AuditFindingRecord(
            finding_id=finding_id,
            finding_severity=finding_severity,
            remediation_status=remediation_status,
            finding_category=finding_category,
            risk_score=risk_score,
            days_open=days_open,
            due_date_days=due_date_days,
            owner=owner,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "audit_finding_remediation.record_added",
            record_id=record.id,
            finding_id=finding_id,
        )
        return record

    def process(self, key: str) -> AuditFindingAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_overdue = rec.days_open > rec.due_date_days
        velocity = round(rec.risk_score / max(rec.days_open, 1.0), 2)
        exposure = round(rec.risk_score * max(rec.days_open - rec.due_date_days, 0), 2)
        analysis = AuditFindingAnalysis(
            finding_id=rec.finding_id,
            finding_severity=rec.finding_severity,
            computed_velocity=velocity,
            is_overdue=is_overdue,
            risk_exposure=exposure,
            description=f"Finding {rec.finding_id} risk {rec.risk_score}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> AuditFindingReport:
        by_fs: dict[str, int] = {}
        by_rs: dict[str, int] = {}
        by_fc: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.finding_severity.value
            by_fs[k] = by_fs.get(k, 0) + 1
            k2 = r.remediation_status.value
            by_rs[k2] = by_rs.get(k2, 0) + 1
            k3 = r.finding_category.value
            by_fc[k3] = by_fc.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        overdue = list({r.finding_id for r in self._records if r.days_open > r.due_date_days})[:10]
        recs: list[str] = []
        if overdue:
            recs.append(f"{len(overdue)} overdue findings detected")
        if not recs:
            recs.append("All findings within SLA")
        return AuditFindingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_finding_severity=by_fs,
            by_remediation_status=by_rs,
            by_finding_category=by_fc,
            overdue_findings=overdue,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        fs_dist: dict[str, int] = {}
        for r in self._records:
            k = r.finding_severity.value
            fs_dist[k] = fs_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "finding_severity_distribution": fs_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("audit_finding_remediation_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_remediation_velocity(
        self,
    ) -> list[dict[str, Any]]:
        """Compute remediation velocity per finding."""
        finding_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.finding_id not in finding_data:
                finding_data[r.finding_id] = {
                    "severity": r.finding_severity.value,
                    "days_open": r.days_open,
                    "risk_score": r.risk_score,
                    "status": r.remediation_status.value,
                }
        results: list[dict[str, Any]] = []
        for fid, data in finding_data.items():
            velocity = round(data["risk_score"] / max(data["days_open"], 1.0), 2)
            results.append(
                {
                    "finding_id": fid,
                    "severity": data["severity"],
                    "velocity": velocity,
                    "days_open": data["days_open"],
                    "status": data["status"],
                }
            )
        results.sort(key=lambda x: x["velocity"], reverse=True)
        return results

    def detect_overdue_findings(
        self,
    ) -> list[dict[str, Any]]:
        """Detect findings past their due date."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.days_open > r.due_date_days and r.finding_id not in seen:
                seen.add(r.finding_id)
                results.append(
                    {
                        "finding_id": r.finding_id,
                        "finding_severity": r.finding_severity.value,
                        "days_open": r.days_open,
                        "due_date_days": r.due_date_days,
                        "overdue_by": round(r.days_open - r.due_date_days, 2),
                    }
                )
        results.sort(key=lambda x: x["overdue_by"], reverse=True)
        return results

    def rank_findings_by_risk_exposure(
        self,
    ) -> list[dict[str, Any]]:
        """Rank findings by cumulative risk exposure."""
        finding_risk: dict[str, float] = {}
        finding_sev: dict[str, str] = {}
        for r in self._records:
            exposure = r.risk_score * max(r.days_open - r.due_date_days, 0)
            finding_risk[r.finding_id] = finding_risk.get(r.finding_id, 0.0) + exposure
            finding_sev[r.finding_id] = r.finding_severity.value
        results: list[dict[str, Any]] = []
        for fid, exposure in finding_risk.items():
            results.append(
                {
                    "finding_id": fid,
                    "severity": finding_sev[fid],
                    "risk_exposure": round(exposure, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["risk_exposure"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
