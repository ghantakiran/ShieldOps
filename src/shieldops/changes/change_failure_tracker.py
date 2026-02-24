"""Change Failure Rate Tracker — deployment failure rates per service/team."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DeploymentResult(StrEnum):
    SUCCESS = "success"
    PARTIAL_FAILURE = "partial_failure"
    FULL_FAILURE = "full_failure"
    ROLLBACK = "rollback"
    HOTFIX_REQUIRED = "hotfix_required"


class FailureTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    CRITICAL_DEGRADATION = "critical_degradation"
    INSUFFICIENT_DATA = "insufficient_data"


class ChangeScope(StrEnum):
    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"
    INFRASTRUCTURE = "infrastructure"
    CONFIGURATION = "configuration"


# --- Models ---


class DeploymentRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    team: str = ""
    result: DeploymentResult = DeploymentResult.SUCCESS
    scope: ChangeScope = ChangeScope.PATCH
    description: str = ""
    deploy_time: float = Field(default_factory=time.time)
    recovery_time_minutes: float = 0.0
    created_at: float = Field(default_factory=time.time)


class FailureRateScore(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    total_deployments: int = 0
    failed_deployments: int = 0
    failure_rate_pct: float = 0.0
    trend: FailureTrend = FailureTrend.INSUFFICIENT_DATA
    window_days: int = 30
    calculated_at: float = Field(default_factory=time.time)


class ChangeFailureReport(BaseModel):
    total_deployments: int = 0
    total_failures: int = 0
    overall_failure_rate: float = 0.0
    by_result: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_service: dict[str, int] = Field(default_factory=dict)
    avg_recovery_minutes: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeFailureRateTracker:
    """Track deployment failure rates per service/team and detect quality regression."""

    def __init__(
        self,
        max_deployments: int = 200000,
        trend_window_days: int = 30,
    ) -> None:
        self._max_deployments = max_deployments
        self._trend_window_days = trend_window_days
        self._deployments: list[DeploymentRecord] = []
        logger.info(
            "change_failure_tracker.initialized",
            max_deployments=max_deployments,
            trend_window_days=trend_window_days,
        )

    def record_deployment(
        self,
        service_name: str = "",
        team: str = "",
        result: DeploymentResult = DeploymentResult.SUCCESS,
        scope: ChangeScope = ChangeScope.PATCH,
        description: str = "",
        recovery_time_minutes: float = 0.0,
    ) -> DeploymentRecord:
        record = DeploymentRecord(
            service_name=service_name,
            team=team,
            result=result,
            scope=scope,
            description=description,
            recovery_time_minutes=recovery_time_minutes,
        )
        self._deployments.append(record)
        if len(self._deployments) > self._max_deployments:
            self._deployments = self._deployments[-self._max_deployments :]
        logger.info(
            "change_failure_tracker.deployment_recorded",
            deployment_id=record.id,
            service_name=service_name,
            result=result,
        )
        return record

    def get_deployment(self, dep_id: str) -> DeploymentRecord | None:
        for d in self._deployments:
            if d.id == dep_id:
                return d
        return None

    def list_deployments(
        self,
        service_name: str | None = None,
        team: str | None = None,
        result: DeploymentResult | None = None,
        limit: int = 100,
    ) -> list[DeploymentRecord]:
        results = list(self._deployments)
        if service_name is not None:
            results = [d for d in results if d.service_name == service_name]
        if team is not None:
            results = [d for d in results if d.team == team]
        if result is not None:
            results = [d for d in results if d.result == result]
        return results[-limit:]

    def calculate_failure_rate(self, service_name: str) -> FailureRateScore:
        deps = [d for d in self._deployments if d.service_name == service_name]
        total = len(deps)
        if total < 3:
            return FailureRateScore(
                service_name=service_name,
                total_deployments=total,
                failed_deployments=sum(1 for d in deps if d.result != DeploymentResult.SUCCESS),
                failure_rate_pct=(
                    round(
                        sum(1 for d in deps if d.result != DeploymentResult.SUCCESS) / total * 100,
                        2,
                    )
                    if total > 0
                    else 0.0
                ),
                trend=FailureTrend.INSUFFICIENT_DATA,
                window_days=self._trend_window_days,
            )
        failed = sum(1 for d in deps if d.result != DeploymentResult.SUCCESS)
        failure_rate = round(failed / total * 100, 2)
        # Determine trend based on failure rate
        if failure_rate < 5.0:
            trend = FailureTrend.IMPROVING
        elif failure_rate < 15.0:
            trend = FailureTrend.STABLE
        elif failure_rate < 30.0:
            trend = FailureTrend.DEGRADING
        else:
            trend = FailureTrend.CRITICAL_DEGRADATION
        score = FailureRateScore(
            service_name=service_name,
            total_deployments=total,
            failed_deployments=failed,
            failure_rate_pct=failure_rate,
            trend=trend,
            window_days=self._trend_window_days,
        )
        logger.info(
            "change_failure_tracker.failure_rate_calculated",
            service_name=service_name,
            failure_rate_pct=failure_rate,
            trend=trend,
        )
        return score

    def detect_failure_trend(self, service_name: str) -> dict[str, Any]:
        score = self.calculate_failure_rate(service_name)
        deps = [d for d in self._deployments if d.service_name == service_name]
        recent_failures = sum(1 for d in deps if d.result != DeploymentResult.SUCCESS)
        return {
            "service_name": service_name,
            "trend": score.trend.value,
            "failure_rate_pct": score.failure_rate_pct,
            "total_deployments": score.total_deployments,
            "recent_failures": recent_failures,
        }

    def rank_services_by_reliability(self) -> list[FailureRateScore]:
        service_names: set[str] = {d.service_name for d in self._deployments}
        scores: list[FailureRateScore] = []
        for svc in service_names:
            score = self.calculate_failure_rate(svc)
            scores.append(score)
        scores.sort(key=lambda s: s.failure_rate_pct)
        return scores

    def identify_risky_change_types(self) -> list[dict[str, Any]]:
        scope_data: dict[str, dict[str, int]] = {}
        for d in self._deployments:
            key = d.scope.value
            if key not in scope_data:
                scope_data[key] = {"total": 0, "failures": 0}
            scope_data[key]["total"] += 1
            if d.result != DeploymentResult.SUCCESS:
                scope_data[key]["failures"] += 1
        result: list[dict[str, Any]] = []
        for scope, data in scope_data.items():
            rate = round(data["failures"] / data["total"] * 100, 2) if data["total"] > 0 else 0.0
            result.append(
                {
                    "scope": scope,
                    "total": data["total"],
                    "failures": data["failures"],
                    "failure_rate_pct": rate,
                }
            )
        result.sort(key=lambda x: x["failure_rate_pct"], reverse=True)
        return result

    def calculate_recovery_time(self, service_name: str | None = None) -> dict[str, Any]:
        failed = [d for d in self._deployments if d.result != DeploymentResult.SUCCESS]
        if service_name is not None:
            failed = [d for d in failed if d.service_name == service_name]
        if not failed:
            return {
                "service_name": service_name or "all",
                "avg_recovery_minutes": 0.0,
                "min_recovery_minutes": 0.0,
                "max_recovery_minutes": 0.0,
                "total_failures": 0,
            }
        recovery_times = [d.recovery_time_minutes for d in failed]
        return {
            "service_name": service_name or "all",
            "avg_recovery_minutes": round(sum(recovery_times) / len(recovery_times), 2),
            "min_recovery_minutes": round(min(recovery_times), 2),
            "max_recovery_minutes": round(max(recovery_times), 2),
            "total_failures": len(failed),
        }

    def generate_failure_report(self) -> ChangeFailureReport:
        total = len(self._deployments)
        failures = sum(1 for d in self._deployments if d.result != DeploymentResult.SUCCESS)
        overall_rate = round(failures / total * 100, 2) if total > 0 else 0.0

        # By result
        by_result: dict[str, int] = {}
        for d in self._deployments:
            key = d.result.value
            by_result[key] = by_result.get(key, 0) + 1

        # By scope
        by_scope: dict[str, int] = {}
        for d in self._deployments:
            key = d.scope.value
            by_scope[key] = by_scope.get(key, 0) + 1

        # By service
        by_service: dict[str, int] = {}
        for d in self._deployments:
            by_service[d.service_name] = by_service.get(d.service_name, 0) + 1

        # Avg recovery for failed deployments
        failed_deps = [d for d in self._deployments if d.result != DeploymentResult.SUCCESS]
        avg_recovery = (
            round(sum(d.recovery_time_minutes for d in failed_deps) / len(failed_deps), 2)
            if failed_deps
            else 0.0
        )

        # Recommendations
        recommendations: list[str] = []
        if overall_rate > 30.0:
            recommendations.append(
                "Critical: Overall failure rate exceeds 30% — immediate review required"
            )
        elif overall_rate > 15.0:
            recommendations.append(
                "Warning: Failure rate above 15% — investigate top failing services"
            )
        risky_types = self.identify_risky_change_types()
        if risky_types and risky_types[0]["failure_rate_pct"] > 50.0:
            recommendations.append(
                f"Scope '{risky_types[0]['scope']}' has a {risky_types[0]['failure_rate_pct']}% "
                f"failure rate — add extra review gates"
            )
        if avg_recovery > 60.0:
            recommendations.append(
                f"Average recovery time is {avg_recovery} minutes — "
                f"invest in faster rollback mechanisms"
            )

        report = ChangeFailureReport(
            total_deployments=total,
            total_failures=failures,
            overall_failure_rate=overall_rate,
            by_result=by_result,
            by_scope=by_scope,
            by_service=by_service,
            avg_recovery_minutes=avg_recovery,
            recommendations=recommendations,
        )
        logger.info(
            "change_failure_tracker.report_generated",
            total_deployments=total,
            total_failures=failures,
            overall_failure_rate=overall_rate,
        )
        return report

    def clear_data(self) -> None:
        self._deployments.clear()
        logger.info("change_failure_tracker.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        services: set[str] = set()
        teams: set[str] = set()
        success_count = 0
        failure_count = 0
        for d in self._deployments:
            services.add(d.service_name)
            teams.add(d.team)
            if d.result == DeploymentResult.SUCCESS:
                success_count += 1
            else:
                failure_count += 1
        return {
            "total_deployments": len(self._deployments),
            "unique_services": len(services),
            "unique_teams": len(teams),
            "success_count": success_count,
            "failure_count": failure_count,
        }
