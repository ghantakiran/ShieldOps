"""Runbook Compliance Checker — check compliance, standards, and trends."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ComplianceArea(StrEnum):
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    APPROVAL = "approval"
    VERSIONING = "versioning"
    REVIEW = "review"


class ComplianceGrade(StrEnum):
    A = "a"
    B = "b"
    C = "c"
    D = "d"
    F = "f"


class CheckStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"
    WAIVED = "waived"


# --- Models ---


class ComplianceCheckRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    compliance_area: ComplianceArea = ComplianceArea.DOCUMENTATION
    compliance_grade: ComplianceGrade = ComplianceGrade.F
    check_status: CheckStatus = CheckStatus.PENDING
    score: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceStandard(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    standard_name: str = ""
    compliance_area: ComplianceArea = ComplianceArea.DOCUMENTATION
    required_score: float = 0.0
    mandatory: bool = True
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RunbookComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_standards: int = 0
    passing_count: int = 0
    avg_score: float = 0.0
    by_area: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    failing_runbooks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RunbookComplianceChecker:
    """Check runbook compliance, identify failing runbooks, and detect trends."""

    def __init__(
        self,
        max_records: int = 200000,
        min_compliance_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._min_compliance_pct = min_compliance_pct
        self._records: list[ComplianceCheckRecord] = []
        self._standards: list[ComplianceStandard] = []
        logger.info(
            "runbook_compliance.initialized",
            max_records=max_records,
            min_compliance_pct=min_compliance_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_check(
        self,
        runbook_id: str,
        compliance_area: ComplianceArea = ComplianceArea.DOCUMENTATION,
        compliance_grade: ComplianceGrade = ComplianceGrade.F,
        check_status: CheckStatus = CheckStatus.PENDING,
        score: float = 0.0,
        team: str = "",
    ) -> ComplianceCheckRecord:
        record = ComplianceCheckRecord(
            runbook_id=runbook_id,
            compliance_area=compliance_area,
            compliance_grade=compliance_grade,
            check_status=check_status,
            score=score,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "runbook_compliance.check_recorded",
            record_id=record.id,
            runbook_id=runbook_id,
            compliance_area=compliance_area.value,
            compliance_grade=compliance_grade.value,
        )
        return record

    def get_check(self, record_id: str) -> ComplianceCheckRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_checks(
        self,
        area: ComplianceArea | None = None,
        grade: ComplianceGrade | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ComplianceCheckRecord]:
        results = list(self._records)
        if area is not None:
            results = [r for r in results if r.compliance_area == area]
        if grade is not None:
            results = [r for r in results if r.compliance_grade == grade]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_standard(
        self,
        standard_name: str,
        compliance_area: ComplianceArea = ComplianceArea.DOCUMENTATION,
        required_score: float = 0.0,
        mandatory: bool = True,
        description: str = "",
    ) -> ComplianceStandard:
        standard = ComplianceStandard(
            standard_name=standard_name,
            compliance_area=compliance_area,
            required_score=required_score,
            mandatory=mandatory,
            description=description,
        )
        self._standards.append(standard)
        if len(self._standards) > self._max_records:
            self._standards = self._standards[-self._max_records :]
        logger.info(
            "runbook_compliance.standard_added",
            standard_name=standard_name,
            compliance_area=compliance_area.value,
            required_score=required_score,
        )
        return standard

    # -- domain operations --------------------------------------------------

    def analyze_compliance_distribution(self) -> dict[str, Any]:
        """Group by area; return count and avg score per area."""
        area_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.compliance_area.value
            area_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for area, scores in area_data.items():
            result[area] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_failing_runbooks(self) -> list[dict[str, Any]]:
        """Return records where check_status == FAILED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.check_status == CheckStatus.FAILED:
                results.append(
                    {
                        "record_id": r.id,
                        "runbook_id": r.runbook_id,
                        "compliance_area": r.compliance_area.value,
                        "compliance_grade": r.compliance_grade.value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by team, avg score, sort ascending (worst first)."""
        team_data: dict[str, list[float]] = {}
        for r in self._records:
            team_data.setdefault(r.team, []).append(r.score)
        results: list[dict[str, Any]] = []
        for team, scores in team_data.items():
            results.append(
                {
                    "team": team,
                    "check_count": len(scores),
                    "avg_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    def detect_compliance_trends(self) -> dict[str, Any]:
        """Split-half on required_score; delta threshold 5.0."""
        if len(self._standards) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [s.required_score for s in self._standards]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> RunbookComplianceReport:
        by_area: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_area[r.compliance_area.value] = by_area.get(r.compliance_area.value, 0) + 1
            by_grade[r.compliance_grade.value] = by_grade.get(r.compliance_grade.value, 0) + 1
            by_status[r.check_status.value] = by_status.get(r.check_status.value, 0) + 1
        passing_count = sum(1 for r in self._records if r.check_status == CheckStatus.PASSED)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        failing = self.identify_failing_runbooks()
        failing_ids = [f["runbook_id"] for f in failing[:5]]
        compliance_pct = (
            round(passing_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        recs: list[str] = []
        if compliance_pct < self._min_compliance_pct and self._records:
            recs.append(
                f"Compliance rate {compliance_pct}% is below "
                f"threshold ({self._min_compliance_pct}%)"
            )
        if failing:
            recs.append(f"{len(failing)} failing runbook(s) detected — review compliance standards")
        if not recs:
            recs.append("Runbook compliance levels are acceptable")
        return RunbookComplianceReport(
            total_records=len(self._records),
            total_standards=len(self._standards),
            passing_count=passing_count,
            avg_score=avg_score,
            by_area=by_area,
            by_grade=by_grade,
            by_status=by_status,
            failing_runbooks=failing_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._standards.clear()
        logger.info("runbook_compliance.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        area_dist: dict[str, int] = {}
        for r in self._records:
            key = r.compliance_area.value
            area_dist[key] = area_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_standards": len(self._standards),
            "min_compliance_pct": self._min_compliance_pct,
            "area_distribution": area_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_runbooks": len({r.runbook_id for r in self._records}),
        }
