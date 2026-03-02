"""Ransomware Defense Engine — mass encryption detection, recovery readiness scoring."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RansomwareIndicator(StrEnum):
    MASS_ENCRYPTION = "mass_encryption"
    SHADOW_COPY_DELETE = "shadow_copy_delete"
    RANSOM_NOTE = "ransom_note"
    C2_COMMUNICATION = "c2_communication"
    LATERAL_SPREAD = "lateral_spread"


class DefenseLayer(StrEnum):
    PREVENTION = "prevention"
    DETECTION = "detection"
    CONTAINMENT = "containment"
    RECOVERY = "recovery"
    POST_INCIDENT = "post_incident"


class ReadinessLevel(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    POOR = "poor"
    CRITICAL = "critical"


# --- Models ---


class RansomwareRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    defense_name: str = ""
    ransomware_indicator: RansomwareIndicator = RansomwareIndicator.MASS_ENCRYPTION
    defense_layer: DefenseLayer = DefenseLayer.PREVENTION
    readiness_level: ReadinessLevel = ReadinessLevel.EXCELLENT
    readiness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RansomwareAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    defense_name: str = ""
    ransomware_indicator: RansomwareIndicator = RansomwareIndicator.MASS_ENCRYPTION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RansomwareReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_readiness_count: int = 0
    avg_readiness_score: float = 0.0
    by_indicator: dict[str, int] = Field(default_factory=dict)
    by_layer: dict[str, int] = Field(default_factory=dict)
    by_readiness: dict[str, int] = Field(default_factory=dict)
    top_low_readiness: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RansomwareDefenseEngine:
    """Mass encryption detection and recovery readiness scoring."""

    def __init__(
        self,
        max_records: int = 200000,
        readiness_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._readiness_threshold = readiness_threshold
        self._records: list[RansomwareRecord] = []
        self._analyses: list[RansomwareAnalysis] = []
        logger.info(
            "ransomware_defense_engine.initialized",
            max_records=max_records,
            readiness_threshold=readiness_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_defense(
        self,
        defense_name: str,
        ransomware_indicator: RansomwareIndicator = RansomwareIndicator.MASS_ENCRYPTION,
        defense_layer: DefenseLayer = DefenseLayer.PREVENTION,
        readiness_level: ReadinessLevel = ReadinessLevel.EXCELLENT,
        readiness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RansomwareRecord:
        record = RansomwareRecord(
            defense_name=defense_name,
            ransomware_indicator=ransomware_indicator,
            defense_layer=defense_layer,
            readiness_level=readiness_level,
            readiness_score=readiness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "ransomware_defense_engine.defense_recorded",
            record_id=record.id,
            defense_name=defense_name,
            ransomware_indicator=ransomware_indicator.value,
            defense_layer=defense_layer.value,
        )
        return record

    def get_defense(self, record_id: str) -> RansomwareRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_defenses(
        self,
        ransomware_indicator: RansomwareIndicator | None = None,
        defense_layer: DefenseLayer | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RansomwareRecord]:
        results = list(self._records)
        if ransomware_indicator is not None:
            results = [r for r in results if r.ransomware_indicator == ransomware_indicator]
        if defense_layer is not None:
            results = [r for r in results if r.defense_layer == defense_layer]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        defense_name: str,
        ransomware_indicator: RansomwareIndicator = RansomwareIndicator.MASS_ENCRYPTION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RansomwareAnalysis:
        analysis = RansomwareAnalysis(
            defense_name=defense_name,
            ransomware_indicator=ransomware_indicator,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "ransomware_defense_engine.analysis_added",
            defense_name=defense_name,
            ransomware_indicator=ransomware_indicator.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_defense_distribution(self) -> dict[str, Any]:
        """Group by ransomware_indicator; return count and avg readiness_score."""
        ind_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.ransomware_indicator.value
            ind_data.setdefault(key, []).append(r.readiness_score)
        result: dict[str, Any] = {}
        for ind, scores in ind_data.items():
            result[ind] = {
                "count": len(scores),
                "avg_readiness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_readiness_defenses(self) -> list[dict[str, Any]]:
        """Return records where readiness_score < readiness_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.readiness_score < self._readiness_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "defense_name": r.defense_name,
                        "ransomware_indicator": r.ransomware_indicator.value,
                        "readiness_score": r.readiness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["readiness_score"])

    def rank_by_readiness_score(self) -> list[dict[str, Any]]:
        """Group by service, avg readiness_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.readiness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_readiness_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_readiness_score"])
        return results

    def detect_readiness_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> RansomwareReport:
        by_indicator: dict[str, int] = {}
        by_layer: dict[str, int] = {}
        by_readiness: dict[str, int] = {}
        for r in self._records:
            by_indicator[r.ransomware_indicator.value] = (
                by_indicator.get(r.ransomware_indicator.value, 0) + 1
            )
            by_layer[r.defense_layer.value] = by_layer.get(r.defense_layer.value, 0) + 1
            by_readiness[r.readiness_level.value] = by_readiness.get(r.readiness_level.value, 0) + 1
        low_readiness_count = sum(
            1 for r in self._records if r.readiness_score < self._readiness_threshold
        )
        scores = [r.readiness_score for r in self._records]
        avg_readiness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_readiness_defenses()
        top_low_readiness = [o["defense_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_readiness_count > 0:
            recs.append(
                f"{low_readiness_count} defense(s) below readiness threshold "
                f"({self._readiness_threshold})"
            )
        if self._records and avg_readiness_score < self._readiness_threshold:
            recs.append(
                f"Avg readiness score {avg_readiness_score} below threshold "
                f"({self._readiness_threshold})"
            )
        if not recs:
            recs.append("Ransomware defense readiness is healthy")
        return RansomwareReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_readiness_count=low_readiness_count,
            avg_readiness_score=avg_readiness_score,
            by_indicator=by_indicator,
            by_layer=by_layer,
            by_readiness=by_readiness,
            top_low_readiness=top_low_readiness,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("ransomware_defense_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        indicator_dist: dict[str, int] = {}
        for r in self._records:
            key = r.ransomware_indicator.value
            indicator_dist[key] = indicator_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "readiness_threshold": self._readiness_threshold,
            "indicator_distribution": indicator_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
