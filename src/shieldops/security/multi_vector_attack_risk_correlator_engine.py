"""Multi-Vector Attack Risk Correlator Engine —
correlate multi-vector attack risks,
detect coordinated campaigns, rank campaigns by risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AttackVector(StrEnum):
    NETWORK = "network"
    APPLICATION = "application"
    IDENTITY = "identity"
    PHYSICAL = "physical"


class CorrelationMethod(StrEnum):
    TEMPORAL = "temporal"
    CAUSAL = "causal"
    STATISTICAL = "statistical"
    GRAPH = "graph"


class CampaignStatus(StrEnum):
    ACTIVE = "active"
    DORMANT = "dormant"
    ESCALATING = "escalating"
    CONTAINED = "contained"


# --- Models ---


class AttackCorrelationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_id: str = ""
    attack_vector: AttackVector = AttackVector.NETWORK
    correlation_method: CorrelationMethod = CorrelationMethod.TEMPORAL
    campaign_status: CampaignStatus = CampaignStatus.DORMANT
    risk_score: float = 0.0
    vector_count: int = 1
    target_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AttackCorrelationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_id: str = ""
    campaign_status: CampaignStatus = CampaignStatus.DORMANT
    composite_risk: float = 0.0
    coordinated_attack: bool = False
    dominant_vector: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AttackCorrelationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_attack_vector: dict[str, int] = Field(default_factory=dict)
    by_correlation_method: dict[str, int] = Field(default_factory=dict)
    by_campaign_status: dict[str, int] = Field(default_factory=dict)
    active_campaigns: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MultiVectorAttackRiskCorrelatorEngine:
    """Correlate multi-vector attack risks, detect coordinated campaigns,
    and rank campaigns by risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[AttackCorrelationRecord] = []
        self._analyses: dict[str, AttackCorrelationAnalysis] = {}
        logger.info(
            "multi_vector_attack_risk_correlator_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        campaign_id: str = "",
        attack_vector: AttackVector = AttackVector.NETWORK,
        correlation_method: CorrelationMethod = CorrelationMethod.TEMPORAL,
        campaign_status: CampaignStatus = CampaignStatus.DORMANT,
        risk_score: float = 0.0,
        vector_count: int = 1,
        target_count: int = 0,
        description: str = "",
    ) -> AttackCorrelationRecord:
        record = AttackCorrelationRecord(
            campaign_id=campaign_id,
            attack_vector=attack_vector,
            correlation_method=correlation_method,
            campaign_status=campaign_status,
            risk_score=risk_score,
            vector_count=vector_count,
            target_count=target_count,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "multi_vector_attack_risk.record_added",
            record_id=record.id,
            campaign_id=campaign_id,
        )
        return record

    def process(self, key: str) -> AttackCorrelationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        status_weights = {
            "escalating": 4,
            "active": 3,
            "dormant": 2,
            "contained": 1,
        }
        w = status_weights.get(rec.campaign_status.value, 1)
        composite = round(w * rec.risk_score * (1 + rec.vector_count * 0.2), 2)
        coordinated = rec.vector_count > 2 and rec.campaign_status in (
            CampaignStatus.ACTIVE,
            CampaignStatus.ESCALATING,
        )
        analysis = AttackCorrelationAnalysis(
            campaign_id=rec.campaign_id,
            campaign_status=rec.campaign_status,
            composite_risk=composite,
            coordinated_attack=coordinated,
            dominant_vector=rec.attack_vector.value,
            description=(
                f"Campaign {rec.campaign_id} vectors={rec.vector_count} targets={rec.target_count}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> AttackCorrelationReport:
        by_av: dict[str, int] = {}
        by_cm: dict[str, int] = {}
        by_cs: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.attack_vector.value
            by_av[k] = by_av.get(k, 0) + 1
            k2 = r.correlation_method.value
            by_cm[k2] = by_cm.get(k2, 0) + 1
            k3 = r.campaign_status.value
            by_cs[k3] = by_cs.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        active_campaigns = list(
            {
                r.campaign_id
                for r in self._records
                if r.campaign_status in (CampaignStatus.ACTIVE, CampaignStatus.ESCALATING)
            }
        )[:10]
        recs: list[str] = []
        if active_campaigns:
            recs.append(f"{len(active_campaigns)} active/escalating attack campaigns detected")
        if not recs:
            recs.append("No active coordinated attack campaigns detected")
        return AttackCorrelationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_attack_vector=by_av,
            by_correlation_method=by_cm,
            by_campaign_status=by_cs,
            active_campaigns=active_campaigns,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        av_dist: dict[str, int] = {}
        for r in self._records:
            k = r.attack_vector.value
            av_dist[k] = av_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "attack_vector_distribution": av_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("multi_vector_attack_risk_correlator_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def correlate_attack_vectors(self) -> list[dict[str, Any]]:
        """Correlate attack vectors across campaigns."""
        campaign_data: dict[str, list[AttackCorrelationRecord]] = {}
        for r in self._records:
            campaign_data.setdefault(r.campaign_id, []).append(r)
        results: list[dict[str, Any]] = []
        for cid, recs in campaign_data.items():
            vectors = list({rec.attack_vector.value for rec in recs})
            total_risk = sum(rec.risk_score for rec in recs)
            max_targets = max(rec.target_count for rec in recs)
            methods = list({rec.correlation_method.value for rec in recs})
            results.append(
                {
                    "campaign_id": cid,
                    "attack_vectors": vectors,
                    "vector_count": len(vectors),
                    "correlation_methods": methods,
                    "total_risk": round(total_risk, 2),
                    "max_targets": max_targets,
                    "event_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["total_risk"], reverse=True)
        return results

    def detect_coordinated_campaigns(self) -> list[dict[str, Any]]:
        """Detect coordinated multi-vector attack campaigns."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.vector_count > 2
                and r.campaign_status in (CampaignStatus.ACTIVE, CampaignStatus.ESCALATING)
                and r.campaign_id not in seen
            ):
                seen.add(r.campaign_id)
                results.append(
                    {
                        "campaign_id": r.campaign_id,
                        "status": r.campaign_status.value,
                        "vector_count": r.vector_count,
                        "dominant_vector": r.attack_vector.value,
                        "risk_score": r.risk_score,
                        "target_count": r.target_count,
                    }
                )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def rank_campaigns_by_risk(self) -> list[dict[str, Any]]:
        """Rank attack campaigns by composite risk score."""
        status_weights = {
            "escalating": 4,
            "active": 3,
            "dormant": 2,
            "contained": 1,
        }
        campaign_scores: dict[str, float] = {}
        for r in self._records:
            w = status_weights.get(r.campaign_status.value, 1)
            campaign_scores[r.campaign_id] = campaign_scores.get(r.campaign_id, 0.0) + (
                w * r.risk_score
            )
        results: list[dict[str, Any]] = []
        for cid, score in campaign_scores.items():
            results.append(
                {
                    "campaign_id": cid,
                    "composite_risk": round(score, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["composite_risk"], reverse=True)
        for idx, entry in enumerate(results, 1):
            entry["rank"] = idx
        return results
