"""Privilege Escalation Risk Detector Engine —
detect privilege escalation risks,
classify escalation patterns, rank by severity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EscalationType(StrEnum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    DIAGONAL = "diagonal"
    TEMPORAL = "temporal"


class DetectionSource(StrEnum):
    AUDIT_LOG = "audit_log"
    POLICY_CHECK = "policy_check"
    BEHAVIOR = "behavior"
    CONFIGURATION = "configuration"


class EscalationSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class EscalationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    resource_id: str = ""
    escalation_type: EscalationType = EscalationType.VERTICAL
    detection_source: DetectionSource = DetectionSource.AUDIT_LOG
    severity: EscalationSeverity = EscalationSeverity.LOW
    risk_score: float = 0.0
    privilege_level_before: int = 0
    privilege_level_after: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EscalationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    escalation_type: EscalationType = EscalationType.VERTICAL
    severity: EscalationSeverity = EscalationSeverity.LOW
    composite_risk: float = 0.0
    privilege_delta: int = 0
    confirmed_attempt: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EscalationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_escalation_type: dict[str, int] = Field(default_factory=dict)
    by_detection_source: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    critical_users: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PrivilegeEscalationRiskDetectorEngine:
    """Detect privilege escalation risks, classify escalation patterns,
    and rank escalations by severity."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[EscalationRecord] = []
        self._analyses: dict[str, EscalationAnalysis] = {}
        logger.info(
            "privilege_escalation_risk_detector_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        user_id: str = "",
        resource_id: str = "",
        escalation_type: EscalationType = EscalationType.VERTICAL,
        detection_source: DetectionSource = DetectionSource.AUDIT_LOG,
        severity: EscalationSeverity = EscalationSeverity.LOW,
        risk_score: float = 0.0,
        privilege_level_before: int = 0,
        privilege_level_after: int = 0,
        description: str = "",
    ) -> EscalationRecord:
        record = EscalationRecord(
            user_id=user_id,
            resource_id=resource_id,
            escalation_type=escalation_type,
            detection_source=detection_source,
            severity=severity,
            risk_score=risk_score,
            privilege_level_before=privilege_level_before,
            privilege_level_after=privilege_level_after,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "privilege_escalation_risk.record_added",
            record_id=record.id,
            user_id=user_id,
        )
        return record

    def process(self, key: str) -> EscalationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        sev_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        w = sev_weights.get(rec.severity.value, 1)
        composite = round(w * rec.risk_score, 2)
        delta = rec.privilege_level_after - rec.privilege_level_before
        analysis = EscalationAnalysis(
            user_id=rec.user_id,
            escalation_type=rec.escalation_type,
            severity=rec.severity,
            composite_risk=composite,
            privilege_delta=delta,
            confirmed_attempt=delta > 0 and rec.risk_score > 0.5,
            description=(f"User {rec.user_id} escalation delta={delta} risk={composite}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> EscalationReport:
        by_et: dict[str, int] = {}
        by_ds: dict[str, int] = {}
        by_sv: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.escalation_type.value
            by_et[k] = by_et.get(k, 0) + 1
            k2 = r.detection_source.value
            by_ds[k2] = by_ds.get(k2, 0) + 1
            k3 = r.severity.value
            by_sv[k3] = by_sv.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        critical_users = list(
            {
                r.user_id
                for r in self._records
                if r.severity in (EscalationSeverity.CRITICAL, EscalationSeverity.HIGH)
            }
        )[:10]
        recs: list[str] = []
        if critical_users:
            recs.append(f"{len(critical_users)} users with critical escalation attempts")
        if not recs:
            recs.append("No critical privilege escalation detected")
        return EscalationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_escalation_type=by_et,
            by_detection_source=by_ds,
            by_severity=by_sv,
            critical_users=critical_users,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        et_dist: dict[str, int] = {}
        for r in self._records:
            k = r.escalation_type.value
            et_dist[k] = et_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "escalation_type_distribution": et_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("privilege_escalation_risk_detector_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def detect_escalation_attempts(self) -> list[dict[str, Any]]:
        """Detect users with active privilege escalation attempts."""
        user_data: dict[str, list[EscalationRecord]] = {}
        for r in self._records:
            user_data.setdefault(r.user_id, []).append(r)
        results: list[dict[str, Any]] = []
        for uid, recs in user_data.items():
            max_delta = max(rec.privilege_level_after - rec.privilege_level_before for rec in recs)
            max_risk = max(rec.risk_score for rec in recs)
            escalation_types = list({rec.escalation_type.value for rec in recs})
            results.append(
                {
                    "user_id": uid,
                    "max_privilege_delta": max_delta,
                    "max_risk_score": round(max_risk, 2),
                    "escalation_types": escalation_types,
                    "attempt_count": len(recs),
                    "confirmed": max_delta > 0 and max_risk > 0.5,
                }
            )
        results.sort(key=lambda x: x["max_risk_score"], reverse=True)
        return results

    def classify_escalation_patterns(self) -> list[dict[str, Any]]:
        """Classify privilege escalation by type and detection source."""
        pattern_map: dict[str, dict[str, Any]] = {}
        for r in self._records:
            pat_key = f"{r.escalation_type.value}:{r.detection_source.value}"
            if pat_key not in pattern_map:
                pattern_map[pat_key] = {
                    "escalation_type": r.escalation_type.value,
                    "detection_source": r.detection_source.value,
                    "count": 0,
                    "total_risk": 0.0,
                    "severities": {},
                }
            entry = pattern_map[pat_key]
            entry["count"] += 1
            entry["total_risk"] += r.risk_score
            sv = r.severity.value
            entry["severities"][sv] = entry["severities"].get(sv, 0) + 1
        results: list[dict[str, Any]] = []
        for pat_key, data in pattern_map.items():
            cnt = data["count"]
            results.append(
                {
                    "pattern_key": pat_key,
                    "escalation_type": data["escalation_type"],
                    "detection_source": data["detection_source"],
                    "count": cnt,
                    "avg_risk": round(data["total_risk"] / cnt, 2),
                    "severity_breakdown": data["severities"],
                }
            )
        results.sort(key=lambda x: x["count"], reverse=True)
        return results

    def rank_escalations_by_severity(self) -> list[dict[str, Any]]:
        """Rank escalation records by composite severity score."""
        sev_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        results: list[dict[str, Any]] = []
        for r in self._records:
            w = sev_weights.get(r.severity.value, 1)
            composite = round(w * r.risk_score, 2)
            delta = r.privilege_level_after - r.privilege_level_before
            results.append(
                {
                    "record_id": r.id,
                    "user_id": r.user_id,
                    "escalation_type": r.escalation_type.value,
                    "severity": r.severity.value,
                    "privilege_delta": delta,
                    "composite_score": composite,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["composite_score"], reverse=True)
        for idx, entry in enumerate(results, 1):
            entry["rank"] = idx
        return results
