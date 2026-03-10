"""ServiceLevelIntelligence — SLO intelligence."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SloMaturity(StrEnum):
    ADHOC = "adhoc"
    DEFINED = "defined"
    MEASURED = "measured"
    OPTIMIZED = "optimized"


class ErrorBudgetStatus(StrEnum):
    HEALTHY = "healthy"
    CONSUMING = "consuming"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"


class ReliabilityTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    VOLATILE = "volatile"


# --- Models ---


class SloRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    maturity: SloMaturity = SloMaturity.DEFINED
    budget_status: ErrorBudgetStatus = ErrorBudgetStatus.HEALTHY
    trend: ReliabilityTrend = ReliabilityTrend.STABLE
    score: float = 0.0
    error_budget_remaining: float = 100.0
    burn_rate: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SloAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    maturity: SloMaturity = SloMaturity.DEFINED
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SloReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    avg_budget_remaining: float = 0.0
    by_maturity: dict[str, int] = Field(default_factory=dict)
    by_budget_status: dict[str, int] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceLevelIntelligence:
    """Service Level Intelligence.

    Provides intelligence on SLOs, error budgets,
    and reliability trends across services.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[SloRecord] = []
        self._analyses: list[SloAnalysis] = []
        logger.info(
            "service_level_intelligence.init",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        maturity: SloMaturity = SloMaturity.DEFINED,
        budget_status: ErrorBudgetStatus = (ErrorBudgetStatus.HEALTHY),
        trend: ReliabilityTrend = (ReliabilityTrend.STABLE),
        score: float = 0.0,
        error_budget_remaining: float = 100.0,
        burn_rate: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SloRecord:
        record = SloRecord(
            name=name,
            maturity=maturity,
            budget_status=budget_status,
            trend=trend,
            score=score,
            error_budget_remaining=(error_budget_remaining),
            burn_rate=burn_rate,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "service_level_intelligence.added",
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
        budgets = [r.error_budget_remaining for r in matching]
        avg_budget = round(sum(budgets) / len(budgets), 2)
        return {
            "key": key,
            "record_count": len(matching),
            "avg_score": avg,
            "avg_budget_remaining": avg_budget,
        }

    def generate_report(self) -> SloReport:
        by_m: dict[str, int] = {}
        by_b: dict[str, int] = {}
        by_t: dict[str, int] = {}
        for r in self._records:
            v1 = r.maturity.value
            by_m[v1] = by_m.get(v1, 0) + 1
            v2 = r.budget_status.value
            by_b[v2] = by_b.get(v2, 0) + 1
            v3 = r.trend.value
            by_t[v3] = by_t.get(v3, 0) + 1
        scores = [r.score for r in self._records]
        avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
        budgets = [r.error_budget_remaining for r in self._records]
        avg_b = round(sum(budgets) / len(budgets), 2) if budgets else 0.0
        recs: list[str] = []
        exhausted = by_b.get("exhausted", 0)
        critical = by_b.get("critical", 0)
        if exhausted > 0:
            recs.append(f"{exhausted} SLO(s) budget exhausted")
        if critical > 0:
            recs.append(f"{critical} SLO(s) budget critical")
        declining = by_t.get("declining", 0)
        if declining > 0:
            recs.append(f"{declining} SLO(s) declining")
        if not recs:
            recs.append("Service level intelligence healthy")
        return SloReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg_s,
            avg_budget_remaining=avg_b,
            by_maturity=by_m,
            by_budget_status=by_b,
            by_trend=by_t,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        m_dist: dict[str, int] = {}
        for r in self._records:
            k = r.maturity.value
            m_dist[k] = m_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "maturity_distribution": m_dist,
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("service_level_intelligence.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def compute_error_budget_velocity(
        self,
    ) -> dict[str, Any]:
        """Compute error budget consumption velocity."""
        if not self._records:
            return {"status": "no_data"}
        svc_burns: dict[str, list[float]] = {}
        for r in self._records:
            svc_burns.setdefault(r.service, []).append(r.burn_rate)
        result: dict[str, Any] = {}
        for svc, burns in svc_burns.items():
            avg_burn = round(sum(burns) / len(burns), 4)
            max_burn = round(max(burns), 4)
            result[svc] = {
                "avg_burn_rate": avg_burn,
                "max_burn_rate": max_burn,
                "sample_count": len(burns),
                "fast_burning": avg_burn > 1.0,
            }
        return result

    def predict_budget_exhaustion(
        self,
    ) -> list[dict[str, Any]]:
        """Predict when error budgets exhaust."""
        at_risk: list[dict[str, Any]] = []
        svc_data: dict[str, list[SloRecord]] = {}
        for r in self._records:
            svc_data.setdefault(r.service, []).append(r)
        for svc, recs in svc_data.items():
            latest = max(recs, key=lambda x: x.created_at)
            if latest.burn_rate > 0 and latest.error_budget_remaining > 0:
                hours_left = round(
                    latest.error_budget_remaining / latest.burn_rate,
                    1,
                )
            else:
                hours_left = -1.0
            if hours_left > 0 and hours_left < 720:
                at_risk.append(
                    {
                        "service": svc,
                        "budget_remaining": (latest.error_budget_remaining),
                        "burn_rate": (latest.burn_rate),
                        "hours_to_exhaustion": (hours_left),
                        "risk": "high" if hours_left < 168 else "medium",
                    }
                )
        at_risk.sort(key=lambda x: x["hours_to_exhaustion"])
        return at_risk

    def recommend_slo_adjustments(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend SLO adjustments per service."""
        svc_data: dict[str, list[SloRecord]] = {}
        for r in self._records:
            svc_data.setdefault(r.service, []).append(r)
        recommendations: list[dict[str, Any]] = []
        for svc, recs in svc_data.items():
            avg_budget = round(
                sum(r.error_budget_remaining for r in recs) / len(recs),
                2,
            )
            avg_burn = round(
                sum(r.burn_rate for r in recs) / len(recs),
                4,
            )
            trends = {r.trend.value for r in recs}
            rec: dict[str, Any] = {
                "service": svc,
                "avg_budget_remaining": avg_budget,
                "avg_burn_rate": avg_burn,
                "trends": sorted(trends),
            }
            if avg_budget < 20:
                rec["suggestion"] = "Relax SLO targets or reduce deployment frequency"
            elif avg_burn > 2.0:
                rec["suggestion"] = "Investigate high burn rate"
            elif avg_budget > 80 and "declining" not in trends:
                rec["suggestion"] = "Consider tightening SLO"
            else:
                rec["suggestion"] = "SLO targets appropriate"
            recommendations.append(rec)
        return recommendations
