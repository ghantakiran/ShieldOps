"""Runtime Protection Engine — enforce runtime protection policies for containers."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ProtectionMode(StrEnum):
    ENFORCE = "enforce"
    DETECT = "detect"
    MONITOR = "monitor"
    LEARN = "learn"
    DISABLED = "disabled"


class ThreatCategory(StrEnum):
    PROCESS_INJECTION = "process_injection"
    FILE_TAMPERING = "file_tampering"
    NETWORK_ANOMALY = "network_anomaly"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    CRYPTOMINING = "cryptomining"


class ResponseAction(StrEnum):
    BLOCK = "block"
    ALERT = "alert"
    CONTAIN = "contain"
    KILL = "kill"
    LOG = "log"


# --- Models ---


class ProtectionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    protection_id: str = ""
    protection_mode: ProtectionMode = ProtectionMode.ENFORCE
    threat_category: ThreatCategory = ThreatCategory.PROCESS_INJECTION
    response_action: ResponseAction = ResponseAction.BLOCK
    protection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ProtectionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    protection_id: str = ""
    protection_mode: ProtectionMode = ProtectionMode.ENFORCE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RuntimeProtectionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_protection_score: float = 0.0
    by_mode: dict[str, int] = Field(default_factory=dict)
    by_threat: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RuntimeProtectionEngine:
    """Enforce runtime protection policies for containers, detect threats, and respond."""

    def __init__(
        self,
        max_records: int = 200000,
        protection_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._protection_gap_threshold = protection_gap_threshold
        self._records: list[ProtectionRecord] = []
        self._analyses: list[ProtectionAnalysis] = []
        logger.info(
            "runtime_protection_engine.initialized",
            max_records=max_records,
            protection_gap_threshold=protection_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_protection(
        self,
        protection_id: str,
        protection_mode: ProtectionMode = ProtectionMode.ENFORCE,
        threat_category: ThreatCategory = ThreatCategory.PROCESS_INJECTION,
        response_action: ResponseAction = ResponseAction.BLOCK,
        protection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ProtectionRecord:
        record = ProtectionRecord(
            protection_id=protection_id,
            protection_mode=protection_mode,
            threat_category=threat_category,
            response_action=response_action,
            protection_score=protection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "runtime_protection_engine.protection_recorded",
            record_id=record.id,
            protection_id=protection_id,
            protection_mode=protection_mode.value,
            threat_category=threat_category.value,
        )
        return record

    def get_protection(self, record_id: str) -> ProtectionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_protections(
        self,
        protection_mode: ProtectionMode | None = None,
        threat_category: ThreatCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ProtectionRecord]:
        results = list(self._records)
        if protection_mode is not None:
            results = [r for r in results if r.protection_mode == protection_mode]
        if threat_category is not None:
            results = [r for r in results if r.threat_category == threat_category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        protection_id: str,
        protection_mode: ProtectionMode = ProtectionMode.ENFORCE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ProtectionAnalysis:
        analysis = ProtectionAnalysis(
            protection_id=protection_id,
            protection_mode=protection_mode,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "runtime_protection_engine.analysis_added",
            protection_id=protection_id,
            protection_mode=protection_mode.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_mode_distribution(self) -> dict[str, Any]:
        """Group by protection_mode; return count and avg protection_score."""
        mode_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.protection_mode.value
            mode_data.setdefault(key, []).append(r.protection_score)
        result: dict[str, Any] = {}
        for mode, scores in mode_data.items():
            result[mode] = {
                "count": len(scores),
                "avg_protection_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_protection_gaps(self) -> list[dict[str, Any]]:
        """Return records where protection_score < protection_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.protection_score < self._protection_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "protection_id": r.protection_id,
                        "protection_mode": r.protection_mode.value,
                        "protection_score": r.protection_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["protection_score"])

    def rank_by_protection(self) -> list[dict[str, Any]]:
        """Group by service, avg protection_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.protection_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_protection_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_protection_score"])
        return results

    def detect_protection_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> RuntimeProtectionReport:
        by_mode: dict[str, int] = {}
        by_threat: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in self._records:
            by_mode[r.protection_mode.value] = by_mode.get(r.protection_mode.value, 0) + 1
            by_threat[r.threat_category.value] = by_threat.get(r.threat_category.value, 0) + 1
            by_action[r.response_action.value] = by_action.get(r.response_action.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.protection_score < self._protection_gap_threshold
        )
        scores = [r.protection_score for r in self._records]
        avg_protection_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_protection_gaps()
        top_gaps = [o["protection_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} protection(s) below threshold ({self._protection_gap_threshold})"
            )
        if self._records and avg_protection_score < self._protection_gap_threshold:
            recs.append(
                f"Avg protection score {avg_protection_score} below threshold "
                f"({self._protection_gap_threshold})"
            )
        if not recs:
            recs.append("Runtime protection is healthy")
        return RuntimeProtectionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_protection_score=avg_protection_score,
            by_mode=by_mode,
            by_threat=by_threat,
            by_action=by_action,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("runtime_protection_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        mode_dist: dict[str, int] = {}
        for r in self._records:
            key = r.protection_mode.value
            mode_dist[key] = mode_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "protection_gap_threshold": self._protection_gap_threshold,
            "mode_distribution": mode_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
