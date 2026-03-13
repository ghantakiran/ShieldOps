"""IaC Test Coverage Analyzer
compute test coverage ratio, detect untested
resources, rank modules by testing gaps."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TestType(StrEnum):
    UNIT = "unit"
    INTEGRATION = "integration"
    CONTRACT = "contract"
    E2E = "e2e"


class CoverageStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NONE = "none"


class TestFramework(StrEnum):
    TERRATEST = "terratest"
    KITCHEN = "kitchen"
    PYTEST = "pytest"
    CUSTOM = "custom"


# --- Models ---


class TestCoverageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    module_id: str = ""
    module_name: str = ""
    test_type: TestType = TestType.UNIT
    coverage_status: CoverageStatus = CoverageStatus.PARTIAL
    test_framework: TestFramework = TestFramework.TERRATEST
    coverage_pct: float = 0.0
    total_resources: int = 0
    tested_resources: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TestCoverageAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    module_id: str = ""
    computed_coverage: float = 0.0
    coverage_status: CoverageStatus = CoverageStatus.PARTIAL
    untested_count: int = 0
    test_type_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TestCoverageReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_coverage: float = 0.0
    by_test_type: dict[str, int] = Field(default_factory=dict)
    by_coverage_status: dict[str, int] = Field(default_factory=dict)
    by_test_framework: dict[str, int] = Field(default_factory=dict)
    low_coverage_modules: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IacTestCoverageAnalyzer:
    """Compute test coverage ratio, detect untested
    resources, rank modules by testing gaps."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TestCoverageRecord] = []
        self._analyses: dict[str, TestCoverageAnalysis] = {}
        logger.info(
            "iac_test_coverage_analyzer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        module_id: str = "",
        module_name: str = "",
        test_type: TestType = TestType.UNIT,
        coverage_status: CoverageStatus = (CoverageStatus.PARTIAL),
        test_framework: TestFramework = (TestFramework.TERRATEST),
        coverage_pct: float = 0.0,
        total_resources: int = 0,
        tested_resources: int = 0,
        description: str = "",
    ) -> TestCoverageRecord:
        record = TestCoverageRecord(
            module_id=module_id,
            module_name=module_name,
            test_type=test_type,
            coverage_status=coverage_status,
            test_framework=test_framework,
            coverage_pct=coverage_pct,
            total_resources=total_resources,
            tested_resources=tested_resources,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "test_coverage.record_added",
            record_id=record.id,
            module_id=module_id,
        )
        return record

    def process(self, key: str) -> TestCoverageAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        untested = rec.total_resources - rec.tested_resources
        types = len({r.test_type for r in self._records if r.module_id == rec.module_id})
        analysis = TestCoverageAnalysis(
            module_id=rec.module_id,
            computed_coverage=round(rec.coverage_pct, 2),
            coverage_status=rec.coverage_status,
            untested_count=max(untested, 0),
            test_type_count=types,
            description=(f"Module {rec.module_id} coverage {rec.coverage_pct}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> TestCoverageReport:
        by_tt: dict[str, int] = {}
        by_cs: dict[str, int] = {}
        by_tf: dict[str, int] = {}
        coverages: list[float] = []
        for r in self._records:
            k = r.test_type.value
            by_tt[k] = by_tt.get(k, 0) + 1
            k2 = r.coverage_status.value
            by_cs[k2] = by_cs.get(k2, 0) + 1
            k3 = r.test_framework.value
            by_tf[k3] = by_tf.get(k3, 0) + 1
            coverages.append(r.coverage_pct)
        avg = round(sum(coverages) / len(coverages), 2) if coverages else 0.0
        low = list(
            {
                r.module_id
                for r in self._records
                if r.coverage_status
                in (
                    CoverageStatus.MINIMAL,
                    CoverageStatus.NONE,
                )
            }
        )[:10]
        recs: list[str] = []
        if low:
            recs.append(f"{len(low)} modules need more tests")
        if not recs:
            recs.append("Test coverage is adequate")
        return TestCoverageReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_coverage=avg,
            by_test_type=by_tt,
            by_coverage_status=by_cs,
            by_test_framework=by_tf,
            low_coverage_modules=low,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        tt_dist: dict[str, int] = {}
        for r in self._records:
            k = r.test_type.value
            tt_dist[k] = tt_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "test_type_distribution": tt_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("iac_test_coverage_analyzer.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_test_coverage_ratio(
        self,
    ) -> list[dict[str, Any]]:
        """Compute test coverage ratio per module."""
        module_data: dict[str, list[float]] = {}
        for r in self._records:
            module_data.setdefault(r.module_id, []).append(r.coverage_pct)
        results: list[dict[str, Any]] = []
        for mid, coverages in module_data.items():
            avg = round(sum(coverages) / len(coverages), 2)
            results.append(
                {
                    "module_id": mid,
                    "avg_coverage": avg,
                    "test_count": len(coverages),
                }
            )
        results.sort(
            key=lambda x: x["avg_coverage"],
            reverse=True,
        )
        return results

    def detect_untested_resources(
        self,
    ) -> list[dict[str, Any]]:
        """Detect untested resources."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            untested = r.total_resources - r.tested_resources
            if untested > 0 and r.module_id not in seen:
                seen.add(r.module_id)
                results.append(
                    {
                        "module_id": r.module_id,
                        "module_name": r.module_name,
                        "untested_count": untested,
                        "total_resources": (r.total_resources),
                        "coverage_pct": (r.coverage_pct),
                    }
                )
        results.sort(
            key=lambda x: x["untested_count"],
            reverse=True,
        )
        return results

    def rank_modules_by_testing_gaps(
        self,
    ) -> list[dict[str, Any]]:
        """Rank modules by testing gaps."""
        module_gaps: dict[str, float] = {}
        for r in self._records:
            gap = 100.0 - r.coverage_pct
            module_gaps[r.module_id] = module_gaps.get(r.module_id, 0.0) + gap
        results: list[dict[str, Any]] = []
        for mid, total in module_gaps.items():
            results.append(
                {
                    "module_id": mid,
                    "gap_score": round(total, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["gap_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
