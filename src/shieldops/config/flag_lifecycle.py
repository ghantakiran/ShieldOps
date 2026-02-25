"""Feature Flag Lifecycle Manager — track flag staleness and cleanup readiness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FlagLifecycleStage(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    STALE = "stale"
    DEPRECATED = "deprecated"
    READY_FOR_REMOVAL = "ready_for_removal"


class FlagRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class CleanupReason(StrEnum):
    FULLY_ROLLED_OUT = "fully_rolled_out"
    EXPERIMENT_COMPLETE = "experiment_complete"
    NEVER_ENABLED = "never_enabled"
    ABANDONED = "abandoned"
    SUPERSEDED = "superseded"


# --- Models ---


class FlagLifecycleRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    flag_name: str = ""
    owner: str = ""
    stage: FlagLifecycleStage = FlagLifecycleStage.CREATED
    risk: FlagRisk = FlagRisk.LOW
    age_days: int = 0
    references_count: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class FlagCleanupCandidate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    flag_name: str = ""
    reason: CleanupReason = CleanupReason.FULLY_ROLLED_OUT
    risk: FlagRisk = FlagRisk.LOW
    tech_debt_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class FlagLifecycleReport(BaseModel):
    total_flags: int = 0
    total_cleanup_candidates: int = 0
    avg_age_days: float = 0.0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    stale_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class FeatureFlagLifecycleManager:
    """Track feature flag staleness, lifecycle stages, and cleanup readiness."""

    def __init__(
        self,
        max_records: int = 200000,
        stale_days_threshold: int = 90,
    ) -> None:
        self._max_records = max_records
        self._stale_days_threshold = stale_days_threshold
        self._records: list[FlagLifecycleRecord] = []
        self._candidates: list[FlagCleanupCandidate] = []
        logger.info(
            "flag_lifecycle.initialized",
            max_records=max_records,
            stale_days_threshold=stale_days_threshold,
        )

    # -- internal helpers ------------------------------------------------

    def _age_to_stage(self, age_days: int) -> FlagLifecycleStage:
        if age_days >= self._stale_days_threshold * 3:
            return FlagLifecycleStage.READY_FOR_REMOVAL
        if age_days >= self._stale_days_threshold * 2:
            return FlagLifecycleStage.DEPRECATED
        if age_days >= self._stale_days_threshold:
            return FlagLifecycleStage.STALE
        if age_days >= 7:
            return FlagLifecycleStage.ACTIVE
        return FlagLifecycleStage.CREATED

    # -- record / get / list ---------------------------------------------

    def record_flag(
        self,
        flag_name: str,
        owner: str = "",
        stage: FlagLifecycleStage | None = None,
        risk: FlagRisk = FlagRisk.LOW,
        age_days: int = 0,
        references_count: int = 0,
        details: str = "",
    ) -> FlagLifecycleRecord:
        if stage is None:
            stage = self._age_to_stage(age_days)
        record = FlagLifecycleRecord(
            flag_name=flag_name,
            owner=owner,
            stage=stage,
            risk=risk,
            age_days=age_days,
            references_count=references_count,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "flag_lifecycle.flag_recorded",
            record_id=record.id,
            flag_name=flag_name,
            stage=record.stage.value,
        )
        return record

    def get_flag(self, record_id: str) -> FlagLifecycleRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_flags(
        self,
        flag_name: str | None = None,
        stage: FlagLifecycleStage | None = None,
        limit: int = 50,
    ) -> list[FlagLifecycleRecord]:
        results = list(self._records)
        if flag_name is not None:
            results = [r for r in results if r.flag_name == flag_name]
        if stage is not None:
            results = [r for r in results if r.stage == stage]
        return results[-limit:]

    def record_cleanup_candidate(
        self,
        flag_name: str,
        reason: CleanupReason = CleanupReason.FULLY_ROLLED_OUT,
        risk: FlagRisk = FlagRisk.LOW,
        tech_debt_score: float = 0.0,
        details: str = "",
    ) -> FlagCleanupCandidate:
        candidate = FlagCleanupCandidate(
            flag_name=flag_name,
            reason=reason,
            risk=risk,
            tech_debt_score=tech_debt_score,
            details=details,
        )
        self._candidates.append(candidate)
        if len(self._candidates) > self._max_records:
            self._candidates = self._candidates[-self._max_records :]
        logger.info(
            "flag_lifecycle.cleanup_candidate_recorded",
            flag_name=flag_name,
            reason=reason.value,
        )
        return candidate

    # -- domain operations -----------------------------------------------

    def identify_stale_flags(self) -> list[dict[str, Any]]:
        """Find flags older than stale threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.age_days >= self._stale_days_threshold:
                results.append(
                    {
                        "flag_name": r.flag_name,
                        "owner": r.owner,
                        "age_days": r.age_days,
                        "stage": r.stage.value,
                        "references_count": r.references_count,
                    }
                )
        results.sort(key=lambda x: x["age_days"], reverse=True)
        return results

    def identify_cleanup_candidates(self) -> list[dict[str, Any]]:
        """Find flags ready for cleanup."""
        results: list[dict[str, Any]] = []
        for c in self._candidates:
            results.append(
                {
                    "flag_name": c.flag_name,
                    "reason": c.reason.value,
                    "risk": c.risk.value,
                    "tech_debt_score": c.tech_debt_score,
                }
            )
        results.sort(key=lambda x: x["tech_debt_score"], reverse=True)
        return results

    def calculate_tech_debt_score(self) -> dict[str, Any]:
        """Calculate overall tech debt from stale flags."""
        if not self._records:
            return {"total_flags": 0, "tech_debt_score": 0.0}
        stale = [r for r in self._records if r.age_days >= self._stale_days_threshold]
        debt_score = round(
            sum(r.age_days * r.references_count for r in stale) / max(len(self._records), 1),
            2,
        )
        return {
            "total_flags": len(self._records),
            "stale_flags": len(stale),
            "tech_debt_score": debt_score,
            "stale_pct": round((len(stale) / len(self._records)) * 100, 2),
        }

    def analyze_owner_responsibility(self) -> list[dict[str, Any]]:
        """Analyze flag ownership and cleanup responsibility."""
        owner_total: dict[str, int] = {}
        owner_stale: dict[str, int] = {}
        for r in self._records:
            if r.owner:
                owner_total[r.owner] = owner_total.get(r.owner, 0) + 1
                if r.age_days >= self._stale_days_threshold:
                    owner_stale[r.owner] = owner_stale.get(r.owner, 0) + 1
        results: list[dict[str, Any]] = []
        for owner, total in owner_total.items():
            stale = owner_stale.get(owner, 0)
            results.append(
                {
                    "owner": owner,
                    "total_flags": total,
                    "stale_flags": stale,
                    "stale_pct": round((stale / total) * 100, 2),
                }
            )
        results.sort(key=lambda x: x["stale_flags"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> FlagLifecycleReport:
        by_stage: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_stage[r.stage.value] = by_stage.get(r.stage.value, 0) + 1
            by_risk[r.risk.value] = by_risk.get(r.risk.value, 0) + 1
        avg_age = (
            round(
                sum(r.age_days for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        stale = sum(1 for r in self._records if r.age_days >= self._stale_days_threshold)
        recs: list[str] = []
        if stale > 0:
            recs.append(f"{stale} flag(s) stale (>{self._stale_days_threshold} days)")
        if self._candidates:
            recs.append(f"{len(self._candidates)} flag(s) ready for cleanup")
        if not recs:
            recs.append("Feature flag lifecycle is well-managed")
        return FlagLifecycleReport(
            total_flags=len(self._records),
            total_cleanup_candidates=len(self._candidates),
            avg_age_days=avg_age,
            by_stage=by_stage,
            by_risk=by_risk,
            stale_count=stale,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._candidates.clear()
        logger.info("flag_lifecycle.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        stage_dist: dict[str, int] = {}
        for r in self._records:
            key = r.stage.value
            stage_dist[key] = stage_dist.get(key, 0) + 1
        return {
            "total_flags": len(self._records),
            "total_cleanup_candidates": len(self._candidates),
            "stale_days_threshold": self._stale_days_threshold,
            "stage_distribution": stage_dist,
            "unique_flags": len({r.flag_name for r in self._records}),
        }
