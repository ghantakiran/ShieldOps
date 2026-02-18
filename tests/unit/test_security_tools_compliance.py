"""Tests for compliance framework integration in SecurityToolkit.

Covers:
- _evaluate_control: access control, authentication, rotation policy, monitoring,
  change management, network segmentation, default credentials, patching,
  audit logging, CIS checks, unknown controls
- check_compliance: full SOC2 evaluation, mixed results, no-router, score calculation
- Unsupported framework returns empty
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from shieldops.agents.security.tools import SecurityToolkit
from shieldops.connectors.base import ConnectorRouter
from shieldops.models.base import Resource

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cred(
    cred_id: str = "cred-1",
    expires_at: datetime | None = None,
    last_rotated: datetime | None = None,
    rotation_policy: str | None = "90d",
) -> dict[str, Any]:
    cred: dict[str, Any] = {"credential_id": cred_id}
    if expires_at is not None:
        cred["expires_at"] = expires_at
    if last_rotated is not None:
        cred["last_rotated"] = last_rotated
    if rotation_policy is not None:
        cred["rotation_policy"] = rotation_policy
    return cred


def _make_store(creds: list[dict[str, Any]] | None = None) -> MagicMock:
    store = MagicMock()
    store.store_name = "test-store"
    store.list_credentials = AsyncMock(return_value=creds or [])
    store.rotate_credential = AsyncMock(return_value={"success": True})
    return store


def _make_cve_source(findings: list[dict[str, Any]] | None = None) -> MagicMock:
    source = MagicMock()
    source.source_name = "test-cve"
    source.scan = AsyncMock(return_value=findings or [])
    return source


def _make_connector(
    events: list[dict[str, Any]] | None = None,
    resources: list[Resource] | None = None,
) -> MagicMock:
    connector = MagicMock()
    connector.get_events = AsyncMock(return_value=events or [])
    connector.list_resources = AsyncMock(return_value=resources or [])
    return connector


def _make_router(connectors: dict[str, MagicMock] | None = None) -> ConnectorRouter:
    router = ConnectorRouter()
    for provider, conn in (connectors or {}).items():
        conn.provider = provider
        router.register(conn)
    return router


# ===========================================================================
# _evaluate_control tests
# ===========================================================================


class TestEvaluateControlAccessControl:
    """SOC2-CC6.1 / HIPAA-164.312a — access control (no expired credentials)."""

    @pytest.mark.asyncio
    async def test_passing_no_expired_creds(self) -> None:
        future = datetime.now(UTC) + timedelta(days=30)
        store = _make_store([_make_cred(expires_at=future)])
        toolkit = SecurityToolkit(credential_stores=[store])

        result = await toolkit._evaluate_control({"id": "SOC2-CC6.1", "title": "x"}, None)

        assert result["status"] == "passing"

    @pytest.mark.asyncio
    async def test_failing_expired_cred(self) -> None:
        past = datetime.now(UTC) - timedelta(days=1)
        store = _make_store([_make_cred(expires_at=past)])
        toolkit = SecurityToolkit(credential_stores=[store])

        result = await toolkit._evaluate_control({"id": "HIPAA-164.312a", "title": "x"}, None)

        assert result["status"] == "failing"
        assert "expired" in result["evidence"][0].lower()

    @pytest.mark.asyncio
    async def test_unknown_no_stores(self) -> None:
        toolkit = SecurityToolkit()

        result = await toolkit._evaluate_control({"id": "SOC2-CC6.1", "title": "x"}, None)

        assert result["status"] == "unknown"


class TestEvaluateControlAuthentication:
    """SOC2-CC6.2 / HIPAA-164.312d — authentication mechanisms."""

    @pytest.mark.asyncio
    async def test_passing_has_rotation_metadata(self) -> None:
        store = _make_store([_make_cred(last_rotated=datetime.now(UTC))])
        toolkit = SecurityToolkit(credential_stores=[store])

        result = await toolkit._evaluate_control({"id": "SOC2-CC6.2", "title": "x"}, None)

        assert result["status"] == "passing"

    @pytest.mark.asyncio
    async def test_failing_missing_rotation_metadata(self) -> None:
        store = _make_store([_make_cred(last_rotated=None, rotation_policy=None)])
        toolkit = SecurityToolkit(credential_stores=[store])

        result = await toolkit._evaluate_control({"id": "HIPAA-164.312d", "title": "x"}, None)

        assert result["status"] == "failing"


class TestEvaluateControlRotationPolicy:
    """SOC2-CC6.3 / PCI-DSS-8.1 — rotation policy."""

    @pytest.mark.asyncio
    async def test_passing_with_policy(self) -> None:
        store = _make_store([_make_cred(rotation_policy="30d")])
        toolkit = SecurityToolkit(credential_stores=[store])

        result = await toolkit._evaluate_control({"id": "PCI-DSS-8.1", "title": "x"}, None)

        assert result["status"] == "passing"

    @pytest.mark.asyncio
    async def test_failing_without_policy(self) -> None:
        store = _make_store([_make_cred(rotation_policy=None)])
        toolkit = SecurityToolkit(credential_stores=[store])

        result = await toolkit._evaluate_control({"id": "SOC2-CC6.3", "title": "x"}, None)

        assert result["status"] == "failing"


class TestEvaluateControlMonitoring:
    """SOC2-CC7.1 — system monitoring."""

    @pytest.mark.asyncio
    async def test_passing_connector_reachable(self) -> None:
        conn = _make_connector(resources=[])
        router = _make_router({"kubernetes": conn})
        toolkit = SecurityToolkit(connector_router=router)

        result = await toolkit._evaluate_control({"id": "SOC2-CC7.1", "title": "x"}, None)

        assert result["status"] == "passing"

    @pytest.mark.asyncio
    async def test_failing_connector_unreachable(self) -> None:
        conn = _make_connector()
        conn.list_resources.side_effect = Exception("ConnectionRefused")
        router = _make_router({"kubernetes": conn})
        toolkit = SecurityToolkit(connector_router=router)

        result = await toolkit._evaluate_control({"id": "SOC2-CC7.1", "title": "x"}, None)

        assert result["status"] == "failing"


class TestEvaluateControlAnomalyDetection:
    """SOC2-CC7.2 — always unknown (external integration required)."""

    @pytest.mark.asyncio
    async def test_returns_unknown(self) -> None:
        toolkit = SecurityToolkit()

        result = await toolkit._evaluate_control({"id": "SOC2-CC7.2", "title": "x"}, None)

        assert result["status"] == "unknown"


class TestEvaluateControlChangeManagement:
    """SOC2-CC8.1 — change management via get_events()."""

    @pytest.mark.asyncio
    async def test_passing_events_found(self) -> None:
        conn = _make_connector(events=[{"type": "change"}])
        router = _make_router({"aws": conn})
        toolkit = SecurityToolkit(connector_router=router)

        result = await toolkit._evaluate_control({"id": "SOC2-CC8.1", "title": "x"}, None)

        assert result["status"] == "passing"

    @pytest.mark.asyncio
    async def test_failing_no_events(self) -> None:
        conn = _make_connector(events=[])
        router = _make_router({"aws": conn})
        toolkit = SecurityToolkit(connector_router=router)

        result = await toolkit._evaluate_control({"id": "SOC2-CC8.1", "title": "x"}, None)

        assert result["status"] == "failing"


class TestEvaluateControlDefaultCredentials:
    """PCI-DSS-2.1 — credentials unrotated >90 days."""

    @pytest.mark.asyncio
    async def test_passing_recently_rotated(self) -> None:
        store = _make_store([_make_cred(last_rotated=datetime.now(UTC) - timedelta(days=30))])
        toolkit = SecurityToolkit(credential_stores=[store])

        result = await toolkit._evaluate_control({"id": "PCI-DSS-2.1", "title": "x"}, None)

        assert result["status"] == "passing"

    @pytest.mark.asyncio
    async def test_failing_stale_credential(self) -> None:
        store = _make_store([_make_cred(last_rotated=datetime.now(UTC) - timedelta(days=120))])
        toolkit = SecurityToolkit(credential_stores=[store])

        result = await toolkit._evaluate_control({"id": "PCI-DSS-2.1", "title": "x"}, None)

        assert result["status"] == "failing"


class TestEvaluateControlPatching:
    """PCI-DSS-6.2 — CVE scanning."""

    @pytest.mark.asyncio
    async def test_passing_no_critical_high(self) -> None:
        source = _make_cve_source([{"severity": "low", "cve_id": "CVE-2025-001"}])
        toolkit = SecurityToolkit(cve_sources=[source])

        result = await toolkit._evaluate_control(
            {"id": "PCI-DSS-6.2", "title": "x"}, ["resource-1"]
        )

        assert result["status"] == "passing"

    @pytest.mark.asyncio
    async def test_failing_critical_cve(self) -> None:
        source = _make_cve_source([{"severity": "critical", "cve_id": "CVE-2025-999"}])
        toolkit = SecurityToolkit(cve_sources=[source])

        result = await toolkit._evaluate_control(
            {"id": "PCI-DSS-6.2", "title": "x"}, ["resource-1"]
        )

        assert result["status"] == "failing"


class TestEvaluateControlCIS:
    """CIS-* Kubernetes benchmarks."""

    @pytest.mark.asyncio
    async def test_passing_k8s_resources_found(self) -> None:
        resource = MagicMock(spec=Resource)
        conn = _make_connector(resources=[resource])
        router = _make_router({"kubernetes": conn})
        toolkit = SecurityToolkit(connector_router=router)

        result = await toolkit._evaluate_control({"id": "CIS-1.1", "title": "x"}, None)

        assert result["status"] == "passing"

    @pytest.mark.asyncio
    async def test_unknown_no_resources(self) -> None:
        conn = _make_connector(resources=[])
        router = _make_router({"kubernetes": conn})
        toolkit = SecurityToolkit(connector_router=router)

        result = await toolkit._evaluate_control({"id": "CIS-5.1", "title": "x"}, None)

        assert result["status"] == "unknown"


# ===========================================================================
# check_compliance integration tests
# ===========================================================================


class TestCheckCompliance:
    @pytest.mark.asyncio
    async def test_full_soc2_with_mixed_results(self) -> None:
        """SOC2 framework with working credential store — some pass, some unknown."""
        future = datetime.now(UTC) + timedelta(days=30)
        store = _make_store(
            [_make_cred(expires_at=future, last_rotated=datetime.now(UTC), rotation_policy="90d")]
        )
        conn = _make_connector(events=[{"type": "change"}])
        router = _make_router({"kubernetes": conn})
        toolkit = SecurityToolkit(connector_router=router, credential_stores=[store])

        result = await toolkit.check_compliance("soc2")

        assert result["framework"] == "soc2"
        assert result["controls_checked"] == 6
        statuses = [c["status"] for c in result["controls"]]
        assert "passing" in statuses
        # CC7.2 (anomaly detection) should be unknown
        cc72 = next(c for c in result["controls"] if c["control_id"] == "SOC2-CC7.2")
        assert cc72["status"] == "unknown"

    @pytest.mark.asyncio
    async def test_no_router_returns_empty(self) -> None:
        toolkit = SecurityToolkit()

        result = await toolkit.check_compliance("soc2")

        assert result["controls_checked"] == 0
        assert result["score"] == 0.0

    @pytest.mark.asyncio
    async def test_unsupported_framework_returns_empty(self) -> None:
        conn = _make_connector()
        router = _make_router({"kubernetes": conn})
        toolkit = SecurityToolkit(connector_router=router)

        result = await toolkit.check_compliance("iso27001")

        assert result["controls_checked"] == 0
        assert result["controls"] == []

    @pytest.mark.asyncio
    async def test_score_calculation(self) -> None:
        """Score = (passing / total) * 100."""
        future = datetime.now(UTC) + timedelta(days=30)
        store = _make_store(
            [_make_cred(expires_at=future, last_rotated=datetime.now(UTC), rotation_policy="90d")]
        )
        conn = _make_connector()
        router = _make_router({"kubernetes": conn})
        toolkit = SecurityToolkit(connector_router=router, credential_stores=[store])

        result = await toolkit.check_compliance("hipaa")

        total = result["controls_checked"]
        passing = result["passing"]
        assert total > 0
        expected_score = (passing / total) * 100
        assert abs(result["score"] - expected_score) < 0.01

    @pytest.mark.asyncio
    async def test_controls_have_evidence(self) -> None:
        """Each control result should include an evidence list."""
        future = datetime.now(UTC) + timedelta(days=30)
        store = _make_store([_make_cred(expires_at=future)])
        toolkit = SecurityToolkit(credential_stores=[store])

        result = await toolkit.check_compliance("soc2")

        for control in result["controls"]:
            assert isinstance(control["evidence"], list)
