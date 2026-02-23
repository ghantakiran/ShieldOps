"""API Contract Testing Engine — schema versioning, breaking change detection."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BreakingChangeType(StrEnum):
    FIELD_REMOVED = "field_removed"
    TYPE_CHANGED = "type_changed"
    REQUIRED_ADDED = "required_added"
    ENUM_VALUE_REMOVED = "enum_value_removed"
    PATH_REMOVED = "path_removed"


class CompatibilityResult(StrEnum):
    COMPATIBLE = "compatible"
    BACKWARD_COMPATIBLE = "backward_compatible"
    BREAKING = "breaking"
    UNKNOWN = "unknown"


class SchemaFormat(StrEnum):
    OPENAPI_3 = "openapi_3"
    JSON_SCHEMA = "json_schema"
    PROTOBUF = "protobuf"
    GRAPHQL_SDL = "graphql_sdl"


# --- Models ---


class SchemaVersion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_name: str
    version: str
    schema_format: SchemaFormat = SchemaFormat.OPENAPI_3
    schema_content: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class CompatibilityCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_name: str
    from_version: str
    to_version: str
    result: CompatibilityResult = CompatibilityResult.UNKNOWN
    breaking_changes: list[str] = Field(default_factory=list)
    checked_at: float = Field(default_factory=time.time)


class BreakingChange(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_name: str
    change_type: BreakingChangeType
    path: str = ""
    description: str = ""
    from_version: str = ""
    to_version: str = ""
    detected_at: float = Field(default_factory=time.time)


# --- Engine ---


class APIContractTestingEngine:
    """Schema versioning, breaking change detection, compatibility checks, schema drift tracking."""

    def __init__(
        self,
        max_schemas: int = 5000,
        max_checks: int = 50000,
    ) -> None:
        self._max_schemas = max_schemas
        self._max_checks = max_checks
        self._schemas: dict[str, SchemaVersion] = {}
        self._checks: list[CompatibilityCheck] = []
        logger.info(
            "contract_testing.initialized",
            max_schemas=max_schemas,
            max_checks=max_checks,
        )

    def register_schema(
        self,
        api_name: str,
        version: str,
        schema_format: SchemaFormat = SchemaFormat.OPENAPI_3,
        schema_content: dict[str, Any] | None = None,
    ) -> SchemaVersion:
        schema = SchemaVersion(
            api_name=api_name,
            version=version,
            schema_format=schema_format,
            schema_content=schema_content or {},
        )
        self._schemas[schema.id] = schema
        if len(self._schemas) > self._max_schemas:
            oldest = next(iter(self._schemas))
            del self._schemas[oldest]
        logger.info(
            "contract_testing.schema_registered",
            schema_id=schema.id,
            api_name=api_name,
            version=version,
        )
        return schema

    def get_schema(self, schema_id: str) -> SchemaVersion | None:
        return self._schemas.get(schema_id)

    def list_versions(self, api_name: str) -> list[SchemaVersion]:
        return [s for s in self._schemas.values() if s.api_name == api_name]

    def get_latest_version(self, api_name: str) -> SchemaVersion | None:
        versions = self.list_versions(api_name)
        if not versions:
            return None
        return max(versions, key=lambda s: s.created_at)

    def check_compatibility(
        self,
        api_name: str,
        from_version: str,
        to_version: str,
    ) -> CompatibilityCheck:
        from_schemas = [
            s
            for s in self._schemas.values()
            if s.api_name == api_name and s.version == from_version
        ]
        to_schemas = [
            s for s in self._schemas.values() if s.api_name == api_name and s.version == to_version
        ]
        if not from_schemas or not to_schemas:
            check = CompatibilityCheck(
                api_name=api_name,
                from_version=from_version,
                to_version=to_version,
                result=CompatibilityResult.UNKNOWN,
            )
            self._checks.append(check)
            return check
        old_keys = set(from_schemas[0].schema_content.keys())
        new_keys = set(to_schemas[0].schema_content.keys())
        removed = old_keys - new_keys
        added = new_keys - old_keys
        breaking: list[str] = []
        for key in removed:
            breaking.append(f"Field removed: {key}")
        for key in old_keys & new_keys:
            old_val = from_schemas[0].schema_content[key]
            new_val = to_schemas[0].schema_content[key]
            if type(old_val) is not type(new_val):
                breaking.append(f"Type changed: {key}")
        if breaking:
            result = CompatibilityResult.BREAKING
        elif added:
            result = CompatibilityResult.BACKWARD_COMPATIBLE
        else:
            result = CompatibilityResult.COMPATIBLE
        check = CompatibilityCheck(
            api_name=api_name,
            from_version=from_version,
            to_version=to_version,
            result=result,
            breaking_changes=breaking,
        )
        self._checks.append(check)
        if len(self._checks) > self._max_checks:
            self._checks = self._checks[-self._max_checks :]
        logger.info(
            "contract_testing.compatibility_checked",
            api_name=api_name,
            result=result,
        )
        return check

    def detect_breaking_changes(
        self,
        api_name: str,
        from_version: str,
        to_version: str,
    ) -> list[BreakingChange]:
        from_schemas = [
            s
            for s in self._schemas.values()
            if s.api_name == api_name and s.version == from_version
        ]
        to_schemas = [
            s for s in self._schemas.values() if s.api_name == api_name and s.version == to_version
        ]
        if not from_schemas or not to_schemas:
            return []
        old_content = from_schemas[0].schema_content
        new_content = to_schemas[0].schema_content
        changes: list[BreakingChange] = []
        for key in set(old_content.keys()) - set(new_content.keys()):
            changes.append(
                BreakingChange(
                    api_name=api_name,
                    change_type=BreakingChangeType.FIELD_REMOVED,
                    path=key,
                    description=f"Field '{key}' was removed",
                    from_version=from_version,
                    to_version=to_version,
                )
            )
        for key in set(old_content.keys()) & set(new_content.keys()):
            if type(old_content[key]) is not type(new_content[key]):
                changes.append(
                    BreakingChange(
                        api_name=api_name,
                        change_type=BreakingChangeType.TYPE_CHANGED,
                        path=key,
                        description=f"Type of '{key}' changed",
                        from_version=from_version,
                        to_version=to_version,
                    )
                )
        return changes

    def get_schema_drift(self, api_name: str) -> dict[str, Any]:
        versions = self.list_versions(api_name)
        if len(versions) < 2:
            return {"api_name": api_name, "drift_detected": False, "versions_compared": 0}
        sorted_versions = sorted(versions, key=lambda s: s.created_at)
        latest = sorted_versions[-1]
        previous = sorted_versions[-2]
        check = self.check_compatibility(api_name, previous.version, latest.version)
        return {
            "api_name": api_name,
            "drift_detected": check.result != CompatibilityResult.COMPATIBLE,
            "versions_compared": 2,
            "from_version": previous.version,
            "to_version": latest.version,
            "result": check.result,
            "breaking_changes": check.breaking_changes,
        }

    def list_checks(
        self,
        api_name: str | None = None,
        result: CompatibilityResult | None = None,
    ) -> list[CompatibilityCheck]:
        checks = list(self._checks)
        if api_name is not None:
            checks = [c for c in checks if c.api_name == api_name]
        if result is not None:
            checks = [c for c in checks if c.result == result]
        return checks

    def delete_schema(self, schema_id: str) -> bool:
        if schema_id in self._schemas:
            del self._schemas[schema_id]
            logger.info("contract_testing.schema_deleted", schema_id=schema_id)
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        format_counts: dict[str, int] = {}
        api_counts: dict[str, int] = {}
        for s in self._schemas.values():
            format_counts[s.schema_format] = format_counts.get(s.schema_format, 0) + 1
            api_counts[s.api_name] = api_counts.get(s.api_name, 0) + 1
        result_counts: dict[str, int] = {}
        for c in self._checks:
            result_counts[c.result] = result_counts.get(c.result, 0) + 1
        return {
            "total_schemas": len(self._schemas),
            "total_checks": len(self._checks),
            "unique_apis": len(api_counts),
            "format_distribution": format_counts,
            "result_distribution": result_counts,
        }
