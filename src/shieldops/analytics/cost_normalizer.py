"""Multi-cloud cost normalization for cross-provider comparison.

Normalizes pricing across AWS, GCP, and Azure so that equivalent workloads can
be compared side-by-side with recommendations for the cheapest provider.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class CloudProvider(enum.StrEnum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"


class ResourceCategory(enum.StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    SERVERLESS = "serverless"
    CONTAINER = "container"


# -- Models --------------------------------------------------------------------


class PricingEntry(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    provider: CloudProvider
    category: ResourceCategory
    resource_type: str
    unit: str = "hour"
    price_per_unit: float
    region: str = "us-east-1"
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: float = Field(default_factory=time.time)


class CostComparison(BaseModel):
    resource_type: str
    category: ResourceCategory
    providers: dict[str, float] = Field(default_factory=dict)
    cheapest: str = ""
    savings_pct: float = 0.0


class NormalizationResult(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    workload_name: str
    comparisons: list[CostComparison] = Field(default_factory=list)
    total_by_provider: dict[str, float] = Field(default_factory=dict)
    recommended_provider: str = ""
    monthly_savings: float = 0.0
    analyzed_at: float = Field(default_factory=time.time)


# -- Engine --------------------------------------------------------------------


class CostNormalizer:
    """Normalize and compare cloud pricing across providers.

    Parameters
    ----------
    max_pricing_entries:
        Maximum number of pricing entries to store.
    """

    def __init__(self, max_pricing_entries: int = 10000) -> None:
        self._pricing: dict[str, PricingEntry] = {}
        self._max_pricing_entries = max_pricing_entries

    def add_pricing(
        self,
        provider: CloudProvider,
        category: ResourceCategory,
        resource_type: str,
        price_per_unit: float,
        unit: str = "hour",
        region: str = "us-east-1",
        metadata: dict[str, Any] | None = None,
    ) -> PricingEntry:
        if len(self._pricing) >= self._max_pricing_entries:
            raise ValueError(f"Maximum pricing entries limit reached: {self._max_pricing_entries}")
        entry = PricingEntry(
            provider=provider,
            category=category,
            resource_type=resource_type,
            price_per_unit=price_per_unit,
            unit=unit,
            region=region,
            metadata=metadata or {},
        )
        self._pricing[entry.id] = entry
        logger.info(
            "pricing_entry_added",
            entry_id=entry.id,
            provider=provider,
            resource_type=resource_type,
        )
        return entry

    def compare_resource(
        self,
        resource_type: str,
        category: ResourceCategory,
    ) -> CostComparison:
        providers: dict[str, float] = {}
        for entry in self._pricing.values():
            if entry.resource_type == resource_type and entry.category == category:
                providers[entry.provider] = entry.price_per_unit

        cheapest = ""
        savings_pct = 0.0
        if providers:
            cheapest = min(providers, key=providers.get)  # type: ignore[arg-type]
            most_expensive = max(providers.values())
            if most_expensive > 0:
                savings_pct = round(
                    (most_expensive - providers[cheapest]) / most_expensive * 100, 2
                )

        return CostComparison(
            resource_type=resource_type,
            category=category,
            providers=providers,
            cheapest=cheapest,
            savings_pct=savings_pct,
        )

    def analyze_workload(
        self,
        workload_name: str,
        resources: list[dict[str, Any]],
    ) -> NormalizationResult:
        comparisons: list[CostComparison] = []
        total_by_provider: dict[str, float] = {}

        for resource in resources:
            resource_type = resource.get("resource_type", "")
            category = ResourceCategory(resource.get("category", "compute"))
            quantity = resource.get("quantity", 1)
            hours = resource.get("hours", 730)  # default ~1 month

            comparison = self.compare_resource(resource_type, category)
            comparisons.append(comparison)

            for prov, price in comparison.providers.items():
                cost = price * quantity * hours
                total_by_provider[prov] = total_by_provider.get(prov, 0.0) + cost

        # Round totals
        total_by_provider = {k: round(v, 2) for k, v in total_by_provider.items()}

        recommended = ""
        monthly_savings = 0.0
        if total_by_provider:
            recommended = min(total_by_provider, key=total_by_provider.get)  # type: ignore[arg-type]
            most_expensive = max(total_by_provider.values())
            monthly_savings = round(most_expensive - total_by_provider[recommended], 2)

        result = NormalizationResult(
            workload_name=workload_name,
            comparisons=comparisons,
            total_by_provider=total_by_provider,
            recommended_provider=recommended,
            monthly_savings=monthly_savings,
        )
        logger.info(
            "workload_analyzed",
            workload=workload_name,
            recommended=recommended,
            monthly_savings=monthly_savings,
        )
        return result

    def get_pricing(
        self,
        provider: CloudProvider | None = None,
        category: ResourceCategory | None = None,
    ) -> list[PricingEntry]:
        entries = list(self._pricing.values())
        if provider:
            entries = [e for e in entries if e.provider == provider]
        if category:
            entries = [e for e in entries if e.category == category]
        return entries

    def update_pricing(
        self,
        pricing_id: str,
        price_per_unit: float,
    ) -> PricingEntry | None:
        entry = self._pricing.get(pricing_id)
        if entry is None:
            return None
        entry.price_per_unit = price_per_unit
        entry.updated_at = time.time()
        logger.info("pricing_updated", entry_id=pricing_id, price=price_per_unit)
        return entry

    def delete_pricing(self, pricing_id: str) -> bool:
        return self._pricing.pop(pricing_id, None) is not None

    def get_cheapest_provider(self, category: ResourceCategory) -> dict[str, Any]:
        entries = [e for e in self._pricing.values() if e.category == category]
        if not entries:
            return {"category": category, "cheapest_provider": "", "avg_price": 0.0}

        provider_prices: dict[str, list[float]] = {}
        for entry in entries:
            provider_prices.setdefault(entry.provider, []).append(entry.price_per_unit)

        avg_by_provider = {
            p: round(sum(prices) / len(prices), 4) for p, prices in provider_prices.items()
        }
        cheapest = min(avg_by_provider, key=avg_by_provider.get)  # type: ignore[arg-type]

        return {
            "category": category,
            "cheapest_provider": cheapest,
            "avg_price": avg_by_provider[cheapest],
            "all_providers": avg_by_provider,
        }

    def get_stats(self) -> dict[str, Any]:
        providers = {e.provider for e in self._pricing.values()}
        categories = {e.category for e in self._pricing.values()}
        return {
            "total_pricing_entries": len(self._pricing),
            "providers": len(providers),
            "categories": len(categories),
        }
