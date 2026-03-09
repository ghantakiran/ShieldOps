"""Security Posture Aggregator — aggregate security posture across all environments."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class Environment(StrEnum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    KUBERNETES = "kubernetes"
    ON_PREM = "on_prem"


class PostureGrade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class PostureCategory(StrEnum):
    IDENTITY = "identity"
    NETWORK = "network"
    DATA = "data"
    COMPUTE = "compute"
    COMPLIANCE = "compliance"


# --- Models ---


class PostureData(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    environment: Environment = Environment.AWS
    category: PostureCategory = PostureCategory.IDENTITY
    score: float = 0.0
    grade: PostureGrade = PostureGrade.F
    service: str = ""
    team: str = ""
    findings_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PostureBaseline(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    environment: Environment = Environment.AWS
    baseline_score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class PostureReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_entries: int = 0
    total_baselines: int = 0
    avg_score: float = 0.0
    overall_grade: str = ""
    by_environment: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    drift_detected: bool = False
    top_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityPostureAggregator:
    """Aggregate security posture across all environments."""

    def __init__(
        self,
        max_records: int = 200000,
        score_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._score_threshold = score_threshold
        self._entries: list[PostureData] = []
        self._baselines: list[PostureBaseline] = []
        logger.info(
            "security_posture_aggregator.initialized",
            max_records=max_records,
            score_threshold=score_threshold,
        )

    @staticmethod
    def _score_to_grade(score: float) -> PostureGrade:
        if score >= 90:
            return PostureGrade.A
        if score >= 75:
            return PostureGrade.B
        if score >= 60:
            return PostureGrade.C
        if score >= 40:
            return PostureGrade.D
        return PostureGrade.F

    def collect_posture_data(
        self,
        environment: Environment = Environment.AWS,
        category: PostureCategory = PostureCategory.IDENTITY,
        score: float = 0.0,
        service: str = "",
        team: str = "",
        findings_count: int = 0,
        description: str = "",
    ) -> PostureData:
        """Collect posture data from an environment."""
        grade = self._score_to_grade(score)
        entry = PostureData(
            environment=environment,
            category=category,
            score=score,
            grade=grade,
            service=service,
            team=team,
            findings_count=findings_count,
            description=description,
        )
        self._entries.append(entry)
        if len(self._entries) > self._max_records:
            self._entries = self._entries[-self._max_records :]
        logger.info(
            "security_posture_aggregator.data_collected",
            entry_id=entry.id,
            environment=environment.value,
            score=score,
        )
        return entry

    def aggregate_scores(self) -> dict[str, Any]:
        """Aggregate scores by environment and category."""
        if not self._entries:
            return {"environments": {}, "categories": {}, "overall": 0.0}
        env_scores: dict[str, list[float]] = {}
        cat_scores: dict[str, list[float]] = {}
        for e in self._entries:
            env_scores.setdefault(e.environment.value, []).append(e.score)
            cat_scores.setdefault(e.category.value, []).append(e.score)
        env_avg = {k: round(sum(v) / len(v), 2) for k, v in env_scores.items()}
        cat_avg = {k: round(sum(v) / len(v), 2) for k, v in cat_scores.items()}
        all_scores = [e.score for e in self._entries]
        overall = round(sum(all_scores) / len(all_scores), 2)
        return {"environments": env_avg, "categories": cat_avg, "overall": overall}

    def detect_posture_drift(self, drift_threshold: float = 10.0) -> list[dict[str, Any]]:
        """Detect posture drift by comparing recent entries to baselines."""
        drifts: list[dict[str, Any]] = []
        baseline_map: dict[str, float] = {}
        for b in self._baselines:
            baseline_map[b.environment.value] = b.baseline_score
        env_scores: dict[str, list[float]] = {}
        for e in self._entries:
            env_scores.setdefault(e.environment.value, []).append(e.score)
        for env, scores in env_scores.items():
            current_avg = sum(scores) / len(scores)
            baseline = baseline_map.get(env)
            if baseline is not None:
                delta = round(current_avg - baseline, 2)
                if abs(delta) >= drift_threshold:
                    drifts.append(
                        {
                            "environment": env,
                            "baseline": baseline,
                            "current": round(current_avg, 2),
                            "delta": delta,
                            "direction": "improved" if delta > 0 else "degraded",
                        }
                    )
        return drifts

    def generate_posture_report(self) -> PostureReport:
        """Generate a comprehensive posture report."""
        by_env: dict[str, int] = {}
        by_cat: dict[str, int] = {}
        for e in self._entries:
            by_env[e.environment.value] = by_env.get(e.environment.value, 0) + 1
            by_cat[e.category.value] = by_cat.get(e.category.value, 0) + 1
        scores = [e.score for e in self._entries]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        grade = self._score_to_grade(avg).value
        drift = len(self.detect_posture_drift()) > 0
        issues = [e.description for e in self._entries if e.score < self._score_threshold][:5]
        recs: list[str] = []
        if issues:
            recs.append(f"{len(issues)} posture item(s) below threshold")
        if avg < self._score_threshold:
            recs.append(f"Avg score {avg} below threshold ({self._score_threshold})")
        if not recs:
            recs.append("Security posture within healthy range")
        return PostureReport(
            total_entries=len(self._entries),
            total_baselines=len(self._baselines),
            avg_score=avg,
            overall_grade=grade,
            by_environment=by_env,
            by_category=by_cat,
            drift_detected=drift,
            top_issues=issues,
            recommendations=recs,
        )

    def compare_baselines(
        self,
        environment: Environment,
        baseline_score: float,
    ) -> PostureBaseline:
        """Store a baseline score for comparison."""
        baseline = PostureBaseline(
            environment=environment,
            baseline_score=baseline_score,
        )
        self._baselines.append(baseline)
        if len(self._baselines) > self._max_records:
            self._baselines = self._baselines[-self._max_records :]
        logger.info(
            "security_posture_aggregator.baseline_stored",
            environment=environment.value,
            baseline_score=baseline_score,
        )
        return baseline

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        dist: dict[str, int] = {}
        for e in self._entries:
            key = e.environment.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_entries": len(self._entries),
            "total_baselines": len(self._baselines),
            "score_threshold": self._score_threshold,
            "environment_distribution": dist,
            "unique_teams": len({e.team for e in self._entries}),
            "unique_services": len({e.service for e in self._entries}),
        }

    def clear_data(self) -> dict[str, str]:
        """Clear all stored data."""
        self._entries.clear()
        self._baselines.clear()
        logger.info("security_posture_aggregator.cleared")
        return {"status": "cleared"}
