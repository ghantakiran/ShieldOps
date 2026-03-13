"""Organizational Resilience Scorer —
compute resilience score, detect gaps,
rank capabilities by improvement priority."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ResilienceDimension(StrEnum):
    TECHNICAL = "technical"
    PROCESS = "process"
    PEOPLE = "people"
    CULTURE = "culture"


class GapType(StrEnum):
    SINGLE_POINT_OF_FAILURE = "single_point_of_failure"
    KNOWLEDGE_GAP = "knowledge_gap"
    PROCESS_GAP = "process_gap"
    TOOLING_GAP = "tooling_gap"


class MaturityLevel(StrEnum):
    OPTIMIZED = "optimized"
    MANAGED = "managed"
    DEFINED = "defined"
    INITIAL = "initial"


# --- Models ---


class ResilienceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    capability_id: str = ""
    team_id: str = ""
    dimension: ResilienceDimension = ResilienceDimension.TECHNICAL
    gap_type: GapType = GapType.PROCESS_GAP
    maturity: MaturityLevel = MaturityLevel.DEFINED
    resilience_score: float = 0.0
    recovery_time_hours: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ResilienceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    capability_id: str = ""
    avg_resilience: float = 0.0
    maturity: MaturityLevel = MaturityLevel.DEFINED
    gap_count: int = 0
    team_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ResilienceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_resilience: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_gap_type: dict[str, int] = Field(default_factory=dict)
    by_maturity: dict[str, int] = Field(default_factory=dict)
    weak_capabilities: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class OrganizationalResilienceScorer:
    """Compute resilience score, detect gaps,
    rank capabilities by improvement priority."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ResilienceRecord] = []
        self._analyses: dict[str, ResilienceAnalysis] = {}
        logger.info(
            "organizational_resilience_scorer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        capability_id: str = "",
        team_id: str = "",
        dimension: ResilienceDimension = (ResilienceDimension.TECHNICAL),
        gap_type: GapType = GapType.PROCESS_GAP,
        maturity: MaturityLevel = MaturityLevel.DEFINED,
        resilience_score: float = 0.0,
        recovery_time_hours: float = 0.0,
        description: str = "",
    ) -> ResilienceRecord:
        record = ResilienceRecord(
            capability_id=capability_id,
            team_id=team_id,
            dimension=dimension,
            gap_type=gap_type,
            maturity=maturity,
            resilience_score=resilience_score,
            recovery_time_hours=recovery_time_hours,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "org_resilience.record_added",
            record_id=record.id,
            capability_id=capability_id,
        )
        return record

    def process(self, key: str) -> ResilienceAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        cap_recs = [r for r in self._records if r.capability_id == rec.capability_id]
        scores = [r.resilience_score for r in cap_recs]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        teams = {r.team_id for r in cap_recs}
        gaps = sum(
            1 for r in cap_recs if r.maturity in (MaturityLevel.INITIAL, MaturityLevel.DEFINED)
        )
        analysis = ResilienceAnalysis(
            capability_id=rec.capability_id,
            avg_resilience=avg,
            maturity=rec.maturity,
            gap_count=gaps,
            team_count=len(teams),
            description=(f"Cap {rec.capability_id} res={avg}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ResilienceReport:
        by_d: dict[str, int] = {}
        by_g: dict[str, int] = {}
        by_m: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.dimension.value
            by_d[k] = by_d.get(k, 0) + 1
            k2 = r.gap_type.value
            by_g[k2] = by_g.get(k2, 0) + 1
            k3 = r.maturity.value
            by_m[k3] = by_m.get(k3, 0) + 1
            scores.append(r.resilience_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        weak = list(
            {r.capability_id for r in self._records if r.maturity == MaturityLevel.INITIAL}
        )[:10]
        recs: list[str] = []
        if weak:
            recs.append(f"{len(weak)} weak capabilities found")
        if not recs:
            recs.append("Organizational resilience adequate")
        return ResilienceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_resilience=avg,
            by_dimension=by_d,
            by_gap_type=by_g,
            by_maturity=by_m,
            weak_capabilities=weak,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        d_dist: dict[str, int] = {}
        for r in self._records:
            k = r.dimension.value
            d_dist[k] = d_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "dimension_distribution": d_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("organizational_resilience_scorer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_resilience_score(
        self,
    ) -> list[dict[str, Any]]:
        """Compute resilience score per capability."""
        cap_scores: dict[str, list[float]] = {}
        cap_dims: dict[str, str] = {}
        for r in self._records:
            cap_scores.setdefault(r.capability_id, []).append(r.resilience_score)
            cap_dims[r.capability_id] = r.dimension.value
        results: list[dict[str, Any]] = []
        for cid, scores in cap_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "capability_id": cid,
                    "resilience_score": avg,
                    "dimension": cap_dims.get(cid, ""),
                    "samples": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["resilience_score"],
            reverse=True,
        )
        return results

    def detect_resilience_gaps(
        self,
    ) -> list[dict[str, Any]]:
        """Detect resilience gaps by capability."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.maturity
                in (
                    MaturityLevel.INITIAL,
                    MaturityLevel.DEFINED,
                )
                and r.capability_id not in seen
            ):
                seen.add(r.capability_id)
                results.append(
                    {
                        "capability_id": (r.capability_id),
                        "gap_type": r.gap_type.value,
                        "maturity": r.maturity.value,
                        "resilience_score": (r.resilience_score),
                    }
                )
        results.sort(
            key=lambda x: x["resilience_score"],
        )
        return results

    def rank_capabilities_by_improvement_priority(
        self,
    ) -> list[dict[str, Any]]:
        """Rank capabilities by improvement priority."""
        cap_scores: dict[str, list[float]] = {}
        cap_recovery: dict[str, float] = {}
        for r in self._records:
            cap_scores.setdefault(r.capability_id, []).append(r.resilience_score)
            cap_recovery[r.capability_id] = max(
                cap_recovery.get(r.capability_id, 0.0),
                r.recovery_time_hours,
            )
        results: list[dict[str, Any]] = []
        for cid, scores in cap_scores.items():
            avg = sum(scores) / len(scores)
            priority = round(
                (100.0 - avg) + cap_recovery.get(cid, 0.0),
                2,
            )
            results.append(
                {
                    "capability_id": cid,
                    "priority_score": priority,
                    "avg_resilience": round(avg, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["priority_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
