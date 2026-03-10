"""Runtime Threat Analyzer
analyze runtime behavior, detect evasion techniques,
compute threat severity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RuntimeContext(StrEnum):
    CONTAINER = "container"
    SERVERLESS = "serverless"
    VM = "vm"
    BARE_METAL = "bare_metal"


class ThreatBehavior(StrEnum):
    PROCESS_INJECTION = "process_injection"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    LATERAL_MOVEMENT = "lateral_movement"
    DATA_STAGING = "data_staging"


class DetectionMethod(StrEnum):
    BEHAVIORAL = "behavioral"
    SIGNATURE = "signature"
    HEURISTIC = "heuristic"
    ANOMALY = "anomaly"


# --- Models ---


class RuntimeThreatRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_id: str = ""
    context: RuntimeContext = RuntimeContext.CONTAINER
    behavior: ThreatBehavior = ThreatBehavior.PROCESS_INJECTION
    detection: DetectionMethod = DetectionMethod.BEHAVIORAL
    severity_score: float = 0.0
    evasion_attempts: int = 0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RuntimeThreatAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_id: str = ""
    context: RuntimeContext = RuntimeContext.CONTAINER
    analysis_score: float = 0.0
    evasion_detected: bool = False
    threat_level: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RuntimeThreatReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_severity: float = 0.0
    total_evasions: int = 0
    by_context: dict[str, int] = Field(default_factory=dict)
    by_behavior: dict[str, int] = Field(default_factory=dict)
    by_detection: dict[str, int] = Field(default_factory=dict)
    critical_threats: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RuntimeThreatAnalyzer:
    """Analyze runtime behavior, detect evasion
    techniques, compute threat severity."""

    def __init__(
        self,
        max_records: int = 200000,
        severity_threshold: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._severity_threshold = severity_threshold
        self._records: list[RuntimeThreatRecord] = []
        self._analyses: list[RuntimeThreatAnalysis] = []
        logger.info(
            "runtime_threat_analyzer.initialized",
            max_records=max_records,
            severity_threshold=severity_threshold,
        )

    def add_record(
        self,
        threat_id: str,
        context: RuntimeContext = (RuntimeContext.CONTAINER),
        behavior: ThreatBehavior = (ThreatBehavior.PROCESS_INJECTION),
        detection: DetectionMethod = (DetectionMethod.BEHAVIORAL),
        severity_score: float = 0.0,
        evasion_attempts: int = 0,
        service: str = "",
        team: str = "",
    ) -> RuntimeThreatRecord:
        record = RuntimeThreatRecord(
            threat_id=threat_id,
            context=context,
            behavior=behavior,
            detection=detection,
            severity_score=severity_score,
            evasion_attempts=evasion_attempts,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "runtime_threat_analyzer.record_added",
            record_id=record.id,
            threat_id=threat_id,
        )
        return record

    def process(self, key: str) -> RuntimeThreatAnalysis | None:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return None
        evasion = rec.evasion_attempts > 0
        level = (
            "critical"
            if rec.severity_score >= 90
            else "high"
            if rec.severity_score >= 70
            else "medium"
            if rec.severity_score >= 40
            else "low"
        )
        analysis = RuntimeThreatAnalysis(
            threat_id=rec.threat_id,
            context=rec.context,
            analysis_score=round(rec.severity_score, 2),
            evasion_detected=evasion,
            threat_level=level,
            description=(f"Threat {rec.threat_id} level={level}"),
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return analysis

    def generate_report(self) -> RuntimeThreatReport:
        by_ctx: dict[str, int] = {}
        by_beh: dict[str, int] = {}
        by_det: dict[str, int] = {}
        sevs: list[float] = []
        total_ev = 0
        for r in self._records:
            c = r.context.value
            by_ctx[c] = by_ctx.get(c, 0) + 1
            b = r.behavior.value
            by_beh[b] = by_beh.get(b, 0) + 1
            d = r.detection.value
            by_det[d] = by_det.get(d, 0) + 1
            sevs.append(r.severity_score)
            total_ev += r.evasion_attempts
        avg_sev = round(sum(sevs) / len(sevs), 2) if sevs else 0.0
        critical = [
            r.threat_id for r in self._records if r.severity_score >= self._severity_threshold
        ][:5]
        recs: list[str] = []
        if critical:
            recs.append(f"{len(critical)} critical threats detected")
        if total_ev > 0:
            recs.append(f"{total_ev} evasion attempts found")
        if not recs:
            recs.append("Runtime threats within norms")
        return RuntimeThreatReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_severity=avg_sev,
            total_evasions=total_ev,
            by_context=by_ctx,
            by_behavior=by_beh,
            by_detection=by_det,
            critical_threats=critical,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ctx_dist: dict[str, int] = {}
        for r in self._records:
            k = r.context.value
            ctx_dist[k] = ctx_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "severity_threshold": (self._severity_threshold),
            "context_distribution": ctx_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("runtime_threat_analyzer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def analyze_runtime_behavior(
        self,
    ) -> list[dict[str, Any]]:
        """Analyze runtime behavior by context."""
        ctx_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            k = r.context.value
            ctx_data.setdefault(k, []).append(
                {
                    "threat_id": r.threat_id,
                    "behavior": r.behavior.value,
                    "severity": r.severity_score,
                    "evasions": r.evasion_attempts,
                }
            )
        results: list[dict[str, Any]] = []
        for ctx, items in ctx_data.items():
            avg_sev = round(
                sum(i["severity"] for i in items) / len(items),
                2,
            )
            results.append(
                {
                    "context": ctx,
                    "threat_count": len(items),
                    "avg_severity": avg_sev,
                    "items": items[:10],
                }
            )
        return results

    def detect_evasion_techniques(
        self,
    ) -> list[dict[str, Any]]:
        """Detect evasion techniques: records with
        evasion_attempts > 0."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.evasion_attempts > 0:
                results.append(
                    {
                        "threat_id": r.threat_id,
                        "context": r.context.value,
                        "behavior": r.behavior.value,
                        "evasion_attempts": (r.evasion_attempts),
                        "severity": r.severity_score,
                    }
                )
        results.sort(
            key=lambda x: x["evasion_attempts"],
            reverse=True,
        )
        return results

    def compute_threat_severity(
        self,
    ) -> dict[str, Any]:
        """Compute severity statistics per behavior."""
        if not self._records:
            return {
                "avg_severity": 0.0,
                "max_severity": 0.0,
                "by_behavior": {},
            }
        beh_sevs: dict[str, list[float]] = {}
        for r in self._records:
            k = r.behavior.value
            beh_sevs.setdefault(k, []).append(r.severity_score)
        by_beh: dict[str, float] = {}
        for b, vals in beh_sevs.items():
            by_beh[b] = round(sum(vals) / len(vals), 2)
        all_s = [r.severity_score for r in self._records]
        return {
            "avg_severity": round(sum(all_s) / len(all_s), 2),
            "max_severity": round(max(all_s), 2),
            "by_behavior": by_beh,
        }
