"""Performance Regression Detector
compute regression magnitude, detect latent regressions,
rank deployments by regression risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RegressionSeverity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    NEGLIGIBLE = "negligible"


class DetectionMethod(StrEnum):
    BASELINE_COMPARISON = "baseline_comparison"
    STATISTICAL = "statistical"
    ML_BASED = "ml_based"
    THRESHOLD = "threshold"


class RegressionType(StrEnum):
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    RESOURCE = "resource"


# --- Models ---


class PerfRegressionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    regression_severity: RegressionSeverity = RegressionSeverity.MINOR
    detection_method: DetectionMethod = DetectionMethod.BASELINE_COMPARISON
    regression_type: RegressionType = RegressionType.LATENCY
    magnitude: float = 0.0
    baseline_value: float = 0.0
    current_value: float = 0.0
    service: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PerfRegressionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    computed_magnitude: float = 0.0
    regression_severity: RegressionSeverity = RegressionSeverity.MINOR
    is_latent: bool = False
    contributing_factors: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PerfRegressionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_magnitude: float = 0.0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_detection_method: dict[str, int] = Field(default_factory=dict)
    by_regression_type: dict[str, int] = Field(default_factory=dict)
    critical_deployments: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PerfRegressionDetector:
    """Compute regression magnitude, detect latent
    regressions, rank deployments by regression risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[PerfRegressionRecord] = []
        self._analyses: dict[str, PerfRegressionAnalysis] = {}
        logger.info(
            "perf_regression_detector.init",
            max_records=max_records,
        )

    def add_record(
        self,
        deployment_id: str = "",
        regression_severity: RegressionSeverity = RegressionSeverity.MINOR,
        detection_method: DetectionMethod = DetectionMethod.BASELINE_COMPARISON,
        regression_type: RegressionType = RegressionType.LATENCY,
        magnitude: float = 0.0,
        baseline_value: float = 0.0,
        current_value: float = 0.0,
        service: str = "",
        description: str = "",
    ) -> PerfRegressionRecord:
        record = PerfRegressionRecord(
            deployment_id=deployment_id,
            regression_severity=regression_severity,
            detection_method=detection_method,
            regression_type=regression_type,
            magnitude=magnitude,
            baseline_value=baseline_value,
            current_value=current_value,
            service=service,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "perf_regression_detector.record_added",
            record_id=record.id,
            deployment_id=deployment_id,
        )
        return record

    def process(self, key: str) -> PerfRegressionAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        factors = sum(1 for r in self._records if r.deployment_id == rec.deployment_id)
        latent = rec.regression_severity == RegressionSeverity.MINOR and rec.magnitude > 0
        analysis = PerfRegressionAnalysis(
            deployment_id=rec.deployment_id,
            computed_magnitude=round(rec.magnitude, 2),
            regression_severity=rec.regression_severity,
            is_latent=latent,
            contributing_factors=factors,
            description=f"Deployment {rec.deployment_id} magnitude {rec.magnitude}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> PerfRegressionReport:
        by_sev: dict[str, int] = {}
        by_dm: dict[str, int] = {}
        by_rt: dict[str, int] = {}
        mags: list[float] = []
        for r in self._records:
            k = r.regression_severity.value
            by_sev[k] = by_sev.get(k, 0) + 1
            k2 = r.detection_method.value
            by_dm[k2] = by_dm.get(k2, 0) + 1
            k3 = r.regression_type.value
            by_rt[k3] = by_rt.get(k3, 0) + 1
            mags.append(r.magnitude)
        avg = round(sum(mags) / len(mags), 2) if mags else 0.0
        critical = list(
            {
                r.deployment_id
                for r in self._records
                if r.regression_severity in (RegressionSeverity.CRITICAL, RegressionSeverity.MAJOR)
            }
        )[:10]
        recs: list[str] = []
        if critical:
            recs.append(f"{len(critical)} critical regression deployments detected")
        if not recs:
            recs.append("No significant regressions detected")
        return PerfRegressionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_magnitude=avg,
            by_severity=by_sev,
            by_detection_method=by_dm,
            by_regression_type=by_rt,
            critical_deployments=critical,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        sev_dist: dict[str, int] = {}
        for r in self._records:
            k = r.regression_severity.value
            sev_dist[k] = sev_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "severity_distribution": sev_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("perf_regression_detector.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_regression_magnitude(
        self,
    ) -> list[dict[str, Any]]:
        """Aggregate regression magnitude per deployment."""
        dep_mags: dict[str, list[float]] = {}
        dep_types: dict[str, str] = {}
        for r in self._records:
            dep_mags.setdefault(r.deployment_id, []).append(r.magnitude)
            dep_types[r.deployment_id] = r.regression_type.value
        results: list[dict[str, Any]] = []
        for did, mags in dep_mags.items():
            total = round(sum(mags), 2)
            avg = round(total / len(mags), 2)
            results.append(
                {
                    "deployment_id": did,
                    "regression_type": dep_types[did],
                    "total_magnitude": total,
                    "avg_magnitude": avg,
                    "event_count": len(mags),
                }
            )
        results.sort(key=lambda x: x["total_magnitude"], reverse=True)
        return results

    def detect_latent_regressions(
        self,
    ) -> list[dict[str, Any]]:
        """Detect deployments with latent regressions."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.magnitude > 0
                and r.regression_severity
                in (RegressionSeverity.MINOR, RegressionSeverity.NEGLIGIBLE)
                and r.deployment_id not in seen
            ):
                seen.add(r.deployment_id)
                results.append(
                    {
                        "deployment_id": r.deployment_id,
                        "regression_type": r.regression_type.value,
                        "magnitude": r.magnitude,
                        "severity": r.regression_severity.value,
                    }
                )
        results.sort(key=lambda x: x["magnitude"], reverse=True)
        return results

    def rank_deployments_by_regression_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Rank all deployments by aggregate regression risk."""
        dep_data: dict[str, float] = {}
        dep_types: dict[str, str] = {}
        for r in self._records:
            dep_data[r.deployment_id] = dep_data.get(r.deployment_id, 0.0) + r.magnitude
            dep_types[r.deployment_id] = r.regression_type.value
        results: list[dict[str, Any]] = []
        for did, total in dep_data.items():
            results.append(
                {
                    "deployment_id": did,
                    "regression_type": dep_types[did],
                    "aggregate_magnitude": round(total, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["aggregate_magnitude"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
