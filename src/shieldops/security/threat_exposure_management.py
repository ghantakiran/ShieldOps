"""Threat Exposure Management
external exposure mapping, vuln correlation, remediation priority."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ExposureType(StrEnum):
    PUBLIC_ENDPOINT = "public_endpoint"
    MISCONFIGURATION = "misconfiguration"
    UNPATCHED_CVE = "unpatched_cve"
    CREDENTIAL_LEAK = "credential_leak"
    SHADOW_IT = "shadow_it"


class ExposureSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class RemediationPriority(StrEnum):
    IMMEDIATE = "immediate"
    URGENT = "urgent"
    PLANNED = "planned"
    DEFERRED = "deferred"
    ACCEPTED_RISK = "accepted_risk"


# --- Models ---


class ExposureRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_name: str = ""
    exposure_type: ExposureType = ExposureType.PUBLIC_ENDPOINT
    severity: ExposureSeverity = ExposureSeverity.MEDIUM
    remediation_priority: RemediationPriority = RemediationPriority.PLANNED
    risk_score: float = 0.0
    cve_ids: list[str] = Field(default_factory=list)
    is_internet_facing: bool = False
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ExposureAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_name: str = ""
    exposure_type: ExposureType = ExposureType.PUBLIC_ENDPOINT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ExposureReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_risk_score: float = 0.0
    internet_facing_count: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    top_risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThreatExposureManagement:
    """External exposure mapping, vulnerability correlation, remediation prioritization."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ExposureRecord] = []
        self._analyses: list[ExposureAnalysis] = []
        logger.info(
            "threat_exposure_management.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def add_record(
        self,
        asset_name: str,
        exposure_type: ExposureType = ExposureType.PUBLIC_ENDPOINT,
        severity: ExposureSeverity = ExposureSeverity.MEDIUM,
        remediation_priority: RemediationPriority = RemediationPriority.PLANNED,
        risk_score: float = 0.0,
        cve_ids: list[str] | None = None,
        is_internet_facing: bool = False,
        service: str = "",
        team: str = "",
    ) -> ExposureRecord:
        record = ExposureRecord(
            asset_name=asset_name,
            exposure_type=exposure_type,
            severity=severity,
            remediation_priority=remediation_priority,
            risk_score=risk_score,
            cve_ids=cve_ids or [],
            is_internet_facing=is_internet_facing,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "threat_exposure_management.record_added",
            record_id=record.id,
            asset_name=asset_name,
            severity=severity.value,
        )
        return record

    def get_record(self, record_id: str) -> ExposureRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        exposure_type: ExposureType | None = None,
        severity: ExposureSeverity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ExposureRecord]:
        results = list(self._records)
        if exposure_type is not None:
            results = [r for r in results if r.exposure_type == exposure_type]
        if severity is not None:
            results = [r for r in results if r.severity == severity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        asset_name: str,
        exposure_type: ExposureType = ExposureType.PUBLIC_ENDPOINT,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ExposureAnalysis:
        analysis = ExposureAnalysis(
            asset_name=asset_name,
            exposure_type=exposure_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "threat_exposure_management.analysis_added",
            asset_name=asset_name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def prioritize_remediation(self) -> list[dict[str, Any]]:
        severity_weight = {
            ExposureSeverity.CRITICAL: 5.0,
            ExposureSeverity.HIGH: 4.0,
            ExposureSeverity.MEDIUM: 3.0,
            ExposureSeverity.LOW: 2.0,
            ExposureSeverity.INFORMATIONAL: 1.0,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            weight = severity_weight.get(r.severity, 1.0)
            internet_mult = 1.5 if r.is_internet_facing else 1.0
            cve_mult = 1.0 + len(r.cve_ids) * 0.1
            priority_score = round(r.risk_score * weight * internet_mult * cve_mult, 2)
            results.append(
                {
                    "asset_name": r.asset_name,
                    "priority_score": priority_score,
                    "severity": r.severity.value,
                    "internet_facing": r.is_internet_facing,
                    "cve_count": len(r.cve_ids),
                }
            )
        return sorted(results, key=lambda x: x["priority_score"], reverse=True)

    def correlate_vulnerabilities(self) -> dict[str, Any]:
        cve_assets: dict[str, list[str]] = {}
        for r in self._records:
            for cve in r.cve_ids:
                cve_assets.setdefault(cve, []).append(r.asset_name)
        widespread = {cve: assets for cve, assets in cve_assets.items() if len(assets) > 1}
        return {
            "total_unique_cves": len(cve_assets),
            "widespread_cves": len(widespread),
            "most_widespread": sorted(
                [{"cve": c, "affected_assets": len(a)} for c, a in widespread.items()],
                key=lambda x: x.get("affected_assets", 0),  # type: ignore[arg-type,return-value]
                reverse=True,
            )[:10],
        }

    def identify_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score >= self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "asset_name": r.asset_name,
                        "exposure_type": r.exposure_type.value,
                        "risk_score": r.risk_score,
                        "severity": r.severity.value,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"], reverse=True)

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
            trend = "increasing_exposure"
        else:
            trend = "decreasing_exposure"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def process(self, asset_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.asset_name == asset_name]
        if not matching:
            return {"asset_name": asset_name, "status": "no_data"}
        scores = [r.risk_score for r in matching]
        all_cves: set[str] = set()
        for r in matching:
            all_cves.update(r.cve_ids)
        return {
            "asset_name": asset_name,
            "exposure_count": len(matching),
            "avg_risk_score": round(sum(scores) / len(scores), 2),
            "unique_cves": len(all_cves),
            "internet_facing": any(r.is_internet_facing for r in matching),
        }

    def generate_report(self) -> ExposureReport:
        by_type: dict[str, int] = {}
        by_sev: dict[str, int] = {}
        by_pri: dict[str, int] = {}
        for r in self._records:
            by_type[r.exposure_type.value] = by_type.get(r.exposure_type.value, 0) + 1
            by_sev[r.severity.value] = by_sev.get(r.severity.value, 0) + 1
            by_pri[r.remediation_priority.value] = by_pri.get(r.remediation_priority.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.risk_score >= self._threshold)
        scores = [r.risk_score for r in self._records]
        avg_risk = round(sum(scores) / len(scores), 2) if scores else 0.0
        internet_facing = sum(1 for r in self._records if r.is_internet_facing)
        top_risks = [g["asset_name"] for g in self.identify_gaps()[:5]]
        recs: list[str] = []
        if gap_count > 0:
            recs.append(f"{gap_count} exposure(s) at or above risk threshold ({self._threshold})")
        if internet_facing > 0:
            recs.append(f"{internet_facing} internet-facing exposure(s) require priority review")
        crit_count = by_sev.get("critical", 0)
        if crit_count > 0:
            recs.append(f"{crit_count} critical severity exposure(s) found")
        if not recs:
            recs.append("Threat exposure posture is healthy")
        return ExposureReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_risk_score=avg_risk,
            internet_facing_count=internet_facing,
            by_type=by_type,
            by_severity=by_sev,
            by_priority=by_pri,
            top_risks=top_risks,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.exposure_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "type_distribution": type_dist,
            "unique_assets": len({r.asset_name for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("threat_exposure_management.cleared")
        return {"status": "cleared"}
