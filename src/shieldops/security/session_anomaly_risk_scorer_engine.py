"""Session Anomaly Risk Scorer Engine —
score session anomaly risks,
detect session hijacking, rank sessions by risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AnomalyType(StrEnum):
    GEO_IMPOSSIBLE = "geo_impossible"
    DEVICE_CHANGE = "device_change"
    BEHAVIOR_SHIFT = "behavior_shift"
    DURATION_ANOMALY = "duration_anomaly"


class SessionType(StrEnum):
    WEB = "web"
    API = "api"
    SSH = "ssh"
    VPN = "vpn"


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class SessionAnomalyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    user_id: str = ""
    anomaly_type: AnomalyType = AnomalyType.BEHAVIOR_SHIFT
    session_type: SessionType = SessionType.WEB
    risk_level: RiskLevel = RiskLevel.LOW
    risk_score: float = 0.0
    session_duration_s: float = 0.0
    source_ip: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SessionAnomalyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    user_id: str = ""
    anomaly_type: AnomalyType = AnomalyType.BEHAVIOR_SHIFT
    composite_risk: float = 0.0
    hijacking_suspected: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SessionAnomalyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_anomaly_type: dict[str, int] = Field(default_factory=dict)
    by_session_type: dict[str, int] = Field(default_factory=dict)
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    suspicious_sessions: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SessionAnomalyRiskScorerEngine:
    """Score session anomaly risks, detect session hijacking,
    and rank sessions by risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[SessionAnomalyRecord] = []
        self._analyses: dict[str, SessionAnomalyAnalysis] = {}
        logger.info(
            "session_anomaly_risk_scorer_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        session_id: str = "",
        user_id: str = "",
        anomaly_type: AnomalyType = AnomalyType.BEHAVIOR_SHIFT,
        session_type: SessionType = SessionType.WEB,
        risk_level: RiskLevel = RiskLevel.LOW,
        risk_score: float = 0.0,
        session_duration_s: float = 0.0,
        source_ip: str = "",
        description: str = "",
    ) -> SessionAnomalyRecord:
        record = SessionAnomalyRecord(
            session_id=session_id,
            user_id=user_id,
            anomaly_type=anomaly_type,
            session_type=session_type,
            risk_level=risk_level,
            risk_score=risk_score,
            session_duration_s=session_duration_s,
            source_ip=source_ip,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "session_anomaly_risk.record_added",
            record_id=record.id,
            session_id=session_id,
        )
        return record

    def process(self, key: str) -> SessionAnomalyAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        level_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        w = level_weights.get(rec.risk_level.value, 1)
        composite = round(w * rec.risk_score, 2)
        hijacking = (
            rec.anomaly_type
            in (
                AnomalyType.GEO_IMPOSSIBLE,
                AnomalyType.DEVICE_CHANGE,
            )
            and rec.risk_score > 0.6
        )
        analysis = SessionAnomalyAnalysis(
            session_id=rec.session_id,
            user_id=rec.user_id,
            anomaly_type=rec.anomaly_type,
            composite_risk=composite,
            hijacking_suspected=hijacking,
            description=(
                f"Session {rec.session_id} anomaly={rec.anomaly_type.value} risk={composite}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> SessionAnomalyReport:
        by_at: dict[str, int] = {}
        by_st: dict[str, int] = {}
        by_rl: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.anomaly_type.value
            by_at[k] = by_at.get(k, 0) + 1
            k2 = r.session_type.value
            by_st[k2] = by_st.get(k2, 0) + 1
            k3 = r.risk_level.value
            by_rl[k3] = by_rl.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        suspicious = list(
            {
                r.session_id
                for r in self._records
                if r.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)
            }
        )[:10]
        recs: list[str] = []
        if suspicious:
            recs.append(f"{len(suspicious)} suspicious sessions require investigation")
        if not recs:
            recs.append("Session anomaly risk within normal bounds")
        return SessionAnomalyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_anomaly_type=by_at,
            by_session_type=by_st,
            by_risk_level=by_rl,
            suspicious_sessions=suspicious,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        at_dist: dict[str, int] = {}
        for r in self._records:
            k = r.anomaly_type.value
            at_dist[k] = at_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "anomaly_type_distribution": at_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("session_anomaly_risk_scorer_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def score_session_anomaly_risk(self) -> list[dict[str, Any]]:
        """Score session anomaly risk per user."""
        user_data: dict[str, list[SessionAnomalyRecord]] = {}
        for r in self._records:
            user_data.setdefault(r.user_id, []).append(r)
        level_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        results: list[dict[str, Any]] = []
        for uid, recs in user_data.items():
            total_risk = sum(
                level_weights.get(rec.risk_level.value, 1) * rec.risk_score for rec in recs
            )
            anomaly_types = list({rec.anomaly_type.value for rec in recs})
            session_types = list({rec.session_type.value for rec in recs})
            results.append(
                {
                    "user_id": uid,
                    "total_risk": round(total_risk, 2),
                    "anomaly_types": anomaly_types,
                    "session_types": session_types,
                    "session_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["total_risk"], reverse=True)
        return results

    def detect_session_hijacking(self) -> list[dict[str, Any]]:
        """Detect suspected session hijacking events."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.anomaly_type in (AnomalyType.GEO_IMPOSSIBLE, AnomalyType.DEVICE_CHANGE)
                and r.risk_score > 0.6
                and r.session_id not in seen
            ):
                seen.add(r.session_id)
                results.append(
                    {
                        "session_id": r.session_id,
                        "user_id": r.user_id,
                        "anomaly_type": r.anomaly_type.value,
                        "session_type": r.session_type.value,
                        "risk_score": r.risk_score,
                        "source_ip": r.source_ip,
                    }
                )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def rank_sessions_by_risk(self) -> list[dict[str, Any]]:
        """Rank sessions by composite anomaly risk score."""
        level_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        session_scores: dict[str, float] = {}
        for r in self._records:
            w = level_weights.get(r.risk_level.value, 1)
            session_scores[r.session_id] = session_scores.get(r.session_id, 0.0) + (
                w * r.risk_score
            )
        results: list[dict[str, Any]] = []
        for sid, score in session_scores.items():
            results.append(
                {
                    "session_id": sid,
                    "total_risk_score": round(score, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["total_risk_score"], reverse=True)
        for idx, entry in enumerate(results, 1):
            entry["rank"] = idx
        return results
