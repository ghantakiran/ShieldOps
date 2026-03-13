"""Trace Root Cause Analyzer Engine —
analyze root causes from trace data,
correlate cause patterns, rank causes by likelihood."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RootCauseType(StrEnum):
    SERVICE_ERROR = "service_error"
    NETWORK_ISSUE = "network_issue"
    RESOURCE_LIMIT = "resource_limit"
    CONFIGURATION = "configuration"


class AnalysisDepth(StrEnum):
    SHALLOW = "shallow"
    MODERATE = "moderate"
    DEEP = "deep"
    EXHAUSTIVE = "exhaustive"


class CauseConfidence(StrEnum):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    SPECULATIVE = "speculative"


# --- Models ---


class TraceRootCauseRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    service_name: str = ""
    root_cause_type: RootCauseType = RootCauseType.SERVICE_ERROR
    analysis_depth: AnalysisDepth = AnalysisDepth.MODERATE
    cause_confidence: CauseConfidence = CauseConfidence.POSSIBLE
    likelihood_score: float = 0.0
    affected_spans: int = 0
    error_message: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TraceRootCauseAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    service_name: str = ""
    root_cause_type: RootCauseType = RootCauseType.SERVICE_ERROR
    weighted_score: float = 0.0
    is_confirmed: bool = False
    confidence: CauseConfidence = CauseConfidence.POSSIBLE
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TraceRootCauseReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_likelihood_score: float = 0.0
    by_root_cause_type: dict[str, int] = Field(default_factory=dict)
    by_analysis_depth: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    top_causes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TraceRootCauseAnalyzerEngine:
    """Analyze root causes from trace data,
    correlate cause patterns, rank causes by likelihood."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TraceRootCauseRecord] = []
        self._analyses: dict[str, TraceRootCauseAnalysis] = {}
        logger.info("trace_root_cause_analyzer_engine.init", max_records=max_records)

    def add_record(
        self,
        trace_id: str = "",
        service_name: str = "",
        root_cause_type: RootCauseType = RootCauseType.SERVICE_ERROR,
        analysis_depth: AnalysisDepth = AnalysisDepth.MODERATE,
        cause_confidence: CauseConfidence = CauseConfidence.POSSIBLE,
        likelihood_score: float = 0.0,
        affected_spans: int = 0,
        error_message: str = "",
        description: str = "",
    ) -> TraceRootCauseRecord:
        record = TraceRootCauseRecord(
            trace_id=trace_id,
            service_name=service_name,
            root_cause_type=root_cause_type,
            analysis_depth=analysis_depth,
            cause_confidence=cause_confidence,
            likelihood_score=likelihood_score,
            affected_spans=affected_spans,
            error_message=error_message,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "trace_root_cause.record_added",
            record_id=record.id,
            trace_id=trace_id,
        )
        return record

    def process(self, key: str) -> TraceRootCauseAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        conf_weights = {
            "confirmed": 1.0,
            "probable": 0.75,
            "possible": 0.5,
            "speculative": 0.25,
        }
        w = conf_weights.get(rec.cause_confidence.value, 0.5)
        weighted = round(rec.likelihood_score * w, 2)
        analysis = TraceRootCauseAnalysis(
            trace_id=rec.trace_id,
            service_name=rec.service_name,
            root_cause_type=rec.root_cause_type,
            weighted_score=weighted,
            is_confirmed=rec.cause_confidence == CauseConfidence.CONFIRMED,
            confidence=rec.cause_confidence,
            description=(f"Root cause {rec.root_cause_type.value} on {rec.service_name}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> TraceRootCauseReport:
        by_type: dict[str, int] = {}
        by_depth: dict[str, int] = {}
        by_conf: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            t = r.root_cause_type.value
            by_type[t] = by_type.get(t, 0) + 1
            d = r.analysis_depth.value
            by_depth[d] = by_depth.get(d, 0) + 1
            c = r.cause_confidence.value
            by_conf[c] = by_conf.get(c, 0) + 1
            scores.append(r.likelihood_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        top_causes = list(
            {
                r.root_cause_type.value
                for r in self._records
                if r.cause_confidence in (CauseConfidence.CONFIRMED, CauseConfidence.PROBABLE)
            }
        )[:10]
        recs: list[str] = []
        if top_causes:
            recs.append(f"Confirmed/probable causes: {', '.join(top_causes)}")
        if not recs:
            recs.append("No confirmed root causes identified")
        return TraceRootCauseReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_likelihood_score=avg,
            by_root_cause_type=by_type,
            by_analysis_depth=by_depth,
            by_confidence=by_conf,
            top_causes=top_causes,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            k = r.root_cause_type.value
            type_dist[k] = type_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "cause_type_distribution": type_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("trace_root_cause_analyzer_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def analyze_root_causes(self) -> list[dict[str, Any]]:
        """Analyze and aggregate root causes by service."""
        service_causes: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            service_causes.setdefault(r.service_name, []).append(
                {
                    "cause_type": r.root_cause_type.value,
                    "score": r.likelihood_score,
                    "confidence": r.cause_confidence.value,
                }
            )
        results: list[dict[str, Any]] = []
        for svc, causes in service_causes.items():
            avg_score = sum(c["score"] for c in causes) / len(causes)
            results.append(
                {
                    "service_name": svc,
                    "cause_count": len(causes),
                    "avg_likelihood": round(avg_score, 2),
                    "cause_types": list({c["cause_type"] for c in causes}),
                }
            )
        results.sort(key=lambda x: x["avg_likelihood"], reverse=True)
        return results

    def correlate_cause_patterns(self) -> list[dict[str, Any]]:
        """Correlate root cause types with analysis depth patterns."""
        pattern_map: dict[str, dict[str, Any]] = {}
        for r in self._records:
            pkey = f"{r.root_cause_type.value}:{r.analysis_depth.value}"
            if pkey not in pattern_map:
                pattern_map[pkey] = {
                    "root_cause_type": r.root_cause_type.value,
                    "analysis_depth": r.analysis_depth.value,
                    "count": 0,
                    "total_score": 0.0,
                }
            pattern_map[pkey]["count"] += 1
            pattern_map[pkey]["total_score"] += r.likelihood_score
        results: list[dict[str, Any]] = []
        for pat in pattern_map.values():
            cnt = pat["count"]
            results.append(
                {
                    "pattern": f"{pat['root_cause_type']}:{pat['analysis_depth']}",
                    "root_cause_type": pat["root_cause_type"],
                    "analysis_depth": pat["analysis_depth"],
                    "count": cnt,
                    "avg_score": round(pat["total_score"] / cnt, 2),
                }
            )
        results.sort(key=lambda x: x["avg_score"], reverse=True)
        return results

    def rank_causes_by_likelihood(self) -> list[dict[str, Any]]:
        """Rank all root cause records by weighted likelihood."""
        conf_weights = {
            "confirmed": 1.0,
            "probable": 0.75,
            "possible": 0.5,
            "speculative": 0.25,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            w = conf_weights.get(r.cause_confidence.value, 0.5)
            weighted = round(r.likelihood_score * w, 2)
            results.append(
                {
                    "trace_id": r.trace_id,
                    "service_name": r.service_name,
                    "root_cause_type": r.root_cause_type.value,
                    "confidence": r.cause_confidence.value,
                    "weighted_likelihood": weighted,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["weighted_likelihood"], reverse=True)
        for idx, entry in enumerate(results, 1):
            entry["rank"] = idx
        return results
