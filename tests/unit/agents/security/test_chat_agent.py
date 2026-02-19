"""Tests for SecurityChatAgent — conversational AI for security operations.

Covers:
- Agent initialization with optional dependencies
- Intent classification for all keyword groups
- Tool dispatch: query_vulnerabilities, get_remediation_steps, run_scan,
  assign_vulnerability, get_security_posture
- OPA policy gating on scan actions (allow, deny, error)
- Context awareness (selected vulnerability, fallback to context)
- Error handling in each tool path
- Fallback text generation when LLM is unavailable
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from shieldops.agents.security.chat import SecurityChatAgent

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_repository() -> AsyncMock:
    repo = AsyncMock()
    repo.get_vulnerability_stats = AsyncMock(
        return_value={
            "total": 42,
            "by_severity": {"critical": 5, "high": 12},
            "sla_breaches": 3,
        }
    )
    repo.list_vulnerabilities = AsyncMock(
        return_value=[
            {
                "id": "vuln-abc",
                "cve_id": "CVE-2024-1234",
                "severity": "critical",
                "remediation_steps": ["Upgrade openssl"],
            },
        ]
    )
    repo.assign_vulnerability = AsyncMock(return_value=True)
    repo.list_teams = AsyncMock(
        return_value=[
            {"id": "team-sec", "name": "Security"},
            {"id": "team-infra", "name": "Infrastructure"},
        ]
    )
    return repo


@pytest.fixture()
def mock_security_runner() -> AsyncMock:
    runner = AsyncMock()
    runner.scan = AsyncMock(
        return_value=SimpleNamespace(
            scan_id="scan-001",
            cve_findings=[{"cve_id": "CVE-2024-9999"}],
        )
    )
    return runner


@pytest.fixture()
def mock_policy_engine() -> AsyncMock:
    engine = AsyncMock()
    engine.evaluate = AsyncMock(
        return_value=SimpleNamespace(
            allowed=True,
            reasons=[],
        )
    )
    return engine


@pytest.fixture()
def agent(mock_repository, mock_security_runner, mock_policy_engine) -> SecurityChatAgent:
    return SecurityChatAgent(
        repository=mock_repository,
        security_runner=mock_security_runner,
        policy_engine=mock_policy_engine,
    )


@pytest.fixture()
def agent_no_deps() -> SecurityChatAgent:
    """Agent with no repository, runner, or policy engine."""
    return SecurityChatAgent()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSecurityChatAgentInit:
    """Verify construction with various dependency combinations."""

    def test_init_with_all_deps(self, agent: SecurityChatAgent):
        assert agent._repository is not None
        assert agent._security_runner is not None
        assert agent._policy_engine is not None

    def test_init_with_no_deps(self, agent_no_deps: SecurityChatAgent):
        assert agent_no_deps._repository is None
        assert agent_no_deps._security_runner is None
        assert agent_no_deps._policy_engine is None


class TestIntentClassification:
    """Keyword-based intent classification."""

    @pytest.mark.parametrize(
        "message,expected",
        [
            ("run scan on production", "run_scan"),
            ("trigger scan", "run_scan"),
            ("please scan containers", "run_scan"),
            ("assign vuln-abc to team: security", "assign_vulnerability"),
            ("reassign CVE-2024-1234", "assign_vulnerability"),
            ("how to fix CVE-2024-1234", "remediation_guidance"),
            ("remediation for openssl", "remediation_guidance"),
            ("patch CVE-2024-9999", "remediation_guidance"),
            ("show me the posture overview", "posture_overview"),
            ("security score summary", "posture_overview"),
            ("what is the current status", "posture_overview"),
            ("list all vulnerabilities", "query_vulnerabilities"),
            ("what happened yesterday", "query_vulnerabilities"),
        ],
    )
    def test_classify_intent(self, agent: SecurityChatAgent, message: str, expected: str):
        assert agent._classify_intent(message) == expected

    def test_classify_intent_case_insensitive(self, agent: SecurityChatAgent):
        assert agent._classify_intent("RUN SCAN now") == "run_scan"


class TestToolQueryVulnerabilities:
    """Tests for _tool_query_vulnerabilities."""

    @pytest.mark.asyncio
    async def test_queries_repo_with_severity_filter(
        self, agent: SecurityChatAgent, mock_repository: AsyncMock
    ):
        result = await agent._tool_query_vulnerabilities("show critical vulns", {})
        mock_repository.list_vulnerabilities.assert_awaited_with(severity="critical", limit=10)
        assert result["source"] == "vulnerability_db"
        assert "stats" in result["data"]

    @pytest.mark.asyncio
    async def test_queries_repo_no_severity(
        self, agent: SecurityChatAgent, mock_repository: AsyncMock
    ):
        await agent._tool_query_vulnerabilities("show all vulns", {})
        mock_repository.list_vulnerabilities.assert_awaited_with(severity=None, limit=10)

    @pytest.mark.asyncio
    async def test_falls_back_to_context_when_no_repo(self, agent_no_deps: SecurityChatAgent):
        ctx = {"vulnerability_stats": {"total": 10}}
        result = await agent_no_deps._tool_query_vulnerabilities("show vulns", ctx)
        assert result["source"] == "context"
        assert result["data"] == {"total": 10}

    @pytest.mark.asyncio
    async def test_handles_repo_exception(
        self, agent: SecurityChatAgent, mock_repository: AsyncMock
    ):
        mock_repository.get_vulnerability_stats.side_effect = RuntimeError("DB down")
        result = await agent._tool_query_vulnerabilities("list vulns", {})
        assert "error" in result


class TestToolGetRemediation:
    """Tests for _tool_get_remediation."""

    @pytest.mark.asyncio
    async def test_returns_specific_cve_remediation(
        self, agent: SecurityChatAgent, mock_repository: AsyncMock
    ):
        result = await agent._tool_get_remediation("fix CVE-2024-1234", {})
        assert result["data"]["cve_id"] == "CVE-2024-1234"
        assert result["source"] == "vulnerability_db"

    @pytest.mark.asyncio
    async def test_falls_back_to_context_critical_vuln(self, agent_no_deps: SecurityChatAgent):
        ctx = {
            "critical_vulnerabilities": [
                {"id": "vuln-x", "remediation_steps": ["Step 1"]},
            ]
        }
        result = await agent_no_deps._tool_get_remediation("how to remediate", ctx)
        assert result["source"] == "context"
        assert result["data"]["vulnerability"]["id"] == "vuln-x"

    @pytest.mark.asyncio
    async def test_returns_no_match_message(self, agent_no_deps: SecurityChatAgent):
        result = await agent_no_deps._tool_get_remediation("fix something", {})
        assert result["source"] == "none"
        assert "No specific vulnerability" in result["data"]["message"]

    @pytest.mark.asyncio
    async def test_handles_repo_exception_during_lookup(
        self, agent: SecurityChatAgent, mock_repository: AsyncMock
    ):
        mock_repository.list_vulnerabilities.side_effect = RuntimeError("timeout")
        result = await agent._tool_get_remediation("fix CVE-2024-1234", {})
        assert "error" in result


class TestToolRunScan:
    """Tests for _tool_run_scan including OPA policy gating."""

    @pytest.mark.asyncio
    async def test_triggers_scan_when_policy_allows(
        self, agent: SecurityChatAgent, mock_security_runner: AsyncMock
    ):
        result = await agent._tool_run_scan("run scan", "user-1")
        assert result["scan_id"] == "scan-001"
        assert result["source"] == "security_runner"
        mock_security_runner.scan.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_scan_denied_by_policy(
        self, agent: SecurityChatAgent, mock_policy_engine: AsyncMock
    ):
        mock_policy_engine.evaluate.return_value = SimpleNamespace(
            allowed=False, reasons=["Restricted environment"]
        )
        result = await agent._tool_run_scan("run scan", "user-1")
        assert "error" in result
        assert "denied by policy" in result["error"]

    @pytest.mark.asyncio
    async def test_scan_fails_closed_on_policy_error(
        self, agent: SecurityChatAgent, mock_policy_engine: AsyncMock
    ):
        mock_policy_engine.evaluate.side_effect = RuntimeError("OPA unreachable")
        result = await agent._tool_run_scan("run scan", "user-1")
        assert "error" in result
        assert "Policy check failed" in result["error"]

    @pytest.mark.asyncio
    async def test_scan_type_detected_from_message(
        self, agent: SecurityChatAgent, mock_security_runner: AsyncMock
    ):
        await agent._tool_run_scan("scan containers", "user-1")
        call_kwargs = mock_security_runner.scan.call_args.kwargs
        assert call_kwargs["scan_type"] == "container"

    @pytest.mark.asyncio
    async def test_returns_error_when_no_runner(self, agent_no_deps: SecurityChatAgent):
        result = await agent_no_deps._tool_run_scan("run scan", "user-1")
        assert result["error"] == "Security scanner not configured"


class TestToolAssign:
    """Tests for _tool_assign."""

    @pytest.mark.asyncio
    async def test_assigns_vuln_with_team(
        self, agent: SecurityChatAgent, mock_repository: AsyncMock
    ):
        result = await agent._tool_assign("assign vuln-abc team: Security", {}, "user-1")
        assert result["assigned"] is True
        assert result["vulnerability_id"] == "vuln-abc"
        assert result["team_id"] == "team-sec"

    @pytest.mark.asyncio
    async def test_returns_error_when_no_vuln_id(self, agent: SecurityChatAgent):
        result = await agent._tool_assign("assign to team: Security", {}, "user-1")
        assert "error" in result
        assert "Could not identify" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_error_when_no_repo(self, agent_no_deps: SecurityChatAgent):
        result = await agent_no_deps._tool_assign("assign vuln-abc", {}, "user-1")
        assert result["error"] == "Repository not configured"


class TestToolGetPosture:
    """Tests for _tool_get_posture."""

    @pytest.mark.asyncio
    async def test_returns_live_data_from_repo(
        self, agent: SecurityChatAgent, mock_repository: AsyncMock
    ):
        result = await agent._tool_get_posture({})
        assert result["source"] == "posture_analysis"
        assert "stats" in result["data"]
        mock_repository.get_vulnerability_stats.assert_awaited()

    @pytest.mark.asyncio
    async def test_falls_back_to_context(self, agent_no_deps: SecurityChatAgent):
        ctx = {"vulnerability_stats": {"total": 5}, "sla_breaches": [{"id": "v1"}]}
        result = await agent_no_deps._tool_get_posture(ctx)
        assert result["data"]["stats"]["total"] == 5
        assert len(result["data"]["sla_breaches"]) == 1


class TestRespondEndToEnd:
    """Integration-level tests for the public respond() method."""

    @pytest.mark.asyncio
    async def test_respond_query_returns_expected_structure(self, agent: SecurityChatAgent):
        with patch.object(agent, "_generate_response", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "Here are your vulnerabilities."
            result = await agent.respond("show critical vulns", user_id="user-1")

        assert "response" in result
        assert "actions" in result
        assert "sources" in result

    @pytest.mark.asyncio
    async def test_respond_scan_includes_action(self, agent: SecurityChatAgent):
        with patch.object(agent, "_generate_response", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "Scan started."
            result = await agent.respond("run scan", user_id="user-1")

        assert any(a["type"] == "scan_started" for a in result["actions"])

    @pytest.mark.asyncio
    async def test_respond_uses_history_and_context(self, agent: SecurityChatAgent):
        with patch.object(agent, "_generate_response", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "OK"
            history = [{"role": "user", "content": "hello"}]
            context = {"vulnerability_stats": {"total": 10}}
            await agent.respond("show posture", history=history, context=context, user_id="u1")
            call_args = mock_gen.call_args
            assert call_args[0][1] == history  # history passed through


class TestFallbackText:
    """Tests for _fallback_text when LLM is unavailable."""

    def test_fallback_with_error(self, agent: SecurityChatAgent):
        result = agent._fallback_text([{"error": "DB down"}])
        assert "I encountered an issue" in result

    def test_fallback_with_stats(self, agent: SecurityChatAgent):
        result = agent._fallback_text(
            [
                {
                    "data": {
                        "stats": {"total": 42, "by_severity": {"critical": 5}, "sla_breaches": 3}
                    },
                }
            ]
        )
        assert "42" in result
        assert "security overview" in result.lower()

    def test_fallback_default(self, agent: SecurityChatAgent):
        result = agent._fallback_text([])
        assert "ready to help" in result.lower()
