"""Event Driven Topology Mapper —
map event flow paths, detect circular flows,
rank services by event centrality."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FlowPattern(StrEnum):
    POINT_TO_POINT = "point_to_point"
    FANOUT = "fanout"
    FANIN = "fanin"
    PIPELINE = "pipeline"


class TopologyRole(StrEnum):
    PRODUCER = "producer"
    CONSUMER = "consumer"
    PROCESSOR = "processor"
    ROUTER = "router"


class CentralityLevel(StrEnum):
    HUB = "hub"
    SIGNIFICANT = "significant"
    PERIPHERAL = "peripheral"
    ISOLATED = "isolated"


# --- Models ---


class TopologyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    flow_pattern: FlowPattern = FlowPattern.POINT_TO_POINT
    topology_role: TopologyRole = TopologyRole.PRODUCER
    centrality_level: CentralityLevel = CentralityLevel.PERIPHERAL
    connection_count: int = 0
    event_rate: float = 0.0
    target_service: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TopologyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    flow_pattern: FlowPattern = FlowPattern.POINT_TO_POINT
    centrality_score: float = 0.0
    circular_risk: bool = False
    path_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TopologyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_connection_count: float = 0.0
    by_flow_pattern: dict[str, int] = Field(default_factory=dict)
    by_role: dict[str, int] = Field(default_factory=dict)
    by_centrality: dict[str, int] = Field(default_factory=dict)
    hub_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EventDrivenTopologyMapper:
    """Map event flow paths, detect circular flows,
    rank services by event centrality."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TopologyRecord] = []
        self._analyses: dict[str, TopologyAnalysis] = {}
        logger.info(
            "event_driven_topology_mapper.init",
            max_records=max_records,
        )

    def record_item(
        self,
        service_name: str = "",
        flow_pattern: FlowPattern = (FlowPattern.POINT_TO_POINT),
        topology_role: TopologyRole = (TopologyRole.PRODUCER),
        centrality_level: CentralityLevel = (CentralityLevel.PERIPHERAL),
        connection_count: int = 0,
        event_rate: float = 0.0,
        target_service: str = "",
        description: str = "",
    ) -> TopologyRecord:
        record = TopologyRecord(
            service_name=service_name,
            flow_pattern=flow_pattern,
            topology_role=topology_role,
            centrality_level=centrality_level,
            connection_count=connection_count,
            event_rate=event_rate,
            target_service=target_service,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "topology_mapper.item_recorded",
            record_id=record.id,
            service_name=service_name,
        )
        return record

    def process(self, key: str) -> TopologyAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        centrality = round(
            rec.connection_count * 10.0 + rec.event_rate * 0.1,
            2,
        )
        circular = rec.target_service == rec.service_name
        paths = sum(
            1
            for r in self._records
            if r.service_name == rec.service_name or r.target_service == rec.service_name
        )
        analysis = TopologyAnalysis(
            service_name=rec.service_name,
            flow_pattern=rec.flow_pattern,
            centrality_score=centrality,
            circular_risk=circular,
            path_count=paths,
            description=(f"Service {rec.service_name} centrality {centrality}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> TopologyReport:
        by_fp: dict[str, int] = {}
        by_r: dict[str, int] = {}
        by_cl: dict[str, int] = {}
        conns: list[int] = []
        for r in self._records:
            k = r.flow_pattern.value
            by_fp[k] = by_fp.get(k, 0) + 1
            k2 = r.topology_role.value
            by_r[k2] = by_r.get(k2, 0) + 1
            k3 = r.centrality_level.value
            by_cl[k3] = by_cl.get(k3, 0) + 1
            conns.append(r.connection_count)
        avg = round(sum(conns) / len(conns), 2) if conns else 0.0
        hubs = list(
            {
                r.service_name
                for r in self._records
                if r.centrality_level
                in (
                    CentralityLevel.HUB,
                    CentralityLevel.SIGNIFICANT,
                )
            }
        )[:10]
        recs: list[str] = []
        if hubs:
            recs.append(f"{len(hubs)} hub services detected")
        if not recs:
            recs.append("Topology well-distributed")
        return TopologyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_connection_count=avg,
            by_flow_pattern=by_fp,
            by_role=by_r,
            by_centrality=by_cl,
            hub_services=hubs,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        fp_dist: dict[str, int] = {}
        for r in self._records:
            k = r.flow_pattern.value
            fp_dist[k] = fp_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "flow_pattern_distribution": fp_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("event_driven_topology_mapper.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def map_event_flow_paths(
        self,
    ) -> list[dict[str, Any]]:
        """Map event flow paths between services."""
        paths: dict[str, set[str]] = {}
        rates: dict[str, float] = {}
        for r in self._records:
            paths.setdefault(r.service_name, set()).add(r.target_service)
            rates[r.service_name] = rates.get(r.service_name, 0.0) + r.event_rate
        results: list[dict[str, Any]] = []
        for svc, targets in paths.items():
            results.append(
                {
                    "service_name": svc,
                    "targets": sorted(targets),
                    "path_count": len(targets),
                    "total_event_rate": round(rates[svc], 2),
                }
            )
        results.sort(
            key=lambda x: x["path_count"],
            reverse=True,
        )
        return results

    def detect_circular_event_flows(
        self,
    ) -> list[dict[str, Any]]:
        """Detect circular event flows."""
        edges: dict[str, set[str]] = {}
        for r in self._records:
            edges.setdefault(r.service_name, set()).add(r.target_service)
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for svc, targets in edges.items():
            for tgt in targets:
                if tgt in edges and svc in edges.get(tgt, set()) and svc not in seen:
                    seen.add(svc)
                    results.append(
                        {
                            "service_a": svc,
                            "service_b": tgt,
                            "circular": True,
                            "risk": "high",
                        }
                    )
        return results

    def rank_services_by_event_centrality(
        self,
    ) -> list[dict[str, Any]]:
        """Rank services by event centrality."""
        svc_score: dict[str, float] = {}
        for r in self._records:
            score = r.connection_count * 10.0 + r.event_rate * 0.1
            svc_score[r.service_name] = svc_score.get(r.service_name, 0.0) + score
        results: list[dict[str, Any]] = []
        for svc, score in svc_score.items():
            results.append(
                {
                    "service_name": svc,
                    "centrality_score": round(score, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["centrality_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
