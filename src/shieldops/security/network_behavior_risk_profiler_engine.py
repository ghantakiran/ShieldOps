"""Network Behavior Risk Profiler Engine —
profile network behavior risk,
detect malicious patterns, rank hosts by risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BehaviorCategory(StrEnum):
    SCANNING = "scanning"
    BEACONING = "beaconing"
    TUNNELING = "tunneling"
    EXFILTRATION = "exfiltration"


class ProfileMethod(StrEnum):
    FLOW_ANALYSIS = "flow_analysis"
    PACKET_INSPECTION = "packet_inspection"
    STATISTICAL = "statistical"
    ML_BASED = "ml_based"


class ThreatLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class NetworkBehaviorRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    host_id: str = ""
    behavior_category: BehaviorCategory = BehaviorCategory.SCANNING
    profile_method: ProfileMethod = ProfileMethod.FLOW_ANALYSIS
    threat_level: ThreatLevel = ThreatLevel.LOW
    risk_score: float = 0.0
    connection_count: int = 0
    bytes_transferred: float = 0.0
    destination_ips: list[str] = Field(default_factory=list)
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class NetworkBehaviorAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    host_id: str = ""
    behavior_category: BehaviorCategory = BehaviorCategory.SCANNING
    composite_risk: float = 0.0
    malicious_pattern: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class NetworkBehaviorReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_behavior_category: dict[str, int] = Field(default_factory=dict)
    by_profile_method: dict[str, int] = Field(default_factory=dict)
    by_threat_level: dict[str, int] = Field(default_factory=dict)
    malicious_hosts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class NetworkBehaviorRiskProfilerEngine:
    """Profile network behavior risk, detect malicious patterns,
    and rank hosts by risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[NetworkBehaviorRecord] = []
        self._analyses: dict[str, NetworkBehaviorAnalysis] = {}
        logger.info(
            "network_behavior_risk_profiler_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        host_id: str = "",
        behavior_category: BehaviorCategory = BehaviorCategory.SCANNING,
        profile_method: ProfileMethod = ProfileMethod.FLOW_ANALYSIS,
        threat_level: ThreatLevel = ThreatLevel.LOW,
        risk_score: float = 0.0,
        connection_count: int = 0,
        bytes_transferred: float = 0.0,
        destination_ips: list[str] | None = None,
        description: str = "",
    ) -> NetworkBehaviorRecord:
        record = NetworkBehaviorRecord(
            host_id=host_id,
            behavior_category=behavior_category,
            profile_method=profile_method,
            threat_level=threat_level,
            risk_score=risk_score,
            connection_count=connection_count,
            bytes_transferred=bytes_transferred,
            destination_ips=destination_ips or [],
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "network_behavior_risk.record_added",
            record_id=record.id,
            host_id=host_id,
        )
        return record

    def process(self, key: str) -> NetworkBehaviorAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        tl_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        w = tl_weights.get(rec.threat_level.value, 1)
        composite = round(
            w * rec.risk_score * (1 + rec.connection_count * 0.001),
            2,
        )
        malicious = (
            rec.behavior_category
            in (
                BehaviorCategory.BEACONING,
                BehaviorCategory.EXFILTRATION,
            )
            and rec.risk_score > 0.65
        )
        analysis = NetworkBehaviorAnalysis(
            host_id=rec.host_id,
            behavior_category=rec.behavior_category,
            composite_risk=composite,
            malicious_pattern=malicious,
            description=(
                f"Host {rec.host_id} {rec.behavior_category.value} conns={rec.connection_count}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> NetworkBehaviorReport:
        by_bc: dict[str, int] = {}
        by_pm: dict[str, int] = {}
        by_tl: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.behavior_category.value
            by_bc[k] = by_bc.get(k, 0) + 1
            k2 = r.profile_method.value
            by_pm[k2] = by_pm.get(k2, 0) + 1
            k3 = r.threat_level.value
            by_tl[k3] = by_tl.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        malicious_hosts = list(
            {
                r.host_id
                for r in self._records
                if r.threat_level in (ThreatLevel.CRITICAL, ThreatLevel.HIGH)
            }
        )[:10]
        recs: list[str] = []
        if malicious_hosts:
            recs.append(f"{len(malicious_hosts)} hosts with malicious network behavior")
        if not recs:
            recs.append("Network behavior within normal parameters")
        return NetworkBehaviorReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_behavior_category=by_bc,
            by_profile_method=by_pm,
            by_threat_level=by_tl,
            malicious_hosts=malicious_hosts,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        bc_dist: dict[str, int] = {}
        for r in self._records:
            k = r.behavior_category.value
            bc_dist[k] = bc_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "behavior_category_distribution": bc_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("network_behavior_risk_profiler_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def profile_network_behavior(self) -> list[dict[str, Any]]:
        """Profile aggregated network behavior per host."""
        host_data: dict[str, list[NetworkBehaviorRecord]] = {}
        for r in self._records:
            host_data.setdefault(r.host_id, []).append(r)
        tl_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        results: list[dict[str, Any]] = []
        for hid, recs in host_data.items():
            total_risk = sum(
                tl_weights.get(rec.threat_level.value, 1) * rec.risk_score for rec in recs
            )
            total_bytes = sum(rec.bytes_transferred for rec in recs)
            categories = list({rec.behavior_category.value for rec in recs})
            unique_dsts: set[str] = set()
            for rec in recs:
                unique_dsts.update(rec.destination_ips)
            results.append(
                {
                    "host_id": hid,
                    "composite_risk": round(total_risk, 2),
                    "total_bytes_transferred": round(total_bytes, 2),
                    "behavior_categories": categories,
                    "unique_destinations": len(unique_dsts),
                    "event_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["composite_risk"], reverse=True)
        return results

    def detect_malicious_patterns(self) -> list[dict[str, Any]]:
        """Detect hosts exhibiting malicious network patterns."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.behavior_category in (BehaviorCategory.BEACONING, BehaviorCategory.EXFILTRATION)
                and r.risk_score > 0.65
                and r.host_id not in seen
            ):
                seen.add(r.host_id)
                results.append(
                    {
                        "host_id": r.host_id,
                        "behavior_category": r.behavior_category.value,
                        "threat_level": r.threat_level.value,
                        "risk_score": r.risk_score,
                        "connection_count": r.connection_count,
                        "bytes_transferred": r.bytes_transferred,
                    }
                )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def rank_hosts_by_risk(self) -> list[dict[str, Any]]:
        """Rank hosts by total network risk score."""
        tl_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        host_scores: dict[str, float] = {}
        for r in self._records:
            w = tl_weights.get(r.threat_level.value, 1)
            host_scores[r.host_id] = host_scores.get(r.host_id, 0.0) + (w * r.risk_score)
        results: list[dict[str, Any]] = []
        for hid, score in host_scores.items():
            results.append(
                {
                    "host_id": hid,
                    "total_risk_score": round(score, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["total_risk_score"], reverse=True)
        for idx, entry in enumerate(results, 1):
            entry["rank"] = idx
        return results
