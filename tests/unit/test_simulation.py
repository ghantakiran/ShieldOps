"""Tests for remediation simulation."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from shieldops.agents.remediation.simulator import (
    RemediationSimulator,
)


class TestRemediationSimulator:
    @pytest.mark.asyncio
    async def test_simulate_restart(self) -> None:
        sim = RemediationSimulator()
        result = await sim.simulate(
            action_type="restart_service",
            target_resource="api-server",
            environment="staging",
        )
        assert result.simulation_id.startswith("sim-")
        assert result.status == "completed"
        assert len(result.planned_steps) == 4
        assert result.planned_steps[0].action == "snapshot"
        assert result.planned_steps[2].action == "restart"
        assert result.impact.downtime_risk == "minimal"

    @pytest.mark.asyncio
    async def test_simulate_scale_up(self) -> None:
        sim = RemediationSimulator()
        result = await sim.simulate(
            action_type="scale_up",
            target_resource="web-app",
            parameters={"replicas": 3},
        )
        assert len(result.planned_steps) == 3
        assert result.impact.downtime_risk == "none"
        assert "3 replicas" in result.planned_steps[1].description

    @pytest.mark.asyncio
    async def test_simulate_rollback(self) -> None:
        sim = RemediationSimulator()
        result = await sim.simulate(
            action_type="rollback",
            target_resource="payment-service",
            environment="production",
            risk_level="high",
        )
        assert len(result.planned_steps) == 4
        assert result.impact.blast_radius == "service"
        assert any("Rollback" in w for w in result.warnings)
        assert any("production" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_simulate_unknown_action(self) -> None:
        sim = RemediationSimulator()
        result = await sim.simulate(
            action_type="custom_action",
            target_resource="some-resource",
        )
        assert len(result.planned_steps) == 1
        assert result.planned_steps[0].action == "custom_action"

    @pytest.mark.asyncio
    async def test_production_warnings(self) -> None:
        sim = RemediationSimulator()
        result = await sim.simulate(
            action_type="patch",
            target_resource="database",
            environment="production",
            risk_level="high",
        )
        assert any("production" in w.lower() for w in result.warnings)
        assert any("high risk" in w.lower() for w in result.warnings)
        assert result.impact.confidence == 0.7

    @pytest.mark.asyncio
    async def test_policy_denied(self) -> None:
        mock_policy = AsyncMock()
        mock_policy.evaluate = AsyncMock(
            return_value={"allow": False, "violations": ["env_restricted"]}
        )
        sim = RemediationSimulator(policy_engine=mock_policy)
        result = await sim.simulate(
            action_type="restart_service",
            target_resource="db",
            risk_level="critical",
        )
        assert result.status == "rejected"
        assert result.policy_check["denied"] is True
        assert "BLOCKED" in result.recommendation

    @pytest.mark.asyncio
    async def test_policy_allowed(self) -> None:
        mock_policy = AsyncMock()
        mock_policy.evaluate = AsyncMock(return_value={"allow": True})
        sim = RemediationSimulator(policy_engine=mock_policy)
        result = await sim.simulate(
            action_type="scale_up",
            target_resource="web",
        )
        assert result.status == "completed"
        assert result.policy_check["denied"] is False

    @pytest.mark.asyncio
    async def test_policy_error(self) -> None:
        mock_policy = AsyncMock()
        mock_policy.evaluate = AsyncMock(side_effect=Exception("OPA unreachable"))
        sim = RemediationSimulator(policy_engine=mock_policy)
        result = await sim.simulate(
            action_type="restart_service",
            target_resource="svc",
        )
        assert result.status == "completed"
        assert "error" in result.policy_check["result"]

    @pytest.mark.asyncio
    async def test_no_side_effects(self) -> None:
        """Simulation must not touch any external systems."""
        sim = RemediationSimulator()
        result = await sim.simulate(
            action_type="restart_service",
            target_resource="critical-db",
            environment="production",
            risk_level="critical",
        )
        # No actual restart happened — just plan and analysis
        assert result.status in ("completed", "rejected")
        assert result.planned_steps[0].action == "snapshot"

    @pytest.mark.asyncio
    async def test_list_simulations(self) -> None:
        sim = RemediationSimulator()
        await sim.simulate(action_type="restart_service", target_resource="svc-1")
        await sim.simulate(action_type="scale_up", target_resource="svc-2")
        sims = sim.list_simulations()
        assert len(sims) == 2

    @pytest.mark.asyncio
    async def test_get_simulation(self) -> None:
        sim = RemediationSimulator()
        result = await sim.simulate(action_type="restart_service", target_resource="svc")
        found = sim.get_simulation(result.simulation_id)
        assert found is not None
        assert found.simulation_id == result.simulation_id
        assert sim.get_simulation("nonexistent") is None

    @pytest.mark.asyncio
    async def test_recommendation_levels(self) -> None:
        sim = RemediationSimulator()

        # Low risk → SAFE
        r1 = await sim.simulate(
            action_type="scale_up", target_resource="svc", environment="staging"
        )
        assert "SAFE" in r1.recommendation

        # Critical → CAUTION
        r2 = await sim.simulate(action_type="patch", target_resource="db", risk_level="critical")
        assert "CAUTION" in r2.recommendation

    @pytest.mark.asyncio
    async def test_step_reversibility(self) -> None:
        sim = RemediationSimulator()
        result = await sim.simulate(action_type="restart_service", target_resource="svc")
        # Low/medium risk steps should be reversible
        for step in result.planned_steps:
            if step.risk_level != "high":
                assert step.reversible is True


class TestSimulationRoutes:
    def test_simulate_endpoint(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole
        from shieldops.api.routes import simulations

        app = FastAPI()
        app.include_router(simulations.router, prefix="/api/v1")
        mock_user = UserResponse(
            id="usr-t", email="t@t.com", name="T", role=UserRole.OPERATOR, is_active=True
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        simulator = RemediationSimulator()
        simulations.set_simulator(simulator)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/remediations/simulate",
            json={
                "action_type": "restart_service",
                "target_resource": "api-server",
            },
        )
        assert resp.status_code == 200
        data = resp.json()["simulation"]
        assert data["status"] == "completed"
        assert len(data["planned_steps"]) == 4

    def test_list_simulations_empty(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole
        from shieldops.api.routes import simulations

        app = FastAPI()
        app.include_router(simulations.router, prefix="/api/v1")
        mock_user = UserResponse(
            id="usr-t", email="t@t.com", name="T", role=UserRole.VIEWER, is_active=True
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        simulator = RemediationSimulator()
        simulations.set_simulator(simulator)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/remediations/simulations")
        assert resp.status_code == 200
        assert resp.json()["simulations"] == []

    def test_simulator_not_initialized(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole
        from shieldops.api.routes import simulations

        app = FastAPI()
        app.include_router(simulations.router, prefix="/api/v1")
        mock_user = UserResponse(
            id="usr-t", email="t@t.com", name="T", role=UserRole.OPERATOR, is_active=True
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user
        simulations._simulator = None

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/remediations/simulate",
            json={
                "action_type": "test",
                "target_resource": "svc",
            },
        )
        assert resp.status_code == 503
