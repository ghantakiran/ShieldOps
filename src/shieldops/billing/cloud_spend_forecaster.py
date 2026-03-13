"""Cloud Spend Forecaster
forecast spend horizons, detect spend seasonality,
simulate growth scenarios."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ForecastHorizon(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    MULTI_YEAR = "multi_year"


class SeasonalityType(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    EVENT_DRIVEN = "event_driven"


class GrowthModel(StrEnum):
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    STEPWISE = "stepwise"
    CUSTOM = "custom"


# --- Models ---


class CloudSpendRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str = ""
    service_name: str = ""
    forecast_horizon: ForecastHorizon = ForecastHorizon.MONTHLY
    seasonality_type: SeasonalityType = SeasonalityType.MONTHLY
    growth_model: GrowthModel = GrowthModel.LINEAR
    current_spend: float = 0.0
    projected_spend: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CloudSpendAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str = ""
    forecast_horizon: ForecastHorizon = ForecastHorizon.MONTHLY
    current_spend: float = 0.0
    projected_spend: float = 0.0
    growth_rate: float = 0.0
    seasonal_factor: float = 1.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CloudSpendReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_current_spend: float = 0.0
    by_horizon: dict[str, int] = Field(default_factory=dict)
    by_seasonality: dict[str, int] = Field(default_factory=dict)
    by_growth_model: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CloudSpendForecaster:
    """Forecast spend horizons, detect seasonality,
    simulate growth scenarios."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CloudSpendRecord] = []
        self._analyses: dict[str, CloudSpendAnalysis] = {}
        logger.info(
            "cloud_spend_forecaster.init",
            max_records=max_records,
        )

    def add_record(
        self,
        account_id: str = "",
        service_name: str = "",
        forecast_horizon: ForecastHorizon = (ForecastHorizon.MONTHLY),
        seasonality_type: SeasonalityType = (SeasonalityType.MONTHLY),
        growth_model: GrowthModel = GrowthModel.LINEAR,
        current_spend: float = 0.0,
        projected_spend: float = 0.0,
        description: str = "",
    ) -> CloudSpendRecord:
        record = CloudSpendRecord(
            account_id=account_id,
            service_name=service_name,
            forecast_horizon=forecast_horizon,
            seasonality_type=seasonality_type,
            growth_model=growth_model,
            current_spend=current_spend,
            projected_spend=projected_spend,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cloud_spend_forecaster.record_added",
            record_id=record.id,
            account_id=account_id,
        )
        return record

    def process(self, key: str) -> CloudSpendAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        growth = 0.0
        if rec.current_spend > 0:
            growth = round(
                (rec.projected_spend - rec.current_spend) / rec.current_spend * 100,
                2,
            )
        analysis = CloudSpendAnalysis(
            account_id=rec.account_id,
            forecast_horizon=rec.forecast_horizon,
            current_spend=rec.current_spend,
            projected_spend=rec.projected_spend,
            growth_rate=growth,
            description=(f"Forecast for {rec.account_id}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CloudSpendReport:
        by_h: dict[str, int] = {}
        by_s: dict[str, int] = {}
        by_g: dict[str, int] = {}
        spends: list[float] = []
        for r in self._records:
            k = r.forecast_horizon.value
            by_h[k] = by_h.get(k, 0) + 1
            k2 = r.seasonality_type.value
            by_s[k2] = by_s.get(k2, 0) + 1
            k3 = r.growth_model.value
            by_g[k3] = by_g.get(k3, 0) + 1
            spends.append(r.current_spend)
        avg = round(sum(spends) / len(spends), 2) if spends else 0.0
        recs: list[str] = []
        high = [r for r in self._records if r.projected_spend > r.current_spend * 1.5]
        if high:
            recs.append(f"{len(high)} accounts with >50% growth")
        if not recs:
            recs.append("Spend growth within norms")
        return CloudSpendReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_current_spend=avg,
            by_horizon=by_h,
            by_seasonality=by_s,
            by_growth_model=by_g,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        h_dist: dict[str, int] = {}
        for r in self._records:
            k = r.forecast_horizon.value
            h_dist[k] = h_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "horizon_distribution": h_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("cloud_spend_forecaster.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def forecast_spend_horizon(
        self,
    ) -> list[dict[str, Any]]:
        """Forecast spend across horizons."""
        acct_spend: dict[str, list[float]] = {}
        acct_proj: dict[str, list[float]] = {}
        for r in self._records:
            acct_spend.setdefault(r.account_id, []).append(r.current_spend)
            acct_proj.setdefault(r.account_id, []).append(r.projected_spend)
        results: list[dict[str, Any]] = []
        for aid, spends in acct_spend.items():
            projs = acct_proj[aid]
            avg_cur = round(sum(spends) / len(spends), 2)
            avg_proj = round(sum(projs) / len(projs), 2)
            results.append(
                {
                    "account_id": aid,
                    "avg_current": avg_cur,
                    "avg_projected": avg_proj,
                    "delta": round(avg_proj - avg_cur, 2),
                }
            )
        results.sort(key=lambda x: x["delta"], reverse=True)
        return results

    def detect_spend_seasonality(
        self,
    ) -> list[dict[str, Any]]:
        """Detect seasonal spend patterns."""
        season_map: dict[str, list[float]] = {}
        for r in self._records:
            k = r.seasonality_type.value
            season_map.setdefault(k, []).append(r.current_spend)
        results: list[dict[str, Any]] = []
        for stype, spends in season_map.items():
            avg = round(sum(spends) / len(spends), 2)
            variance = round(
                sum((s - avg) ** 2 for s in spends) / max(len(spends), 1),
                2,
            )
            results.append(
                {
                    "seasonality_type": stype,
                    "record_count": len(spends),
                    "avg_spend": avg,
                    "variance": variance,
                }
            )
        return results

    def simulate_growth_scenario(
        self,
    ) -> list[dict[str, Any]]:
        """Simulate growth scenarios."""
        model_map: dict[str, list[float]] = {}
        for r in self._records:
            k = r.growth_model.value
            model_map.setdefault(k, []).append(r.projected_spend)
        results: list[dict[str, Any]] = []
        for model, projs in model_map.items():
            avg = round(sum(projs) / len(projs), 2)
            results.append(
                {
                    "growth_model": model,
                    "scenario_count": len(projs),
                    "avg_projected": avg,
                    "max_projected": round(max(projs), 2),
                }
            )
        return results
