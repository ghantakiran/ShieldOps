"""Session Trust Evaluator — evaluate session trust levels and manage session security."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SessionRisk(StrEnum):
    HIJACKED = "hijacked"
    SUSPICIOUS = "suspicious"
    ELEVATED = "elevated"
    NORMAL = "normal"
    TRUSTED = "trusted"


class EvaluationTrigger(StrEnum):
    LOGIN = "login"
    ACCESS_CHANGE = "access_change"
    LOCATION_CHANGE = "location_change"
    TIMEOUT = "timeout"
    ANOMALY = "anomaly"


class TrustAction(StrEnum):
    CONTINUE = "continue"
    REAUTHENTICATE = "reauthenticate"
    RESTRICT = "restrict"
    TERMINATE = "terminate"
    MONITOR = "monitor"


# --- Models ---


class SessionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_eval_id: str = ""
    session_risk: SessionRisk = SessionRisk.HIJACKED
    evaluation_trigger: EvaluationTrigger = EvaluationTrigger.LOGIN
    trust_action: TrustAction = TrustAction.CONTINUE
    evaluation_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SessionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_eval_id: str = ""
    session_risk: SessionRisk = SessionRisk.HIJACKED
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SessionTrustReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_evaluation_score: float = 0.0
    by_session_risk: dict[str, int] = Field(default_factory=dict)
    by_evaluation_trigger: dict[str, int] = Field(default_factory=dict)
    by_trust_action: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SessionTrustEvaluator:
    """Evaluate session trust levels, detect anomalies, and manage session security posture."""

    def __init__(
        self,
        max_records: int = 200000,
        session_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._session_gap_threshold = session_gap_threshold
        self._records: list[SessionRecord] = []
        self._analyses: list[SessionAnalysis] = []
        logger.info(
            "session_trust_evaluator.initialized",
            max_records=max_records,
            session_gap_threshold=session_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_session(
        self,
        session_eval_id: str,
        session_risk: SessionRisk = SessionRisk.HIJACKED,
        evaluation_trigger: EvaluationTrigger = EvaluationTrigger.LOGIN,
        trust_action: TrustAction = TrustAction.CONTINUE,
        evaluation_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SessionRecord:
        record = SessionRecord(
            session_eval_id=session_eval_id,
            session_risk=session_risk,
            evaluation_trigger=evaluation_trigger,
            trust_action=trust_action,
            evaluation_score=evaluation_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "session_trust_evaluator.session_recorded",
            record_id=record.id,
            session_eval_id=session_eval_id,
            session_risk=session_risk.value,
            evaluation_trigger=evaluation_trigger.value,
        )
        return record

    def get_session(self, record_id: str) -> SessionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_sessions(
        self,
        session_risk: SessionRisk | None = None,
        evaluation_trigger: EvaluationTrigger | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SessionRecord]:
        results = list(self._records)
        if session_risk is not None:
            results = [r for r in results if r.session_risk == session_risk]
        if evaluation_trigger is not None:
            results = [r for r in results if r.evaluation_trigger == evaluation_trigger]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        session_eval_id: str,
        session_risk: SessionRisk = SessionRisk.HIJACKED,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SessionAnalysis:
        analysis = SessionAnalysis(
            session_eval_id=session_eval_id,
            session_risk=session_risk,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "session_trust_evaluator.analysis_added",
            session_eval_id=session_eval_id,
            session_risk=session_risk.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_session_distribution(self) -> dict[str, Any]:
        """Group by session_risk; return count and avg evaluation_score."""
        risk_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.session_risk.value
            risk_data.setdefault(key, []).append(r.evaluation_score)
        result: dict[str, Any] = {}
        for risk, scores in risk_data.items():
            result[risk] = {
                "count": len(scores),
                "avg_evaluation_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_session_gaps(self) -> list[dict[str, Any]]:
        """Return records where evaluation_score < session_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.evaluation_score < self._session_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "session_eval_id": r.session_eval_id,
                        "session_risk": r.session_risk.value,
                        "evaluation_score": r.evaluation_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["evaluation_score"])

    def rank_by_session(self) -> list[dict[str, Any]]:
        """Group by service, avg evaluation_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.evaluation_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_evaluation_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_evaluation_score"])
        return results

    def detect_session_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
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

    def generate_report(self) -> SessionTrustReport:
        by_session_risk: dict[str, int] = {}
        by_evaluation_trigger: dict[str, int] = {}
        by_trust_action: dict[str, int] = {}
        for r in self._records:
            by_session_risk[r.session_risk.value] = by_session_risk.get(r.session_risk.value, 0) + 1
            by_evaluation_trigger[r.evaluation_trigger.value] = (
                by_evaluation_trigger.get(r.evaluation_trigger.value, 0) + 1
            )
            by_trust_action[r.trust_action.value] = by_trust_action.get(r.trust_action.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.evaluation_score < self._session_gap_threshold
        )
        scores = [r.evaluation_score for r in self._records]
        avg_evaluation_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_session_gaps()
        top_gaps = [o["session_eval_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} session(s) below evaluation threshold ({self._session_gap_threshold})"
            )
        if self._records and avg_evaluation_score < self._session_gap_threshold:
            recs.append(
                f"Avg evaluation score {avg_evaluation_score} below threshold "
                f"({self._session_gap_threshold})"
            )
        if not recs:
            recs.append("Session trust evaluation is healthy")
        return SessionTrustReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_evaluation_score=avg_evaluation_score,
            by_session_risk=by_session_risk,
            by_evaluation_trigger=by_evaluation_trigger,
            by_trust_action=by_trust_action,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("session_trust_evaluator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        risk_dist: dict[str, int] = {}
        for r in self._records:
            key = r.session_risk.value
            risk_dist[key] = risk_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "session_gap_threshold": self._session_gap_threshold,
            "session_risk_distribution": risk_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
