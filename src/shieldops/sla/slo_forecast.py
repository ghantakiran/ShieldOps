"""SLO Compliance Forecaster — forecast whether services will meet SLO at end-of-period."""

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
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class ComplianceRisk(StrEnum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    CRITICAL = "critical"
    BREACHED = "breached"
    UNKNOWN = "unknown"


class TrendDirection(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class SLIMeasurement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    slo_name: str = ""
    target_pct: float = 99.9
    current_pct: float = 100.0
    horizon: ForecastHorizon = ForecastHorizon.MONTHLY
    period_elapsed_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class SLOForecast(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    slo_name: str = ""
    target_pct: float = 99.9
    forecasted_pct: float = 100.0
    risk: ComplianceRisk = ComplianceRisk.UNKNOWN
    trend: TrendDirection = TrendDirection.INSUFFICIENT_DATA
    probability_of_breach_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class SLOForecastReport(BaseModel):
    total_measurements: int = 0
    total_forecasts: int = 0
    at_risk_count: int = 0
    breached_count: int = 0
    by_risk: dict[str, int] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLOComplianceForecaster:
    """Forecast whether a service will meet its SLO at end-of-period."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_threshold_pct: float = 95.0,
    ) -> None:
        self._max_records = max_records
        self._risk_threshold_pct = risk_threshold_pct
        self._measurements: list[SLIMeasurement] = []
        self._forecasts: list[SLOForecast] = []
        logger.info(
            "slo_forecast.initialized",
            max_records=max_records,
            risk_threshold_pct=risk_threshold_pct,
        )

    # -- internal helpers ------------------------------------------------

    def _assess_risk(
        self, current_pct: float, target_pct: float, period_elapsed_pct: float
    ) -> ComplianceRisk:
        if current_pct < target_pct:
            return ComplianceRisk.BREACHED
        margin = current_pct - target_pct
        if period_elapsed_pct > 75 and margin < 0.5:
            return ComplianceRisk.CRITICAL
        if margin < 1.0:
            return ComplianceRisk.AT_RISK
        return ComplianceRisk.ON_TRACK

    # -- record / get / list ---------------------------------------------

    def record_measurement(
        self,
        service: str,
        slo_name: str,
        target_pct: float = 99.9,
        current_pct: float = 100.0,
        horizon: ForecastHorizon = ForecastHorizon.MONTHLY,
        period_elapsed_pct: float = 0.0,
    ) -> SLIMeasurement:
        m = SLIMeasurement(
            service=service,
            slo_name=slo_name,
            target_pct=target_pct,
            current_pct=current_pct,
            horizon=horizon,
            period_elapsed_pct=period_elapsed_pct,
        )
        self._measurements.append(m)
        if len(self._measurements) > self._max_records:
            self._measurements = self._measurements[-self._max_records :]
        logger.info(
            "slo_forecast.measurement_recorded",
            measurement_id=m.id,
            service=service,
            slo_name=slo_name,
        )
        return m

    def get_measurement(self, measurement_id: str) -> SLIMeasurement | None:
        for m in self._measurements:
            if m.id == measurement_id:
                return m
        return None

    def list_measurements(
        self,
        service: str | None = None,
        slo_name: str | None = None,
        limit: int = 50,
    ) -> list[SLIMeasurement]:
        results = list(self._measurements)
        if service is not None:
            results = [m for m in results if m.service == service]
        if slo_name is not None:
            results = [m for m in results if m.slo_name == slo_name]
        return results[-limit:]

    # -- domain operations -----------------------------------------------

    def forecast_compliance(self, service: str, slo_name: str) -> SLOForecast:
        """Forecast end-of-period SLO compliance."""
        measurements = [
            m for m in self._measurements if m.service == service and m.slo_name == slo_name
        ]
        if not measurements:
            forecast = SLOForecast(
                service=service,
                slo_name=slo_name,
                risk=ComplianceRisk.UNKNOWN,
                trend=TrendDirection.INSUFFICIENT_DATA,
            )
            self._forecasts.append(forecast)
            return forecast

        latest = measurements[-1]
        risk = self._assess_risk(latest.current_pct, latest.target_pct, latest.period_elapsed_pct)
        trend = self.detect_trend(service, slo_name)

        # Project forward
        if trend == TrendDirection.DEGRADING:
            forecasted_pct = max(0, latest.current_pct - 0.5)
            breach_prob = min(100, (latest.target_pct - forecasted_pct + 1) * 20)
        elif trend == TrendDirection.IMPROVING:
            forecasted_pct = min(100, latest.current_pct + 0.2)
            breach_prob = max(0, (latest.target_pct - forecasted_pct) * 10)
        else:
            forecasted_pct = latest.current_pct
            breach_prob = max(0, (latest.target_pct - forecasted_pct) * 15)

        breach_prob = round(max(0, min(100, breach_prob)), 2)

        forecast = SLOForecast(
            service=service,
            slo_name=slo_name,
            target_pct=latest.target_pct,
            forecasted_pct=round(forecasted_pct, 4),
            risk=risk,
            trend=trend,
            probability_of_breach_pct=breach_prob,
        )
        self._forecasts.append(forecast)
        if len(self._forecasts) > self._max_records:
            self._forecasts = self._forecasts[-self._max_records :]
        logger.info(
            "slo_forecast.compliance_forecasted",
            forecast_id=forecast.id,
            service=service,
            slo_name=slo_name,
            risk=risk.value,
        )
        return forecast

    def assess_risk(self, service: str, slo_name: str) -> dict[str, Any]:
        """Assess current risk level for an SLO."""
        measurements = [
            m for m in self._measurements if m.service == service and m.slo_name == slo_name
        ]
        if not measurements:
            return {
                "service": service,
                "slo_name": slo_name,
                "risk": ComplianceRisk.UNKNOWN.value,
            }
        latest = measurements[-1]
        risk = self._assess_risk(latest.current_pct, latest.target_pct, latest.period_elapsed_pct)
        return {
            "service": service,
            "slo_name": slo_name,
            "risk": risk.value,
            "current_pct": latest.current_pct,
            "target_pct": latest.target_pct,
            "margin": round(latest.current_pct - latest.target_pct, 4),
        }

    def detect_trend(self, service: str, slo_name: str) -> TrendDirection:
        """Detect the trend direction for an SLO based on measurements."""
        measurements = [
            m for m in self._measurements if m.service == service and m.slo_name == slo_name
        ]
        if len(measurements) < 2:
            return TrendDirection.INSUFFICIENT_DATA
        recent = measurements[-3:] if len(measurements) >= 3 else measurements
        diffs = [recent[i + 1].current_pct - recent[i].current_pct for i in range(len(recent) - 1)]
        if all(d > 0 for d in diffs):
            return TrendDirection.IMPROVING
        if all(d < 0 for d in diffs):
            return TrendDirection.DEGRADING
        if all(abs(d) < 0.1 for d in diffs):
            return TrendDirection.STABLE
        return TrendDirection.VOLATILE

    def identify_at_risk_slos(self) -> list[dict[str, Any]]:
        """Find SLOs that are at risk or breached."""
        # Group latest measurement per service/slo_name
        latest: dict[tuple[str, str], SLIMeasurement] = {}
        for m in self._measurements:
            key = (m.service, m.slo_name)
            latest[key] = m

        results: list[dict[str, Any]] = []
        for (service, slo_name), m in latest.items():
            risk = self._assess_risk(m.current_pct, m.target_pct, m.period_elapsed_pct)
            if risk in (ComplianceRisk.AT_RISK, ComplianceRisk.CRITICAL, ComplianceRisk.BREACHED):
                results.append(
                    {
                        "service": service,
                        "slo_name": slo_name,
                        "risk": risk.value,
                        "current_pct": m.current_pct,
                        "target_pct": m.target_pct,
                    }
                )
        results.sort(key=lambda x: x["current_pct"])
        return results

    def project_end_of_period(self, service: str, slo_name: str) -> dict[str, Any]:
        """Project SLO value at end of current period."""
        measurements = [
            m for m in self._measurements if m.service == service and m.slo_name == slo_name
        ]
        if not measurements:
            return {
                "service": service,
                "slo_name": slo_name,
                "projected_pct": 0.0,
                "risk": "unknown",
            }
        latest = measurements[-1]
        trend = self.detect_trend(service, slo_name)
        remaining_pct = 100.0 - latest.period_elapsed_pct
        if trend == TrendDirection.DEGRADING:
            projected = max(0, latest.current_pct - (remaining_pct / 100) * 1.0)
        elif trend == TrendDirection.IMPROVING:
            projected = min(100, latest.current_pct + (remaining_pct / 100) * 0.5)
        else:
            projected = latest.current_pct
        risk = self._assess_risk(projected, latest.target_pct, 100.0)
        return {
            "service": service,
            "slo_name": slo_name,
            "projected_pct": round(projected, 4),
            "current_pct": latest.current_pct,
            "target_pct": latest.target_pct,
            "trend": trend.value,
            "risk": risk.value,
        }

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> SLOForecastReport:
        by_risk: dict[str, int] = {}
        by_trend: dict[str, int] = {}
        for f in self._forecasts:
            by_risk[f.risk.value] = by_risk.get(f.risk.value, 0) + 1
            by_trend[f.trend.value] = by_trend.get(f.trend.value, 0) + 1
        at_risk = sum(
            1
            for f in self._forecasts
            if f.risk in (ComplianceRisk.AT_RISK, ComplianceRisk.CRITICAL)
        )
        breached = sum(1 for f in self._forecasts if f.risk == ComplianceRisk.BREACHED)
        recs: list[str] = []
        if breached > 0:
            recs.append(f"{breached} SLO(s) already breached")
        if at_risk > 0:
            recs.append(f"{at_risk} SLO(s) at risk of breach")
        degrading = by_trend.get(TrendDirection.DEGRADING.value, 0)
        if degrading > 0:
            recs.append(f"{degrading} SLO(s) showing degrading trend")
        if not recs:
            recs.append("All SLOs on track")
        return SLOForecastReport(
            total_measurements=len(self._measurements),
            total_forecasts=len(self._forecasts),
            at_risk_count=at_risk,
            breached_count=breached,
            by_risk=by_risk,
            by_trend=by_trend,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._measurements.clear()
        self._forecasts.clear()
        logger.info("slo_forecast.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        risk_dist: dict[str, int] = {}
        for f in self._forecasts:
            key = f.risk.value
            risk_dist[key] = risk_dist.get(key, 0) + 1
        return {
            "total_measurements": len(self._measurements),
            "total_forecasts": len(self._forecasts),
            "risk_threshold_pct": self._risk_threshold_pct,
            "risk_distribution": risk_dist,
            "unique_services": len({m.service for m in self._measurements}),
        }
