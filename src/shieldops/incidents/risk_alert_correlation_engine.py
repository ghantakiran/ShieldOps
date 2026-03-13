"""Risk Alert Correlation Engine
correlate risk alerts, build attack timelines,
compute correlation confidence."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CorrelationType(StrEnum):
    TEMPORAL = "temporal"
    ENTITY = "entity"
    TECHNIQUE = "technique"
    CAMPAIGN = "campaign"


class CorrelationStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"


class AlertRelation(StrEnum):
    CAUSAL = "causal"
    CONCURRENT = "concurrent"
    SEQUENTIAL = "sequential"
    INDEPENDENT = "independent"


# --- Models ---


class RiskAlertCorrelationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = ""
    corr_type: CorrelationType = CorrelationType.TEMPORAL
    strength: CorrelationStrength = CorrelationStrength.MODERATE
    relation: AlertRelation = AlertRelation.CONCURRENT
    alert_id_a: str = ""
    alert_id_b: str = ""
    entity_id: str = ""
    confidence: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskAlertCorrelationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = ""
    corr_type: CorrelationType = CorrelationType.TEMPORAL
    confidence_score: float = 0.0
    timeline_length: int = 0
    is_campaign: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskAlertCorrelationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_confidence: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_strength: dict[str, int] = Field(default_factory=dict)
    by_relation: dict[str, int] = Field(default_factory=dict)
    campaign_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RiskAlertCorrelationEngine:
    """Correlate risk alerts, build attack timelines,
    compute correlation confidence."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[RiskAlertCorrelationRecord] = []
        self._analyses: dict[str, RiskAlertCorrelationAnalysis] = {}
        logger.info(
            "risk_alert_correlation_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        correlation_id: str = "",
        corr_type: CorrelationType = (CorrelationType.TEMPORAL),
        strength: CorrelationStrength = (CorrelationStrength.MODERATE),
        relation: AlertRelation = (AlertRelation.CONCURRENT),
        alert_id_a: str = "",
        alert_id_b: str = "",
        entity_id: str = "",
        confidence: float = 0.0,
        description: str = "",
    ) -> RiskAlertCorrelationRecord:
        record = RiskAlertCorrelationRecord(
            correlation_id=correlation_id,
            corr_type=corr_type,
            strength=strength,
            relation=relation,
            alert_id_a=alert_id_a,
            alert_id_b=alert_id_b,
            entity_id=entity_id,
            confidence=confidence,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "risk_alert_correlation.record_added",
            record_id=record.id,
            correlation_id=correlation_id,
        )
        return record

    def process(self, key: str) -> RiskAlertCorrelationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        entity_corrs = [r for r in self._records if r.entity_id == rec.entity_id]
        timeline_len = len(entity_corrs)
        is_campaign = rec.corr_type == CorrelationType.CAMPAIGN or timeline_len >= 5
        analysis = RiskAlertCorrelationAnalysis(
            correlation_id=rec.correlation_id,
            corr_type=rec.corr_type,
            confidence_score=round(rec.confidence, 2),
            timeline_length=timeline_len,
            is_campaign=is_campaign,
            description=(f"Correlation {rec.correlation_id} confidence={rec.confidence}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> RiskAlertCorrelationReport:
        by_t: dict[str, int] = {}
        by_s: dict[str, int] = {}
        by_r: dict[str, int] = {}
        confs: list[float] = []
        for r in self._records:
            k = r.corr_type.value
            by_t[k] = by_t.get(k, 0) + 1
            k2 = r.strength.value
            by_s[k2] = by_s.get(k2, 0) + 1
            k3 = r.relation.value
            by_r[k3] = by_r.get(k3, 0) + 1
            confs.append(r.confidence)
        avg = round(sum(confs) / len(confs), 2) if confs else 0.0
        campaigns = by_t.get("campaign", 0)
        recs: list[str] = []
        if campaigns > 0:
            recs.append(f"{campaigns} campaign correlations")
        strong = by_s.get("strong", 0)
        if strong > 0:
            recs.append(f"{strong} strong correlations found")
        if not recs:
            recs.append("No notable correlations")
        return RiskAlertCorrelationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_confidence=avg,
            by_type=by_t,
            by_strength=by_s,
            by_relation=by_r,
            campaign_count=campaigns,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            k = r.corr_type.value
            type_dist[k] = type_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "type_distribution": type_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("risk_alert_correlation_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def correlate_risk_alerts(
        self,
    ) -> list[dict[str, Any]]:
        """Group correlated alerts by entity."""
        entity_alerts: dict[str, list[str]] = {}
        for r in self._records:
            entity_alerts.setdefault(r.entity_id, [])
            if r.alert_id_a not in (entity_alerts[r.entity_id]):
                entity_alerts[r.entity_id].append(r.alert_id_a)
            if r.alert_id_b not in (entity_alerts[r.entity_id]):
                entity_alerts[r.entity_id].append(r.alert_id_b)
        results: list[dict[str, Any]] = []
        for eid, alerts in entity_alerts.items():
            results.append(
                {
                    "entity_id": eid,
                    "correlated_alerts": alerts,
                    "alert_count": len(alerts),
                }
            )
        results.sort(
            key=lambda x: x["alert_count"],
            reverse=True,
        )
        return results

    def build_attack_timeline(
        self,
    ) -> list[dict[str, Any]]:
        """Build timeline of alerts per entity."""
        entity_events: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            entity_events.setdefault(r.entity_id, []).append(
                {
                    "correlation_id": (r.correlation_id),
                    "type": r.corr_type.value,
                    "relation": r.relation.value,
                    "timestamp": r.created_at,
                }
            )
        results: list[dict[str, Any]] = []
        for eid, events in entity_events.items():
            events.sort(key=lambda x: x["timestamp"])
            results.append(
                {
                    "entity_id": eid,
                    "timeline": events,
                    "event_count": len(events),
                }
            )
        results.sort(
            key=lambda x: x["event_count"],
            reverse=True,
        )
        return results

    def compute_correlation_confidence(
        self,
    ) -> dict[str, Any]:
        """Compute overall correlation confidence."""
        if not self._records:
            return {
                "avg_confidence": 0.0,
                "by_type": {},
            }
        type_confs: dict[str, list[float]] = {}
        for r in self._records:
            k = r.corr_type.value
            type_confs.setdefault(k, []).append(r.confidence)
        by_type: dict[str, float] = {}
        all_confs: list[float] = []
        for t, confs in type_confs.items():
            avg = round(sum(confs) / len(confs), 2)
            by_type[t] = avg
            all_confs.extend(confs)
        overall = round(sum(all_confs) / len(all_confs), 2) if all_confs else 0.0
        return {
            "avg_confidence": overall,
            "by_type": by_type,
        }
