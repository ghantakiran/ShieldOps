"""Terraform Drift Detection module.

Detects infrastructure configuration drift by comparing Terraform state files
against live resource state queried through ShieldOps connectors.

Supports AWS, GCP, Azure, and Kubernetes resources with severity classification
for each detected drift item.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

from shieldops.connectors.base import ConnectorRouter

logger = structlog.get_logger()

# Fields that change frequently and should be ignored during drift comparison.
VOLATILE_FIELDS: frozenset[str] = frozenset(
    {
        "updated_at",
        "created_at",
        "etag",
        "self_link",
        "fingerprint",
        "metadata_fingerprint",
        "label_fingerprint",
        "generation",
        "id",
        "arn",
        "unique_id",
        "create_time",
        "update_time",
        "last_modified",
        "last_modified_date",
        "creation_timestamp",
        "timeouts",
    }
)

# Maps Terraform resource type prefixes to ShieldOps connector provider names.
PROVIDER_MAP: dict[str, str] = {
    "aws_": "aws",
    "google_": "gcp",
    "azurerm_": "azure",
    "kubernetes_": "kubernetes",
}

# Resource types where changes are security-critical.
SECURITY_RESOURCE_TYPES: frozenset[str] = frozenset(
    {
        "aws_security_group",
        "aws_security_group_rule",
        "aws_network_acl",
        "aws_iam_policy",
        "aws_iam_role",
        "aws_iam_role_policy",
        "google_compute_firewall",
        "google_compute_network",
        "azurerm_network_security_group",
        "azurerm_network_security_rule",
        "kubernetes_network_policy",
    }
)

# Fields that indicate instance sizing / capacity.
SIZING_FIELDS: frozenset[str] = frozenset(
    {
        "instance_type",
        "machine_type",
        "vm_size",
        "size",
        "sku",
        "replicas",
        "desired_count",
        "min_size",
        "max_size",
        "cpu",
        "memory",
    }
)

# Fields that are purely cosmetic (tags / labels).
TAG_FIELDS: frozenset[str] = frozenset(
    {
        "tags",
        "tags_all",
        "labels",
        "annotations",
        "metadata_labels",
    }
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TerraformResource(BaseModel):
    """A single resource extracted from a Terraform state file."""

    address: str
    type: str
    provider: str
    name: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class DriftItem(BaseModel):
    """A single field-level drift between expected and actual state."""

    resource_address: str
    resource_type: str
    provider: str
    field: str
    expected: Any
    actual: Any
    severity: str  # "critical", "high", "medium", "low"


class DriftReport(BaseModel):
    """Aggregated drift scan report."""

    scan_id: str
    started_at: datetime
    completed_at: datetime
    status: str  # "completed", "partial", "failed"
    total_resources: int
    drifted_resources: int
    drift_items: list[DriftItem] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class DriftScanRequest(BaseModel):
    """Input parameters for a drift scan."""

    tfstate_path: str | None = None
    tfstate_content: dict[str, Any] | None = None
    environment: str = "production"
    providers: list[str] | None = None


# ---------------------------------------------------------------------------
# DriftDetector
# ---------------------------------------------------------------------------


class DriftDetector:
    """Detects drift between Terraform state and live infrastructure.

    Args:
        connector_router: Optional ConnectorRouter for querying live state.
            When ``None``, live-state queries will return empty dicts and
            all resources will be reported as "not reachable".
    """

    def __init__(self, connector_router: ConnectorRouter | None = None) -> None:
        self._router = connector_router
        self._reports: dict[str, DriftReport] = {}

    # ------------------------------------------------------------------
    # State parsing
    # ------------------------------------------------------------------

    def parse_tfstate(self, state: dict[str, Any]) -> list[TerraformResource]:
        """Parse a Terraform v4 state file into a flat resource list.

        Args:
            state: Parsed JSON content of a ``terraform.tfstate`` file.

        Returns:
            List of ``TerraformResource`` models.
        """
        resources: list[TerraformResource] = []
        version = state.get("version", 4)
        if version < 4:
            logger.warning("tfstate_unsupported_version", version=version)
            return resources

        for resource_block in state.get("resources", []):
            res_type: str = resource_block.get("type", "")
            res_name: str = resource_block.get("name", "")
            provider_raw: str = resource_block.get("provider", "")
            module: str = resource_block.get("module", "")

            provider = self._normalize_provider(provider_raw, res_type)

            for instance in resource_block.get("instances", []):
                attrs = instance.get("attributes", {}) or {}
                index_key = instance.get("index_key")

                address = f"{module}.{res_type}.{res_name}" if module else f"{res_type}.{res_name}"
                if index_key is not None:
                    address = f"{address}[{index_key}]"

                resources.append(
                    TerraformResource(
                        address=address,
                        type=res_type,
                        provider=provider,
                        name=res_name,
                        attributes=attrs,
                    )
                )

        logger.info("tfstate_parsed", resource_count=len(resources))
        return resources

    # ------------------------------------------------------------------
    # Live-state queries
    # ------------------------------------------------------------------

    async def get_live_state(self, resource: TerraformResource) -> dict[str, Any]:
        """Query the live state of a resource via the connector router.

        Maps Terraform resource types to the appropriate connector and calls
        ``get_health`` as a proxy for live attribute retrieval.

        Returns:
            A dict of live attributes, or an empty dict if the resource
            could not be reached.
        """
        if self._router is None:
            logger.debug("drift_no_connector_router", resource=resource.address)
            return {}

        provider = resource.provider
        try:
            connector = self._router.get(provider)
        except ValueError:
            logger.warning(
                "drift_connector_not_found",
                provider=provider,
                resource=resource.address,
            )
            return {}

        resource_id = self._extract_resource_id(resource)

        try:
            health = await connector.get_health(resource_id)
            # Build a minimal live-state dict from health + known attributes.
            live: dict[str, Any] = {
                "status": health.status,
                "healthy": health.healthy,
            }
            if health.metrics:
                live.update(health.metrics)
            return live
        except Exception as exc:
            logger.error(
                "drift_live_state_error",
                resource=resource.address,
                error=str(exc),
            )
            return {}

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def compare_resource(
        self,
        expected: TerraformResource,
        actual: dict[str, Any],
    ) -> list[DriftItem]:
        """Compare expected (tfstate) attributes against live attributes.

        Volatile fields are automatically skipped. Only fields present in
        *both* expected and actual are compared (missing fields in actual
        are considered unreachable, not drifted).

        Args:
            expected: The Terraform resource with expected attributes.
            actual: Live attribute dict.

        Returns:
            A list of ``DriftItem`` for every field that differs.
        """
        items: list[DriftItem] = []

        if not actual:
            return items

        for field, expected_value in expected.attributes.items():
            if field in VOLATILE_FIELDS:
                continue
            if field not in actual:
                continue

            actual_value = actual[field]

            if not self._values_equal(expected_value, actual_value):
                items.append(
                    DriftItem(
                        resource_address=expected.address,
                        resource_type=expected.type,
                        provider=expected.provider,
                        field=field,
                        expected=expected_value,
                        actual=actual_value,
                        severity=self.classify_severity(expected.type, field),
                    )
                )

        return items

    # ------------------------------------------------------------------
    # Severity classification
    # ------------------------------------------------------------------

    def classify_severity(self, resource_type: str, field: str) -> str:
        """Classify the severity of a drift item.

        Rules (evaluated in order):
            1. Security group / firewall / IAM changes -> critical
            2. Instance type / sizing changes -> high
            3. Tag / label changes -> low
            4. Everything else -> medium
        """
        if resource_type in SECURITY_RESOURCE_TYPES:
            return "critical"
        if field in SIZING_FIELDS:
            return "high"
        if field in TAG_FIELDS:
            return "low"
        return "medium"

    # ------------------------------------------------------------------
    # Full scan
    # ------------------------------------------------------------------

    async def scan(self, request: DriftScanRequest) -> DriftReport:
        """Execute a full drift scan.

        Workflow: parse tfstate -> query live state per resource ->
        compare -> build report.
        """
        scan_id = str(uuid4())
        started_at = datetime.now(UTC)

        logger.info(
            "drift_scan_started",
            scan_id=scan_id,
            environment=request.environment,
        )

        # Resolve state content
        state = request.tfstate_content
        if state is None and request.tfstate_path:
            state = self._read_state_file(request.tfstate_path)
        if state is None:
            report = DriftReport(
                scan_id=scan_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                status="failed",
                total_resources=0,
                drifted_resources=0,
                summary={"error": "No tfstate content or path provided"},
            )
            self._reports[scan_id] = report
            return report

        # Parse
        resources = self.parse_tfstate(state)

        # Filter by requested providers
        if request.providers:
            resources = [r for r in resources if r.provider in request.providers]

        # Compare each resource
        all_drift_items: list[DriftItem] = []
        drifted_addresses: set[str] = set()
        not_reachable: list[str] = []

        for resource in resources:
            live = await self.get_live_state(resource)
            if not live:
                not_reachable.append(resource.address)
                continue
            items = self.compare_resource(resource, live)
            if items:
                drifted_addresses.add(resource.address)
                all_drift_items.extend(items)

        # Build summary
        severity_counts: dict[str, int] = {}
        for item in all_drift_items:
            severity_counts[item.severity] = severity_counts.get(item.severity, 0) + 1

        providers = sorted({r.provider for r in resources})

        status = "completed"
        if not_reachable and resources:
            status = "partial"

        report = DriftReport(
            scan_id=scan_id,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            status=status,
            total_resources=len(resources),
            drifted_resources=len(drifted_addresses),
            drift_items=all_drift_items,
            providers=providers,
            summary={
                "severity_counts": severity_counts,
                "not_reachable": len(not_reachable),
                "environment": request.environment,
            },
        )

        self._reports[scan_id] = report

        logger.info(
            "drift_scan_completed",
            scan_id=scan_id,
            total_resources=len(resources),
            drifted=len(drifted_addresses),
            drift_items=len(all_drift_items),
        )

        return report

    async def scan_from_file(
        self,
        file_path: str,
        environment: str = "production",
    ) -> DriftReport:
        """Convenience wrapper: run a scan from a tfstate file path."""
        return await self.scan(DriftScanRequest(tfstate_path=file_path, environment=environment))

    # ------------------------------------------------------------------
    # Report retrieval
    # ------------------------------------------------------------------

    def get_report(self, scan_id: str) -> DriftReport | None:
        """Return a stored report by scan ID."""
        return self._reports.get(scan_id)

    def get_latest_report(self) -> DriftReport | None:
        """Return the most recently completed report."""
        if not self._reports:
            return None
        return list(self._reports.values())[-1]

    def list_reports(self) -> list[dict[str, Any]]:
        """Return summary dicts for all stored reports, newest first."""
        return [
            {
                "scan_id": r.scan_id,
                "started_at": r.started_at.isoformat(),
                "completed_at": r.completed_at.isoformat(),
                "status": r.status,
                "total_resources": r.total_resources,
                "drifted_resources": r.drifted_resources,
                "drift_item_count": len(r.drift_items),
                "providers": r.providers,
            }
            for r in reversed(list(self._reports.values()))
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_provider(provider_raw: str, resource_type: str) -> str:
        """Derive a short provider name from the tfstate provider string or resource type."""
        lower = provider_raw.lower()
        if "aws" in lower:
            return "aws"
        if "google" in lower:
            return "gcp"
        if "azurerm" in lower or "azure" in lower:
            return "azure"
        if "kubernetes" in lower:
            return "kubernetes"

        # Fallback: infer from resource type prefix
        for prefix, provider in PROVIDER_MAP.items():
            if resource_type.startswith(prefix):
                return provider

        return "unknown"

    @staticmethod
    def _extract_resource_id(resource: TerraformResource) -> str:
        """Extract the cloud resource ID from Terraform attributes."""
        attrs = resource.attributes
        # Try common ID fields in priority order
        for key in ("id", "self_link", "arn", "name"):
            val = attrs.get(key)
            if val:
                return str(val)
        return resource.address

    @staticmethod
    def _values_equal(expected: Any, actual: Any) -> bool:
        """Deep-compare two values, tolerating type coercion (str ↔ int/float)."""
        if expected == actual:
            return True

        # Coerce comparable numerics
        try:
            if isinstance(expected, (int, float)) and isinstance(actual, str):
                return expected == type(expected)(actual)
            if isinstance(actual, (int, float)) and isinstance(expected, str):
                return actual == type(actual)(expected)
        except (ValueError, TypeError):
            pass

        # Nested dicts
        if isinstance(expected, dict) and isinstance(actual, dict):
            if set(expected.keys()) != set(actual.keys()):
                return False
            return all(DriftDetector._values_equal(expected[k], actual[k]) for k in expected)

        # Lists (order-sensitive)
        if isinstance(expected, list) and isinstance(actual, list):
            if len(expected) != len(actual):
                return False
            return all(
                DriftDetector._values_equal(e, a) for e, a in zip(expected, actual, strict=False)
            )

        return False

    @staticmethod
    def _read_state_file(file_path: str) -> dict[str, Any] | None:
        """Read and parse a tfstate JSON file from disk."""
        try:
            path = Path(file_path)
            content = path.read_text(encoding="utf-8")
            result: dict[str, Any] = json.loads(content)
            return result
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("tfstate_read_error", path=file_path, error=str(exc))
            return None
