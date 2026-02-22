"""Comprehensive tests for Terraform Drift Detection.

Covers:
- TerraformResource / DriftItem / DriftReport model validation
- parse_tfstate: v4 state parsing, empty state, missing attributes, multi-instance
- compare_resource: field drift, no-drift, volatile field skipping, nested attrs
- classify_severity: security group -> critical, instance type -> high,
  tags -> low, unknown -> medium
- Full scan: drifted resources, no drift, partial state, multi-provider
- Report retrieval and listing
- API routes: POST /scan, GET /report, GET /reports, GET /report/{id}, 503
- Scheduler job: periodic_drift_scan
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.agents.security.drift import (
    DriftDetector,
    DriftItem,
    DriftReport,
    DriftScanRequest,
    TerraformResource,
)
from shieldops.api.routes import drift as drift_routes
from shieldops.api.routes.drift import router as drift_router

# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_drift_detector() -> Any:
    """Reset module-level detector between tests."""
    drift_routes._detector = None
    yield
    drift_routes._detector = None


def _make_v4_state(
    resources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a minimal Terraform v4 state dict."""
    return {
        "version": 4,
        "terraform_version": "1.7.0",
        "serial": 1,
        "lineage": "abc-123",
        "resources": resources or [],
    }


def _make_resource_block(
    res_type: str = "aws_instance",
    name: str = "web",
    provider: str = 'provider["registry.terraform.io/hashicorp/aws"]',
    attributes: dict[str, Any] | None = None,
    module: str = "",
    index_key: int | str | None = None,
) -> dict[str, Any]:
    """Build a single resource block for a tfstate."""
    instance: dict[str, Any] = {
        "schema_version": 0,
        "attributes": attributes or {"id": "i-abc123", "instance_type": "t3.micro"},
    }
    if index_key is not None:
        instance["index_key"] = index_key
    block: dict[str, Any] = {
        "type": res_type,
        "name": name,
        "provider": provider,
        "instances": [instance],
    }
    if module:
        block["module"] = module
    return block


def _make_detector(
    connector_router: Any = None,
) -> DriftDetector:
    """Build a DriftDetector with optional mock router."""
    return DriftDetector(connector_router=connector_router)


# ===========================================================================
# TerraformResource model
# ===========================================================================


class TestTerraformResourceModel:
    def test_basic_construction(self) -> None:
        r = TerraformResource(
            address="aws_instance.web",
            type="aws_instance",
            provider="aws",
            name="web",
            attributes={"id": "i-123", "instance_type": "t3.micro"},
        )
        assert r.address == "aws_instance.web"
        assert r.type == "aws_instance"
        assert r.provider == "aws"
        assert r.attributes["instance_type"] == "t3.micro"

    def test_default_attributes(self) -> None:
        r = TerraformResource(
            address="aws_instance.x",
            type="aws_instance",
            provider="aws",
            name="x",
        )
        assert r.attributes == {}


# ===========================================================================
# DriftItem model
# ===========================================================================


class TestDriftItemModel:
    def test_construction(self) -> None:
        item = DriftItem(
            resource_address="aws_instance.web",
            resource_type="aws_instance",
            provider="aws",
            field="instance_type",
            expected="t3.micro",
            actual="t3.large",
            severity="high",
        )
        assert item.severity == "high"
        assert item.expected == "t3.micro"
        assert item.actual == "t3.large"


# ===========================================================================
# DriftReport model
# ===========================================================================


class TestDriftReportModel:
    def test_construction_and_defaults(self) -> None:
        now = datetime.now(UTC)
        report = DriftReport(
            scan_id="test-scan",
            started_at=now,
            completed_at=now,
            status="completed",
            total_resources=5,
            drifted_resources=2,
        )
        assert report.scan_id == "test-scan"
        assert report.drift_items == []
        assert report.providers == []
        assert report.summary == {}

    def test_model_dump_serializes_correctly(self) -> None:
        now = datetime.now(UTC)
        report = DriftReport(
            scan_id="test-dump",
            started_at=now,
            completed_at=now,
            status="completed",
            total_resources=3,
            drifted_resources=1,
            drift_items=[
                DriftItem(
                    resource_address="aws_instance.web",
                    resource_type="aws_instance",
                    provider="aws",
                    field="instance_type",
                    expected="t3.micro",
                    actual="t3.large",
                    severity="high",
                ),
            ],
            providers=["aws"],
            summary={"severity_counts": {"high": 1}},
        )
        data = report.model_dump(mode="json")
        assert data["scan_id"] == "test-dump"
        assert len(data["drift_items"]) == 1
        assert data["providers"] == ["aws"]


# ===========================================================================
# parse_tfstate
# ===========================================================================


class TestParseTfstate:
    """Tests for parsing Terraform v4 state files."""

    def test_parse_valid_v4_state(self) -> None:
        state = _make_v4_state(
            [
                _make_resource_block(
                    res_type="aws_instance",
                    name="web",
                    attributes={"id": "i-abc", "instance_type": "t3.micro"},
                ),
            ]
        )
        detector = _make_detector()
        resources = detector.parse_tfstate(state)
        assert len(resources) == 1
        assert resources[0].address == "aws_instance.web"
        assert resources[0].type == "aws_instance"
        assert resources[0].provider == "aws"
        assert resources[0].attributes["instance_type"] == "t3.micro"

    def test_parse_extracts_multiple_resources(self) -> None:
        state = _make_v4_state(
            [
                _make_resource_block("aws_instance", "web"),
                _make_resource_block("aws_security_group", "sg"),
            ]
        )
        detector = _make_detector()
        resources = detector.parse_tfstate(state)
        assert len(resources) == 2
        types = {r.type for r in resources}
        assert types == {"aws_instance", "aws_security_group"}

    def test_parse_empty_state(self) -> None:
        state = _make_v4_state([])
        detector = _make_detector()
        resources = detector.parse_tfstate(state)
        assert resources == []

    def test_parse_missing_attributes(self) -> None:
        """Resources with no attributes should still parse."""
        state = _make_v4_state(
            [
                {
                    "type": "aws_instance",
                    "name": "minimal",
                    "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
                    "instances": [{"schema_version": 0}],
                },
            ]
        )
        detector = _make_detector()
        resources = detector.parse_tfstate(state)
        assert len(resources) == 1
        assert resources[0].attributes == {}

    def test_parse_with_module_prefix(self) -> None:
        state = _make_v4_state(
            [
                _make_resource_block("aws_instance", "web", module="module.vpc"),
            ]
        )
        detector = _make_detector()
        resources = detector.parse_tfstate(state)
        assert resources[0].address == "module.vpc.aws_instance.web"

    def test_parse_with_index_key(self) -> None:
        state = _make_v4_state(
            [
                _make_resource_block("aws_instance", "web", index_key=0),
            ]
        )
        detector = _make_detector()
        resources = detector.parse_tfstate(state)
        assert resources[0].address == "aws_instance.web[0]"

    def test_parse_gcp_provider(self) -> None:
        state = _make_v4_state(
            [
                _make_resource_block(
                    res_type="google_compute_instance",
                    name="vm",
                    provider='provider["registry.terraform.io/hashicorp/google"]',
                    attributes={"id": "vm-1", "machine_type": "e2-medium"},
                ),
            ]
        )
        detector = _make_detector()
        resources = detector.parse_tfstate(state)
        assert resources[0].provider == "gcp"

    def test_parse_azure_provider(self) -> None:
        state = _make_v4_state(
            [
                _make_resource_block(
                    res_type="azurerm_virtual_machine",
                    name="vm1",
                    provider='provider["registry.terraform.io/hashicorp/azurerm"]',
                    attributes={"id": "/subscriptions/xxx", "vm_size": "Standard_B2s"},
                ),
            ]
        )
        detector = _make_detector()
        resources = detector.parse_tfstate(state)
        assert resources[0].provider == "azure"

    def test_parse_kubernetes_provider(self) -> None:
        state = _make_v4_state(
            [
                _make_resource_block(
                    res_type="kubernetes_deployment",
                    name="app",
                    provider='provider["registry.terraform.io/hashicorp/kubernetes"]',
                    attributes={"id": "default/app"},
                ),
            ]
        )
        detector = _make_detector()
        resources = detector.parse_tfstate(state)
        assert resources[0].provider == "kubernetes"

    def test_parse_unsupported_version(self) -> None:
        state = {"version": 3, "resources": []}
        detector = _make_detector()
        resources = detector.parse_tfstate(state)
        assert resources == []


# ===========================================================================
# compare_resource
# ===========================================================================


class TestCompareResource:
    """Tests for attribute comparison."""

    def test_detect_field_drift(self) -> None:
        expected = TerraformResource(
            address="aws_instance.web",
            type="aws_instance",
            provider="aws",
            name="web",
            attributes={"instance_type": "t3.micro", "status": "running"},
        )
        actual = {"instance_type": "t3.large", "status": "running"}
        detector = _make_detector()
        items = detector.compare_resource(expected, actual)
        assert len(items) == 1
        assert items[0].field == "instance_type"
        assert items[0].expected == "t3.micro"
        assert items[0].actual == "t3.large"

    def test_no_drift_when_matching(self) -> None:
        expected = TerraformResource(
            address="aws_instance.web",
            type="aws_instance",
            provider="aws",
            name="web",
            attributes={"instance_type": "t3.micro", "status": "running"},
        )
        actual = {"instance_type": "t3.micro", "status": "running"}
        detector = _make_detector()
        items = detector.compare_resource(expected, actual)
        assert items == []

    def test_skip_volatile_fields(self) -> None:
        expected = TerraformResource(
            address="aws_instance.web",
            type="aws_instance",
            provider="aws",
            name="web",
            attributes={
                "instance_type": "t3.micro",
                "updated_at": "2024-01-01T00:00:00Z",
                "etag": "abc123",
            },
        )
        actual = {
            "instance_type": "t3.micro",
            "updated_at": "2025-06-15T12:00:00Z",
            "etag": "xyz789",
        }
        detector = _make_detector()
        items = detector.compare_resource(expected, actual)
        assert items == []

    def test_nested_dict_comparison(self) -> None:
        expected = TerraformResource(
            address="aws_instance.web",
            type="aws_instance",
            provider="aws",
            name="web",
            attributes={
                "config": {"cpu": 2, "memory": 4096},
            },
        )
        actual = {"config": {"cpu": 4, "memory": 4096}}
        detector = _make_detector()
        items = detector.compare_resource(expected, actual)
        assert len(items) == 1
        assert items[0].field == "config"

    def test_empty_actual_returns_no_drift(self) -> None:
        expected = TerraformResource(
            address="aws_instance.web",
            type="aws_instance",
            provider="aws",
            name="web",
            attributes={"instance_type": "t3.micro"},
        )
        detector = _make_detector()
        items = detector.compare_resource(expected, {})
        assert items == []

    def test_fields_only_in_expected_are_skipped(self) -> None:
        """Fields present in expected but absent in actual should not drift."""
        expected = TerraformResource(
            address="aws_instance.web",
            type="aws_instance",
            provider="aws",
            name="web",
            attributes={"instance_type": "t3.micro", "extra_field": "value"},
        )
        actual = {"instance_type": "t3.micro"}
        detector = _make_detector()
        items = detector.compare_resource(expected, actual)
        assert items == []

    def test_numeric_string_coercion(self) -> None:
        """Integer 2 should equal string '2' via coercion."""
        expected = TerraformResource(
            address="aws_instance.web",
            type="aws_instance",
            provider="aws",
            name="web",
            attributes={"replicas": 2},
        )
        actual = {"replicas": "2"}
        detector = _make_detector()
        items = detector.compare_resource(expected, actual)
        assert items == []


# ===========================================================================
# classify_severity
# ===========================================================================


class TestClassifySeverity:
    """Tests for drift severity classification."""

    def test_security_group_is_critical(self) -> None:
        detector = _make_detector()
        assert detector.classify_severity("aws_security_group", "ingress") == "critical"

    def test_firewall_is_critical(self) -> None:
        detector = _make_detector()
        assert detector.classify_severity("google_compute_firewall", "allowed") == "critical"

    def test_iam_role_is_critical(self) -> None:
        detector = _make_detector()
        assert detector.classify_severity("aws_iam_role", "assume_role_policy") == "critical"

    def test_instance_type_is_high(self) -> None:
        detector = _make_detector()
        assert detector.classify_severity("aws_instance", "instance_type") == "high"

    def test_vm_size_is_high(self) -> None:
        detector = _make_detector()
        assert detector.classify_severity("azurerm_virtual_machine", "vm_size") == "high"

    def test_tags_is_low(self) -> None:
        detector = _make_detector()
        assert detector.classify_severity("aws_instance", "tags") == "low"

    def test_labels_is_low(self) -> None:
        detector = _make_detector()
        assert detector.classify_severity("google_compute_instance", "labels") == "low"

    def test_unknown_field_is_medium(self) -> None:
        detector = _make_detector()
        assert detector.classify_severity("aws_instance", "availability_zone") == "medium"


# ===========================================================================
# Full drift scan
# ===========================================================================


class TestDriftScan:
    """Tests for the end-to-end scan() method."""

    @pytest.mark.asyncio
    async def test_scan_with_drifted_resources(self) -> None:
        """Scan detects drift when live state differs from tfstate."""
        state = _make_v4_state(
            [
                _make_resource_block(
                    "aws_instance",
                    "web",
                    attributes={
                        "id": "i-abc",
                        "instance_type": "t3.micro",
                        "status": "running",
                    },
                ),
            ]
        )

        # Mock router returns different instance_type
        mock_connector = AsyncMock()
        mock_connector.get_health.return_value = MagicMock(
            status="running",
            healthy=True,
            metrics={"instance_type": "t3.large"},
        )
        mock_router = MagicMock()
        mock_router.get.return_value = mock_connector

        detector = _make_detector(connector_router=mock_router)
        request = DriftScanRequest(tfstate_content=state, environment="production")
        report = await detector.scan(request)

        assert report.total_resources == 1
        assert report.drifted_resources == 1
        assert len(report.drift_items) == 1
        assert report.drift_items[0].field == "instance_type"
        assert report.drift_items[0].expected == "t3.micro"
        assert report.drift_items[0].actual == "t3.large"
        assert report.status == "completed"

    @pytest.mark.asyncio
    async def test_scan_with_no_drift(self) -> None:
        """Scan reports zero drift when live matches expected."""
        state = _make_v4_state(
            [
                _make_resource_block(
                    "aws_instance",
                    "web",
                    attributes={"id": "i-abc", "status": "running"},
                ),
            ]
        )

        mock_connector = AsyncMock()
        mock_connector.get_health.return_value = MagicMock(
            status="running",
            healthy=True,
            metrics={},
        )
        mock_router = MagicMock()
        mock_router.get.return_value = mock_connector

        detector = _make_detector(connector_router=mock_router)
        request = DriftScanRequest(tfstate_content=state)
        report = await detector.scan(request)

        assert report.drifted_resources == 0
        assert report.drift_items == []

    @pytest.mark.asyncio
    async def test_scan_partial_state_unreachable(self) -> None:
        """Resources that cannot be reached produce a partial report."""
        state = _make_v4_state(
            [
                _make_resource_block("aws_instance", "reachable", attributes={"id": "i-1"}),
                _make_resource_block("aws_instance", "unreachable", attributes={"id": "i-2"}),
            ]
        )

        call_count = 0

        async def mock_get_health(resource_id: str) -> Any:
            nonlocal call_count
            call_count += 1
            if resource_id == "i-2":
                raise ConnectionError("Host unreachable")
            return MagicMock(status="running", healthy=True, metrics={})

        mock_connector = AsyncMock()
        mock_connector.get_health = mock_get_health
        mock_router = MagicMock()
        mock_router.get.return_value = mock_connector

        detector = _make_detector(connector_router=mock_router)
        request = DriftScanRequest(tfstate_content=state)
        report = await detector.scan(request)

        assert report.total_resources == 2
        assert report.status == "partial"
        assert report.summary["not_reachable"] == 1

    @pytest.mark.asyncio
    async def test_scan_multi_provider(self) -> None:
        """Scan covers resources across multiple providers."""
        state = _make_v4_state(
            [
                _make_resource_block(
                    "aws_instance",
                    "web",
                    provider='provider["registry.terraform.io/hashicorp/aws"]',
                    attributes={"id": "i-aws", "status": "running"},
                ),
                _make_resource_block(
                    "google_compute_instance",
                    "api",
                    provider='provider["registry.terraform.io/hashicorp/google"]',
                    attributes={"id": "gcp-vm-1", "status": "RUNNING"},
                ),
            ]
        )

        mock_connector = AsyncMock()
        mock_connector.get_health.return_value = MagicMock(
            status="running",
            healthy=True,
            metrics={},
        )
        mock_router = MagicMock()
        mock_router.get.return_value = mock_connector

        detector = _make_detector(connector_router=mock_router)
        request = DriftScanRequest(tfstate_content=state)
        report = await detector.scan(request)

        assert report.total_resources == 2
        assert sorted(report.providers) == ["aws", "gcp"]

    @pytest.mark.asyncio
    async def test_scan_no_state_fails(self) -> None:
        """Scan with no tfstate content or path produces a failed report."""
        detector = _make_detector()
        request = DriftScanRequest()
        report = await detector.scan(request)

        assert report.status == "failed"
        assert report.total_resources == 0
        assert "error" in report.summary

    @pytest.mark.asyncio
    async def test_scan_provider_filter(self) -> None:
        """Provider filter limits scan to specific providers."""
        state = _make_v4_state(
            [
                _make_resource_block("aws_instance", "web", attributes={"id": "i-1"}),
                _make_resource_block(
                    "google_compute_instance",
                    "api",
                    provider='provider["registry.terraform.io/hashicorp/google"]',
                    attributes={"id": "gcp-1"},
                ),
            ]
        )

        mock_connector = AsyncMock()
        mock_connector.get_health.return_value = MagicMock(
            status="running",
            healthy=True,
            metrics={},
        )
        mock_router = MagicMock()
        mock_router.get.return_value = mock_connector

        detector = _make_detector(connector_router=mock_router)
        request = DriftScanRequest(
            tfstate_content=state,
            providers=["aws"],
        )
        report = await detector.scan(request)

        assert report.total_resources == 1
        assert report.providers == ["aws"]

    @pytest.mark.asyncio
    async def test_scan_no_router_reports_all_unreachable(self) -> None:
        """Without a connector router all resources are unreachable."""
        state = _make_v4_state(
            [
                _make_resource_block("aws_instance", "web", attributes={"id": "i-1"}),
            ]
        )
        detector = _make_detector(connector_router=None)
        request = DriftScanRequest(tfstate_content=state)
        report = await detector.scan(request)

        assert report.total_resources == 1
        assert report.drifted_resources == 0
        assert report.summary["not_reachable"] == 1


# ===========================================================================
# Report retrieval
# ===========================================================================


class TestDriftReportRetrieval:
    """Tests for get_report, get_latest_report, and list_reports."""

    @pytest.mark.asyncio
    async def test_get_report_by_id(self) -> None:
        detector = _make_detector()
        state = _make_v4_state([])
        report = await detector.scan(DriftScanRequest(tfstate_content=state))

        fetched = detector.get_report(report.scan_id)
        assert fetched is not None
        assert fetched.scan_id == report.scan_id

    @pytest.mark.asyncio
    async def test_get_report_missing(self) -> None:
        detector = _make_detector()
        assert detector.get_report("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_latest_report(self) -> None:
        detector = _make_detector()
        state = _make_v4_state([])
        await detector.scan(DriftScanRequest(tfstate_content=state))
        r2 = await detector.scan(DriftScanRequest(tfstate_content=state))

        latest = detector.get_latest_report()
        assert latest is not None
        assert latest.scan_id == r2.scan_id

    def test_get_latest_report_empty(self) -> None:
        detector = _make_detector()
        assert detector.get_latest_report() is None

    @pytest.mark.asyncio
    async def test_list_reports(self) -> None:
        detector = _make_detector()
        state = _make_v4_state([])
        r1 = await detector.scan(DriftScanRequest(tfstate_content=state))
        r2 = await detector.scan(DriftScanRequest(tfstate_content=state))

        reports = detector.list_reports()
        assert len(reports) == 2
        # Newest first
        assert reports[0]["scan_id"] == r2.scan_id
        assert reports[1]["scan_id"] == r1.scan_id

    @pytest.mark.asyncio
    async def test_list_reports_summary_fields(self) -> None:
        detector = _make_detector()
        state = _make_v4_state(
            [
                _make_resource_block("aws_instance", "web", attributes={"id": "i-1"}),
            ]
        )
        await detector.scan(DriftScanRequest(tfstate_content=state))

        reports = detector.list_reports()
        entry = reports[0]
        assert "scan_id" in entry
        assert "started_at" in entry
        assert "completed_at" in entry
        assert "status" in entry
        assert "total_resources" in entry
        assert "drifted_resources" in entry
        assert "drift_item_count" in entry
        assert "providers" in entry


# ===========================================================================
# API route tests
# ===========================================================================


class TestDriftAPIRoutes:
    """Tests for the drift detection FastAPI routes."""

    @pytest.fixture
    def app(self) -> FastAPI:
        test_app = FastAPI()
        test_app.include_router(drift_router)
        return test_app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        return TestClient(app)

    def test_post_scan_returns_report(self, client: TestClient) -> None:
        detector = DriftDetector()
        drift_routes.set_detector(detector)

        state = _make_v4_state([])
        resp = client.post("/drift/scan", json={"tfstate_content": state})
        assert resp.status_code == 200
        data = resp.json()
        assert "scan_id" in data
        assert data["status"] in ("completed", "partial", "failed")

    def test_post_scan_with_resources(self, client: TestClient) -> None:
        detector = DriftDetector()
        drift_routes.set_detector(detector)

        state = _make_v4_state(
            [
                _make_resource_block("aws_instance", "web", attributes={"id": "i-1"}),
            ]
        )
        resp = client.post("/drift/scan", json={"tfstate_content": state})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_resources"] == 1

    def test_get_report_returns_latest(self, client: TestClient) -> None:
        detector = DriftDetector()
        drift_routes.set_detector(detector)

        state = _make_v4_state([])
        # Create a scan first
        client.post("/drift/scan", json={"tfstate_content": state})

        resp = client.get("/drift/report")
        assert resp.status_code == 200
        data = resp.json()
        assert "scan_id" in data

    def test_get_report_404_when_empty(self, client: TestClient) -> None:
        detector = DriftDetector()
        drift_routes.set_detector(detector)

        resp = client.get("/drift/report")
        assert resp.status_code == 404

    def test_get_reports_list(self, client: TestClient) -> None:
        detector = DriftDetector()
        drift_routes.set_detector(detector)

        state = _make_v4_state([])
        client.post("/drift/scan", json={"tfstate_content": state})
        client.post("/drift/scan", json={"tfstate_content": state})

        resp = client.get("/drift/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["reports"]) == 2

    def test_get_report_by_id(self, client: TestClient) -> None:
        detector = DriftDetector()
        drift_routes.set_detector(detector)

        state = _make_v4_state([])
        scan_resp = client.post("/drift/scan", json={"tfstate_content": state})
        scan_id = scan_resp.json()["scan_id"]

        resp = client.get(f"/drift/report/{scan_id}")
        assert resp.status_code == 200
        assert resp.json()["scan_id"] == scan_id

    def test_get_report_by_id_not_found(self, client: TestClient) -> None:
        detector = DriftDetector()
        drift_routes.set_detector(detector)

        resp = client.get("/drift/report/does-not-exist")
        assert resp.status_code == 404

    def test_503_when_no_detector(self, client: TestClient) -> None:
        """All endpoints should return 503 when no detector is wired."""
        resp = client.post("/drift/scan", json={"tfstate_content": {}})
        assert resp.status_code == 503

        resp = client.get("/drift/report")
        assert resp.status_code == 503

        resp = client.get("/drift/reports")
        assert resp.status_code == 503

        resp = client.get("/drift/report/some-id")
        assert resp.status_code == 503


# ===========================================================================
# Scheduler job
# ===========================================================================


class TestPeriodicDriftScanJob:
    """Tests for the periodic_drift_scan scheduler job."""

    @pytest.mark.asyncio
    async def test_calls_detector_scan(self) -> None:
        from shieldops.scheduler.jobs import periodic_drift_scan

        mock_detector = AsyncMock()
        mock_detector.scan.return_value = MagicMock(
            scan_id="drift-job-1",
            total_resources=5,
            drifted_resources=1,
            drift_items=[MagicMock()],
        )

        await periodic_drift_scan(
            drift_detector=mock_detector,
            environment="staging",
            tfstate_path="/opt/infra/state/terraform.tfstate",
        )

        mock_detector.scan.assert_awaited_once()
        call_args = mock_detector.scan.call_args
        request = call_args[0][0]
        assert request.environment == "staging"
        assert request.tfstate_path == "/opt/infra/state/terraform.tfstate"

    @pytest.mark.asyncio
    async def test_skips_when_no_detector(self) -> None:
        from shieldops.scheduler.jobs import periodic_drift_scan

        # Should not raise
        await periodic_drift_scan(drift_detector=None)

    @pytest.mark.asyncio
    async def test_skips_with_default_args(self) -> None:
        from shieldops.scheduler.jobs import periodic_drift_scan

        # Called with no arguments at all
        await periodic_drift_scan()
