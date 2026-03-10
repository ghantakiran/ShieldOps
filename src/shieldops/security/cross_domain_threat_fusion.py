"""Cross Domain Threat Fusion
fuse cross-domain signals, detect multi-stage attacks,
compute signal reliability."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SecurityDomain(StrEnum):
    ENDPOINT = "endpoint"
    NETWORK = "network"
    CLOUD = "cloud"
    IDENTITY = "identity"


class FusionMethod(StrEnum):
    CORRELATION = "correlation"
    ENRICHMENT = "enrichment"
    AGGREGATION = "aggregation"
    DEDUP = "dedup"


class SignalFidelity(StrEnum):
    VERIFIED = "verified"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    NOISE = "noise"


# --- Models ---


class ThreatFusionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signal_id: str = ""
    domain: SecurityDomain = SecurityDomain.ENDPOINT
    method: FusionMethod = FusionMethod.CORRELATION
    fidelity: SignalFidelity = SignalFidelity.PROBABLE
    reliability_score: float = 0.0
    correlated_signals: int = 0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ThreatFusionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signal_id: str = ""
    domain: SecurityDomain = SecurityDomain.ENDPOINT
    analysis_score: float = 0.0
    multi_stage_flag: bool = False
    fusion_confidence: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ThreatFusionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_reliability: float = 0.0
    avg_correlated: float = 0.0
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    by_fidelity: dict[str, int] = Field(default_factory=dict)
    noise_signals: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CrossDomainThreatFusion:
    """Fuse cross-domain signals, detect multi-stage
    attacks, compute signal reliability."""

    def __init__(
        self,
        max_records: int = 200000,
        reliability_threshold: float = 0.6,
    ) -> None:
        self._max_records = max_records
        self._reliability_threshold = reliability_threshold
        self._records: list[ThreatFusionRecord] = []
        self._analyses: list[ThreatFusionAnalysis] = []
        logger.info(
            "cross_domain_threat_fusion.init",
            max_records=max_records,
            reliability_threshold=(reliability_threshold),
        )

    def add_record(
        self,
        signal_id: str,
        domain: SecurityDomain = (SecurityDomain.ENDPOINT),
        method: FusionMethod = (FusionMethod.CORRELATION),
        fidelity: SignalFidelity = (SignalFidelity.PROBABLE),
        reliability_score: float = 0.0,
        correlated_signals: int = 0,
        service: str = "",
        team: str = "",
    ) -> ThreatFusionRecord:
        record = ThreatFusionRecord(
            signal_id=signal_id,
            domain=domain,
            method=method,
            fidelity=fidelity,
            reliability_score=reliability_score,
            correlated_signals=correlated_signals,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cross_domain_threat_fusion.added",
            record_id=record.id,
            signal_id=signal_id,
        )
        return record

    def process(self, key: str) -> ThreatFusionAnalysis | None:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return None
        score = rec.reliability_score * 100.0
        multi = rec.correlated_signals >= 3
        analysis = ThreatFusionAnalysis(
            signal_id=rec.signal_id,
            domain=rec.domain,
            analysis_score=round(score, 2),
            multi_stage_flag=multi,
            fusion_confidence=rec.reliability_score,
            description=(f"Signal {rec.signal_id} reliability {score:.1f}%"),
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return analysis

    def generate_report(self) -> ThreatFusionReport:
        by_dom: dict[str, int] = {}
        by_meth: dict[str, int] = {}
        by_fid: dict[str, int] = {}
        rels: list[float] = []
        corrs: list[int] = []
        for r in self._records:
            d = r.domain.value
            by_dom[d] = by_dom.get(d, 0) + 1
            m = r.method.value
            by_meth[m] = by_meth.get(m, 0) + 1
            f = r.fidelity.value
            by_fid[f] = by_fid.get(f, 0) + 1
            rels.append(r.reliability_score)
            corrs.append(r.correlated_signals)
        avg_r = round(sum(rels) / len(rels), 4) if rels else 0.0
        avg_c = round(sum(corrs) / len(corrs), 2) if corrs else 0.0
        noise = [r.signal_id for r in self._records if r.fidelity == SignalFidelity.NOISE][:5]
        recs: list[str] = []
        if noise:
            recs.append(f"{len(noise)} noise signals detected")
        if not recs:
            recs.append("Signal fusion is healthy")
        return ThreatFusionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_reliability=avg_r,
            avg_correlated=avg_c,
            by_domain=by_dom,
            by_method=by_meth,
            by_fidelity=by_fid,
            noise_signals=noise,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dom_dist: dict[str, int] = {}
        for r in self._records:
            k = r.domain.value
            dom_dist[k] = dom_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "reliability_threshold": (self._reliability_threshold),
            "domain_distribution": dom_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("cross_domain_threat_fusion.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def fuse_cross_domain_signals(
        self,
    ) -> list[dict[str, Any]]:
        """Fuse signals grouped by domain."""
        dom_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            k = r.domain.value
            dom_data.setdefault(k, []).append(
                {
                    "signal_id": r.signal_id,
                    "method": r.method.value,
                    "fidelity": r.fidelity.value,
                    "reliability": r.reliability_score,
                }
            )
        results: list[dict[str, Any]] = []
        for dom, signals in dom_data.items():
            avg_rel = round(
                sum(s["reliability"] for s in signals) / len(signals),
                4,
            )
            results.append(
                {
                    "domain": dom,
                    "signal_count": len(signals),
                    "avg_reliability": avg_rel,
                    "signals": signals[:10],
                }
            )
        return results

    def detect_multi_stage_attacks(
        self,
    ) -> list[dict[str, Any]]:
        """Detect multi-stage attacks: signals
        correlated across 3+ domains."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.correlated_signals >= 3:
                results.append(
                    {
                        "signal_id": r.signal_id,
                        "domain": r.domain.value,
                        "correlated_signals": (r.correlated_signals),
                        "reliability": (r.reliability_score),
                        "fidelity": r.fidelity.value,
                    }
                )
        results.sort(
            key=lambda x: x["correlated_signals"],
            reverse=True,
        )
        return results

    def compute_signal_reliability(
        self,
    ) -> dict[str, Any]:
        """Compute signal reliability per domain."""
        if not self._records:
            return {
                "overall_reliability": 0.0,
                "by_domain": {},
            }
        dom_rels: dict[str, list[float]] = {}
        for r in self._records:
            k = r.domain.value
            dom_rels.setdefault(k, []).append(r.reliability_score)
        by_dom: dict[str, float] = {}
        for d, vals in dom_rels.items():
            by_dom[d] = round(sum(vals) / len(vals), 4)
        all_r = [r.reliability_score for r in self._records]
        return {
            "overall_reliability": round(sum(all_r) / len(all_r), 4),
            "by_domain": by_dom,
        }
