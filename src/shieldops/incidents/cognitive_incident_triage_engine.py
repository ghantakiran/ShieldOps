"""Cognitive Incident Triage Engine

AI-driven incident triage recommending severity, routing,
and resolution strategies based on historical patterns.
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


class TriageDecision(StrEnum):
    AUTO_RESOLVE = "auto_resolve"
    ASSIGN_ONCALL = "assign_oncall"
    ESCALATE = "escalate"
    DEFER = "defer"
    INVESTIGATE = "investigate"


class SeverityRecommendation(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class TriageConfidence(StrEnum):
    DEFINITIVE = "definitive"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


# --- Models ---


class TriageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    service: str = ""
    recommended_severity: SeverityRecommendation = SeverityRecommendation.MEDIUM
    triage_decision: TriageDecision = TriageDecision.INVESTIGATE
    confidence: TriageConfidence = TriageConfidence.MODERATE
    similar_incident_count: int = 0
    blast_radius_score: float = 0.0
    responder_load_pct: float = 0.0
    resolution_time_minutes: float = 0.0
    created_at: float = Field(default_factory=time.time)


class TriageAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TriageReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_resolution_minutes: float = 0.0
    auto_resolve_rate: float = 0.0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_decision: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CognitiveIncidentTriageEngine:
    """Cognitive Incident Triage Engine

    AI-driven incident triage recommending severity
    and routing based on historical patterns.
    """

    def __init__(
        self,
        max_records: int = 200000,
        auto_resolve_threshold: float = 0.9,
    ) -> None:
        self._max_records = max_records
        self._auto_resolve_threshold = auto_resolve_threshold
        self._records: list[TriageRecord] = []
        self._analyses: list[TriageAnalysis] = []
        logger.info(
            "cognitive_incident_triage_engine.initialized",
            max_records=max_records,
            auto_resolve_threshold=(auto_resolve_threshold),
        )

    def add_record(
        self,
        incident_id: str,
        service: str,
        recommended_severity: SeverityRecommendation = (SeverityRecommendation.MEDIUM),
        triage_decision: TriageDecision = (TriageDecision.INVESTIGATE),
        confidence: TriageConfidence = (TriageConfidence.MODERATE),
        similar_incident_count: int = 0,
        blast_radius_score: float = 0.0,
        responder_load_pct: float = 0.0,
        resolution_time_minutes: float = 0.0,
    ) -> TriageRecord:
        record = TriageRecord(
            incident_id=incident_id,
            service=service,
            recommended_severity=recommended_severity,
            triage_decision=triage_decision,
            confidence=confidence,
            similar_incident_count=(similar_incident_count),
            blast_radius_score=blast_radius_score,
            responder_load_pct=responder_load_pct,
            resolution_time_minutes=(resolution_time_minutes),
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cognitive_incident_triage_engine.record_added",
            record_id=record.id,
            incident_id=incident_id,
            service=service,
        )
        return record

    def recommend_triage(self, incident_id: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.incident_id == incident_id]
        if not matching:
            return {
                "incident_id": incident_id,
                "status": "no_data",
            }
        latest = max(matching, key=lambda r: r.created_at)
        return {
            "incident_id": incident_id,
            "severity": (latest.recommended_severity.value),
            "decision": latest.triage_decision.value,
            "confidence": latest.confidence.value,
            "similar_count": (latest.similar_incident_count),
            "blast_radius": latest.blast_radius_score,
        }

    def compute_responder_load(self, service: str = "") -> dict[str, Any]:
        matching = list(self._records)
        if service:
            matching = [r for r in matching if r.service == service]
        if not matching:
            return {
                "service": service or "all",
                "status": "no_data",
            }
        loads = [r.responder_load_pct for r in matching]
        avg_load = round(sum(loads) / len(loads), 4)
        overloaded = sum(1 for ld in loads if ld > 0.8)
        return {
            "service": service or "all",
            "avg_load_pct": avg_load,
            "overloaded_count": overloaded,
            "total_incidents": len(matching),
        }

    def analyze_similar_incidents(self, incident_id: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.incident_id == incident_id]
        if not matching:
            return {
                "incident_id": incident_id,
                "status": "no_data",
            }
        latest = max(matching, key=lambda r: r.created_at)
        svc = latest.service
        similar = [r for r in self._records if r.service == svc and r.incident_id != incident_id]
        if not similar:
            return {
                "incident_id": incident_id,
                "similar_count": 0,
            }
        res_times = [r.resolution_time_minutes for r in similar if r.resolution_time_minutes > 0]
        avg_res = round(sum(res_times) / len(res_times), 2) if res_times else 0.0
        return {
            "incident_id": incident_id,
            "similar_count": len(similar),
            "avg_resolution_minutes": avg_res,
            "service": svc,
        }

    def process(self, incident_id: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.incident_id == incident_id]
        if not matching:
            return {
                "incident_id": incident_id,
                "status": "no_data",
            }
        latest = max(matching, key=lambda r: r.created_at)
        res_times = [r.resolution_time_minutes for r in matching if r.resolution_time_minutes > 0]
        avg_res = round(sum(res_times) / len(res_times), 2) if res_times else 0.0
        return {
            "incident_id": incident_id,
            "record_count": len(matching),
            "severity": (latest.recommended_severity.value),
            "decision": latest.triage_decision.value,
            "avg_resolution_minutes": avg_res,
        }

    def generate_report(self) -> TriageReport:
        by_sev: dict[str, int] = {}
        by_dec: dict[str, int] = {}
        by_conf: dict[str, int] = {}
        for r in self._records:
            sv = r.recommended_severity.value
            by_sev[sv] = by_sev.get(sv, 0) + 1
            dv = r.triage_decision.value
            by_dec[dv] = by_dec.get(dv, 0) + 1
            cv = r.confidence.value
            by_conf[cv] = by_conf.get(cv, 0) + 1
        total = len(self._records)
        res_times = [
            r.resolution_time_minutes for r in self._records if r.resolution_time_minutes > 0
        ]
        avg_res = round(sum(res_times) / len(res_times), 2) if res_times else 0.0
        auto = by_dec.get("auto_resolve", 0)
        auto_rate = round(auto / total, 4) if total else 0.0
        recs: list[str] = []
        low_conf = by_conf.get("low", 0)
        if total > 0 and low_conf / total > 0.3:
            recs.append("Over 30% low-confidence triage — improve signal enrichment")
        if avg_res > 60:
            recs.append(f"Avg resolution {avg_res:.0f}min — increase auto-resolve scope")
        if not recs:
            recs.append("Incident triage quality is nominal")
        return TriageReport(
            total_records=total,
            total_analyses=len(self._analyses),
            avg_resolution_minutes=avg_res,
            auto_resolve_rate=auto_rate,
            by_severity=by_sev,
            by_decision=by_dec,
            by_confidence=by_conf,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dec_dist: dict[str, int] = {}
        for r in self._records:
            k = r.triage_decision.value
            dec_dist[k] = dec_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "auto_resolve_threshold": (self._auto_resolve_threshold),
            "decision_distribution": dec_dist,
            "unique_incidents": len({r.incident_id for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("cognitive_incident_triage_engine.cleared")
        return {"status": "cleared"}
