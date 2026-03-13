"""Intelligent Waste Classifier
classify waste categories, estimate recovery value,
prioritize waste remediation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class WasteCategory(StrEnum):
    ORPHANED = "orphaned"
    OVERSIZED = "oversized"
    IDLE = "idle"
    ZOMBIE = "zombie"


class RemediationComplexity(StrEnum):
    TRIVIAL = "trivial"
    MODERATE = "moderate"
    COMPLEX = "complex"
    RISKY = "risky"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


# --- Models ---


class WasteRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    waste_category: WasteCategory = WasteCategory.IDLE
    remediation_complexity: RemediationComplexity = RemediationComplexity.MODERATE
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    monthly_waste: float = 0.0
    resource_type: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class WasteAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    waste_category: WasteCategory = WasteCategory.IDLE
    recovery_value: float = 0.0
    priority_score: float = 0.0
    remediation_complexity: RemediationComplexity = RemediationComplexity.MODERATE
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class WasteReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    total_monthly_waste: float = 0.0
    by_waste_category: dict[str, int] = Field(default_factory=dict)
    by_complexity: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IntelligentWasteClassifier:
    """Classify waste categories, estimate recovery,
    prioritize remediation."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[WasteRecord] = []
        self._analyses: dict[str, WasteAnalysis] = {}
        logger.info(
            "intelligent_waste_classifier.init",
            max_records=max_records,
        )

    def add_record(
        self,
        resource_id: str = "",
        waste_category: WasteCategory = (WasteCategory.IDLE),
        remediation_complexity: RemediationComplexity = (RemediationComplexity.MODERATE),
        confidence_level: ConfidenceLevel = (ConfidenceLevel.MEDIUM),
        monthly_waste: float = 0.0,
        resource_type: str = "",
        description: str = "",
    ) -> WasteRecord:
        record = WasteRecord(
            resource_id=resource_id,
            waste_category=waste_category,
            remediation_complexity=(remediation_complexity),
            confidence_level=confidence_level,
            monthly_waste=monthly_waste,
            resource_type=resource_type,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "waste_classifier.record_added",
            record_id=record.id,
            resource_id=resource_id,
        )
        return record

    def process(self, key: str) -> WasteAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        complexity_mult = {
            RemediationComplexity.TRIVIAL: 1.0,
            RemediationComplexity.MODERATE: 0.8,
            RemediationComplexity.COMPLEX: 0.6,
            RemediationComplexity.RISKY: 0.4,
        }
        mult = complexity_mult.get(rec.remediation_complexity, 0.8)
        recovery = round(rec.monthly_waste * 12 * mult, 2)
        priority = round(rec.monthly_waste * mult * 100, 2)
        analysis = WasteAnalysis(
            resource_id=rec.resource_id,
            waste_category=rec.waste_category,
            recovery_value=recovery,
            priority_score=priority,
            remediation_complexity=(rec.remediation_complexity),
            description=(f"Waste {rec.resource_id} ${rec.monthly_waste}/mo"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> WasteReport:
        by_wc: dict[str, int] = {}
        by_cx: dict[str, int] = {}
        by_cf: dict[str, int] = {}
        total_waste = 0.0
        for r in self._records:
            k = r.waste_category.value
            by_wc[k] = by_wc.get(k, 0) + 1
            k2 = r.remediation_complexity.value
            by_cx[k2] = by_cx.get(k2, 0) + 1
            k3 = r.confidence_level.value
            by_cf[k3] = by_cf.get(k3, 0) + 1
            total_waste += r.monthly_waste
        recs: list[str] = []
        if total_waste > 0:
            recs.append(f"${round(total_waste, 2)}/mo recoverable waste identified")
        if not recs:
            recs.append("No significant waste found")
        return WasteReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            total_monthly_waste=round(total_waste, 2),
            by_waste_category=by_wc,
            by_complexity=by_cx,
            by_confidence=by_cf,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        wc_dist: dict[str, int] = {}
        for r in self._records:
            k = r.waste_category.value
            wc_dist[k] = wc_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "waste_category_distribution": wc_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("intelligent_waste_classifier.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def classify_waste_category(
        self,
    ) -> list[dict[str, Any]]:
        """Classify waste by category."""
        cat_map: dict[str, list[float]] = {}
        for r in self._records:
            k = r.waste_category.value
            cat_map.setdefault(k, []).append(r.monthly_waste)
        results: list[dict[str, Any]] = []
        for cat, wastes in cat_map.items():
            total = round(sum(wastes), 2)
            results.append(
                {
                    "category": cat,
                    "count": len(wastes),
                    "total_waste": total,
                    "avg_waste": round(total / len(wastes), 2),
                }
            )
        results.sort(
            key=lambda x: x["total_waste"],
            reverse=True,
        )
        return results

    def estimate_waste_recovery_value(
        self,
    ) -> list[dict[str, Any]]:
        """Estimate annual recovery value."""
        res_map: dict[str, float] = {}
        res_cat: dict[str, str] = {}
        for r in self._records:
            res_map[r.resource_id] = res_map.get(r.resource_id, 0.0) + r.monthly_waste
            res_cat[r.resource_id] = r.waste_category.value
        results: list[dict[str, Any]] = []
        for rid, monthly in res_map.items():
            results.append(
                {
                    "resource_id": rid,
                    "category": res_cat[rid],
                    "monthly_waste": round(monthly, 2),
                    "annual_recovery": round(monthly * 12, 2),
                }
            )
        results.sort(
            key=lambda x: x["annual_recovery"],
            reverse=True,
        )
        return results

    def prioritize_waste_remediation(
        self,
    ) -> list[dict[str, Any]]:
        """Prioritize waste by value and ease."""
        complexity_weight = {
            RemediationComplexity.TRIVIAL: 4,
            RemediationComplexity.MODERATE: 3,
            RemediationComplexity.COMPLEX: 2,
            RemediationComplexity.RISKY: 1,
        }
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.resource_id not in seen:
                seen.add(r.resource_id)
                w = complexity_weight.get(r.remediation_complexity, 2)
                score = round(r.monthly_waste * w, 2)
                results.append(
                    {
                        "resource_id": (r.resource_id),
                        "category": (r.waste_category.value),
                        "complexity": (r.remediation_complexity.value),
                        "priority_score": score,
                    }
                )
        results.sort(
            key=lambda x: x["priority_score"],
            reverse=True,
        )
        return results
