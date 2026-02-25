"""Developer Environment Health Monitor — track dev env issues, version drift, baselines."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EnvironmentType(StrEnum):
    LOCAL = "local"
    CODESPACE = "codespace"
    CONTAINER = "container"
    VM = "vm"
    REMOTE = "remote"


class HealthIssueType(StrEnum):
    DEPENDENCY_CONFLICT = "dependency_conflict"
    TOOL_VERSION_DRIFT = "tool_version_drift"
    BUILD_FAILURE = "build_failure"
    CONFIG_MISMATCH = "config_mismatch"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


class IssueImpact(StrEnum):
    BLOCKING = "blocking"
    DEGRADED = "degraded"
    MINOR = "minor"
    COSMETIC = "cosmetic"
    NONE = "none"


# --- Models ---


class EnvironmentIssueRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    developer: str = ""
    env_type: EnvironmentType = EnvironmentType.LOCAL
    issue_type: HealthIssueType = HealthIssueType.DEPENDENCY_CONFLICT
    impact: IssueImpact = IssueImpact.MINOR
    tool_name: str = ""
    expected_version: str = ""
    actual_version: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class EnvironmentBaseline(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    env_type: EnvironmentType = EnvironmentType.LOCAL
    tool_name: str = ""
    required_version: str = ""
    max_drift_days: int = 14
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class DevEnvironmentReport(BaseModel):
    total_issues: int = 0
    total_baselines: int = 0
    by_issue_type: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    blocking_count: int = 0
    drift_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DevEnvironmentHealthMonitor:
    """Track developer environment issues, version drift, and baselines."""

    def __init__(
        self,
        max_records: int = 200000,
        max_drift_days: int = 14,
    ) -> None:
        self._max_records = max_records
        self._max_drift_days = max_drift_days
        self._records: list[EnvironmentIssueRecord] = []
        self._baselines: list[EnvironmentBaseline] = []
        logger.info(
            "dev_environment.initialized",
            max_records=max_records,
            max_drift_days=max_drift_days,
        )

    # -- record / get / list -------------------------------------------------

    def record_issue(
        self,
        developer: str,
        env_type: EnvironmentType = EnvironmentType.LOCAL,
        issue_type: HealthIssueType = HealthIssueType.DEPENDENCY_CONFLICT,
        impact: IssueImpact = IssueImpact.MINOR,
        tool_name: str = "",
        expected_version: str = "",
        actual_version: str = "",
        details: str = "",
    ) -> EnvironmentIssueRecord:
        record = EnvironmentIssueRecord(
            developer=developer,
            env_type=env_type,
            issue_type=issue_type,
            impact=impact,
            tool_name=tool_name,
            expected_version=expected_version,
            actual_version=actual_version,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dev_environment.issue_recorded",
            record_id=record.id,
            developer=developer,
            issue_type=issue_type.value,
        )
        return record

    def get_issue(self, record_id: str) -> EnvironmentIssueRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_issues(
        self,
        developer: str | None = None,
        issue_type: HealthIssueType | None = None,
        limit: int = 50,
    ) -> list[EnvironmentIssueRecord]:
        results = list(self._records)
        if developer is not None:
            results = [r for r in results if r.developer == developer]
        if issue_type is not None:
            results = [r for r in results if r.issue_type == issue_type]
        return results[-limit:]

    def set_baseline(
        self,
        env_type: EnvironmentType = EnvironmentType.LOCAL,
        tool_name: str = "",
        required_version: str = "",
        max_drift_days: int = 14,
        details: str = "",
    ) -> EnvironmentBaseline:
        baseline = EnvironmentBaseline(
            env_type=env_type,
            tool_name=tool_name,
            required_version=required_version,
            max_drift_days=max_drift_days,
            details=details,
        )
        self._baselines.append(baseline)
        if len(self._baselines) > self._max_records:
            self._baselines = self._baselines[-self._max_records :]
        logger.info(
            "dev_environment.baseline_set",
            tool_name=tool_name,
            required_version=required_version,
        )
        return baseline

    # -- domain operations ---------------------------------------------------

    def detect_version_drift(self) -> list[dict[str, Any]]:
        """Detect issues where actual version differs from expected."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if (
                r.issue_type == HealthIssueType.TOOL_VERSION_DRIFT
                and r.expected_version
                and r.actual_version
                and r.expected_version != r.actual_version
            ):
                results.append(
                    {
                        "developer": r.developer,
                        "tool_name": r.tool_name,
                        "expected_version": r.expected_version,
                        "actual_version": r.actual_version,
                        "env_type": r.env_type.value,
                        "impact": r.impact.value,
                    }
                )
        results.sort(key=lambda x: x["impact"])
        return results

    def identify_blocking_issues(self) -> list[dict[str, Any]]:
        """Find all blocking issues across developers."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.impact == IssueImpact.BLOCKING:
                results.append(
                    {
                        "developer": r.developer,
                        "issue_type": r.issue_type.value,
                        "tool_name": r.tool_name,
                        "env_type": r.env_type.value,
                        "details": r.details,
                    }
                )
        return results

    def rank_most_affected_developers(self) -> list[dict[str, Any]]:
        """Rank developers by number of issues."""
        counts: dict[str, int] = {}
        for r in self._records:
            counts[r.developer] = counts.get(r.developer, 0) + 1
        results: list[dict[str, Any]] = []
        for dev, count in counts.items():
            results.append({"developer": dev, "issue_count": count})
        results.sort(key=lambda x: x["issue_count"], reverse=True)
        return results

    def compare_to_baseline(self) -> list[dict[str, Any]]:
        """Compare recorded issues against baselines."""
        baseline_map: dict[str, EnvironmentBaseline] = {}
        for b in self._baselines:
            key = f"{b.env_type.value}:{b.tool_name}"
            baseline_map[key] = b
        results: list[dict[str, Any]] = []
        for r in self._records:
            key = f"{r.env_type.value}:{r.tool_name}"
            baseline = baseline_map.get(key)
            if baseline and r.actual_version and r.actual_version != baseline.required_version:
                results.append(
                    {
                        "developer": r.developer,
                        "tool_name": r.tool_name,
                        "required_version": baseline.required_version,
                        "actual_version": r.actual_version,
                        "env_type": r.env_type.value,
                        "max_drift_days": baseline.max_drift_days,
                    }
                )
        return results

    # -- report / stats ------------------------------------------------------

    def generate_report(self) -> DevEnvironmentReport:
        by_issue_type: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        for r in self._records:
            by_issue_type[r.issue_type.value] = by_issue_type.get(r.issue_type.value, 0) + 1
            by_impact[r.impact.value] = by_impact.get(r.impact.value, 0) + 1
        blocking_count = sum(1 for r in self._records if r.impact == IssueImpact.BLOCKING)
        drift_count = sum(
            1 for r in self._records if r.issue_type == HealthIssueType.TOOL_VERSION_DRIFT
        )
        recs: list[str] = []
        if blocking_count > 0:
            recs.append(f"{blocking_count} blocking issue(s) require immediate attention")
        if drift_count > 0:
            recs.append(f"{drift_count} version drift issue(s) detected")
        if not recs:
            recs.append("Developer environment health meets targets")
        return DevEnvironmentReport(
            total_issues=len(self._records),
            total_baselines=len(self._baselines),
            by_issue_type=by_issue_type,
            by_impact=by_impact,
            blocking_count=blocking_count,
            drift_count=drift_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._baselines.clear()
        logger.info("dev_environment.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        issue_dist: dict[str, int] = {}
        for r in self._records:
            key = r.issue_type.value
            issue_dist[key] = issue_dist.get(key, 0) + 1
        return {
            "total_issues": len(self._records),
            "total_baselines": len(self._baselines),
            "max_drift_days": self._max_drift_days,
            "issue_distribution": issue_dist,
            "unique_developers": len({r.developer for r in self._records}),
        }
