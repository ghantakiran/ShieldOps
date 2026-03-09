"""AIOps Correlation Engine — ML-powered cross-signal correlation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SignalType(StrEnum):
    METRIC = "metric"
    LOG = "log"
    TRACE = "trace"
    EVENT = "event"
    ALERT = "alert"


class CorrelationStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"


class PatternType(StrEnum):
    TEMPORAL = "temporal"
    CAUSAL = "causal"
    STATISTICAL = "statistical"
    TOPOLOGICAL = "topological"


# --- Models ---


class SignalRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    signal_type: SignalType = SignalType.METRIC
    source: str = ""
    value: float = 0.0
    tags: dict[str, str] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class CorrelationResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signal_a: str = ""
    signal_b: str = ""
    strength: CorrelationStrength = CorrelationStrength.NONE
    score: float = 0.0
    pattern_type: PatternType = PatternType.STATISTICAL
    confidence: float = 0.0
    created_at: float = Field(default_factory=time.time)


class CorrelationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_signals: int = 0
    total_correlations: int = 0
    strong_count: int = 0
    avg_score: float = 0.0
    by_signal_type: dict[str, int] = Field(default_factory=dict)
    by_strength: dict[str, int] = Field(default_factory=dict)
    root_cause_candidates: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AIOpsCorrelationEngine:
    """ML-powered cross-signal correlation for AIOps."""

    def __init__(
        self,
        max_signals: int = 100000,
        correlation_threshold: float = 0.6,
    ) -> None:
        self._max_signals = max_signals
        self._correlation_threshold = correlation_threshold
        self._signals: list[SignalRecord] = []
        self._correlations: list[CorrelationResult] = []
        logger.info(
            "aiops_correlation_engine.initialized",
            max_signals=max_signals,
            correlation_threshold=correlation_threshold,
        )

    def add_signal(
        self,
        name: str,
        signal_type: SignalType = SignalType.METRIC,
        source: str = "",
        value: float = 0.0,
        tags: dict[str, str] | None = None,
    ) -> SignalRecord:
        """Ingest a signal for correlation analysis."""
        record = SignalRecord(
            name=name,
            signal_type=signal_type,
            source=source,
            value=value,
            tags=tags or {},
        )
        self._signals.append(record)
        if len(self._signals) > self._max_signals:
            self._signals = self._signals[-self._max_signals :]
        logger.info(
            "aiops_correlation_engine.signal_added",
            signal_id=record.id,
            name=name,
            signal_type=signal_type.value,
        )
        return record

    def correlate_signals(
        self,
        window_seconds: float = 300.0,
    ) -> list[CorrelationResult]:
        """Correlate signals within a time window."""
        results: list[CorrelationResult] = []
        now = time.time()
        window_signals = [s for s in self._signals if now - s.timestamp <= window_seconds]
        source_groups: dict[str, list[SignalRecord]] = {}
        for s in window_signals:
            source_groups.setdefault(s.source, []).append(s)
        sources = list(source_groups.keys())
        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                vals_a = [s.value for s in source_groups[sources[i]]]
                vals_b = [s.value for s in source_groups[sources[j]]]
                avg_a = sum(vals_a) / len(vals_a) if vals_a else 0
                avg_b = sum(vals_b) / len(vals_b) if vals_b else 0
                diff = abs(avg_a - avg_b)
                score = round(max(0, 1.0 - diff / 100.0), 4)
                if score >= self._correlation_threshold:
                    strength = CorrelationStrength.STRONG
                elif score >= 0.4:
                    strength = CorrelationStrength.MODERATE
                elif score >= 0.2:
                    strength = CorrelationStrength.WEAK
                else:
                    strength = CorrelationStrength.NONE
                cr = CorrelationResult(
                    signal_a=sources[i],
                    signal_b=sources[j],
                    strength=strength,
                    score=score,
                    confidence=score * 0.9,
                )
                results.append(cr)
                self._correlations.append(cr)
        logger.info(
            "aiops_correlation_engine.correlated",
            count=len(results),
        )
        return results

    def detect_patterns(self) -> list[dict[str, Any]]:
        """Detect recurring patterns across signals."""
        patterns: list[dict[str, Any]] = []
        type_groups: dict[str, list[float]] = {}
        for s in self._signals:
            type_groups.setdefault(s.signal_type.value, []).append(s.value)
        for sig_type, values in type_groups.items():
            avg = sum(values) / len(values) if values else 0
            variance = sum((v - avg) ** 2 for v in values) / len(values) if values else 0
            patterns.append(
                {
                    "signal_type": sig_type,
                    "count": len(values),
                    "avg_value": round(avg, 2),
                    "variance": round(variance, 2),
                    "pattern": "spike" if variance > 100 else "stable",
                }
            )
        return patterns

    def build_correlation_graph(self) -> dict[str, Any]:
        """Build a graph of correlated signals."""
        nodes: set[str] = set()
        edges: list[dict[str, Any]] = []
        for c in self._correlations:
            nodes.add(c.signal_a)
            nodes.add(c.signal_b)
            edges.append(
                {
                    "source": c.signal_a,
                    "target": c.signal_b,
                    "weight": c.score,
                    "strength": c.strength.value,
                }
            )
        return {
            "nodes": sorted(nodes),
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    def score_correlations(self) -> dict[str, Any]:
        """Aggregate scores across all correlations."""
        if not self._correlations:
            return {"avg_score": 0.0, "max_score": 0.0, "count": 0}
        scores = [c.score for c in self._correlations]
        return {
            "avg_score": round(sum(scores) / len(scores), 4),
            "max_score": round(max(scores), 4),
            "min_score": round(min(scores), 4),
            "count": len(scores),
        }

    def get_root_cause_candidates(self) -> list[dict[str, Any]]:
        """Identify root cause candidates based on correlation density."""
        source_scores: dict[str, list[float]] = {}
        for c in self._correlations:
            source_scores.setdefault(c.signal_a, []).append(c.score)
            source_scores.setdefault(c.signal_b, []).append(c.score)
        candidates: list[dict[str, Any]] = []
        for src, scores in source_scores.items():
            avg = sum(scores) / len(scores) if scores else 0
            candidates.append(
                {
                    "source": src,
                    "correlation_count": len(scores),
                    "avg_score": round(avg, 4),
                }
            )
        candidates.sort(key=lambda x: x["avg_score"], reverse=True)
        return candidates

    def generate_report(self) -> CorrelationReport:
        """Generate a comprehensive correlation report."""
        by_type: dict[str, int] = {}
        for s in self._signals:
            by_type[s.signal_type.value] = by_type.get(s.signal_type.value, 0) + 1
        by_str: dict[str, int] = {}
        for c in self._correlations:
            by_str[c.strength.value] = by_str.get(c.strength.value, 0) + 1
        scores = [c.score for c in self._correlations]
        avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        strong = sum(1 for c in self._correlations if c.strength == CorrelationStrength.STRONG)
        candidates = self.get_root_cause_candidates()
        recs: list[str] = []
        if strong > 0:
            recs.append(f"{strong} strong correlation(s) detected")
        if not recs:
            recs.append("No significant correlations found")
        return CorrelationReport(
            total_signals=len(self._signals),
            total_correlations=len(self._correlations),
            strong_count=strong,
            avg_score=avg_score,
            by_signal_type=by_type,
            by_strength=by_str,
            root_cause_candidates=[c["source"] for c in candidates[:5]],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        """Clear all signals and correlations."""
        self._signals.clear()
        self._correlations.clear()
        logger.info("aiops_correlation_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        """Return engine statistics."""
        return {
            "total_signals": len(self._signals),
            "total_correlations": len(self._correlations),
            "correlation_threshold": self._correlation_threshold,
            "unique_sources": len({s.source for s in self._signals}),
        }
