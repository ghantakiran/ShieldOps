"""Threat Hunt Orchestrator — automated threat hunting campaigns and IOC correlation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HuntType(StrEnum):
    HYPOTHESIS_DRIVEN = "hypothesis_driven"
    IOC_SWEEP = "ioc_sweep"
    ANOMALY_BASED = "anomaly_based"
    BEHAVIORAL = "behavioral"
    INTEL_LED = "intel_led"


class HuntStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ThreatSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Models ---


class HuntRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_name: str = ""
    hunt_type: HuntType = HuntType.HYPOTHESIS_DRIVEN
    hunt_status: HuntStatus = HuntStatus.PLANNING
    threat_severity: ThreatSeverity = ThreatSeverity.MEDIUM
    findings_count: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class HuntFinding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    finding_label: str = ""
    hunt_type: HuntType = HuntType.IOC_SWEEP
    threat_severity: ThreatSeverity = ThreatSeverity.HIGH
    confidence_score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ThreatHuntReport(BaseModel):
    total_hunts: int = 0
    total_findings: int = 0
    detection_rate_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    critical_finding_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThreatHuntOrchestrator:
    """Automated threat hunting campaigns and IOC correlation."""

    def __init__(
        self,
        max_records: int = 200000,
        min_detection_rate_pct: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._min_detection_rate_pct = min_detection_rate_pct
        self._records: list[HuntRecord] = []
        self._findings: list[HuntFinding] = []
        logger.info(
            "threat_hunt.initialized",
            max_records=max_records,
            min_detection_rate_pct=min_detection_rate_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_hunt(
        self,
        campaign_name: str,
        hunt_type: HuntType = HuntType.HYPOTHESIS_DRIVEN,
        hunt_status: HuntStatus = HuntStatus.PLANNING,
        threat_severity: ThreatSeverity = ThreatSeverity.MEDIUM,
        findings_count: int = 0,
        details: str = "",
    ) -> HuntRecord:
        record = HuntRecord(
            campaign_name=campaign_name,
            hunt_type=hunt_type,
            hunt_status=hunt_status,
            threat_severity=threat_severity,
            findings_count=findings_count,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "threat_hunt.hunt_recorded",
            record_id=record.id,
            campaign_name=campaign_name,
            hunt_type=hunt_type.value,
            hunt_status=hunt_status.value,
        )
        return record

    def get_hunt(self, record_id: str) -> HuntRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_hunts(
        self,
        campaign_name: str | None = None,
        hunt_type: HuntType | None = None,
        limit: int = 50,
    ) -> list[HuntRecord]:
        results = list(self._records)
        if campaign_name is not None:
            results = [r for r in results if r.campaign_name == campaign_name]
        if hunt_type is not None:
            results = [r for r in results if r.hunt_type == hunt_type]
        return results[-limit:]

    def add_finding(
        self,
        finding_label: str,
        hunt_type: HuntType = HuntType.IOC_SWEEP,
        threat_severity: ThreatSeverity = ThreatSeverity.HIGH,
        confidence_score: float = 0.0,
    ) -> HuntFinding:
        finding = HuntFinding(
            finding_label=finding_label,
            hunt_type=hunt_type,
            threat_severity=threat_severity,
            confidence_score=confidence_score,
        )
        self._findings.append(finding)
        if len(self._findings) > self._max_records:
            self._findings = self._findings[-self._max_records :]
        logger.info(
            "threat_hunt.finding_added",
            finding_label=finding_label,
            hunt_type=hunt_type.value,
            threat_severity=threat_severity.value,
        )
        return finding

    # -- domain operations -----------------------------------------------

    def analyze_hunt_effectiveness(self, campaign_name: str) -> dict[str, Any]:
        """Analyze effectiveness for a specific campaign."""
        records = [r for r in self._records if r.campaign_name == campaign_name]
        if not records:
            return {"campaign_name": campaign_name, "status": "no_data"}
        findings_with_severity = sum(
            1
            for r in records
            if r.threat_severity in (ThreatSeverity.CRITICAL, ThreatSeverity.HIGH)
        )
        detection_rate = round(findings_with_severity / len(records) * 100, 2)
        return {
            "campaign_name": campaign_name,
            "total_hunts": len(records),
            "high_severity_count": findings_with_severity,
            "detection_rate_pct": detection_rate,
            "meets_threshold": detection_rate >= self._min_detection_rate_pct,
        }

    def identify_low_yield_hunts(self) -> list[dict[str, Any]]:
        """Find campaigns with zero-finding hunts."""
        zero_counts: dict[str, int] = {}
        for r in self._records:
            if r.findings_count == 0:
                zero_counts[r.campaign_name] = zero_counts.get(r.campaign_name, 0) + 1
        results: list[dict[str, Any]] = []
        for campaign, count in zero_counts.items():
            if count > 1:
                results.append(
                    {
                        "campaign_name": campaign,
                        "zero_finding_count": count,
                    }
                )
        results.sort(key=lambda x: x["zero_finding_count"], reverse=True)
        return results

    def rank_by_findings_count(self) -> list[dict[str, Any]]:
        """Rank campaigns by total findings count descending."""
        freq: dict[str, int] = {}
        for r in self._records:
            freq[r.campaign_name] = freq.get(r.campaign_name, 0) + r.findings_count
        results: list[dict[str, Any]] = []
        for campaign, count in freq.items():
            results.append(
                {
                    "campaign_name": campaign,
                    "findings_count": count,
                }
            )
        results.sort(key=lambda x: x["findings_count"], reverse=True)
        return results

    def detect_hunt_stagnation(self) -> list[dict[str, Any]]:
        """Detect campaigns with >3 non-active/completed hunts (PLANNING+ARCHIVED)."""
        svc_stagnant: dict[str, int] = {}
        for r in self._records:
            if r.hunt_status in (HuntStatus.PLANNING, HuntStatus.ARCHIVED):
                svc_stagnant[r.campaign_name] = svc_stagnant.get(r.campaign_name, 0) + 1
        results: list[dict[str, Any]] = []
        for campaign, count in svc_stagnant.items():
            if count > 3:
                results.append(
                    {
                        "campaign_name": campaign,
                        "stagnant_count": count,
                        "stagnation_detected": True,
                    }
                )
        results.sort(key=lambda x: x["stagnant_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ThreatHuntReport:
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_type[r.hunt_type.value] = by_type.get(r.hunt_type.value, 0) + 1
            by_severity[r.threat_severity.value] = by_severity.get(r.threat_severity.value, 0) + 1
        critical_count = sum(
            1 for r in self._records if r.threat_severity == ThreatSeverity.CRITICAL
        )
        high_sev = sum(
            1
            for r in self._records
            if r.threat_severity in (ThreatSeverity.CRITICAL, ThreatSeverity.HIGH)
        )
        detection_rate = round(high_sev / len(self._records) * 100, 2) if self._records else 0.0
        low_yield = sum(1 for d in self.identify_low_yield_hunts())
        recs: list[str] = []
        if detection_rate < self._min_detection_rate_pct:
            recs.append(
                f"Detection rate {detection_rate}% is below"
                f" {self._min_detection_rate_pct}% threshold"
            )
        if low_yield > 0:
            recs.append(f"{low_yield} campaign(s) with low-yield hunts")
        stagnant = len(self.detect_hunt_stagnation())
        if stagnant > 0:
            recs.append(f"{stagnant} campaign(s) detected with stagnation")
        if not recs:
            recs.append("Threat hunt effectiveness meets targets")
        return ThreatHuntReport(
            total_hunts=len(self._records),
            total_findings=len(self._findings),
            detection_rate_pct=detection_rate,
            by_type=by_type,
            by_severity=by_severity,
            critical_finding_count=critical_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._findings.clear()
        logger.info("threat_hunt.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.hunt_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_hunts": len(self._records),
            "total_findings": len(self._findings),
            "min_detection_rate_pct": self._min_detection_rate_pct,
            "type_distribution": type_dist,
            "unique_campaigns": len({r.campaign_name for r in self._records}),
        }
