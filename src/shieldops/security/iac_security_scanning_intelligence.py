"""IaC Security Scanning Intelligence
classify security findings, compute scan coverage,
rank modules by security risk."""

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


class ScanTool(StrEnum):
    TFSEC = "tfsec"
    CHECKOV = "checkov"
    SNYK = "snyk"
    CUSTOM = "custom"


class FindingCategory(StrEnum):
    ENCRYPTION = "encryption"
    ACCESS = "access"
    NETWORK = "network"
    LOGGING = "logging"


# --- Models ---


class SecurityScanRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    module_id: str = ""
    finding_id: str = ""
    finding_severity: FindingSeverity = FindingSeverity.LOW
    scan_tool: ScanTool = ScanTool.TFSEC
    finding_category: FindingCategory = FindingCategory.ENCRYPTION
    risk_score: float = 0.0
    resolved: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SecurityScanAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    module_id: str = ""
    total_findings: int = 0
    critical_count: int = 0
    computed_risk: float = 0.0
    coverage_pct: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SecurityScanReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_finding_severity: dict[str, int] = Field(default_factory=dict)
    by_scan_tool: dict[str, int] = Field(default_factory=dict)
    by_finding_category: dict[str, int] = Field(default_factory=dict)
    high_risk_modules: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IacSecurityScanningIntelligence:
    """Classify security findings, compute scan
    coverage, rank modules by security risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[SecurityScanRecord] = []
        self._analyses: dict[str, SecurityScanAnalysis] = {}
        logger.info(
            "iac_security_scanning_intelligence.init",
            max_records=max_records,
        )

    def add_record(
        self,
        module_id: str = "",
        finding_id: str = "",
        finding_severity: FindingSeverity = (FindingSeverity.LOW),
        scan_tool: ScanTool = ScanTool.TFSEC,
        finding_category: FindingCategory = (FindingCategory.ENCRYPTION),
        risk_score: float = 0.0,
        resolved: bool = False,
        description: str = "",
    ) -> SecurityScanRecord:
        record = SecurityScanRecord(
            module_id=module_id,
            finding_id=finding_id,
            finding_severity=finding_severity,
            scan_tool=scan_tool,
            finding_category=finding_category,
            risk_score=risk_score,
            resolved=resolved,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_scan.record_added",
            record_id=record.id,
            module_id=module_id,
        )
        return record

    def process(self, key: str) -> SecurityScanAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        findings = [r for r in self._records if r.module_id == rec.module_id]
        critical = sum(1 for f in findings if f.finding_severity == FindingSeverity.CRITICAL)
        resolved = sum(1 for f in findings if f.resolved)
        coverage = round(resolved / len(findings) * 100, 2) if findings else 0.0
        analysis = SecurityScanAnalysis(
            module_id=rec.module_id,
            total_findings=len(findings),
            critical_count=critical,
            computed_risk=round(rec.risk_score, 2),
            coverage_pct=coverage,
            description=(f"Module {rec.module_id} risk {rec.risk_score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> SecurityScanReport:
        by_fs: dict[str, int] = {}
        by_st: dict[str, int] = {}
        by_fc: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.finding_severity.value
            by_fs[k] = by_fs.get(k, 0) + 1
            k2 = r.scan_tool.value
            by_st[k2] = by_st.get(k2, 0) + 1
            k3 = r.finding_category.value
            by_fc[k3] = by_fc.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        high = list(
            {
                r.module_id
                for r in self._records
                if r.finding_severity
                in (
                    FindingSeverity.CRITICAL,
                    FindingSeverity.HIGH,
                )
            }
        )[:10]
        recs: list[str] = []
        if high:
            recs.append(f"{len(high)} high-risk modules found")
        if not recs:
            recs.append("No high-risk modules found")
        return SecurityScanReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_finding_severity=by_fs,
            by_scan_tool=by_st,
            by_finding_category=by_fc,
            high_risk_modules=high,
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
            "severity_distribution": fs_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("iac_security_scanning.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def classify_security_findings(
        self,
    ) -> list[dict[str, Any]]:
        """Classify findings by severity and category."""
        module_findings: dict[str, dict[str, int]] = {}
        for r in self._records:
            if r.module_id not in module_findings:
                module_findings[r.module_id] = {
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                }
            sev = r.finding_severity.value
            module_findings[r.module_id][sev] = module_findings[r.module_id].get(sev, 0) + 1
        results: list[dict[str, Any]] = []
        for mid, counts in module_findings.items():
            total = sum(counts.values())
            results.append(
                {
                    "module_id": mid,
                    "total_findings": total,
                    "by_severity": counts,
                }
            )
        results.sort(
            key=lambda x: x["total_findings"],
            reverse=True,
        )
        return results

    def compute_scan_coverage(
        self,
    ) -> list[dict[str, Any]]:
        """Compute scan coverage per module."""
        module_total: dict[str, int] = {}
        module_resolved: dict[str, int] = {}
        for r in self._records:
            module_total[r.module_id] = module_total.get(r.module_id, 0) + 1
            if r.resolved:
                module_resolved[r.module_id] = module_resolved.get(r.module_id, 0) + 1
        results: list[dict[str, Any]] = []
        for mid, total in module_total.items():
            resolved = module_resolved.get(mid, 0)
            pct = round(resolved / total * 100, 2)
            results.append(
                {
                    "module_id": mid,
                    "total_findings": total,
                    "resolved": resolved,
                    "coverage_pct": pct,
                }
            )
        results.sort(
            key=lambda x: x["coverage_pct"],
            reverse=True,
        )
        return results

    def rank_modules_by_security_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Rank modules by aggregate security risk."""
        module_risk: dict[str, float] = {}
        for r in self._records:
            module_risk[r.module_id] = module_risk.get(r.module_id, 0.0) + r.risk_score
        results: list[dict[str, Any]] = []
        for mid, total in module_risk.items():
            results.append(
                {
                    "module_id": mid,
                    "aggregate_risk": round(total, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["aggregate_risk"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
