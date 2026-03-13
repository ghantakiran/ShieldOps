"""Multi-Hop Root Cause Engine —
model root cause analysis as multi-hop reasoning chains,
validate hop dependencies, rank chains by confidence."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HopDepth(StrEnum):
    SINGLE_HOP = "single_hop"
    TWO_HOP = "two_hop"
    THREE_HOP = "three_hop"
    DEEP_HOP = "deep_hop"


class CausalLinkType(StrEnum):
    DIRECT = "direct"
    INDIRECT = "indirect"
    CORRELATED = "correlated"
    SPECULATIVE = "speculative"


class ChainStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BROKEN = "broken"
    UNVERIFIED = "unverified"


# --- Models ---


class MultiHopRootCauseRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chain_id: str = ""
    hop_depth: HopDepth = HopDepth.SINGLE_HOP
    causal_link_type: CausalLinkType = CausalLinkType.DIRECT
    chain_status: ChainStatus = ChainStatus.UNVERIFIED
    confidence_score: float = 0.0
    hop_count: int = 1
    root_cause: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MultiHopRootCauseAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chain_id: str = ""
    hop_depth: HopDepth = HopDepth.SINGLE_HOP
    chain_status: ChainStatus = ChainStatus.UNVERIFIED
    dependency_valid: bool = False
    confidence_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MultiHopRootCauseReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_confidence_score: float = 0.0
    by_hop_depth: dict[str, int] = Field(default_factory=dict)
    by_causal_link: dict[str, int] = Field(default_factory=dict)
    by_chain_status: dict[str, int] = Field(default_factory=dict)
    top_chains: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MultiHopRootCauseEngine:
    """Model root cause analysis as multi-hop reasoning chains,
    validate hop dependencies, rank chains by confidence."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[MultiHopRootCauseRecord] = []
        self._analyses: dict[str, MultiHopRootCauseAnalysis] = {}
        logger.info("multi_hop_root_cause_engine.init", max_records=max_records)

    def add_record(
        self,
        chain_id: str = "",
        hop_depth: HopDepth = HopDepth.SINGLE_HOP,
        causal_link_type: CausalLinkType = CausalLinkType.DIRECT,
        chain_status: ChainStatus = ChainStatus.UNVERIFIED,
        confidence_score: float = 0.0,
        hop_count: int = 1,
        root_cause: str = "",
        description: str = "",
    ) -> MultiHopRootCauseRecord:
        record = MultiHopRootCauseRecord(
            chain_id=chain_id,
            hop_depth=hop_depth,
            causal_link_type=causal_link_type,
            chain_status=chain_status,
            confidence_score=confidence_score,
            hop_count=hop_count,
            root_cause=root_cause,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "multi_hop_root_cause.record_added",
            record_id=record.id,
            chain_id=chain_id,
        )
        return record

    def process(self, key: str) -> MultiHopRootCauseAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        dep_valid = rec.chain_status in (ChainStatus.COMPLETE, ChainStatus.PARTIAL)
        analysis = MultiHopRootCauseAnalysis(
            chain_id=rec.chain_id,
            hop_depth=rec.hop_depth,
            chain_status=rec.chain_status,
            dependency_valid=dep_valid,
            confidence_score=round(rec.confidence_score, 4),
            description=(f"Chain {rec.chain_id} depth={rec.hop_depth.value} hops={rec.hop_count}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> MultiHopRootCauseReport:
        by_hd: dict[str, int] = {}
        by_cl: dict[str, int] = {}
        by_cs: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.hop_depth.value
            by_hd[k] = by_hd.get(k, 0) + 1
            k2 = r.causal_link_type.value
            by_cl[k2] = by_cl.get(k2, 0) + 1
            k3 = r.chain_status.value
            by_cs[k3] = by_cs.get(k3, 0) + 1
            scores.append(r.confidence_score)
        avg_conf = round(sum(scores) / len(scores), 4) if scores else 0.0
        top: list[str] = list(
            {
                r.chain_id
                for r in self._records
                if r.chain_status == ChainStatus.COMPLETE and r.confidence_score >= 0.8
            }
        )[:10]
        recs: list[str] = []
        broken = by_cs.get("broken", 0)
        if broken:
            recs.append(f"{broken} broken causal chains need investigation")
        spec = by_cl.get("speculative", 0)
        if spec:
            recs.append(f"{spec} speculative links require evidence validation")
        if not recs:
            recs.append("Causal chain coverage is healthy")
        return MultiHopRootCauseReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_confidence_score=avg_conf,
            by_hop_depth=by_hd,
            by_causal_link=by_cl,
            by_chain_status=by_cs,
            top_chains=top,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.hop_depth.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "hop_depth_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("multi_hop_root_cause_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def trace_causal_chain(self) -> list[dict[str, Any]]:
        """Trace and return causal chains grouped by chain_id."""
        chain_map: dict[str, list[MultiHopRootCauseRecord]] = {}
        for r in self._records:
            chain_map.setdefault(r.chain_id, []).append(r)
        results: list[dict[str, Any]] = []
        for cid, chain_recs in chain_map.items():
            max_hops = max(r.hop_count for r in chain_recs)
            avg_conf = sum(r.confidence_score for r in chain_recs) / len(chain_recs)
            statuses = [r.chain_status.value for r in chain_recs]
            results.append(
                {
                    "chain_id": cid,
                    "max_hops": max_hops,
                    "avg_confidence": round(avg_conf, 4),
                    "statuses": list(set(statuses)),
                    "record_count": len(chain_recs),
                }
            )
        results.sort(key=lambda x: x["avg_confidence"], reverse=True)
        return results

    def validate_hop_dependencies(self) -> list[dict[str, Any]]:
        """Validate hop dependencies for each causal chain."""
        chain_map: dict[str, list[MultiHopRootCauseRecord]] = {}
        for r in self._records:
            chain_map.setdefault(r.chain_id, []).append(r)
        results: list[dict[str, Any]] = []
        for cid, chain_recs in chain_map.items():
            broken = [r for r in chain_recs if r.chain_status == ChainStatus.BROKEN]
            speculative = [
                r for r in chain_recs if r.causal_link_type == CausalLinkType.SPECULATIVE
            ]
            valid = len(broken) == 0
            results.append(
                {
                    "chain_id": cid,
                    "valid": valid,
                    "broken_hops": len(broken),
                    "speculative_links": len(speculative),
                    "total_hops": len(chain_recs),
                }
            )
        results.sort(key=lambda x: x["broken_hops"], reverse=True)
        return results

    def rank_chains_by_confidence(self) -> list[dict[str, Any]]:
        """Rank causal chains by average confidence score."""
        chain_scores: dict[str, list[float]] = {}
        chain_depth: dict[str, str] = {}
        for r in self._records:
            chain_scores.setdefault(r.chain_id, []).append(r.confidence_score)
            chain_depth[r.chain_id] = r.hop_depth.value
        results: list[dict[str, Any]] = []
        for cid, score_list in chain_scores.items():
            avg_c = sum(score_list) / len(score_list)
            results.append(
                {
                    "chain_id": cid,
                    "avg_confidence": round(avg_c, 4),
                    "hop_depth": chain_depth[cid],
                    "samples": len(score_list),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["avg_confidence"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
