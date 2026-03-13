"""AutoInstrumentationManager — auto-instrumentation orchestration."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class InstrumentationTarget(StrEnum):
    PYTHON = "python"
    JAVA = "java"
    NODEJS = "nodejs"
    DOTNET = "dotnet"


class InstrumentationMethod(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"
    HYBRID = "hybrid"
    SDK = "sdk"


class CoverageLevel(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NONE = "none"


# --- Models ---


class AutoInstrumentationManagerRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    instrumentation_target: InstrumentationTarget = InstrumentationTarget.PYTHON
    instrumentation_method: InstrumentationMethod = InstrumentationMethod.AUTO
    coverage_level: CoverageLevel = CoverageLevel.FULL
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AutoInstrumentationManagerAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    instrumentation_target: InstrumentationTarget = InstrumentationTarget.PYTHON
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AutoInstrumentationManagerReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_instrumentation_target: dict[str, int] = Field(default_factory=dict)
    by_instrumentation_method: dict[str, int] = Field(default_factory=dict)
    by_coverage_level: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutoInstrumentationManager:
    """Auto-instrumentation orchestration engine."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[AutoInstrumentationManagerRecord] = []
        self._analyses: list[AutoInstrumentationManagerAnalysis] = []
        logger.info(
            "auto.instrumentation.manager.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        instrumentation_target: InstrumentationTarget = (InstrumentationTarget.PYTHON),
        instrumentation_method: InstrumentationMethod = (InstrumentationMethod.AUTO),
        coverage_level: CoverageLevel = (CoverageLevel.FULL),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AutoInstrumentationManagerRecord:
        record = AutoInstrumentationManagerRecord(
            name=name,
            instrumentation_target=instrumentation_target,
            instrumentation_method=instrumentation_method,
            coverage_level=coverage_level,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "auto.instrumentation.manager.record_added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        """Find record by id, create analysis."""
        for r in self._records:
            if r.id == key:
                analysis = AutoInstrumentationManagerAnalysis(
                    name=r.name,
                    instrumentation_target=(r.instrumentation_target),
                    analysis_score=r.score,
                    threshold=self._threshold,
                    breached=(r.score < self._threshold),
                    description=(f"Processed {r.name}"),
                )
                self._analyses.append(analysis)
                return {
                    "status": "processed",
                    "analysis_id": analysis.id,
                    "breached": analysis.breached,
                }
        return {"status": "not_found", "key": key}

    # -- domain methods ---

    def compute_instrumentation_coverage(
        self,
    ) -> dict[str, Any]:
        """Compute coverage per target language."""
        target_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.instrumentation_target.value
            target_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in target_data.items():
            result[k] = {
                "count": len(scores),
                "avg_coverage": round(sum(scores) / len(scores), 2),
            }
        return result

    def detect_missing_instrumentors(
        self,
    ) -> list[dict[str, Any]]:
        """Detect services with missing instrumentation."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.coverage_level == CoverageLevel.NONE:
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "target": (r.instrumentation_target.value),
                        "service": r.service,
                        "score": r.score,
                    }
                )
        return results

    def recommend_instrumentation_plan(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend instrumentation plans per service."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "service": svc,
                    "avg_score": avg,
                    "plan": (
                        "enable_auto_instrumentation" if avg < self._threshold else "maintain"
                    ),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    # -- report / stats ---

    def generate_report(
        self,
    ) -> AutoInstrumentationManagerReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            v1 = r.instrumentation_target.value
            by_e1[v1] = by_e1.get(v1, 0) + 1
            v2 = r.instrumentation_method.value
            by_e2[v2] = by_e2.get(v2, 0) + 1
            v3 = r.coverage_level.value
            by_e3[v3] = by_e3.get(v3, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg < self._threshold:
            recs.append(f"Avg score {avg} below threshold ({self._threshold})")
        if not recs:
            recs.append("Auto Instrumentation Manager is healthy")
        return AutoInstrumentationManagerReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg,
            by_instrumentation_target=by_e1,
            by_instrumentation_method=by_e2,
            by_coverage_level=by_e3,
            top_gaps=[r.name for r in self._records if r.score < self._threshold][:5],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("auto.instrumentation.manager.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.instrumentation_target.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "target_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
