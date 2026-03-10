"""IntelligentSamplingCoordinator — sampling coord."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SamplingStrategy(StrEnum):
    HEAD = "head"
    TAIL = "tail"
    PRIORITY = "priority"
    ADAPTIVE = "adaptive"


class TraceImportance(StrEnum):
    CRITICAL = "critical"
    IMPORTANT = "important"
    ROUTINE = "routine"
    NOISE = "noise"


class SamplingOutcome(StrEnum):
    SAMPLED = "sampled"
    DROPPED = "dropped"
    DEFERRED = "deferred"


# --- Models ---


class SamplingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    strategy: SamplingStrategy = SamplingStrategy.HEAD
    importance: TraceImportance = TraceImportance.ROUTINE
    outcome: SamplingOutcome = SamplingOutcome.SAMPLED
    score: float = 0.0
    sample_rate: float = 1.0
    accuracy: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SamplingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    strategy: SamplingStrategy = SamplingStrategy.HEAD
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SamplingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    avg_sample_rate: float = 0.0
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_importance: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IntelligentSamplingCoordinator:
    """Intelligent Sampling Coordinator.

    Coordinates sampling decisions across services
    using priority-aware adaptive strategies.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[SamplingRecord] = []
        self._analyses: list[SamplingAnalysis] = []
        logger.info(
            "intelligent_sampling_coord.init",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        strategy: SamplingStrategy = (SamplingStrategy.HEAD),
        importance: TraceImportance = (TraceImportance.ROUTINE),
        outcome: SamplingOutcome = (SamplingOutcome.SAMPLED),
        score: float = 0.0,
        sample_rate: float = 1.0,
        accuracy: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SamplingRecord:
        record = SamplingRecord(
            name=name,
            strategy=strategy,
            importance=importance,
            outcome=outcome,
            score=score,
            sample_rate=sample_rate,
            accuracy=accuracy,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "intelligent_sampling_coord.added",
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
        rates = [r.sample_rate for r in matching]
        avg_rate = round(sum(rates) / len(rates), 4)
        return {
            "key": key,
            "record_count": len(matching),
            "avg_score": avg,
            "avg_sample_rate": avg_rate,
        }

    def generate_report(self) -> SamplingReport:
        by_st: dict[str, int] = {}
        by_im: dict[str, int] = {}
        by_oc: dict[str, int] = {}
        for r in self._records:
            v1 = r.strategy.value
            by_st[v1] = by_st.get(v1, 0) + 1
            v2 = r.importance.value
            by_im[v2] = by_im.get(v2, 0) + 1
            v3 = r.outcome.value
            by_oc[v3] = by_oc.get(v3, 0) + 1
        scores = [r.score for r in self._records]
        avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
        rates = [r.sample_rate for r in self._records]
        avg_r = round(sum(rates) / len(rates), 4) if rates else 0.0
        recs: list[str] = []
        dropped = by_oc.get("dropped", 0)
        total = len(self._records)
        if total > 0 and dropped / total > 0.5:
            recs.append(f"High drop rate: {dropped}/{total} dropped")
        if avg_s < self._threshold and self._records:
            recs.append(f"Avg score {avg_s} below threshold {self._threshold}")
        if not recs:
            recs.append("Sampling coordination healthy")
        return SamplingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg_s,
            avg_sample_rate=avg_r,
            by_strategy=by_st,
            by_importance=by_im,
            by_outcome=by_oc,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        st_dist: dict[str, int] = {}
        for r in self._records:
            k = r.strategy.value
            st_dist[k] = st_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "strategy_distribution": st_dist,
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("intelligent_sampling_coord.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def compute_sampling_accuracy(
        self,
    ) -> dict[str, Any]:
        """Compute sampling accuracy per strategy."""
        if not self._records:
            return {"status": "no_data"}
        strat_acc: dict[str, list[float]] = {}
        for r in self._records:
            key = r.strategy.value
            strat_acc.setdefault(key, []).append(r.accuracy)
        result: dict[str, Any] = {}
        for strat, accs in strat_acc.items():
            avg = round(sum(accs) / len(accs), 4)
            result[strat] = {
                "avg_accuracy": avg,
                "sample_count": len(accs),
                "meets_threshold": (avg >= self._threshold / 100),
            }
        overall = round(
            sum(r.accuracy for r in self._records) / len(self._records),
            4,
        )
        return {
            "overall_accuracy": overall,
            "by_strategy": result,
        }

    def optimize_sampling_rates(
        self,
    ) -> list[dict[str, Any]]:
        """Optimize sampling rates per service."""
        svc_data: dict[str, list[SamplingRecord]] = {}
        for r in self._records:
            svc_data.setdefault(r.service, []).append(r)
        recommendations: list[dict[str, Any]] = []
        for svc, recs in svc_data.items():
            rates = [r.sample_rate for r in recs]
            avg_rate = round(sum(rates) / len(rates), 4)
            crit_count = sum(1 for r in recs if r.importance == TraceImportance.CRITICAL)
            noise_count = sum(1 for r in recs if r.importance == TraceImportance.NOISE)
            rec: dict[str, Any] = {
                "service": svc,
                "current_avg_rate": avg_rate,
                "critical_traces": crit_count,
                "noise_traces": noise_count,
            }
            if noise_count > len(recs) * 0.5:
                rec["suggestion"] = "Reduce sampling rate for noise"
                rec["recommended_rate"] = round(avg_rate * 0.5, 4)
            elif crit_count > len(recs) * 0.3:
                rec["suggestion"] = "Increase rate for critical"
                rec["recommended_rate"] = min(1.0, round(avg_rate * 1.5, 4))
            else:
                rec["suggestion"] = "Rate is optimal"
                rec["recommended_rate"] = avg_rate
            recommendations.append(rec)
        return recommendations

    def detect_sampling_bias(
        self,
    ) -> dict[str, Any]:
        """Detect bias in sampling decisions."""
        if not self._records:
            return {"status": "no_data"}
        importance_outcomes: dict[str, dict[str, int]] = {}
        for r in self._records:
            imp = r.importance.value
            out = r.outcome.value
            if imp not in importance_outcomes:
                importance_outcomes[imp] = {}
            importance_outcomes[imp][out] = importance_outcomes[imp].get(out, 0) + 1
        biases: list[dict[str, Any]] = []
        for imp, outcomes in importance_outcomes.items():
            total = sum(outcomes.values())
            dropped = outcomes.get("dropped", 0)
            drop_rate = round(dropped / total, 4) if total > 0 else 0.0
            if imp == "critical" and drop_rate > 0.05:
                biases.append(
                    {
                        "importance": imp,
                        "drop_rate": drop_rate,
                        "issue": ("Critical traces dropped"),
                    }
                )
            elif imp == "noise" and drop_rate < 0.3:
                biases.append(
                    {
                        "importance": imp,
                        "drop_rate": drop_rate,
                        "issue": ("Noise not dropped enough"),
                    }
                )
        return {
            "distribution": importance_outcomes,
            "biases_detected": len(biases),
            "biases": biases,
        }
