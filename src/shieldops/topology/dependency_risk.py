"""Dependency Risk Scorer — score dependency failure risk and track mitigations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RiskFactor(StrEnum):
    VERSION_LAG = "version_lag"
    SINGLE_MAINTAINER = "single_maintainer"
    NO_FALLBACK = "no_fallback"
    HIGH_BLAST_RADIUS = "high_blast_radius"
    TRANSITIVE_DEPTH = "transitive_depth"


class RiskTier(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    ACCEPTABLE = "acceptable"


class MitigationStatus(StrEnum):
    UNMITIGATED = "unmitigated"
    IN_PROGRESS = "in_progress"
    PARTIALLY_MITIGATED = "partially_mitigated"
    FULLY_MITIGATED = "fully_mitigated"
    ACCEPTED = "accepted"


# --- Models ---


class DependencyRiskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dependency_name: str = ""
    risk_factor: RiskFactor = RiskFactor.VERSION_LAG
    risk_tier: RiskTier = RiskTier.MODERATE
    risk_score: float = 0.0
    mitigation_status: MitigationStatus = MitigationStatus.UNMITIGATED
    affected_services_count: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskMitigation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dependency_name: str = ""
    mitigation_name: str = ""
    status: MitigationStatus = MitigationStatus.IN_PROGRESS
    effectiveness_pct: float = 0.0
    notes: str = ""
    created_at: float = Field(default_factory=time.time)


class DependencyRiskReport(BaseModel):
    total_risks: int = 0
    total_mitigations: int = 0
    avg_risk_score: float = 0.0
    by_risk_factor: dict[str, int] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)
    critical_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DependencyRiskScorer:
    """Score dependency failure risk and track mitigations."""

    def __init__(
        self,
        max_records: int = 200000,
        critical_threshold: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._critical_threshold = critical_threshold
        self._records: list[DependencyRiskRecord] = []
        self._mitigations: list[RiskMitigation] = []
        logger.info(
            "dependency_risk.initialized",
            max_records=max_records,
            critical_threshold=critical_threshold,
        )

    # -- internal helpers ------------------------------------------------

    def _score_to_tier(self, score: float) -> RiskTier:
        if score >= 90:
            return RiskTier.CRITICAL
        if score >= 70:
            return RiskTier.HIGH
        if score >= 50:
            return RiskTier.MODERATE
        if score >= 30:
            return RiskTier.LOW
        return RiskTier.ACCEPTABLE

    # -- record / get / list ---------------------------------------------

    def record_risk(
        self,
        dependency_name: str,
        risk_factor: RiskFactor = RiskFactor.VERSION_LAG,
        risk_tier: RiskTier | None = None,
        risk_score: float = 0.0,
        mitigation_status: MitigationStatus = MitigationStatus.UNMITIGATED,
        affected_services_count: int = 0,
        details: str = "",
    ) -> DependencyRiskRecord:
        if risk_tier is None:
            risk_tier = self._score_to_tier(risk_score)
        record = DependencyRiskRecord(
            dependency_name=dependency_name,
            risk_factor=risk_factor,
            risk_tier=risk_tier,
            risk_score=risk_score,
            mitigation_status=mitigation_status,
            affected_services_count=affected_services_count,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dependency_risk.risk_recorded",
            record_id=record.id,
            dependency_name=dependency_name,
            risk_tier=risk_tier.value,
        )
        return record

    def get_risk(self, record_id: str) -> DependencyRiskRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_risks(
        self,
        dependency_name: str | None = None,
        risk_factor: RiskFactor | None = None,
        limit: int = 50,
    ) -> list[DependencyRiskRecord]:
        results = list(self._records)
        if dependency_name is not None:
            results = [r for r in results if r.dependency_name == dependency_name]
        if risk_factor is not None:
            results = [r for r in results if r.risk_factor == risk_factor]
        return results[-limit:]

    def record_mitigation(
        self,
        dependency_name: str,
        mitigation_name: str,
        status: MitigationStatus = MitigationStatus.IN_PROGRESS,
        effectiveness_pct: float = 0.0,
        notes: str = "",
    ) -> RiskMitigation:
        mit = RiskMitigation(
            dependency_name=dependency_name,
            mitigation_name=mitigation_name,
            status=status,
            effectiveness_pct=effectiveness_pct,
            notes=notes,
        )
        self._mitigations.append(mit)
        if len(self._mitigations) > self._max_records:
            self._mitigations = self._mitigations[-self._max_records :]
        logger.info(
            "dependency_risk.mitigation_recorded",
            dependency_name=dependency_name,
            mitigation_name=mitigation_name,
        )
        return mit

    # -- domain operations -----------------------------------------------

    def analyze_dependency_risk(self, dependency_name: str) -> dict[str, Any]:
        """Analyze risk for a specific dependency."""
        records = [r for r in self._records if r.dependency_name == dependency_name]
        if not records:
            return {
                "dependency_name": dependency_name,
                "status": "no_data",
            }
        latest = records[-1]
        return {
            "dependency_name": dependency_name,
            "risk_factor": latest.risk_factor.value,
            "risk_tier": latest.risk_tier.value,
            "risk_score": latest.risk_score,
            "mitigation_status": latest.mitigation_status.value,
        }

    def identify_critical_risks(self) -> list[dict[str, Any]]:
        """Find dependencies with critical/high risk tier."""
        critical = {RiskTier.CRITICAL, RiskTier.HIGH}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_tier in critical:
                results.append(
                    {
                        "dependency_name": r.dependency_name,
                        "risk_factor": r.risk_factor.value,
                        "risk_tier": r.risk_tier.value,
                        "risk_score": r.risk_score,
                    }
                )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Rank dependencies by risk score descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "dependency_name": r.dependency_name,
                    "risk_score": r.risk_score,
                    "risk_tier": r.risk_tier.value,
                    "mitigation_status": r.mitigation_status.value,
                }
            )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def detect_unmitigated_risks(self) -> list[dict[str, Any]]:
        """Detect unmitigated high-risk dependencies."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if (
                r.mitigation_status == MitigationStatus.UNMITIGATED
                and r.risk_score >= self._critical_threshold
            ):
                results.append(
                    {
                        "dependency_name": r.dependency_name,
                        "risk_score": r.risk_score,
                        "risk_tier": r.risk_tier.value,
                        "risk_factor": r.risk_factor.value,
                    }
                )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> DependencyRiskReport:
        by_factor: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        for r in self._records:
            by_factor[r.risk_factor.value] = by_factor.get(r.risk_factor.value, 0) + 1
            by_tier[r.risk_tier.value] = by_tier.get(r.risk_tier.value, 0) + 1
        avg_score = (
            round(
                sum(r.risk_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        critical = {RiskTier.CRITICAL, RiskTier.HIGH}
        critical_count = sum(1 for r in self._records if r.risk_tier in critical)
        recs: list[str] = []
        if critical_count > 0:
            recs.append(f"{critical_count} critical/high risk dependency(ies)")
        unmitigated = sum(
            1
            for r in self._records
            if r.mitigation_status == MitigationStatus.UNMITIGATED
            and r.risk_score >= self._critical_threshold
        )
        if unmitigated > 0:
            recs.append(f"{unmitigated} unmitigated high-risk dependency(ies)")
        if not recs:
            recs.append("Dependency risk within acceptable limits")
        return DependencyRiskReport(
            total_risks=len(self._records),
            total_mitigations=len(self._mitigations),
            avg_risk_score=avg_score,
            by_risk_factor=by_factor,
            by_tier=by_tier,
            critical_count=critical_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._mitigations.clear()
        logger.info("dependency_risk.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        factor_dist: dict[str, int] = {}
        for r in self._records:
            key = r.risk_factor.value
            factor_dist[key] = factor_dist.get(key, 0) + 1
        return {
            "total_risks": len(self._records),
            "total_mitigations": len(self._mitigations),
            "critical_threshold": self._critical_threshold,
            "risk_factor_distribution": factor_dist,
            "unique_dependencies": len({r.dependency_name for r in self._records}),
        }
