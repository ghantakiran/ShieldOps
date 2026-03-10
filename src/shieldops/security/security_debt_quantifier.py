"""Security Debt Quantifier
quantify security debt, compute debt interest rate,
prioritize debt reduction."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DebtCategory(StrEnum):
    VULNERABILITY = "vulnerability"
    CONFIGURATION = "configuration"
    PROCESS = "process"
    ARCHITECTURE = "architecture"


class DebtPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RemediationEffort(StrEnum):
    TRIVIAL = "trivial"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"


# --- Models ---


class SecurityDebtRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    debt_id: str = ""
    category: DebtCategory = DebtCategory.VULNERABILITY
    priority: DebtPriority = DebtPriority.MEDIUM
    effort: RemediationEffort = RemediationEffort.MODERATE
    debt_score: float = 0.0
    age_days: int = 0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SecurityDebtAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    debt_id: str = ""
    category: DebtCategory = DebtCategory.VULNERABILITY
    analysis_score: float = 0.0
    interest_rate: float = 0.0
    compounded_debt: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SecurityDebtReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    total_debt_score: float = 0.0
    avg_age_days: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    by_effort: dict[str, int] = Field(default_factory=dict)
    critical_debts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityDebtQuantifier:
    """Quantify security debt, compute debt interest
    rate, prioritize debt reduction."""

    def __init__(
        self,
        max_records: int = 200000,
        debt_threshold: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._debt_threshold = debt_threshold
        self._records: list[SecurityDebtRecord] = []
        self._analyses: list[SecurityDebtAnalysis] = []
        logger.info(
            "security_debt_quantifier.initialized",
            max_records=max_records,
            debt_threshold=debt_threshold,
        )

    def add_record(
        self,
        debt_id: str,
        category: DebtCategory = (DebtCategory.VULNERABILITY),
        priority: DebtPriority = DebtPriority.MEDIUM,
        effort: RemediationEffort = (RemediationEffort.MODERATE),
        debt_score: float = 0.0,
        age_days: int = 0,
        service: str = "",
        team: str = "",
    ) -> SecurityDebtRecord:
        record = SecurityDebtRecord(
            debt_id=debt_id,
            category=category,
            priority=priority,
            effort=effort,
            debt_score=debt_score,
            age_days=age_days,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_debt_quantifier.record_added",
            record_id=record.id,
            debt_id=debt_id,
        )
        return record

    def process(self, key: str) -> SecurityDebtAnalysis | None:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return None
        rate = round(0.01 * max(1, rec.age_days / 30), 4)
        compounded = round(rec.debt_score * (1.0 + rate), 2)
        analysis = SecurityDebtAnalysis(
            debt_id=rec.debt_id,
            category=rec.category,
            analysis_score=round(rec.debt_score, 2),
            interest_rate=rate,
            compounded_debt=compounded,
            description=(f"Debt {rec.debt_id} compounded to {compounded}"),
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return analysis

    def generate_report(self) -> SecurityDebtReport:
        by_cat: dict[str, int] = {}
        by_pri: dict[str, int] = {}
        by_eff: dict[str, int] = {}
        total_debt = 0.0
        ages: list[int] = []
        for r in self._records:
            c = r.category.value
            by_cat[c] = by_cat.get(c, 0) + 1
            p = r.priority.value
            by_pri[p] = by_pri.get(p, 0) + 1
            e = r.effort.value
            by_eff[e] = by_eff.get(e, 0) + 1
            total_debt += r.debt_score
            ages.append(r.age_days)
        avg_age = round(sum(ages) / len(ages), 2) if ages else 0.0
        critical = [r.debt_id for r in self._records if r.debt_score >= self._debt_threshold][:5]
        recs: list[str] = []
        if critical:
            recs.append(f"{len(critical)} debts above threshold")
        if not recs:
            recs.append("Security debt is manageable")
        return SecurityDebtReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            total_debt_score=round(total_debt, 2),
            avg_age_days=avg_age,
            by_category=by_cat,
            by_priority=by_pri,
            by_effort=by_eff,
            critical_debts=critical,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            k = r.category.value
            cat_dist[k] = cat_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "debt_threshold": self._debt_threshold,
            "category_distribution": cat_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_debt_quantifier.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def quantify_security_debt(
        self,
    ) -> list[dict[str, Any]]:
        """Quantify security debt per category."""
        cat_data: dict[str, list[float]] = {}
        cat_ages: dict[str, list[int]] = {}
        for r in self._records:
            k = r.category.value
            cat_data.setdefault(k, []).append(r.debt_score)
            cat_ages.setdefault(k, []).append(r.age_days)
        results: list[dict[str, Any]] = []
        for cat, scores in cat_data.items():
            total = round(sum(scores), 2)
            avg = round(total / len(scores), 2)
            avg_age = round(
                sum(cat_ages[cat]) / len(cat_ages[cat]),
                1,
            )
            results.append(
                {
                    "category": cat,
                    "total_debt": total,
                    "avg_debt": avg,
                    "avg_age_days": avg_age,
                    "count": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["total_debt"],
            reverse=True,
        )
        return results

    def compute_debt_interest_rate(
        self,
    ) -> dict[str, Any]:
        """Compute interest rate based on age."""
        if not self._records:
            return {
                "avg_interest_rate": 0.0,
                "by_category": {},
            }
        cat_rates: dict[str, list[float]] = {}
        for r in self._records:
            rate = 0.01 * max(1, r.age_days / 30)
            k = r.category.value
            cat_rates.setdefault(k, []).append(rate)
        by_cat: dict[str, float] = {}
        all_rates: list[float] = []
        for c, rates in cat_rates.items():
            avg = round(sum(rates) / len(rates), 4)
            by_cat[c] = avg
            all_rates.extend(rates)
        avg_all = round(sum(all_rates) / len(all_rates), 4) if all_rates else 0.0
        return {
            "avg_interest_rate": avg_all,
            "by_category": by_cat,
        }

    def prioritize_debt_reduction(
        self,
    ) -> list[dict[str, Any]]:
        """Prioritize debt reduction by score
        and effort."""
        effort_w = {
            "trivial": 1.0,
            "minor": 2.0,
            "moderate": 3.0,
            "major": 4.0,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            w = effort_w.get(r.effort.value, 2.0)
            roi = round(r.debt_score / w, 2)
            results.append(
                {
                    "debt_id": r.debt_id,
                    "category": r.category.value,
                    "priority": r.priority.value,
                    "debt_score": r.debt_score,
                    "effort": r.effort.value,
                    "reduction_roi": roi,
                }
            )
        results.sort(
            key=lambda x: x["reduction_roi"],
            reverse=True,
        )
        return results
