"""Deployment Frequency Analyzer — measure and trend deployment cadence by team and service."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FrequencyBand(StrEnum):
    ELITE = "elite"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    RARE = "rare"


class DeploymentType(StrEnum):
    FEATURE = "feature"
    HOTFIX = "hotfix"
    ROLLBACK = "rollback"
    CONFIG_CHANGE = "config_change"
    INFRASTRUCTURE = "infrastructure"


class FrequencyTrend(StrEnum):
    ACCELERATING = "accelerating"
    STABLE = "stable"
    DECELERATING = "decelerating"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class FrequencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    service: str = ""
    team: str = ""
    deployment_type: DeploymentType = DeploymentType.FEATURE
    frequency_band: FrequencyBand = FrequencyBand.MEDIUM
    deploys_per_week: float = 0.0
    deploy_success_rate: float = 100.0
    lead_time_hours: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class FrequencyMetric(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    metric_name: str = ""
    service: str = ""
    team: str = ""
    value: float = 0.0
    unit: str = ""
    trend: FrequencyTrend = FrequencyTrend.STABLE
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DeployFrequencyReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_records: int = 0
    total_metrics: int = 0
    avg_deploys_per_week: float = 0.0
    by_frequency_band: dict[str, int] = Field(default_factory=dict)
    by_deployment_type: dict[str, int] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    low_frequency_services: list[str] = Field(default_factory=list)
    elite_teams: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeploymentFrequencyAnalyzer:
    """Measure and trend deployment cadence across teams and services."""

    def __init__(
        self,
        max_records: int = 200000,
        min_deploy_per_week: float = 1.0,
    ) -> None:
        self._max_records = max_records
        self._min_deploy_per_week = min_deploy_per_week
        self._records: list[FrequencyRecord] = []
        self._metrics: list[FrequencyMetric] = []
        logger.info(
            "deploy_frequency.initialized",
            max_records=max_records,
            min_deploy_per_week=min_deploy_per_week,
        )

    # -- CRUD --

    def record_frequency(
        self,
        service: str,
        team: str = "",
        deployment_type: DeploymentType = DeploymentType.FEATURE,
        frequency_band: FrequencyBand = FrequencyBand.MEDIUM,
        deploys_per_week: float = 0.0,
        deploy_success_rate: float = 100.0,
        lead_time_hours: float = 0.0,
        details: str = "",
    ) -> FrequencyRecord:
        record = FrequencyRecord(
            service=service,
            team=team,
            deployment_type=deployment_type,
            frequency_band=frequency_band,
            deploys_per_week=deploys_per_week,
            deploy_success_rate=deploy_success_rate,
            lead_time_hours=lead_time_hours,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "deploy_frequency.recorded",
            record_id=record.id,
            service=service,
            deploys_per_week=deploys_per_week,
        )
        return record

    def get_frequency(self, record_id: str) -> FrequencyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_frequencies(
        self,
        frequency_band: FrequencyBand | None = None,
        deployment_type: DeploymentType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FrequencyRecord]:
        results = list(self._records)
        if frequency_band is not None:
            results = [r for r in results if r.frequency_band == frequency_band]
        if deployment_type is not None:
            results = [r for r in results if r.deployment_type == deployment_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        metric_name: str,
        service: str = "",
        team: str = "",
        value: float = 0.0,
        unit: str = "",
        trend: FrequencyTrend = FrequencyTrend.STABLE,
        description: str = "",
    ) -> FrequencyMetric:
        metric = FrequencyMetric(
            metric_name=metric_name,
            service=service,
            team=team,
            value=value,
            unit=unit,
            trend=trend,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "deploy_frequency.metric_added",
            metric_id=metric.id,
            metric_name=metric_name,
            value=value,
        )
        return metric

    # -- Domain operations --

    def analyze_frequency_by_team(self) -> list[dict[str, Any]]:
        """Aggregate deployment frequency statistics per team."""
        team_records: dict[str, list[FrequencyRecord]] = {}
        for r in self._records:
            if not r.team:
                continue
            team_records.setdefault(r.team, []).append(r)
        results: list[dict[str, Any]] = []
        for team, records in team_records.items():
            avg_dpw = round(sum(r.deploys_per_week for r in records) / len(records), 2)
            avg_success = round(sum(r.deploy_success_rate for r in records) / len(records), 2)
            bands: dict[str, int] = {}
            for r in records:
                bands[r.frequency_band.value] = bands.get(r.frequency_band.value, 0) + 1
            results.append(
                {
                    "team": team,
                    "total_services": len({r.service for r in records}),
                    "total_records": len(records),
                    "avg_deploys_per_week": avg_dpw,
                    "avg_success_rate": avg_success,
                    "frequency_bands": bands,
                }
            )
        results.sort(key=lambda x: x["avg_deploys_per_week"], reverse=True)
        return results

    def identify_low_frequency_services(self) -> list[dict[str, Any]]:
        """Find services deploying less than min_deploy_per_week."""
        service_latest: dict[str, FrequencyRecord] = {}
        for r in self._records:
            if r.service:
                service_latest[r.service] = r
        results: list[dict[str, Any]] = []
        for service, rec in service_latest.items():
            if rec.deploys_per_week < self._min_deploy_per_week:
                results.append(
                    {
                        "service": service,
                        "team": rec.team,
                        "deploys_per_week": rec.deploys_per_week,
                        "frequency_band": rec.frequency_band.value,
                        "threshold": self._min_deploy_per_week,
                    }
                )
        results.sort(key=lambda x: x["deploys_per_week"])
        return results

    def rank_by_deploy_rate(self) -> list[dict[str, Any]]:
        """Rank services by their average deploys per week (highest first)."""
        service_dpw: dict[str, list[float]] = {}
        for r in self._records:
            if r.service:
                service_dpw.setdefault(r.service, []).append(r.deploys_per_week)
        results: list[dict[str, Any]] = []
        for service, rates in service_dpw.items():
            avg_rate = round(sum(rates) / len(rates), 2) if rates else 0.0
            results.append(
                {
                    "service": service,
                    "avg_deploys_per_week": avg_rate,
                    "samples": len(rates),
                }
            )
        results.sort(key=lambda x: x["avg_deploys_per_week"], reverse=True)
        return results

    def detect_frequency_trends(self) -> dict[str, Any]:
        """Detect whether deployment frequency is accelerating or decelerating overall."""
        if len(self._records) < 4:
            return {
                "trend": FrequencyTrend.INSUFFICIENT_DATA.value,
                "sample_count": len(self._records),
            }
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]

        def _avg_dpw(records: list[FrequencyRecord]) -> float:
            if not records:
                return 0.0
            return round(sum(r.deploys_per_week for r in records) / len(records), 2)

        first_avg = _avg_dpw(first_half)
        second_avg = _avg_dpw(second_half)
        delta = round(second_avg - first_avg, 2)
        if delta > 1.0:
            trend = FrequencyTrend.ACCELERATING
        elif delta < -1.0:
            trend = FrequencyTrend.DECELERATING
        else:
            trend = FrequencyTrend.STABLE
        logger.info(
            "deploy_frequency.trend_detected",
            trend=trend.value,
            first_avg=first_avg,
            second_avg=second_avg,
        )
        return {
            "trend": trend.value,
            "first_half_avg_dpw": first_avg,
            "second_half_avg_dpw": second_avg,
            "delta_dpw": delta,
            "total_records": len(self._records),
        }

    # -- Report --

    def generate_report(self) -> DeployFrequencyReport:
        by_band: dict[str, int] = {}
        by_type: dict[str, int] = {}
        total_dpw = 0.0
        for r in self._records:
            by_band[r.frequency_band.value] = by_band.get(r.frequency_band.value, 0) + 1
            by_type[r.deployment_type.value] = by_type.get(r.deployment_type.value, 0) + 1
            total_dpw += r.deploys_per_week
        by_trend: dict[str, int] = {}
        for m in self._metrics:
            by_trend[m.trend.value] = by_trend.get(m.trend.value, 0) + 1
        total = len(self._records)
        avg_dpw = round(total_dpw / total, 2) if total else 0.0
        low_freq = self.identify_low_frequency_services()
        low_freq_services = [s["service"] for s in low_freq]
        team_stats = self.analyze_frequency_by_team()
        elite_teams = [t["team"] for t in team_stats if t["avg_deploys_per_week"] >= 7.0]
        recs: list[str] = []
        if low_freq_services:
            recs.append(
                f"{len(low_freq_services)} service(s) below {self._min_deploy_per_week}"
                " deploy/week threshold"
            )
        low_band = by_band.get(FrequencyBand.LOW.value, 0) + by_band.get(
            FrequencyBand.RARE.value, 0
        )
        if low_band > 0:
            recs.append(f"{low_band} service(s) in LOW/RARE frequency band")
        if not recs:
            recs.append("Deployment frequency is within healthy range")
        return DeployFrequencyReport(
            total_records=total,
            total_metrics=len(self._metrics),
            avg_deploys_per_week=avg_dpw,
            by_frequency_band=by_band,
            by_deployment_type=by_type,
            by_trend=by_trend,
            low_frequency_services=low_freq_services[:10],
            elite_teams=elite_teams[:10],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("deploy_frequency.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        band_dist: dict[str, int] = {}
        for r in self._records:
            band_dist[r.frequency_band.value] = band_dist.get(r.frequency_band.value, 0) + 1
        total = len(self._records)
        avg_dpw = round(sum(r.deploys_per_week for r in self._records) / total, 2) if total else 0.0
        return {
            "total_records": total,
            "total_metrics": len(self._metrics),
            "avg_deploys_per_week": avg_dpw,
            "min_deploy_per_week": self._min_deploy_per_week,
            "band_distribution": band_dist,
            "unique_services": len({r.service for r in self._records if r.service}),
            "unique_teams": len({r.team for r in self._records if r.team}),
        }
