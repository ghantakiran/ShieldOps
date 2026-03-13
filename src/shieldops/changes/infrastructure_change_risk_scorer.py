"""Infrastructure Change Risk Scorer
compute change risk scores, detect high risk patterns,
rank changes by rollback complexity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ChangeScope(StrEnum):
    SINGLE_RESOURCE = "single_resource"
    MODULE = "module"
    STACK = "stack"
    CROSS_STACK = "cross_stack"


class RiskFactor(StrEnum):
    BLAST_RADIUS = "blast_radius"
    REVERSIBILITY = "reversibility"
    DEPENDENCY = "dependency"
    TIMING = "timing"


class RollbackComplexity(StrEnum):
    TRIVIAL = "trivial"
    MODERATE = "moderate"
    COMPLEX = "complex"
    IMPOSSIBLE = "impossible"


# --- Models ---


class ChangeRiskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_id: str = ""
    change_name: str = ""
    change_scope: ChangeScope = ChangeScope.SINGLE_RESOURCE
    risk_factor: RiskFactor = RiskFactor.BLAST_RADIUS
    rollback_complexity: RollbackComplexity = RollbackComplexity.MODERATE
    risk_score: float = 0.0
    affected_services: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ChangeRiskAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_id: str = ""
    computed_risk: float = 0.0
    change_scope: ChangeScope = ChangeScope.SINGLE_RESOURCE
    rollback_complexity: RollbackComplexity = RollbackComplexity.MODERATE
    is_high_risk: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ChangeRiskReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_change_scope: dict[str, int] = Field(default_factory=dict)
    by_risk_factor: dict[str, int] = Field(default_factory=dict)
    by_rollback_complexity: dict[str, int] = Field(default_factory=dict)
    high_risk_changes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class InfrastructureChangeRiskScorer:
    """Compute change risk scores, detect high risk
    patterns, rank changes by rollback complexity."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ChangeRiskRecord] = []
        self._analyses: dict[str, ChangeRiskAnalysis] = {}
        logger.info(
            "infrastructure_change_risk_scorer.init",
            max_records=max_records,
        )

    def record_item(
        self,
        change_id: str = "",
        change_name: str = "",
        change_scope: ChangeScope = (ChangeScope.SINGLE_RESOURCE),
        risk_factor: RiskFactor = (RiskFactor.BLAST_RADIUS),
        rollback_complexity: RollbackComplexity = (RollbackComplexity.MODERATE),
        risk_score: float = 0.0,
        affected_services: int = 0,
        description: str = "",
    ) -> ChangeRiskRecord:
        record = ChangeRiskRecord(
            change_id=change_id,
            change_name=change_name,
            change_scope=change_scope,
            risk_factor=risk_factor,
            rollback_complexity=rollback_complexity,
            risk_score=risk_score,
            affected_services=affected_services,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "change_risk.record_added",
            record_id=record.id,
            change_id=change_id,
        )
        return record

    def process(self, key: str) -> ChangeRiskAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_high = rec.risk_score >= 70.0
        analysis = ChangeRiskAnalysis(
            change_id=rec.change_id,
            computed_risk=round(rec.risk_score, 2),
            change_scope=rec.change_scope,
            rollback_complexity=(rec.rollback_complexity),
            is_high_risk=is_high,
            description=(f"Change {rec.change_id} risk {rec.risk_score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ChangeRiskReport:
        by_cs: dict[str, int] = {}
        by_rf: dict[str, int] = {}
        by_rc: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.change_scope.value
            by_cs[k] = by_cs.get(k, 0) + 1
            k2 = r.risk_factor.value
            by_rf[k2] = by_rf.get(k2, 0) + 1
            k3 = r.rollback_complexity.value
            by_rc[k3] = by_rc.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        high = list({r.change_id for r in self._records if r.risk_score >= 70.0})[:10]
        recs: list[str] = []
        if high:
            recs.append(f"{len(high)} high-risk changes found")
        if not recs:
            recs.append("No high-risk changes found")
        return ChangeRiskReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_change_scope=by_cs,
            by_risk_factor=by_rf,
            by_rollback_complexity=by_rc,
            high_risk_changes=high,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        cs_dist: dict[str, int] = {}
        for r in self._records:
            k = r.change_scope.value
            cs_dist[k] = cs_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "change_scope_distribution": cs_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("infrastructure_change_risk_scorer.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_change_risk_score(
        self,
    ) -> list[dict[str, Any]]:
        """Compute risk score per change."""
        change_scores: dict[str, list[float]] = {}
        change_scopes: dict[str, str] = {}
        for r in self._records:
            change_scores.setdefault(r.change_id, []).append(r.risk_score)
            change_scopes[r.change_id] = r.change_scope.value
        results: list[dict[str, Any]] = []
        for cid, scores in change_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "change_id": cid,
                    "scope": change_scopes[cid],
                    "avg_risk": avg,
                    "factor_count": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["avg_risk"],
            reverse=True,
        )
        return results

    def detect_high_risk_patterns(
        self,
    ) -> list[dict[str, Any]]:
        """Detect high risk change patterns."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.risk_score >= 70.0 and r.change_id not in seen:
                seen.add(r.change_id)
                results.append(
                    {
                        "change_id": r.change_id,
                        "scope": (r.change_scope.value),
                        "risk_score": r.risk_score,
                        "risk_factor": (r.risk_factor.value),
                        "rollback": (r.rollback_complexity.value),
                    }
                )
        results.sort(
            key=lambda x: x["risk_score"],
            reverse=True,
        )
        return results

    def rank_changes_by_rollback_complexity(
        self,
    ) -> list[dict[str, Any]]:
        """Rank changes by rollback complexity."""
        complexity_order = {
            "impossible": 4,
            "complex": 3,
            "moderate": 2,
            "trivial": 1,
        }
        change_complexity: dict[str, int] = {}
        change_risk: dict[str, float] = {}
        for r in self._records:
            val = complexity_order.get(r.rollback_complexity.value, 0)
            prev = change_complexity.get(r.change_id, 0)
            if val > prev:
                change_complexity[r.change_id] = val
            change_risk[r.change_id] = change_risk.get(r.change_id, 0.0) + r.risk_score
        results: list[dict[str, Any]] = []
        for cid, comp in change_complexity.items():
            results.append(
                {
                    "change_id": cid,
                    "complexity_score": comp,
                    "aggregate_risk": round(change_risk[cid], 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["complexity_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
