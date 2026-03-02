"""Security Alert Dedup Engine — deduplicate security alerts via fingerprinting."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DedupStrategy(StrEnum):
    EXACT_MATCH = "exact_match"
    FUZZY_MATCH = "fuzzy_match"
    TIME_WINDOW = "time_window"
    CONTENT_HASH = "content_hash"
    BEHAVIORAL = "behavioral"


class AlertSource(StrEnum):
    SIEM = "siem"
    IDS = "ids"
    EDR = "edr"
    CLOUD_SECURITY = "cloud_security"
    CUSTOM = "custom"


class DedupResult(StrEnum):
    DUPLICATE = "duplicate"
    UNIQUE = "unique"
    NEAR_DUPLICATE = "near_duplicate"
    CLUSTER_MEMBER = "cluster_member"
    AMBIGUOUS = "ambiguous"


# --- Models ---


class DedupRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_fingerprint: str = ""
    dedup_strategy: DedupStrategy = DedupStrategy.EXACT_MATCH
    alert_source: AlertSource = AlertSource.SIEM
    dedup_result: DedupResult = DedupResult.DUPLICATE
    dedup_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DedupAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_fingerprint: str = ""
    dedup_strategy: DedupStrategy = DedupStrategy.EXACT_MATCH
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DedupReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_dedup_count: int = 0
    avg_dedup_score: float = 0.0
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    top_low_dedup: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityAlertDedupEngine:
    """Deduplicate security alerts via fingerprinting and similarity analysis."""

    def __init__(
        self,
        max_records: int = 200000,
        dedup_effectiveness_threshold: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._dedup_effectiveness_threshold = dedup_effectiveness_threshold
        self._records: list[DedupRecord] = []
        self._analyses: list[DedupAnalysis] = []
        logger.info(
            "security_alert_dedup_engine.initialized",
            max_records=max_records,
            dedup_effectiveness_threshold=dedup_effectiveness_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_dedup(
        self,
        alert_fingerprint: str,
        dedup_strategy: DedupStrategy = DedupStrategy.EXACT_MATCH,
        alert_source: AlertSource = AlertSource.SIEM,
        dedup_result: DedupResult = DedupResult.DUPLICATE,
        dedup_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DedupRecord:
        record = DedupRecord(
            alert_fingerprint=alert_fingerprint,
            dedup_strategy=dedup_strategy,
            alert_source=alert_source,
            dedup_result=dedup_result,
            dedup_score=dedup_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_alert_dedup_engine.dedup_recorded",
            record_id=record.id,
            alert_fingerprint=alert_fingerprint,
            dedup_strategy=dedup_strategy.value,
            alert_source=alert_source.value,
        )
        return record

    def get_dedup(self, record_id: str) -> DedupRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_dedups(
        self,
        dedup_strategy: DedupStrategy | None = None,
        alert_source: AlertSource | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DedupRecord]:
        results = list(self._records)
        if dedup_strategy is not None:
            results = [r for r in results if r.dedup_strategy == dedup_strategy]
        if alert_source is not None:
            results = [r for r in results if r.alert_source == alert_source]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        alert_fingerprint: str,
        dedup_strategy: DedupStrategy = DedupStrategy.EXACT_MATCH,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DedupAnalysis:
        analysis = DedupAnalysis(
            alert_fingerprint=alert_fingerprint,
            dedup_strategy=dedup_strategy,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "security_alert_dedup_engine.analysis_added",
            alert_fingerprint=alert_fingerprint,
            dedup_strategy=dedup_strategy.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_dedup_distribution(self) -> dict[str, Any]:
        """Group by dedup_strategy; return count and avg dedup_score."""
        src_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.dedup_strategy.value
            src_data.setdefault(key, []).append(r.dedup_score)
        result: dict[str, Any] = {}
        for src, scores in src_data.items():
            result[src] = {
                "count": len(scores),
                "avg_dedup_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_dedup_alerts(self) -> list[dict[str, Any]]:
        """Return records where dedup_score < dedup_effectiveness_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.dedup_score < self._dedup_effectiveness_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "alert_fingerprint": r.alert_fingerprint,
                        "dedup_strategy": r.dedup_strategy.value,
                        "dedup_score": r.dedup_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["dedup_score"])

    def rank_by_dedup(self) -> list[dict[str, Any]]:
        """Group by service, avg dedup_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.dedup_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_dedup_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_dedup_score"])
        return results

    def detect_dedup_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
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

    def generate_report(self) -> DedupReport:
        by_strategy: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_result: dict[str, int] = {}
        for r in self._records:
            by_strategy[r.dedup_strategy.value] = by_strategy.get(r.dedup_strategy.value, 0) + 1
            by_source[r.alert_source.value] = by_source.get(r.alert_source.value, 0) + 1
            by_result[r.dedup_result.value] = by_result.get(r.dedup_result.value, 0) + 1
        low_dedup_count = sum(
            1 for r in self._records if r.dedup_score < self._dedup_effectiveness_threshold
        )
        scores = [r.dedup_score for r in self._records]
        avg_dedup_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_dedup_alerts()
        top_low_dedup = [o["alert_fingerprint"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_dedup_count > 0:
            recs.append(
                f"{low_dedup_count} alert(s) below dedup effectiveness threshold "
                f"({self._dedup_effectiveness_threshold})"
            )
        if self._records and avg_dedup_score < self._dedup_effectiveness_threshold:
            recs.append(
                f"Avg dedup score {avg_dedup_score} below threshold "
                f"({self._dedup_effectiveness_threshold})"
            )
        if not recs:
            recs.append("Security alert deduplication is healthy")
        return DedupReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_dedup_count=low_dedup_count,
            avg_dedup_score=avg_dedup_score,
            by_strategy=by_strategy,
            by_source=by_source,
            by_result=by_result,
            top_low_dedup=top_low_dedup,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_alert_dedup_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        strategy_dist: dict[str, int] = {}
        for r in self._records:
            key = r.dedup_strategy.value
            strategy_dist[key] = strategy_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "dedup_effectiveness_threshold": self._dedup_effectiveness_threshold,
            "strategy_distribution": strategy_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
