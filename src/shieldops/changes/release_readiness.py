"""Release Readiness Checker — evaluate release readiness across quality gates."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReadinessCategory(StrEnum):
    TEST_COVERAGE = "test_coverage"
    SECURITY_SCAN = "security_scan"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"
    ROLLBACK_PLAN = "rollback_plan"


class ReadinessStatus(StrEnum):
    READY = "ready"
    CONDITIONAL = "conditional"
    NOT_READY = "not_ready"
    BLOCKED = "blocked"
    WAIVED = "waived"


class CheckPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"


# --- Models ---


class ReadinessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    release_name: str = ""
    category: ReadinessCategory = ReadinessCategory.TEST_COVERAGE
    status: ReadinessStatus = ReadinessStatus.READY
    priority: CheckPriority = CheckPriority.CRITICAL
    score_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ReadinessCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    check_name: str = ""
    category: ReadinessCategory = ReadinessCategory.TEST_COVERAGE
    status: ReadinessStatus = ReadinessStatus.READY
    min_required_score_pct: float = 0.0
    is_blocking: bool = True
    created_at: float = Field(default_factory=time.time)


class ReleaseReadinessReport(BaseModel):
    total_readiness_checks: int = 0
    total_checks: int = 0
    ready_rate_pct: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    blocker_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ReleaseReadinessChecker:
    """Evaluate release readiness across quality gates."""

    def __init__(
        self,
        max_records: int = 200000,
        min_score_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_score_pct = min_score_pct
        self._records: list[ReadinessRecord] = []
        self._checks: list[ReadinessCheck] = []
        logger.info(
            "release_readiness.initialized",
            max_records=max_records,
            min_score_pct=min_score_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_readiness(
        self,
        release_name: str,
        category: ReadinessCategory = ReadinessCategory.TEST_COVERAGE,
        status: ReadinessStatus = ReadinessStatus.READY,
        priority: CheckPriority = CheckPriority.CRITICAL,
        score_pct: float = 0.0,
        details: str = "",
    ) -> ReadinessRecord:
        record = ReadinessRecord(
            release_name=release_name,
            category=category,
            status=status,
            priority=priority,
            score_pct=score_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "release_readiness.readiness_recorded",
            record_id=record.id,
            release_name=release_name,
            category=category.value,
            status=status.value,
        )
        return record

    def get_readiness(self, record_id: str) -> ReadinessRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_readiness_checks(
        self,
        release_name: str | None = None,
        category: ReadinessCategory | None = None,
        limit: int = 50,
    ) -> list[ReadinessRecord]:
        results = list(self._records)
        if release_name is not None:
            results = [r for r in results if r.release_name == release_name]
        if category is not None:
            results = [r for r in results if r.category == category]
        return results[-limit:]

    def add_check(
        self,
        check_name: str,
        category: ReadinessCategory = ReadinessCategory.TEST_COVERAGE,
        status: ReadinessStatus = ReadinessStatus.READY,
        min_required_score_pct: float = 0.0,
        is_blocking: bool = True,
    ) -> ReadinessCheck:
        check = ReadinessCheck(
            check_name=check_name,
            category=category,
            status=status,
            min_required_score_pct=min_required_score_pct,
            is_blocking=is_blocking,
        )
        self._checks.append(check)
        if len(self._checks) > self._max_records:
            self._checks = self._checks[-self._max_records :]
        logger.info(
            "release_readiness.check_added",
            check_name=check_name,
            category=category.value,
            status=status.value,
        )
        return check

    # -- domain operations -----------------------------------------------

    def analyze_release_readiness(self, release_name: str) -> dict[str, Any]:
        """Analyze readiness for a specific release."""
        records = [r for r in self._records if r.release_name == release_name]
        if not records:
            return {"release_name": release_name, "status": "no_data"}
        avg_score = round(sum(r.score_pct for r in records) / len(records), 2)
        return {
            "release_name": release_name,
            "avg_score": avg_score,
            "record_count": len(records),
            "meets_threshold": avg_score >= self._min_score_pct,
        }

    def identify_blockers(self) -> list[dict[str, Any]]:
        """Find releases with >1 BLOCKED or NOT_READY status."""
        blocker_counts: dict[str, int] = {}
        for r in self._records:
            if r.status in (ReadinessStatus.BLOCKED, ReadinessStatus.NOT_READY):
                blocker_counts[r.release_name] = blocker_counts.get(r.release_name, 0) + 1
        results: list[dict[str, Any]] = []
        for rel, count in blocker_counts.items():
            if count > 1:
                results.append(
                    {
                        "release_name": rel,
                        "blocker_count": count,
                    }
                )
        results.sort(key=lambda x: x["blocker_count"], reverse=True)
        return results

    def rank_by_readiness_score(self) -> list[dict[str, Any]]:
        """Rank releases by avg score_pct descending."""
        scores: dict[str, list[float]] = {}
        for r in self._records:
            scores.setdefault(r.release_name, []).append(r.score_pct)
        results: list[dict[str, Any]] = []
        for rel, sc in scores.items():
            avg = round(sum(sc) / len(sc), 2)
            results.append(
                {
                    "release_name": rel,
                    "avg_score_pct": avg,
                }
            )
        results.sort(key=lambda x: x["avg_score_pct"], reverse=True)
        return results

    def detect_readiness_trends(self) -> list[dict[str, Any]]:
        """Detect releases with >3 records."""
        counts: dict[str, int] = {}
        for r in self._records:
            counts[r.release_name] = counts.get(r.release_name, 0) + 1
        results: list[dict[str, Any]] = []
        for rel, count in counts.items():
            if count > 3:
                results.append(
                    {
                        "release_name": rel,
                        "record_count": count,
                        "trend_detected": True,
                    }
                )
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ReleaseReadinessReport:
        by_category: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        ready_count = sum(1 for r in self._records if r.status == ReadinessStatus.READY)
        ready_rate = round(ready_count / len(self._records) * 100, 2) if self._records else 0.0
        blocker_count = len(self.identify_blockers())
        recs: list[str] = []
        if self._records and ready_rate < self._min_score_pct:
            recs.append(f"Ready rate {ready_rate}% is below {self._min_score_pct}% threshold")
        if blocker_count > 0:
            recs.append(f"{blocker_count} release(s) with blockers")
        trends = len(self.detect_readiness_trends())
        if trends > 0:
            recs.append(f"{trends} release(s) with detected trends")
        if not recs:
            recs.append("Release readiness meets targets")
        return ReleaseReadinessReport(
            total_readiness_checks=len(self._records),
            total_checks=len(self._checks),
            ready_rate_pct=ready_rate,
            by_category=by_category,
            by_status=by_status,
            blocker_count=blocker_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._checks.clear()
        logger.info("release_readiness.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_readiness_checks": len(self._records),
            "total_checks": len(self._checks),
            "min_score_pct": self._min_score_pct,
            "category_distribution": category_dist,
            "unique_releases": len({r.release_name for r in self._records}),
        }
