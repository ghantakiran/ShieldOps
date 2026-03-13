"""Hypothesis Generator Engine

Generate, rank, and prune optimization hypotheses
based on metric analysis and failure patterns.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HypothesisSource(StrEnum):
    METRIC_ANALYSIS = "metric_analysis"
    FAILURE_PATTERN = "failure_pattern"
    PEER_COMPARISON = "peer_comparison"
    RANDOM_EXPLORATION = "random_exploration"


class HypothesisConfidence(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    SPECULATIVE = "speculative"


class ValidationMethod(StrEnum):
    AB_TEST = "ab_test"
    HOLDOUT = "holdout"
    CROSS_VALIDATION = "cross_validation"
    BOOTSTRAP = "bootstrap"


# --- Models ---


class HypothesisRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hypothesis_name: str = ""
    source: HypothesisSource = HypothesisSource.METRIC_ANALYSIS
    confidence: HypothesisConfidence = HypothesisConfidence.MODERATE
    validation: ValidationMethod = ValidationMethod.AB_TEST
    expected_impact: float = 0.0
    tested: bool = False
    agent_id: str = ""
    service: str = ""
    created_at: float = Field(default_factory=time.time)


class HypothesisAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hypothesis_name: str = ""
    source: HypothesisSource = HypothesisSource.METRIC_ANALYSIS
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class HypothesisReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    untested_count: int = 0
    avg_expected_impact: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_validation: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class HypothesisGeneratorEngine:
    """Generate, rank, and prune optimization
    hypotheses from metric and failure analysis.
    """

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[HypothesisRecord] = []
        self._analyses: dict[str, HypothesisAnalysis] = {}
        logger.info(
            "hypothesis_generator_engine.initialized",
            max_records=max_records,
        )

    def add_record(
        self,
        hypothesis_name: str = "",
        source: HypothesisSource = (HypothesisSource.METRIC_ANALYSIS),
        confidence: HypothesisConfidence = (HypothesisConfidence.MODERATE),
        validation: ValidationMethod = (ValidationMethod.AB_TEST),
        expected_impact: float = 0.0,
        tested: bool = False,
        agent_id: str = "",
        service: str = "",
    ) -> HypothesisRecord:
        record = HypothesisRecord(
            hypothesis_name=hypothesis_name,
            source=source,
            confidence=confidence,
            validation=validation,
            expected_impact=expected_impact,
            tested=tested,
            agent_id=agent_id,
            service=service,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "hypothesis_generator_engine.record_added",
            record_id=record.id,
            hypothesis_name=hypothesis_name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.id == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        rec = matching[0]
        analysis = HypothesisAnalysis(
            hypothesis_name=rec.hypothesis_name,
            source=rec.source,
            analysis_score=rec.expected_impact,
            description=(f"Hypothesis {rec.hypothesis_name} impact={rec.expected_impact}"),
        )
        self._analyses[key] = analysis
        return {
            "key": key,
            "analysis_id": analysis.id,
            "impact": analysis.analysis_score,
        }

    def generate_report(self) -> HypothesisReport:
        by_src: dict[str, int] = {}
        by_conf: dict[str, int] = {}
        by_val: dict[str, int] = {}
        untested = 0
        impacts: list[float] = []
        for r in self._records:
            s = r.source.value
            by_src[s] = by_src.get(s, 0) + 1
            c = r.confidence.value
            by_conf[c] = by_conf.get(c, 0) + 1
            v = r.validation.value
            by_val[v] = by_val.get(v, 0) + 1
            if not r.tested:
                untested += 1
            impacts.append(r.expected_impact)
        avg_impact = round(sum(impacts) / len(impacts), 4) if impacts else 0.0
        recs: list[str] = []
        total = len(self._records)
        if total > 0 and untested / total > 0.7:
            recs.append("High untested ratio — prioritize hypothesis validation")
        if not recs:
            recs.append("Hypothesis pipeline is healthy")
        return HypothesisReport(
            total_records=total,
            total_analyses=len(self._analyses),
            untested_count=untested,
            avg_expected_impact=avg_impact,
            by_source=by_src,
            by_confidence=by_conf,
            by_validation=by_val,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        src_dist: dict[str, int] = {}
        for r in self._records:
            k = r.source.value
            src_dist[k] = src_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "source_distribution": src_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("hypothesis_generator_engine.cleared")
        return {"status": "cleared"}

    # --- Domain methods ---

    def generate_hypotheses(self, agent_id: str) -> list[dict[str, Any]]:
        """Generate hypotheses for an agent."""
        matching = [r for r in self._records if r.agent_id == agent_id]
        if not matching:
            return []
        return [
            {
                "hypothesis_name": r.hypothesis_name,
                "source": r.source.value,
                "confidence": r.confidence.value,
                "expected_impact": r.expected_impact,
                "tested": r.tested,
            }
            for r in matching
        ]

    def rank_by_expected_impact(self, agent_id: str, top_n: int = 5) -> list[dict[str, Any]]:
        """Rank hypotheses by expected impact."""
        matching = [r for r in self._records if r.agent_id == agent_id]
        if not matching:
            return []
        ranked = sorted(
            matching,
            key=lambda r: r.expected_impact,
            reverse=True,
        )
        return [
            {
                "hypothesis_name": r.hypothesis_name,
                "expected_impact": r.expected_impact,
                "confidence": r.confidence.value,
            }
            for r in ranked[:top_n]
        ]

    def prune_tested_hypotheses(self, agent_id: str) -> dict[str, Any]:
        """Prune already-tested hypotheses."""
        matching = [r for r in self._records if r.agent_id == agent_id]
        if not matching:
            return {
                "agent_id": agent_id,
                "status": "no_data",
            }
        tested = [r for r in matching if r.tested]
        untested = [r for r in matching if not r.tested]
        return {
            "agent_id": agent_id,
            "tested_count": len(tested),
            "untested_count": len(untested),
            "pruned_names": [r.hypothesis_name for r in tested],
        }
