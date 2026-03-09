"""Security Chaos Engine — chaos engineering for security testing."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ExperimentType(StrEnum):
    CREDENTIAL_LEAK = "credential_leak"
    NETWORK_PARTITION = "network_partition"
    CERTIFICATE_EXPIRY = "certificate_expiry"
    DNS_HIJACK = "dns_hijack"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_CORRUPTION = "data_corruption"


class ExperimentStatus(StrEnum):
    DESIGNED = "designed"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


class ResilienceGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


# --- Models ---


class Experiment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    experiment_type: ExperimentType = ExperimentType.CREDENTIAL_LEAK
    status: ExperimentStatus = ExperimentStatus.DESIGNED
    blast_radius: str = ""
    target_service: str = ""
    team: str = ""
    hypothesis: str = ""
    created_at: float = Field(default_factory=time.time)


class ExperimentResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str = ""
    detected: bool = False
    response_time_ms: float = 0.0
    resilience_score: float = 0.0
    findings: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class ChaosReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_experiments: int = 0
    total_results: int = 0
    avg_resilience: float = 0.0
    detection_rate: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    grade: str = ""
    top_findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityChaosEngine:
    """Chaos engineering for security testing."""

    def __init__(
        self,
        max_records: int = 200000,
        resilience_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._resilience_threshold = resilience_threshold
        self._experiments: list[Experiment] = []
        self._results: list[ExperimentResult] = []
        logger.info(
            "security_chaos_engine.initialized",
            max_records=max_records,
            resilience_threshold=resilience_threshold,
        )

    @staticmethod
    def _score_to_grade(score: float) -> ResilienceGrade:
        if score >= 90:
            return ResilienceGrade.EXCELLENT
        if score >= 75:
            return ResilienceGrade.GOOD
        if score >= 50:
            return ResilienceGrade.FAIR
        if score >= 25:
            return ResilienceGrade.POOR
        return ResilienceGrade.CRITICAL

    def design_experiment(
        self,
        name: str,
        experiment_type: ExperimentType = ExperimentType.CREDENTIAL_LEAK,
        blast_radius: str = "",
        target_service: str = "",
        team: str = "",
        hypothesis: str = "",
    ) -> Experiment:
        """Design a security chaos experiment."""
        experiment = Experiment(
            name=name,
            experiment_type=experiment_type,
            blast_radius=blast_radius,
            target_service=target_service,
            team=team,
            hypothesis=hypothesis,
        )
        self._experiments.append(experiment)
        if len(self._experiments) > self._max_records:
            self._experiments = self._experiments[-self._max_records :]
        logger.info(
            "security_chaos_engine.experiment_designed",
            experiment_id=experiment.id,
            name=name,
            type=experiment_type.value,
        )
        return experiment

    def inject_security_failure(
        self,
        experiment_id: str,
    ) -> dict[str, Any]:
        """Inject a security failure for an experiment."""
        for e in self._experiments:
            if e.id == experiment_id:
                e.status = ExperimentStatus.RUNNING
                logger.info(
                    "security_chaos_engine.failure_injected",
                    experiment_id=experiment_id,
                )
                return {
                    "experiment_id": experiment_id,
                    "status": ExperimentStatus.RUNNING.value,
                    "type": e.experiment_type.value,
                }
        return {"experiment_id": experiment_id, "error": "not_found"}

    def observe_response(
        self,
        experiment_id: str,
        detected: bool = False,
        response_time_ms: float = 0.0,
        resilience_score: float = 0.0,
        findings: list[str] | None = None,
    ) -> ExperimentResult:
        """Observe and record the system response to injected failure."""
        for e in self._experiments:
            if e.id == experiment_id:
                e.status = ExperimentStatus.COMPLETED
                break
        result = ExperimentResult(
            experiment_id=experiment_id,
            detected=detected,
            response_time_ms=response_time_ms,
            resilience_score=resilience_score,
            findings=findings or [],
        )
        self._results.append(result)
        if len(self._results) > self._max_records:
            self._results = self._results[-self._max_records :]
        logger.info(
            "security_chaos_engine.response_observed",
            experiment_id=experiment_id,
            detected=detected,
            resilience_score=resilience_score,
        )
        return result

    def evaluate_resilience(self) -> dict[str, Any]:
        """Evaluate overall security resilience across experiments."""
        if not self._results:
            return {"avg_resilience": 0.0, "detection_rate": 0.0, "grade": "critical"}
        scores = [r.resilience_score for r in self._results]
        avg = round(sum(scores) / len(scores), 2)
        detected = sum(1 for r in self._results if r.detected)
        rate = round(detected / len(self._results) * 100, 2)
        grade = self._score_to_grade(avg)
        return {
            "avg_resilience": avg,
            "detection_rate": rate,
            "grade": grade.value,
            "total_experiments": len(self._results),
        }

    def generate_findings(self) -> list[dict[str, Any]]:
        """Generate consolidated findings from all experiments."""
        findings: list[dict[str, Any]] = []
        for r in self._results:
            exp_name = ""
            exp_type = ""
            for e in self._experiments:
                if e.id == r.experiment_id:
                    exp_name = e.name
                    exp_type = e.experiment_type.value
                    break
            for f in r.findings:
                findings.append(
                    {
                        "experiment": exp_name,
                        "type": exp_type,
                        "finding": f,
                        "resilience_score": r.resilience_score,
                        "detected": r.detected,
                    }
                )
        return sorted(findings, key=lambda x: x["resilience_score"])

    def generate_report(self) -> ChaosReport:
        """Generate a comprehensive chaos engineering report."""
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for e in self._experiments:
            by_type[e.experiment_type.value] = by_type.get(e.experiment_type.value, 0) + 1
            by_status[e.status.value] = by_status.get(e.status.value, 0) + 1
        scores = [r.resilience_score for r in self._results]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        detected = sum(1 for r in self._results if r.detected)
        det_rate = round(detected / len(self._results) * 100, 2) if self._results else 0.0
        grade = self._score_to_grade(avg).value
        all_findings = []
        for r in self._results:
            all_findings.extend(r.findings)
        recs: list[str] = []
        if avg < self._resilience_threshold:
            recs.append(f"Avg resilience {avg} below threshold ({self._resilience_threshold})")
        if det_rate < 80:
            recs.append(f"Detection rate {det_rate}% needs improvement")
        if not recs:
            recs.append("Security resilience within healthy range")
        return ChaosReport(
            total_experiments=len(self._experiments),
            total_results=len(self._results),
            avg_resilience=avg,
            detection_rate=det_rate,
            by_type=by_type,
            by_status=by_status,
            grade=grade,
            top_findings=all_findings[:5],
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        dist: dict[str, int] = {}
        for e in self._experiments:
            key = e.experiment_type.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_experiments": len(self._experiments),
            "total_results": len(self._results),
            "resilience_threshold": self._resilience_threshold,
            "type_distribution": dist,
            "unique_teams": len({e.team for e in self._experiments}),
            "unique_services": len({e.target_service for e in self._experiments}),
        }

    def clear_data(self) -> dict[str, str]:
        """Clear all stored data."""
        self._experiments.clear()
        self._results.clear()
        logger.info("security_chaos_engine.cleared")
        return {"status": "cleared"}
