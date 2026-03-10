"""TelemetryComplianceEngine — telemetry compliance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ComplianceStandard(StrEnum):
    GDPR = "gdpr"
    HIPAA = "hipaa"
    SOX = "sox"
    PCI = "pci"


class DataSensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class RetentionPolicy(StrEnum):
    DAYS_30 = "days_30"
    DAYS_90 = "days_90"
    DAYS_365 = "days_365"
    INDEFINITE = "indefinite"


# --- Models ---


class ComplianceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    standard: ComplianceStandard = ComplianceStandard.GDPR
    sensitivity: DataSensitivity = DataSensitivity.INTERNAL
    retention: RetentionPolicy = RetentionPolicy.DAYS_90
    score: float = 0.0
    pii_detected: bool = False
    region: str = ""
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    standard: ComplianceStandard = ComplianceStandard.GDPR
    analysis_score: float = 0.0
    compliant: bool = True
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    pii_count: int = 0
    by_standard: dict[str, int] = Field(default_factory=dict)
    by_sensitivity: dict[str, int] = Field(default_factory=dict)
    by_retention: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TelemetryComplianceEngine:
    """Telemetry Compliance Engine.

    Ensures telemetry data meets compliance
    requirements across GDPR, HIPAA, SOX, PCI.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ComplianceRecord] = []
        self._analyses: list[ComplianceAnalysis] = []
        logger.info(
            "telemetry_compliance_engine.init",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        standard: ComplianceStandard = (ComplianceStandard.GDPR),
        sensitivity: DataSensitivity = (DataSensitivity.INTERNAL),
        retention: RetentionPolicy = (RetentionPolicy.DAYS_90),
        score: float = 0.0,
        pii_detected: bool = False,
        region: str = "",
        service: str = "",
        team: str = "",
    ) -> ComplianceRecord:
        record = ComplianceRecord(
            name=name,
            standard=standard,
            sensitivity=sensitivity,
            retention=retention,
            score=score,
            pii_detected=pii_detected,
            region=region,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "telemetry_compliance_engine.added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.name == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        scores = [r.score for r in matching]
        avg = round(sum(scores) / len(scores), 2)
        pii_cnt = sum(1 for r in matching if r.pii_detected)
        return {
            "key": key,
            "record_count": len(matching),
            "avg_score": avg,
            "pii_detected_count": pii_cnt,
        }

    def generate_report(self) -> ComplianceReport:
        by_st: dict[str, int] = {}
        by_se: dict[str, int] = {}
        by_re: dict[str, int] = {}
        for r in self._records:
            v1 = r.standard.value
            by_st[v1] = by_st.get(v1, 0) + 1
            v2 = r.sensitivity.value
            by_se[v2] = by_se.get(v2, 0) + 1
            v3 = r.retention.value
            by_re[v3] = by_re.get(v3, 0) + 1
        scores = [r.score for r in self._records]
        avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
        pii_cnt = sum(1 for r in self._records if r.pii_detected)
        recs: list[str] = []
        if pii_cnt > 0:
            recs.append(f"{pii_cnt} record(s) with PII detected")
        if avg_s < self._threshold and self._records:
            recs.append(f"Avg compliance score {avg_s} below threshold {self._threshold}")
        if not recs:
            recs.append("Telemetry compliance healthy")
        return ComplianceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg_s,
            pii_count=pii_cnt,
            by_standard=by_st,
            by_sensitivity=by_se,
            by_retention=by_re,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        st_dist: dict[str, int] = {}
        for r in self._records:
            k = r.standard.value
            st_dist[k] = st_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "standard_distribution": st_dist,
            "unique_regions": len({r.region for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("telemetry_compliance_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def audit_data_residency(
        self,
    ) -> dict[str, Any]:
        """Audit data residency by region."""
        if not self._records:
            return {"status": "no_data"}
        region_data: dict[str, dict[str, int]] = {}
        for r in self._records:
            rgn = r.region or "unknown"
            if rgn not in region_data:
                region_data[rgn] = {
                    "total": 0,
                    "pii": 0,
                    "restricted": 0,
                }
            region_data[rgn]["total"] += 1
            if r.pii_detected:
                region_data[rgn]["pii"] += 1
            if r.sensitivity == DataSensitivity.RESTRICTED:
                region_data[rgn]["restricted"] += 1
        violations: list[str] = []
        for rgn, data in region_data.items():
            if data["pii"] > 0 and rgn == "unknown":
                violations.append("PII data in unknown region")
        return {
            "regions": region_data,
            "violations": violations,
            "total_regions": len(region_data),
        }

    def detect_pii_in_telemetry(
        self,
    ) -> list[dict[str, Any]]:
        """Detect PII in telemetry records."""
        pii_records: list[dict[str, Any]] = []
        for r in self._records:
            if r.pii_detected:
                pii_records.append(
                    {
                        "name": r.name,
                        "service": r.service,
                        "region": r.region,
                        "standard": r.standard.value,
                        "sensitivity": (r.sensitivity.value),
                        "retention": (r.retention.value),
                    }
                )
        return pii_records

    def enforce_retention_rules(
        self,
    ) -> dict[str, Any]:
        """Enforce retention rules per standard."""
        if not self._records:
            return {"status": "no_data"}
        required_retention = {
            ComplianceStandard.GDPR: (RetentionPolicy.DAYS_30),
            ComplianceStandard.HIPAA: (RetentionPolicy.DAYS_365),
            ComplianceStandard.SOX: (RetentionPolicy.DAYS_365),
            ComplianceStandard.PCI: (RetentionPolicy.DAYS_90),
        }
        retention_order = [
            RetentionPolicy.DAYS_30,
            RetentionPolicy.DAYS_90,
            RetentionPolicy.DAYS_365,
            RetentionPolicy.INDEFINITE,
        ]
        violations: list[dict[str, Any]] = []
        compliant_count = 0
        for r in self._records:
            req = required_retention.get(r.standard)
            if req is None:
                compliant_count += 1
                continue
            req_idx = retention_order.index(req)
            act_idx = retention_order.index(r.retention)
            if act_idx < req_idx:
                violations.append(
                    {
                        "name": r.name,
                        "standard": r.standard.value,
                        "required": req.value,
                        "actual": r.retention.value,
                    }
                )
            else:
                compliant_count += 1
        return {
            "total_checked": len(self._records),
            "compliant": compliant_count,
            "violations": len(violations),
            "violation_details": violations[:20],
        }
