"""Telemetry Schema Registry

Schema versioning, backward compatibility validation, field deprecation
tracking, and migration planning for telemetry data governance.
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


class SchemaType(StrEnum):
    METRIC = "metric"
    LOG = "log"
    TRACE = "trace"
    EVENT = "event"
    RESOURCE = "resource"


class CompatibilityMode(StrEnum):
    BACKWARD = "backward"
    FORWARD = "forward"
    FULL = "full"
    NONE = "none"


class FieldStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    REMOVED = "removed"
    EXPERIMENTAL = "experimental"
    STABLE = "stable"


class MigrationStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


# --- Models ---


class SchemaRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schema_name: str = ""
    version: str = ""
    schema_type: SchemaType = SchemaType.METRIC
    compatibility_mode: CompatibilityMode = CompatibilityMode.BACKWARD
    field_count: int = 0
    deprecated_field_count: int = 0
    breaking_changes: int = 0
    is_compatible: bool = True
    owner_team: str = ""
    consumers: list[str] = Field(default_factory=list)
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class FieldDeprecation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schema_name: str = ""
    field_name: str = ""
    field_status: FieldStatus = FieldStatus.ACTIVE
    deprecated_in_version: str = ""
    removal_target_version: str = ""
    replacement_field: str = ""
    usage_count: int = 0
    consumer_count: int = 0
    created_at: float = Field(default_factory=time.time)


class SchemaRegistryReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_schemas: int = 0
    total_deprecations: int = 0
    incompatible_count: int = 0
    breaking_change_count: int = 0
    avg_field_count: float = 0.0
    deprecation_rate: float = 0.0
    by_schema_type: dict[str, int] = Field(default_factory=dict)
    by_compatibility_mode: dict[str, int] = Field(default_factory=dict)
    by_field_status: dict[str, int] = Field(default_factory=dict)
    schemas_with_breaking_changes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TelemetrySchemaRegistry:
    """Telemetry Schema Registry

    Schema versioning, backward compatibility validation, field deprecation
    tracking, and migration planning.
    """

    def __init__(
        self,
        max_records: int = 200000,
        max_deprecated_ratio: float = 0.30,
    ) -> None:
        self._max_records = max_records
        self._max_deprecated_ratio = max_deprecated_ratio
        self._records: list[SchemaRecord] = []
        self._deprecations: list[FieldDeprecation] = []
        logger.info(
            "telemetry_schema_registry.initialized",
            max_records=max_records,
            max_deprecated_ratio=max_deprecated_ratio,
        )

    def add_record(
        self,
        schema_name: str,
        version: str,
        schema_type: SchemaType = SchemaType.METRIC,
        compatibility_mode: CompatibilityMode = CompatibilityMode.BACKWARD,
        field_count: int = 0,
        deprecated_field_count: int = 0,
        breaking_changes: int = 0,
        owner_team: str = "",
        consumers: list[str] | None = None,
        service: str = "",
        team: str = "",
    ) -> SchemaRecord:
        is_compatible = breaking_changes == 0
        if compatibility_mode == CompatibilityMode.NONE:
            is_compatible = True
        record = SchemaRecord(
            schema_name=schema_name,
            version=version,
            schema_type=schema_type,
            compatibility_mode=compatibility_mode,
            field_count=field_count,
            deprecated_field_count=deprecated_field_count,
            breaking_changes=breaking_changes,
            is_compatible=is_compatible,
            owner_team=owner_team,
            consumers=consumers or [],
            service=service,
            team=team or owner_team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "telemetry_schema_registry.record_added",
            record_id=record.id,
            schema_name=schema_name,
            version=version,
            is_compatible=is_compatible,
        )
        return record

    def add_deprecation(
        self,
        schema_name: str,
        field_name: str,
        field_status: FieldStatus = FieldStatus.DEPRECATED,
        deprecated_in_version: str = "",
        removal_target_version: str = "",
        replacement_field: str = "",
        usage_count: int = 0,
        consumer_count: int = 0,
    ) -> FieldDeprecation:
        dep = FieldDeprecation(
            schema_name=schema_name,
            field_name=field_name,
            field_status=field_status,
            deprecated_in_version=deprecated_in_version,
            removal_target_version=removal_target_version,
            replacement_field=replacement_field,
            usage_count=usage_count,
            consumer_count=consumer_count,
        )
        self._deprecations.append(dep)
        if len(self._deprecations) > self._max_records:
            self._deprecations = self._deprecations[-self._max_records :]
        logger.info(
            "telemetry_schema_registry.deprecation_added",
            schema_name=schema_name,
            field_name=field_name,
            field_status=field_status.value,
        )
        return dep

    def get_record(self, record_id: str) -> SchemaRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        schema_type: SchemaType | None = None,
        compatibility_mode: CompatibilityMode | None = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[SchemaRecord]:
        results = list(self._records)
        if schema_type is not None:
            results = [r for r in results if r.schema_type == schema_type]
        if compatibility_mode is not None:
            results = [r for r in results if r.compatibility_mode == compatibility_mode]
        if service is not None:
            results = [r for r in results if r.service == service]
        return results[-limit:]

    def validate_compatibility(self, schema_name: str) -> dict[str, Any]:
        versions = [r for r in self._records if r.schema_name == schema_name]
        if not versions:
            return {"schema_name": schema_name, "status": "no_data"}
        versions_sorted = sorted(versions, key=lambda x: x.version)
        breaking = sum(v.breaking_changes for v in versions_sorted)
        incompatible = sum(1 for v in versions_sorted if not v.is_compatible)
        latest = versions_sorted[-1]
        dep_ratio = latest.deprecated_field_count / max(1, latest.field_count)
        return {
            "schema_name": schema_name,
            "version_count": len(versions_sorted),
            "latest_version": latest.version,
            "total_breaking_changes": breaking,
            "incompatible_versions": incompatible,
            "deprecation_ratio": round(dep_ratio, 4),
            "compatible": incompatible == 0,
        }

    def plan_migration(self, schema_name: str) -> dict[str, Any]:
        deps = [d for d in self._deprecations if d.schema_name == schema_name]
        if not deps:
            return {"schema_name": schema_name, "status": "no_deprecations"}
        active_deps = [d for d in deps if d.field_status == FieldStatus.DEPRECATED]
        total_usage = sum(d.usage_count for d in active_deps)
        total_consumers = sum(d.consumer_count for d in active_deps)
        steps: list[dict[str, Any]] = []
        for d in sorted(active_deps, key=lambda x: x.consumer_count, reverse=True):
            steps.append(
                {
                    "field": d.field_name,
                    "replacement": d.replacement_field or "N/A",
                    "usage_count": d.usage_count,
                    "consumer_count": d.consumer_count,
                    "target_version": d.removal_target_version,
                    "effort": "high" if d.consumer_count > 5 else "low",
                }
            )
        return {
            "schema_name": schema_name,
            "deprecated_fields": len(active_deps),
            "total_usage": total_usage,
            "total_consumers": total_consumers,
            "migration_steps": steps,
        }

    def process(self, schema_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.schema_name == schema_name]
        if not matching:
            return {"schema_name": schema_name, "status": "no_data"}
        latest = sorted(matching, key=lambda x: x.version)[-1]
        deps = [d for d in self._deprecations if d.schema_name == schema_name]
        dep_ratio = latest.deprecated_field_count / max(1, latest.field_count)
        health = "healthy"
        if not latest.is_compatible:
            health = "breaking_changes"
        elif dep_ratio > self._max_deprecated_ratio:
            health = "high_deprecation"
        return {
            "schema_name": schema_name,
            "version_count": len(matching),
            "latest_version": latest.version,
            "field_count": latest.field_count,
            "deprecated_fields": latest.deprecated_field_count,
            "deprecation_ratio": round(dep_ratio, 4),
            "total_deprecation_records": len(deps),
            "health": health,
        }

    def generate_report(self) -> SchemaRegistryReport:
        by_type: dict[str, int] = {}
        by_compat: dict[str, int] = {}
        for r in self._records:
            by_type[r.schema_type.value] = by_type.get(r.schema_type.value, 0) + 1
            by_compat[r.compatibility_mode.value] = by_compat.get(r.compatibility_mode.value, 0) + 1
        by_field_status: dict[str, int] = {}
        for d in self._deprecations:
            by_field_status[d.field_status.value] = by_field_status.get(d.field_status.value, 0) + 1
        incompatible = sum(1 for r in self._records if not r.is_compatible)
        breaking_total = sum(r.breaking_changes for r in self._records)
        fields = [r.field_count for r in self._records]
        dep_fields = sum(r.deprecated_field_count for r in self._records)
        total_fields = sum(fields)
        breaking_schemas = list({r.schema_name for r in self._records if r.breaking_changes > 0})
        recs: list[str] = []
        if incompatible > 0:
            recs.append(f"{incompatible} schema(s) have compatibility violations")
        if breaking_total > 0:
            recs.append(f"{breaking_total} breaking change(s) detected across schemas")
        if total_fields > 0 and dep_fields / total_fields > self._max_deprecated_ratio:
            recs.append(f"Deprecation ratio {dep_fields / total_fields:.1%} exceeds threshold")
        if not recs:
            recs.append("Schema registry is healthy — all schemas compatible")
        return SchemaRegistryReport(
            total_schemas=len(self._records),
            total_deprecations=len(self._deprecations),
            incompatible_count=incompatible,
            breaking_change_count=breaking_total,
            avg_field_count=round(sum(fields) / max(1, len(fields)), 2),
            deprecation_rate=round(dep_fields / max(1, total_fields), 4),
            by_schema_type=by_type,
            by_compatibility_mode=by_compat,
            by_field_status=by_field_status,
            schemas_with_breaking_changes=breaking_schemas[:10],
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            type_dist[r.schema_type.value] = type_dist.get(r.schema_type.value, 0) + 1
        return {
            "total_schemas": len(self._records),
            "total_deprecations": len(self._deprecations),
            "max_deprecated_ratio": self._max_deprecated_ratio,
            "schema_type_distribution": type_dist,
            "unique_schema_names": len({r.schema_name for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._deprecations.clear()
        logger.info("telemetry_schema_registry.cleared")
        return {"status": "cleared"}
