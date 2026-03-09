"""Realtime Streaming Analytics

Streaming telemetry processing, windowed aggregations, late-arrival handling,
and backpressure management for continuous observability pipelines.
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


class WindowType(StrEnum):
    TUMBLING = "tumbling"
    SLIDING = "sliding"
    SESSION = "session"
    HOPPING = "hopping"
    GLOBAL = "global"


class StreamStatus(StrEnum):
    HEALTHY = "healthy"
    BACKPRESSURE = "backpressure"
    LAGGING = "lagging"
    STALLED = "stalled"
    RECOVERING = "recovering"


class ArrivalStatus(StrEnum):
    ON_TIME = "on_time"
    LATE = "late"
    VERY_LATE = "very_late"
    OUT_OF_ORDER = "out_of_order"
    DUPLICATE = "duplicate"


# --- Models ---


class StreamRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    stream_name: str = ""
    window_type: WindowType = WindowType.TUMBLING
    stream_status: StreamStatus = StreamStatus.HEALTHY
    arrival_status: ArrivalStatus = ArrivalStatus.ON_TIME
    events_per_second: float = 0.0
    window_duration_sec: float = 60.0
    watermark_lag_ms: float = 0.0
    buffer_utilization_pct: float = 0.0
    late_event_count: int = 0
    dropped_event_count: int = 0
    service: str = ""
    partition: str = ""
    created_at: float = Field(default_factory=time.time)


class StreamAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    stream_name: str = ""
    throughput_score: float = 0.0
    latency_score: float = 0.0
    reliability_score: float = 0.0
    overall_score: float = 0.0
    backpressure_detected: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class StreamingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_events_per_second: float = 0.0
    total_late_events: int = 0
    total_dropped_events: int = 0
    avg_buffer_utilization: float = 0.0
    backpressure_count: int = 0
    by_window_type: dict[str, int] = Field(default_factory=dict)
    by_stream_status: dict[str, int] = Field(default_factory=dict)
    by_arrival_status: dict[str, int] = Field(default_factory=dict)
    lagging_streams: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RealtimeStreamingAnalytics:
    """Realtime Streaming Analytics

    Streaming telemetry processing, windowed aggregations, late-arrival
    handling, and backpressure management.
    """

    def __init__(
        self,
        max_records: int = 200000,
        backpressure_threshold_pct: float = 80.0,
        late_event_threshold: float = 0.05,
    ) -> None:
        self._max_records = max_records
        self._backpressure_threshold = backpressure_threshold_pct
        self._late_event_threshold = late_event_threshold
        self._records: list[StreamRecord] = []
        self._analyses: list[StreamAnalysis] = []
        logger.info(
            "realtime_streaming_analytics.initialized",
            max_records=max_records,
            backpressure_threshold_pct=backpressure_threshold_pct,
        )

    def add_record(
        self,
        stream_name: str,
        window_type: WindowType = WindowType.TUMBLING,
        stream_status: StreamStatus = StreamStatus.HEALTHY,
        arrival_status: ArrivalStatus = ArrivalStatus.ON_TIME,
        events_per_second: float = 0.0,
        window_duration_sec: float = 60.0,
        watermark_lag_ms: float = 0.0,
        buffer_utilization_pct: float = 0.0,
        late_event_count: int = 0,
        dropped_event_count: int = 0,
        service: str = "",
        partition: str = "",
    ) -> StreamRecord:
        record = StreamRecord(
            stream_name=stream_name,
            window_type=window_type,
            stream_status=stream_status,
            arrival_status=arrival_status,
            events_per_second=events_per_second,
            window_duration_sec=window_duration_sec,
            watermark_lag_ms=watermark_lag_ms,
            buffer_utilization_pct=buffer_utilization_pct,
            late_event_count=late_event_count,
            dropped_event_count=dropped_event_count,
            service=service,
            partition=partition,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "realtime_streaming_analytics.record_added",
            record_id=record.id,
            stream_name=stream_name,
            stream_status=stream_status.value,
        )
        return record

    def get_record(self, record_id: str) -> StreamRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        stream_name: str | None = None,
        stream_status: StreamStatus | None = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[StreamRecord]:
        results = list(self._records)
        if stream_name is not None:
            results = [r for r in results if r.stream_name == stream_name]
        if stream_status is not None:
            results = [r for r in results if r.stream_status == stream_status]
        if service is not None:
            results = [r for r in results if r.service == service]
        return results[-limit:]

    def compute_windowed_aggregation(self, stream_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.stream_name == stream_name]
        if not matching:
            return {"stream_name": stream_name, "status": "no_data"}
        eps_values = [r.events_per_second for r in matching]
        buf_values = [r.buffer_utilization_pct for r in matching]
        lag_values = [r.watermark_lag_ms for r in matching]
        return {
            "stream_name": stream_name,
            "window_count": len(matching),
            "avg_eps": round(sum(eps_values) / len(eps_values), 2),
            "max_eps": round(max(eps_values), 2),
            "min_eps": round(min(eps_values), 2),
            "avg_buffer_pct": round(sum(buf_values) / len(buf_values), 2),
            "max_buffer_pct": round(max(buf_values), 2),
            "avg_watermark_lag_ms": round(sum(lag_values) / len(lag_values), 2),
            "max_watermark_lag_ms": round(max(lag_values), 2),
        }

    def detect_backpressure(self) -> list[dict[str, Any]]:
        stream_bufs: dict[str, list[float]] = {}
        for r in self._records:
            stream_bufs.setdefault(r.stream_name, []).append(r.buffer_utilization_pct)
        issues: list[dict[str, Any]] = []
        for name, bufs in stream_bufs.items():
            avg_buf = sum(bufs) / len(bufs)
            if avg_buf > self._backpressure_threshold:
                issues.append(
                    {
                        "stream_name": name,
                        "avg_buffer_pct": round(avg_buf, 2),
                        "max_buffer_pct": round(max(bufs), 2),
                        "samples": len(bufs),
                        "severity": "critical" if avg_buf > 95 else "warning",
                    }
                )
        return sorted(issues, key=lambda x: x["avg_buffer_pct"], reverse=True)

    def analyze_late_arrivals(self) -> dict[str, Any]:
        total = len(self._records)
        if total == 0:
            return {"status": "no_data"}
        late_count = sum(1 for r in self._records if r.arrival_status != ArrivalStatus.ON_TIME)
        late_rate = round(late_count / total, 4)
        by_status: dict[str, int] = {}
        for r in self._records:
            by_status[r.arrival_status.value] = by_status.get(r.arrival_status.value, 0) + 1
        total_late_events = sum(r.late_event_count for r in self._records)
        total_dropped = sum(r.dropped_event_count for r in self._records)
        return {
            "total_records": total,
            "late_rate": late_rate,
            "total_late_events": total_late_events,
            "total_dropped_events": total_dropped,
            "by_arrival_status": by_status,
            "exceeds_threshold": late_rate > self._late_event_threshold,
        }

    def process(self, stream_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.stream_name == stream_name]
        if not matching:
            return {"stream_name": stream_name, "status": "no_data"}
        eps_vals = [r.events_per_second for r in matching]
        buf_vals = [r.buffer_utilization_pct for r in matching]
        late_total = sum(r.late_event_count for r in matching)
        dropped_total = sum(r.dropped_event_count for r in matching)
        avg_buf = sum(buf_vals) / len(buf_vals)
        throughput_score = min(100.0, round(sum(eps_vals) / len(eps_vals) / 10.0 * 100, 2))
        latency_score = max(0.0, round(100 - avg_buf, 2))
        reliability_score = max(
            0.0,
            round(
                100 - (dropped_total / max(1, sum(r.events_per_second for r in matching))) * 100, 2
            ),
        )
        overall = round((throughput_score + latency_score + reliability_score) / 3, 2)
        analysis = StreamAnalysis(
            stream_name=stream_name,
            throughput_score=throughput_score,
            latency_score=latency_score,
            reliability_score=reliability_score,
            overall_score=overall,
            backpressure_detected=avg_buf > self._backpressure_threshold,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return {
            "stream_name": stream_name,
            "flow_count": len(matching),
            "avg_eps": round(sum(eps_vals) / len(eps_vals), 2),
            "avg_buffer_pct": round(avg_buf, 2),
            "late_events": late_total,
            "dropped_events": dropped_total,
            "overall_score": overall,
            "backpressure": avg_buf > self._backpressure_threshold,
        }

    def generate_report(self) -> StreamingReport:
        by_wt: dict[str, int] = {}
        by_ss: dict[str, int] = {}
        by_as: dict[str, int] = {}
        for r in self._records:
            by_wt[r.window_type.value] = by_wt.get(r.window_type.value, 0) + 1
            by_ss[r.stream_status.value] = by_ss.get(r.stream_status.value, 0) + 1
            by_as[r.arrival_status.value] = by_as.get(r.arrival_status.value, 0) + 1
        eps_vals = [r.events_per_second for r in self._records]
        buf_vals = [r.buffer_utilization_pct for r in self._records]
        total_late = sum(r.late_event_count for r in self._records)
        total_dropped = sum(r.dropped_event_count for r in self._records)
        bp_count = sum(
            1 for r in self._records if r.buffer_utilization_pct > self._backpressure_threshold
        )
        lagging = list(
            {
                r.stream_name
                for r in self._records
                if r.stream_status in (StreamStatus.LAGGING, StreamStatus.STALLED)
            }
        )
        recs: list[str] = []
        if bp_count > 0:
            recs.append(f"{bp_count} record(s) showing backpressure — scale consumers")
        if total_late > 0:
            recs.append(f"{total_late} late events detected — increase watermark tolerance")
        if total_dropped > 0:
            recs.append(f"{total_dropped} events dropped — review buffer capacity")
        if lagging:
            recs.append(f"{len(lagging)} stream(s) lagging: {', '.join(lagging[:5])}")
        if not recs:
            recs.append("Streaming pipeline health is nominal")
        return StreamingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_events_per_second=round(sum(eps_vals) / len(eps_vals), 2) if eps_vals else 0.0,
            total_late_events=total_late,
            total_dropped_events=total_dropped,
            avg_buffer_utilization=round(sum(buf_vals) / len(buf_vals), 2) if buf_vals else 0.0,
            backpressure_count=bp_count,
            by_window_type=by_wt,
            by_stream_status=by_ss,
            by_arrival_status=by_as,
            lagging_streams=lagging[:10],
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            status_dist[r.stream_status.value] = status_dist.get(r.stream_status.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "backpressure_threshold_pct": self._backpressure_threshold,
            "late_event_threshold": self._late_event_threshold,
            "status_distribution": status_dist,
            "unique_streams": len({r.stream_name for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("realtime_streaming_analytics.cleared")
        return {"status": "cleared"}
