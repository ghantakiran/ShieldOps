"""Security Posture Trend Engine
compute posture trajectory, detect regression signals,
benchmark against peers."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PostureDimension(StrEnum):
    NETWORK = "network"
    IDENTITY = "identity"
    DATA = "data"
    APPLICATION = "application"


class TrendDirection(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    VOLATILE = "volatile"


class BenchmarkSource(StrEnum):
    INDUSTRY = "industry"
    INTERNAL = "internal"
    REGULATORY = "regulatory"
    PEER = "peer"


# --- Models ---


class PostureTrendRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    posture_id: str = ""
    dimension: PostureDimension = PostureDimension.NETWORK
    direction: TrendDirection = TrendDirection.STABLE
    benchmark: BenchmarkSource = BenchmarkSource.INDUSTRY
    posture_score: float = 0.0
    benchmark_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PostureTrendAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    posture_id: str = ""
    dimension: PostureDimension = PostureDimension.NETWORK
    analysis_score: float = 0.0
    trajectory: str = ""
    regression_risk: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PostureTrendReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_posture_score: float = 0.0
    avg_benchmark_gap: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_direction: dict[str, int] = Field(default_factory=dict)
    by_benchmark: dict[str, int] = Field(default_factory=dict)
    declining_areas: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityPostureTrendEngine:
    """Compute posture trajectory, detect regression
    signals, benchmark against peers."""

    def __init__(
        self,
        max_records: int = 200000,
        regression_threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._regression_threshold = regression_threshold
        self._records: list[PostureTrendRecord] = []
        self._analyses: list[PostureTrendAnalysis] = []
        logger.info(
            "security_posture_trend_engine.init",
            max_records=max_records,
            regression_threshold=regression_threshold,
        )

    def add_record(
        self,
        posture_id: str,
        dimension: PostureDimension = (PostureDimension.NETWORK),
        direction: TrendDirection = (TrendDirection.STABLE),
        benchmark: BenchmarkSource = (BenchmarkSource.INDUSTRY),
        posture_score: float = 0.0,
        benchmark_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PostureTrendRecord:
        record = PostureTrendRecord(
            posture_id=posture_id,
            dimension=dimension,
            direction=direction,
            benchmark=benchmark,
            posture_score=posture_score,
            benchmark_score=benchmark_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_posture_trend.record_added",
            record_id=record.id,
            posture_id=posture_id,
        )
        return record

    def process(self, key: str) -> PostureTrendAnalysis | None:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return None
        gap = rec.benchmark_score - rec.posture_score
        regression = max(0.0, gap)
        trajectory = "above_benchmark" if gap <= 0 else "below_benchmark"
        analysis = PostureTrendAnalysis(
            posture_id=rec.posture_id,
            dimension=rec.dimension,
            analysis_score=round(rec.posture_score, 2),
            trajectory=trajectory,
            regression_risk=round(regression, 2),
            description=(f"Posture {rec.posture_id} {trajectory}"),
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return analysis

    def generate_report(self) -> PostureTrendReport:
        by_dim: dict[str, int] = {}
        by_dir: dict[str, int] = {}
        by_bm: dict[str, int] = {}
        scores: list[float] = []
        gaps: list[float] = []
        for r in self._records:
            d = r.dimension.value
            by_dim[d] = by_dim.get(d, 0) + 1
            dr = r.direction.value
            by_dir[dr] = by_dir.get(dr, 0) + 1
            b = r.benchmark.value
            by_bm[b] = by_bm.get(b, 0) + 1
            scores.append(r.posture_score)
            gaps.append(r.benchmark_score - r.posture_score)
        avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
        avg_g = round(sum(gaps) / len(gaps), 2) if gaps else 0.0
        declining = [
            r.posture_id for r in self._records if r.posture_score < self._regression_threshold
        ][:5]
        recs: list[str] = []
        if declining:
            recs.append(f"{len(declining)} areas below regression threshold")
        if not recs:
            recs.append("Security posture is healthy")
        return PostureTrendReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_posture_score=avg_s,
            avg_benchmark_gap=avg_g,
            by_dimension=by_dim,
            by_direction=by_dir,
            by_benchmark=by_bm,
            declining_areas=declining,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dim_dist: dict[str, int] = {}
        for r in self._records:
            k = r.dimension.value
            dim_dist[k] = dim_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "regression_threshold": (self._regression_threshold),
            "dimension_distribution": dim_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_posture_trend_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_posture_trajectory(
        self,
    ) -> list[dict[str, Any]]:
        """Compute posture trajectory per dimension."""
        dim_data: dict[str, list[float]] = {}
        for r in self._records:
            k = r.dimension.value
            dim_data.setdefault(k, []).append(r.posture_score)
        results: list[dict[str, Any]] = []
        for dim, scores in dim_data.items():
            avg = round(sum(scores) / len(scores), 2)
            mid = len(scores) // 2
            if mid > 0 and len(scores) > 1:
                first = sum(scores[:mid]) / mid
                second = sum(scores[mid:]) / (len(scores) - mid)
                delta = round(second - first, 2)
            else:
                delta = 0.0
            results.append(
                {
                    "dimension": dim,
                    "avg_score": avg,
                    "trajectory_delta": delta,
                    "sample_count": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["avg_score"],
        )
        return results

    def detect_regression_signals(
        self,
    ) -> list[dict[str, Any]]:
        """Detect regression: score below threshold
        or declining direction."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if (
                r.posture_score < self._regression_threshold
                or r.direction == TrendDirection.DECLINING
            ):
                gap = round(
                    self._regression_threshold - r.posture_score,
                    2,
                )
                results.append(
                    {
                        "posture_id": r.posture_id,
                        "dimension": r.dimension.value,
                        "posture_score": r.posture_score,
                        "direction": r.direction.value,
                        "regression_gap": gap,
                    }
                )
        results.sort(
            key=lambda x: x["regression_gap"],
            reverse=True,
        )
        return results

    def benchmark_against_peers(
        self,
    ) -> dict[str, Any]:
        """Benchmark posture scores vs benchmark
        scores per dimension."""
        if not self._records:
            return {
                "overall_gap": 0.0,
                "by_dimension": {},
            }
        dim_gaps: dict[str, list[float]] = {}
        for r in self._records:
            k = r.dimension.value
            gap = r.benchmark_score - r.posture_score
            dim_gaps.setdefault(k, []).append(gap)
        by_dim: dict[str, float] = {}
        all_gaps: list[float] = []
        for d, gps in dim_gaps.items():
            avg = round(sum(gps) / len(gps), 2)
            by_dim[d] = avg
            all_gaps.extend(gps)
        overall = round(sum(all_gaps) / len(all_gaps), 2) if all_gaps else 0.0
        return {
            "overall_gap": overall,
            "by_dimension": by_dim,
        }
