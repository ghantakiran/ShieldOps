"""Security Posture Trend Analyzer — track security posture over time with regression detection."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PostureTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    VOLATILE = "volatile"
    UNASSESSED = "unassessed"


class PostureDomain(StrEnum):
    NETWORK = "network"
    IDENTITY = "identity"
    DATA = "data"
    APPLICATION = "application"
    INFRASTRUCTURE = "infrastructure"


class RegressionSeverity(StrEnum):
    NEGLIGIBLE = "negligible"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


# --- Models ---


class PostureSnapshot(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain: PostureDomain = PostureDomain.NETWORK
    score: float = 0.0
    max_score: float = 100.0
    findings_count: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    scan_source: str = ""
    created_at: float = Field(default_factory=time.time)


class PostureRegression(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain: PostureDomain = PostureDomain.NETWORK
    previous_score: float = 0.0
    current_score: float = 0.0
    delta: float = 0.0
    severity: RegressionSeverity = RegressionSeverity.NEGLIGIBLE
    cause: str = ""
    created_at: float = Field(default_factory=time.time)


class PostureTrendReport(BaseModel):
    total_snapshots: int = 0
    avg_score: float = 0.0
    by_domain: dict[str, float] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    regressions_detected: int = 0
    weakest_domains: list[str] = Field(default_factory=list)
    improvement_velocity: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityPostureTrendAnalyzer:
    """Track security posture over time with regression detection."""

    def __init__(
        self,
        max_records: int = 200000,
        regression_threshold: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._regression_threshold = regression_threshold
        self._records: list[PostureSnapshot] = []
        self._regressions: list[PostureRegression] = []
        logger.info(
            "posture_trend.initialized",
            max_records=max_records,
            regression_threshold=regression_threshold,
        )

    # -- internal helpers ------------------------------------------------

    def _classify_regression_severity(self, delta: float) -> RegressionSeverity:
        abs_delta = abs(delta)
        if abs_delta <= 2:
            return RegressionSeverity.NEGLIGIBLE
        if abs_delta <= 5:
            return RegressionSeverity.MINOR
        if abs_delta <= 10:
            return RegressionSeverity.MODERATE
        if abs_delta <= 20:
            return RegressionSeverity.MAJOR
        return RegressionSeverity.CRITICAL

    def _snapshots_for_domain(
        self,
        domain: PostureDomain,
    ) -> list[PostureSnapshot]:
        return [s for s in self._records if s.domain == domain]

    # -- record / get / list ---------------------------------------------

    def record_snapshot(
        self,
        domain: PostureDomain,
        score: float,
        max_score: float = 100.0,
        findings_count: int = 0,
        critical_findings: int = 0,
        high_findings: int = 0,
        scan_source: str = "",
    ) -> PostureSnapshot:
        snapshot = PostureSnapshot(
            domain=domain,
            score=score,
            max_score=max_score,
            findings_count=findings_count,
            critical_findings=critical_findings,
            high_findings=high_findings,
            scan_source=scan_source,
        )
        self._records.append(snapshot)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "posture_trend.snapshot_recorded",
            snapshot_id=snapshot.id,
            domain=domain.value,
            score=score,
        )
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> PostureSnapshot | None:
        for s in self._records:
            if s.id == snapshot_id:
                return s
        return None

    def list_snapshots(
        self,
        domain: PostureDomain | None = None,
        limit: int = 50,
    ) -> list[PostureSnapshot]:
        results = list(self._records)
        if domain is not None:
            results = [s for s in results if s.domain == domain]
        return results[-limit:]

    # -- domain operations -----------------------------------------------

    def detect_regression(
        self,
        domain: PostureDomain,
    ) -> PostureRegression | None:
        """Compare latest 2 snapshots for domain, return regression if delta > threshold."""
        domain_snapshots = self._snapshots_for_domain(domain)
        if len(domain_snapshots) < 2:
            return None
        previous = domain_snapshots[-2]
        current = domain_snapshots[-1]
        delta = round(previous.score - current.score, 4)
        if delta <= self._regression_threshold:
            return None
        severity = self._classify_regression_severity(delta)
        regression = PostureRegression(
            domain=domain,
            previous_score=previous.score,
            current_score=current.score,
            delta=delta,
            severity=severity,
            cause=f"Score dropped from {previous.score} to {current.score}",
        )
        self._regressions.append(regression)
        logger.info(
            "posture_trend.regression_detected",
            regression_id=regression.id,
            domain=domain.value,
            delta=delta,
            severity=severity.value,
        )
        return regression

    def compute_trend(
        self,
        domain: PostureDomain,
    ) -> dict[str, Any]:
        """Analyze score direction over recent snapshots."""
        domain_snapshots = self._snapshots_for_domain(domain)
        if len(domain_snapshots) < 2:
            return {
                "domain": domain.value,
                "trend": PostureTrend.UNASSESSED.value,
                "snapshot_count": len(domain_snapshots),
                "avg_score": domain_snapshots[0].score if domain_snapshots else 0.0,
            }
        scores = [s.score for s in domain_snapshots]
        recent = scores[-3:] if len(scores) >= 3 else scores
        previous = scores[-6:-3] if len(scores) >= 6 else scores[: len(scores) // 2] or scores[:1]
        avg_recent = sum(recent) / len(recent)
        avg_previous = sum(previous) / len(previous)
        diff = avg_recent - avg_previous
        # Volatility check: std deviation of all scores
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std_dev = variance**0.5
        if std_dev > 5:
            trend = PostureTrend.VOLATILE
        elif diff >= 2:
            trend = PostureTrend.IMPROVING
        elif diff <= -2:
            trend = PostureTrend.DECLINING
        else:
            trend = PostureTrend.STABLE
        return {
            "domain": domain.value,
            "trend": trend.value,
            "snapshot_count": len(domain_snapshots),
            "avg_score": round(mean, 4),
            "std_dev": round(std_dev, 4),
            "recent_avg": round(avg_recent, 4),
            "previous_avg": round(avg_previous, 4),
        }

    def calculate_improvement_velocity(self) -> dict[str, Any]:
        """Average score change per snapshot across all domains."""
        domain_velocities: dict[str, float] = {}
        for domain in PostureDomain:
            snapshots = self._snapshots_for_domain(domain)
            if len(snapshots) < 2:
                continue
            deltas = [snapshots[i].score - snapshots[i - 1].score for i in range(1, len(snapshots))]
            avg_delta = sum(deltas) / len(deltas)
            domain_velocities[domain.value] = round(avg_delta, 4)
        overall = (
            round(sum(domain_velocities.values()) / len(domain_velocities), 4)
            if domain_velocities
            else 0.0
        )
        return {
            "overall_velocity": overall,
            "by_domain": domain_velocities,
            "interpretation": (
                "improving" if overall > 0 else "declining" if overall < 0 else "flat"
            ),
        }

    def identify_weakest_domains(self) -> list[dict[str, Any]]:
        """Domains with lowest average scores."""
        domain_scores: dict[str, list[float]] = {}
        for s in self._records:
            domain_scores.setdefault(s.domain.value, []).append(s.score)
        results: list[dict[str, Any]] = []
        for domain_name, scores in domain_scores.items():
            avg = round(sum(scores) / len(scores), 4)
            results.append(
                {
                    "domain": domain_name,
                    "avg_score": avg,
                    "snapshot_count": len(scores),
                    "min_score": min(scores),
                    "max_score": max(scores),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    def rank_regressions_by_severity(self) -> list[dict[str, Any]]:
        """Sort detected regressions by severity."""
        severity_order = {
            RegressionSeverity.CRITICAL: 0,
            RegressionSeverity.MAJOR: 1,
            RegressionSeverity.MODERATE: 2,
            RegressionSeverity.MINOR: 3,
            RegressionSeverity.NEGLIGIBLE: 4,
        }
        sorted_regressions = sorted(
            self._regressions,
            key=lambda r: severity_order.get(r.severity, 5),
        )
        return [
            {
                "regression_id": r.id,
                "domain": r.domain.value,
                "delta": r.delta,
                "severity": r.severity.value,
                "previous_score": r.previous_score,
                "current_score": r.current_score,
            }
            for r in sorted_regressions
        ]

    # -- report / stats --------------------------------------------------

    def generate_trend_report(self) -> PostureTrendReport:
        scores = [s.score for s in self._records]
        avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        by_domain: dict[str, float] = {}
        domain_scores: dict[str, list[float]] = {}
        for s in self._records:
            domain_scores.setdefault(s.domain.value, []).append(s.score)
        for d, sc in domain_scores.items():
            by_domain[d] = round(sum(sc) / len(sc), 4)
        by_trend: dict[str, int] = {}
        for domain in PostureDomain:
            trend_result = self.compute_trend(domain)
            trend_val = trend_result["trend"]
            by_trend[trend_val] = by_trend.get(trend_val, 0) + 1
        weakest = self.identify_weakest_domains()
        weakest_names = [w["domain"] for w in weakest[:3]]
        velocity = self.calculate_improvement_velocity()
        recs: list[str] = []
        if self._regressions:
            recs.append(f"{len(self._regressions)} regression(s) detected")
        if weakest:
            recs.append(f"Weakest domain: {weakest[0]['domain']} (avg {weakest[0]['avg_score']})")
        declining = by_trend.get(PostureTrend.DECLINING.value, 0)
        if declining > 0:
            recs.append(f"{declining} domain(s) showing declining trend")
        if not recs:
            recs.append("Security posture is stable across all domains")
        return PostureTrendReport(
            total_snapshots=len(self._records),
            avg_score=avg_score,
            by_domain=by_domain,
            by_trend=by_trend,
            regressions_detected=len(self._regressions),
            weakest_domains=weakest_names,
            improvement_velocity=velocity["overall_velocity"],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._regressions.clear()
        logger.info("posture_trend.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        domain_dist: dict[str, int] = {}
        for s in self._records:
            key = s.domain.value
            domain_dist[key] = domain_dist.get(key, 0) + 1
        return {
            "total_snapshots": len(self._records),
            "total_regressions": len(self._regressions),
            "regression_threshold": self._regression_threshold,
            "domain_distribution": domain_dist,
        }
