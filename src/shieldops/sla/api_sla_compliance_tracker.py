"""API SLA Compliance Tracker.

Measure API SLA adherence, detect SLA breach risk,
and generate SLA compliance reports."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ComplianceStatus(StrEnum):
    COMPLIANT = "compliant"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    EXEMPT = "exempt"


class SlaMetric(StrEnum):
    AVAILABILITY = "availability"
    LATENCY_P99 = "latency_p99"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"


class ConsumerTier(StrEnum):
    PLATINUM = "platinum"
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"


# --- Models ---


class SlaComplianceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_name: str = ""
    consumer_id: str = ""
    compliance_status: ComplianceStatus = ComplianceStatus.COMPLIANT
    sla_metric: SlaMetric = SlaMetric.AVAILABILITY
    consumer_tier: ConsumerTier = ConsumerTier.SILVER
    target_value: float = 99.9
    actual_value: float = 99.9
    breach_margin: float = 0.0
    created_at: float = Field(default_factory=time.time)


class SlaComplianceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_name: str = ""
    consumer_id: str = ""
    is_compliant: bool = True
    breach_risk: bool = False
    margin: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SlaComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_breach_margin: float = 0.0
    by_compliance_status: dict[str, int] = Field(default_factory=dict)
    by_sla_metric: dict[str, int] = Field(default_factory=dict)
    by_consumer_tier: dict[str, int] = Field(default_factory=dict)
    breached_apis: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ApiSlaComplianceTracker:
    """Measure SLA adherence, detect breach risk,
    generate compliance reports."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[SlaComplianceRecord] = []
        self._analyses: dict[str, SlaComplianceAnalysis] = {}
        logger.info(
            "api_sla_compliance_tracker.init",
            max_records=max_records,
        )

    def add_record(
        self,
        api_name: str = "",
        consumer_id: str = "",
        compliance_status: ComplianceStatus = (ComplianceStatus.COMPLIANT),
        sla_metric: SlaMetric = (SlaMetric.AVAILABILITY),
        consumer_tier: ConsumerTier = (ConsumerTier.SILVER),
        target_value: float = 99.9,
        actual_value: float = 99.9,
        breach_margin: float = 0.0,
    ) -> SlaComplianceRecord:
        record = SlaComplianceRecord(
            api_name=api_name,
            consumer_id=consumer_id,
            compliance_status=compliance_status,
            sla_metric=sla_metric,
            consumer_tier=consumer_tier,
            target_value=target_value,
            actual_value=actual_value,
            breach_margin=breach_margin,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "sla_compliance.record_added",
            record_id=record.id,
            api_name=api_name,
        )
        return record

    def process(self, key: str) -> SlaComplianceAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_comp = rec.compliance_status == ComplianceStatus.COMPLIANT
        breach_risk = rec.compliance_status in (
            ComplianceStatus.AT_RISK,
            ComplianceStatus.BREACHED,
        )
        margin = round(rec.actual_value - rec.target_value, 2)
        analysis = SlaComplianceAnalysis(
            api_name=rec.api_name,
            consumer_id=rec.consumer_id,
            is_compliant=is_comp,
            breach_risk=breach_risk,
            margin=margin,
            description=(f"API {rec.api_name} margin {margin}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> SlaComplianceReport:
        by_cs: dict[str, int] = {}
        by_sm: dict[str, int] = {}
        by_ct: dict[str, int] = {}
        margins: list[float] = []
        for r in self._records:
            k = r.compliance_status.value
            by_cs[k] = by_cs.get(k, 0) + 1
            k2 = r.sla_metric.value
            by_sm[k2] = by_sm.get(k2, 0) + 1
            k3 = r.consumer_tier.value
            by_ct[k3] = by_ct.get(k3, 0) + 1
            margins.append(r.breach_margin)
        avg = round(sum(margins) / len(margins), 2) if margins else 0.0
        breached = list(
            {r.api_name for r in self._records if r.compliance_status == ComplianceStatus.BREACHED}
        )[:10]
        recs: list[str] = []
        if breached:
            recs.append(f"{len(breached)} APIs with SLA breaches")
        if not recs:
            recs.append("All SLAs compliant")
        return SlaComplianceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_breach_margin=avg,
            by_compliance_status=by_cs,
            by_sla_metric=by_sm,
            by_consumer_tier=by_ct,
            breached_apis=breached,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.compliance_status.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "compliance_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("api_sla_compliance_tracker.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def measure_api_sla_adherence(
        self,
    ) -> list[dict[str, Any]]:
        """Measure SLA adherence per API."""
        api_data: dict[str, list[float]] = {}
        api_target: dict[str, float] = {}
        for r in self._records:
            api_data.setdefault(r.api_name, []).append(r.actual_value)
            api_target[r.api_name] = r.target_value
        results: list[dict[str, Any]] = []
        for api, vals in api_data.items():
            avg = round(sum(vals) / len(vals), 2)
            target = api_target[api]
            adherence = round(avg / max(target, 0.01) * 100, 2)
            results.append(
                {
                    "api_name": api,
                    "avg_actual": avg,
                    "target": target,
                    "adherence_pct": adherence,
                    "sample_count": len(vals),
                }
            )
        results.sort(
            key=lambda x: x["adherence_pct"],
        )
        return results

    def detect_sla_breach_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Detect APIs at risk of SLA breach."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.compliance_status
                in (
                    ComplianceStatus.AT_RISK,
                    ComplianceStatus.BREACHED,
                )
                and r.api_name not in seen
            ):
                seen.add(r.api_name)
                results.append(
                    {
                        "api_name": r.api_name,
                        "status": (r.compliance_status.value),
                        "metric": (r.sla_metric.value),
                        "target": r.target_value,
                        "actual": r.actual_value,
                        "margin": r.breach_margin,
                    }
                )
        results.sort(
            key=lambda x: x["margin"],
        )
        return results

    def generate_sla_compliance_report(
        self,
    ) -> list[dict[str, Any]]:
        """Generate per-tier compliance report."""
        tier_data: dict[str, dict[str, int]] = {}
        for r in self._records:
            tier_data.setdefault(r.consumer_tier.value, {})
            s = r.compliance_status.value
            tier_data[r.consumer_tier.value][s] = tier_data[r.consumer_tier.value].get(s, 0) + 1
        results: list[dict[str, Any]] = []
        for tier, statuses in tier_data.items():
            total = sum(statuses.values())
            compliant = statuses.get("compliant", 0)
            rate = round(compliant / max(total, 1) * 100, 2)
            results.append(
                {
                    "tier": tier,
                    "compliance_rate": rate,
                    "total_records": total,
                    "status_counts": statuses,
                }
            )
        results.sort(
            key=lambda x: x["compliance_rate"],
        )
        return results
