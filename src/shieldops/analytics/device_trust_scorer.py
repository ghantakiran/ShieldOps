"""Device Trust Scorer — score device trust based on compliance and security posture."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DeviceType(StrEnum):
    MANAGED = "managed"
    UNMANAGED = "unmanaged"
    BYOD = "byod"
    IOT = "iot"
    VIRTUAL = "virtual"


class ComplianceStatus(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    EXEMPT = "exempt"


class TrustLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNTRUSTED = "untrusted"
    BLOCKED = "blocked"


# --- Models ---


class DeviceTrustRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    device_name: str = ""
    device_type: DeviceType = DeviceType.MANAGED
    compliance_status: ComplianceStatus = ComplianceStatus.COMPLIANT
    trust_level: TrustLevel = TrustLevel.HIGH
    trust_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DeviceTrustAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    device_name: str = ""
    device_type: DeviceType = DeviceType.MANAGED
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DeviceTrustReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_trust_score: float = 0.0
    by_device_type: dict[str, int] = Field(default_factory=dict)
    by_compliance_status: dict[str, int] = Field(default_factory=dict)
    by_trust_level: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeviceTrustScorer:
    """Score device trust based on compliance status, security posture, and device type."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[DeviceTrustRecord] = []
        self._analyses: list[DeviceTrustAnalysis] = []
        logger.info(
            "device_trust_scorer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_trust(
        self,
        device_name: str,
        device_type: DeviceType = DeviceType.MANAGED,
        compliance_status: ComplianceStatus = ComplianceStatus.COMPLIANT,
        trust_level: TrustLevel = TrustLevel.HIGH,
        trust_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DeviceTrustRecord:
        record = DeviceTrustRecord(
            device_name=device_name,
            device_type=device_type,
            compliance_status=compliance_status,
            trust_level=trust_level,
            trust_score=trust_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "device_trust_scorer.trust_recorded",
            record_id=record.id,
            device_name=device_name,
            device_type=device_type.value,
            compliance_status=compliance_status.value,
        )
        return record

    def get_record(self, record_id: str) -> DeviceTrustRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        device_type: DeviceType | None = None,
        compliance_status: ComplianceStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DeviceTrustRecord]:
        results = list(self._records)
        if device_type is not None:
            results = [r for r in results if r.device_type == device_type]
        if compliance_status is not None:
            results = [r for r in results if r.compliance_status == compliance_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        device_name: str,
        device_type: DeviceType = DeviceType.MANAGED,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DeviceTrustAnalysis:
        analysis = DeviceTrustAnalysis(
            device_name=device_name,
            device_type=device_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "device_trust_scorer.analysis_added",
            device_name=device_name,
            device_type=device_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by device_type; return count and avg trust_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.device_type.value
            type_data.setdefault(key, []).append(r.trust_score)
        result: dict[str, Any] = {}
        for dtype, scores in type_data.items():
            result[dtype] = {
                "count": len(scores),
                "avg_trust_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where trust_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.trust_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "device_name": r.device_name,
                        "device_type": r.device_type.value,
                        "trust_score": r.trust_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["trust_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg trust_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.trust_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_trust_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_trust_score"])
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

    def generate_report(self) -> DeviceTrustReport:
        by_device_type: dict[str, int] = {}
        by_compliance_status: dict[str, int] = {}
        by_trust_level: dict[str, int] = {}
        for r in self._records:
            by_device_type[r.device_type.value] = by_device_type.get(r.device_type.value, 0) + 1
            by_compliance_status[r.compliance_status.value] = (
                by_compliance_status.get(r.compliance_status.value, 0) + 1
            )
            by_trust_level[r.trust_level.value] = by_trust_level.get(r.trust_level.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.trust_score < self._threshold)
        scores = [r.trust_score for r in self._records]
        avg_trust_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["device_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} device(s) below trust threshold ({self._threshold})")
        if self._records and avg_trust_score < self._threshold:
            recs.append(f"Avg trust score {avg_trust_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Device trust scoring is healthy")
        return DeviceTrustReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_trust_score=avg_trust_score,
            by_device_type=by_device_type,
            by_compliance_status=by_compliance_status,
            by_trust_level=by_trust_level,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("device_trust_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        device_type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.device_type.value
            device_type_dist[key] = device_type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "device_type_distribution": device_type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
