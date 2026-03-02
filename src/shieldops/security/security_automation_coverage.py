"""Security Automation Coverage — SOC automation coverage scoring."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AutomationType(StrEnum):
    PLAYBOOK = "playbook"
    RULE_BASED = "rule_based"
    ML_DRIVEN = "ml_driven"
    ORCHESTRATION = "orchestration"
    CUSTOM_SCRIPT = "custom_script"


class CoverageArea(StrEnum):
    DETECTION = "detection"
    RESPONSE = "response"
    INVESTIGATION = "investigation"
    REPORTING = "reporting"
    REMEDIATION = "remediation"


class MaturityLevel(StrEnum):
    OPTIMIZED = "optimized"
    MANAGED = "managed"
    DEFINED = "defined"
    DEVELOPING = "developing"
    INITIAL = "initial"


# --- Models ---


class AutomationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    automation_name: str = ""
    automation_type: AutomationType = AutomationType.PLAYBOOK
    coverage_area: CoverageArea = CoverageArea.DETECTION
    maturity_level: MaturityLevel = MaturityLevel.OPTIMIZED
    coverage_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AutomationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    automation_name: str = ""
    automation_type: AutomationType = AutomationType.PLAYBOOK
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AutomationCoverageReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_coverage_count: int = 0
    avg_coverage_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_area: dict[str, int] = Field(default_factory=dict)
    by_maturity: dict[str, int] = Field(default_factory=dict)
    top_low_coverage: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityAutomationCoverage:
    """SOC automation coverage scoring and gap identification."""

    def __init__(
        self,
        max_records: int = 200000,
        automation_coverage_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._automation_coverage_threshold = automation_coverage_threshold
        self._records: list[AutomationRecord] = []
        self._analyses: list[AutomationAnalysis] = []
        logger.info(
            "security_automation_coverage.initialized",
            max_records=max_records,
            automation_coverage_threshold=automation_coverage_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_automation(
        self,
        automation_name: str,
        automation_type: AutomationType = AutomationType.PLAYBOOK,
        coverage_area: CoverageArea = CoverageArea.DETECTION,
        maturity_level: MaturityLevel = MaturityLevel.OPTIMIZED,
        coverage_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AutomationRecord:
        record = AutomationRecord(
            automation_name=automation_name,
            automation_type=automation_type,
            coverage_area=coverage_area,
            maturity_level=maturity_level,
            coverage_score=coverage_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_automation_coverage.automation_recorded",
            record_id=record.id,
            automation_name=automation_name,
            automation_type=automation_type.value,
            coverage_area=coverage_area.value,
        )
        return record

    def get_automation(self, record_id: str) -> AutomationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_automations(
        self,
        automation_type: AutomationType | None = None,
        coverage_area: CoverageArea | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AutomationRecord]:
        results = list(self._records)
        if automation_type is not None:
            results = [r for r in results if r.automation_type == automation_type]
        if coverage_area is not None:
            results = [r for r in results if r.coverage_area == coverage_area]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        automation_name: str,
        automation_type: AutomationType = AutomationType.PLAYBOOK,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AutomationAnalysis:
        analysis = AutomationAnalysis(
            automation_name=automation_name,
            automation_type=automation_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "security_automation_coverage.analysis_added",
            automation_name=automation_name,
            automation_type=automation_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_type_distribution(self) -> dict[str, Any]:
        """Group by automation_type; return count and avg coverage_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.automation_type.value
            type_data.setdefault(key, []).append(r.coverage_score)
        result: dict[str, Any] = {}
        for atype, scores in type_data.items():
            result[atype] = {
                "count": len(scores),
                "avg_coverage_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_coverage_automations(self) -> list[dict[str, Any]]:
        """Return records where coverage_score < automation_coverage_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.coverage_score < self._automation_coverage_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "automation_name": r.automation_name,
                        "automation_type": r.automation_type.value,
                        "coverage_score": r.coverage_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["coverage_score"])

    def rank_by_coverage_score(self) -> list[dict[str, Any]]:
        """Group by service, avg coverage_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.coverage_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_coverage_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_coverage_score"])
        return results

    def detect_coverage_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> AutomationCoverageReport:
        by_type: dict[str, int] = {}
        by_area: dict[str, int] = {}
        by_maturity: dict[str, int] = {}
        for r in self._records:
            by_type[r.automation_type.value] = by_type.get(r.automation_type.value, 0) + 1
            by_area[r.coverage_area.value] = by_area.get(r.coverage_area.value, 0) + 1
            by_maturity[r.maturity_level.value] = by_maturity.get(r.maturity_level.value, 0) + 1
        low_coverage_count = sum(
            1 for r in self._records if r.coverage_score < self._automation_coverage_threshold
        )
        scores = [r.coverage_score for r in self._records]
        avg_coverage_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_coverage_automations()
        top_low_coverage = [o["automation_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_coverage_count > 0:
            recs.append(
                f"{low_coverage_count} automation(s) below coverage threshold "
                f"({self._automation_coverage_threshold})"
            )
        if self._records and avg_coverage_score < self._automation_coverage_threshold:
            recs.append(
                f"Avg coverage score {avg_coverage_score} below threshold "
                f"({self._automation_coverage_threshold})"
            )
        if not recs:
            recs.append("Security automation coverage is healthy")
        return AutomationCoverageReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_coverage_count=low_coverage_count,
            avg_coverage_score=avg_coverage_score,
            by_type=by_type,
            by_area=by_area,
            by_maturity=by_maturity,
            top_low_coverage=top_low_coverage,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_automation_coverage.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.automation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "automation_coverage_threshold": self._automation_coverage_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
