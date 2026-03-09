"""DeploymentIntelligenceEngine

Deployment pattern analysis, success prediction,
rollback probability scoring, optimization recommendations.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DeploymentOutcome(StrEnum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeploymentStrategy(StrEnum):
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    RECREATE = "recreate"
    A_B_TESTING = "a_b_testing"


class RollbackRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NEGLIGIBLE = "negligible"


# --- Models ---


class DeploymentIntelligenceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    outcome: DeploymentOutcome = DeploymentOutcome.SUCCESS
    strategy: DeploymentStrategy = DeploymentStrategy.ROLLING
    rollback_risk: RollbackRisk = RollbackRisk.LOW
    success_probability: float = 0.0
    rollback_probability: float = 0.0
    deploy_duration_seconds: float = 0.0
    change_size_lines: int = 0
    files_changed: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    environment: str = ""
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DeploymentIntelligenceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    strategy: DeploymentStrategy = DeploymentStrategy.ROLLING
    analysis_score: float = 0.0
    predicted_success_rate: float = 0.0
    risk_factors: list[str] = Field(default_factory=list)
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DeploymentIntelligenceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    success_rate: float = 0.0
    rollback_rate: float = 0.0
    avg_deploy_duration: float = 0.0
    avg_rollback_probability: float = 0.0
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_risky_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeploymentIntelligenceEngine:
    """Deployment pattern analysis with success prediction and rollback scoring."""

    def __init__(
        self,
        max_records: int = 200000,
        success_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._success_threshold = success_threshold
        self._records: list[DeploymentIntelligenceRecord] = []
        self._analyses: list[DeploymentIntelligenceAnalysis] = []
        logger.info(
            "deployment.intelligence.engine.initialized",
            max_records=max_records,
            success_threshold=success_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_item(
        self,
        name: str,
        outcome: DeploymentOutcome = DeploymentOutcome.SUCCESS,
        strategy: DeploymentStrategy = DeploymentStrategy.ROLLING,
        rollback_risk: RollbackRisk = RollbackRisk.LOW,
        success_probability: float = 0.0,
        rollback_probability: float = 0.0,
        deploy_duration_seconds: float = 0.0,
        change_size_lines: int = 0,
        files_changed: int = 0,
        tests_passed: int = 0,
        tests_failed: int = 0,
        environment: str = "",
        service: str = "",
        team: str = "",
    ) -> DeploymentIntelligenceRecord:
        record = DeploymentIntelligenceRecord(
            name=name,
            outcome=outcome,
            strategy=strategy,
            rollback_risk=rollback_risk,
            success_probability=success_probability,
            rollback_probability=rollback_probability,
            deploy_duration_seconds=deploy_duration_seconds,
            change_size_lines=change_size_lines,
            files_changed=files_changed,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            environment=environment,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "deployment.intelligence.engine.item_recorded",
            record_id=record.id,
            name=name,
            outcome=outcome.value,
            strategy=strategy.value,
        )
        return record

    def get_record(self, record_id: str) -> DeploymentIntelligenceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        outcome: DeploymentOutcome | None = None,
        strategy: DeploymentStrategy | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DeploymentIntelligenceRecord]:
        results = list(self._records)
        if outcome is not None:
            results = [r for r in results if r.outcome == outcome]
        if strategy is not None:
            results = [r for r in results if r.strategy == strategy]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        strategy: DeploymentStrategy = DeploymentStrategy.ROLLING,
        analysis_score: float = 0.0,
        predicted_success_rate: float = 0.0,
        risk_factors: list[str] | None = None,
        description: str = "",
    ) -> DeploymentIntelligenceAnalysis:
        analysis = DeploymentIntelligenceAnalysis(
            name=name,
            strategy=strategy,
            analysis_score=analysis_score,
            predicted_success_rate=predicted_success_rate,
            risk_factors=risk_factors or [],
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "deployment.intelligence.engine.analysis_added",
            name=name,
            strategy=strategy.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def predict_rollback_risk(self) -> list[dict[str, Any]]:
        """Score rollback probability based on deployment characteristics."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            risk_score = r.rollback_probability
            if r.tests_failed > 0:
                total_tests = r.tests_passed + r.tests_failed
                failure_ratio = r.tests_failed / total_tests if total_tests else 0
                risk_score = min(100.0, risk_score + failure_ratio * 40)
            if r.change_size_lines > 1000:
                risk_score = min(100.0, risk_score + 15.0)
            results.append(
                {
                    "record_id": r.id,
                    "name": r.name,
                    "service": r.service,
                    "rollback_risk_score": round(risk_score, 2),
                    "rollback_risk": r.rollback_risk.value,
                    "change_size": r.change_size_lines,
                    "test_failures": r.tests_failed,
                }
            )
        return sorted(results, key=lambda x: x["rollback_risk_score"], reverse=True)

    def analyze_success_patterns(self) -> dict[str, Any]:
        """Analyze patterns in successful vs failed deployments."""
        strategy_outcomes: dict[str, dict[str, int]] = {}
        for r in self._records:
            key = r.strategy.value
            strategy_outcomes.setdefault(key, {"success": 0, "failure": 0})
            if r.outcome == DeploymentOutcome.SUCCESS:
                strategy_outcomes[key]["success"] += 1
            elif r.outcome in (DeploymentOutcome.FAILED, DeploymentOutcome.ROLLED_BACK):
                strategy_outcomes[key]["failure"] += 1
        result: dict[str, Any] = {}
        for strategy, counts in strategy_outcomes.items():
            total = counts["success"] + counts["failure"]
            result[strategy] = {
                "total": total,
                "success_rate": round(counts["success"] / total * 100, 2) if total > 0 else 0.0,
            }
        return result

    def identify_risky_services(self) -> list[dict[str, Any]]:
        svc_data: dict[str, dict[str, int]] = {}
        for r in self._records:
            svc_data.setdefault(r.service, {"total": 0, "failures": 0, "rollbacks": 0})
            svc_data[r.service]["total"] += 1
            if r.outcome == DeploymentOutcome.FAILED:
                svc_data[r.service]["failures"] += 1
            if r.outcome == DeploymentOutcome.ROLLED_BACK:
                svc_data[r.service]["rollbacks"] += 1
        results: list[dict[str, Any]] = []
        for svc, data in svc_data.items():
            failure_rate = (data["failures"] + data["rollbacks"]) / data["total"] * 100
            results.append(
                {
                    "service": svc,
                    "total_deploys": data["total"],
                    "failure_rate": round(failure_rate, 2),
                    "rollback_count": data["rollbacks"],
                }
            )
        return sorted(results, key=lambda x: x["failure_rate"], reverse=True)

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        avg_first = sum(vals[:mid]) / len(vals[:mid])
        avg_second = sum(vals[mid:]) / len(vals[mid:])
        delta = round(avg_second - avg_first, 2)
        trend = "stable" if abs(delta) < 5.0 else ("improving" if delta > 0 else "degrading")
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> DeploymentIntelligenceReport:
        by_outcome: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_outcome[r.outcome.value] = by_outcome.get(r.outcome.value, 0) + 1
            by_strategy[r.strategy.value] = by_strategy.get(r.strategy.value, 0) + 1
            by_risk[r.rollback_risk.value] = by_risk.get(r.rollback_risk.value, 0) + 1
        total = len(self._records)
        successes = sum(1 for r in self._records if r.outcome == DeploymentOutcome.SUCCESS)
        rollbacks = sum(1 for r in self._records if r.outcome == DeploymentOutcome.ROLLED_BACK)
        success_rate = round(successes / total * 100, 2) if total else 0.0
        rollback_rate = round(rollbacks / total * 100, 2) if total else 0.0
        durations = [
            r.deploy_duration_seconds for r in self._records if r.deploy_duration_seconds > 0
        ]
        avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0
        rb_probs = [r.rollback_probability for r in self._records]
        avg_rb = round(sum(rb_probs) / len(rb_probs), 2) if rb_probs else 0.0
        risky = self.identify_risky_services()
        top_risky = [s["service"] for s in risky[:5]]
        recs: list[str] = []
        if rollback_rate > 10.0:
            recs.append(f"Rollback rate {rollback_rate}% exceeds 10% target")
        if success_rate < 95.0 and total > 0:
            recs.append(f"Success rate {success_rate}% below 95% target")
        if avg_duration > 600:
            recs.append(f"Avg deploy duration {avg_duration}s — consider parallelization")
        if not recs:
            recs.append("Deployment intelligence is healthy — success rate on target")
        return DeploymentIntelligenceReport(
            total_records=total,
            total_analyses=len(self._analyses),
            success_rate=success_rate,
            rollback_rate=rollback_rate,
            avg_deploy_duration=avg_duration,
            avg_rollback_probability=avg_rb,
            by_outcome=by_outcome,
            by_strategy=by_strategy,
            by_risk=by_risk,
            top_risky_services=top_risky,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("deployment.intelligence.engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        outcome_dist: dict[str, int] = {}
        for r in self._records:
            outcome_dist[r.outcome.value] = outcome_dist.get(r.outcome.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "success_threshold": self._success_threshold,
            "outcome_distribution": outcome_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
