"""Mitigation Efficacy Tracker — compute mitigation success rate,
detect ineffective mitigations, rank strategies by efficacy."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MitigationResult(StrEnum):
    EFFECTIVE = "effective"
    PARTIALLY_EFFECTIVE = "partially_effective"
    INEFFECTIVE = "ineffective"
    COUNTERPRODUCTIVE = "counterproductive"


class MitigationType(StrEnum):
    AUTOMATED = "automated"
    MANUAL = "manual"
    HYBRID = "hybrid"
    ESCALATION = "escalation"


class EfficacyLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


# --- Models ---


class MitigationEfficacyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    mitigation_result: MitigationResult = MitigationResult.EFFECTIVE
    mitigation_type: MitigationType = MitigationType.AUTOMATED
    efficacy_level: EfficacyLevel = EfficacyLevel.MEDIUM
    strategy_name: str = ""
    time_to_mitigate_seconds: float = 0.0
    efficacy_score: float = 0.0
    service: str = ""
    team: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MitigationEfficacyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    mitigation_result: MitigationResult = MitigationResult.EFFECTIVE
    success_rate: float = 0.0
    is_ineffective: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MitigationEfficacyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_efficacy_score: float = 0.0
    by_result: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MitigationEfficacyTracker:
    """Compute mitigation success rate, detect ineffective
    mitigations, rank strategies by efficacy."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[MitigationEfficacyRecord] = []
        self._analyses: dict[str, MitigationEfficacyAnalysis] = {}
        logger.info(
            "mitigation_efficacy_tracker.init",
            max_records=max_records,
        )

    def add_record(
        self,
        incident_id: str = "",
        mitigation_result: MitigationResult = MitigationResult.EFFECTIVE,
        mitigation_type: MitigationType = MitigationType.AUTOMATED,
        efficacy_level: EfficacyLevel = EfficacyLevel.MEDIUM,
        strategy_name: str = "",
        time_to_mitigate_seconds: float = 0.0,
        efficacy_score: float = 0.0,
        service: str = "",
        team: str = "",
        description: str = "",
    ) -> MitigationEfficacyRecord:
        record = MitigationEfficacyRecord(
            incident_id=incident_id,
            mitigation_result=mitigation_result,
            mitigation_type=mitigation_type,
            efficacy_level=efficacy_level,
            strategy_name=strategy_name,
            time_to_mitigate_seconds=time_to_mitigate_seconds,
            efficacy_score=efficacy_score,
            service=service,
            team=team,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "mitigation_efficacy.record_added",
            record_id=record.id,
            incident_id=incident_id,
        )
        return record

    def process(self, key: str) -> MitigationEfficacyAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        related = [r for r in self._records if r.strategy_name == rec.strategy_name]
        effective = sum(1 for r in related if r.mitigation_result == MitigationResult.EFFECTIVE)
        rate = round(effective / len(related), 2) if related else 0.0
        is_ineffective = rec.mitigation_result in (
            MitigationResult.INEFFECTIVE,
            MitigationResult.COUNTERPRODUCTIVE,
        )
        analysis = MitigationEfficacyAnalysis(
            incident_id=rec.incident_id,
            mitigation_result=rec.mitigation_result,
            success_rate=rate,
            is_ineffective=is_ineffective,
            description=f"Strategy {rec.strategy_name} efficacy {rate}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> MitigationEfficacyReport:
        by_res: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_lev: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            by_res[r.mitigation_result.value] = by_res.get(r.mitigation_result.value, 0) + 1
            by_type[r.mitigation_type.value] = by_type.get(r.mitigation_type.value, 0) + 1
            by_lev[r.efficacy_level.value] = by_lev.get(r.efficacy_level.value, 0) + 1
            scores.append(r.efficacy_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        recs: list[str] = []
        ineffective = by_res.get("ineffective", 0) + by_res.get("counterproductive", 0)
        if ineffective > 0:
            recs.append(f"{ineffective} ineffective mitigations need review")
        if not recs:
            recs.append("Mitigation strategies performing effectively")
        return MitigationEfficacyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_efficacy_score=avg,
            by_result=by_res,
            by_type=by_type,
            by_level=by_lev,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        result_dist: dict[str, int] = {}
        for r in self._records:
            k = r.mitigation_result.value
            result_dist[k] = result_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "result_distribution": result_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("mitigation_efficacy_tracker.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_mitigation_success_rate(self) -> list[dict[str, Any]]:
        """Compute success rate per strategy."""
        strategy_data: dict[str, dict[str, int]] = {}
        for r in self._records:
            k = r.strategy_name
            if k not in strategy_data:
                strategy_data[k] = {"effective": 0, "total": 0}
            strategy_data[k]["total"] += 1
            if r.mitigation_result == MitigationResult.EFFECTIVE:
                strategy_data[k]["effective"] += 1
        results: list[dict[str, Any]] = []
        for name, data in strategy_data.items():
            rate = round(data["effective"] / data["total"], 2) if data["total"] > 0 else 0.0
            results.append(
                {
                    "strategy_name": name,
                    "success_rate": rate,
                    "effective_count": data["effective"],
                    "total_uses": data["total"],
                }
            )
        results.sort(key=lambda x: x["success_rate"], reverse=True)
        return results

    def detect_ineffective_mitigations(self) -> list[dict[str, Any]]:
        """Detect strategies with high ineffectiveness."""
        strategy_data: dict[str, dict[str, int]] = {}
        for r in self._records:
            k = r.strategy_name
            if k not in strategy_data:
                strategy_data[k] = {"ineffective": 0, "total": 0}
            strategy_data[k]["total"] += 1
            if r.mitigation_result in (
                MitigationResult.INEFFECTIVE,
                MitigationResult.COUNTERPRODUCTIVE,
            ):
                strategy_data[k]["ineffective"] += 1
        results: list[dict[str, Any]] = []
        for name, data in strategy_data.items():
            rate = round(data["ineffective"] / data["total"], 2) if data["total"] > 0 else 0.0
            if rate > 0.2:
                results.append(
                    {
                        "strategy_name": name,
                        "ineffective_rate": rate,
                        "ineffective_count": data["ineffective"],
                        "total_uses": data["total"],
                    }
                )
        results.sort(key=lambda x: x["ineffective_rate"], reverse=True)
        return results

    def rank_strategies_by_efficacy(self) -> list[dict[str, Any]]:
        """Rank mitigation strategies by efficacy score."""
        strategy_scores: dict[str, list[float]] = {}
        for r in self._records:
            strategy_scores.setdefault(r.strategy_name, []).append(r.efficacy_score)
        results: list[dict[str, Any]] = []
        for name, scores in strategy_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "strategy_name": name,
                    "avg_efficacy_score": avg,
                    "usage_count": len(scores),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["avg_efficacy_score"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
