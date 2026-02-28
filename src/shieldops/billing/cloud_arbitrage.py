"""Cloud Cost Arbitrage Analyzer — analyze cross-cloud pricing for workload migration savings."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CloudProvider(StrEnum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    ON_PREM = "on_prem"
    HYBRID = "hybrid"


class WorkloadType(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    DATABASE = "database"
    NETWORKING = "networking"
    ML_TRAINING = "ml_training"


class SavingsConfidence(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    SPECULATIVE = "speculative"
    NO_SAVINGS = "no_savings"


# --- Models ---


class ArbitrageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    current_provider: CloudProvider = CloudProvider.AWS
    workload_type: WorkloadType = WorkloadType.COMPUTE
    savings_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class MigrationOpportunity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    opportunity_name: str = ""
    target_provider: CloudProvider = CloudProvider.GCP
    workload_type: WorkloadType = WorkloadType.COMPUTE
    estimated_savings_usd: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CloudArbitrageReport(BaseModel):
    total_records: int = 0
    total_opportunities: int = 0
    avg_savings_pct: float = 0.0
    by_provider: dict[str, int] = Field(default_factory=dict)
    by_workload: dict[str, int] = Field(default_factory=dict)
    high_savings_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CloudCostArbitrageAnalyzer:
    """Analyze cross-cloud pricing for workload migration savings."""

    def __init__(
        self,
        max_records: int = 200000,
        min_savings_pct: float = 15.0,
    ) -> None:
        self._max_records = max_records
        self._min_savings_pct = min_savings_pct
        self._records: list[ArbitrageRecord] = []
        self._opportunities: list[MigrationOpportunity] = []
        logger.info(
            "cloud_arbitrage.initialized",
            max_records=max_records,
            min_savings_pct=min_savings_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_arbitrage(
        self,
        service_name: str,
        current_provider: CloudProvider = CloudProvider.AWS,
        workload_type: WorkloadType = WorkloadType.COMPUTE,
        savings_pct: float = 0.0,
        details: str = "",
    ) -> ArbitrageRecord:
        record = ArbitrageRecord(
            service_name=service_name,
            current_provider=current_provider,
            workload_type=workload_type,
            savings_pct=savings_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cloud_arbitrage.recorded",
            record_id=record.id,
            service_name=service_name,
            current_provider=current_provider.value,
        )
        return record

    def get_arbitrage(self, record_id: str) -> ArbitrageRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_arbitrages(
        self,
        service_name: str | None = None,
        current_provider: CloudProvider | None = None,
        limit: int = 50,
    ) -> list[ArbitrageRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if current_provider is not None:
            results = [r for r in results if r.current_provider == current_provider]
        return results[-limit:]

    def add_opportunity(
        self,
        opportunity_name: str,
        target_provider: CloudProvider = CloudProvider.GCP,
        workload_type: WorkloadType = WorkloadType.COMPUTE,
        estimated_savings_usd: float = 0.0,
        description: str = "",
    ) -> MigrationOpportunity:
        opp = MigrationOpportunity(
            opportunity_name=opportunity_name,
            target_provider=target_provider,
            workload_type=workload_type,
            estimated_savings_usd=estimated_savings_usd,
            description=description,
        )
        self._opportunities.append(opp)
        if len(self._opportunities) > self._max_records:
            self._opportunities = self._opportunities[-self._max_records :]
        logger.info(
            "cloud_arbitrage.opportunity_added",
            opportunity_name=opportunity_name,
            target_provider=target_provider.value,
        )
        return opp

    # -- domain operations -----------------------------------------------

    def analyze_savings_potential(self, service_name: str) -> dict[str, Any]:
        """Analyze savings potential for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {
                "service_name": service_name,
                "status": "no_data",
            }
        total_savings = sum(r.savings_pct for r in records)
        avg_savings = round(total_savings / len(records), 2)
        return {
            "service_name": service_name,
            "avg_savings_pct": avg_savings,
            "record_count": len(records),
            "meets_threshold": avg_savings >= self._min_savings_pct,
        }

    def identify_high_savings_services(self) -> list[dict[str, Any]]:
        """Find services with more than one record above savings threshold."""
        by_service: dict[str, list[float]] = {}
        for r in self._records:
            by_service.setdefault(r.service_name, []).append(r.savings_pct)
        results: list[dict[str, Any]] = []
        for service, savings in by_service.items():
            high_count = sum(1 for s in savings if s >= self._min_savings_pct)
            if high_count > 1:
                results.append(
                    {
                        "service_name": service,
                        "high_savings_count": high_count,
                        "avg_savings_pct": round(sum(savings) / len(savings), 2),
                    }
                )
        results.sort(key=lambda x: x["avg_savings_pct"], reverse=True)
        return results

    def rank_by_savings(self) -> list[dict[str, Any]]:
        """Rank services by average savings percentage (descending)."""
        by_service: dict[str, list[float]] = {}
        for r in self._records:
            by_service.setdefault(r.service_name, []).append(r.savings_pct)
        results: list[dict[str, Any]] = []
        for service, savings in by_service.items():
            avg_savings = round(sum(savings) / len(savings), 2)
            results.append(
                {
                    "service_name": service,
                    "avg_savings_pct": avg_savings,
                    "record_count": len(savings),
                }
            )
        results.sort(key=lambda x: x["avg_savings_pct"], reverse=True)
        return results

    def detect_arbitrage_trends(self) -> list[dict[str, Any]]:
        """Detect savings trends for services with more than 3 records."""
        by_service: dict[str, list[ArbitrageRecord]] = {}
        for r in self._records:
            by_service.setdefault(r.service_name, []).append(r)
        results: list[dict[str, Any]] = []
        for service, records in by_service.items():
            if len(records) <= 3:
                continue
            mid = len(records) // 2
            older_avg = sum(r.savings_pct for r in records[:mid]) / mid
            recent_avg = sum(r.savings_pct for r in records[mid:]) / (len(records) - mid)
            if older_avg == 0:
                trend = SavingsConfidence.NO_SAVINGS
            else:
                change_pct = ((recent_avg - older_avg) / older_avg) * 100
                if change_pct > 20:
                    trend = SavingsConfidence.HIGH
                elif change_pct < -20:
                    trend = SavingsConfidence.LOW
                elif abs(change_pct) <= 20:
                    trend = SavingsConfidence.MODERATE
                else:
                    trend = SavingsConfidence.SPECULATIVE
            results.append(
                {
                    "service_name": service,
                    "trend": trend.value,
                    "older_avg_savings": round(older_avg, 2),
                    "recent_avg_savings": round(recent_avg, 2),
                    "record_count": len(records),
                }
            )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> CloudArbitrageReport:
        by_provider: dict[str, int] = {}
        by_workload: dict[str, int] = {}
        for r in self._records:
            by_provider[r.current_provider.value] = by_provider.get(r.current_provider.value, 0) + 1
            by_workload[r.workload_type.value] = by_workload.get(r.workload_type.value, 0) + 1
        avg_savings = (
            round(
                sum(r.savings_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        high_savings = sum(1 for r in self._records if r.savings_pct >= self._min_savings_pct)
        recs: list[str] = []
        if high_savings > 0:
            recs.append(f"{high_savings} service(s) with savings >= {self._min_savings_pct}%")
        if avg_savings < self._min_savings_pct and self._records:
            recs.append(f"Average savings {avg_savings}% below target {self._min_savings_pct}%")
        if not recs:
            recs.append("Cloud arbitrage analysis meets savings targets")
        return CloudArbitrageReport(
            total_records=len(self._records),
            total_opportunities=len(self._opportunities),
            avg_savings_pct=avg_savings,
            by_provider=by_provider,
            by_workload=by_workload,
            high_savings_count=high_savings,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._opportunities.clear()
        logger.info("cloud_arbitrage.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        provider_dist: dict[str, int] = {}
        for r in self._records:
            key = r.current_provider.value
            provider_dist[key] = provider_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_opportunities": len(self._opportunities),
            "min_savings_pct": self._min_savings_pct,
            "provider_distribution": provider_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
