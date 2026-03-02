"""Detection Rule Effectiveness — track detection rule TPR/FPR and maintenance cost."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RuleType(StrEnum):
    SIGNATURE = "signature"
    BEHAVIORAL = "behavioral"
    ANOMALY = "anomaly"
    CORRELATION = "correlation"
    CUSTOM = "custom"


class RuleStatus(StrEnum):
    ACTIVE = "active"
    TUNING = "tuning"
    DEPRECATED = "deprecated"
    TESTING = "testing"
    DISABLED = "disabled"


class EffectivenessLevel(StrEnum):
    HIGH_PERFORMING = "high_performing"
    EFFECTIVE = "effective"
    MODERATE = "moderate"
    UNDERPERFORMING = "underperforming"
    INEFFECTIVE = "ineffective"


# --- Models ---


class RuleRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    rule_type: RuleType = RuleType.SIGNATURE
    rule_status: RuleStatus = RuleStatus.ACTIVE
    effectiveness_level: EffectivenessLevel = EffectivenessLevel.HIGH_PERFORMING
    effectiveness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RuleAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    rule_type: RuleType = RuleType.SIGNATURE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DetectionRuleReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_effectiveness_count: int = 0
    avg_effectiveness_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_effectiveness: dict[str, int] = Field(default_factory=dict)
    top_low_effectiveness: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DetectionRuleEffectiveness:
    """Track detection rule TPR/FPR and maintenance cost."""

    def __init__(
        self,
        max_records: int = 200000,
        rule_effectiveness_threshold: float = 65.0,
    ) -> None:
        self._max_records = max_records
        self._rule_effectiveness_threshold = rule_effectiveness_threshold
        self._records: list[RuleRecord] = []
        self._analyses: list[RuleAnalysis] = []
        logger.info(
            "detection_rule_effectiveness.initialized",
            max_records=max_records,
            rule_effectiveness_threshold=rule_effectiveness_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_rule(
        self,
        rule_name: str,
        rule_type: RuleType = RuleType.SIGNATURE,
        rule_status: RuleStatus = RuleStatus.ACTIVE,
        effectiveness_level: EffectivenessLevel = EffectivenessLevel.HIGH_PERFORMING,
        effectiveness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RuleRecord:
        record = RuleRecord(
            rule_name=rule_name,
            rule_type=rule_type,
            rule_status=rule_status,
            effectiveness_level=effectiveness_level,
            effectiveness_score=effectiveness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "detection_rule_effectiveness.rule_recorded",
            record_id=record.id,
            rule_name=rule_name,
            rule_type=rule_type.value,
            rule_status=rule_status.value,
        )
        return record

    def get_rule(self, record_id: str) -> RuleRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_rules(
        self,
        rule_type: RuleType | None = None,
        rule_status: RuleStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RuleRecord]:
        results = list(self._records)
        if rule_type is not None:
            results = [r for r in results if r.rule_type == rule_type]
        if rule_status is not None:
            results = [r for r in results if r.rule_status == rule_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        rule_name: str,
        rule_type: RuleType = RuleType.SIGNATURE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RuleAnalysis:
        analysis = RuleAnalysis(
            rule_name=rule_name,
            rule_type=rule_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "detection_rule_effectiveness.analysis_added",
            rule_name=rule_name,
            rule_type=rule_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_rule_distribution(self) -> dict[str, Any]:
        """Group by rule_type; return count and avg effectiveness_score."""
        src_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.rule_type.value
            src_data.setdefault(key, []).append(r.effectiveness_score)
        result: dict[str, Any] = {}
        for src, scores in src_data.items():
            result[src] = {
                "count": len(scores),
                "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_effectiveness_rules(self) -> list[dict[str, Any]]:
        """Return records where effectiveness_score < rule_effectiveness_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.effectiveness_score < self._rule_effectiveness_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "rule_name": r.rule_name,
                        "rule_type": r.rule_type.value,
                        "effectiveness_score": r.effectiveness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["effectiveness_score"])

    def rank_by_effectiveness(self) -> list[dict[str, Any]]:
        """Group by service, avg effectiveness_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.effectiveness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_effectiveness_score"])
        return results

    def detect_rule_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> DetectionRuleReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_effectiveness: dict[str, int] = {}
        for r in self._records:
            by_type[r.rule_type.value] = by_type.get(r.rule_type.value, 0) + 1
            by_status[r.rule_status.value] = by_status.get(r.rule_status.value, 0) + 1
            by_effectiveness[r.effectiveness_level.value] = (
                by_effectiveness.get(r.effectiveness_level.value, 0) + 1
            )
        low_effectiveness_count = sum(
            1 for r in self._records if r.effectiveness_score < self._rule_effectiveness_threshold
        )
        scores = [r.effectiveness_score for r in self._records]
        avg_effectiveness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_effectiveness_rules()
        top_low_effectiveness = [o["rule_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_effectiveness_count > 0:
            recs.append(
                f"{low_effectiveness_count} rule(s) below effectiveness threshold "
                f"({self._rule_effectiveness_threshold})"
            )
        if self._records and avg_effectiveness_score < self._rule_effectiveness_threshold:
            recs.append(
                f"Avg effectiveness score {avg_effectiveness_score} below threshold "
                f"({self._rule_effectiveness_threshold})"
            )
        if not recs:
            recs.append("Detection rule effectiveness is healthy")
        return DetectionRuleReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_effectiveness_count=low_effectiveness_count,
            avg_effectiveness_score=avg_effectiveness_score,
            by_type=by_type,
            by_status=by_status,
            by_effectiveness=by_effectiveness,
            top_low_effectiveness=top_low_effectiveness,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("detection_rule_effectiveness.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.rule_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "rule_effectiveness_threshold": self._rule_effectiveness_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
