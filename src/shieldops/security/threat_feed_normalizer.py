"""Threat Feed Normalizer — normalize and correlate threat intelligence feeds."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FeedSource(StrEnum):
    OPEN_SOURCE = "open_source"
    COMMERCIAL = "commercial"
    GOVERNMENT = "government"
    ISAC = "isac"
    INTERNAL = "internal"


class FeedFormat(StrEnum):
    STIX = "stix"
    TAXII = "taxii"
    CSV = "csv"
    JSON = "json"
    CUSTOM = "custom"


class NormalizationStatus(StrEnum):
    RAW = "raw"
    NORMALIZED = "normalized"
    ENRICHED = "enriched"
    VALIDATED = "validated"
    EXPIRED = "expired"


# --- Models ---


class FeedRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    feed_name: str = ""
    feed_source: FeedSource = FeedSource.OPEN_SOURCE
    feed_format: FeedFormat = FeedFormat.STIX
    normalization_status: NormalizationStatus = NormalizationStatus.RAW
    indicator_count: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class FeedAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    feed_name: str = ""
    feed_source: FeedSource = FeedSource.OPEN_SOURCE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FeedNormalizationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_indicator_count: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_format: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThreatFeedNormalizer:
    """Normalize and correlate threat intelligence feeds from multiple sources."""

    def __init__(self, max_records: int = 200000, quality_threshold: float = 50.0) -> None:
        self._max_records = max_records
        self._quality_threshold = quality_threshold
        self._records: list[FeedRecord] = []
        self._analyses: list[FeedAnalysis] = []
        logger.info(
            "threat_feed_normalizer.initialized",
            max_records=max_records,
            quality_threshold=quality_threshold,
        )

    def record_feed(
        self,
        feed_name: str,
        feed_source: FeedSource = FeedSource.OPEN_SOURCE,
        feed_format: FeedFormat = FeedFormat.STIX,
        normalization_status: NormalizationStatus = NormalizationStatus.RAW,
        indicator_count: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> FeedRecord:
        record = FeedRecord(
            feed_name=feed_name,
            feed_source=feed_source,
            feed_format=feed_format,
            normalization_status=normalization_status,
            indicator_count=indicator_count,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "threat_feed_normalizer.recorded",
            record_id=record.id,
            feed_name=feed_name,
            feed_source=feed_source.value,
        )
        return record

    def get_record(self, record_id: str) -> FeedRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        feed_source: FeedSource | None = None,
        feed_format: FeedFormat | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FeedRecord]:
        results = list(self._records)
        if feed_source is not None:
            results = [r for r in results if r.feed_source == feed_source]
        if feed_format is not None:
            results = [r for r in results if r.feed_format == feed_format]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        feed_name: str,
        feed_source: FeedSource = FeedSource.OPEN_SOURCE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> FeedAnalysis:
        analysis = FeedAnalysis(
            feed_name=feed_name,
            feed_source=feed_source,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "threat_feed_normalizer.analysis_added",
            feed_name=feed_name,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_source_distribution(self) -> dict[str, Any]:
        source_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.feed_source.value
            source_data.setdefault(key, []).append(r.indicator_count)
        result: dict[str, Any] = {}
        for source, counts in source_data.items():
            result[source] = {
                "count": len(counts),
                "avg_indicator_count": round(sum(counts) / len(counts), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.indicator_count < self._quality_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "feed_name": r.feed_name,
                        "feed_source": r.feed_source.value,
                        "indicator_count": r.indicator_count,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["indicator_count"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.indicator_count)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_indicator_count": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_indicator_count"])
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

    def generate_report(self) -> FeedNormalizationReport:
        by_source: dict[str, int] = {}
        by_format: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_source[r.feed_source.value] = by_source.get(r.feed_source.value, 0) + 1
            by_format[r.feed_format.value] = by_format.get(r.feed_format.value, 0) + 1
            by_status[r.normalization_status.value] = (
                by_status.get(r.normalization_status.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.indicator_count < self._quality_threshold)
        scores = [r.indicator_count for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["feed_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} feed(s) below quality threshold ({self._quality_threshold})")
        if self._records and avg_score < self._quality_threshold:
            recs.append(
                f"Avg indicator count {avg_score} below threshold ({self._quality_threshold})"
            )
        if not recs:
            recs.append("Threat feed normalization is healthy")
        return FeedNormalizationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_indicator_count=avg_score,
            by_source=by_source,
            by_format=by_format,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("threat_feed_normalizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        source_dist: dict[str, int] = {}
        for r in self._records:
            key = r.feed_source.value
            source_dist[key] = source_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "quality_threshold": self._quality_threshold,
            "source_distribution": source_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
