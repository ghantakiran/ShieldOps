"""Synthetic Scenario Quality Engine —
evaluates quality of generated incident scenarios."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ScenarioRealism(StrEnum):
    REALISTIC = "realistic"
    PLAUSIBLE = "plausible"
    UNLIKELY = "unlikely"
    DEGENERATE = "degenerate"


class QualityDimension(StrEnum):
    SOLVABILITY = "solvability"
    DIVERSITY = "diversity"
    RELEVANCE = "relevance"
    COMPLEXITY = "complexity"


class QualityVerdict(StrEnum):
    ACCEPTED = "accepted"
    MARGINAL = "marginal"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


# --- Models ---


class ScenarioQualityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario_id: str = ""
    realism: ScenarioRealism = ScenarioRealism.REALISTIC
    dimension: QualityDimension = QualityDimension.SOLVABILITY
    verdict: QualityVerdict = QualityVerdict.ACCEPTED
    realism_score: float = 0.0
    diversity_score: float = 0.0
    complexity_score: float = 0.0
    overall_quality: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ScenarioQualityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario_id: str = ""
    avg_quality: float = 0.0
    dominant_realism: ScenarioRealism = ScenarioRealism.REALISTIC
    verdict: QualityVerdict = QualityVerdict.ACCEPTED
    record_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ScenarioQualityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_quality: float = 0.0
    by_realism: dict[str, int] = Field(default_factory=dict)
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_verdict: dict[str, int] = Field(default_factory=dict)
    top_quality_scenarios: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SyntheticScenarioQualityEngine:
    """Evaluates quality of generated incident scenarios."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ScenarioQualityRecord] = []
        self._analyses: dict[str, ScenarioQualityAnalysis] = {}
        logger.info(
            "synthetic_scenario_quality_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        scenario_id: str = "",
        realism: ScenarioRealism = ScenarioRealism.REALISTIC,
        dimension: QualityDimension = QualityDimension.SOLVABILITY,
        verdict: QualityVerdict = QualityVerdict.ACCEPTED,
        realism_score: float = 0.0,
        diversity_score: float = 0.0,
        complexity_score: float = 0.0,
        overall_quality: float = 0.0,
        description: str = "",
    ) -> ScenarioQualityRecord:
        record = ScenarioQualityRecord(
            scenario_id=scenario_id,
            realism=realism,
            dimension=dimension,
            verdict=verdict,
            realism_score=realism_score,
            diversity_score=diversity_score,
            complexity_score=complexity_score,
            overall_quality=overall_quality,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "synthetic_scenario_quality.record_added",
            record_id=record.id,
            scenario_id=scenario_id,
        )
        return record

    def process(self, key: str) -> ScenarioQualityAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        scen_recs = [r for r in self._records if r.scenario_id == rec.scenario_id]
        qualities = [r.overall_quality for r in scen_recs]
        avg_q = round(sum(qualities) / len(qualities), 4) if qualities else 0.0
        realism_counts: dict[str, int] = {}
        for sr in scen_recs:
            rk = sr.realism.value
            realism_counts[rk] = realism_counts.get(rk, 0) + 1
        dom_real_str = (
            max(realism_counts, key=lambda x: realism_counts[x]) if realism_counts else ""
        )
        dom_real = ScenarioRealism(dom_real_str) if dom_real_str else rec.realism
        analysis = ScenarioQualityAnalysis(
            scenario_id=rec.scenario_id,
            avg_quality=avg_q,
            dominant_realism=dom_real,
            verdict=rec.verdict,
            record_count=len(scen_recs),
            description=f"Scenario {rec.scenario_id} avg quality {avg_q}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ScenarioQualityReport:
        by_r: dict[str, int] = {}
        by_d: dict[str, int] = {}
        by_v: dict[str, int] = {}
        qualities: list[float] = []
        for r in self._records:
            k1 = r.realism.value
            by_r[k1] = by_r.get(k1, 0) + 1
            k2 = r.dimension.value
            by_d[k2] = by_d.get(k2, 0) + 1
            k3 = r.verdict.value
            by_v[k3] = by_v.get(k3, 0) + 1
            qualities.append(r.overall_quality)
        avg_q = round(sum(qualities) / len(qualities), 4) if qualities else 0.0
        scen_quality: dict[str, float] = {}
        for r in self._records:
            if r.overall_quality > scen_quality.get(r.scenario_id, -1.0):
                scen_quality[r.scenario_id] = r.overall_quality
        top_scenarios = sorted(
            scen_quality,
            key=lambda x: scen_quality[x],
            reverse=True,
        )[:10]
        recs_list: list[str] = []
        degenerate = by_r.get("degenerate", 0)
        rejected = by_v.get("rejected", 0)
        if degenerate > 0:
            recs_list.append(f"{degenerate} degenerate scenarios — filter before training")
        if rejected > 0:
            recs_list.append(f"{rejected} rejected scenarios — review generation pipeline")
        if not recs_list:
            recs_list.append("Scenario quality is within acceptable bounds")
        return ScenarioQualityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_quality=avg_q,
            by_realism=by_r,
            by_dimension=by_d,
            by_verdict=by_v,
            top_quality_scenarios=top_scenarios,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        verdict_dist: dict[str, int] = {}
        for r in self._records:
            k = r.verdict.value
            verdict_dist[k] = verdict_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "verdict_distribution": verdict_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("synthetic_scenario_quality_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def score_scenario_realism(
        self,
        scenario_id: str,
    ) -> dict[str, Any]:
        """Compute aggregate realism score for a scenario."""
        scen_recs = [r for r in self._records if r.scenario_id == scenario_id]
        if not scen_recs:
            return {"scenario_id": scenario_id, "realism_score": 0.0, "verdict": "no_data"}
        realism_scores = [r.realism_score for r in scen_recs]
        avg_realism = round(sum(realism_scores) / len(realism_scores), 4)
        if avg_realism >= 0.8:
            verdict = ScenarioRealism.REALISTIC
        elif avg_realism >= 0.6:
            verdict = ScenarioRealism.PLAUSIBLE
        elif avg_realism >= 0.35:
            verdict = ScenarioRealism.UNLIKELY
        else:
            verdict = ScenarioRealism.DEGENERATE
        return {
            "scenario_id": scenario_id,
            "avg_realism_score": avg_realism,
            "realism_verdict": verdict.value,
            "sample_count": len(scen_recs),
        }

    def evaluate_scenario_diversity(self) -> dict[str, Any]:
        """Evaluate diversity across all generated scenarios."""
        scen_diversity: dict[str, float] = {}
        for r in self._records:
            if r.diversity_score > scen_diversity.get(r.scenario_id, -1.0):
                scen_diversity[r.scenario_id] = r.diversity_score
        if not scen_diversity:
            return {"total_scenarios": 0, "avg_diversity": 0.0, "diversity_verdict": "no_data"}
        div_vals = list(scen_diversity.values())
        avg_div = round(sum(div_vals) / len(div_vals), 4)
        low_diversity = [sid for sid, d in scen_diversity.items() if d < 0.3]
        return {
            "total_scenarios": len(scen_diversity),
            "avg_diversity": avg_div,
            "low_diversity_scenarios": low_diversity[:10],
            "low_diversity_count": len(low_diversity),
            "diversity_verdict": "high"
            if avg_div >= 0.7
            else "moderate"
            if avg_div >= 0.4
            else "low",
        }

    def filter_degenerate_scenarios(self) -> list[dict[str, Any]]:
        """Filter out degenerate or rejected scenarios from the pool."""
        filtered: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for r in self._records:
            if r.scenario_id in seen_ids:
                continue
            if r.realism == ScenarioRealism.DEGENERATE or r.verdict == QualityVerdict.REJECTED:
                seen_ids.add(r.scenario_id)
                filtered.append(
                    {
                        "scenario_id": r.scenario_id,
                        "realism": r.realism.value,
                        "verdict": r.verdict.value,
                        "overall_quality": r.overall_quality,
                        "reason": "degenerate"
                        if r.realism == ScenarioRealism.DEGENERATE
                        else "rejected",
                    }
                )
        filtered.sort(key=lambda x: x["overall_quality"])
        return filtered
