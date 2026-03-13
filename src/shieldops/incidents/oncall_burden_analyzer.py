"""Oncall Burden Analyzer
calculate burden index, detect burden imbalance,
forecast burnout risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BurdenLevel(StrEnum):
    EXTREME = "extreme"
    HIGH = "high"
    MODERATE = "moderate"
    SUSTAINABLE = "sustainable"


class ShiftPeriod(StrEnum):
    BUSINESS_HOURS = "business_hours"
    EVENING = "evening"
    OVERNIGHT = "overnight"
    WEEKEND = "weekend"


class BurnoutRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class OncallBurdenRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    responder_id: str = ""
    burden_level: BurdenLevel = BurdenLevel.SUSTAINABLE
    shift_period: ShiftPeriod = ShiftPeriod.BUSINESS_HOURS
    burnout_risk: BurnoutRisk = BurnoutRisk.LOW
    pages_received: int = 0
    hours_on_call: float = 0.0
    incidents_handled: int = 0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class OncallBurdenAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    responder_id: str = ""
    burden_index: float = 0.0
    burden_level: BurdenLevel = BurdenLevel.SUSTAINABLE
    burnout_risk: BurnoutRisk = BurnoutRisk.LOW
    total_pages: int = 0
    total_hours: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class OncallBurdenReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_burden_index: float = 0.0
    by_burden_level: dict[str, int] = Field(default_factory=dict)
    by_shift_period: dict[str, int] = Field(default_factory=dict)
    by_burnout_risk: dict[str, int] = Field(default_factory=dict)
    high_burden_responders: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class OncallBurdenAnalyzer:
    """Calculate burden index, detect burden
    imbalance, forecast burnout risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[OncallBurdenRecord] = []
        self._analyses: dict[str, OncallBurdenAnalysis] = {}
        logger.info(
            "oncall_burden_analyzer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        responder_id: str = "",
        burden_level: BurdenLevel = (BurdenLevel.SUSTAINABLE),
        shift_period: ShiftPeriod = (ShiftPeriod.BUSINESS_HOURS),
        burnout_risk: BurnoutRisk = BurnoutRisk.LOW,
        pages_received: int = 0,
        hours_on_call: float = 0.0,
        incidents_handled: int = 0,
        team: str = "",
    ) -> OncallBurdenRecord:
        record = OncallBurdenRecord(
            responder_id=responder_id,
            burden_level=burden_level,
            shift_period=shift_period,
            burnout_risk=burnout_risk,
            pages_received=pages_received,
            hours_on_call=hours_on_call,
            incidents_handled=incidents_handled,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "oncall_burden.record_added",
            record_id=record.id,
            responder_id=responder_id,
        )
        return record

    def process(self, key: str) -> OncallBurdenAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        related = [r for r in self._records if r.responder_id == rec.responder_id]
        total_pages = sum(r.pages_received for r in related)
        total_hours = sum(r.hours_on_call for r in related)
        burden_idx = min(
            100.0,
            total_pages * 2.0 + total_hours * 0.5,
        )
        analysis = OncallBurdenAnalysis(
            responder_id=rec.responder_id,
            burden_index=round(burden_idx, 2),
            burden_level=rec.burden_level,
            burnout_risk=rec.burnout_risk,
            total_pages=total_pages,
            total_hours=round(total_hours, 2),
            description=(f"Responder {rec.responder_id} burden index {burden_idx:.2f}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> OncallBurdenReport:
        by_bl: dict[str, int] = {}
        by_sp: dict[str, int] = {}
        by_br: dict[str, int] = {}
        pages: list[int] = []
        for r in self._records:
            k = r.burden_level.value
            by_bl[k] = by_bl.get(k, 0) + 1
            k2 = r.shift_period.value
            by_sp[k2] = by_sp.get(k2, 0) + 1
            k3 = r.burnout_risk.value
            by_br[k3] = by_br.get(k3, 0) + 1
            pages.append(r.pages_received)
        avg = round(sum(pages) / len(pages), 2) if pages else 0.0
        high = list(
            {
                r.responder_id
                for r in self._records
                if r.burden_level
                in (
                    BurdenLevel.EXTREME,
                    BurdenLevel.HIGH,
                )
            }
        )[:10]
        recs: list[str] = []
        if high:
            recs.append(f"{len(high)} high-burden responders")
        if not recs:
            recs.append("Oncall burden within norms")
        return OncallBurdenReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_burden_index=avg,
            by_burden_level=by_bl,
            by_shift_period=by_sp,
            by_burnout_risk=by_br,
            high_burden_responders=high,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        bl_dist: dict[str, int] = {}
        for r in self._records:
            k = r.burden_level.value
            bl_dist[k] = bl_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "burden_level_distribution": bl_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("oncall_burden_analyzer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def calculate_burden_index(
        self,
    ) -> list[dict[str, Any]]:
        """Calculate burden index per responder."""
        resp_pages: dict[str, int] = {}
        resp_hours: dict[str, float] = {}
        resp_incidents: dict[str, int] = {}
        for r in self._records:
            resp_pages[r.responder_id] = resp_pages.get(r.responder_id, 0) + r.pages_received
            resp_hours[r.responder_id] = resp_hours.get(r.responder_id, 0.0) + r.hours_on_call
            resp_incidents[r.responder_id] = (
                resp_incidents.get(r.responder_id, 0) + r.incidents_handled
            )
        results: list[dict[str, Any]] = []
        for rid in resp_pages:
            idx = min(
                100.0,
                resp_pages[rid] * 2.0 + resp_hours[rid] * 0.5,
            )
            results.append(
                {
                    "responder_id": rid,
                    "burden_index": round(idx, 2),
                    "total_pages": resp_pages[rid],
                    "total_hours": round(resp_hours[rid], 2),
                    "total_incidents": (resp_incidents[rid]),
                }
            )
        results.sort(
            key=lambda x: x["burden_index"],
            reverse=True,
        )
        return results

    def detect_burden_imbalance(
        self,
    ) -> list[dict[str, Any]]:
        """Detect burden imbalance across teams."""
        team_pages: dict[str, list[int]] = {}
        for r in self._records:
            team_pages.setdefault(r.team, []).append(r.pages_received)
        results: list[dict[str, Any]] = []
        for team, pages in team_pages.items():
            avg = sum(pages) / len(pages) if pages else 0.0
            mx = max(pages) if pages else 0
            mn = min(pages) if pages else 0
            spread = mx - mn
            results.append(
                {
                    "team": team,
                    "avg_pages": round(avg, 2),
                    "max_pages": mx,
                    "min_pages": mn,
                    "spread": spread,
                    "imbalanced": spread > avg * 2,
                }
            )
        results.sort(
            key=lambda x: x["spread"],
            reverse=True,
        )
        return results

    def forecast_burnout_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Forecast burnout risk per responder."""
        resp_data: dict[str, list[OncallBurdenRecord]] = {}
        for r in self._records:
            resp_data.setdefault(r.responder_id, []).append(r)
        results: list[dict[str, Any]] = []
        for rid, records in resp_data.items():
            total_pages = sum(r.pages_received for r in records)
            overnight = sum(1 for r in records if r.shift_period == ShiftPeriod.OVERNIGHT)
            risk_score = min(
                100.0,
                total_pages * 1.5 + overnight * 10.0,
            )
            risk = (
                "critical"
                if risk_score > 80
                else "high"
                if risk_score > 60
                else "medium"
                if risk_score > 30
                else "low"
            )
            results.append(
                {
                    "responder_id": rid,
                    "burnout_risk_score": round(risk_score, 2),
                    "risk_level": risk,
                    "total_pages": total_pages,
                    "overnight_shifts": overnight,
                }
            )
        results.sort(
            key=lambda x: x["burnout_risk_score"],
            reverse=True,
        )
        return results
