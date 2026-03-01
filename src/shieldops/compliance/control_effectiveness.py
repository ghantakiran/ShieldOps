"""Control Effectiveness Tracker — track control effectiveness, identify weak controls."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ControlType(StrEnum):
    PREVENTIVE = "preventive"
    DETECTIVE = "detective"
    CORRECTIVE = "corrective"
    COMPENSATING = "compensating"
    DIRECTIVE = "directive"


class EffectivenessLevel(StrEnum):
    HIGHLY_EFFECTIVE = "highly_effective"
    EFFECTIVE = "effective"
    PARTIALLY_EFFECTIVE = "partially_effective"
    INEFFECTIVE = "ineffective"
    NOT_TESTED = "not_tested"


class ControlDomain(StrEnum):
    ACCESS_MANAGEMENT = "access_management"
    DATA_PROTECTION = "data_protection"
    CHANGE_CONTROL = "change_control"
    INCIDENT_RESPONSE = "incident_response"
    MONITORING = "monitoring"


# --- Models ---


class ControlRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    control_type: ControlType = ControlType.PREVENTIVE
    effectiveness_level: EffectivenessLevel = EffectivenessLevel.NOT_TESTED
    control_domain: ControlDomain = ControlDomain.ACCESS_MANAGEMENT
    effectiveness_pct: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EffectivenessTest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    test_name: str = ""
    control_type: ControlType = ControlType.PREVENTIVE
    test_score: float = 0.0
    controls_tested: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ControlEffectivenessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_tests: int = 0
    effective_controls: int = 0
    avg_effectiveness_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_domain: dict[str, int] = Field(default_factory=dict)
    weak_controls: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ControlEffectivenessTracker:
    """Track control effectiveness, identify weak controls, measure compliance posture."""

    def __init__(
        self,
        max_records: int = 200000,
        min_effectiveness_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_effectiveness_pct = min_effectiveness_pct
        self._records: list[ControlRecord] = []
        self._tests: list[EffectivenessTest] = []
        logger.info(
            "control_effectiveness.initialized",
            max_records=max_records,
            min_effectiveness_pct=min_effectiveness_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_control(
        self,
        control_id: str,
        control_type: ControlType = ControlType.PREVENTIVE,
        effectiveness_level: EffectivenessLevel = EffectivenessLevel.NOT_TESTED,
        control_domain: ControlDomain = ControlDomain.ACCESS_MANAGEMENT,
        effectiveness_pct: float = 0.0,
        team: str = "",
    ) -> ControlRecord:
        record = ControlRecord(
            control_id=control_id,
            control_type=control_type,
            effectiveness_level=effectiveness_level,
            control_domain=control_domain,
            effectiveness_pct=effectiveness_pct,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "control_effectiveness.control_recorded",
            record_id=record.id,
            control_id=control_id,
            control_type=control_type.value,
            effectiveness_level=effectiveness_level.value,
        )
        return record

    def get_control(self, record_id: str) -> ControlRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_controls(
        self,
        control_type: ControlType | None = None,
        effectiveness_level: EffectivenessLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ControlRecord]:
        results = list(self._records)
        if control_type is not None:
            results = [r for r in results if r.control_type == control_type]
        if effectiveness_level is not None:
            results = [r for r in results if r.effectiveness_level == effectiveness_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_test(
        self,
        test_name: str,
        control_type: ControlType = ControlType.PREVENTIVE,
        test_score: float = 0.0,
        controls_tested: int = 0,
        description: str = "",
    ) -> EffectivenessTest:
        test = EffectivenessTest(
            test_name=test_name,
            control_type=control_type,
            test_score=test_score,
            controls_tested=controls_tested,
            description=description,
        )
        self._tests.append(test)
        if len(self._tests) > self._max_records:
            self._tests = self._tests[-self._max_records :]
        logger.info(
            "control_effectiveness.test_added",
            test_name=test_name,
            control_type=control_type.value,
            test_score=test_score,
        )
        return test

    # -- domain operations --------------------------------------------------

    def analyze_control_effectiveness(self) -> dict[str, Any]:
        """Group by control_type; return count and avg effectiveness_pct per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.control_type.value
            type_data.setdefault(key, []).append(r.effectiveness_pct)
        result: dict[str, Any] = {}
        for ctype, pcts in type_data.items():
            result[ctype] = {
                "count": len(pcts),
                "avg_effectiveness_pct": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_weak_controls(self) -> list[dict[str, Any]]:
        """Return records where effectiveness_pct < min_effectiveness_pct."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.effectiveness_pct < self._min_effectiveness_pct:
                results.append(
                    {
                        "record_id": r.id,
                        "control_id": r.control_id,
                        "effectiveness_pct": r.effectiveness_pct,
                        "control_type": r.control_type.value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_effectiveness(self) -> list[dict[str, Any]]:
        """Group by team, total effectiveness_pct, sort descending."""
        team_scores: dict[str, float] = {}
        for r in self._records:
            team_scores[r.team] = team_scores.get(r.team, 0) + r.effectiveness_pct
        results: list[dict[str, Any]] = []
        for team, total in team_scores.items():
            results.append(
                {
                    "team": team,
                    "total_effectiveness": total,
                }
            )
        results.sort(key=lambda x: x["total_effectiveness"], reverse=True)
        return results

    def detect_effectiveness_trends(self) -> dict[str, Any]:
        """Split-half on effectiveness_pct; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        counts = [r.effectiveness_pct for r in self._records]
        mid = len(counts) // 2
        first_half = counts[:mid]
        second_half = counts[mid:]
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

    def generate_report(self) -> ControlEffectivenessReport:
        by_type: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_domain: dict[str, int] = {}
        for r in self._records:
            by_type[r.control_type.value] = by_type.get(r.control_type.value, 0) + 1
            by_level[r.effectiveness_level.value] = by_level.get(r.effectiveness_level.value, 0) + 1
            by_domain[r.control_domain.value] = by_domain.get(r.control_domain.value, 0) + 1
        weak_count = sum(
            1 for r in self._records if r.effectiveness_pct < self._min_effectiveness_pct
        )
        effective_controls = len({r.control_id for r in self._records if r.effectiveness_pct > 0})
        avg_eff = (
            round(sum(r.effectiveness_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        weak_ids = [
            r.control_id for r in self._records if r.effectiveness_pct < self._min_effectiveness_pct
        ][:5]
        recs: list[str] = []
        if weak_count > 0:
            recs.append(
                f"{weak_count} control(s) below minimum effectiveness"
                f" ({self._min_effectiveness_pct}%)"
            )
        if self._records and avg_eff < self._min_effectiveness_pct:
            recs.append(
                f"Average effectiveness {avg_eff}% is below threshold"
                f" ({self._min_effectiveness_pct}%)"
            )
        if not recs:
            recs.append("Control effectiveness levels are healthy")
        return ControlEffectivenessReport(
            total_records=len(self._records),
            total_tests=len(self._tests),
            effective_controls=effective_controls,
            avg_effectiveness_pct=avg_eff,
            by_type=by_type,
            by_level=by_level,
            by_domain=by_domain,
            weak_controls=weak_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._tests.clear()
        logger.info("control_effectiveness.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.control_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_tests": len(self._tests),
            "min_effectiveness_pct": self._min_effectiveness_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_controls": len({r.control_id for r in self._records}),
        }
