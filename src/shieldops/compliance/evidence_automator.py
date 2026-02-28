"""Compliance Evidence Automator — auto-collect compliance evidence."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EvidenceSource(StrEnum):
    PLATFORM_TELEMETRY = "platform_telemetry"
    AUDIT_LOGS = "audit_logs"
    CONFIG_SNAPSHOTS = "config_snapshots"
    ACCESS_RECORDS = "access_records"
    SCAN_RESULTS = "scan_results"


class EvidenceStatus(StrEnum):
    COLLECTED = "collected"
    VALIDATED = "validated"
    EXPIRED = "expired"
    PENDING = "pending"
    REJECTED = "rejected"


class ComplianceFramework(StrEnum):
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    GDPR = "gdpr"


# --- Models ---


class EvidenceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_name: str = ""
    source: EvidenceSource = EvidenceSource.PLATFORM_TELEMETRY
    status: EvidenceStatus = EvidenceStatus.COLLECTED
    framework: ComplianceFramework = ComplianceFramework.SOC2
    freshness_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class EvidenceRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    source: EvidenceSource = EvidenceSource.PLATFORM_TELEMETRY
    framework: ComplianceFramework = ComplianceFramework.SOC2
    collection_frequency_hours: int = 24
    retention_days: float = 365.0
    created_at: float = Field(default_factory=time.time)


class EvidenceAutomatorReport(BaseModel):
    total_evidence: int = 0
    total_rules: int = 0
    collection_rate_pct: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    expired_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceEvidenceAutomator:
    """Auto-collect compliance evidence."""

    def __init__(
        self,
        max_records: int = 200000,
        min_freshness_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._min_freshness_pct = min_freshness_pct
        self._records: list[EvidenceRecord] = []
        self._rules: list[EvidenceRule] = []
        logger.info(
            "evidence_automator.initialized",
            max_records=max_records,
            min_freshness_pct=min_freshness_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_evidence(
        self,
        control_name: str,
        source: EvidenceSource = (EvidenceSource.PLATFORM_TELEMETRY),
        status: EvidenceStatus = EvidenceStatus.COLLECTED,
        framework: ComplianceFramework = (ComplianceFramework.SOC2),
        freshness_score: float = 0.0,
        details: str = "",
    ) -> EvidenceRecord:
        record = EvidenceRecord(
            control_name=control_name,
            source=source,
            status=status,
            framework=framework,
            freshness_score=freshness_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "evidence_automator.evidence_recorded",
            record_id=record.id,
            control_name=control_name,
            source=source.value,
            status=status.value,
        )
        return record

    def get_evidence(self, record_id: str) -> EvidenceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_evidence(
        self,
        control_name: str | None = None,
        source: EvidenceSource | None = None,
        limit: int = 50,
    ) -> list[EvidenceRecord]:
        results = list(self._records)
        if control_name is not None:
            results = [r for r in results if r.control_name == control_name]
        if source is not None:
            results = [r for r in results if r.source == source]
        return results[-limit:]

    def add_rule(
        self,
        rule_name: str,
        source: EvidenceSource = (EvidenceSource.PLATFORM_TELEMETRY),
        framework: ComplianceFramework = (ComplianceFramework.SOC2),
        collection_frequency_hours: int = 24,
        retention_days: float = 365.0,
    ) -> EvidenceRule:
        rule = EvidenceRule(
            rule_name=rule_name,
            source=source,
            framework=framework,
            collection_frequency_hours=(collection_frequency_hours),
            retention_days=retention_days,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "evidence_automator.rule_added",
            rule_name=rule_name,
            source=source.value,
            framework=framework.value,
        )
        return rule

    # -- domain operations -------------------------------------------

    def analyze_evidence_coverage(self, control_name: str) -> dict[str, Any]:
        """Analyze evidence coverage for a control."""
        records = [r for r in self._records if r.control_name == control_name]
        if not records:
            return {
                "control_name": control_name,
                "status": "no_data",
            }
        collected = sum(1 for r in records if r.status == EvidenceStatus.COLLECTED)
        rate = round(collected / len(records) * 100, 2)
        avg_fresh = round(
            sum(r.freshness_score for r in records) / len(records),
            2,
        )
        return {
            "control_name": control_name,
            "evidence_count": len(records),
            "collected_count": collected,
            "collection_rate": rate,
            "avg_freshness": avg_fresh,
            "meets_threshold": (rate >= self._min_freshness_pct),
        }

    def identify_expired_evidence(
        self,
    ) -> list[dict[str, Any]]:
        """Find controls with repeated expired evidence."""
        exp_counts: dict[str, int] = {}
        for r in self._records:
            if r.status in (
                EvidenceStatus.EXPIRED,
                EvidenceStatus.REJECTED,
            ):
                exp_counts[r.control_name] = exp_counts.get(r.control_name, 0) + 1
        results: list[dict[str, Any]] = []
        for ctrl, count in exp_counts.items():
            if count > 1:
                results.append(
                    {
                        "control_name": ctrl,
                        "expired_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["expired_count"],
            reverse=True,
        )
        return results

    def rank_by_freshness(
        self,
    ) -> list[dict[str, Any]]:
        """Rank controls by avg freshness descending."""
        totals: dict[str, list[float]] = {}
        for r in self._records:
            totals.setdefault(r.control_name, []).append(r.freshness_score)
        results: list[dict[str, Any]] = []
        for ctrl, scores in totals.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "control_name": ctrl,
                    "avg_freshness": avg,
                    "evidence_count": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["avg_freshness"],
            reverse=True,
        )
        return results

    def detect_evidence_gaps(
        self,
    ) -> list[dict[str, Any]]:
        """Detect controls with >3 non-COLLECTED."""
        ctrl_non: dict[str, int] = {}
        for r in self._records:
            if r.status != EvidenceStatus.COLLECTED:
                ctrl_non[r.control_name] = ctrl_non.get(r.control_name, 0) + 1
        results: list[dict[str, Any]] = []
        for ctrl, count in ctrl_non.items():
            if count > 3:
                results.append(
                    {
                        "control_name": ctrl,
                        "non_collected_count": count,
                        "gap_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_collected_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> EvidenceAutomatorReport:
        by_source: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_source[r.source.value] = by_source.get(r.source.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        collected = sum(1 for r in self._records if r.status == EvidenceStatus.COLLECTED)
        rate = (
            round(
                collected / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        expired_count = sum(1 for d in self.identify_expired_evidence())
        recs: list[str] = []
        if rate < self._min_freshness_pct:
            recs.append(f"Collection rate {rate}% is below {self._min_freshness_pct}% threshold")
        if expired_count > 0:
            recs.append(f"{expired_count} control(s) with expired evidence")
        gaps = len(self.detect_evidence_gaps())
        if gaps > 0:
            recs.append(f"{gaps} control(s) with evidence gaps")
        if not recs:
            recs.append("Evidence freshness meets targets")
        return EvidenceAutomatorReport(
            total_evidence=len(self._records),
            total_rules=len(self._rules),
            collection_rate_pct=rate,
            by_source=by_source,
            by_status=by_status,
            expired_count=expired_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("evidence_automator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        source_dist: dict[str, int] = {}
        for r in self._records:
            key = r.source.value
            source_dist[key] = source_dist.get(key, 0) + 1
        return {
            "total_evidence": len(self._records),
            "total_rules": len(self._rules),
            "min_freshness_pct": (self._min_freshness_pct),
            "source_distribution": source_dist,
            "unique_controls": len({r.control_name for r in self._records}),
        }
