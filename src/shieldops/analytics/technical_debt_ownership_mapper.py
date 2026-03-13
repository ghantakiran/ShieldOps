"""Technical Debt Ownership Mapper —
map debt to owners, detect orphaned debt,
rank teams by debt burden."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DebtType(StrEnum):
    CODE = "code"
    ARCHITECTURE = "architecture"
    INFRASTRUCTURE = "infrastructure"
    DOCUMENTATION = "documentation"


class OwnershipStatus(StrEnum):
    OWNED = "owned"
    SHARED = "shared"
    ORPHANED = "orphaned"
    DISPUTED = "disputed"


class DebtAge(StrEnum):
    RECENT = "recent"
    AGING = "aging"
    LEGACY = "legacy"
    ANCIENT = "ancient"


# --- Models ---


class TechDebtRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    debt_id: str = ""
    team_id: str = ""
    debt_type: DebtType = DebtType.CODE
    ownership: OwnershipStatus = OwnershipStatus.OWNED
    age: DebtAge = DebtAge.RECENT
    severity_score: float = 0.0
    estimated_hours: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TechDebtAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_id: str = ""
    total_debt_items: int = 0
    avg_severity: float = 0.0
    orphaned_count: int = 0
    total_hours: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TechDebtReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_severity: float = 0.0
    by_debt_type: dict[str, int] = Field(default_factory=dict)
    by_ownership: dict[str, int] = Field(default_factory=dict)
    by_age: dict[str, int] = Field(default_factory=dict)
    orphaned_debts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TechnicalDebtOwnershipMapper:
    """Map debt to owners, detect orphaned debt,
    rank teams by debt burden."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TechDebtRecord] = []
        self._analyses: dict[str, TechDebtAnalysis] = {}
        logger.info(
            "technical_debt_ownership_mapper.init",
            max_records=max_records,
        )

    def add_record(
        self,
        debt_id: str = "",
        team_id: str = "",
        debt_type: DebtType = DebtType.CODE,
        ownership: OwnershipStatus = (OwnershipStatus.OWNED),
        age: DebtAge = DebtAge.RECENT,
        severity_score: float = 0.0,
        estimated_hours: float = 0.0,
        description: str = "",
    ) -> TechDebtRecord:
        record = TechDebtRecord(
            debt_id=debt_id,
            team_id=team_id,
            debt_type=debt_type,
            ownership=ownership,
            age=age,
            severity_score=severity_score,
            estimated_hours=estimated_hours,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "tech_debt.record_added",
            record_id=record.id,
            debt_id=debt_id,
        )
        return record

    def process(self, key: str) -> TechDebtAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        team_recs = [r for r in self._records if r.team_id == rec.team_id]
        scores = [r.severity_score for r in team_recs]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        orphaned = sum(1 for r in team_recs if r.ownership == OwnershipStatus.ORPHANED)
        total_h = round(
            sum(r.estimated_hours for r in team_recs),
            2,
        )
        analysis = TechDebtAnalysis(
            team_id=rec.team_id,
            total_debt_items=len(team_recs),
            avg_severity=avg,
            orphaned_count=orphaned,
            total_hours=total_h,
            description=(f"Team {rec.team_id} debt={len(team_recs)}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> TechDebtReport:
        by_dt: dict[str, int] = {}
        by_o: dict[str, int] = {}
        by_a: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.debt_type.value
            by_dt[k] = by_dt.get(k, 0) + 1
            k2 = r.ownership.value
            by_o[k2] = by_o.get(k2, 0) + 1
            k3 = r.age.value
            by_a[k3] = by_a.get(k3, 0) + 1
            scores.append(r.severity_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        orphaned = list(
            {r.debt_id for r in self._records if r.ownership == OwnershipStatus.ORPHANED}
        )[:10]
        recs: list[str] = []
        if orphaned:
            recs.append(f"{len(orphaned)} orphaned debts found")
        if not recs:
            recs.append("Tech debt ownership healthy")
        return TechDebtReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_severity=avg,
            by_debt_type=by_dt,
            by_ownership=by_o,
            by_age=by_a,
            orphaned_debts=orphaned,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dt_dist: dict[str, int] = {}
        for r in self._records:
            k = r.debt_type.value
            dt_dist[k] = dt_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "debt_type_distribution": dt_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("technical_debt_ownership_mapper.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def map_debt_to_owners(
        self,
    ) -> list[dict[str, Any]]:
        """Map debt items to owning teams."""
        team_debts: dict[str, list[str]] = {}
        team_hours: dict[str, float] = {}
        for r in self._records:
            team_debts.setdefault(r.team_id, []).append(r.debt_id)
            team_hours[r.team_id] = team_hours.get(r.team_id, 0.0) + r.estimated_hours
        results: list[dict[str, Any]] = []
        for tid, debts in team_debts.items():
            results.append(
                {
                    "team_id": tid,
                    "debt_count": len(debts),
                    "total_hours": round(team_hours.get(tid, 0.0), 2),
                    "debt_ids": debts[:10],
                }
            )
        results.sort(
            key=lambda x: x["debt_count"],
            reverse=True,
        )
        return results

    def detect_orphaned_debt(
        self,
    ) -> list[dict[str, Any]]:
        """Detect orphaned technical debt."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.ownership == OwnershipStatus.ORPHANED and r.debt_id not in seen:
                seen.add(r.debt_id)
                results.append(
                    {
                        "debt_id": r.debt_id,
                        "debt_type": (r.debt_type.value),
                        "age": r.age.value,
                        "severity": r.severity_score,
                        "estimated_hours": (r.estimated_hours),
                    }
                )
        results.sort(
            key=lambda x: x["severity"],
            reverse=True,
        )
        return results

    def rank_teams_by_debt_burden(
        self,
    ) -> list[dict[str, Any]]:
        """Rank teams by total debt burden."""
        team_burden: dict[str, float] = {}
        team_counts: dict[str, int] = {}
        for r in self._records:
            team_burden[r.team_id] = (
                team_burden.get(r.team_id, 0.0) + r.severity_score * r.estimated_hours
            )
            team_counts[r.team_id] = team_counts.get(r.team_id, 0) + 1
        results: list[dict[str, Any]] = []
        for tid, burden in team_burden.items():
            results.append(
                {
                    "team_id": tid,
                    "debt_burden": round(burden, 2),
                    "debt_count": team_counts.get(tid, 0),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["debt_burden"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
