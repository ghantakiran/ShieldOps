"""DNS Tunneling Detector — detect DNS tunneling via query pattern and entropy analysis."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TunnelingMethod(StrEnum):
    TXT_RECORD = "txt_record"
    CNAME_CHAIN = "cname_chain"
    SUBDOMAIN_ENCODING = "subdomain_encoding"
    NULL_RECORD = "null_record"
    MX_ABUSE = "mx_abuse"


class QueryPattern(StrEnum):
    HIGH_FREQUENCY = "high_frequency"
    UNUSUAL_LENGTH = "unusual_length"
    ENCODED_PAYLOAD = "encoded_payload"
    RARE_TYPE = "rare_type"
    ENTROPY_ANOMALY = "entropy_anomaly"


class TunnelingRisk(StrEnum):
    ACTIVE_EXFIL = "active_exfil"
    SUSPECTED = "suspected"
    ELEVATED = "elevated"
    NORMAL = "normal"
    BENIGN = "benign"


# --- Models ---


class TunnelingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tunneling_id: str = ""
    tunneling_method: TunnelingMethod = TunnelingMethod.TXT_RECORD
    query_pattern: QueryPattern = QueryPattern.HIGH_FREQUENCY
    tunneling_risk: TunnelingRisk = TunnelingRisk.ACTIVE_EXFIL
    detection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class TunnelingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tunneling_id: str = ""
    tunneling_method: TunnelingMethod = TunnelingMethod.TXT_RECORD
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DNSTunnelingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_detection_score: float = 0.0
    by_method: dict[str, int] = Field(default_factory=dict)
    by_pattern: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DNSTunnelingDetector:
    """Detect DNS tunneling via query pattern analysis, entropy scoring, and risk assessment."""

    def __init__(
        self,
        max_records: int = 200000,
        detection_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._detection_threshold = detection_threshold
        self._records: list[TunnelingRecord] = []
        self._analyses: list[TunnelingAnalysis] = []
        logger.info(
            "dns_tunneling_detector.initialized",
            max_records=max_records,
            detection_threshold=detection_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_tunneling(
        self,
        tunneling_id: str,
        tunneling_method: TunnelingMethod = TunnelingMethod.TXT_RECORD,
        query_pattern: QueryPattern = QueryPattern.HIGH_FREQUENCY,
        tunneling_risk: TunnelingRisk = TunnelingRisk.ACTIVE_EXFIL,
        detection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> TunnelingRecord:
        record = TunnelingRecord(
            tunneling_id=tunneling_id,
            tunneling_method=tunneling_method,
            query_pattern=query_pattern,
            tunneling_risk=tunneling_risk,
            detection_score=detection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dns_tunneling_detector.tunneling_recorded",
            record_id=record.id,
            tunneling_id=tunneling_id,
            tunneling_method=tunneling_method.value,
            query_pattern=query_pattern.value,
        )
        return record

    def get_tunneling(self, record_id: str) -> TunnelingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_tunnelings(
        self,
        tunneling_method: TunnelingMethod | None = None,
        query_pattern: QueryPattern | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[TunnelingRecord]:
        results = list(self._records)
        if tunneling_method is not None:
            results = [r for r in results if r.tunneling_method == tunneling_method]
        if query_pattern is not None:
            results = [r for r in results if r.query_pattern == query_pattern]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        tunneling_id: str,
        tunneling_method: TunnelingMethod = TunnelingMethod.TXT_RECORD,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> TunnelingAnalysis:
        analysis = TunnelingAnalysis(
            tunneling_id=tunneling_id,
            tunneling_method=tunneling_method,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "dns_tunneling_detector.analysis_added",
            tunneling_id=tunneling_id,
            tunneling_method=tunneling_method.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_method_distribution(self) -> dict[str, Any]:
        """Group by tunneling_method; return count and avg detection_score."""
        method_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.tunneling_method.value
            method_data.setdefault(key, []).append(r.detection_score)
        result: dict[str, Any] = {}
        for method, scores in method_data.items():
            result[method] = {
                "count": len(scores),
                "avg_detection_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_detection_gaps(self) -> list[dict[str, Any]]:
        """Return records where detection_score < detection_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.detection_score < self._detection_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "tunneling_id": r.tunneling_id,
                        "tunneling_method": r.tunneling_method.value,
                        "detection_score": r.detection_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["detection_score"])

    def rank_by_detection(self) -> list[dict[str, Any]]:
        """Group by service, avg detection_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.detection_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_detection_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_detection_score"])
        return results

    def detect_detection_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
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

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> DNSTunnelingReport:
        by_method: dict[str, int] = {}
        by_pattern: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_method[r.tunneling_method.value] = by_method.get(r.tunneling_method.value, 0) + 1
            by_pattern[r.query_pattern.value] = by_pattern.get(r.query_pattern.value, 0) + 1
            by_risk[r.tunneling_risk.value] = by_risk.get(r.tunneling_risk.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.detection_score < self._detection_threshold)
        scores = [r.detection_score for r in self._records]
        avg_detection_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_detection_gaps()
        top_gaps = [o["tunneling_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} tunneling record(s) below detection threshold "
                f"({self._detection_threshold})"
            )
        if self._records and avg_detection_score < self._detection_threshold:
            recs.append(
                f"Avg detection score {avg_detection_score} below threshold "
                f"({self._detection_threshold})"
            )
        if not recs:
            recs.append("DNS tunneling detection is healthy")
        return DNSTunnelingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_detection_score=avg_detection_score,
            by_method=by_method,
            by_pattern=by_pattern,
            by_risk=by_risk,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("dns_tunneling_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        method_dist: dict[str, int] = {}
        for r in self._records:
            key = r.tunneling_method.value
            method_dist[key] = method_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "detection_threshold": self._detection_threshold,
            "method_distribution": method_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
