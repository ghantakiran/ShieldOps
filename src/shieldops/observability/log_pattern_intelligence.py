"""Log Pattern Intelligence

Log template extraction, pattern clustering, anomaly detection in log
patterns, and trend analysis for intelligent log observability.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"


class PatternType(StrEnum):
    KNOWN = "known"
    NEW = "new"
    RARE = "rare"
    BURSTY = "bursty"
    DECLINING = "declining"
    ANOMALOUS = "anomalous"


class ClusterStatus(StrEnum):
    STABLE = "stable"
    GROWING = "growing"
    SHRINKING = "shrinking"
    EMERGING = "emerging"
    EXTINCT = "extinct"


# --- Models ---


class LogPatternRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    template: str = ""
    sample_message: str = ""
    log_level: LogLevel = LogLevel.INFO
    pattern_type: PatternType = PatternType.KNOWN
    cluster_id: str = ""
    cluster_status: ClusterStatus = ClusterStatus.STABLE
    occurrence_count: int = 1
    unique_params: int = 0
    entropy_score: float = 0.0
    service: str = ""
    source_file: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PatternAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    template: str = ""
    pattern_type: PatternType = PatternType.KNOWN
    frequency_score: float = 0.0
    anomaly_score: float = 0.0
    trend_direction: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LogPatternReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    unique_templates: int = 0
    unique_clusters: int = 0
    avg_entropy: float = 0.0
    anomalous_pattern_count: int = 0
    by_log_level: dict[str, int] = Field(default_factory=dict)
    by_pattern_type: dict[str, int] = Field(default_factory=dict)
    by_cluster_status: dict[str, int] = Field(default_factory=dict)
    top_templates: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class LogPatternIntelligence:
    """Log Pattern Intelligence

    Log template extraction, pattern clustering, anomaly detection in
    log patterns, and trend analysis.
    """

    def __init__(
        self,
        max_records: int = 200000,
        anomaly_entropy_threshold: float = 0.8,
        rare_threshold_count: int = 5,
    ) -> None:
        self._max_records = max_records
        self._anomaly_entropy_threshold = anomaly_entropy_threshold
        self._rare_threshold = rare_threshold_count
        self._records: list[LogPatternRecord] = []
        self._analyses: list[PatternAnalysis] = []
        logger.info(
            "log_pattern_intelligence.initialized",
            max_records=max_records,
            anomaly_entropy_threshold=anomaly_entropy_threshold,
        )

    def add_record(
        self,
        template: str,
        sample_message: str = "",
        log_level: LogLevel = LogLevel.INFO,
        pattern_type: PatternType = PatternType.KNOWN,
        cluster_id: str = "",
        occurrence_count: int = 1,
        unique_params: int = 0,
        service: str = "",
        source_file: str = "",
        team: str = "",
    ) -> LogPatternRecord:
        words = template.split()
        param_count = sum(1 for w in words if w.startswith("{") or w.startswith("<"))
        total_words = max(1, len(words))
        entropy = round(param_count / total_words, 4) if total_words > 0 else 0.0
        existing = [r for r in self._records if r.template == template]
        if not existing:
            cluster_status = ClusterStatus.EMERGING
        elif len(existing) > 20:
            cluster_status = ClusterStatus.STABLE
        else:
            cluster_status = ClusterStatus.GROWING
        if occurrence_count <= self._rare_threshold and pattern_type == PatternType.KNOWN:
            pattern_type = PatternType.RARE
        cid = cluster_id or self._assign_cluster(template)
        record = LogPatternRecord(
            template=template,
            sample_message=sample_message or template,
            log_level=log_level,
            pattern_type=pattern_type,
            cluster_id=cid,
            cluster_status=cluster_status,
            occurrence_count=occurrence_count,
            unique_params=unique_params or param_count,
            entropy_score=entropy,
            service=service,
            source_file=source_file,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "log_pattern_intelligence.record_added",
            record_id=record.id,
            template=template[:80],
            log_level=log_level.value,
            pattern_type=pattern_type.value,
        )
        return record

    def _assign_cluster(self, template: str) -> str:
        words = set(template.lower().split())
        best_match = ""
        best_overlap = 0.0
        cluster_templates: dict[str, str] = {}
        for r in self._records:
            if r.cluster_id not in cluster_templates:
                cluster_templates[r.cluster_id] = r.template
        for cid, existing_template in cluster_templates.items():
            existing_words = set(existing_template.lower().split())
            if not words or not existing_words:
                continue
            overlap = len(words & existing_words) / len(words | existing_words)
            if overlap > best_overlap and overlap > 0.5:
                best_overlap = overlap
                best_match = cid
        return best_match or str(uuid.uuid4())[:8]

    def get_record(self, record_id: str) -> LogPatternRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        log_level: LogLevel | None = None,
        pattern_type: PatternType | None = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[LogPatternRecord]:
        results = list(self._records)
        if log_level is not None:
            results = [r for r in results if r.log_level == log_level]
        if pattern_type is not None:
            results = [r for r in results if r.pattern_type == pattern_type]
        if service is not None:
            results = [r for r in results if r.service == service]
        return results[-limit:]

    def extract_top_templates(self, top_n: int = 20) -> list[dict[str, Any]]:
        template_stats: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.template not in template_stats:
                template_stats[r.template] = {
                    "template": r.template,
                    "total_occurrences": 0,
                    "record_count": 0,
                    "log_levels": set(),
                    "services": set(),
                }
            template_stats[r.template]["total_occurrences"] += r.occurrence_count
            template_stats[r.template]["record_count"] += 1
            template_stats[r.template]["log_levels"].add(r.log_level.value)
            template_stats[r.template]["services"].add(r.service)
        results: list[dict[str, Any]] = []
        for stats in template_stats.values():
            results.append(
                {
                    "template": stats["template"],
                    "total_occurrences": stats["total_occurrences"],
                    "record_count": stats["record_count"],
                    "log_levels": list(stats["log_levels"]),
                    "service_count": len(stats["services"]),
                }
            )
        return sorted(results, key=lambda x: x["total_occurrences"], reverse=True)[:top_n]

    def detect_anomalous_patterns(self) -> list[dict[str, Any]]:
        anomalies: list[dict[str, Any]] = []
        for r in self._records:
            is_anomalous = False
            reasons: list[str] = []
            if r.entropy_score > self._anomaly_entropy_threshold:
                is_anomalous = True
                reasons.append(f"High entropy ({r.entropy_score:.2f})")
            if r.pattern_type == PatternType.NEW and r.log_level in (
                LogLevel.ERROR,
                LogLevel.FATAL,
            ):
                is_anomalous = True
                reasons.append("New error/fatal pattern")
            if r.pattern_type == PatternType.BURSTY:
                is_anomalous = True
                reasons.append("Bursty pattern detected")
            if is_anomalous:
                anomalies.append(
                    {
                        "record_id": r.id,
                        "template": r.template[:100],
                        "service": r.service,
                        "log_level": r.log_level.value,
                        "entropy": r.entropy_score,
                        "reasons": reasons,
                    }
                )
        return anomalies

    def process(self, service: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.service == service]
        if not matching:
            return {"service": service, "status": "no_data"}
        unique_templates = len({r.template for r in matching})
        total_occ = sum(r.occurrence_count for r in matching)
        entropies = [r.entropy_score for r in matching]
        anomalous = sum(1 for r in matching if r.entropy_score > self._anomaly_entropy_threshold)
        analysis = PatternAnalysis(
            template=f"service:{service}",
            pattern_type=PatternType.KNOWN,
            frequency_score=round(total_occ / max(1, unique_templates), 2),
            anomaly_score=round(anomalous / max(1, len(matching)), 4),
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return {
            "service": service,
            "record_count": len(matching),
            "unique_templates": unique_templates,
            "total_occurrences": total_occ,
            "avg_entropy": round(sum(entropies) / len(entropies), 4),
            "anomalous_count": anomalous,
        }

    def generate_report(self) -> LogPatternReport:
        by_level: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_level[r.log_level.value] = by_level.get(r.log_level.value, 0) + 1
            by_type[r.pattern_type.value] = by_type.get(r.pattern_type.value, 0) + 1
            by_status[r.cluster_status.value] = by_status.get(r.cluster_status.value, 0) + 1
        unique_templates = len({r.template for r in self._records})
        unique_clusters = len({r.cluster_id for r in self._records})
        entropies = [r.entropy_score for r in self._records]
        avg_entropy = round(sum(entropies) / max(1, len(entropies)), 4)
        anomalous = sum(
            1
            for r in self._records
            if r.entropy_score > self._anomaly_entropy_threshold
            or r.pattern_type == PatternType.ANOMALOUS
        )
        top = self.extract_top_templates(5)
        recs: list[str] = []
        if anomalous > 0:
            recs.append(f"{anomalous} anomalous pattern(s) detected — investigate")
        error_count = by_level.get("error", 0) + by_level.get("fatal", 0)
        if error_count > 0:
            recs.append(f"{error_count} error/fatal log pattern(s) — review root causes")
        new_count = by_type.get("new", 0)
        if new_count > 0:
            recs.append(f"{new_count} new pattern(s) emerged — classify and monitor")
        if not recs:
            recs.append("Log patterns are stable — no anomalies detected")
        return LogPatternReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            unique_templates=unique_templates,
            unique_clusters=unique_clusters,
            avg_entropy=avg_entropy,
            anomalous_pattern_count=anomalous,
            by_log_level=by_level,
            by_pattern_type=by_type,
            by_cluster_status=by_status,
            top_templates=top,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            level_dist[r.log_level.value] = level_dist.get(r.log_level.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "anomaly_entropy_threshold": self._anomaly_entropy_threshold,
            "rare_threshold_count": self._rare_threshold,
            "log_level_distribution": level_dist,
            "unique_templates": len({r.template for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("log_pattern_intelligence.cleared")
        return {"status": "cleared"}
