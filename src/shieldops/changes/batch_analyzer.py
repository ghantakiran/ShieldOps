"""Change Batch Analyzer — analyze risk and conflicts across change batches."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BatchRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    SAFE = "safe"


class BatchType(StrEnum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    MIXED = "mixed"
    ATOMIC = "atomic"
    PHASED = "phased"


class ConflictType(StrEnum):
    RESOURCE = "resource"
    DEPENDENCY = "dependency"
    TIMING = "timing"
    CONFIGURATION = "configuration"
    SCHEMA = "schema"


# --- Models ---


class BatchRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    batch_name: str = ""
    batch_type: BatchType = BatchType.SEQUENTIAL
    risk: BatchRisk = BatchRisk.LOW
    change_count: int = 0
    risk_score: float = 0.0
    team: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class BatchConflict(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    batch_id: str = ""
    conflict_type: ConflictType = ConflictType.RESOURCE
    severity: BatchRisk = BatchRisk.LOW
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ChangeBatchReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_conflicts: int = 0
    avg_risk_score: float = 0.0
    high_risk_batches: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    risky_teams: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeBatchAnalyzer:
    """Analyze risk profiles, conflicts, and trends across change batches."""

    def __init__(
        self,
        max_records: int = 200000,
        max_batch_risk_score: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._max_batch_risk_score = max_batch_risk_score
        self._records: list[BatchRecord] = []
        self._conflicts: list[BatchConflict] = []
        logger.info(
            "batch_analyzer.initialized",
            max_records=max_records,
            max_batch_risk_score=max_batch_risk_score,
        )

    # -- record / get / list ---------------------------------------------

    def record_batch(
        self,
        batch_name: str,
        batch_type: BatchType = BatchType.SEQUENTIAL,
        risk: BatchRisk = BatchRisk.LOW,
        change_count: int = 0,
        risk_score: float = 0.0,
        team: str = "",
        details: str = "",
    ) -> BatchRecord:
        record = BatchRecord(
            batch_name=batch_name,
            batch_type=batch_type,
            risk=risk,
            change_count=change_count,
            risk_score=risk_score,
            team=team,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "batch_analyzer.batch_recorded",
            record_id=record.id,
            batch_name=batch_name,
            batch_type=batch_type.value,
            risk=risk.value,
            risk_score=risk_score,
        )
        return record

    def get_batch(self, record_id: str) -> BatchRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_batches(
        self,
        batch_type: BatchType | None = None,
        risk: BatchRisk | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[BatchRecord]:
        results = list(self._records)
        if batch_type is not None:
            results = [r for r in results if r.batch_type == batch_type]
        if risk is not None:
            results = [r for r in results if r.risk == risk]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_conflict(
        self,
        batch_id: str,
        conflict_type: ConflictType = ConflictType.RESOURCE,
        severity: BatchRisk = BatchRisk.LOW,
        description: str = "",
    ) -> BatchConflict:
        conflict = BatchConflict(
            batch_id=batch_id,
            conflict_type=conflict_type,
            severity=severity,
            description=description,
        )
        self._conflicts.append(conflict)
        if len(self._conflicts) > self._max_records:
            self._conflicts = self._conflicts[-self._max_records :]
        logger.info(
            "batch_analyzer.conflict_added",
            conflict_id=conflict.id,
            batch_id=batch_id,
            conflict_type=conflict_type.value,
            severity=severity.value,
        )
        return conflict

    # -- domain operations -----------------------------------------------

    def analyze_batch_risk(self) -> list[dict[str, Any]]:
        """Group batches by type, compute avg risk_score and count."""
        type_map: dict[str, list[float]] = {}
        for r in self._records:
            type_map.setdefault(r.batch_type.value, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for btype, scores in type_map.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append({"batch_type": btype, "count": len(scores), "avg_risk_score": avg})
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def identify_high_risk_batches(self) -> list[dict[str, Any]]:
        """Find batches where risk_score exceeds max_batch_risk_score."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score > self._max_batch_risk_score:
                results.append(
                    {
                        "batch_id": r.id,
                        "batch_name": r.batch_name,
                        "team": r.team,
                        "risk_score": r.risk_score,
                        "risk": r.risk.value,
                    }
                )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Group by team, average risk_score, sort descending."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append({"team": team, "avg_risk_score": avg, "batch_count": len(scores)})
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def detect_batch_trends(self) -> list[dict[str, Any]]:
        """Split records in half; flag teams where delta risk_score > 5.0."""
        if len(self._records) < 2:
            return []
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]

        def avg_score(recs: list[BatchRecord], team: str) -> float:
            subset = [r.risk_score for r in recs if r.team == team]
            return sum(subset) / len(subset) if subset else 0.0

        teams = {r.team for r in self._records}
        results: list[dict[str, Any]] = []
        for team in teams:
            early = avg_score(first_half, team)
            late = avg_score(second_half, team)
            delta = round(late - early, 2)
            if abs(delta) > 5.0:
                results.append(
                    {
                        "team": team,
                        "early_avg": round(early, 2),
                        "late_avg": round(late, 2),
                        "delta": delta,
                        "trend": "worsening" if delta > 0 else "improving",
                    }
                )
        results.sort(key=lambda x: abs(x["delta"]), reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ChangeBatchReport:
        by_type: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_type[r.batch_type.value] = by_type.get(r.batch_type.value, 0) + 1
            by_risk[r.risk.value] = by_risk.get(r.risk.value, 0) + 1
        avg_score = (
            round(sum(r.risk_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        high_risk = [r for r in self._records if r.risk_score > self._max_batch_risk_score]
        risky_teams = list({r.team for r in high_risk if r.team})
        recs: list[str] = []
        if high_risk:
            recs.append(f"{len(high_risk)} batch(es) exceed risk score threshold")
        conflict_count = len(self._conflicts)
        if conflict_count > 0:
            recs.append(f"{conflict_count} conflict(s) detected across batches")
        if not recs:
            recs.append("All batches within acceptable risk thresholds")
        return ChangeBatchReport(
            total_records=len(self._records),
            total_conflicts=len(self._conflicts),
            avg_risk_score=avg_score,
            high_risk_batches=len(high_risk),
            by_type=by_type,
            by_risk=by_risk,
            risky_teams=risky_teams,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._conflicts.clear()
        logger.info("batch_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        risk_dist: dict[str, int] = {}
        for r in self._records:
            key = r.risk.value
            risk_dist[key] = risk_dist.get(key, 0) + 1
        return {
            "total_batches": len(self._records),
            "total_conflicts": len(self._conflicts),
            "max_batch_risk_score": self._max_batch_risk_score,
            "risk_distribution": risk_dist,
            "unique_teams": len({r.team for r in self._records}),
        }
