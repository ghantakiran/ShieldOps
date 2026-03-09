"""Cloud Workload Protection
runtime security, file integrity, process monitoring, micro-segmentation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class WorkloadType(StrEnum):
    CONTAINER = "container"
    VIRTUAL_MACHINE = "virtual_machine"
    SERVERLESS = "serverless"
    BARE_METAL = "bare_metal"
    KUBERNETES_POD = "kubernetes_pod"


class ThreatCategory(StrEnum):
    FILE_INTEGRITY = "file_integrity"
    PROCESS_ANOMALY = "process_anomaly"
    NETWORK_VIOLATION = "network_violation"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    CRYPTO_MINING = "crypto_mining"


class ProtectionStatus(StrEnum):
    PROTECTED = "protected"
    UNPROTECTED = "unprotected"
    DEGRADED = "degraded"
    MONITORING = "monitoring"
    QUARANTINED = "quarantined"


# --- Models ---


class WorkloadRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workload_name: str = ""
    workload_type: WorkloadType = WorkloadType.CONTAINER
    threat_category: ThreatCategory = ThreatCategory.PROCESS_ANOMALY
    protection_status: ProtectionStatus = ProtectionStatus.MONITORING
    security_score: float = 0.0
    open_findings: int = 0
    network_policies_applied: int = 0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkloadAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workload_name: str = ""
    workload_type: WorkloadType = WorkloadType.CONTAINER
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkloadProtectionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_security_score: float = 0.0
    protected_pct: float = 0.0
    by_workload_type: dict[str, int] = Field(default_factory=dict)
    by_threat_category: dict[str, int] = Field(default_factory=dict)
    by_protection_status: dict[str, int] = Field(default_factory=dict)
    unprotected_workloads: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CloudWorkloadProtection:
    """Workload runtime security, file integrity monitoring, process monitoring
    micro-segmentation."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[WorkloadRecord] = []
        self._analyses: list[WorkloadAnalysis] = []
        logger.info(
            "cloud_workload_protection.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def add_record(
        self,
        workload_name: str,
        workload_type: WorkloadType = WorkloadType.CONTAINER,
        threat_category: ThreatCategory = ThreatCategory.PROCESS_ANOMALY,
        protection_status: ProtectionStatus = ProtectionStatus.MONITORING,
        security_score: float = 0.0,
        open_findings: int = 0,
        network_policies_applied: int = 0,
        service: str = "",
        team: str = "",
    ) -> WorkloadRecord:
        record = WorkloadRecord(
            workload_name=workload_name,
            workload_type=workload_type,
            threat_category=threat_category,
            protection_status=protection_status,
            security_score=security_score,
            open_findings=open_findings,
            network_policies_applied=network_policies_applied,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cloud_workload_protection.record_added",
            record_id=record.id,
            workload_name=workload_name,
            workload_type=workload_type.value,
        )
        return record

    def get_record(self, record_id: str) -> WorkloadRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        workload_type: WorkloadType | None = None,
        protection_status: ProtectionStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[WorkloadRecord]:
        results = list(self._records)
        if workload_type is not None:
            results = [r for r in results if r.workload_type == workload_type]
        if protection_status is not None:
            results = [r for r in results if r.protection_status == protection_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        workload_name: str,
        workload_type: WorkloadType = WorkloadType.CONTAINER,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> WorkloadAnalysis:
        analysis = WorkloadAnalysis(
            workload_name=workload_name,
            workload_type=workload_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "cloud_workload_protection.analysis_added",
            workload_name=workload_name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def assess_protection_coverage(self) -> dict[str, Any]:
        if not self._records:
            return {"protected_pct": 0.0, "total_workloads": 0}
        protected = sum(
            1 for r in self._records if r.protection_status == ProtectionStatus.PROTECTED
        )
        degraded = sum(1 for r in self._records if r.protection_status == ProtectionStatus.DEGRADED)
        unprotected = sum(
            1 for r in self._records if r.protection_status == ProtectionStatus.UNPROTECTED
        )
        total = len(self._records)
        return {
            "protected_pct": round(protected / total * 100, 2),
            "protected": protected,
            "degraded": degraded,
            "unprotected": unprotected,
            "total_workloads": total,
        }

    def analyze_threat_distribution(self) -> dict[str, Any]:
        threat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.threat_category.value
            threat_data.setdefault(key, []).append(r.security_score)
        result: dict[str, Any] = {}
        for cat, scores in threat_data.items():
            result[cat] = {
                "count": len(scores),
                "avg_security_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_unprotected(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.protection_status in (
                ProtectionStatus.UNPROTECTED,
                ProtectionStatus.DEGRADED,
            ):
                results.append(
                    {
                        "workload_name": r.workload_name,
                        "workload_type": r.workload_type.value,
                        "protection_status": r.protection_status.value,
                        "security_score": r.security_score,
                        "open_findings": r.open_findings,
                    }
                )
        return sorted(results, key=lambda x: x["security_score"])

    def evaluate_segmentation(self) -> dict[str, Any]:
        type_policies: dict[str, list[int]] = {}
        for r in self._records:
            key = r.workload_type.value
            type_policies.setdefault(key, []).append(r.network_policies_applied)
        results: dict[str, Any] = {}
        for wtype, policies in type_policies.items():
            no_policy = sum(1 for p in policies if p == 0)
            results[wtype] = {
                "avg_policies": round(sum(policies) / len(policies), 1),
                "no_policy_count": no_policy,
                "total": len(policies),
            }
        return results

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def process(self, workload_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.workload_name == workload_name]
        if not matching:
            return {"workload_name": workload_name, "status": "no_data"}
        scores = [r.security_score for r in matching]
        findings = [r.open_findings for r in matching]
        return {
            "workload_name": workload_name,
            "record_count": len(matching),
            "avg_security_score": round(sum(scores) / len(scores), 2),
            "total_open_findings": sum(findings),
            "latest_status": matching[-1].protection_status.value,
        }

    def generate_report(self) -> WorkloadProtectionReport:
        by_wt: dict[str, int] = {}
        by_tc: dict[str, int] = {}
        by_ps: dict[str, int] = {}
        for r in self._records:
            by_wt[r.workload_type.value] = by_wt.get(r.workload_type.value, 0) + 1
            by_tc[r.threat_category.value] = by_tc.get(r.threat_category.value, 0) + 1
            by_ps[r.protection_status.value] = by_ps.get(r.protection_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.security_score < self._threshold)
        scores = [r.security_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        coverage = self.assess_protection_coverage()
        unprotected = self.identify_unprotected()
        unp_names = [u["workload_name"] for u in unprotected[:5]]
        recs: list[str] = []
        if gap_count > 0:
            recs.append(f"{gap_count} workload(s) below security threshold ({self._threshold})")
        if coverage.get("unprotected", 0) > 0:
            recs.append(
                f"{coverage['unprotected']} unprotected workload(s) — deploy agents immediately"
            )
        if coverage.get("degraded", 0) > 0:
            recs.append(f"{coverage['degraded']} workload(s) in degraded protection state")
        if not recs:
            recs.append("Cloud workload protection is healthy")
        return WorkloadProtectionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_security_score=avg_score,
            protected_pct=coverage.get("protected_pct", 0.0),
            by_workload_type=by_wt,
            by_threat_category=by_tc,
            by_protection_status=by_ps,
            unprotected_workloads=unp_names,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        wt_dist: dict[str, int] = {}
        for r in self._records:
            key = r.workload_type.value
            wt_dist[key] = wt_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "workload_type_distribution": wt_dist,
            "unique_workloads": len({r.workload_name for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("cloud_workload_protection.cleared")
        return {"status": "cleared"}
