"""Multi Cloud Cost Normalizer
normalize billing taxonomy, reconcile cross-cloud
spend, generate unified cost view."""

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
    ON_PREMISES = "on_premises"


class CostCategory(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    MANAGED_SERVICE = "managed_service"


class NormalizationStatus(StrEnum):
    MAPPED = "mapped"
    APPROXIMATED = "approximated"
    UNMAPPED = "unmapped"
    EXCLUDED = "excluded"


# --- Models ---


class CloudCostRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str = ""
    cloud_provider: CloudProvider = CloudProvider.AWS
    cost_category: CostCategory = CostCategory.COMPUTE
    normalization_status: NormalizationStatus = NormalizationStatus.MAPPED
    raw_cost: float = 0.0
    normalized_cost: float = 0.0
    service_name: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CloudCostAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str = ""
    cloud_provider: CloudProvider = CloudProvider.AWS
    raw_cost: float = 0.0
    normalized_cost: float = 0.0
    normalization_status: NormalizationStatus = NormalizationStatus.MAPPED
    variance_pct: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CloudCostReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    total_normalized_cost: float = 0.0
    by_cloud_provider: dict[str, int] = Field(default_factory=dict)
    by_cost_category: dict[str, int] = Field(default_factory=dict)
    by_normalization_status: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MultiCloudCostNormalizer:
    """Normalize billing taxonomy, reconcile
    cross-cloud spend, generate unified view."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CloudCostRecord] = []
        self._analyses: dict[str, CloudCostAnalysis] = {}
        logger.info(
            "multi_cloud_cost_normalizer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        account_id: str = "",
        cloud_provider: CloudProvider = (CloudProvider.AWS),
        cost_category: CostCategory = (CostCategory.COMPUTE),
        normalization_status: NormalizationStatus = (NormalizationStatus.MAPPED),
        raw_cost: float = 0.0,
        normalized_cost: float = 0.0,
        service_name: str = "",
        description: str = "",
    ) -> CloudCostRecord:
        record = CloudCostRecord(
            account_id=account_id,
            cloud_provider=cloud_provider,
            cost_category=cost_category,
            normalization_status=(normalization_status),
            raw_cost=raw_cost,
            normalized_cost=normalized_cost,
            service_name=service_name,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "multi_cloud_cost.record_added",
            record_id=record.id,
            account_id=account_id,
        )
        return record

    def process(self, key: str) -> CloudCostAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        var = 0.0
        if rec.raw_cost > 0:
            var = round(
                abs(rec.normalized_cost - rec.raw_cost) / rec.raw_cost * 100,
                2,
            )
        analysis = CloudCostAnalysis(
            account_id=rec.account_id,
            cloud_provider=rec.cloud_provider,
            raw_cost=rec.raw_cost,
            normalized_cost=rec.normalized_cost,
            normalization_status=(rec.normalization_status),
            variance_pct=var,
            description=(f"Normalized {rec.account_id} var {var}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CloudCostReport:
        by_cp: dict[str, int] = {}
        by_cc: dict[str, int] = {}
        by_ns: dict[str, int] = {}
        total_norm = 0.0
        for r in self._records:
            k = r.cloud_provider.value
            by_cp[k] = by_cp.get(k, 0) + 1
            k2 = r.cost_category.value
            by_cc[k2] = by_cc.get(k2, 0) + 1
            k3 = r.normalization_status.value
            by_ns[k3] = by_ns.get(k3, 0) + 1
            total_norm += r.normalized_cost
        recs: list[str] = []
        unmapped = [
            r for r in self._records if r.normalization_status == NormalizationStatus.UNMAPPED
        ]
        if unmapped:
            recs.append(f"{len(unmapped)} unmapped cost items need mapping")
        if not recs:
            recs.append("All costs normalized")
        return CloudCostReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            total_normalized_cost=round(total_norm, 2),
            by_cloud_provider=by_cp,
            by_cost_category=by_cc,
            by_normalization_status=by_ns,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        cp_dist: dict[str, int] = {}
        for r in self._records:
            k = r.cloud_provider.value
            cp_dist[k] = cp_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "cloud_provider_distribution": cp_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("multi_cloud_cost_normalizer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def normalize_billing_taxonomy(
        self,
    ) -> list[dict[str, Any]]:
        """Normalize billing across providers."""
        prov_map: dict[str, list[float]] = {}
        prov_norm: dict[str, list[float]] = {}
        for r in self._records:
            k = r.cloud_provider.value
            prov_map.setdefault(k, []).append(r.raw_cost)
            prov_norm.setdefault(k, []).append(r.normalized_cost)
        results: list[dict[str, Any]] = []
        for prov, raws in prov_map.items():
            norms = prov_norm[prov]
            results.append(
                {
                    "provider": prov,
                    "total_raw": round(sum(raws), 2),
                    "total_normalized": round(sum(norms), 2),
                    "item_count": len(raws),
                }
            )
        return results

    def reconcile_cross_cloud_spend(
        self,
    ) -> list[dict[str, Any]]:
        """Reconcile spend across clouds."""
        cat_map: dict[str, dict[str, float]] = {}
        for r in self._records:
            cat = r.cost_category.value
            prov = r.cloud_provider.value
            if cat not in cat_map:
                cat_map[cat] = {}
            cat_map[cat][prov] = cat_map[cat].get(prov, 0.0) + r.normalized_cost
        results: list[dict[str, Any]] = []
        for cat, provs in cat_map.items():
            total = round(sum(provs.values()), 2)
            results.append(
                {
                    "category": cat,
                    "by_provider": {k: round(v, 2) for k, v in provs.items()},
                    "total": total,
                }
            )
        results.sort(key=lambda x: x["total"], reverse=True)
        return results

    def generate_unified_cost_view(
        self,
    ) -> list[dict[str, Any]]:
        """Generate unified cost view."""
        acct_map: dict[str, float] = {}
        acct_prov: dict[str, str] = {}
        for r in self._records:
            acct_map[r.account_id] = acct_map.get(r.account_id, 0.0) + r.normalized_cost
            acct_prov[r.account_id] = r.cloud_provider.value
        results: list[dict[str, Any]] = []
        for aid, total in acct_map.items():
            results.append(
                {
                    "account_id": aid,
                    "provider": acct_prov[aid],
                    "total_cost": round(total, 2),
                }
            )
        results.sort(
            key=lambda x: x["total_cost"],
            reverse=True,
        )
        return results
