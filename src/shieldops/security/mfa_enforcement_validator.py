"""MFA Enforcement Validator — validate and track multi-factor authentication enforcement."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MFAMethod(StrEnum):
    TOTP = "totp"
    FIDO2 = "fido2"
    SMS = "sms"
    PUSH = "push"
    BIOMETRIC = "biometric"


class EnforcementScope(StrEnum):
    ALL_USERS = "all_users"
    PRIVILEGED = "privileged"
    EXTERNAL = "external"
    SENSITIVE = "sensitive"
    CONDITIONAL = "conditional"


class ComplianceStatus(StrEnum):
    ENFORCED = "enforced"
    PARTIAL = "partial"
    EXEMPT = "exempt"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


# --- Models ---


class MFARecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mfa_id: str = ""
    mfa_method: MFAMethod = MFAMethod.TOTP
    enforcement_scope: EnforcementScope = EnforcementScope.ALL_USERS
    compliance_status: ComplianceStatus = ComplianceStatus.ENFORCED
    enforcement_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MFAAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mfa_id: str = ""
    mfa_method: MFAMethod = MFAMethod.TOTP
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MFAEnforcementReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_enforcement_score: float = 0.0
    by_mfa_method: dict[str, int] = Field(default_factory=dict)
    by_enforcement_scope: dict[str, int] = Field(default_factory=dict)
    by_compliance_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class MFAEnforcementValidator:
    """Validate MFA enforcement policies, track compliance, and analyze enforcement gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        enforcement_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._enforcement_gap_threshold = enforcement_gap_threshold
        self._records: list[MFARecord] = []
        self._analyses: list[MFAAnalysis] = []
        logger.info(
            "mfa_enforcement_validator.initialized",
            max_records=max_records,
            enforcement_gap_threshold=enforcement_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_mfa(
        self,
        mfa_id: str,
        mfa_method: MFAMethod = MFAMethod.TOTP,
        enforcement_scope: EnforcementScope = EnforcementScope.ALL_USERS,
        compliance_status: ComplianceStatus = ComplianceStatus.ENFORCED,
        enforcement_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> MFARecord:
        record = MFARecord(
            mfa_id=mfa_id,
            mfa_method=mfa_method,
            enforcement_scope=enforcement_scope,
            compliance_status=compliance_status,
            enforcement_score=enforcement_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "mfa_enforcement_validator.mfa_recorded",
            record_id=record.id,
            mfa_id=mfa_id,
            mfa_method=mfa_method.value,
            enforcement_scope=enforcement_scope.value,
        )
        return record

    def get_mfa(self, record_id: str) -> MFARecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_mfas(
        self,
        mfa_method: MFAMethod | None = None,
        enforcement_scope: EnforcementScope | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MFARecord]:
        results = list(self._records)
        if mfa_method is not None:
            results = [r for r in results if r.mfa_method == mfa_method]
        if enforcement_scope is not None:
            results = [r for r in results if r.enforcement_scope == enforcement_scope]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        mfa_id: str,
        mfa_method: MFAMethod = MFAMethod.TOTP,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> MFAAnalysis:
        analysis = MFAAnalysis(
            mfa_id=mfa_id,
            mfa_method=mfa_method,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "mfa_enforcement_validator.analysis_added",
            mfa_id=mfa_id,
            mfa_method=mfa_method.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_mfa_distribution(self) -> dict[str, Any]:
        """Group by mfa_method; return count and avg enforcement_score."""
        method_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.mfa_method.value
            method_data.setdefault(key, []).append(r.enforcement_score)
        result: dict[str, Any] = {}
        for method, scores in method_data.items():
            result[method] = {
                "count": len(scores),
                "avg_enforcement_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_mfa_gaps(self) -> list[dict[str, Any]]:
        """Return records where enforcement_score < enforcement_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.enforcement_score < self._enforcement_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "mfa_id": r.mfa_id,
                        "mfa_method": r.mfa_method.value,
                        "enforcement_score": r.enforcement_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["enforcement_score"])

    def rank_by_mfa(self) -> list[dict[str, Any]]:
        """Group by service, avg enforcement_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.enforcement_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_enforcement_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_enforcement_score"])
        return results

    def detect_mfa_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> MFAEnforcementReport:
        by_mfa_method: dict[str, int] = {}
        by_enforcement_scope: dict[str, int] = {}
        by_compliance_status: dict[str, int] = {}
        for r in self._records:
            by_mfa_method[r.mfa_method.value] = by_mfa_method.get(r.mfa_method.value, 0) + 1
            by_enforcement_scope[r.enforcement_scope.value] = (
                by_enforcement_scope.get(r.enforcement_scope.value, 0) + 1
            )
            by_compliance_status[r.compliance_status.value] = (
                by_compliance_status.get(r.compliance_status.value, 0) + 1
            )
        gap_count = sum(
            1 for r in self._records if r.enforcement_score < self._enforcement_gap_threshold
        )
        scores = [r.enforcement_score for r in self._records]
        avg_enforcement_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_mfa_gaps()
        top_gaps = [o["mfa_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} MFA record(s) below enforcement threshold "
                f"({self._enforcement_gap_threshold})"
            )
        if self._records and avg_enforcement_score < self._enforcement_gap_threshold:
            recs.append(
                f"Avg enforcement score {avg_enforcement_score} below threshold "
                f"({self._enforcement_gap_threshold})"
            )
        if not recs:
            recs.append("MFA enforcement is healthy")
        return MFAEnforcementReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_enforcement_score=avg_enforcement_score,
            by_mfa_method=by_mfa_method,
            by_enforcement_scope=by_enforcement_scope,
            by_compliance_status=by_compliance_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("mfa_enforcement_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        method_dist: dict[str, int] = {}
        for r in self._records:
            key = r.mfa_method.value
            method_dist[key] = method_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "enforcement_gap_threshold": self._enforcement_gap_threshold,
            "mfa_method_distribution": method_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
