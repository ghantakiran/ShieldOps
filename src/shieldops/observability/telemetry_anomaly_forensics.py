"""TelemetryAnomalyForensics — anomaly forensics."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AnomalyOrigin(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    NETWORK = "network"
    EXTERNAL = "external"


class ForensicDepth(StrEnum):
    SURFACE = "surface"
    MODERATE = "moderate"
    DEEP = "deep"
    EXHAUSTIVE = "exhaustive"


class EvidenceType(StrEnum):
    METRIC_SPIKE = "metric_spike"
    LOG_PATTERN = "log_pattern"
    TRACE_GAP = "trace_gap"
    CONFIG_CHANGE = "config_change"


# --- Models ---


class ForensicRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    origin: AnomalyOrigin = AnomalyOrigin.APPLICATION
    depth: ForensicDepth = ForensicDepth.MODERATE
    evidence_type: EvidenceType = EvidenceType.METRIC_SPIKE
    score: float = 0.0
    severity: float = 0.0
    confidence: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ForensicAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    origin: AnomalyOrigin = AnomalyOrigin.APPLICATION
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ForensicReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    avg_severity: float = 0.0
    by_origin: dict[str, int] = Field(default_factory=dict)
    by_depth: dict[str, int] = Field(default_factory=dict)
    by_evidence_type: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TelemetryAnomalyForensics:
    """Telemetry Anomaly Forensics.

    Performs forensic analysis on telemetry
    anomalies to trace origin and build
    evidence chains.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ForensicRecord] = []
        self._analyses: list[ForensicAnalysis] = []
        logger.info(
            "telemetry_anomaly_forensics.init",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        origin: AnomalyOrigin = (AnomalyOrigin.APPLICATION),
        depth: ForensicDepth = ForensicDepth.MODERATE,
        evidence_type: EvidenceType = (EvidenceType.METRIC_SPIKE),
        score: float = 0.0,
        severity: float = 0.0,
        confidence: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ForensicRecord:
        record = ForensicRecord(
            name=name,
            origin=origin,
            depth=depth,
            evidence_type=evidence_type,
            score=score,
            severity=severity,
            confidence=confidence,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "telemetry_anomaly_forensics.added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.name == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        scores = [r.score for r in matching]
        avg = round(sum(scores) / len(scores), 2)
        sevs = [r.severity for r in matching]
        avg_sev = round(sum(sevs) / len(sevs), 2)
        return {
            "key": key,
            "record_count": len(matching),
            "avg_score": avg,
            "avg_severity": avg_sev,
        }

    def generate_report(self) -> ForensicReport:
        by_o: dict[str, int] = {}
        by_d: dict[str, int] = {}
        by_e: dict[str, int] = {}
        for r in self._records:
            v1 = r.origin.value
            by_o[v1] = by_o.get(v1, 0) + 1
            v2 = r.depth.value
            by_d[v2] = by_d.get(v2, 0) + 1
            v3 = r.evidence_type.value
            by_e[v3] = by_e.get(v3, 0) + 1
        scores = [r.score for r in self._records]
        avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
        sevs = [r.severity for r in self._records]
        avg_sev = round(sum(sevs) / len(sevs), 2) if sevs else 0.0
        recs: list[str] = []
        high_sev = sum(1 for r in self._records if r.severity > 80.0)
        if high_sev > 0:
            recs.append(f"{high_sev} high-severity anomaly(ies)")
        if avg_s < self._threshold and self._records:
            recs.append(f"Avg score {avg_s} below threshold {self._threshold}")
        if not recs:
            recs.append("Anomaly forensics healthy")
        return ForensicReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg_s,
            avg_severity=avg_sev,
            by_origin=by_o,
            by_depth=by_d,
            by_evidence_type=by_e,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        o_dist: dict[str, int] = {}
        for r in self._records:
            k = r.origin.value
            o_dist[k] = o_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "origin_distribution": o_dist,
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("telemetry_anomaly_forensics.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def trace_anomaly_origin(
        self,
    ) -> dict[str, Any]:
        """Trace anomalies back to origin."""
        if not self._records:
            return {"status": "no_data"}
        origin_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            orig = r.origin.value
            if orig not in origin_data:
                origin_data[orig] = {
                    "count": 0,
                    "total_severity": 0.0,
                    "total_confidence": 0.0,
                    "services": set(),
                }
            origin_data[orig]["count"] += 1
            origin_data[orig]["total_severity"] += r.severity
            origin_data[orig]["total_confidence"] += r.confidence
            origin_data[orig]["services"].add(r.service)
        result: dict[str, Any] = {}
        for orig, data in origin_data.items():
            cnt = data["count"]
            result[orig] = {
                "count": cnt,
                "avg_severity": round(data["total_severity"] / cnt, 2),
                "avg_confidence": round(
                    data["total_confidence"] / cnt,
                    4,
                ),
                "affected_services": len(data["services"]),
            }
        return result

    def correlate_evidence_chain(
        self,
    ) -> list[dict[str, Any]]:
        """Correlate evidence into chains."""
        svc_evidence: dict[str, list[ForensicRecord]] = {}
        for r in self._records:
            svc_evidence.setdefault(r.service, []).append(r)
        chains: list[dict[str, Any]] = []
        for svc, recs in svc_evidence.items():
            if len(recs) < 2:
                continue
            sorted_recs = sorted(recs, key=lambda x: x.created_at)
            evidence_types = [r.evidence_type.value for r in sorted_recs]
            origins = {r.origin.value for r in sorted_recs}
            avg_conf = round(
                sum(r.confidence for r in sorted_recs) / len(sorted_recs),
                4,
            )
            chains.append(
                {
                    "service": svc,
                    "chain_length": len(sorted_recs),
                    "evidence_sequence": (evidence_types),
                    "origins": sorted(origins),
                    "avg_confidence": avg_conf,
                }
            )
        chains.sort(
            key=lambda x: x["chain_length"],
            reverse=True,
        )
        return chains

    def generate_forensic_timeline(
        self,
        service: str = "",
    ) -> list[dict[str, Any]]:
        """Generate forensic timeline."""
        matching = list(self._records)
        if service:
            matching = [r for r in matching if r.service == service]
        if not matching:
            return []
        sorted_recs = sorted(matching, key=lambda x: x.created_at)
        timeline: list[dict[str, Any]] = []
        for r in sorted_recs:
            timeline.append(
                {
                    "timestamp": r.created_at,
                    "name": r.name,
                    "origin": r.origin.value,
                    "evidence_type": (r.evidence_type.value),
                    "severity": r.severity,
                    "confidence": r.confidence,
                    "service": r.service,
                }
            )
        return timeline
