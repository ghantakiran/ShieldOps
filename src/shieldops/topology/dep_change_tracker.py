"""Dependency Change Tracker — track dependency changes, risk, and breaking changes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ChangeType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    VERSION_BUMP = "version_bump"
    CONFIG_CHANGE = "config_change"
    DEPRECATED = "deprecated"


class ChangeImpact(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BREAKING = "breaking"


class ChangeStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


# --- Models ---


class DepChangeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dependency_name: str = ""
    change_type: ChangeType = ChangeType.ADDED
    change_impact: ChangeImpact = ChangeImpact.NONE
    change_status: ChangeStatus = ChangeStatus.PENDING
    risk_score: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DepChangeRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dependency_pattern: str = ""
    change_type: ChangeType = ChangeType.ADDED
    max_risk_score: float = 0.0
    auto_approve: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DepChangeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_rules: int = 0
    breaking_changes: int = 0
    avg_risk_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    high_risk: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DependencyChangeTracker:
    """Track dependency changes, identify breaking changes, assess risk."""

    def __init__(
        self,
        max_records: int = 200000,
        max_breaking_change_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_breaking_change_pct = max_breaking_change_pct
        self._records: list[DepChangeRecord] = []
        self._rules: list[DepChangeRule] = []
        logger.info(
            "dep_change_tracker.initialized",
            max_records=max_records,
            max_breaking_change_pct=max_breaking_change_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_change(
        self,
        dependency_name: str,
        change_type: ChangeType = ChangeType.ADDED,
        change_impact: ChangeImpact = ChangeImpact.NONE,
        change_status: ChangeStatus = ChangeStatus.PENDING,
        risk_score: float = 0.0,
        team: str = "",
    ) -> DepChangeRecord:
        record = DepChangeRecord(
            dependency_name=dependency_name,
            change_type=change_type,
            change_impact=change_impact,
            change_status=change_status,
            risk_score=risk_score,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dep_change_tracker.change_recorded",
            record_id=record.id,
            dependency_name=dependency_name,
            change_type=change_type.value,
            change_impact=change_impact.value,
        )
        return record

    def get_change(self, record_id: str) -> DepChangeRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_changes(
        self,
        change_type: ChangeType | None = None,
        impact: ChangeImpact | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DepChangeRecord]:
        results = list(self._records)
        if change_type is not None:
            results = [r for r in results if r.change_type == change_type]
        if impact is not None:
            results = [r for r in results if r.change_impact == impact]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_rule(
        self,
        dependency_pattern: str,
        change_type: ChangeType = ChangeType.ADDED,
        max_risk_score: float = 0.0,
        auto_approve: bool = False,
        description: str = "",
    ) -> DepChangeRule:
        rule = DepChangeRule(
            dependency_pattern=dependency_pattern,
            change_type=change_type,
            max_risk_score=max_risk_score,
            auto_approve=auto_approve,
            description=description,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "dep_change_tracker.rule_added",
            dependency_pattern=dependency_pattern,
            change_type=change_type.value,
            max_risk_score=max_risk_score,
        )
        return rule

    # -- domain operations --------------------------------------------------

    def analyze_change_patterns(self) -> dict[str, Any]:
        """Group by change_type; return count and avg risk_score per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.change_type.value
            type_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for ctype, scores in type_data.items():
            result[ctype] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_breaking_changes(self) -> list[dict[str, Any]]:
        """Return records where impact == BREAKING."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.change_impact == ChangeImpact.BREAKING:
                results.append(
                    {
                        "record_id": r.id,
                        "dependency_name": r.dependency_name,
                        "change_type": r.change_type.value,
                        "risk_score": r.risk_score,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Group by team, avg risk_score, sort descending."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            results.append(
                {
                    "team": team,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                    "count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def detect_change_trends(self) -> dict[str, Any]:
        """Split-half on max_risk_score; delta threshold 5.0."""
        if len(self._rules) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [ru.max_risk_score for ru in self._rules]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> DepChangeReport:
        by_type: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.change_type.value] = by_type.get(r.change_type.value, 0) + 1
            by_impact[r.change_impact.value] = by_impact.get(r.change_impact.value, 0) + 1
            by_status[r.change_status.value] = by_status.get(r.change_status.value, 0) + 1
        breaking_count = sum(1 for r in self._records if r.change_impact == ChangeImpact.BREAKING)
        breaking_pct = round(breaking_count / len(self._records) * 100, 2) if self._records else 0.0
        avg_risk = (
            round(sum(r.risk_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_risk_score()
        high_risk = [rk["team"] for rk in rankings[:5]]
        recs: list[str] = []
        if breaking_pct > self._max_breaking_change_pct:
            recs.append(
                f"Breaking change rate {breaking_pct}% exceeds "
                f"threshold ({self._max_breaking_change_pct}%)"
            )
        if breaking_count > 0:
            recs.append(f"{breaking_count} breaking change(s) detected — review dependency updates")
        if not recs:
            recs.append("Dependency changes are within acceptable limits")
        return DepChangeReport(
            total_records=len(self._records),
            total_rules=len(self._rules),
            breaking_changes=breaking_count,
            avg_risk_score=avg_risk,
            by_type=by_type,
            by_impact=by_impact,
            by_status=by_status,
            high_risk=high_risk,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("dep_change_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.change_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "max_breaking_change_pct": self._max_breaking_change_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_dependencies": len({r.dependency_name for r in self._records}),
        }
