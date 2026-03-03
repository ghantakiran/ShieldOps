"""Device Posture Validator — validate device posture compliance and security state."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PostureCheck(StrEnum):
    OS_VERSION = "os_version"
    ENCRYPTION = "encryption"
    ANTIVIRUS = "antivirus"
    FIREWALL = "firewall"
    PATCH_LEVEL = "patch_level"


class ComplianceState(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    EXEMPT = "exempt"


class DeviceType(StrEnum):
    MANAGED = "managed"
    BYOD = "byod"
    CONTRACTOR = "contractor"
    IOT = "iot"
    VIRTUAL = "virtual"


# --- Models ---


class PostureRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    posture_id: str = ""
    posture_check: PostureCheck = PostureCheck.OS_VERSION
    compliance_state: ComplianceState = ComplianceState.COMPLIANT
    device_type: DeviceType = DeviceType.MANAGED
    compliance_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PostureAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    posture_id: str = ""
    posture_check: PostureCheck = PostureCheck.OS_VERSION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DevicePostureReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_compliance_score: float = 0.0
    by_posture_check: dict[str, int] = Field(default_factory=dict)
    by_compliance_state: dict[str, int] = Field(default_factory=dict)
    by_device_type: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DevicePostureValidator:
    """Validate device posture compliance, track security state, and analyze device health."""

    def __init__(
        self,
        max_records: int = 200000,
        compliance_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._compliance_gap_threshold = compliance_gap_threshold
        self._records: list[PostureRecord] = []
        self._analyses: list[PostureAnalysis] = []
        logger.info(
            "device_posture_validator.initialized",
            max_records=max_records,
            compliance_gap_threshold=compliance_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_posture(
        self,
        posture_id: str,
        posture_check: PostureCheck = PostureCheck.OS_VERSION,
        compliance_state: ComplianceState = ComplianceState.COMPLIANT,
        device_type: DeviceType = DeviceType.MANAGED,
        compliance_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PostureRecord:
        record = PostureRecord(
            posture_id=posture_id,
            posture_check=posture_check,
            compliance_state=compliance_state,
            device_type=device_type,
            compliance_score=compliance_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "device_posture_validator.posture_recorded",
            record_id=record.id,
            posture_id=posture_id,
            posture_check=posture_check.value,
            compliance_state=compliance_state.value,
        )
        return record

    def get_posture(self, record_id: str) -> PostureRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_postures(
        self,
        posture_check: PostureCheck | None = None,
        compliance_state: ComplianceState | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PostureRecord]:
        results = list(self._records)
        if posture_check is not None:
            results = [r for r in results if r.posture_check == posture_check]
        if compliance_state is not None:
            results = [r for r in results if r.compliance_state == compliance_state]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        posture_id: str,
        posture_check: PostureCheck = PostureCheck.OS_VERSION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PostureAnalysis:
        analysis = PostureAnalysis(
            posture_id=posture_id,
            posture_check=posture_check,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "device_posture_validator.analysis_added",
            posture_id=posture_id,
            posture_check=posture_check.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_posture_distribution(self) -> dict[str, Any]:
        """Group by posture_check; return count and avg compliance_score."""
        check_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.posture_check.value
            check_data.setdefault(key, []).append(r.compliance_score)
        result: dict[str, Any] = {}
        for check, scores in check_data.items():
            result[check] = {
                "count": len(scores),
                "avg_compliance_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_posture_gaps(self) -> list[dict[str, Any]]:
        """Return records where compliance_score < compliance_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_score < self._compliance_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "posture_id": r.posture_id,
                        "posture_check": r.posture_check.value,
                        "compliance_score": r.compliance_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["compliance_score"])

    def rank_by_posture(self) -> list[dict[str, Any]]:
        """Group by service, avg compliance_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.compliance_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_compliance_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_compliance_score"])
        return results

    def detect_posture_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> DevicePostureReport:
        by_posture_check: dict[str, int] = {}
        by_compliance_state: dict[str, int] = {}
        by_device_type: dict[str, int] = {}
        for r in self._records:
            by_posture_check[r.posture_check.value] = (
                by_posture_check.get(r.posture_check.value, 0) + 1
            )
            by_compliance_state[r.compliance_state.value] = (
                by_compliance_state.get(r.compliance_state.value, 0) + 1
            )
            by_device_type[r.device_type.value] = by_device_type.get(r.device_type.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.compliance_score < self._compliance_gap_threshold
        )
        scores = [r.compliance_score for r in self._records]
        avg_compliance_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_posture_gaps()
        top_gaps = [o["posture_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} device(s) below compliance threshold "
                f"({self._compliance_gap_threshold})"
            )
        if self._records and avg_compliance_score < self._compliance_gap_threshold:
            recs.append(
                f"Avg compliance score {avg_compliance_score} below threshold "
                f"({self._compliance_gap_threshold})"
            )
        if not recs:
            recs.append("Device posture compliance is healthy")
        return DevicePostureReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_compliance_score=avg_compliance_score,
            by_posture_check=by_posture_check,
            by_compliance_state=by_compliance_state,
            by_device_type=by_device_type,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("device_posture_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        check_dist: dict[str, int] = {}
        for r in self._records:
            key = r.posture_check.value
            check_dist[key] = check_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "compliance_gap_threshold": self._compliance_gap_threshold,
            "posture_check_distribution": check_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
