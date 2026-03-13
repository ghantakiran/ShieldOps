"""Investigation Reasoning Depth Engine —
analyze investigation reasoning chain depth,
identify breakdowns, correlate depth with resolution."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReasoningDepth(StrEnum):
    SHALLOW = "shallow"
    MODERATE = "moderate"
    DEEP = "deep"
    EXHAUSTIVE = "exhaustive"


class BreakdownPoint(StrEnum):
    DATA_GAP = "data_gap"
    AMBIGUITY = "ambiguity"
    TIMEOUT = "timeout"
    COMPLEXITY_LIMIT = "complexity_limit"


class InvestigationStyle(StrEnum):
    LINEAR = "linear"
    BRANCHING = "branching"
    ITERATIVE = "iterative"
    PARALLEL = "parallel"


# --- Models ---


class InvestigationReasoningDepthRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = ""
    reasoning_depth: ReasoningDepth = ReasoningDepth.SHALLOW
    breakdown_point: BreakdownPoint = BreakdownPoint.DATA_GAP
    investigation_style: InvestigationStyle = InvestigationStyle.LINEAR
    depth_score: float = 0.0
    steps_taken: int = 0
    resolved: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class InvestigationReasoningDepthAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = ""
    reasoning_depth: ReasoningDepth = ReasoningDepth.SHALLOW
    breakdown_point: BreakdownPoint = BreakdownPoint.DATA_GAP
    depth_score: float = 0.0
    breakdown_detected: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class InvestigationReasoningDepthReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_depth_score: float = 0.0
    by_reasoning_depth: dict[str, int] = Field(default_factory=dict)
    by_breakdown_point: dict[str, int] = Field(default_factory=dict)
    by_investigation_style: dict[str, int] = Field(default_factory=dict)
    resolution_rate: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class InvestigationReasoningDepthEngine:
    """Analyze investigation reasoning chain depth,
    identify breakdowns, correlate depth with resolution."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[InvestigationReasoningDepthRecord] = []
        self._analyses: dict[str, InvestigationReasoningDepthAnalysis] = {}
        logger.info("investigation_reasoning_depth_engine.init", max_records=max_records)

    def add_record(
        self,
        investigation_id: str = "",
        reasoning_depth: ReasoningDepth = ReasoningDepth.SHALLOW,
        breakdown_point: BreakdownPoint = BreakdownPoint.DATA_GAP,
        investigation_style: InvestigationStyle = InvestigationStyle.LINEAR,
        depth_score: float = 0.0,
        steps_taken: int = 0,
        resolved: bool = False,
        description: str = "",
    ) -> InvestigationReasoningDepthRecord:
        record = InvestigationReasoningDepthRecord(
            investigation_id=investigation_id,
            reasoning_depth=reasoning_depth,
            breakdown_point=breakdown_point,
            investigation_style=investigation_style,
            depth_score=depth_score,
            steps_taken=steps_taken,
            resolved=resolved,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "investigation_reasoning_depth.record_added",
            record_id=record.id,
            investigation_id=investigation_id,
        )
        return record

    def process(self, key: str) -> InvestigationReasoningDepthAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        breakdown = rec.reasoning_depth == ReasoningDepth.SHALLOW and not rec.resolved
        analysis = InvestigationReasoningDepthAnalysis(
            investigation_id=rec.investigation_id,
            reasoning_depth=rec.reasoning_depth,
            breakdown_point=rec.breakdown_point,
            depth_score=round(rec.depth_score, 4),
            breakdown_detected=breakdown,
            description=(
                f"Investigation {rec.investigation_id} depth={rec.reasoning_depth.value} "
                f"steps={rec.steps_taken}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> InvestigationReasoningDepthReport:
        by_rd: dict[str, int] = {}
        by_bp: dict[str, int] = {}
        by_is: dict[str, int] = {}
        scores: list[float] = []
        resolved_count = 0
        for r in self._records:
            k = r.reasoning_depth.value
            by_rd[k] = by_rd.get(k, 0) + 1
            k2 = r.breakdown_point.value
            by_bp[k2] = by_bp.get(k2, 0) + 1
            k3 = r.investigation_style.value
            by_is[k3] = by_is.get(k3, 0) + 1
            scores.append(r.depth_score)
            if r.resolved:
                resolved_count += 1
        avg_depth = round(sum(scores) / len(scores), 4) if scores else 0.0
        res_rate = round(resolved_count / len(self._records), 4) if self._records else 0.0
        recs: list[str] = []
        shallow = by_rd.get("shallow", 0)
        if shallow:
            recs.append(f"{shallow} shallow investigations may be under-analyzed")
        timeout = by_bp.get("timeout", 0)
        if timeout:
            recs.append(f"{timeout} investigations timed out — increase depth limits")
        if not recs:
            recs.append("Investigation depth distribution is healthy")
        return InvestigationReasoningDepthReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_depth_score=avg_depth,
            by_reasoning_depth=by_rd,
            by_breakdown_point=by_bp,
            by_investigation_style=by_is,
            resolution_rate=res_rate,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.reasoning_depth.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "reasoning_depth_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("investigation_reasoning_depth_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def measure_reasoning_depth(self) -> list[dict[str, Any]]:
        """Measure reasoning depth per investigation."""
        inv_map: dict[str, list[InvestigationReasoningDepthRecord]] = {}
        for r in self._records:
            inv_map.setdefault(r.investigation_id, []).append(r)
        results: list[dict[str, Any]] = []
        depth_order = {
            "shallow": 1,
            "moderate": 2,
            "deep": 3,
            "exhaustive": 4,
        }
        for inv_id, inv_recs in inv_map.items():
            avg_score = sum(r.depth_score for r in inv_recs) / len(inv_recs)
            max_depth = max(inv_recs, key=lambda r: depth_order.get(r.reasoning_depth.value, 0))
            results.append(
                {
                    "investigation_id": inv_id,
                    "avg_depth_score": round(avg_score, 4),
                    "max_depth": max_depth.reasoning_depth.value,
                    "total_steps": sum(r.steps_taken for r in inv_recs),
                    "record_count": len(inv_recs),
                }
            )
        results.sort(key=lambda x: x["avg_depth_score"], reverse=True)
        return results

    def identify_reasoning_breakdowns(self) -> list[dict[str, Any]]:
        """Identify investigations with reasoning breakdowns."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.reasoning_depth == ReasoningDepth.SHALLOW
                and not r.resolved
                and r.investigation_id not in seen
            ):
                seen.add(r.investigation_id)
                results.append(
                    {
                        "investigation_id": r.investigation_id,
                        "breakdown_point": r.breakdown_point.value,
                        "depth_score": r.depth_score,
                        "steps_taken": r.steps_taken,
                        "style": r.investigation_style.value,
                    }
                )
        results.sort(key=lambda x: x["depth_score"])
        return results

    def correlate_depth_with_resolution(self) -> list[dict[str, Any]]:
        """Correlate reasoning depth level with resolution rate."""
        depth_stats: dict[str, dict[str, int]] = {}
        for r in self._records:
            dv = r.reasoning_depth.value
            depth_stats.setdefault(dv, {"total": 0, "resolved": 0})
            depth_stats[dv]["total"] += 1
            if r.resolved:
                depth_stats[dv]["resolved"] += 1
        results: list[dict[str, Any]] = []
        for depth_val, stats in depth_stats.items():
            res_rate = round(stats["resolved"] / stats["total"], 4) if stats["total"] > 0 else 0.0
            results.append(
                {
                    "reasoning_depth": depth_val,
                    "total": stats["total"],
                    "resolved": stats["resolved"],
                    "resolution_rate": res_rate,
                }
            )
        results.sort(key=lambda x: x["resolution_rate"], reverse=True)
        return results
