"""Network Flow Analyzer — C2 beaconing, DNS tunneling, exfiltration indicators."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FlowType(StrEnum):
    C2_BEACONING = "c2_beaconing"
    DNS_TUNNELING = "dns_tunneling"
    DATA_EXFILTRATION = "data_exfiltration"
    LATERAL_MOVEMENT = "lateral_movement"
    PORT_SCANNING = "port_scanning"


class FlowSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BENIGN = "benign"


class AnalysisMethod(StrEnum):
    PATTERN_MATCHING = "pattern_matching"
    FREQUENCY_ANALYSIS = "frequency_analysis"
    VOLUME_ANALYSIS = "volume_analysis"
    PROTOCOL_ANALYSIS = "protocol_analysis"
    BEHAVIORAL = "behavioral"


# --- Models ---


class FlowRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    flow_name: str = ""
    flow_type: FlowType = FlowType.C2_BEACONING
    flow_severity: FlowSeverity = FlowSeverity.CRITICAL
    analysis_method: AnalysisMethod = AnalysisMethod.PATTERN_MATCHING
    suspicion_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class FlowAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    flow_name: str = ""
    flow_type: FlowType = FlowType.C2_BEACONING
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FlowReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_suspicion_count: int = 0
    avg_suspicion_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    top_high_suspicion: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class NetworkFlowAnalyzer:
    """Analyze network flows for C2 beaconing, DNS tunneling, and exfiltration."""

    def __init__(
        self,
        max_records: int = 200000,
        suspicion_score_threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._suspicion_score_threshold = suspicion_score_threshold
        self._records: list[FlowRecord] = []
        self._analyses: list[FlowAnalysis] = []
        logger.info(
            "network_flow_analyzer.initialized",
            max_records=max_records,
            suspicion_score_threshold=suspicion_score_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_flow(
        self,
        flow_name: str,
        flow_type: FlowType = FlowType.C2_BEACONING,
        flow_severity: FlowSeverity = FlowSeverity.CRITICAL,
        analysis_method: AnalysisMethod = AnalysisMethod.PATTERN_MATCHING,
        suspicion_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> FlowRecord:
        record = FlowRecord(
            flow_name=flow_name,
            flow_type=flow_type,
            flow_severity=flow_severity,
            analysis_method=analysis_method,
            suspicion_score=suspicion_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "network_flow_analyzer.flow_recorded",
            record_id=record.id,
            flow_name=flow_name,
            flow_type=flow_type.value,
            flow_severity=flow_severity.value,
        )
        return record

    def get_flow(self, record_id: str) -> FlowRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_flows(
        self,
        flow_type: FlowType | None = None,
        flow_severity: FlowSeverity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FlowRecord]:
        results = list(self._records)
        if flow_type is not None:
            results = [r for r in results if r.flow_type == flow_type]
        if flow_severity is not None:
            results = [r for r in results if r.flow_severity == flow_severity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        flow_name: str,
        flow_type: FlowType = FlowType.C2_BEACONING,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> FlowAnalysis:
        analysis = FlowAnalysis(
            flow_name=flow_name,
            flow_type=flow_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "network_flow_analyzer.analysis_added",
            flow_name=flow_name,
            flow_type=flow_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_flow_distribution(self) -> dict[str, Any]:
        """Group by flow_type; return count and avg suspicion_score."""
        src_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.flow_type.value
            src_data.setdefault(key, []).append(r.suspicion_score)
        result: dict[str, Any] = {}
        for src, scores in src_data.items():
            result[src] = {
                "count": len(scores),
                "avg_suspicion_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_suspicion_flows(self) -> list[dict[str, Any]]:
        """Return records where suspicion_score > suspicion_score_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.suspicion_score > self._suspicion_score_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "flow_name": r.flow_name,
                        "flow_type": r.flow_type.value,
                        "suspicion_score": r.suspicion_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["suspicion_score"], reverse=True)

    def rank_by_suspicion(self) -> list[dict[str, Any]]:
        """Group by service, avg suspicion_score, sort descending (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.suspicion_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_suspicion_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_suspicion_score"], reverse=True)
        return results

    def detect_flow_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> FlowReport:
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_method: dict[str, int] = {}
        for r in self._records:
            by_type[r.flow_type.value] = by_type.get(r.flow_type.value, 0) + 1
            by_severity[r.flow_severity.value] = by_severity.get(r.flow_severity.value, 0) + 1
            by_method[r.analysis_method.value] = by_method.get(r.analysis_method.value, 0) + 1
        high_suspicion_count = sum(
            1 for r in self._records if r.suspicion_score > self._suspicion_score_threshold
        )
        scores = [r.suspicion_score for r in self._records]
        avg_suspicion_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_suspicion_flows()
        top_high_suspicion = [o["flow_name"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_suspicion_count > 0:
            recs.append(
                f"{high_suspicion_count} flow(s) above suspicion score threshold "
                f"({self._suspicion_score_threshold})"
            )
        if self._records and avg_suspicion_score > self._suspicion_score_threshold:
            recs.append(
                f"Avg suspicion score {avg_suspicion_score} above threshold "
                f"({self._suspicion_score_threshold})"
            )
        if not recs:
            recs.append("Network flow analysis is healthy")
        return FlowReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_suspicion_count=high_suspicion_count,
            avg_suspicion_score=avg_suspicion_score,
            by_type=by_type,
            by_severity=by_severity,
            by_method=by_method,
            top_high_suspicion=top_high_suspicion,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("network_flow_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.flow_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "suspicion_score_threshold": self._suspicion_score_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
