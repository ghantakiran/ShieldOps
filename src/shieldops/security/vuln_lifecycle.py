"""Vulnerability Lifecycle Manager — CVE lifecycle tracking, exploit prediction, patch success."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VulnPhase(StrEnum):
    DISCLOSED = "disclosed"
    ASSESSED = "assessed"
    PATCH_AVAILABLE = "patch_available"
    PATCH_TESTING = "patch_testing"
    PATCH_DEPLOYED = "patch_deployed"
    MITIGATED = "mitigated"
    ACCEPTED_RISK = "accepted_risk"


class ExploitStatus(StrEnum):
    NO_KNOWN_EXPLOIT = "no_known_exploit"
    POC_AVAILABLE = "poc_available"
    ACTIVE_EXPLOITATION = "active_exploitation"
    WEAPONIZED = "weaponized"


class PatchOutcome(StrEnum):
    SUCCESS = "success"
    REGRESSION = "regression"
    ROLLBACK = "rollback"
    PENDING = "pending"
    SKIPPED = "skipped"


# --- Models ---


class VulnerabilityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    cve_id: str = ""
    title: str = ""
    description: str = ""
    severity: str = "medium"
    cvss_score: float = 0.0
    phase: VulnPhase = VulnPhase.DISCLOSED
    exploit_status: ExploitStatus = ExploitStatus.NO_KNOWN_EXPLOIT
    affected_services: list[str] = Field(default_factory=list)
    patch_attempts: list[str] = Field(default_factory=list)
    disclosed_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class PatchAttempt(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vuln_id: str = ""
    patch_version: str = ""
    outcome: PatchOutcome = PatchOutcome.PENDING
    applied_by: str = ""
    notes: str = ""
    applied_at: float = Field(default_factory=time.time)


class ExploitPrediction(BaseModel):
    vuln_id: str = ""
    cve_id: str = ""
    current_status: ExploitStatus = ExploitStatus.NO_KNOWN_EXPLOIT
    predicted_risk: float = 0.0
    days_since_disclosure: float = 0.0
    recommendation: str = ""


# --- Engine ---


class VulnerabilityLifecycleManager:
    """CVE lifecycle tracking, exploit prediction, patch success tracking."""

    def __init__(
        self,
        max_records: int = 100000,
        patch_sla_days: int = 14,
    ) -> None:
        self._max_records = max_records
        self._patch_sla_days = patch_sla_days
        self._vulns: list[VulnerabilityRecord] = []
        self._patches: list[PatchAttempt] = []
        logger.info(
            "vuln_lifecycle.initialized",
            max_records=max_records,
            patch_sla_days=patch_sla_days,
        )

    def register_vulnerability(
        self,
        cve_id: str = "",
        title: str = "",
        description: str = "",
        severity: str = "medium",
        cvss_score: float = 0.0,
        affected_services: list[str] | None = None,
    ) -> VulnerabilityRecord:
        vuln = VulnerabilityRecord(
            cve_id=cve_id,
            title=title,
            description=description,
            severity=severity,
            cvss_score=cvss_score,
            affected_services=affected_services or [],
        )
        self._vulns.append(vuln)
        if len(self._vulns) > self._max_records:
            self._vulns = self._vulns[-self._max_records :]
        logger.info(
            "vuln_lifecycle.registered",
            vuln_id=vuln.id,
            cve_id=cve_id,
            severity=severity,
        )
        return vuln

    def get_vulnerability(self, vuln_id: str) -> VulnerabilityRecord | None:
        for v in self._vulns:
            if v.id == vuln_id:
                return v
        return None

    def list_vulnerabilities(
        self,
        phase: VulnPhase | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[VulnerabilityRecord]:
        results = list(self._vulns)
        if phase is not None:
            results = [v for v in results if v.phase == phase]
        if severity is not None:
            results = [v for v in results if v.severity == severity]
        return results[-limit:]

    def advance_phase(self, vuln_id: str, new_phase: VulnPhase) -> bool:
        vuln = self.get_vulnerability(vuln_id)
        if vuln is None:
            return False
        vuln.phase = new_phase
        vuln.updated_at = time.time()
        logger.info(
            "vuln_lifecycle.phase_advanced",
            vuln_id=vuln_id,
            new_phase=new_phase,
        )
        return True

    def record_patch_attempt(
        self,
        vuln_id: str,
        patch_version: str = "",
        outcome: PatchOutcome = PatchOutcome.PENDING,
        applied_by: str = "",
        notes: str = "",
    ) -> PatchAttempt | None:
        vuln = self.get_vulnerability(vuln_id)
        if vuln is None:
            return None
        attempt = PatchAttempt(
            vuln_id=vuln_id,
            patch_version=patch_version,
            outcome=outcome,
            applied_by=applied_by,
            notes=notes,
        )
        self._patches.append(attempt)
        vuln.patch_attempts.append(attempt.id)
        vuln.updated_at = time.time()
        if outcome == PatchOutcome.SUCCESS:
            vuln.phase = VulnPhase.PATCH_DEPLOYED
        logger.info(
            "vuln_lifecycle.patch_recorded",
            vuln_id=vuln_id,
            attempt_id=attempt.id,
            outcome=outcome,
        )
        return attempt

    def predict_exploit_risk(self, vuln_id: str) -> ExploitPrediction | None:
        vuln = self.get_vulnerability(vuln_id)
        if vuln is None:
            return None
        days = (time.time() - vuln.disclosed_at) / 86400
        # Simple heuristic: higher CVSS + longer unpatched = higher risk
        base_risk = vuln.cvss_score / 10.0
        time_factor = min(1.0, days / 30)
        exploit_factor = {
            ExploitStatus.NO_KNOWN_EXPLOIT: 0.1,
            ExploitStatus.POC_AVAILABLE: 0.5,
            ExploitStatus.ACTIVE_EXPLOITATION: 0.8,
            ExploitStatus.WEAPONIZED: 1.0,
        }.get(vuln.exploit_status, 0.1)
        risk = min(1.0, (base_risk * 0.4 + time_factor * 0.3 + exploit_factor * 0.3))
        if risk > 0.8:
            rec = "Immediate patching required"
        elif risk > 0.5:
            rec = "Prioritize patching within SLA"
        elif risk > 0.3:
            rec = "Schedule patching"
        else:
            rec = "Monitor and track"
        return ExploitPrediction(
            vuln_id=vuln_id,
            cve_id=vuln.cve_id,
            current_status=vuln.exploit_status,
            predicted_risk=round(risk, 3),
            days_since_disclosure=round(days, 1),
            recommendation=rec,
        )

    def get_overdue_patches(self) -> list[dict[str, Any]]:
        now = time.time()
        sla_seconds = self._patch_sla_days * 86400
        overdue: list[dict[str, Any]] = []
        for v in self._vulns:
            closed = (VulnPhase.PATCH_DEPLOYED, VulnPhase.MITIGATED, VulnPhase.ACCEPTED_RISK)
            if v.phase not in closed:
                age = now - v.disclosed_at
                if age > sla_seconds:
                    overdue.append(
                        {
                            "vuln_id": v.id,
                            "cve_id": v.cve_id,
                            "severity": v.severity,
                            "days_overdue": round((age - sla_seconds) / 86400, 1),
                            "phase": v.phase.value,
                        }
                    )
        overdue.sort(key=lambda o: o["days_overdue"], reverse=True)
        return overdue

    def get_risk_summary(self) -> dict[str, Any]:
        severity_counts: dict[str, int] = {}
        exploit_counts: dict[str, int] = {}
        open_count = 0
        for v in self._vulns:
            severity_counts[v.severity] = severity_counts.get(v.severity, 0) + 1
            exploit_counts[v.exploit_status] = exploit_counts.get(v.exploit_status, 0) + 1
            closed = (VulnPhase.PATCH_DEPLOYED, VulnPhase.MITIGATED, VulnPhase.ACCEPTED_RISK)
            if v.phase not in closed:
                open_count += 1
        return {
            "total_vulnerabilities": len(self._vulns),
            "open_vulnerabilities": open_count,
            "severity_distribution": severity_counts,
            "exploit_status_distribution": exploit_counts,
            "overdue_count": len(self.get_overdue_patches()),
        }

    def get_patch_success_rate(self) -> dict[str, Any]:
        if not self._patches:
            return {"total_attempts": 0, "success_rate": 0.0, "by_outcome": {}}
        outcome_counts: dict[str, int] = {}
        for p in self._patches:
            outcome_counts[p.outcome] = outcome_counts.get(p.outcome, 0) + 1
        successes = outcome_counts.get(PatchOutcome.SUCCESS, 0)
        total = len(self._patches)
        return {
            "total_attempts": total,
            "success_rate": round(successes / total * 100, 1) if total > 0 else 0.0,
            "by_outcome": outcome_counts,
        }

    def get_stats(self) -> dict[str, Any]:
        phase_counts: dict[str, int] = {}
        for v in self._vulns:
            phase_counts[v.phase] = phase_counts.get(v.phase, 0) + 1
        return {
            "total_vulnerabilities": len(self._vulns),
            "total_patch_attempts": len(self._patches),
            "phase_distribution": phase_counts,
            "patch_success_rate": self.get_patch_success_rate()["success_rate"],
        }
