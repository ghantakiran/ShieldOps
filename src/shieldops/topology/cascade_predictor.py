"""Cascading Failure Predictor — graph-based multi-hop cascade propagation prediction."""

from __future__ import annotations

import time
import uuid
from collections import deque
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PropagationMode(StrEnum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    EXPONENTIAL = "exponential"
    PROBABILISTIC = "probabilistic"
    BOUNDED = "bounded"


class FailureType(StrEnum):
    LATENCY_SPIKE = "latency_spike"
    TOTAL_OUTAGE = "total_outage"
    PARTIAL_DEGRADATION = "partial_degradation"
    DATA_CORRUPTION = "data_corruption"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


class CascadeRisk(StrEnum):
    NEGLIGIBLE = "negligible"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


# --- Models ---


class ServiceNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    dependencies: list[str] = Field(default_factory=list)
    failure_type: FailureType = FailureType.LATENCY_SPIKE
    propagation_mode: PropagationMode = PropagationMode.SEQUENTIAL
    criticality_score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class CascadePrediction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_service_id: str = ""
    affected_services: list[str] = Field(default_factory=list)
    cascade_depth: int = 0
    propagation_mode: PropagationMode = PropagationMode.SEQUENTIAL
    risk_level: CascadeRisk = CascadeRisk.LOW
    estimated_impact_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class CascadeReport(BaseModel):
    total_services: int = 0
    critical_paths: int = 0
    single_points_of_failure: int = 0
    avg_cascade_depth: float = 0.0
    max_cascade_depth: int = 0
    risk_distribution: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CascadingFailurePredictor:
    """Graph-based multi-hop cascade propagation prediction for service topologies."""

    def __init__(
        self,
        max_services: int = 50000,
        max_cascade_depth: int = 10,
    ) -> None:
        self._max_services = max_services
        self._max_cascade_depth = max_cascade_depth
        self._services: list[ServiceNode] = []
        self._predictions: list[CascadePrediction] = []
        logger.info(
            "cascade_predictor.initialized",
            max_services=max_services,
            max_cascade_depth=max_cascade_depth,
        )

    def register_service(
        self,
        service_name: str,
        dependencies: list[str] | None = None,
        failure_type: FailureType = FailureType.LATENCY_SPIKE,
        propagation_mode: PropagationMode = PropagationMode.SEQUENTIAL,
        criticality_score: float = 0.0,
    ) -> ServiceNode:
        node = ServiceNode(
            service_name=service_name,
            dependencies=dependencies or [],
            failure_type=failure_type,
            propagation_mode=propagation_mode,
            criticality_score=criticality_score,
        )
        self._services.append(node)
        if len(self._services) > self._max_services:
            self._services = self._services[-self._max_services :]
        logger.info(
            "cascade_predictor.service_registered",
            service_id=node.id,
            service_name=service_name,
            dependency_count=len(node.dependencies),
            failure_type=failure_type,
        )
        return node

    def get_service(self, service_id: str) -> ServiceNode | None:
        for s in self._services:
            if s.id == service_id:
                return s
        return None

    def list_services(
        self,
        failure_type: FailureType | None = None,
        propagation_mode: PropagationMode | None = None,
        limit: int = 100,
    ) -> list[ServiceNode]:
        results = list(self._services)
        if failure_type is not None:
            results = [s for s in results if s.failure_type == failure_type]
        if propagation_mode is not None:
            results = [s for s in results if s.propagation_mode == propagation_mode]
        return results[-limit:]

    def _build_reverse_dependency_map(self) -> dict[str, list[str]]:
        """Build a map from service_id -> list of service_ids that depend on it."""
        name_to_id: dict[str, str] = {}
        for s in self._services:
            name_to_id[s.service_name] = s.id

        reverse_deps: dict[str, list[str]] = {}
        for s in self._services:
            for dep_name in s.dependencies:
                dep_id = name_to_id.get(dep_name)
                if dep_id is not None:
                    reverse_deps.setdefault(dep_id, []).append(s.id)
        return reverse_deps

    def predict_cascade(self, source_service_id: str) -> CascadePrediction:
        source = self.get_service(source_service_id)
        if source is None:
            return CascadePrediction(source_service_id=source_service_id)

        reverse_deps = self._build_reverse_dependency_map()
        total_services = len(self._services)

        # BFS traversal from the source service
        visited: set[str] = set()
        visited.add(source_service_id)
        queue: deque[tuple[str, int]] = deque()
        queue.append((source_service_id, 0))
        max_depth = 0
        affected: list[str] = []

        while queue:
            current_id, depth = queue.popleft()
            if depth >= self._max_cascade_depth:
                continue

            dependents = reverse_deps.get(current_id, [])
            for dep_id in dependents:
                if dep_id not in visited:
                    visited.add(dep_id)
                    affected.append(dep_id)
                    next_depth = depth + 1
                    if next_depth > max_depth:
                        max_depth = next_depth
                    queue.append((dep_id, next_depth))

        # Determine risk level based on depth and affected count
        affected_pct = (len(affected) / total_services * 100) if total_services > 0 else 0.0
        if max_depth >= 5 or affected_pct >= 50:
            risk_level = CascadeRisk.CRITICAL
        elif max_depth >= 4 or affected_pct >= 30:
            risk_level = CascadeRisk.HIGH
        elif max_depth >= 3 or affected_pct >= 15:
            risk_level = CascadeRisk.MODERATE
        elif max_depth >= 2 or affected_pct >= 5:
            risk_level = CascadeRisk.LOW
        else:
            risk_level = CascadeRisk.NEGLIGIBLE

        prediction = CascadePrediction(
            source_service_id=source_service_id,
            affected_services=affected,
            cascade_depth=max_depth,
            propagation_mode=source.propagation_mode,
            risk_level=risk_level,
            estimated_impact_pct=round(affected_pct, 2),
        )
        self._predictions.append(prediction)
        if len(self._predictions) > self._max_services:
            self._predictions = self._predictions[-self._max_services :]

        logger.info(
            "cascade_predictor.cascade_predicted",
            source_service_id=source_service_id,
            affected_count=len(affected),
            cascade_depth=max_depth,
            risk_level=risk_level,
        )
        return prediction

    def identify_critical_paths(self) -> list[dict[str, Any]]:
        """Find services whose failure affects >30% of all services."""
        total = len(self._services)
        if total == 0:
            return []

        critical_paths: list[dict[str, Any]] = []
        threshold_pct = 30.0

        for service in self._services:
            prediction = self.predict_cascade(service.id)
            if prediction.estimated_impact_pct > threshold_pct:
                critical_paths.append(
                    {
                        "service_id": service.id,
                        "service_name": service.service_name,
                        "affected_count": len(prediction.affected_services),
                        "impact_pct": prediction.estimated_impact_pct,
                        "cascade_depth": prediction.cascade_depth,
                        "risk_level": prediction.risk_level.value,
                    }
                )

        critical_paths.sort(key=lambda x: x["impact_pct"], reverse=True)
        logger.info(
            "cascade_predictor.critical_paths_identified",
            critical_path_count=len(critical_paths),
        )
        return critical_paths

    def calculate_blast_radius(self, service_id: str) -> dict[str, Any]:
        """Predict cascade and return affected count, percentage, and depth."""
        service = self.get_service(service_id)
        if service is None:
            return {
                "service_id": service_id,
                "service_name": "",
                "affected_count": 0,
                "affected_pct": 0.0,
                "cascade_depth": 0,
                "risk_level": CascadeRisk.NEGLIGIBLE.value,
            }

        prediction = self.predict_cascade(service_id)
        return {
            "service_id": service_id,
            "service_name": service.service_name,
            "affected_count": len(prediction.affected_services),
            "affected_pct": prediction.estimated_impact_pct,
            "cascade_depth": prediction.cascade_depth,
            "risk_level": prediction.risk_level.value,
        }

    def detect_single_points_of_failure(self) -> list[ServiceNode]:
        """Services that >3 other services depend on directly."""
        name_to_node: dict[str, ServiceNode] = {}
        for s in self._services:
            name_to_node[s.service_name] = s

        dependency_counts: dict[str, int] = {}
        for s in self._services:
            for dep_name in s.dependencies:
                dependency_counts[dep_name] = dependency_counts.get(dep_name, 0) + 1

        spofs: list[ServiceNode] = []
        for dep_name, count in dependency_counts.items():
            if count > 3:
                node = name_to_node.get(dep_name)
                if node is not None:
                    spofs.append(node)

        spofs.sort(key=lambda n: dependency_counts.get(n.service_name, 0), reverse=True)
        logger.info(
            "cascade_predictor.spofs_detected",
            spof_count=len(spofs),
        )
        return spofs

    def rank_services_by_cascade_risk(self) -> list[dict[str, Any]]:
        """Predict cascade for each service and sort by risk descending."""
        risk_order = {
            CascadeRisk.CRITICAL: 5,
            CascadeRisk.HIGH: 4,
            CascadeRisk.MODERATE: 3,
            CascadeRisk.LOW: 2,
            CascadeRisk.NEGLIGIBLE: 1,
        }

        rankings: list[dict[str, Any]] = []
        for service in self._services:
            prediction = self.predict_cascade(service.id)
            rankings.append(
                {
                    "service_id": service.id,
                    "service_name": service.service_name,
                    "risk_level": prediction.risk_level.value,
                    "risk_rank": risk_order.get(prediction.risk_level, 0),
                    "affected_count": len(prediction.affected_services),
                    "impact_pct": prediction.estimated_impact_pct,
                    "cascade_depth": prediction.cascade_depth,
                    "criticality_score": service.criticality_score,
                }
            )

        rankings.sort(key=lambda x: (x["risk_rank"], x["impact_pct"]), reverse=True)
        logger.info(
            "cascade_predictor.services_ranked",
            service_count=len(rankings),
        )
        return rankings

    def generate_cascade_report(self) -> CascadeReport:
        total = len(self._services)
        if total == 0:
            return CascadeReport()

        # Run predictions for all services
        all_predictions: list[CascadePrediction] = []
        for service in self._services:
            prediction = self.predict_cascade(service.id)
            all_predictions.append(prediction)

        critical_paths = self.identify_critical_paths()
        spofs = self.detect_single_points_of_failure()

        depths = [p.cascade_depth for p in all_predictions]
        avg_depth = sum(depths) / len(depths) if depths else 0.0
        max_depth = max(depths) if depths else 0

        # Risk distribution
        risk_dist: dict[str, int] = {}
        for p in all_predictions:
            key = p.risk_level.value
            risk_dist[key] = risk_dist.get(key, 0) + 1

        # Build recommendations
        recommendations: list[str] = []
        if spofs:
            recommendations.append(
                f"{len(spofs)} single point(s) of failure detected — "
                f"add redundancy for these services"
            )
        if critical_paths:
            recommendations.append(
                f"{len(critical_paths)} critical path(s) found — "
                f"implement circuit breakers and fallback mechanisms"
            )
        critical_count = risk_dist.get(CascadeRisk.CRITICAL.value, 0)
        if critical_count > 0:
            recommendations.append(
                f"{critical_count} service(s) pose critical cascade risk — "
                f"prioritize isolation and graceful degradation"
            )
        if avg_depth > 3:
            recommendations.append("High average cascade depth — reduce dependency chain lengths")

        report = CascadeReport(
            total_services=total,
            critical_paths=len(critical_paths),
            single_points_of_failure=len(spofs),
            avg_cascade_depth=round(avg_depth, 2),
            max_cascade_depth=max_depth,
            risk_distribution=risk_dist,
            recommendations=recommendations,
        )
        logger.info(
            "cascade_predictor.report_generated",
            total_services=total,
            critical_paths=len(critical_paths),
            spof_count=len(spofs),
        )
        return report

    def clear_data(self) -> None:
        self._services.clear()
        self._predictions.clear()
        logger.info("cascade_predictor.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        service_names = {s.service_name for s in self._services}
        failure_types = {s.failure_type.value for s in self._services}
        propagation_modes = {s.propagation_mode.value for s in self._services}
        return {
            "total_services": len(self._services),
            "total_predictions": len(self._predictions),
            "unique_service_names": len(service_names),
            "failure_types": sorted(failure_types),
            "propagation_modes": sorted(propagation_modes),
        }
