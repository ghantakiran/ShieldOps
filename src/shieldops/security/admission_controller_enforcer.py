"""Admission Controller Enforcer — enforce admission control policies in Kubernetes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ControllerType(StrEnum):
    VALIDATING = "validating"
    MUTATING = "mutating"
    OPA_GATEKEEPER = "opa_gatekeeper"
    KYVERNO = "kyverno"
    CUSTOM = "custom"


class EnforcementMode(StrEnum):
    ENFORCE = "enforce"
    AUDIT = "audit"
    WARN = "warn"
    DRY_RUN = "dry_run"
    DISABLED = "disabled"


class PolicyCategory(StrEnum):
    SECURITY = "security"
    COMPLIANCE = "compliance"
    RESOURCE = "resource"
    NAMING = "naming"
    CUSTOM = "custom"


# --- Models ---


class AdmissionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    admission_id: str = ""
    controller_type: ControllerType = ControllerType.VALIDATING
    enforcement_mode: EnforcementMode = EnforcementMode.ENFORCE
    policy_category: PolicyCategory = PolicyCategory.SECURITY
    enforcement_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AdmissionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    admission_id: str = ""
    controller_type: ControllerType = ControllerType.VALIDATING
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AdmissionControllerReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_enforcement_score: float = 0.0
    by_controller: dict[str, int] = Field(default_factory=dict)
    by_mode: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AdmissionControllerEnforcer:
    """Enforce admission control policies, track violations, and audit compliance."""

    def __init__(
        self,
        max_records: int = 200000,
        enforcement_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._enforcement_gap_threshold = enforcement_gap_threshold
        self._records: list[AdmissionRecord] = []
        self._analyses: list[AdmissionAnalysis] = []
        logger.info(
            "admission_controller_enforcer.initialized",
            max_records=max_records,
            enforcement_gap_threshold=enforcement_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_admission(
        self,
        admission_id: str,
        controller_type: ControllerType = ControllerType.VALIDATING,
        enforcement_mode: EnforcementMode = EnforcementMode.ENFORCE,
        policy_category: PolicyCategory = PolicyCategory.SECURITY,
        enforcement_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AdmissionRecord:
        record = AdmissionRecord(
            admission_id=admission_id,
            controller_type=controller_type,
            enforcement_mode=enforcement_mode,
            policy_category=policy_category,
            enforcement_score=enforcement_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "admission_controller_enforcer.admission_recorded",
            record_id=record.id,
            admission_id=admission_id,
            controller_type=controller_type.value,
            enforcement_mode=enforcement_mode.value,
        )
        return record

    def get_admission(self, record_id: str) -> AdmissionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_admissions(
        self,
        controller_type: ControllerType | None = None,
        enforcement_mode: EnforcementMode | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AdmissionRecord]:
        results = list(self._records)
        if controller_type is not None:
            results = [r for r in results if r.controller_type == controller_type]
        if enforcement_mode is not None:
            results = [r for r in results if r.enforcement_mode == enforcement_mode]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        admission_id: str,
        controller_type: ControllerType = ControllerType.VALIDATING,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AdmissionAnalysis:
        analysis = AdmissionAnalysis(
            admission_id=admission_id,
            controller_type=controller_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "admission_controller_enforcer.analysis_added",
            admission_id=admission_id,
            controller_type=controller_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_controller_distribution(self) -> dict[str, Any]:
        """Group by controller_type; return count and avg enforcement_score."""
        controller_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.controller_type.value
            controller_data.setdefault(key, []).append(r.enforcement_score)
        result: dict[str, Any] = {}
        for controller, scores in controller_data.items():
            result[controller] = {
                "count": len(scores),
                "avg_enforcement_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_enforcement_gaps(self) -> list[dict[str, Any]]:
        """Return records where enforcement_score < enforcement_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.enforcement_score < self._enforcement_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "admission_id": r.admission_id,
                        "controller_type": r.controller_type.value,
                        "enforcement_score": r.enforcement_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["enforcement_score"])

    def rank_by_enforcement(self) -> list[dict[str, Any]]:
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

    def detect_enforcement_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> AdmissionControllerReport:
        by_controller: dict[str, int] = {}
        by_mode: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_controller[r.controller_type.value] = (
                by_controller.get(r.controller_type.value, 0) + 1
            )
            by_mode[r.enforcement_mode.value] = by_mode.get(r.enforcement_mode.value, 0) + 1
            by_category[r.policy_category.value] = by_category.get(r.policy_category.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.enforcement_score < self._enforcement_gap_threshold
        )
        scores = [r.enforcement_score for r in self._records]
        avg_enforcement_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_enforcement_gaps()
        top_gaps = [o["admission_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} admission(s) below enforcement threshold "
                f"({self._enforcement_gap_threshold})"
            )
        if self._records and avg_enforcement_score < self._enforcement_gap_threshold:
            recs.append(
                f"Avg enforcement score {avg_enforcement_score} below threshold "
                f"({self._enforcement_gap_threshold})"
            )
        if not recs:
            recs.append("Admission controller enforcement is healthy")
        return AdmissionControllerReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_enforcement_score=avg_enforcement_score,
            by_controller=by_controller,
            by_mode=by_mode,
            by_category=by_category,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("admission_controller_enforcer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        controller_dist: dict[str, int] = {}
        for r in self._records:
            key = r.controller_type.value
            controller_dist[key] = controller_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "enforcement_gap_threshold": self._enforcement_gap_threshold,
            "controller_distribution": controller_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
