"""EnvironmentParityEngine
Cross-environment comparison, parity scoring, deviation alerting, sync recommendations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EnvironmentType(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    DR_SITE = "dr_site"
    CANARY = "canary"


class DeviationType(StrEnum):
    VERSION_MISMATCH = "version_mismatch"
    CONFIG_DRIFT = "config_drift"
    RESOURCE_SIZING = "resource_sizing"
    FEATURE_FLAG = "feature_flag"
    DEPENDENCY_GAP = "dependency_gap"
    SECURITY_POLICY = "security_policy"


class ParityLevel(StrEnum):
    IDENTICAL = "identical"
    MINOR_DEVIATION = "minor_deviation"
    SIGNIFICANT_DEVIATION = "significant_deviation"
    CRITICAL_DEVIATION = "critical_deviation"
    INCOMPATIBLE = "incompatible"


# --- Models ---


class EnvironmentParityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    source_env: EnvironmentType = EnvironmentType.PRODUCTION
    target_env: EnvironmentType = EnvironmentType.STAGING
    deviation_type: DeviationType = DeviationType.VERSION_MISMATCH
    parity_level: ParityLevel = ParityLevel.IDENTICAL
    parity_score: float = 100.0
    deviations_found: int = 0
    source_version: str = ""
    target_version: str = ""
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EnvironmentParityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    source_env: EnvironmentType = EnvironmentType.PRODUCTION
    target_env: EnvironmentType = EnvironmentType.STAGING
    analysis_score: float = 0.0
    total_deviations: int = 0
    critical_deviations: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EnvironmentParityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_parity_score: float = 0.0
    critical_deviations: int = 0
    total_deviations: int = 0
    by_deviation_type: dict[str, int] = Field(default_factory=dict)
    by_parity_level: dict[str, int] = Field(default_factory=dict)
    by_environment_pair: dict[str, float] = Field(default_factory=dict)
    top_deviating_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class EnvironmentParityEngine:
    """Cross-environment comparison with parity scoring and deviation alerting."""

    def __init__(
        self,
        max_records: int = 200000,
        parity_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._parity_threshold = parity_threshold
        self._records: list[EnvironmentParityRecord] = []
        self._analyses: list[EnvironmentParityAnalysis] = []
        logger.info(
            "environment.parity.engine.initialized",
            max_records=max_records,
            parity_threshold=parity_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_item(
        self,
        name: str,
        source_env: EnvironmentType = EnvironmentType.PRODUCTION,
        target_env: EnvironmentType = EnvironmentType.STAGING,
        deviation_type: DeviationType = DeviationType.VERSION_MISMATCH,
        parity_level: ParityLevel = ParityLevel.IDENTICAL,
        parity_score: float = 100.0,
        deviations_found: int = 0,
        source_version: str = "",
        target_version: str = "",
        service: str = "",
        team: str = "",
    ) -> EnvironmentParityRecord:
        record = EnvironmentParityRecord(
            name=name,
            source_env=source_env,
            target_env=target_env,
            deviation_type=deviation_type,
            parity_level=parity_level,
            parity_score=parity_score,
            deviations_found=deviations_found,
            source_version=source_version,
            target_version=target_version,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "environment.parity.engine.item_recorded",
            record_id=record.id,
            name=name,
            source_env=source_env.value,
            target_env=target_env.value,
        )
        return record

    def get_record(self, record_id: str) -> EnvironmentParityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        deviation_type: DeviationType | None = None,
        parity_level: ParityLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EnvironmentParityRecord]:
        results = list(self._records)
        if deviation_type is not None:
            results = [r for r in results if r.deviation_type == deviation_type]
        if parity_level is not None:
            results = [r for r in results if r.parity_level == parity_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        source_env: EnvironmentType = EnvironmentType.PRODUCTION,
        target_env: EnvironmentType = EnvironmentType.STAGING,
        analysis_score: float = 0.0,
        total_deviations: int = 0,
        critical_deviations: int = 0,
        description: str = "",
    ) -> EnvironmentParityAnalysis:
        analysis = EnvironmentParityAnalysis(
            name=name,
            source_env=source_env,
            target_env=target_env,
            analysis_score=analysis_score,
            total_deviations=total_deviations,
            critical_deviations=critical_deviations,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "environment.parity.engine.analysis_added",
            name=name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def compare_environments(self) -> dict[str, Any]:
        pair_scores: dict[str, list[float]] = {}
        for r in self._records:
            key = f"{r.source_env.value} -> {r.target_env.value}"
            pair_scores.setdefault(key, []).append(r.parity_score)
        result: dict[str, Any] = {}
        for pair, scores in pair_scores.items():
            result[pair] = {
                "comparisons": len(scores),
                "avg_parity": round(sum(scores) / len(scores), 2),
                "min_parity": round(min(scores), 2),
            }
        return result

    def identify_critical_deviations(self) -> list[dict[str, Any]]:
        critical: list[dict[str, Any]] = []
        for r in self._records:
            if r.parity_level in (ParityLevel.CRITICAL_DEVIATION, ParityLevel.INCOMPATIBLE):
                critical.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "source_env": r.source_env.value,
                        "target_env": r.target_env.value,
                        "deviation_type": r.deviation_type.value,
                        "parity_score": r.parity_score,
                        "service": r.service,
                    }
                )
        return sorted(critical, key=lambda x: x["parity_score"])

    def recommend_sync_actions(self) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        for r in self._records:
            if r.parity_score < self._parity_threshold:
                action = (
                    "upgrade_version"
                    if r.deviation_type == DeviationType.VERSION_MISMATCH
                    else "sync_config"
                    if r.deviation_type == DeviationType.CONFIG_DRIFT
                    else "resize_resources"
                    if r.deviation_type == DeviationType.RESOURCE_SIZING
                    else "align_flags"
                    if r.deviation_type == DeviationType.FEATURE_FLAG
                    else "review_deviation"
                )
                actions.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "recommended_action": action,
                        "parity_score": r.parity_score,
                        "source_env": r.source_env.value,
                        "target_env": r.target_env.value,
                    }
                )
        return sorted(actions, key=lambda x: x["parity_score"])

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

    def generate_report(self) -> EnvironmentParityReport:
        by_dev: dict[str, int] = {}
        by_parity: dict[str, int] = {}
        for r in self._records:
            by_dev[r.deviation_type.value] = by_dev.get(r.deviation_type.value, 0) + 1
            by_parity[r.parity_level.value] = by_parity.get(r.parity_level.value, 0) + 1
        scores = [r.parity_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        critical = sum(
            1
            for r in self._records
            if r.parity_level in (ParityLevel.CRITICAL_DEVIATION, ParityLevel.INCOMPATIBLE)
        )
        total_devs = sum(r.deviations_found for r in self._records)
        env_pairs = self.compare_environments()
        by_env_pair = {k: v["avg_parity"] for k, v in env_pairs.items()}
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.parity_score)
        svc_avgs = {s: sum(v) / len(v) for s, v in svc_scores.items()}
        top_deviating = sorted(svc_avgs, key=svc_avgs.get)[:5]  # type: ignore[arg-type]
        recs: list[str] = []
        if critical > 0:
            recs.append(f"{critical} critical deviation(s) — sync environments immediately")
        if avg_score < self._parity_threshold:
            recs.append(f"Avg parity {avg_score}% below {self._parity_threshold}% threshold")
        version_mismatches = by_dev.get("version_mismatch", 0)
        if version_mismatches > 0:
            recs.append(f"{version_mismatches} version mismatch(es) — update lower environments")
        if not recs:
            recs.append("Environment parity is healthy — all environments aligned")
        return EnvironmentParityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_parity_score=avg_score,
            critical_deviations=critical,
            total_deviations=total_devs,
            by_deviation_type=by_dev,
            by_parity_level=by_parity,
            by_environment_pair=by_env_pair,
            top_deviating_services=top_deviating,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("environment.parity.engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dev_dist: dict[str, int] = {}
        for r in self._records:
            dev_dist[r.deviation_type.value] = dev_dist.get(r.deviation_type.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "parity_threshold": self._parity_threshold,
            "deviation_distribution": dev_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
