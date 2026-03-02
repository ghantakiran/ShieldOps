"""Intel Sharing Orchestrator — orchestrate intelligence sharing across organizations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SharingProtocol(StrEnum):
    STIX_TAXII = "stix_taxii"
    MISP = "misp"
    OPENCTF = "openctf"
    EMAIL = "email"
    API = "api"


class SharingLevel(StrEnum):
    TLP_RED = "tlp_red"
    TLP_AMBER = "tlp_amber"
    TLP_GREEN = "tlp_green"
    TLP_WHITE = "tlp_white"
    TLP_CLEAR = "tlp_clear"


class SharingStatus(StrEnum):
    SHARED = "shared"
    PENDING = "pending"
    RESTRICTED = "restricted"
    REVOKED = "revoked"
    QUEUED = "queued"


# --- Models ---


class SharingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intel_name: str = ""
    sharing_protocol: SharingProtocol = SharingProtocol.STIX_TAXII
    sharing_level: SharingLevel = SharingLevel.TLP_AMBER
    sharing_status: SharingStatus = SharingStatus.PENDING
    share_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SharingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intel_name: str = ""
    sharing_protocol: SharingProtocol = SharingProtocol.STIX_TAXII
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SharingOrchestrationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_share_score: float = 0.0
    by_protocol: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IntelSharingOrchestrator:
    """Orchestrate intelligence sharing across organizations and partners."""

    def __init__(self, max_records: int = 200000, quality_threshold: float = 50.0) -> None:
        self._max_records = max_records
        self._quality_threshold = quality_threshold
        self._records: list[SharingRecord] = []
        self._analyses: list[SharingAnalysis] = []
        logger.info(
            "intel_sharing_orchestrator.initialized",
            max_records=max_records,
            quality_threshold=quality_threshold,
        )

    def record_sharing(
        self,
        intel_name: str,
        sharing_protocol: SharingProtocol = SharingProtocol.STIX_TAXII,
        sharing_level: SharingLevel = SharingLevel.TLP_AMBER,
        sharing_status: SharingStatus = SharingStatus.PENDING,
        share_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SharingRecord:
        record = SharingRecord(
            intel_name=intel_name,
            sharing_protocol=sharing_protocol,
            sharing_level=sharing_level,
            sharing_status=sharing_status,
            share_score=share_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "intel_sharing_orchestrator.recorded",
            record_id=record.id,
            intel_name=intel_name,
            sharing_protocol=sharing_protocol.value,
        )
        return record

    def get_record(self, record_id: str) -> SharingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        sharing_protocol: SharingProtocol | None = None,
        sharing_level: SharingLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SharingRecord]:
        results = list(self._records)
        if sharing_protocol is not None:
            results = [r for r in results if r.sharing_protocol == sharing_protocol]
        if sharing_level is not None:
            results = [r for r in results if r.sharing_level == sharing_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        intel_name: str,
        sharing_protocol: SharingProtocol = SharingProtocol.STIX_TAXII,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SharingAnalysis:
        analysis = SharingAnalysis(
            intel_name=intel_name,
            sharing_protocol=sharing_protocol,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "intel_sharing_orchestrator.analysis_added",
            intel_name=intel_name,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_protocol_distribution(self) -> dict[str, Any]:
        proto_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.sharing_protocol.value
            proto_data.setdefault(key, []).append(r.share_score)
        result: dict[str, Any] = {}
        for proto, scores in proto_data.items():
            result[proto] = {
                "count": len(scores),
                "avg_share_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.share_score < self._quality_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "intel_name": r.intel_name,
                        "sharing_protocol": r.sharing_protocol.value,
                        "share_score": r.share_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["share_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.share_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_share_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_share_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
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

    def generate_report(self) -> SharingOrchestrationReport:
        by_protocol: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_protocol[r.sharing_protocol.value] = by_protocol.get(r.sharing_protocol.value, 0) + 1
            by_level[r.sharing_level.value] = by_level.get(r.sharing_level.value, 0) + 1
            by_status[r.sharing_status.value] = by_status.get(r.sharing_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.share_score < self._quality_threshold)
        scores = [r.share_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["intel_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} sharing record(s) below quality threshold ({self._quality_threshold})"
            )
        if self._records and avg_score < self._quality_threshold:
            recs.append(f"Avg share score {avg_score} below threshold ({self._quality_threshold})")
        if not recs:
            recs.append("Intel sharing orchestration is healthy")
        return SharingOrchestrationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_share_score=avg_score,
            by_protocol=by_protocol,
            by_level=by_level,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("intel_sharing_orchestrator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        proto_dist: dict[str, int] = {}
        for r in self._records:
            key = r.sharing_protocol.value
            proto_dist[key] = proto_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "quality_threshold": self._quality_threshold,
            "protocol_distribution": proto_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
