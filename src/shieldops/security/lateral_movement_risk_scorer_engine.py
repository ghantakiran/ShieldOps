"""Lateral Movement Risk Scorer Engine —
score lateral movement risk in networks,
detect movement chains, rank paths by risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MovementPattern(StrEnum):
    CREDENTIAL_REUSE = "credential_reuse"
    PASS_THE_HASH = "pass_the_hash"  # noqa: S105
    RDP_HOP = "rdp_hop"
    SERVICE_ABUSE = "service_abuse"


class DetectionMethod(StrEnum):
    GRAPH_ANALYSIS = "graph_analysis"
    TRAFFIC_PATTERN = "traffic_pattern"
    CREDENTIAL_TRACKING = "credential_tracking"
    BEHAVIORAL = "behavioral"


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class LateralMovementRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_host: str = ""
    target_host: str = ""
    movement_pattern: MovementPattern = MovementPattern.CREDENTIAL_REUSE
    detection_method: DetectionMethod = DetectionMethod.GRAPH_ANALYSIS
    risk_level: RiskLevel = RiskLevel.LOW
    risk_score: float = 0.0
    hop_count: int = 1
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LateralMovementAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_host: str = ""
    target_host: str = ""
    movement_pattern: MovementPattern = MovementPattern.CREDENTIAL_REUSE
    composite_risk: float = 0.0
    chain_detected: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LateralMovementReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_movement_pattern: dict[str, int] = Field(default_factory=dict)
    by_detection_method: dict[str, int] = Field(default_factory=dict)
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    critical_paths: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class LateralMovementRiskScorerEngine:
    """Score lateral movement risk in networks, detect movement chains,
    and rank paths by risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[LateralMovementRecord] = []
        self._analyses: dict[str, LateralMovementAnalysis] = {}
        logger.info(
            "lateral_movement_risk_scorer_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        source_host: str = "",
        target_host: str = "",
        movement_pattern: MovementPattern = MovementPattern.CREDENTIAL_REUSE,
        detection_method: DetectionMethod = DetectionMethod.GRAPH_ANALYSIS,
        risk_level: RiskLevel = RiskLevel.LOW,
        risk_score: float = 0.0,
        hop_count: int = 1,
        description: str = "",
    ) -> LateralMovementRecord:
        record = LateralMovementRecord(
            source_host=source_host,
            target_host=target_host,
            movement_pattern=movement_pattern,
            detection_method=detection_method,
            risk_level=risk_level,
            risk_score=risk_score,
            hop_count=hop_count,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "lateral_movement_risk.record_added",
            record_id=record.id,
            source_host=source_host,
            target_host=target_host,
        )
        return record

    def process(self, key: str) -> LateralMovementAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        level_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        w = level_weights.get(rec.risk_level.value, 1)
        composite = round(w * rec.risk_score * (1 + rec.hop_count * 0.1), 2)
        chain = rec.hop_count > 2
        analysis = LateralMovementAnalysis(
            source_host=rec.source_host,
            target_host=rec.target_host,
            movement_pattern=rec.movement_pattern,
            composite_risk=composite,
            chain_detected=chain,
            description=(f"{rec.source_host} -> {rec.target_host} hops={rec.hop_count}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> LateralMovementReport:
        by_mp: dict[str, int] = {}
        by_dm: dict[str, int] = {}
        by_rl: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.movement_pattern.value
            by_mp[k] = by_mp.get(k, 0) + 1
            k2 = r.detection_method.value
            by_dm[k2] = by_dm.get(k2, 0) + 1
            k3 = r.risk_level.value
            by_rl[k3] = by_rl.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        critical_paths = list(
            {
                f"{r.source_host}->{r.target_host}"
                for r in self._records
                if r.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)
            }
        )[:10]
        recs: list[str] = []
        if critical_paths:
            recs.append(f"{len(critical_paths)} critical lateral movement paths detected")
        if not recs:
            recs.append("No significant lateral movement detected")
        return LateralMovementReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_movement_pattern=by_mp,
            by_detection_method=by_dm,
            by_risk_level=by_rl,
            critical_paths=critical_paths,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        rl_dist: dict[str, int] = {}
        for r in self._records:
            k = r.risk_level.value
            rl_dist[k] = rl_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "risk_level_distribution": rl_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("lateral_movement_risk_scorer_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def score_lateral_movement_risk(self) -> list[dict[str, Any]]:
        """Score lateral movement risk per source host."""
        host_data: dict[str, list[LateralMovementRecord]] = {}
        for r in self._records:
            host_data.setdefault(r.source_host, []).append(r)
        level_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        results: list[dict[str, Any]] = []
        for host, recs in host_data.items():
            total_score = sum(
                level_weights.get(rec.risk_level.value, 1) * rec.risk_score for rec in recs
            )
            targets = list({rec.target_host for rec in recs})
            results.append(
                {
                    "source_host": host,
                    "total_risk_score": round(total_score, 2),
                    "unique_targets": len(targets),
                    "max_hop_count": max(rec.hop_count for rec in recs),
                    "movement_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["total_risk_score"], reverse=True)
        return results

    def detect_movement_chains(self) -> list[dict[str, Any]]:
        """Detect multi-hop lateral movement chains."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            chain_key = f"{r.source_host}->{r.target_host}"
            if r.hop_count > 2 and chain_key not in seen:
                seen.add(chain_key)
                results.append(
                    {
                        "chain": chain_key,
                        "source_host": r.source_host,
                        "target_host": r.target_host,
                        "hop_count": r.hop_count,
                        "movement_pattern": r.movement_pattern.value,
                        "risk_score": r.risk_score,
                    }
                )
        results.sort(key=lambda x: x["hop_count"], reverse=True)
        return results

    def rank_paths_by_risk(self) -> list[dict[str, Any]]:
        """Rank lateral movement paths by composite risk."""
        level_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        path_scores: dict[str, float] = {}
        for r in self._records:
            path_key = f"{r.source_host}->{r.target_host}"
            w = level_weights.get(r.risk_level.value, 1)
            path_scores[path_key] = path_scores.get(path_key, 0.0) + (r.risk_score * w)
        results: list[dict[str, Any]] = []
        for path, score in path_scores.items():
            results.append(
                {
                    "path": path,
                    "composite_risk": round(score, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["composite_risk"], reverse=True)
        for idx, entry in enumerate(results, 1):
            entry["rank"] = idx
        return results
