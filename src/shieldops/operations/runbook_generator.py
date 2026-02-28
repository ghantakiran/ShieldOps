"""Runbook Generator — AI-generate runbooks from incident patterns."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RunbookSource(StrEnum):
    INCIDENT_PATTERN = "incident_pattern"
    HISTORICAL_RESOLUTION = "historical_resolution"
    BEST_PRACTICE = "best_practice"
    TEMPLATE = "template"
    MANUAL_INPUT = "manual_input"


class RunbookQuality(StrEnum):
    PRODUCTION_READY = "production_ready"
    REVIEWED = "reviewed"
    DRAFT = "draft"
    NEEDS_REVISION = "needs_revision"
    OBSOLETE = "obsolete"


class RunbookScope(StrEnum):
    SERVICE_SPECIFIC = "service_specific"
    TEAM_WIDE = "team_wide"
    PLATFORM_WIDE = "platform_wide"
    CROSS_TEAM = "cross_team"
    EMERGENCY = "emergency"


# --- Models ---


class GeneratedRunbook(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_name: str = ""
    source: RunbookSource = RunbookSource.INCIDENT_PATTERN
    quality: RunbookQuality = RunbookQuality.DRAFT
    scope: RunbookScope = RunbookScope.SERVICE_SPECIFIC
    accuracy_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class GenerationRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    source: RunbookSource = RunbookSource.INCIDENT_PATTERN
    scope: RunbookScope = RunbookScope.SERVICE_SPECIFIC
    min_incidents: int = 3
    auto_generate: bool = True
    created_at: float = Field(default_factory=time.time)


class RunbookGeneratorReport(BaseModel):
    total_runbooks: int = 0
    total_rules: int = 0
    production_ready_rate_pct: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_quality: dict[str, int] = Field(default_factory=dict)
    obsolete_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class OperationalRunbookGenerator:
    """AI-generate runbooks from incident patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        min_accuracy_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_accuracy_pct = min_accuracy_pct
        self._records: list[GeneratedRunbook] = []
        self._rules: list[GenerationRule] = []
        logger.info(
            "runbook_generator.initialized",
            max_records=max_records,
            min_accuracy_pct=min_accuracy_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_runbook(
        self,
        runbook_name: str,
        source: RunbookSource = (RunbookSource.INCIDENT_PATTERN),
        quality: RunbookQuality = RunbookQuality.DRAFT,
        scope: RunbookScope = (RunbookScope.SERVICE_SPECIFIC),
        accuracy_score: float = 0.0,
        details: str = "",
    ) -> GeneratedRunbook:
        record = GeneratedRunbook(
            runbook_name=runbook_name,
            source=source,
            quality=quality,
            scope=scope,
            accuracy_score=accuracy_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "runbook_generator.runbook_recorded",
            record_id=record.id,
            runbook_name=runbook_name,
            source=source.value,
            quality=quality.value,
        )
        return record

    def get_runbook(self, record_id: str) -> GeneratedRunbook | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_runbooks(
        self,
        runbook_name: str | None = None,
        source: RunbookSource | None = None,
        limit: int = 50,
    ) -> list[GeneratedRunbook]:
        results = list(self._records)
        if runbook_name is not None:
            results = [r for r in results if r.runbook_name == runbook_name]
        if source is not None:
            results = [r for r in results if r.source == source]
        return results[-limit:]

    def add_rule(
        self,
        rule_name: str,
        source: RunbookSource = (RunbookSource.INCIDENT_PATTERN),
        scope: RunbookScope = (RunbookScope.SERVICE_SPECIFIC),
        min_incidents: int = 3,
        auto_generate: bool = True,
    ) -> GenerationRule:
        rule = GenerationRule(
            rule_name=rule_name,
            source=source,
            scope=scope,
            min_incidents=min_incidents,
            auto_generate=auto_generate,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "runbook_generator.rule_added",
            rule_name=rule_name,
            source=source.value,
            scope=scope.value,
        )
        return rule

    # -- domain operations -------------------------------------------

    def analyze_runbook_quality(self, runbook_name: str) -> dict[str, Any]:
        """Analyze runbook quality for a name."""
        records = [r for r in self._records if r.runbook_name == runbook_name]
        if not records:
            return {
                "runbook_name": runbook_name,
                "status": "no_data",
            }
        ready = sum(1 for r in records if r.quality == RunbookQuality.PRODUCTION_READY)
        ready_rate = round(ready / len(records) * 100, 2)
        avg_accuracy = round(
            sum(r.accuracy_score for r in records) / len(records),
            2,
        )
        return {
            "runbook_name": runbook_name,
            "runbook_count": len(records),
            "ready_count": ready,
            "ready_rate": ready_rate,
            "avg_accuracy": avg_accuracy,
            "meets_threshold": (avg_accuracy >= self._min_accuracy_pct),
        }

    def identify_obsolete_runbooks(
        self,
    ) -> list[dict[str, Any]]:
        """Find runbooks with repeated obsolete status."""
        obs_counts: dict[str, int] = {}
        for r in self._records:
            if r.quality in (
                RunbookQuality.OBSOLETE,
                RunbookQuality.NEEDS_REVISION,
            ):
                obs_counts[r.runbook_name] = obs_counts.get(r.runbook_name, 0) + 1
        results: list[dict[str, Any]] = []
        for name, count in obs_counts.items():
            if count > 1:
                results.append(
                    {
                        "runbook_name": name,
                        "obsolete_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["obsolete_count"],
            reverse=True,
        )
        return results

    def rank_by_accuracy(
        self,
    ) -> list[dict[str, Any]]:
        """Rank runbooks by avg accuracy descending."""
        totals: dict[str, list[float]] = {}
        for r in self._records:
            totals.setdefault(r.runbook_name, []).append(r.accuracy_score)
        results: list[dict[str, Any]] = []
        for name, scores in totals.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "runbook_name": name,
                    "avg_accuracy": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_accuracy"],
            reverse=True,
        )
        return results

    def detect_quality_gaps(
        self,
    ) -> list[dict[str, Any]]:
        """Detect runbooks >3 non-PRODUCTION_READY/REVIEWED."""
        name_bad: dict[str, int] = {}
        for r in self._records:
            if r.quality not in (
                RunbookQuality.PRODUCTION_READY,
                RunbookQuality.REVIEWED,
            ):
                name_bad[r.runbook_name] = name_bad.get(r.runbook_name, 0) + 1
        results: list[dict[str, Any]] = []
        for name, count in name_bad.items():
            if count > 3:
                results.append(
                    {
                        "runbook_name": name,
                        "gap_count": count,
                        "gap_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["gap_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(
        self,
    ) -> RunbookGeneratorReport:
        by_source: dict[str, int] = {}
        by_quality: dict[str, int] = {}
        for r in self._records:
            by_source[r.source.value] = by_source.get(r.source.value, 0) + 1
            by_quality[r.quality.value] = by_quality.get(r.quality.value, 0) + 1
        ready_count = sum(1 for r in self._records if r.quality == RunbookQuality.PRODUCTION_READY)
        ready_rate = (
            round(
                ready_count / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        obsolete_count = sum(1 for r in self._records if r.quality == RunbookQuality.OBSOLETE)
        obs_names = len(self.identify_obsolete_runbooks())
        recs: list[str] = []
        if ready_rate < 50.0:
            recs.append(f"Production-ready rate {ready_rate}% is below 50.0% threshold")
        if obs_names > 0:
            recs.append(f"{obs_names} runbook(s) with obsolete status")
        gaps = len(self.detect_quality_gaps())
        if gaps > 0:
            recs.append(f"{gaps} runbook(s) with quality gaps")
        if not recs:
            recs.append("Runbook generation quality is healthy")
        return RunbookGeneratorReport(
            total_runbooks=len(self._records),
            total_rules=len(self._rules),
            production_ready_rate_pct=ready_rate,
            by_source=by_source,
            by_quality=by_quality,
            obsolete_count=obsolete_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("runbook_generator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        source_dist: dict[str, int] = {}
        for r in self._records:
            key = r.source.value
            source_dist[key] = source_dist.get(key, 0) + 1
        return {
            "total_runbooks": len(self._records),
            "total_rules": len(self._rules),
            "min_accuracy_pct": (self._min_accuracy_pct),
            "source_distribution": source_dist,
            "unique_runbooks": len({r.runbook_name for r in self._records}),
        }
