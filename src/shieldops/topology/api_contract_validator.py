"""API Contract Validator — validate inter-service API contracts."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ContractStatus(StrEnum):
    VALID = "valid"
    BREAKING_CHANGE = "breaking_change"
    DEPRECATED_FIELD = "deprecated_field"
    MISSING_FIELD = "missing_field"
    VERSION_MISMATCH = "version_mismatch"


class BreakingChangeType(StrEnum):
    FIELD_REMOVED = "field_removed"
    TYPE_CHANGED = "type_changed"
    REQUIRED_ADDED = "required_added"
    ENDPOINT_REMOVED = "endpoint_removed"
    RESPONSE_CHANGED = "response_changed"


class SchemaFormat(StrEnum):
    OPENAPI = "openapi"
    PROTOBUF = "protobuf"
    GRAPHQL = "graphql"
    AVRO = "avro"
    JSON_SCHEMA = "json_schema"


# --- Models ---


class APIContract(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    provider_service: str = ""
    consumer_service: str = ""
    endpoint: str = ""
    schema_format: SchemaFormat = SchemaFormat.OPENAPI
    version: str = ""
    status: ContractStatus = ContractStatus.VALID
    fields: list[str] = Field(default_factory=list)
    breaking_changes: list[str] = Field(
        default_factory=list,
    )
    created_at: float = Field(default_factory=time.time)


class ContractViolation(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    contract_id: str = ""
    change_type: BreakingChangeType = BreakingChangeType.FIELD_REMOVED
    field_name: str = ""
    old_value: str = ""
    new_value: str = ""
    is_breaking: bool = False
    created_at: float = Field(default_factory=time.time)


class ContractReport(BaseModel):
    total_contracts: int = 0
    total_violations: int = 0
    compliance_pct: float = 0.0
    by_status: dict[str, int] = Field(
        default_factory=dict,
    )
    by_format: dict[str, int] = Field(
        default_factory=dict,
    )
    by_change_type: dict[str, int] = Field(
        default_factory=dict,
    )
    breaking_contracts: list[str] = Field(
        default_factory=list,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Validator ---


class APIContractValidator:
    """Validate API contracts between services for schema
    compatibility, breaking change detection, and version
    compliance."""

    def __init__(
        self,
        max_contracts: int = 100000,
        compliance_target_pct: float = 95.0,
    ) -> None:
        self._max_contracts = max_contracts
        self._compliance_target_pct = compliance_target_pct
        self._items: list[APIContract] = []
        self._violations: list[ContractViolation] = []
        logger.info(
            "api_contract_validator.initialized",
            max_contracts=max_contracts,
            compliance_target_pct=compliance_target_pct,
        )

    # -- register / get / list ---------------------------------------

    def register_contract(
        self,
        provider_service: str,
        consumer_service: str = "",
        endpoint: str = "",
        schema_format: SchemaFormat = (SchemaFormat.OPENAPI),
        version: str = "",
        fields: list[str] | None = None,
        **kw: Any,
    ) -> APIContract:
        """Register a new API contract."""
        contract = APIContract(
            provider_service=provider_service,
            consumer_service=consumer_service,
            endpoint=endpoint,
            schema_format=schema_format,
            version=version,
            fields=fields or [],
            **kw,
        )
        self._items.append(contract)
        if len(self._items) > self._max_contracts:
            self._items = self._items[-self._max_contracts :]
        logger.info(
            "api_contract_validator.registered",
            contract_id=contract.id,
            provider=provider_service,
            consumer=consumer_service,
        )
        return contract

    def get_contract(
        self,
        contract_id: str,
    ) -> APIContract | None:
        """Get a contract by ID."""
        for item in self._items:
            if item.id == contract_id:
                return item
        return None

    def list_contracts(
        self,
        provider: str | None = None,
        consumer: str | None = None,
        limit: int = 50,
    ) -> list[APIContract]:
        """List contracts with optional filters."""
        results = list(self._items)
        if provider is not None:
            results = [c for c in results if c.provider_service == provider]
        if consumer is not None:
            results = [c for c in results if c.consumer_service == consumer]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def validate_contract(
        self,
        contract_id: str,
    ) -> dict[str, Any] | None:
        """Validate a contract for completeness."""
        contract = self.get_contract(contract_id)
        if contract is None:
            return None
        issues: list[str] = []
        if not contract.endpoint:
            issues.append("missing endpoint")
        if not contract.version:
            issues.append("missing version")
        if not contract.fields:
            issues.append("no fields defined")
        status = ContractStatus.VALID if not issues else ContractStatus.MISSING_FIELD
        contract.status = status
        logger.info(
            "api_contract_validator.validated",
            contract_id=contract_id,
            status=status,
            issues=issues,
        )
        return {
            "contract_id": contract_id,
            "status": status.value,
            "issues": issues,
            "is_valid": len(issues) == 0,
        }

    def detect_breaking_changes(
        self,
        contract_id: str,
        new_fields: list[str],
    ) -> list[ContractViolation]:
        """Detect breaking changes between current and
        new fields."""
        contract = self.get_contract(contract_id)
        if contract is None:
            return []
        violations: list[ContractViolation] = []
        old_set = set(contract.fields)
        new_set = set(new_fields)
        # Removed fields
        for field in sorted(old_set - new_set):
            v = ContractViolation(
                contract_id=contract_id,
                change_type=(BreakingChangeType.FIELD_REMOVED),
                field_name=field,
                old_value=field,
                new_value="",
                is_breaking=True,
            )
            violations.append(v)
            self._violations.append(v)
        if violations:
            contract.status = ContractStatus.BREAKING_CHANGE
            contract.breaking_changes = [v.field_name for v in violations]
        logger.info(
            "api_contract_validator.breaking_detected",
            contract_id=contract_id,
            count=len(violations),
        )
        return violations

    def check_version_compatibility(
        self,
    ) -> list[dict[str, Any]]:
        """Check version compatibility across contracts."""
        by_provider: dict[str, list[APIContract]] = {}
        for c in self._items:
            by_provider.setdefault(c.provider_service, []).append(c)
        issues: list[dict[str, Any]] = []
        for provider, contracts in sorted(by_provider.items()):
            versions = {c.version for c in contracts}
            if len(versions) > 1:
                issues.append(
                    {
                        "provider": provider,
                        "versions": sorted(versions),
                        "contract_count": len(contracts),
                        "status": "version_mismatch",
                    }
                )
                for c in contracts:
                    c.status = ContractStatus.VERSION_MISMATCH
        return issues

    def identify_undocumented_apis(
        self,
    ) -> list[dict[str, Any]]:
        """Identify APIs missing documentation fields."""
        undocumented: list[dict[str, Any]] = []
        for c in self._items:
            missing: list[str] = []
            if not c.endpoint:
                missing.append("endpoint")
            if not c.version:
                missing.append("version")
            if not c.fields:
                missing.append("fields")
            if missing:
                undocumented.append(
                    {
                        "contract_id": c.id,
                        "provider": c.provider_service,
                        "consumer": c.consumer_service,
                        "missing": missing,
                    }
                )
        return undocumented

    def calculate_compliance_rate(self) -> float:
        """Calculate compliance rate as percentage."""
        if not self._items:
            return 100.0
        valid = sum(1 for c in self._items if c.status == ContractStatus.VALID)
        return round(valid / len(self._items) * 100, 2)

    # -- report / stats ----------------------------------------------

    def generate_contract_report(
        self,
    ) -> ContractReport:
        """Generate a comprehensive contract report."""
        by_status: dict[str, int] = {}
        for c in self._items:
            key = c.status.value
            by_status[key] = by_status.get(key, 0) + 1
        by_format: dict[str, int] = {}
        for c in self._items:
            key = c.schema_format.value
            by_format[key] = by_format.get(key, 0) + 1
        by_change_type: dict[str, int] = {}
        for v in self._violations:
            key = v.change_type.value
            by_change_type[key] = by_change_type.get(key, 0) + 1
        breaking = [c.id for c in self._items if c.status == ContractStatus.BREAKING_CHANGE]
        compliance = self.calculate_compliance_rate()
        recs = self._build_recommendations(
            by_status,
            compliance,
        )
        return ContractReport(
            total_contracts=len(self._items),
            total_violations=len(self._violations),
            compliance_pct=compliance,
            by_status=by_status,
            by_format=by_format,
            by_change_type=by_change_type,
            breaking_contracts=breaking,
            recommendations=recs,
        )

    def clear_data(self) -> int:
        """Clear all data. Returns count cleared."""
        count = len(self._items)
        self._items.clear()
        self._violations.clear()
        logger.info(
            "api_contract_validator.cleared",
            count=count,
        )
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        status_dist: dict[str, int] = {}
        for c in self._items:
            key = c.status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_contracts": len(self._items),
            "total_violations": len(self._violations),
            "compliance_target_pct": (self._compliance_target_pct),
            "status_distribution": status_dist,
        }

    # -- internal helpers --------------------------------------------

    def _build_recommendations(
        self,
        by_status: dict[str, int],
        compliance: float,
    ) -> list[str]:
        recs: list[str] = []
        breaking = by_status.get(ContractStatus.BREAKING_CHANGE.value, 0)
        if breaking > 0:
            recs.append(f"{breaking} contract(s) with breaking changes — coordinate migration")
        if compliance < self._compliance_target_pct:
            recs.append(
                f"Compliance {compliance}% below target"
                f" {self._compliance_target_pct}%"
                " — address violations"
            )
        if not recs:
            recs.append("API contract compliance within target range")
        return recs
