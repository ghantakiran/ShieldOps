"""DisasterRecoveryIntelligence
DR readiness scoring, RTO/RPO tracking, failover testing, recovery plan validation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DRTier(StrEnum):
    TIER_1_CRITICAL = "tier_1_critical"
    TIER_2_IMPORTANT = "tier_2_important"
    TIER_3_STANDARD = "tier_3_standard"
    TIER_4_LOW = "tier_4_low"
    UNCLASSIFIED = "unclassified"


class RecoveryStrategy(StrEnum):
    ACTIVE_ACTIVE = "active_active"
    ACTIVE_PASSIVE = "active_passive"
    PILOT_LIGHT = "pilot_light"
    WARM_STANDBY = "warm_standby"
    BACKUP_RESTORE = "backup_restore"


class FailoverTestResult(StrEnum):
    PASSED = "passed"
    PARTIAL_PASS = "partial_pass"  # noqa: S105
    FAILED = "failed"
    NOT_TESTED = "not_tested"
    EXPIRED = "expired"


# --- Models ---


class DisasterRecoveryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    dr_tier: DRTier = DRTier.UNCLASSIFIED
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.BACKUP_RESTORE
    failover_test_result: FailoverTestResult = FailoverTestResult.NOT_TESTED
    rto_target_minutes: float = 0.0
    rto_actual_minutes: float = 0.0
    rpo_target_minutes: float = 0.0
    rpo_actual_minutes: float = 0.0
    readiness_score: float = 0.0
    last_test_days_ago: int = 0
    backup_verified: bool = False
    runbook_current: bool = False
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DisasterRecoveryAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    dr_tier: DRTier = DRTier.UNCLASSIFIED
    analysis_score: float = 0.0
    rto_compliance_rate: float = 0.0
    rpo_compliance_rate: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DisasterRecoveryReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_readiness_score: float = 0.0
    rto_compliant_count: int = 0
    rpo_compliant_count: int = 0
    untested_count: int = 0
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_test_result: dict[str, int] = Field(default_factory=dict)
    top_at_risk_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DisasterRecoveryIntelligence:
    """DR readiness scoring with RTO/RPO tracking and failover testing validation."""

    def __init__(
        self,
        max_records: int = 200000,
        readiness_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._readiness_threshold = readiness_threshold
        self._records: list[DisasterRecoveryRecord] = []
        self._analyses: list[DisasterRecoveryAnalysis] = []
        logger.info(
            "disaster.recovery.intelligence.initialized",
            max_records=max_records,
            readiness_threshold=readiness_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_item(
        self,
        name: str,
        dr_tier: DRTier = DRTier.UNCLASSIFIED,
        recovery_strategy: RecoveryStrategy = RecoveryStrategy.BACKUP_RESTORE,
        failover_test_result: FailoverTestResult = FailoverTestResult.NOT_TESTED,
        rto_target_minutes: float = 0.0,
        rto_actual_minutes: float = 0.0,
        rpo_target_minutes: float = 0.0,
        rpo_actual_minutes: float = 0.0,
        readiness_score: float = 0.0,
        last_test_days_ago: int = 0,
        backup_verified: bool = False,
        runbook_current: bool = False,
        service: str = "",
        team: str = "",
    ) -> DisasterRecoveryRecord:
        record = DisasterRecoveryRecord(
            name=name,
            dr_tier=dr_tier,
            recovery_strategy=recovery_strategy,
            failover_test_result=failover_test_result,
            rto_target_minutes=rto_target_minutes,
            rto_actual_minutes=rto_actual_minutes,
            rpo_target_minutes=rpo_target_minutes,
            rpo_actual_minutes=rpo_actual_minutes,
            readiness_score=readiness_score,
            last_test_days_ago=last_test_days_ago,
            backup_verified=backup_verified,
            runbook_current=runbook_current,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "disaster.recovery.intelligence.item_recorded",
            record_id=record.id,
            name=name,
            dr_tier=dr_tier.value,
            readiness_score=readiness_score,
        )
        return record

    def get_record(self, record_id: str) -> DisasterRecoveryRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        dr_tier: DRTier | None = None,
        failover_test_result: FailoverTestResult | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DisasterRecoveryRecord]:
        results = list(self._records)
        if dr_tier is not None:
            results = [r for r in results if r.dr_tier == dr_tier]
        if failover_test_result is not None:
            results = [r for r in results if r.failover_test_result == failover_test_result]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        dr_tier: DRTier = DRTier.UNCLASSIFIED,
        analysis_score: float = 0.0,
        rto_compliance_rate: float = 0.0,
        rpo_compliance_rate: float = 0.0,
        description: str = "",
    ) -> DisasterRecoveryAnalysis:
        analysis = DisasterRecoveryAnalysis(
            name=name,
            dr_tier=dr_tier,
            analysis_score=analysis_score,
            rto_compliance_rate=rto_compliance_rate,
            rpo_compliance_rate=rpo_compliance_rate,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "disaster.recovery.intelligence.analysis_added",
            name=name,
            dr_tier=dr_tier.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def assess_rto_rpo_compliance(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            rto_ok = (
                r.rto_actual_minutes <= r.rto_target_minutes if r.rto_target_minutes > 0 else True
            )
            rpo_ok = (
                r.rpo_actual_minutes <= r.rpo_target_minutes if r.rpo_target_minutes > 0 else True
            )
            rto_gap = max(0, r.rto_actual_minutes - r.rto_target_minutes)
            rpo_gap = max(0, r.rpo_actual_minutes - r.rpo_target_minutes)
            results.append(
                {
                    "record_id": r.id,
                    "name": r.name,
                    "service": r.service,
                    "rto_compliant": rto_ok,
                    "rpo_compliant": rpo_ok,
                    "rto_gap_minutes": round(rto_gap, 2),
                    "rpo_gap_minutes": round(rpo_gap, 2),
                    "dr_tier": r.dr_tier.value,
                }
            )
        return sorted(
            results, key=lambda x: x["rto_gap_minutes"] + x["rpo_gap_minutes"], reverse=True
        )

    def identify_stale_tests(self) -> list[dict[str, Any]]:
        stale: list[dict[str, Any]] = []
        for r in self._records:
            if r.last_test_days_ago > 90 or r.failover_test_result == FailoverTestResult.NOT_TESTED:
                stale.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "service": r.service,
                        "dr_tier": r.dr_tier.value,
                        "last_test_days_ago": r.last_test_days_ago,
                        "test_result": r.failover_test_result.value,
                    }
                )
        return sorted(stale, key=lambda x: x["last_test_days_ago"], reverse=True)

    def score_readiness_by_tier(self) -> dict[str, Any]:
        tier_data: dict[str, list[float]] = {}
        for r in self._records:
            tier_data.setdefault(r.dr_tier.value, []).append(r.readiness_score)
        result: dict[str, Any] = {}
        for tier, scores in tier_data.items():
            result[tier] = {
                "count": len(scores),
                "avg_readiness": round(sum(scores) / len(scores), 2),
                "min_readiness": round(min(scores), 2),
            }
        return result

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        avg_first = sum(vals[:mid]) / len(vals[:mid])
        avg_second = sum(vals[mid:]) / len(vals[mid:])
        delta = round(avg_second - avg_first, 2)
        trend = "stable" if abs(delta) < 5.0 else ("improving" if delta > 0 else "degrading")
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> DisasterRecoveryReport:
        by_tier: dict[str, int] = {}
        by_strat: dict[str, int] = {}
        by_test: dict[str, int] = {}
        for r in self._records:
            by_tier[r.dr_tier.value] = by_tier.get(r.dr_tier.value, 0) + 1
            by_strat[r.recovery_strategy.value] = by_strat.get(r.recovery_strategy.value, 0) + 1
            by_test[r.failover_test_result.value] = by_test.get(r.failover_test_result.value, 0) + 1
        scores = [r.readiness_score for r in self._records]
        avg_readiness = round(sum(scores) / len(scores), 2) if scores else 0.0
        rto_ok = sum(
            1
            for r in self._records
            if r.rto_target_minutes > 0 and r.rto_actual_minutes <= r.rto_target_minutes
        )
        rpo_ok = sum(
            1
            for r in self._records
            if r.rpo_target_minutes > 0 and r.rpo_actual_minutes <= r.rpo_target_minutes
        )
        untested = sum(
            1 for r in self._records if r.failover_test_result == FailoverTestResult.NOT_TESTED
        )
        at_risk = [r for r in self._records if r.readiness_score < self._readiness_threshold]
        at_risk.sort(key=lambda x: x.readiness_score)
        top_at_risk = [r.name for r in at_risk[:5]]
        recs: list[str] = []
        if untested > 0:
            recs.append(f"{untested} service(s) have never been failover tested")
        if avg_readiness < self._readiness_threshold:
            recs.append(f"Avg readiness {avg_readiness}% below {self._readiness_threshold}% target")
        stale = self.identify_stale_tests()
        if stale:
            recs.append(f"{len(stale)} service(s) have stale DR tests (>90 days)")
        no_backup = sum(1 for r in self._records if not r.backup_verified)
        if no_backup > 0:
            recs.append(f"{no_backup} service(s) have unverified backups")
        if not recs:
            recs.append("Disaster recovery posture is healthy — all services DR-ready")
        return DisasterRecoveryReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_readiness_score=avg_readiness,
            rto_compliant_count=rto_ok,
            rpo_compliant_count=rpo_ok,
            untested_count=untested,
            by_tier=by_tier,
            by_strategy=by_strat,
            by_test_result=by_test,
            top_at_risk_services=top_at_risk,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("disaster.recovery.intelligence.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        tier_dist: dict[str, int] = {}
        for r in self._records:
            tier_dist[r.dr_tier.value] = tier_dist.get(r.dr_tier.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "readiness_threshold": self._readiness_threshold,
            "tier_distribution": tier_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
