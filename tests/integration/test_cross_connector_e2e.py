"""End-to-end cross-connector tests using ConnectorRouter with fake connectors.

Validates that the ConnectorRouter correctly routes operations to the right
provider, that actions execute and mutate state independently across providers,
and that failures in one connector do not affect others.
"""

import pytest

from shieldops.connectors.base import ConnectorRouter
from shieldops.models.base import Environment, ExecutionStatus, RemediationAction, RiskLevel
from tests.integration.fakes.azure_fake import FakeAzureConnector
from tests.integration.fakes.gcp_fake import FakeGCPConnector

# ============================================================================
# Multi-Provider Remediation
# ============================================================================


@pytest.mark.integration
class TestMultiProviderRemediation:
    """Verify that the router dispatches to the correct connector and that
    remediation actions succeed independently across providers."""

    @pytest.mark.asyncio
    async def test_route_to_correct_connector(self, fake_connector_router: ConnectorRouter) -> None:
        """Router returns the right connector type for each registered provider."""
        gcp = fake_connector_router.get("gcp")
        azure = fake_connector_router.get("azure")
        k8s = fake_connector_router.get("kubernetes")

        assert isinstance(gcp, FakeGCPConnector)
        assert isinstance(azure, FakeAzureConnector)
        assert k8s is not None

        providers = fake_connector_router.providers
        assert "gcp" in providers
        assert "azure" in providers
        assert "kubernetes" in providers

    @pytest.mark.asyncio
    async def test_same_action_different_providers(
        self,
        fake_connector_router: ConnectorRouter,
    ) -> None:
        """The same logical action (reboot) succeeds on both GCP and Azure
        when dispatched through their respective connectors."""
        gcp_connector = fake_connector_router.get("gcp")
        azure_connector = fake_connector_router.get("azure")

        gcp_action = RemediationAction(
            id="gcp-reboot-001",
            action_type="reboot_instance",
            target_resource="web-server-1",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.MEDIUM,
            parameters={},
            description="Reboot GCP instance",
        )

        azure_action = RemediationAction(
            id="azure-restart-001",
            action_type="restart_vm",
            target_resource="web-vm-1",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.MEDIUM,
            parameters={},
            description="Restart Azure VM",
        )

        gcp_result = await gcp_connector.execute_action(gcp_action)
        azure_result = await azure_connector.execute_action(azure_action)

        assert gcp_result.status == ExecutionStatus.SUCCESS
        assert azure_result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_sequential_cross_provider_remediation(
        self,
        fake_connector_router: ConnectorRouter,
    ) -> None:
        """Sequential actions across providers: reboot GCP, then restart Azure,
        then verify both resources remain healthy."""
        gcp = fake_connector_router.get("gcp")
        azure = fake_connector_router.get("azure")

        gcp_action = RemediationAction(
            id="seq-gcp-001",
            action_type="reboot_instance",
            target_resource="web-server-1",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.MEDIUM,
            parameters={},
            description="Sequential GCP reboot",
        )
        gcp_result = await gcp.execute_action(gcp_action)
        assert gcp_result.status == ExecutionStatus.SUCCESS

        azure_action = RemediationAction(
            id="seq-azure-001",
            action_type="restart_vm",
            target_resource="web-vm-1",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.MEDIUM,
            parameters={},
            description="Sequential Azure restart",
        )
        azure_result = await azure.execute_action(azure_action)
        assert azure_result.status == ExecutionStatus.SUCCESS

        # Verify both resources are healthy after remediation
        gcp_health = await gcp.get_health("web-server-1")
        azure_health = await azure.get_health("web-vm-1")
        assert gcp_health.healthy is True
        assert azure_health.healthy is True


# ============================================================================
# Cross-Provider Rollback
# ============================================================================


@pytest.mark.integration
class TestCrossProviderRollback:
    """Verify snapshot-and-rollback works across different providers."""

    @pytest.mark.asyncio
    async def test_snapshot_and_rollback_gcp(
        self,
        fake_gcp_connector: FakeGCPConnector,
    ) -> None:
        """Snapshot a GCP instance, stop it, then rollback and verify RUNNING."""
        # Snapshot while RUNNING
        snapshot = await fake_gcp_connector.create_snapshot("web-server-1")
        assert snapshot.state.get("status") == "RUNNING"

        # Stop the instance
        stop_action = RemediationAction(
            id="gcp-stop-001",
            action_type="stop_instance",
            target_resource="web-server-1",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.LOW,
            parameters={},
            description="Stop GCP instance for rollback test",
        )
        stop_result = await fake_gcp_connector.execute_action(stop_action)
        assert stop_result.status == ExecutionStatus.SUCCESS

        # Confirm it's stopped
        health = await fake_gcp_connector.get_health("web-server-1")
        assert health.healthy is False

        # Rollback
        rollback_result = await fake_gcp_connector.rollback(snapshot.id)
        assert rollback_result.status == ExecutionStatus.SUCCESS

        # Verify restored to RUNNING
        health_after = await fake_gcp_connector.get_health("web-server-1")
        assert health_after.healthy is True

    @pytest.mark.asyncio
    async def test_snapshot_and_rollback_azure(
        self,
        fake_azure_connector: FakeAzureConnector,
    ) -> None:
        """Snapshot an Azure VM, deallocate it, then rollback and verify running."""
        # Snapshot while running
        snapshot = await fake_azure_connector.create_snapshot("web-vm-1")
        assert snapshot.state.get("power_state") == "running"

        # Deallocate the VM
        dealloc_action = RemediationAction(
            id="azure-dealloc-001",
            action_type="deallocate_vm",
            target_resource="web-vm-1",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.LOW,
            parameters={},
            description="Deallocate Azure VM for rollback test",
        )
        dealloc_result = await fake_azure_connector.execute_action(dealloc_action)
        assert dealloc_result.status == ExecutionStatus.SUCCESS

        # Confirm it's deallocated
        health = await fake_azure_connector.get_health("web-vm-1")
        assert health.healthy is False

        # Rollback
        rollback_result = await fake_azure_connector.rollback(snapshot.id)
        assert rollback_result.status == ExecutionStatus.SUCCESS

        # Verify restored to running
        health_after = await fake_azure_connector.get_health("web-vm-1")
        assert health_after.healthy is True

    @pytest.mark.asyncio
    async def test_multi_resource_rollback(
        self,
        fake_connector_router: ConnectorRouter,
    ) -> None:
        """Snapshot resources across GCP and Azure, break both, then rollback
        both and verify they return to healthy state."""
        gcp = fake_connector_router.get("gcp")
        azure = fake_connector_router.get("azure")

        # Snapshot both
        gcp_snapshot = await gcp.create_snapshot("web-server-1")
        azure_snapshot = await azure.create_snapshot("web-vm-1")

        # Break both -- stop GCP, deallocate Azure
        stop_gcp = RemediationAction(
            id="multi-stop-gcp",
            action_type="stop_instance",
            target_resource="web-server-1",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.LOW,
            parameters={},
            description="Stop GCP for multi-rollback",
        )
        dealloc_azure = RemediationAction(
            id="multi-dealloc-azure",
            action_type="deallocate_vm",
            target_resource="web-vm-1",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.LOW,
            parameters={},
            description="Deallocate Azure for multi-rollback",
        )

        gcp_stop_result = await gcp.execute_action(stop_gcp)
        azure_dealloc_result = await azure.execute_action(dealloc_azure)
        assert gcp_stop_result.status == ExecutionStatus.SUCCESS
        assert azure_dealloc_result.status == ExecutionStatus.SUCCESS

        # Confirm both are unhealthy
        assert (await gcp.get_health("web-server-1")).healthy is False
        assert (await azure.get_health("web-vm-1")).healthy is False

        # Rollback both
        gcp_rollback = await gcp.rollback(gcp_snapshot.id)
        azure_rollback = await azure.rollback(azure_snapshot.id)
        assert gcp_rollback.status == ExecutionStatus.SUCCESS
        assert azure_rollback.status == ExecutionStatus.SUCCESS

        # Both healthy again
        assert (await gcp.get_health("web-server-1")).healthy is True
        assert (await azure.get_health("web-vm-1")).healthy is True


# ============================================================================
# Provider Failure Isolation
# ============================================================================


@pytest.mark.integration
class TestProviderFailureIsolation:
    """Verify that failures in one connector do not affect others
    and that the router handles missing providers gracefully."""

    @pytest.mark.asyncio
    async def test_missing_provider_raises(
        self,
        fake_connector_router: ConnectorRouter,
    ) -> None:
        """Requesting a nonexistent provider raises ValueError."""
        with pytest.raises(ValueError, match="No connector registered for provider 'nonexistent'"):
            fake_connector_router.get("nonexistent")

    @pytest.mark.asyncio
    async def test_one_connector_fail_others_unaffected(
        self,
        fake_connector_router: ConnectorRouter,
    ) -> None:
        """A failed action on GCP (nonexistent resource) does not break Azure."""
        gcp = fake_connector_router.get("gcp")
        azure = fake_connector_router.get("azure")

        # Action on nonexistent GCP resource should fail
        bad_action = RemediationAction(
            id="fail-gcp-001",
            action_type="reboot_instance",
            target_resource="nonexistent-instance",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.LOW,
            parameters={},
            description="Reboot nonexistent GCP instance",
        )
        gcp_result = await gcp.execute_action(bad_action)
        assert gcp_result.status == ExecutionStatus.FAILED

        # Azure connector should still work fine
        good_action = RemediationAction(
            id="ok-azure-001",
            action_type="restart_vm",
            target_resource="web-vm-1",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.LOW,
            parameters={},
            description="Restart existing Azure VM",
        )
        azure_result = await azure.execute_action(good_action)
        assert azure_result.status == ExecutionStatus.SUCCESS

        # Azure resource is healthy
        health = await azure.get_health("web-vm-1")
        assert health.healthy is True

    @pytest.mark.asyncio
    async def test_action_on_nonexistent_resource_doesnt_crash_router(
        self,
        fake_connector_router: ConnectorRouter,
    ) -> None:
        """Executing an action on a missing resource via a routed connector
        returns FAILED but does not affect the router's ability to serve
        other providers."""
        gcp = fake_connector_router.get("gcp")

        # Execute on missing resource
        bad_action = RemediationAction(
            id="missing-resource-001",
            action_type="stop_instance",
            target_resource="does-not-exist",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.LOW,
            parameters={},
            description="Stop nonexistent instance",
        )
        result = await gcp.execute_action(bad_action)
        assert result.status == ExecutionStatus.FAILED

        # Router still serves other providers
        azure = fake_connector_router.get("azure")
        assert isinstance(azure, FakeAzureConnector)

        k8s = fake_connector_router.get("kubernetes")
        assert k8s is not None

        # And GCP connector itself still works for valid resources
        gcp_health = await gcp.get_health("web-server-1")
        assert gcp_health.healthy is True
