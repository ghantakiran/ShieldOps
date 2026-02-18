"""Comprehensive tests for the Investigation Agent.

Tests cover:
- InvestigationToolkit (tools.py)
- Node functions (nodes.py)
- Graph construction and routing (graph.py)
- InvestigationRunner (runner.py)
- API endpoints (routes/investigations.py)
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.agents.investigation.models import (
    CorrelatedEvent,
    InvestigationState,
    LogFinding,
    MetricAnomaly,
    ReasoningStep,
    TraceResult,
)
from shieldops.agents.investigation.prompts import (
    CorrelationResult,
    HypothesesOutput,
    HypothesisResult,
    LogAnalysisResult,
    MetricAnalysisResult,
    RecommendedActionOutput,
)
from shieldops.agents.investigation.tools import InvestigationToolkit
from shieldops.models.base import AlertContext, Hypothesis, RiskLevel

# --- Fixtures ---


@pytest.fixture
def alert_context():
    return AlertContext(
        alert_id="alert-test-001",
        alert_name="KubePodCrashLooping",
        severity="critical",
        source="prometheus",
        resource_id="default/api-server",
        labels={"app": "api", "environment": "production"},
        triggered_at=datetime.now(UTC),
        description="Pod api-server has restarted 15 times in the last hour",
    )


@pytest.fixture
def investigation_state(alert_context):
    return InvestigationState(
        alert_id=alert_context.alert_id,
        alert_context=alert_context,
        investigation_start=datetime.now(UTC),
    )


@pytest.fixture
def state_with_findings(investigation_state):
    """State populated with findings from earlier pipeline stages."""
    investigation_state.log_findings = [
        LogFinding(
            source="kubernetes",
            query="default/api-server",
            summary="OOMKilled: container exceeded memory limit",
            severity="error",
            sample_entries=["OOMKilled", "Exit code 137"],
            count=15,
        ),
    ]
    investigation_state.metric_anomalies = [
        MetricAnomaly(
            metric_name="container_memory_usage_bytes",
            source="prometheus",
            current_value=1073741824,
            baseline_value=536870912,
            deviation_percent=100.0,
            started_at=datetime.now(UTC),
            labels={"namespace": "default", "pod": "api-server"},
        ),
    ]
    investigation_state.correlated_events = [
        CorrelatedEvent(
            timestamp=datetime.now(UTC),
            source="cross-correlation",
            event_type="correlated",
            description="Memory spike at 14:30 correlates with OOMKill at 14:31",
            correlation_score=0.9,
        ),
    ]
    investigation_state.reasoning_chain = [
        ReasoningStep(
            step_number=1,
            action="gather_context",
            input_summary="Alert: KubePodCrashLooping",
            output_summary="Resource health: CrashLoopBackOff",
            duration_ms=50,
            tool_used="k8s_connector",
        ),
        ReasoningStep(
            step_number=2,
            action="analyze_logs",
            input_summary="Querying logs",
            output_summary="15 OOMKilled errors",
            duration_ms=200,
            tool_used="query_logs + llm",
        ),
        ReasoningStep(
            step_number=3,
            action="analyze_metrics",
            input_summary="Checking 4 metrics",
            output_summary="Memory at 100% deviation",
            duration_ms=150,
            tool_used="query_metrics + llm",
        ),
        ReasoningStep(
            step_number=4,
            action="correlate_findings",
            input_summary="Correlating findings",
            output_summary="Memory spike causes OOMKill",
            duration_ms=300,
            tool_used="llm",
        ),
    ]
    return investigation_state


@pytest.fixture
def state_with_hypotheses(state_with_findings):
    """State with hypotheses generated (for recommend_action testing)."""
    state_with_findings.hypotheses = [
        Hypothesis(
            id="hyp-test-1",
            description="Memory leak in api-server causing OOM kills",
            confidence=0.92,
            evidence=["OOMKilled 15 times", "Memory usage at 100% deviation"],
            affected_resources=["default/api-server"],
            recommended_action="increase_memory_limit",
            reasoning_chain=["Logs show OOMKilled", "Memory doubled vs baseline"],
        ),
        Hypothesis(
            id="hyp-test-2",
            description="Increased traffic causing resource exhaustion",
            confidence=0.45,
            evidence=["Network bytes elevated"],
            affected_resources=["default/api-server"],
            recommended_action="scale_horizontal",
            reasoning_chain=["Network traffic up"],
        ),
    ]
    state_with_findings.confidence_score = 0.92
    state_with_findings.reasoning_chain.append(
        ReasoningStep(
            step_number=5,
            action="generate_hypotheses",
            input_summary="Synthesizing findings",
            output_summary="2 hypotheses, top: memory leak (0.92)",
            duration_ms=500,
            tool_used="llm",
        ),
    )
    return state_with_findings


@pytest.fixture
def mock_log_source():
    source = AsyncMock()
    source.source_name = "kubernetes"
    source.query_logs = AsyncMock(
        return_value=[
            {"timestamp": "2025-01-01T00:00:00Z", "message": "ERROR OOMKilled", "level": "error"},
            {"timestamp": "2025-01-01T00:00:01Z", "message": "INFO Starting", "level": "info"},
        ]
    )
    source.search_patterns = AsyncMock(
        return_value={
            "error": [{"message": "ERROR OOMKilled"}],
            "OOMKilled": [{"message": "ERROR OOMKilled"}],
        }
    )
    return source


@pytest.fixture
def mock_metric_source():
    source = AsyncMock()
    source.source_name = "prometheus"
    source.query_instant = AsyncMock(return_value=[{"value": 1073741824}])
    source.detect_anomalies = AsyncMock(
        return_value=[
            {
                "metric_name": "container_memory_usage_bytes",
                "current_value": 1073741824,
                "baseline_value": 536870912,
                "deviation_percent": 100.0,
                "labels": {"namespace": "default", "pod": "api-server"},
            },
        ]
    )
    return source


@pytest.fixture
def mock_connector_router():
    router = MagicMock()
    connector = AsyncMock()
    connector.get_events = AsyncMock(
        return_value=[
            {"reason": "OOMKilling", "message": "Memory cgroup out of memory"},
        ]
    )
    connector.get_health = AsyncMock(
        return_value=MagicMock(
            model_dump=lambda: {
                "healthy": False,
                "status": "CrashLoopBackOff",
                "message": "Restarting",
            }
        )
    )
    router.get = MagicMock(return_value=connector)
    return router


# ============================================================================
# InvestigationToolkit tests
# ============================================================================


class TestInvestigationToolkit:
    @pytest.mark.asyncio
    async def test_query_logs_aggregates_sources(self, mock_log_source):
        toolkit = InvestigationToolkit(log_sources=[mock_log_source])
        result = await toolkit.query_logs("default/api-server")

        assert result["total_entries"] == 2
        assert result["error_count"] == 1
        assert result["sources_queried"] == ["kubernetes"]
        mock_log_source.query_logs.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_query_logs_with_patterns(self, mock_log_source):
        toolkit = InvestigationToolkit(log_sources=[mock_log_source])
        result = await toolkit.query_logs("default/api-server", patterns=["error", "OOMKilled"])

        assert "error" in result["pattern_matches"]
        assert "OOMKilled" in result["pattern_matches"]
        mock_log_source.search_patterns.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_query_logs_no_sources(self):
        toolkit = InvestigationToolkit()
        result = await toolkit.query_logs("default/api-server")

        assert result["total_entries"] == 0
        assert result["sources_queried"] == []

    @pytest.mark.asyncio
    async def test_query_logs_source_failure_handled(self):
        source = AsyncMock()
        source.source_name = "failing"
        source.query_logs = AsyncMock(side_effect=ConnectionError("Timeout"))
        toolkit = InvestigationToolkit(log_sources=[source])

        result = await toolkit.query_logs("default/pod")
        assert result["total_entries"] == 0  # Graceful fallback

    @pytest.mark.asyncio
    async def test_query_metrics_aggregates(self, mock_metric_source):
        toolkit = InvestigationToolkit(metric_sources=[mock_metric_source])
        result = await toolkit.query_metrics("default/api-server")

        assert result["anomaly_count"] > 0
        assert "container_cpu_usage_seconds_total" in result["metrics_checked"]
        assert result["sources_queried"] == ["prometheus"]

    @pytest.mark.asyncio
    async def test_query_metrics_custom_names(self, mock_metric_source):
        toolkit = InvestigationToolkit(metric_sources=[mock_metric_source])
        result = await toolkit.query_metrics("default/api-server", metric_names=["custom_metric"])

        assert result["metrics_checked"] == ["custom_metric"]

    @pytest.mark.asyncio
    async def test_query_traces_with_bottleneck(self):
        trace_source = AsyncMock()
        trace_source.source_name = "jaeger"
        trace_source.search_traces = AsyncMock(return_value=[])
        trace_source.find_bottleneck = AsyncMock(
            return_value={
                "trace_id": "abc123",
                "service": "db-service",
                "duration_ms": 5000,
            }
        )

        toolkit = InvestigationToolkit(trace_sources=[trace_source])
        result = await toolkit.query_traces("api-service")

        assert result["bottleneck"]["service"] == "db-service"
        assert result["sources_queried"] == ["jaeger"]

    @pytest.mark.asyncio
    async def test_get_k8s_events_no_router(self):
        toolkit = InvestigationToolkit()
        result = await toolkit.get_k8s_events("default/pod")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_k8s_events(self, mock_connector_router):
        toolkit = InvestigationToolkit(connector_router=mock_connector_router)
        result = await toolkit.get_k8s_events("default/api-server")

        assert len(result) == 1
        assert result[0]["reason"] == "OOMKilling"

    @pytest.mark.asyncio
    async def test_get_resource_health(self, mock_connector_router):
        toolkit = InvestigationToolkit(connector_router=mock_connector_router)
        result = await toolkit.get_resource_health("default/api-server")

        assert result["healthy"] is False
        assert result["status"] == "CrashLoopBackOff"

    @pytest.mark.asyncio
    async def test_get_resource_health_no_router(self):
        toolkit = InvestigationToolkit()
        result = await toolkit.get_resource_health("default/pod")
        assert result["healthy"] is None

    def test_labels_from_resource_id_with_namespace(self):
        labels = InvestigationToolkit._labels_from_resource_id("default/api-server")
        assert labels == {"namespace": "default", "pod": "api-server"}

    def test_labels_from_resource_id_without_namespace(self):
        labels = InvestigationToolkit._labels_from_resource_id("api-server")
        assert labels == {"pod": "api-server"}

    def test_format_labels(self):
        result = InvestigationToolkit._format_labels({"namespace": "default", "pod": "api-server"})
        assert 'namespace="default"' in result
        assert 'pod="api-server"' in result


# ============================================================================
# Node tests
# ============================================================================


class TestGatherContextNode:
    @pytest.mark.asyncio
    async def test_gather_context(self, investigation_state):
        from shieldops.agents.investigation.nodes import gather_context, set_toolkit

        toolkit = InvestigationToolkit()  # Empty toolkit
        set_toolkit(toolkit)

        result = await gather_context(investigation_state)

        assert result["current_step"] == "gather_context"
        assert result["investigation_start"] is not None
        assert len(result["reasoning_chain"]) == 1
        assert result["reasoning_chain"][0].action == "gather_context"

        # Cleanup
        set_toolkit(None)


class TestAnalyzeLogsNode:
    @pytest.mark.asyncio
    async def test_analyze_logs_empty_sources(self, investigation_state):
        """With no log sources, should produce empty findings gracefully."""
        from shieldops.agents.investigation.nodes import analyze_logs, set_toolkit

        toolkit = InvestigationToolkit()
        set_toolkit(toolkit)

        investigation_state.reasoning_chain = [
            ReasoningStep(
                step_number=1,
                action="gather_context",
                input_summary="",
                output_summary="",
                duration_ms=0,
            ),
        ]
        result = await analyze_logs(investigation_state)

        assert result["current_step"] == "analyze_logs"
        assert len(result["log_findings"]) == 0

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_analyze_logs_with_data(self, investigation_state, mock_log_source):
        """With log data, should call LLM and produce findings."""
        from shieldops.agents.investigation.nodes import analyze_logs, set_toolkit

        toolkit = InvestigationToolkit(log_sources=[mock_log_source])
        set_toolkit(toolkit)

        investigation_state.reasoning_chain = [
            ReasoningStep(
                step_number=1,
                action="gather_context",
                input_summary="",
                output_summary="",
                duration_ms=0,
            ),
        ]

        mock_llm_result = LogAnalysisResult(
            summary="OOM kills detected",
            error_patterns=["OOMKilled: container exceeded memory limit"],
            severity="error",
            root_cause_hints=["Memory leak"],
            affected_services=["api-server"],
        )

        with patch(
            "shieldops.agents.investigation.nodes.llm_structured",
            new_callable=AsyncMock,
            return_value=mock_llm_result,
        ):
            result = await analyze_logs(investigation_state)

        assert len(result["log_findings"]) == 1
        assert result["log_findings"][0].severity == "error"

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_analyze_logs_llm_failure_fallback(self, investigation_state, mock_log_source):
        """When LLM fails, should fall back to raw data analysis."""
        from shieldops.agents.investigation.nodes import analyze_logs, set_toolkit

        toolkit = InvestigationToolkit(log_sources=[mock_log_source])
        set_toolkit(toolkit)

        investigation_state.reasoning_chain = [
            ReasoningStep(
                step_number=1,
                action="gather_context",
                input_summary="",
                output_summary="",
                duration_ms=0,
            ),
        ]

        with patch(
            "shieldops.agents.investigation.nodes.llm_structured",
            new_callable=AsyncMock,
            side_effect=Exception("LLM unavailable"),
        ):
            result = await analyze_logs(investigation_state)

        # Should still produce findings from raw error data
        assert len(result["log_findings"]) == 1
        assert (
            "error" in result["log_findings"][0].summary.lower()
            or result["log_findings"][0].severity == "error"
        )

        set_toolkit(None)


class TestAnalyzeMetricsNode:
    @pytest.mark.asyncio
    async def test_analyze_metrics_with_anomalies(self, investigation_state, mock_metric_source):
        from shieldops.agents.investigation.nodes import analyze_metrics, set_toolkit

        toolkit = InvestigationToolkit(metric_sources=[mock_metric_source])
        set_toolkit(toolkit)

        investigation_state.reasoning_chain = [
            ReasoningStep(
                step_number=1,
                action="gather_context",
                input_summary="",
                output_summary="",
                duration_ms=0,
            ),
            ReasoningStep(
                step_number=2,
                action="analyze_logs",
                input_summary="",
                output_summary="",
                duration_ms=0,
            ),
        ]

        mock_result = MetricAnalysisResult(
            summary="Memory usage critically high",
            anomalies_detected=["Memory at 100% deviation"],
            resource_pressure="critical",
            likely_bottleneck="memory",
        )

        with patch(
            "shieldops.agents.investigation.nodes.llm_structured",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await analyze_metrics(investigation_state)

        assert result["current_step"] == "analyze_metrics"
        assert len(result["metric_anomalies"]) > 0

        set_toolkit(None)


class TestCorrelateFindings:
    @pytest.mark.asyncio
    async def test_correlate_with_findings(self, state_with_findings):
        from shieldops.agents.investigation.nodes import correlate_findings

        mock_result = CorrelationResult(
            timeline=["14:30 Memory spike", "14:31 OOMKill"],
            causal_chain="Memory leak caused OOM which caused pod restart",
            correlated_events=["Memory spike → OOMKill → CrashLoopBackOff"],
            key_evidence=["Memory at 100% deviation", "15 OOMKills"],
        )

        with patch(
            "shieldops.agents.investigation.nodes.llm_structured",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await correlate_findings(state_with_findings)

        assert len(result["correlated_events"]) == 1
        assert result["current_step"] == "correlate_findings"

    @pytest.mark.asyncio
    async def test_correlate_no_findings(self, investigation_state):
        from shieldops.agents.investigation.nodes import correlate_findings

        investigation_state.reasoning_chain = [
            ReasoningStep(
                step_number=1, action="test", input_summary="", output_summary="", duration_ms=0
            ),
        ]

        result = await correlate_findings(investigation_state)
        assert len(result["correlated_events"]) == 0


class TestGenerateHypotheses:
    @pytest.mark.asyncio
    async def test_generate_hypotheses(self, state_with_findings):
        from shieldops.agents.investigation.nodes import generate_hypotheses

        mock_result = HypothesesOutput(
            hypotheses=[
                HypothesisResult(
                    description="Memory leak causing OOM kills",
                    confidence=0.92,
                    evidence=["OOMKilled 15 times", "Memory at 100% deviation"],
                    affected_resources=["default/api-server"],
                    recommended_action="increase_memory_limit",
                    reasoning=["Logs show OOMKilled", "Memory doubled"],
                ),
            ]
        )

        with patch(
            "shieldops.agents.investigation.nodes.llm_structured",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await generate_hypotheses(state_with_findings)

        assert len(result["hypotheses"]) == 1
        assert result["confidence_score"] == 0.92
        assert result["hypotheses"][0].id.startswith("hyp-")

    @pytest.mark.asyncio
    async def test_generate_hypotheses_llm_failure(self, state_with_findings):
        from shieldops.agents.investigation.nodes import generate_hypotheses

        with patch(
            "shieldops.agents.investigation.nodes.llm_structured",
            new_callable=AsyncMock,
            side_effect=Exception("LLM down"),
        ):
            result = await generate_hypotheses(state_with_findings)

        assert len(result["hypotheses"]) == 0
        assert result["confidence_score"] == 0.0


# ============================================================================
# Graph routing tests
# ============================================================================


class TestGraphRouting:
    def test_should_analyze_traces_on_timeout(self, investigation_state):
        from shieldops.agents.investigation.graph import should_analyze_traces

        investigation_state.log_findings = [
            LogFinding(
                source="kubernetes",
                query="",
                summary="Connection timeout to db",
                severity="error",
                count=5,
            ),
        ]
        assert should_analyze_traces(investigation_state) == "analyze_traces"

    def test_should_skip_traces_on_non_distributed(self, investigation_state):
        from shieldops.agents.investigation.graph import should_analyze_traces

        investigation_state.log_findings = [
            LogFinding(
                source="kubernetes",
                query="",
                summary="OOMKilled",
                severity="error",
                count=5,
            ),
        ]
        assert should_analyze_traces(investigation_state) == "correlate_findings"

    def test_should_skip_traces_on_error(self, investigation_state):
        from shieldops.agents.investigation.graph import should_analyze_traces

        investigation_state.error = "Something failed"
        assert should_analyze_traces(investigation_state) == "generate_hypotheses"

    def test_should_recommend_high_confidence(self, state_with_hypotheses):
        from shieldops.agents.investigation.graph import should_recommend_action

        assert should_recommend_action(state_with_hypotheses) == "recommend_action"

    def test_should_not_recommend_low_confidence(self, investigation_state):
        from shieldops.agents.investigation.graph import should_recommend_action

        investigation_state.confidence_score = 0.3
        assert should_recommend_action(investigation_state) == "__end__"


class TestRecommendActionNode:
    @pytest.mark.asyncio
    async def test_recommend_action_with_hypothesis(self, state_with_hypotheses):
        from shieldops.agents.investigation.graph import recommend_action

        mock_result = RecommendedActionOutput(
            action_type="increase_memory_limit",
            target_resource="default/api-server",
            description="Increase memory limit from 512Mi to 1Gi",
            risk_level="low",
            parameters={"memory_limit": "1Gi"},
            estimated_duration_seconds=30,
        )

        with patch(
            "shieldops.agents.investigation.graph.llm_structured",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await recommend_action(state_with_hypotheses)

        assert result["recommended_action"] is not None
        assert result["recommended_action"].action_type == "increase_memory_limit"
        assert result["recommended_action"].risk_level == RiskLevel.LOW
        assert result["current_step"] == "complete"

    @pytest.mark.asyncio
    async def test_recommend_action_llm_failure(self, state_with_hypotheses):
        from shieldops.agents.investigation.graph import recommend_action

        with patch(
            "shieldops.agents.investigation.graph.llm_structured",
            new_callable=AsyncMock,
            side_effect=Exception("LLM error"),
        ):
            result = await recommend_action(state_with_hypotheses)

        assert result["recommended_action"] is None
        assert result["current_step"] == "complete"

    @pytest.mark.asyncio
    async def test_recommend_action_no_hypotheses(self, investigation_state):
        from shieldops.agents.investigation.graph import recommend_action

        investigation_state.investigation_start = datetime.now(UTC)
        result = await recommend_action(investigation_state)

        assert result["recommended_action"] is None
        assert result["current_step"] == "complete"


class TestGraphConstruction:
    def test_create_investigation_graph(self):
        from shieldops.agents.investigation.graph import create_investigation_graph

        graph = create_investigation_graph()
        assert graph is not None

        compiled = graph.compile()
        assert compiled is not None


# ============================================================================
# Runner tests
# ============================================================================


class TestInvestigationRunner:
    def test_runner_init(self):
        from shieldops.agents.investigation.runner import InvestigationRunner

        runner = InvestigationRunner()
        assert runner._investigations == {}

    @pytest.mark.asyncio
    async def test_investigate_returns_state(self, alert_context):
        from shieldops.agents.investigation.runner import InvestigationRunner

        runner = InvestigationRunner()

        # Mock the compiled graph's ainvoke to return a valid state dict
        mock_state = InvestigationState(
            alert_id=alert_context.alert_id,
            alert_context=alert_context,
            investigation_start=datetime.now(UTC),
            current_step="complete",
            confidence_score=0.85,
            hypotheses=[
                Hypothesis(
                    id="hyp-1",
                    description="Test hypothesis",
                    confidence=0.85,
                    evidence=["Evidence 1"],
                    affected_resources=["default/api-server"],
                    reasoning_chain=["Step 1"],
                ),
            ],
        )
        runner._app = AsyncMock()
        runner._app.ainvoke = AsyncMock(return_value=mock_state.model_dump())

        result = await runner.investigate(alert_context)

        assert result.alert_id == alert_context.alert_id
        assert result.current_step == "complete"
        assert len(runner._investigations) == 1

    @pytest.mark.asyncio
    async def test_investigate_handles_error(self, alert_context):
        from shieldops.agents.investigation.runner import InvestigationRunner

        runner = InvestigationRunner()
        runner._app = AsyncMock()
        runner._app.ainvoke = AsyncMock(side_effect=RuntimeError("Graph exploded"))

        result = await runner.investigate(alert_context)

        assert result.error == "Graph exploded"
        assert result.current_step == "failed"
        assert len(runner._investigations) == 1

    def test_list_investigations_empty(self):
        from shieldops.agents.investigation.runner import InvestigationRunner

        runner = InvestigationRunner()
        assert runner.list_investigations() == []

    def test_get_investigation_not_found(self):
        from shieldops.agents.investigation.runner import InvestigationRunner

        runner = InvestigationRunner()
        assert runner.get_investigation("nonexistent") is None


# ============================================================================
# API endpoint tests
# ============================================================================


class TestInvestigationAPI:
    @pytest.fixture
    def mock_runner(self, alert_context):
        from shieldops.agents.investigation.runner import InvestigationRunner

        runner = MagicMock(spec=InvestigationRunner)
        runner.list_investigations.return_value = [
            {
                "investigation_id": "inv-abc123",
                "alert_id": "alert-001",
                "alert_name": "TestAlert",
                "status": "complete",
                "confidence": 0.85,
                "hypotheses_count": 2,
                "duration_ms": 5000,
                "error": None,
            },
        ]
        runner.get_investigation.return_value = InvestigationState(
            alert_id="alert-001",
            alert_context=alert_context,
            current_step="complete",
            confidence_score=0.85,
        )
        runner.investigate = AsyncMock(
            return_value=InvestigationState(
                alert_id="alert-001",
                alert_context=alert_context,
                current_step="complete",
            )
        )
        return runner

    @pytest.fixture
    async def client(self, mock_runner):
        from httpx import ASGITransport, AsyncClient

        from shieldops.api.app import create_app
        from shieldops.api.routes.investigations import set_runner

        set_runner(mock_runner)
        app = create_app()

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole

        def _mock_admin_user():
            return UserResponse(
                id="test-admin",
                email="admin@test.com",
                name="Test Admin",
                role=UserRole.ADMIN,
                is_active=True,
            )

        app.dependency_overrides[get_current_user] = _mock_admin_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

        set_runner(None)

    @pytest.mark.asyncio
    async def test_list_investigations(self, client):
        response = await client.get("/api/v1/investigations")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["investigations"][0]["investigation_id"] == "inv-abc123"

    @pytest.mark.asyncio
    async def test_list_investigations_with_filter(self, client, mock_runner):
        response = await client.get("/api/v1/investigations?status=complete")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_list_investigations_filter_no_match(self, client, mock_runner):
        response = await client.get("/api/v1/investigations?status=in_progress")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_investigation_found(self, client, mock_runner):
        mock_runner.get_investigation.return_value = InvestigationState(
            alert_id="alert-001",
            alert_context=AlertContext(
                alert_id="alert-001",
                alert_name="Test",
                severity="warning",
                source="test",
                triggered_at=datetime.now(UTC),
            ),
            current_step="complete",
        )
        response = await client.get("/api/v1/investigations/inv-abc123")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_investigation_not_found(self, client, mock_runner):
        mock_runner.get_investigation.return_value = None
        response = await client.get("/api/v1/investigations/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_trigger_investigation_async(self, client):
        response = await client.post(
            "/api/v1/investigations",
            json={
                "alert_id": "alert-new-001",
                "alert_name": "HighLatency",
                "severity": "warning",
                "resource_id": "default/web-server",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["alert_id"] == "alert-new-001"

    @pytest.mark.asyncio
    async def test_trigger_investigation_sync(self, client):
        response = await client.post(
            "/api/v1/investigations/sync",
            json={
                "alert_id": "alert-sync-001",
                "alert_name": "PodCrashLoop",
                "severity": "critical",
                "source": "prometheus",
                "resource_id": "default/api-server",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["alert_id"] == "alert-001"  # From mock


# ============================================================================
# Investigation models tests
# ============================================================================


class TestInvestigationModels:
    def test_log_finding(self):
        finding = LogFinding(
            source="kubernetes",
            query="default/api-server",
            summary="OOMKilled",
            severity="error",
            count=5,
        )
        assert finding.severity == "error"
        assert finding.sample_entries == []

    def test_metric_anomaly(self):
        anomaly = MetricAnomaly(
            metric_name="cpu_usage",
            source="prometheus",
            current_value=95.0,
            baseline_value=30.0,
            deviation_percent=216.7,
            started_at=datetime.now(UTC),
        )
        assert anomaly.deviation_percent > 200

    def test_trace_result(self):
        trace = TraceResult(
            trace_id="abc-123",
            root_service="api-gateway",
            bottleneck_service="database",
            total_duration_ms=5000.0,
        )
        assert trace.bottleneck_service == "database"

    def test_correlated_event_score_bounds(self):
        event = CorrelatedEvent(
            timestamp=datetime.now(UTC),
            source="cross-correlation",
            event_type="correlated",
            description="Test correlation",
            correlation_score=0.95,
        )
        assert 0.0 <= event.correlation_score <= 1.0

    def test_reasoning_step(self):
        step = ReasoningStep(
            step_number=1,
            action="analyze_logs",
            input_summary="Querying logs",
            output_summary="Found 15 errors",
            duration_ms=200,
            tool_used="query_logs",
        )
        assert step.tool_used == "query_logs"

    def test_investigation_state_defaults(self, alert_context):
        state = InvestigationState(
            alert_id="test",
            alert_context=alert_context,
        )
        assert state.log_findings == []
        assert state.metric_anomalies == []
        assert state.trace_analysis is None
        assert state.hypotheses == []
        assert state.confidence_score == 0.0
        assert state.recommended_action is None
        assert state.current_step == "init"
        assert state.error is None
