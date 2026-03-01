"""Security Event Correlator — correlate events to detect attack chains."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EventSource(StrEnum):
    FIREWALL = "firewall"
    IDS = "ids"
    ENDPOINT = "endpoint"
    CLOUD_TRAIL = "cloud_trail"
    APPLICATION = "application"


class ChainStage(StrEnum):
    RECONNAISSANCE = "reconnaissance"
    INITIAL_ACCESS = "initial_access"
    LATERAL_MOVEMENT = "lateral_movement"
    EXFILTRATION = "exfiltration"
    PERSISTENCE = "persistence"


class ThreatLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    BENIGN = "benign"


# --- Models ---


class EventRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str = ""
    source: EventSource = EventSource.FIREWALL
    chain_stage: ChainStage = ChainStage.RECONNAISSANCE
    threat_level: ThreatLevel = ThreatLevel.BENIGN
    confidence_score: float = 0.0
    team: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class EventChain(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chain_name: str = ""
    source: EventSource = EventSource.FIREWALL
    chain_stage: ChainStage = ChainStage.RECONNAISSANCE
    event_count: int = 0
    avg_threat_score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class SecurityEventReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_chains: int = 0
    active_chains: int = 0
    critical_events: int = 0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_threat: dict[str, int] = Field(default_factory=dict)
    attack_chain_alerts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityEventCorrelator:
    """Correlate security events across sources to detect attack chains."""

    def __init__(
        self,
        max_records: int = 200000,
        min_threat_confidence_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_threat_confidence_pct = min_threat_confidence_pct
        self._records: list[EventRecord] = []
        self._chains: list[EventChain] = []
        logger.info(
            "event_correlator.initialized",
            max_records=max_records,
            min_threat_confidence_pct=min_threat_confidence_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_event(
        self,
        event_id: str,
        source: EventSource = EventSource.FIREWALL,
        chain_stage: ChainStage = ChainStage.RECONNAISSANCE,
        threat_level: ThreatLevel = ThreatLevel.BENIGN,
        confidence_score: float = 0.0,
        team: str = "",
        details: str = "",
    ) -> EventRecord:
        record = EventRecord(
            event_id=event_id,
            source=source,
            chain_stage=chain_stage,
            threat_level=threat_level,
            confidence_score=confidence_score,
            team=team,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "event_correlator.event_recorded",
            record_id=record.id,
            event_id=event_id,
            source=source.value,
            chain_stage=chain_stage.value,
        )
        return record

    def get_event(self, record_id: str) -> EventRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_events(
        self,
        source: EventSource | None = None,
        chain_stage: ChainStage | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EventRecord]:
        results = list(self._records)
        if source is not None:
            results = [r for r in results if r.source == source]
        if chain_stage is not None:
            results = [r for r in results if r.chain_stage == chain_stage]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_chain(
        self,
        chain_name: str,
        source: EventSource = EventSource.FIREWALL,
        chain_stage: ChainStage = ChainStage.RECONNAISSANCE,
        event_count: int = 0,
        avg_threat_score: float = 0.0,
    ) -> EventChain:
        chain = EventChain(
            chain_name=chain_name,
            source=source,
            chain_stage=chain_stage,
            event_count=event_count,
            avg_threat_score=avg_threat_score,
        )
        self._chains.append(chain)
        if len(self._chains) > self._max_records:
            self._chains = self._chains[-self._max_records :]
        logger.info(
            "event_correlator.chain_added",
            chain_name=chain_name,
            source=source.value,
            chain_stage=chain_stage.value,
        )
        return chain

    # -- domain operations --------------------------------------------------

    def analyze_event_distribution(self) -> dict[str, Any]:
        """Group by source; return count and avg confidence."""
        source_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.source.value
            source_data.setdefault(key, []).append(r.confidence_score)
        result: dict[str, Any] = {}
        for src, scores in source_data.items():
            result[src] = {
                "count": len(scores),
                "avg_confidence": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_critical_events(
        self,
    ) -> list[dict[str, Any]]:
        """Return events where threat_level is CRITICAL."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.threat_level == ThreatLevel.CRITICAL:
                results.append(
                    {
                        "record_id": r.id,
                        "event_id": r.event_id,
                        "source": r.source.value,
                        "chain_stage": r.chain_stage.value,
                        "confidence_score": (r.confidence_score),
                        "team": r.team,
                    }
                )
        results.sort(
            key=lambda x: x["confidence_score"],
            reverse=True,
        )
        return results

    def rank_by_threat_score(self) -> list[dict[str, Any]]:
        """Group by team, avg confidence, sort descending."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team, []).append(r.confidence_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            results.append(
                {
                    "team": team,
                    "avg_confidence": round(sum(scores) / len(scores), 2),
                    "event_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_confidence"], reverse=True)
        return results

    def detect_event_trends(self) -> dict[str, Any]:
        """Split-half comparison on confidence; delta 5.0."""
        if len(self._records) < 2:
            return {
                "trend": "insufficient_data",
                "delta": 0.0,
            }
        scores = [r.confidence_score for r in self._records]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> SecurityEventReport:
        by_source: dict[str, int] = {}
        by_stage: dict[str, int] = {}
        by_threat: dict[str, int] = {}
        for r in self._records:
            by_source[r.source.value] = by_source.get(r.source.value, 0) + 1
            by_stage[r.chain_stage.value] = by_stage.get(r.chain_stage.value, 0) + 1
            by_threat[r.threat_level.value] = by_threat.get(r.threat_level.value, 0) + 1
        critical_events = sum(1 for r in self._records if r.threat_level == ThreatLevel.CRITICAL)
        active_chains = len(self._chains)
        critical_list = self.identify_critical_events()
        attack_chain_alerts = [c["event_id"] for c in critical_list]
        recs: list[str] = []
        if critical_events > 0:
            recs.append(f"{critical_events} critical event(s) detected — escalate immediately")
        low_conf = sum(
            1 for r in self._records if r.confidence_score < self._min_threat_confidence_pct
        )
        if low_conf > 0:
            recs.append(
                f"{low_conf} event(s) below confidence"
                " threshold"
                f" ({self._min_threat_confidence_pct}%)"
            )
        if not recs:
            recs.append("Security event levels are healthy")
        return SecurityEventReport(
            total_records=len(self._records),
            total_chains=len(self._chains),
            active_chains=active_chains,
            critical_events=critical_events,
            by_source=by_source,
            by_stage=by_stage,
            by_threat=by_threat,
            attack_chain_alerts=attack_chain_alerts,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._chains.clear()
        logger.info("event_correlator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        source_dist: dict[str, int] = {}
        for r in self._records:
            key = r.source.value
            source_dist[key] = source_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_chains": len(self._chains),
            "min_threat_confidence_pct": (self._min_threat_confidence_pct),
            "source_distribution": source_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_events": len({r.event_id for r in self._records}),
        }
