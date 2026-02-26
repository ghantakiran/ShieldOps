"""Incident Auto-Triage Engine — automated classification, priority assignment, team routing."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TriageCategory(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    NETWORK = "network"
    SECURITY = "security"
    DATA = "data"


class TriagePriority(StrEnum):
    P1_CRITICAL = "p1_critical"
    P2_HIGH = "p2_high"
    P3_MEDIUM = "p3_medium"
    P4_LOW = "p4_low"
    P5_INFORMATIONAL = "p5_informational"


class TriageConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"
    MANUAL_REQUIRED = "manual_required"


# --- Models ---


class TriageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    category: TriageCategory = TriageCategory.APPLICATION
    priority: TriagePriority = TriagePriority.P3_MEDIUM
    confidence: TriageConfidence = TriageConfidence.MEDIUM
    assigned_team: str = ""
    triage_time_seconds: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class TriageRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    category: TriageCategory = TriageCategory.APPLICATION
    priority: TriagePriority = TriagePriority.P3_MEDIUM
    match_pattern: str = ""
    hit_count: int = 0
    created_at: float = Field(default_factory=time.time)


class AutoTriageReport(BaseModel):
    total_triages: int = 0
    total_rules: int = 0
    avg_triage_time_seconds: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    misclassified_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentAutoTriageEngine:
    """Automated incident classification, priority assignment, and team routing."""

    def __init__(
        self,
        max_records: int = 200000,
        min_confidence_pct: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._min_confidence_pct = min_confidence_pct
        self._records: list[TriageRecord] = []
        self._rules: list[TriageRule] = []
        logger.info(
            "auto_triage.initialized",
            max_records=max_records,
            min_confidence_pct=min_confidence_pct,
        )

    # -- internal helpers ------------------------------------------------

    def _priority_to_confidence(self, priority: TriagePriority) -> TriageConfidence:
        if priority in (TriagePriority.P1_CRITICAL, TriagePriority.P2_HIGH):
            return TriageConfidence.HIGH
        if priority == TriagePriority.P3_MEDIUM:
            return TriageConfidence.MEDIUM
        return TriageConfidence.LOW

    def _confidence_to_pct(self, confidence: TriageConfidence) -> float:
        mapping = {
            TriageConfidence.HIGH: 90.0,
            TriageConfidence.MEDIUM: 70.0,
            TriageConfidence.LOW: 50.0,
            TriageConfidence.UNCERTAIN: 30.0,
            TriageConfidence.MANUAL_REQUIRED: 10.0,
        }
        return mapping.get(confidence, 50.0)

    # -- record / get / list ---------------------------------------------

    def record_triage(
        self,
        incident_id: str,
        category: TriageCategory = TriageCategory.APPLICATION,
        priority: TriagePriority = TriagePriority.P3_MEDIUM,
        confidence: TriageConfidence | None = None,
        assigned_team: str = "",
        triage_time_seconds: float = 0.0,
        details: str = "",
    ) -> TriageRecord:
        if confidence is None:
            confidence = self._priority_to_confidence(priority)
        record = TriageRecord(
            incident_id=incident_id,
            category=category,
            priority=priority,
            confidence=confidence,
            assigned_team=assigned_team,
            triage_time_seconds=triage_time_seconds,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "auto_triage.triage_recorded",
            record_id=record.id,
            incident_id=incident_id,
            category=category.value,
            priority=priority.value,
        )
        return record

    def get_triage(self, record_id: str) -> TriageRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_triages(
        self,
        incident_id: str | None = None,
        category: TriageCategory | None = None,
        limit: int = 50,
    ) -> list[TriageRecord]:
        results = list(self._records)
        if incident_id is not None:
            results = [r for r in results if r.incident_id == incident_id]
        if category is not None:
            results = [r for r in results if r.category == category]
        return results[-limit:]

    def add_rule(
        self,
        rule_name: str,
        category: TriageCategory = TriageCategory.APPLICATION,
        priority: TriagePriority = TriagePriority.P3_MEDIUM,
        match_pattern: str = "",
        hit_count: int = 0,
    ) -> TriageRule:
        rule = TriageRule(
            rule_name=rule_name,
            category=category,
            priority=priority,
            match_pattern=match_pattern,
            hit_count=hit_count,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "auto_triage.rule_added",
            rule_name=rule_name,
            category=category.value,
            priority=priority.value,
        )
        return rule

    # -- domain operations -----------------------------------------------

    def analyze_triage_accuracy(self, incident_id: str) -> dict[str, Any]:
        """Analyze accuracy for a specific incident."""
        records = [r for r in self._records if r.incident_id == incident_id]
        if not records:
            return {"incident_id": incident_id, "status": "no_data"}
        latest = records[-1]
        conf_pct = self._confidence_to_pct(latest.confidence)
        return {
            "incident_id": incident_id,
            "category": latest.category.value,
            "priority": latest.priority.value,
            "confidence": latest.confidence.value,
            "confidence_pct": conf_pct,
            "assigned_team": latest.assigned_team,
            "triage_time_seconds": latest.triage_time_seconds,
            "meets_threshold": conf_pct >= self._min_confidence_pct,
        }

    def identify_misclassified(self) -> list[dict[str, Any]]:
        """Find triages with confidence below threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            conf_pct = self._confidence_to_pct(r.confidence)
            if conf_pct < self._min_confidence_pct:
                results.append(
                    {
                        "incident_id": r.incident_id,
                        "category": r.category.value,
                        "priority": r.priority.value,
                        "confidence": r.confidence.value,
                        "confidence_pct": conf_pct,
                        "gap_pct": round(self._min_confidence_pct - conf_pct, 2),
                    }
                )
        results.sort(key=lambda x: x["confidence_pct"])
        return results

    def rank_rules_by_hit_rate(self) -> list[dict[str, Any]]:
        """Rank rules by hit_count descending."""
        results: list[dict[str, Any]] = []
        for r in self._rules:
            results.append(
                {
                    "rule_name": r.rule_name,
                    "category": r.category.value,
                    "priority": r.priority.value,
                    "match_pattern": r.match_pattern,
                    "hit_count": r.hit_count,
                }
            )
        results.sort(key=lambda x: x["hit_count"], reverse=True)
        return results

    def detect_category_drift(self) -> list[dict[str, Any]]:
        """Detect category distribution changes."""
        if len(self._records) < 2:
            return []
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]
        first_dist: dict[str, int] = {}
        for r in first_half:
            key = r.category.value
            first_dist[key] = first_dist.get(key, 0) + 1
        second_dist: dict[str, int] = {}
        for r in second_half:
            key = r.category.value
            second_dist[key] = second_dist.get(key, 0) + 1
        all_cats = set(first_dist) | set(second_dist)
        results: list[dict[str, Any]] = []
        for cat in sorted(all_cats):
            first_pct = round(first_dist.get(cat, 0) / len(first_half) * 100, 2)
            second_pct = round(second_dist.get(cat, 0) / len(second_half) * 100, 2)
            drift = round(second_pct - first_pct, 2)
            if abs(drift) > 5.0:
                results.append(
                    {
                        "category": cat,
                        "first_half_pct": first_pct,
                        "second_half_pct": second_pct,
                        "drift_pct": drift,
                    }
                )
        results.sort(key=lambda x: abs(x["drift_pct"]), reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> AutoTriageReport:
        by_category: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for r in self._records:
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            by_priority[r.priority.value] = by_priority.get(r.priority.value, 0) + 1
        avg_time = (
            round(
                sum(r.triage_time_seconds for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        misclassified = sum(
            1
            for r in self._records
            if self._confidence_to_pct(r.confidence) < self._min_confidence_pct
        )
        recs: list[str] = []
        if misclassified > 0:
            recs.append(
                f"{misclassified} triage(s) below {self._min_confidence_pct}% confidence threshold"
            )
        low_conf = sum(1 for r in self._records if r.confidence == TriageConfidence.MANUAL_REQUIRED)
        if low_conf > 0:
            recs.append(f"{low_conf} triage(s) require manual classification")
        if not recs:
            recs.append("Auto-triage accuracy meets targets")
        return AutoTriageReport(
            total_triages=len(self._records),
            total_rules=len(self._rules),
            avg_triage_time_seconds=avg_time,
            by_category=by_category,
            by_priority=by_priority,
            misclassified_count=misclassified,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("auto_triage.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_triages": len(self._records),
            "total_rules": len(self._rules),
            "min_confidence_pct": self._min_confidence_pct,
            "category_distribution": category_dist,
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
