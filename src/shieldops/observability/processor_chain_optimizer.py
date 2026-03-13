"""ProcessorChainOptimizer — processor chain optimization."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ProcessorType(StrEnum):
    BATCH = "batch"
    FILTER = "filter"
    TRANSFORM = "transform"
    ENRICH = "enrich"


class ChainPosition(StrEnum):
    EARLY = "early"
    MIDDLE = "middle"
    LATE = "late"
    TERMINAL = "terminal"


class OptimizationGoal(StrEnum):
    THROUGHPUT = "throughput"
    LATENCY = "latency"
    ACCURACY = "accuracy"
    COST = "cost"


# --- Models ---


class ProcessorChainOptimizerRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    processor_type: ProcessorType = ProcessorType.BATCH
    chain_position: ChainPosition = ChainPosition.EARLY
    optimization_goal: OptimizationGoal = OptimizationGoal.THROUGHPUT
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ProcessorChainOptimizerAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    processor_type: ProcessorType = ProcessorType.BATCH
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ProcessorChainOptimizerReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_processor_type: dict[str, int] = Field(default_factory=dict)
    by_chain_position: dict[str, int] = Field(default_factory=dict)
    by_optimization_goal: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ProcessorChainOptimizer:
    """Processor chain optimization engine."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ProcessorChainOptimizerRecord] = []
        self._analyses: list[ProcessorChainOptimizerAnalysis] = []
        logger.info(
            "processor.chain.optimizer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        processor_type: ProcessorType = (ProcessorType.BATCH),
        chain_position: ChainPosition = (ChainPosition.EARLY),
        optimization_goal: OptimizationGoal = (OptimizationGoal.THROUGHPUT),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ProcessorChainOptimizerRecord:
        record = ProcessorChainOptimizerRecord(
            name=name,
            processor_type=processor_type,
            chain_position=chain_position,
            optimization_goal=optimization_goal,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "processor.chain.optimizer.record_added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        """Find record by id, create analysis."""
        for r in self._records:
            if r.id == key:
                analysis = ProcessorChainOptimizerAnalysis(
                    name=r.name,
                    processor_type=(r.processor_type),
                    analysis_score=r.score,
                    threshold=self._threshold,
                    breached=(r.score < self._threshold),
                    description=(f"Processed {r.name}"),
                )
                self._analyses.append(analysis)
                return {
                    "status": "processed",
                    "analysis_id": analysis.id,
                    "breached": analysis.breached,
                }
        return {"status": "not_found", "key": key}

    # -- domain methods ---

    def analyze_chain_performance(
        self,
    ) -> dict[str, Any]:
        """Analyze performance per processor type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.processor_type.value
            type_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in type_data.items():
            result[k] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def detect_redundant_processors(
        self,
    ) -> list[dict[str, Any]]:
        """Detect redundant processors in chain."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "processor_type": (r.processor_type.value),
                        "position": (r.chain_position.value),
                        "score": r.score,
                        "service": r.service,
                    }
                )
        return sorted(results, key=lambda x: x["score"])

    def recommend_chain_reorder(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend processor chain reordering."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "service": svc,
                    "avg_score": avg,
                    "action": ("reorder_chain" if avg < self._threshold else "optimal"),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    # -- report / stats ---

    def generate_report(
        self,
    ) -> ProcessorChainOptimizerReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            v1 = r.processor_type.value
            by_e1[v1] = by_e1.get(v1, 0) + 1
            v2 = r.chain_position.value
            by_e2[v2] = by_e2.get(v2, 0) + 1
            v3 = r.optimization_goal.value
            by_e3[v3] = by_e3.get(v3, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg < self._threshold:
            recs.append(f"Avg score {avg} below threshold ({self._threshold})")
        if not recs:
            recs.append("Processor Chain Optimizer is healthy")
        return ProcessorChainOptimizerReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg,
            by_processor_type=by_e1,
            by_chain_position=by_e2,
            by_optimization_goal=by_e3,
            top_gaps=[r.name for r in self._records if r.score < self._threshold][:5],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("processor.chain.optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.processor_type.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "processor_type_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
