"""Tests for cost optimization autopilot."""

from __future__ import annotations

import pytest

from shieldops.agents.cost.autopilot import (
    AutopilotConfig,
    CostAutopilot,
    CostRecommendation,
)


def _sample_cost_data() -> dict:
    return {
        "resources": [
            {"id": "staging/vm-idle-1", "type": "compute", "monthly_cost": 100, "utilization": 5},
            {
                "id": "staging/vm-underused",
                "type": "compute",
                "monthly_cost": 200,
                "utilization": 30,
            },
            {
                "id": "production/db-main",
                "type": "database",
                "monthly_cost": 500,
                "utilization": 80,
            },
        ]
    }


class TestCostAutopilot:
    @pytest.mark.asyncio
    async def test_generate_recommendations(self) -> None:
        ap = CostAutopilot()
        result = await ap.analyze_and_recommend(cost_data=_sample_cost_data())
        assert result.total_recommendations == 2  # idle + underused
        assert result.total_estimated_savings > 0

    @pytest.mark.asyncio
    async def test_idle_resource_detected(self) -> None:
        ap = CostAutopilot()
        result = await ap.analyze_and_recommend(cost_data=_sample_cost_data())
        idle_recs = [r for r in result.recommendations if r.category == "idle_resource"]
        assert len(idle_recs) == 1
        assert idle_recs[0].savings_percentage == 90.0

    @pytest.mark.asyncio
    async def test_rightsize_detected(self) -> None:
        ap = CostAutopilot()
        result = await ap.analyze_and_recommend(cost_data=_sample_cost_data())
        rightsize_recs = [r for r in result.recommendations if r.category == "rightsize"]
        assert len(rightsize_recs) == 1
        assert rightsize_recs[0].savings_percentage == 40.0

    @pytest.mark.asyncio
    async def test_no_recommendation_for_utilized(self) -> None:
        ap = CostAutopilot()
        result = await ap.analyze_and_recommend(cost_data=_sample_cost_data())
        # The 80% utilized DB should not generate a recommendation
        db_recs = [r for r in result.recommendations if "db-main" in r.resource_id]
        assert len(db_recs) == 0

    @pytest.mark.asyncio
    async def test_auto_approval_disabled(self) -> None:
        config = AutopilotConfig(enabled=False)
        ap = CostAutopilot(config=config)
        result = await ap.analyze_and_recommend(cost_data=_sample_cost_data())
        assert result.auto_approved == 0
        assert all(r.status == "pending" for r in result.recommendations)

    @pytest.mark.asyncio
    async def test_auto_approval_enabled(self) -> None:
        config = AutopilotConfig(enabled=True, auto_approval_threshold=0.5, dry_run=True)
        ap = CostAutopilot(config=config)
        result = await ap.analyze_and_recommend(cost_data=_sample_cost_data())
        assert result.auto_approved > 0

    @pytest.mark.asyncio
    async def test_auto_execution(self) -> None:
        config = AutopilotConfig(
            enabled=True,
            auto_approval_threshold=0.5,
            dry_run=False,
            max_monthly_savings_auto=1000,
        )
        ap = CostAutopilot(config=config)
        result = await ap.analyze_and_recommend(cost_data=_sample_cost_data())
        executed = [r for r in result.recommendations if r.status == "executed"]
        assert len(executed) > 0
        assert result.total_executed_savings > 0

    @pytest.mark.asyncio
    async def test_excluded_environment(self) -> None:
        config = AutopilotConfig(
            enabled=True,
            excluded_environments=["staging"],
            dry_run=True,
        )
        ap = CostAutopilot(config=config)
        result = await ap.analyze_and_recommend(cost_data=_sample_cost_data())
        # All resources are staging/* so none should be auto-approved
        assert result.auto_approved == 0

    @pytest.mark.asyncio
    async def test_risk_scoring(self) -> None:
        ap = CostAutopilot()
        rec = CostRecommendation(
            category="idle_resource",
            resource_type="compute",
            estimated_savings_monthly=50,
        )
        score = ap._calculate_risk(rec)
        assert 0.0 <= score <= 1.0
        assert score < 0.5  # idle_resource + compute should be low risk

    @pytest.mark.asyncio
    async def test_database_higher_risk(self) -> None:
        ap = CostAutopilot()
        rec = CostRecommendation(
            category="rightsize",
            resource_type="database",
            estimated_savings_monthly=1500,
        )
        score = ap._calculate_risk(rec)
        assert score >= 0.5  # database + rightsize + high savings

    @pytest.mark.asyncio
    async def test_manual_approve_and_execute(self) -> None:
        ap = CostAutopilot()
        await ap.analyze_and_recommend(cost_data=_sample_cost_data())
        pending = ap.list_recommendations(status="pending")
        if pending:
            rec = pending[0]
            approved = await ap.approve_recommendation(rec.id)
            assert approved is not None
            assert approved.status == "approved"

            executed = await ap.execute_recommendation(rec.id)
            assert executed is not None
            assert executed.status == "executed"

    @pytest.mark.asyncio
    async def test_approve_nonexistent(self) -> None:
        ap = CostAutopilot()
        result = await ap.approve_recommendation("fake-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_execute_unapproved(self) -> None:
        ap = CostAutopilot()
        await ap.analyze_and_recommend(cost_data=_sample_cost_data())
        pending = ap.list_recommendations(status="pending")
        if pending:
            result = await ap.execute_recommendation(pending[0].id)
            assert result is None  # Can't execute unapproved

    @pytest.mark.asyncio
    async def test_update_config(self) -> None:
        ap = CostAutopilot()
        updated = ap.update_config(enabled=True, dry_run=False)
        assert updated.enabled is True
        assert updated.dry_run is False

    @pytest.mark.asyncio
    async def test_history(self) -> None:
        ap = CostAutopilot()
        await ap.analyze_and_recommend(cost_data=_sample_cost_data())
        await ap.analyze_and_recommend(cost_data={})
        history = ap.get_history()
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_max_savings_threshold(self) -> None:
        config = AutopilotConfig(
            enabled=True,
            max_monthly_savings_auto=50,
            dry_run=True,
        )
        ap = CostAutopilot(config=config)
        result = await ap.analyze_and_recommend(cost_data=_sample_cost_data())
        # All recs should exceed $50 threshold, so none auto-approved
        for rec in result.recommendations:
            if rec.estimated_savings_monthly > 50:
                assert not rec.auto_approved


class TestAutopilotRoutes:
    def test_get_config(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole
        from shieldops.api.routes import autopilot

        app = FastAPI()
        app.include_router(autopilot.router, prefix="/api/v1")
        mock_user = UserResponse(
            id="usr-t", email="t@t.com", name="T", role=UserRole.ADMIN, is_active=True
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        ap = CostAutopilot()
        autopilot.set_autopilot(ap)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/cost/autopilot/config")
        assert resp.status_code == 200
        assert resp.json()["configured"] is True

    def test_run_analysis(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole
        from shieldops.api.routes import autopilot

        app = FastAPI()
        app.include_router(autopilot.router, prefix="/api/v1")
        mock_user = UserResponse(
            id="usr-t", email="t@t.com", name="T", role=UserRole.ADMIN, is_active=True
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        ap = CostAutopilot()
        autopilot.set_autopilot(ap)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/cost/autopilot/analyze",
            json={
                "cost_data": _sample_cost_data(),
            },
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["total_recommendations"] == 2
