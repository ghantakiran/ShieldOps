"""End-to-end integration tests for the Security Agent.

Tests the full LangGraph workflow: scan_vulnerabilities → assess_findings →
check_credentials → evaluate_compliance → synthesize_posture, plus the
optional action phase (evaluate_policy → execute_patches → rotate_credentials).
"""

from unittest.mock import patch

import pytest

from shieldops.agents.security.models import SecurityScanState
from shieldops.agents.security.runner import SecurityRunner
from shieldops.models.base import Environment


@pytest.mark.asyncio
async def test_security_scan_full_pipeline(
    mock_connector_router,
    mock_cve_source,
    mock_credential_store,
    security_llm_responses,
):
    """Full scan executes all phases and produces a posture score > 0."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return security_llm_responses[schema]

    with patch("shieldops.agents.security.nodes.llm_structured", side_effect=fake_llm):
        runner = SecurityRunner(
            connector_router=mock_connector_router,
            cve_sources=[mock_cve_source],
            credential_stores=[mock_credential_store],
        )

        result = await runner.scan(
            environment=Environment.PRODUCTION,
            scan_type="full",
            target_resources=["default/api-server"],
        )

    assert isinstance(result, SecurityScanState)
    assert result.error is None
    assert result.current_step == "complete"
    assert result.posture is not None
    assert result.posture.overall_score > 0
    assert len(result.cve_findings) > 0
    assert result.critical_cve_count >= 1
    assert len(result.credential_statuses) > 0
    assert result.compliance_score > 0
    assert len(result.reasoning_chain) >= 4  # scan, assess, creds, compliance, posture
    assert result.scan_duration_ms > 0
    # No actions executed (execute_actions defaults to False)
    assert result.patches_applied == 0
    assert result.credentials_rotated == 0


@pytest.mark.asyncio
async def test_security_scan_cve_only(
    mock_connector_router,
    mock_cve_source,
    mock_credential_store,
    security_llm_responses,
):
    """cve_only scan skips credentials and compliance phases."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return security_llm_responses[schema]

    with patch("shieldops.agents.security.nodes.llm_structured", side_effect=fake_llm):
        runner = SecurityRunner(
            connector_router=mock_connector_router,
            cve_sources=[mock_cve_source],
            credential_stores=[mock_credential_store],
        )

        result = await runner.scan(
            environment=Environment.PRODUCTION,
            scan_type="cve_only",
            target_resources=["default/api-server"],
        )

    assert result.error is None
    assert result.current_step == "complete"
    assert len(result.cve_findings) > 0
    # Credentials and compliance should be skipped
    assert len(result.credential_statuses) == 0
    assert len(result.compliance_controls) == 0


@pytest.mark.asyncio
async def test_security_scan_with_actions_policy_allowed(
    mock_connector_router,
    mock_policy_engine,
    mock_cve_source,
    mock_credential_store,
    security_llm_responses,
):
    """When execute_actions=True and policy allows, patches and rotations run."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return security_llm_responses[schema]

    with patch("shieldops.agents.security.nodes.llm_structured", side_effect=fake_llm):
        runner = SecurityRunner(
            connector_router=mock_connector_router,
            cve_sources=[mock_cve_source],
            credential_stores=[mock_credential_store],
            policy_engine=mock_policy_engine,
        )

        result = await runner.scan(
            environment=Environment.PRODUCTION,
            scan_type="full",
            target_resources=["default/api-server"],
            execute_actions=True,
        )

    assert result.error is None
    assert result.action_policy_result is not None
    assert result.action_policy_result.allowed is True
    assert result.patches_applied > 0
    assert len(result.patch_results) > 0
    assert result.credentials_rotated > 0
    assert len(result.rotation_results) > 0


@pytest.mark.asyncio
async def test_security_scan_with_actions_policy_denied(
    mock_connector_router,
    mock_policy_engine_deny,
    mock_cve_source,
    mock_credential_store,
    security_llm_responses,
):
    """When policy denies, no patches or rotations execute."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return security_llm_responses[schema]

    with patch("shieldops.agents.security.nodes.llm_structured", side_effect=fake_llm):
        runner = SecurityRunner(
            connector_router=mock_connector_router,
            cve_sources=[mock_cve_source],
            credential_stores=[mock_credential_store],
            policy_engine=mock_policy_engine_deny,
        )

        result = await runner.scan(
            environment=Environment.PRODUCTION,
            scan_type="full",
            target_resources=["default/api-server"],
            execute_actions=True,
        )

    assert result.error is None
    assert result.action_policy_result is not None
    assert result.action_policy_result.allowed is False
    # No actions should have been executed
    assert result.patches_applied == 0
    assert result.credentials_rotated == 0


@pytest.mark.asyncio
async def test_security_scan_stores_result(
    mock_connector_router,
    mock_cve_source,
    mock_credential_store,
    security_llm_responses,
):
    """Runner stores scans in internal dict; list_scans/get_scan work."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return security_llm_responses[schema]

    with patch("shieldops.agents.security.nodes.llm_structured", side_effect=fake_llm):
        runner = SecurityRunner(
            connector_router=mock_connector_router,
            cve_sources=[mock_cve_source],
            credential_stores=[mock_credential_store],
        )

        result = await runner.scan(
            environment=Environment.PRODUCTION,
            target_resources=["default/api-server"],
        )

    listed = runner.list_scans()
    assert len(listed) == 1
    assert listed[0]["scan_id"] == result.scan_id
    assert listed[0]["scan_type"] == "full"
    assert listed[0]["status"] == "complete"

    fetched = runner.get_scan(result.scan_id)
    assert fetched is not None
    assert fetched.scan_id == result.scan_id


@pytest.mark.asyncio
async def test_security_scan_handles_error(
    mock_connector_router,
    security_llm_responses,
):
    """Graceful error handling when a scan fails."""
    # CVE source that raises an exception
    from unittest.mock import AsyncMock

    bad_source = AsyncMock()
    bad_source.source_name = "bad-source"
    bad_source.scan.side_effect = RuntimeError("Scanner offline")

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return security_llm_responses[schema]

    with patch("shieldops.agents.security.nodes.llm_structured", side_effect=fake_llm):
        runner = SecurityRunner(
            connector_router=mock_connector_router,
            cve_sources=[bad_source],
        )

        result = await runner.scan(
            environment=Environment.PRODUCTION,
            target_resources=["default/api-server"],
        )

    # Should still complete (scan_cves handles source errors gracefully)
    assert isinstance(result, SecurityScanState)
    assert result.current_step == "complete"
    assert len(result.cve_findings) == 0  # no findings from broken source


@pytest.mark.asyncio
async def test_security_scan_default_no_actions(
    mock_connector_router,
    mock_policy_engine,
    mock_cve_source,
    mock_credential_store,
    security_llm_responses,
):
    """Default execute_actions=False skips the entire action phase."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return security_llm_responses[schema]

    with patch("shieldops.agents.security.nodes.llm_structured", side_effect=fake_llm):
        runner = SecurityRunner(
            connector_router=mock_connector_router,
            cve_sources=[mock_cve_source],
            credential_stores=[mock_credential_store],
            policy_engine=mock_policy_engine,
        )

        result = await runner.scan(
            environment=Environment.PRODUCTION,
            scan_type="full",
            target_resources=["default/api-server"],
            # execute_actions omitted — defaults to False
        )

    assert result.error is None
    assert result.current_step == "complete"
    # Action phase should not have run at all
    assert result.action_policy_result is None
    assert result.patches_applied == 0
    assert result.credentials_rotated == 0
    # But the policy engine's evaluate should NOT have been called
    # (action phase was skipped entirely)
    mock_policy_engine.evaluate.assert_not_called()
