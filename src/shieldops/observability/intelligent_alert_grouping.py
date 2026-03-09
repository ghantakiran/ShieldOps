"""Intelligent Alert Grouping

ML-based alert clustering, temporal correlation, topology-aware grouping,
and deduplication scoring for alert noise reduction.
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


class GroupingStrategy(StrEnum):
    TEMPORAL = "temporal"
    TOPOLOGICAL = "topological"
    SEMANTIC = "semantic"
    FINGERPRINT = "fingerprint"
    ML_CLUSTER = "ml_cluster"
    HYBRID = "hybrid"


class AlertPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class GroupStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"
    MERGED = "merged"
    RESOLVED = "resolved"


# --- Models ---


class AlertGroupRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str = ""
    fingerprint: str = ""
    group_id: str = ""
    grouping_strategy: GroupingStrategy = GroupingStrategy.FINGERPRINT
    priority: AlertPriority = AlertPriority.MEDIUM
    group_status: GroupStatus = GroupStatus.OPEN
    similarity_score: float = 0.0
    dedup_score: float = 0.0
    source_service: str = ""
    labels: dict[str, str] = Field(default_factory=dict)
    alert_count_in_group: int = 1
    first_seen_at: float = Field(default_factory=time.time)
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class GroupAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    group_id: str = ""
    alert_count: int = 0
    unique_services: int = 0
    dedup_ratio: float = 0.0
    noise_reduction_pct: float = 0.0
    root_cause_candidate: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertGroupingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    total_groups: int = 0
    avg_group_size: float = 0.0
    dedup_ratio: float = 0.0
    noise_reduction_pct: float = 0.0
    by_grouping_strategy: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    by_group_status: dict[str, int] = Field(default_factory=dict)
    largest_groups: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IntelligentAlertGrouping:
    """Intelligent Alert Grouping

    ML-based alert clustering, temporal correlation, topology-aware grouping,
    and deduplication scoring.
    """

    def __init__(
        self,
        max_records: int = 200000,
        similarity_threshold: float = 0.75,
        temporal_window_sec: float = 300.0,
    ) -> None:
        self._max_records = max_records
        self._similarity_threshold = similarity_threshold
        self._temporal_window_sec = temporal_window_sec
        self._records: list[AlertGroupRecord] = []
        self._analyses: list[GroupAnalysis] = []
        logger.info(
            "intelligent_alert_grouping.initialized",
            max_records=max_records,
            similarity_threshold=similarity_threshold,
            temporal_window_sec=temporal_window_sec,
        )

    def add_record(
        self,
        alert_name: str,
        fingerprint: str = "",
        group_id: str = "",
        grouping_strategy: GroupingStrategy = GroupingStrategy.FINGERPRINT,
        priority: AlertPriority = AlertPriority.MEDIUM,
        group_status: GroupStatus = GroupStatus.OPEN,
        similarity_score: float = 0.0,
        source_service: str = "",
        labels: dict[str, str] | None = None,
        alert_count_in_group: int = 1,
        service: str = "",
        team: str = "",
    ) -> AlertGroupRecord:
        fp = fingerprint or f"{alert_name}:{source_service}"
        gid = group_id or self._find_matching_group(fp, alert_name)
        existing = [r for r in self._records if r.group_id == gid]
        dedup_score = min(1.0, len(existing) / max(1, len(existing) + 1))
        record = AlertGroupRecord(
            alert_name=alert_name,
            fingerprint=fp,
            group_id=gid,
            grouping_strategy=grouping_strategy,
            priority=priority,
            group_status=group_status,
            similarity_score=similarity_score,
            dedup_score=round(dedup_score, 4),
            source_service=source_service,
            labels=labels or {},
            alert_count_in_group=alert_count_in_group,
            service=service or source_service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "intelligent_alert_grouping.record_added",
            record_id=record.id,
            alert_name=alert_name,
            group_id=gid,
            dedup_score=dedup_score,
        )
        return record

    def _find_matching_group(self, fingerprint: str, alert_name: str) -> str:
        now = time.time()
        for r in reversed(self._records):
            if now - r.created_at > self._temporal_window_sec:
                break
            if r.fingerprint == fingerprint:
                return r.group_id
            name_overlap = len(set(alert_name.lower().split()) & set(r.alert_name.lower().split()))
            total_words = max(
                1, len(set(alert_name.lower().split()) | set(r.alert_name.lower().split()))
            )
            sim = name_overlap / total_words
            if sim >= self._similarity_threshold:
                return r.group_id
        return str(uuid.uuid4())

    def get_record(self, record_id: str) -> AlertGroupRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        priority: AlertPriority | None = None,
        group_status: GroupStatus | None = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[AlertGroupRecord]:
        results = list(self._records)
        if priority is not None:
            results = [r for r in results if r.priority == priority]
        if group_status is not None:
            results = [r for r in results if r.group_status == group_status]
        if service is not None:
            results = [r for r in results if r.service == service]
        return results[-limit:]

    def compute_group_statistics(self) -> list[dict[str, Any]]:
        groups: dict[str, list[AlertGroupRecord]] = {}
        for r in self._records:
            groups.setdefault(r.group_id, []).append(r)
        stats: list[dict[str, Any]] = []
        for gid, members in groups.items():
            unique_svcs = len({m.source_service for m in members})
            priorities = [m.priority.value for m in members]
            highest = "info"
            for p in ["critical", "high", "medium", "low", "info"]:
                if p in priorities:
                    highest = p
                    break
            stats.append(
                {
                    "group_id": gid,
                    "alert_count": len(members),
                    "unique_services": unique_svcs,
                    "highest_priority": highest,
                    "first_alert": members[0].alert_name,
                    "span_seconds": round(members[-1].created_at - members[0].created_at, 2),
                }
            )
        return sorted(stats, key=lambda x: x["alert_count"], reverse=True)

    def calculate_noise_reduction(self) -> dict[str, Any]:
        total_alerts = len(self._records)
        if total_alerts == 0:
            return {"status": "no_data"}
        unique_groups = len({r.group_id for r in self._records})
        dedup_ratio = round(1 - (unique_groups / total_alerts), 4) if total_alerts > 0 else 0.0
        noise_reduction = round(dedup_ratio * 100, 2)
        suppressed = sum(1 for r in self._records if r.group_status == GroupStatus.SUPPRESSED)
        merged = sum(1 for r in self._records if r.group_status == GroupStatus.MERGED)
        return {
            "total_alerts": total_alerts,
            "unique_groups": unique_groups,
            "dedup_ratio": dedup_ratio,
            "noise_reduction_pct": noise_reduction,
            "suppressed_count": suppressed,
            "merged_count": merged,
            "actionable_alerts": unique_groups - suppressed,
        }

    def process(self, alert_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.alert_name == alert_name]
        if not matching:
            return {"alert_name": alert_name, "status": "no_data"}
        groups = {r.group_id for r in matching}
        dedup_scores = [r.dedup_score for r in matching]
        analysis = GroupAnalysis(
            group_id=list(groups)[0] if len(groups) == 1 else "multiple",
            alert_count=len(matching),
            unique_services=len({r.source_service for r in matching}),
            dedup_ratio=round(1 - len(groups) / len(matching), 4),
            noise_reduction_pct=round((1 - len(groups) / len(matching)) * 100, 2),
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return {
            "alert_name": alert_name,
            "occurrence_count": len(matching),
            "group_count": len(groups),
            "avg_dedup_score": round(sum(dedup_scores) / len(dedup_scores), 4),
            "noise_reduction_pct": analysis.noise_reduction_pct,
        }

    def generate_report(self) -> AlertGroupingReport:
        by_strat: dict[str, int] = {}
        by_pri: dict[str, int] = {}
        by_stat: dict[str, int] = {}
        for r in self._records:
            by_strat[r.grouping_strategy.value] = by_strat.get(r.grouping_strategy.value, 0) + 1
            by_pri[r.priority.value] = by_pri.get(r.priority.value, 0) + 1
            by_stat[r.group_status.value] = by_stat.get(r.group_status.value, 0) + 1
        total = len(self._records)
        unique_groups = len({r.group_id for r in self._records})
        dedup_ratio = round(1 - unique_groups / max(1, total), 4)
        noise_pct = round(dedup_ratio * 100, 2)
        avg_size = round(total / max(1, unique_groups), 2)
        group_stats = self.compute_group_statistics()
        largest = group_stats[:5]
        recs: list[str] = []
        if noise_pct > 50:
            recs.append(f"High deduplication ratio ({noise_pct}%) — grouping is effective")
        elif noise_pct < 20 and total > 10:
            recs.append("Low grouping rate — consider relaxing similarity threshold")
        critical_open = sum(
            1
            for r in self._records
            if r.priority == AlertPriority.CRITICAL and r.group_status == GroupStatus.OPEN
        )
        if critical_open > 0:
            recs.append(f"{critical_open} critical open alert(s) need attention")
        if not recs:
            recs.append("Alert grouping is healthy")
        return AlertGroupingReport(
            total_records=total,
            total_analyses=len(self._analyses),
            total_groups=unique_groups,
            avg_group_size=avg_size,
            dedup_ratio=dedup_ratio,
            noise_reduction_pct=noise_pct,
            by_grouping_strategy=by_strat,
            by_priority=by_pri,
            by_group_status=by_stat,
            largest_groups=largest,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        pri_dist: dict[str, int] = {}
        for r in self._records:
            pri_dist[r.priority.value] = pri_dist.get(r.priority.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "similarity_threshold": self._similarity_threshold,
            "temporal_window_sec": self._temporal_window_sec,
            "priority_distribution": pri_dist,
            "unique_groups": len({r.group_id for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("intelligent_alert_grouping.cleared")
        return {"status": "cleared"}
