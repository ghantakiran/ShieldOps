"""Certificate Transparency Monitor — monitor CT logs for unauthorized certificates."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CertType(StrEnum):
    DV = "dv"
    OV = "ov"
    EV = "ev"
    SELF_SIGNED = "self_signed"
    WILDCARD = "wildcard"


class CertStatus(StrEnum):
    VALID = "valid"
    EXPIRING = "expiring"
    EXPIRED = "expired"
    REVOKED = "revoked"
    UNKNOWN = "unknown"


class MonitoringAction(StrEnum):
    ALERT = "alert"
    INVESTIGATE = "investigate"
    BLOCK = "block"
    RENEW = "renew"
    IGNORE = "ignore"


# --- Models ---


class CertTransparencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_name: str = ""
    cert_type: CertType = CertType.DV
    cert_status: CertStatus = CertStatus.VALID
    monitoring_action: MonitoringAction = MonitoringAction.ALERT
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CertTransparencyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_name: str = ""
    cert_type: CertType = CertType.DV
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CertTransparencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_risk_score: float = 0.0
    by_cert_type: dict[str, int] = Field(default_factory=dict)
    by_cert_status: dict[str, int] = Field(default_factory=dict)
    by_monitoring_action: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CertificateTransparencyMonitor:
    """Monitor certificate transparency logs for unauthorized or suspicious certificates."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._risk_threshold = risk_threshold
        self._records: list[CertTransparencyRecord] = []
        self._analyses: list[CertTransparencyAnalysis] = []
        logger.info(
            "certificate_transparency_monitor.initialized",
            max_records=max_records,
            risk_threshold=risk_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_certificate(
        self,
        domain_name: str,
        cert_type: CertType = CertType.DV,
        cert_status: CertStatus = CertStatus.VALID,
        monitoring_action: MonitoringAction = MonitoringAction.ALERT,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CertTransparencyRecord:
        record = CertTransparencyRecord(
            domain_name=domain_name,
            cert_type=cert_type,
            cert_status=cert_status,
            monitoring_action=monitoring_action,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "certificate_transparency_monitor.certificate_recorded",
            record_id=record.id,
            domain_name=domain_name,
            cert_type=cert_type.value,
            cert_status=cert_status.value,
        )
        return record

    def get_certificate(self, record_id: str) -> CertTransparencyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_certificates(
        self,
        cert_type: CertType | None = None,
        cert_status: CertStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CertTransparencyRecord]:
        results = list(self._records)
        if cert_type is not None:
            results = [r for r in results if r.cert_type == cert_type]
        if cert_status is not None:
            results = [r for r in results if r.cert_status == cert_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        domain_name: str,
        cert_type: CertType = CertType.DV,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CertTransparencyAnalysis:
        analysis = CertTransparencyAnalysis(
            domain_name=domain_name,
            cert_type=cert_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "certificate_transparency_monitor.analysis_added",
            domain_name=domain_name,
            cert_type=cert_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by cert_type; return count and avg risk_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.cert_type.value
            type_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for cert_type, scores in type_data.items():
            result[cert_type] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where risk_score < risk_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score < self._risk_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "domain_name": r.domain_name,
                        "cert_type": r.cert_type.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> CertTransparencyReport:
        by_cert_type: dict[str, int] = {}
        by_cert_status: dict[str, int] = {}
        by_monitoring_action: dict[str, int] = {}
        for r in self._records:
            by_cert_type[r.cert_type.value] = by_cert_type.get(r.cert_type.value, 0) + 1
            by_cert_status[r.cert_status.value] = by_cert_status.get(r.cert_status.value, 0) + 1
            by_monitoring_action[r.monitoring_action.value] = (
                by_monitoring_action.get(r.monitoring_action.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.risk_score < self._risk_threshold)
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["domain_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} certificate(s) below risk threshold ({self._risk_threshold})")
        if self._records and avg_risk_score < self._risk_threshold:
            recs.append(f"Avg risk score {avg_risk_score} below threshold ({self._risk_threshold})")
        if not recs:
            recs.append("Certificate transparency monitoring is healthy")
        return CertTransparencyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_risk_score=avg_risk_score,
            by_cert_type=by_cert_type,
            by_cert_status=by_cert_status,
            by_monitoring_action=by_monitoring_action,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("certificate_transparency_monitor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.cert_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "risk_threshold": self._risk_threshold,
            "cert_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
