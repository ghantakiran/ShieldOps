"""SLI Calculation Pipeline — define, calculate, and aggregate SLIs from raw metric data points."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SLIType(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    SATURATION = "saturation"


class AggregationMethod(StrEnum):
    AVERAGE = "average"
    PERCENTILE_95 = "percentile_95"
    PERCENTILE_99 = "percentile_99"
    SUM = "sum"
    COUNT = "count"


class SLIHealth(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    BREACHING = "breaching"
    CRITICAL = "critical"
    NO_DATA = "no_data"


# --- Models ---


class SLIDefinition(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    sli_type: SLIType = SLIType.AVAILABILITY
    name: str = ""
    aggregation: AggregationMethod = AggregationMethod.AVERAGE
    target_value: float = 99.9
    warning_threshold: float = 99.5
    critical_threshold: float = 99.0
    unit: str = "percent"
    created_at: float = Field(default_factory=time.time)


class SLIDataPoint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sli_id: str = ""
    value: float = 0.0
    timestamp: float = Field(default_factory=time.time)
    labels: dict[str, Any] = Field(default_factory=dict)


class SLIPipelineReport(BaseModel):
    total_definitions: int = 0
    total_data_points: int = 0
    healthy_count: int = 0
    warning_count: int = 0
    breaching_count: int = 0
    critical_count: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLICalculationPipeline:
    """Define, calculate, and aggregate SLIs from raw metric data points."""

    def __init__(
        self,
        max_definitions: int = 50000,
        data_retention_hours: int = 168,
    ) -> None:
        self._max_definitions = max_definitions
        self._data_retention_hours = data_retention_hours
        self._definitions: list[SLIDefinition] = []
        self._data_points: list[SLIDataPoint] = []
        logger.info(
            "sli_pipeline.initialized",
            max_definitions=max_definitions,
            data_retention_hours=data_retention_hours,
        )

    def register_sli(
        self,
        service_name: str = "",
        sli_type: SLIType = SLIType.AVAILABILITY,
        name: str = "",
        aggregation: AggregationMethod = AggregationMethod.AVERAGE,
        target_value: float = 99.9,
        warning_threshold: float = 99.5,
        critical_threshold: float = 99.0,
        unit: str = "percent",
    ) -> SLIDefinition:
        definition = SLIDefinition(
            service_name=service_name,
            sli_type=sli_type,
            name=name,
            aggregation=aggregation,
            target_value=target_value,
            warning_threshold=warning_threshold,
            critical_threshold=critical_threshold,
            unit=unit,
        )
        self._definitions.append(definition)
        if len(self._definitions) > self._max_definitions:
            self._definitions = self._definitions[-self._max_definitions :]
        logger.info(
            "sli_pipeline.sli_registered",
            sli_id=definition.id,
            service_name=service_name,
            sli_type=sli_type,
            name=name,
        )
        return definition

    def get_sli(self, sli_id: str) -> SLIDefinition | None:
        for d in self._definitions:
            if d.id == sli_id:
                return d
        return None

    def list_slis(
        self,
        service_name: str | None = None,
        sli_type: SLIType | None = None,
        limit: int = 100,
    ) -> list[SLIDefinition]:
        results = list(self._definitions)
        if service_name is not None:
            results = [d for d in results if d.service_name == service_name]
        if sli_type is not None:
            results = [d for d in results if d.sli_type == sli_type]
        return results[-limit:]

    def ingest_data_point(
        self,
        sli_id: str,
        value: float,
        timestamp: float | None = None,
        labels: dict[str, Any] | None = None,
    ) -> SLIDataPoint | None:
        definition = self.get_sli(sli_id)
        if definition is None:
            return None
        data_point = SLIDataPoint(
            sli_id=sli_id,
            value=value,
            timestamp=timestamp if timestamp is not None else time.time(),
            labels=labels if labels is not None else {},
        )
        self._data_points.append(data_point)
        logger.info(
            "sli_pipeline.data_point_ingested",
            data_point_id=data_point.id,
            sli_id=sli_id,
            value=value,
        )
        return data_point

    def _get_data_points_for_sli(self, sli_id: str) -> list[SLIDataPoint]:
        return [dp for dp in self._data_points if dp.sli_id == sli_id]

    def calculate_sli_value(self, sli_id: str) -> dict[str, Any]:
        definition = self.get_sli(sli_id)
        if definition is None:
            return {
                "sli_id": sli_id,
                "aggregated_value": 0.0,
                "data_point_count": 0,
                "aggregation_method": "",
            }

        points = self._get_data_points_for_sli(sli_id)
        if not points:
            return {
                "sli_id": sli_id,
                "aggregated_value": 0.0,
                "data_point_count": 0,
                "aggregation_method": definition.aggregation.value,
            }

        values = [dp.value for dp in points]
        aggregation = definition.aggregation

        if aggregation == AggregationMethod.AVERAGE:
            aggregated = round(sum(values) / len(values), 4)
        elif aggregation == AggregationMethod.PERCENTILE_95:
            sorted_vals = sorted(values)
            idx = int(0.95 * (len(sorted_vals) - 1))
            aggregated = round(sorted_vals[idx], 4)
        elif aggregation == AggregationMethod.PERCENTILE_99:
            sorted_vals = sorted(values)
            idx = int(0.99 * (len(sorted_vals) - 1))
            aggregated = round(sorted_vals[idx], 4)
        elif aggregation == AggregationMethod.SUM:
            aggregated = round(sum(values), 4)
        elif aggregation == AggregationMethod.COUNT:
            aggregated = len(values)
        else:
            aggregated = round(sum(values) / len(values), 4)

        return {
            "sli_id": sli_id,
            "aggregated_value": aggregated,
            "data_point_count": len(values),
            "aggregation_method": aggregation.value,
        }

    def _is_lower_better(self, sli_type: SLIType) -> bool:
        return sli_type in (SLIType.LATENCY, SLIType.ERROR_RATE, SLIType.SATURATION)

    def evaluate_sli_health(self, sli_id: str) -> dict[str, Any]:
        definition = self.get_sli(sli_id)
        if definition is None:
            return {
                "sli_id": sli_id,
                "health": SLIHealth.NO_DATA.value,
                "current_value": 0.0,
                "target_value": 0.0,
            }

        calc = self.calculate_sli_value(sli_id)
        if calc["data_point_count"] == 0:
            return {
                "sli_id": sli_id,
                "health": SLIHealth.NO_DATA.value,
                "current_value": 0.0,
                "target_value": definition.target_value,
            }

        current_value = calc["aggregated_value"]
        target = definition.target_value
        warning = definition.warning_threshold
        critical = definition.critical_threshold

        if self._is_lower_better(definition.sli_type):
            # For latency/error_rate/saturation: lower is better
            if current_value <= target:
                health = SLIHealth.HEALTHY
            elif current_value <= warning:
                health = SLIHealth.WARNING
            elif current_value <= critical:
                health = SLIHealth.BREACHING
            else:
                health = SLIHealth.CRITICAL
        else:
            # For availability/throughput: higher is better
            if current_value >= target:
                health = SLIHealth.HEALTHY
            elif current_value >= warning:
                health = SLIHealth.WARNING
            elif current_value >= critical:
                health = SLIHealth.BREACHING
            else:
                health = SLIHealth.CRITICAL

        return {
            "sli_id": sli_id,
            "health": health.value,
            "current_value": current_value,
            "target_value": target,
        }

    def detect_sli_regression(self, sli_id: str) -> dict[str, Any]:
        definition = self.get_sli(sli_id)
        if definition is None:
            return {
                "sli_id": sli_id,
                "regression_detected": False,
                "first_half_avg": 0.0,
                "second_half_avg": 0.0,
                "change_pct": 0.0,
            }

        points = self._get_data_points_for_sli(sli_id)
        if len(points) < 2:
            return {
                "sli_id": sli_id,
                "regression_detected": False,
                "first_half_avg": 0.0,
                "second_half_avg": 0.0,
                "change_pct": 0.0,
            }

        mid = len(points) // 2
        first_half = points[:mid]
        second_half = points[mid:]

        first_avg = round(sum(dp.value for dp in first_half) / len(first_half), 4)
        second_avg = round(sum(dp.value for dp in second_half) / len(second_half), 4)

        if first_avg != 0:
            change_pct = round((second_avg - first_avg) / abs(first_avg) * 100, 2)
        else:
            change_pct = 0.0

        # Determine if regression: for lower-is-better metrics, increase is regression;
        # for higher-is-better metrics, decrease is regression.
        if self._is_lower_better(definition.sli_type):
            regression_detected = change_pct > 5.0
        else:
            regression_detected = change_pct < -5.0

        return {
            "sli_id": sli_id,
            "regression_detected": regression_detected,
            "first_half_avg": first_avg,
            "second_half_avg": second_avg,
            "change_pct": change_pct,
        }

    def aggregate_service_slis(self, service_name: str) -> dict[str, Any]:
        service_defs = [d for d in self._definitions if d.service_name == service_name]
        if not service_defs:
            return {
                "service_name": service_name,
                "sli_count": 0,
                "health_summary": {},
                "overall_health": SLIHealth.NO_DATA.value,
            }

        health_summary: dict[str, int] = {}
        worst_health = SLIHealth.HEALTHY
        health_order = [
            SLIHealth.HEALTHY,
            SLIHealth.WARNING,
            SLIHealth.BREACHING,
            SLIHealth.CRITICAL,
            SLIHealth.NO_DATA,
        ]

        for d in service_defs:
            evaluation = self.evaluate_sli_health(d.id)
            health_val = evaluation["health"]
            health_summary[health_val] = health_summary.get(health_val, 0) + 1

            current_health = SLIHealth(health_val)
            if health_order.index(current_health) > health_order.index(worst_health):
                worst_health = current_health

        return {
            "service_name": service_name,
            "sli_count": len(service_defs),
            "health_summary": health_summary,
            "overall_health": worst_health.value,
        }

    def generate_pipeline_report(self) -> SLIPipelineReport:
        by_type: dict[str, int] = {}
        by_health: dict[str, int] = {}
        healthy_count = 0
        warning_count = 0
        breaching_count = 0
        critical_count = 0
        recommendations: list[str] = []

        for d in self._definitions:
            by_type[d.sli_type.value] = by_type.get(d.sli_type.value, 0) + 1
            evaluation = self.evaluate_sli_health(d.id)
            health_val = evaluation["health"]
            by_health[health_val] = by_health.get(health_val, 0) + 1

            if health_val == SLIHealth.HEALTHY.value:
                healthy_count += 1
            elif health_val == SLIHealth.WARNING.value:
                warning_count += 1
            elif health_val == SLIHealth.BREACHING.value:
                breaching_count += 1
            elif health_val == SLIHealth.CRITICAL.value:
                critical_count += 1

        if critical_count > 0:
            recommendations.append(
                f"{critical_count} SLI(s) in critical state — immediate investigation required"
            )
        if breaching_count > 0:
            recommendations.append(
                f"{breaching_count} SLI(s) breaching thresholds — review targets and remediate"
            )
        if warning_count > 0:
            recommendations.append(
                f"{warning_count} SLI(s) in warning state — monitor closely for degradation"
            )
        if not self._data_points:
            recommendations.append(
                "No data points ingested — configure metric collection pipelines"
            )

        report = SLIPipelineReport(
            total_definitions=len(self._definitions),
            total_data_points=len(self._data_points),
            healthy_count=healthy_count,
            warning_count=warning_count,
            breaching_count=breaching_count,
            critical_count=critical_count,
            by_type=by_type,
            by_health=by_health,
            recommendations=recommendations,
        )
        logger.info(
            "sli_pipeline.report_generated",
            total_definitions=len(self._definitions),
            total_data_points=len(self._data_points),
            healthy=healthy_count,
            warning=warning_count,
            breaching=breaching_count,
            critical=critical_count,
        )
        return report

    def clear_data(self) -> None:
        self._definitions.clear()
        self._data_points.clear()
        logger.info("sli_pipeline.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        services = {d.service_name for d in self._definitions}
        type_distribution: dict[str, int] = {}
        for d in self._definitions:
            type_distribution[d.sli_type.value] = type_distribution.get(d.sli_type.value, 0) + 1
        aggregation_distribution: dict[str, int] = {}
        for d in self._definitions:
            aggregation_distribution[d.aggregation.value] = (
                aggregation_distribution.get(d.aggregation.value, 0) + 1
            )
        return {
            "total_definitions": len(self._definitions),
            "total_data_points": len(self._data_points),
            "unique_services": len(services),
            "type_distribution": type_distribution,
            "aggregation_distribution": aggregation_distribution,
        }
