"""Identity Threat Detection — credential stuffing, account takeover, MFA bypass."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class IdentityThreat(StrEnum):
    CREDENTIAL_STUFFING = "credential_stuffing"
    ACCOUNT_TAKEOVER = "account_takeover"
    MFA_BYPASS = "mfa_bypass"
    SESSION_HIJACK = "session_hijack"
    BRUTE_FORCE = "brute_force"


class AuthProtocol(StrEnum):
    OAUTH2 = "oauth2"
    SAML = "saml"
    LDAP = "ldap"
    KERBEROS = "kerberos"
    CUSTOM = "custom"


class RiskScore(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


# --- Models ---


class IdentityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_name: str = ""
    identity_threat: IdentityThreat = IdentityThreat.CREDENTIAL_STUFFING
    auth_protocol: AuthProtocol = AuthProtocol.OAUTH2
    risk_score_level: RiskScore = RiskScore.CRITICAL
    detection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class IdentityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_name: str = ""
    identity_threat: IdentityThreat = IdentityThreat.CREDENTIAL_STUFFING
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IdentityThreatReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_threat_count: int = 0
    avg_detection_score: float = 0.0
    by_threat: dict[str, int] = Field(default_factory=dict)
    by_protocol: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_high_threat: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IdentityThreatDetection:
    """Detect identity threats including credential stuffing and account takeover."""

    def __init__(
        self,
        max_records: int = 200000,
        identity_threat_threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._identity_threat_threshold = identity_threat_threshold
        self._records: list[IdentityRecord] = []
        self._analyses: list[IdentityAnalysis] = []
        logger.info(
            "identity_threat_detection.initialized",
            max_records=max_records,
            identity_threat_threshold=identity_threat_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_threat(
        self,
        threat_name: str,
        identity_threat: IdentityThreat = IdentityThreat.CREDENTIAL_STUFFING,
        auth_protocol: AuthProtocol = AuthProtocol.OAUTH2,
        risk_score_level: RiskScore = RiskScore.CRITICAL,
        detection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> IdentityRecord:
        record = IdentityRecord(
            threat_name=threat_name,
            identity_threat=identity_threat,
            auth_protocol=auth_protocol,
            risk_score_level=risk_score_level,
            detection_score=detection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "identity_threat_detection.threat_recorded",
            record_id=record.id,
            threat_name=threat_name,
            identity_threat=identity_threat.value,
            auth_protocol=auth_protocol.value,
        )
        return record

    def get_threat(self, record_id: str) -> IdentityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_threats(
        self,
        identity_threat: IdentityThreat | None = None,
        auth_protocol: AuthProtocol | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[IdentityRecord]:
        results = list(self._records)
        if identity_threat is not None:
            results = [r for r in results if r.identity_threat == identity_threat]
        if auth_protocol is not None:
            results = [r for r in results if r.auth_protocol == auth_protocol]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        threat_name: str,
        identity_threat: IdentityThreat = IdentityThreat.CREDENTIAL_STUFFING,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> IdentityAnalysis:
        analysis = IdentityAnalysis(
            threat_name=threat_name,
            identity_threat=identity_threat,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "identity_threat_detection.analysis_added",
            threat_name=threat_name,
            identity_threat=identity_threat.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_threat_distribution(self) -> dict[str, Any]:
        """Group by identity_threat; return count and avg detection_score."""
        thr_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.identity_threat.value
            thr_data.setdefault(key, []).append(r.detection_score)
        result: dict[str, Any] = {}
        for thr, scores in thr_data.items():
            result[thr] = {
                "count": len(scores),
                "avg_detection_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_threat_detections(self) -> list[dict[str, Any]]:
        """Return records where detection_score > identity_threat_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.detection_score > self._identity_threat_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "threat_name": r.threat_name,
                        "identity_threat": r.identity_threat.value,
                        "detection_score": r.detection_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["detection_score"], reverse=True)

    def rank_by_detection_score(self) -> list[dict[str, Any]]:
        """Group by service, avg detection_score, sort descending (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.detection_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_detection_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_detection_score"], reverse=True)
        return results

    def detect_threat_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> IdentityThreatReport:
        by_threat: dict[str, int] = {}
        by_protocol: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_threat[r.identity_threat.value] = by_threat.get(r.identity_threat.value, 0) + 1
            by_protocol[r.auth_protocol.value] = by_protocol.get(r.auth_protocol.value, 0) + 1
            by_risk[r.risk_score_level.value] = by_risk.get(r.risk_score_level.value, 0) + 1
        high_threat_count = sum(
            1 for r in self._records if r.detection_score > self._identity_threat_threshold
        )
        scores = [r.detection_score for r in self._records]
        avg_detection_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_threat_detections()
        top_high_threat = [o["threat_name"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_threat_count > 0:
            recs.append(
                f"{high_threat_count} threat(s) above identity threat threshold "
                f"({self._identity_threat_threshold})"
            )
        if self._records and avg_detection_score > self._identity_threat_threshold:
            recs.append(
                f"Avg detection score {avg_detection_score} above threshold "
                f"({self._identity_threat_threshold})"
            )
        if not recs:
            recs.append("Identity threat detection posture is healthy")
        return IdentityThreatReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_threat_count=high_threat_count,
            avg_detection_score=avg_detection_score,
            by_threat=by_threat,
            by_protocol=by_protocol,
            by_risk=by_risk,
            top_high_threat=top_high_threat,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("identity_threat_detection.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        threat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.identity_threat.value
            threat_dist[key] = threat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "identity_threat_threshold": self._identity_threat_threshold,
            "threat_distribution": threat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
