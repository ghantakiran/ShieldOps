"""Responder Effectiveness Scorer
score responder performance, benchmark against peers,
identify skill development areas."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PerformanceTier(StrEnum):
    EXCEPTIONAL = "exceptional"
    PROFICIENT = "proficient"
    DEVELOPING = "developing"
    NOVICE = "novice"


class MetricCategory(StrEnum):
    SPEED = "speed"
    ACCURACY = "accuracy"
    QUALITY = "quality"
    COMMUNICATION = "communication"


class BenchmarkScope(StrEnum):
    TEAM = "team"
    DEPARTMENT = "department"
    ORGANIZATION = "organization"
    INDUSTRY = "industry"


# --- Models ---


class ResponderEffectivenessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    responder_id: str = ""
    performance_tier: PerformanceTier = PerformanceTier.PROFICIENT
    metric_category: MetricCategory = MetricCategory.SPEED
    benchmark_scope: BenchmarkScope = BenchmarkScope.TEAM
    score: float = 0.0
    incidents_resolved: int = 0
    avg_resolution_min: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ResponderEffectivenessAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    responder_id: str = ""
    performance_tier: PerformanceTier = PerformanceTier.PROFICIENT
    overall_score: float = 0.0
    speed_score: float = 0.0
    quality_score: float = 0.0
    incident_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ResponderEffectivenessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    by_performance_tier: dict[str, int] = Field(default_factory=dict)
    by_metric_category: dict[str, int] = Field(default_factory=dict)
    by_benchmark_scope: dict[str, int] = Field(default_factory=dict)
    top_performers: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ResponderEffectivenessScorer:
    """Score responder performance, benchmark against
    peers, identify skill development areas."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ResponderEffectivenessRecord] = []
        self._analyses: dict[str, ResponderEffectivenessAnalysis] = {}
        logger.info(
            "responder_effectiveness_scorer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        responder_id: str = "",
        performance_tier: PerformanceTier = (PerformanceTier.PROFICIENT),
        metric_category: MetricCategory = (MetricCategory.SPEED),
        benchmark_scope: BenchmarkScope = (BenchmarkScope.TEAM),
        score: float = 0.0,
        incidents_resolved: int = 0,
        avg_resolution_min: float = 0.0,
        team: str = "",
    ) -> ResponderEffectivenessRecord:
        record = ResponderEffectivenessRecord(
            responder_id=responder_id,
            performance_tier=performance_tier,
            metric_category=metric_category,
            benchmark_scope=benchmark_scope,
            score=score,
            incidents_resolved=incidents_resolved,
            avg_resolution_min=avg_resolution_min,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "responder_effectiveness.record_added",
            record_id=record.id,
            responder_id=responder_id,
        )
        return record

    def process(self, key: str) -> ResponderEffectivenessAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        related = [r for r in self._records if r.responder_id == rec.responder_id]
        count = len(related)
        avg_score = sum(r.score for r in related) / count if count else 0.0
        speed_recs = [r for r in related if r.metric_category == MetricCategory.SPEED]
        speed = sum(r.score for r in speed_recs) / len(speed_recs) if speed_recs else 0.0
        qual_recs = [r for r in related if r.metric_category == MetricCategory.QUALITY]
        quality = sum(r.score for r in qual_recs) / len(qual_recs) if qual_recs else 0.0
        analysis = ResponderEffectivenessAnalysis(
            responder_id=rec.responder_id,
            performance_tier=rec.performance_tier,
            overall_score=round(avg_score, 2),
            speed_score=round(speed, 2),
            quality_score=round(quality, 2),
            incident_count=sum(r.incidents_resolved for r in related),
            description=(f"Responder {rec.responder_id} score {avg_score:.2f}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> ResponderEffectivenessReport:
        by_pt: dict[str, int] = {}
        by_mc: dict[str, int] = {}
        by_bs: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.performance_tier.value
            by_pt[k] = by_pt.get(k, 0) + 1
            k2 = r.metric_category.value
            by_mc[k2] = by_mc.get(k2, 0) + 1
            k3 = r.benchmark_scope.value
            by_bs[k3] = by_bs.get(k3, 0) + 1
            scores.append(r.score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        top = list(
            {
                r.responder_id
                for r in self._records
                if r.performance_tier == PerformanceTier.EXCEPTIONAL
            }
        )[:10]
        recs: list[str] = []
        if top:
            recs.append(f"{len(top)} top performers found")
        if not recs:
            recs.append("Performance within normal range")
        return ResponderEffectivenessReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg,
            by_performance_tier=by_pt,
            by_metric_category=by_mc,
            by_benchmark_scope=by_bs,
            top_performers=top,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        pt_dist: dict[str, int] = {}
        for r in self._records:
            k = r.performance_tier.value
            pt_dist[k] = pt_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "performance_tier_distribution": pt_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("responder_effectiveness_scorer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def score_responder_performance(
        self,
    ) -> list[dict[str, Any]]:
        """Score responder performance."""
        resp_scores: dict[str, list[float]] = {}
        resp_incidents: dict[str, int] = {}
        for r in self._records:
            resp_scores.setdefault(r.responder_id, []).append(r.score)
            resp_incidents[r.responder_id] = (
                resp_incidents.get(r.responder_id, 0) + r.incidents_resolved
            )
        results: list[dict[str, Any]] = []
        for rid, scores in resp_scores.items():
            avg = sum(scores) / len(scores) if scores else 0.0
            results.append(
                {
                    "responder_id": rid,
                    "avg_score": round(avg, 2),
                    "total_incidents": (resp_incidents[rid]),
                    "measurement_count": len(scores),
                    "tier": "exceptional"
                    if avg > 90
                    else "proficient"
                    if avg > 70
                    else "developing",
                }
            )
        results.sort(
            key=lambda x: x["avg_score"],
            reverse=True,
        )
        return results

    def benchmark_against_peers(
        self,
    ) -> list[dict[str, Any]]:
        """Benchmark responders against peers."""
        team_scores: dict[str, dict[str, list[float]]] = {}
        for r in self._records:
            if r.team not in team_scores:
                team_scores[r.team] = {}
            team_scores[r.team].setdefault(r.responder_id, []).append(r.score)
        results: list[dict[str, Any]] = []
        for team, responders in team_scores.items():
            all_scores = [s for scores in responders.values() for s in scores]
            team_avg = sum(all_scores) / len(all_scores) if all_scores else 0.0
            for rid, scores in responders.items():
                avg = sum(scores) / len(scores) if scores else 0.0
                diff = avg - team_avg
                results.append(
                    {
                        "responder_id": rid,
                        "team": team,
                        "avg_score": round(avg, 2),
                        "team_avg": round(team_avg, 2),
                        "vs_team": round(diff, 2),
                        "position": "above" if diff > 0 else "below",
                    }
                )
        results.sort(
            key=lambda x: x["vs_team"],
            reverse=True,
        )
        return results

    def identify_skill_development_areas(
        self,
    ) -> list[dict[str, Any]]:
        """Identify skill development areas."""
        resp_cats: dict[str, dict[str, list[float]]] = {}
        for r in self._records:
            if r.responder_id not in resp_cats:
                resp_cats[r.responder_id] = {}
            cat = r.metric_category.value
            resp_cats[r.responder_id].setdefault(cat, []).append(r.score)
        results: list[dict[str, Any]] = []
        for rid, cats in resp_cats.items():
            weakest_cat = ""
            weakest_score = float("inf")
            cat_avgs: dict[str, float] = {}
            for cat, scores in cats.items():
                avg = sum(scores) / len(scores) if scores else 0.0
                cat_avgs[cat] = round(avg, 2)
                if avg < weakest_score:
                    weakest_score = avg
                    weakest_cat = cat
            results.append(
                {
                    "responder_id": rid,
                    "category_scores": cat_avgs,
                    "weakest_area": weakest_cat,
                    "weakest_score": round(weakest_score, 2),
                    "recommendation": (f"Focus on {weakest_cat}"),
                }
            )
        results.sort(
            key=lambda x: x["weakest_score"],
        )
        return results
