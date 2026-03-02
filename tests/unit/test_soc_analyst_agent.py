"""Tests for the SOC Analyst Agent LangGraph workflow.

Covers:
- SOCAnalystState model creation, defaults, and field types
- Sub-models: ThreatIntelEnrichment, CorrelatedEvent, ContainmentRecommendation, ReasoningStep
- Prompt schemas: TriageOutput, AttackNarrativeOutput, ContainmentOutput
- SOCAnalystToolkit initialization and async methods
- Graph creation (create_soc_analyst_graph returns a StateGraph)
- SOCAnalystRunner initialization and list_results
- Node functions (triage_alert, enrich_alert, correlate_events, map_attack_chain,
  generate_narrative, recommend_containment, execute_playbook, finalize) with mock state
- Conditional edges (should_suppress, should_map_attack_chain, should_auto_execute)
- Integration: full workflow with simple inputs
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.agents.soc_analyst.graph import (
    create_soc_analyst_graph,
    should_auto_execute,
    should_map_attack_chain,
    should_suppress,
)
from shieldops.agents.soc_analyst.models import (
    ContainmentRecommendation,
    CorrelatedEvent,
    ReasoningStep,
    SOCAnalystState,
    ThreatIntelEnrichment,
)
from shieldops.agents.soc_analyst.nodes import (
    _get_toolkit,
    correlate_events,
    enrich_alert,
    execute_playbook,
    finalize,
    generate_narrative,
    map_attack_chain,
    recommend_containment,
    set_toolkit,
    triage_alert,
)
from shieldops.agents.soc_analyst.prompts import (
    AttackNarrativeOutput,
    ContainmentOutput,
    TriageOutput,
)
from shieldops.agents.soc_analyst.runner import SOCAnalystRunner
from shieldops.agents.soc_analyst.tools import SOCAnalystToolkit

# -- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_toolkit():
    """Reset the module-level toolkit singleton between tests."""
    import shieldops.agents.soc_analyst.nodes as nodes_mod

    original = nodes_mod._toolkit
    nodes_mod._toolkit = None
    yield
    nodes_mod._toolkit = original


@pytest.fixture
def base_state() -> SOCAnalystState:
    return SOCAnalystState(
        alert_id="alert-001",
        alert_data={"severity": "high", "source_ip": "10.0.0.5"},
    )


@pytest.fixture
def enriched_state() -> SOCAnalystState:
    return SOCAnalystState(
        alert_id="alert-002",
        alert_data={"severity": "critical", "source_ip": "192.168.1.100"},
        tier=3,
        triage_score=95.0,
        threat_intel_enrichment=ThreatIntelEnrichment(
            ioc_matches=["malware.exe"],
            reputation_score=85.0,
        ),
        correlated_events=[
            CorrelatedEvent(
                event_id="evt-1",
                event_type="auth_failure",
                source="siem",
                severity="high",
                relevance_score=0.9,
            ),
        ],
    )


# -- TestState ---------------------------------------------------------------


class TestState:
    def test_default_values(self):
        state = SOCAnalystState()
        assert state.alert_id == ""
        assert state.alert_data == {}
        assert state.tier == 1
        assert state.triage_score == pytest.approx(0.0)
        assert state.should_suppress is False
        assert state.threat_intel_enrichment is None
        assert state.asset_context == {}
        assert state.correlated_events == []
        assert state.mitre_techniques == []
        assert state.attack_chain == []
        assert state.attack_narrative == ""
        assert state.containment_recommendations == []
        assert state.playbook_executed is False
        assert state.playbook_result == {}
        assert state.session_start is None
        assert state.session_duration_ms == 0
        assert state.reasoning_chain == []
        assert state.current_step == "init"
        assert state.error is None

    def test_creation_with_custom_values(self, base_state: SOCAnalystState):
        assert base_state.alert_id == "alert-001"
        assert base_state.alert_data["severity"] == "high"
        assert base_state.alert_data["source_ip"] == "10.0.0.5"

    def test_list_fields_are_independent_instances(self):
        s1 = SOCAnalystState()
        s2 = SOCAnalystState()
        s1.mitre_techniques.append("T1059")
        assert s2.mitre_techniques == []

    def test_state_with_error(self):
        state = SOCAnalystState(error="connection timeout", current_step="failed")
        assert state.error == "connection timeout"
        assert state.current_step == "failed"


# -- TestSubModels -----------------------------------------------------------


class TestSubModels:
    def test_threat_intel_enrichment_defaults(self):
        enrichment = ThreatIntelEnrichment()
        assert enrichment.ioc_matches == []
        assert enrichment.threat_feeds == []
        assert enrichment.reputation_score == pytest.approx(0.0)
        assert enrichment.geo_ip_info == {}
        assert enrichment.related_campaigns == []

    def test_correlated_event_defaults(self):
        event = CorrelatedEvent()
        assert event.event_id == ""
        assert event.event_type == ""
        assert event.source == ""
        assert event.timestamp == ""
        assert event.summary == ""
        assert event.severity == "low"
        assert event.relevance_score == pytest.approx(0.0)

    def test_containment_recommendation_defaults(self):
        rec = ContainmentRecommendation()
        assert rec.action == ""
        assert rec.target == ""
        assert rec.urgency == "medium"
        assert rec.risk_level == "low"
        assert rec.automated is False
        assert rec.description == ""

    def test_reasoning_step_creation(self):
        step = ReasoningStep(
            step_number=1,
            action="triage_alert",
            input_summary="Alert alert-001",
            output_summary="Triaged",
        )
        assert step.step_number == 1
        assert step.action == "triage_alert"
        assert step.duration_ms == 0
        assert step.tool_used is None

    def test_correlated_event_with_all_fields(self):
        event = CorrelatedEvent(
            event_id="evt-1",
            event_type="dns_query",
            source="dns_logs",
            timestamp="2026-01-01T00:00:00Z",
            summary="Suspicious DNS query",
            severity="high",
            relevance_score=0.95,
        )
        assert event.severity == "high"
        assert event.relevance_score == pytest.approx(0.95)


# -- TestPromptSchemas -------------------------------------------------------


class TestPromptSchemas:
    def test_triage_output_fields(self):
        output = TriageOutput(
            triage_score=85.0,
            tier=3,
            should_suppress=False,
            reasoning="Critical alert from known APT",
        )
        assert output.triage_score == pytest.approx(85.0)
        assert output.tier == 3
        assert output.should_suppress is False

    def test_attack_narrative_output_fields(self):
        output = AttackNarrativeOutput(
            narrative="Attacker gained initial access via phishing",
            mitre_techniques=["T1566", "T1059"],
            confidence=0.85,
            severity="critical",
        )
        assert len(output.mitre_techniques) == 2
        assert output.confidence == pytest.approx(0.85)

    def test_containment_output_fields(self):
        output = ContainmentOutput(
            recommendations=[{"action": "isolate", "target": "host-1"}],
            auto_executable=True,
            reasoning="Host shows signs of compromise",
        )
        assert len(output.recommendations) == 1
        assert output.auto_executable is True


# -- TestToolkit -------------------------------------------------------------


class TestToolkit:
    def test_toolkit_initialization_with_no_deps(self):
        toolkit = SOCAnalystToolkit()
        assert toolkit._mitre_mapper is None
        assert toolkit._threat_intel is None
        assert toolkit._soar_engine is None

    def test_toolkit_initialization_with_deps(self):
        mock_mapper = MagicMock()
        toolkit = SOCAnalystToolkit(mitre_mapper=mock_mapper)
        assert toolkit._mitre_mapper is mock_mapper

    @pytest.mark.asyncio
    async def test_enrich_with_threat_intel_returns_expected_keys(self):
        toolkit = SOCAnalystToolkit()
        result = await toolkit.enrich_with_threat_intel(["10.0.0.1"])
        assert "ioc_matches" in result
        assert "threat_feeds" in result
        assert "reputation_score" in result
        assert "geo_ip_info" in result

    @pytest.mark.asyncio
    async def test_map_to_mitre_returns_list(self):
        toolkit = SOCAnalystToolkit()
        result = await toolkit.map_to_mitre([{"type": "auth_failure"}])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_correlate_signals_returns_list(self):
        toolkit = SOCAnalystToolkit()
        result = await toolkit.correlate_signals("alert-001")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_execute_playbook_returns_status(self):
        toolkit = SOCAnalystToolkit()
        result = await toolkit.execute_playbook("auto_containment", {"alert_id": "a1"})
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_check_policy_returns_allowed(self):
        toolkit = SOCAnalystToolkit()
        result = await toolkit.check_policy("isolate_host", "10.0.0.1")
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_record_soc_metric(self):
        toolkit = SOCAnalystToolkit()
        await toolkit.record_soc_metric("triage", 85.0)  # should not raise


# -- TestGraph ---------------------------------------------------------------


class TestGraph:
    def test_create_soc_analyst_graph_returns_state_graph(self):
        graph = create_soc_analyst_graph()
        assert graph is not None
        assert hasattr(graph, "compile")

    def test_graph_has_expected_nodes(self):
        graph = create_soc_analyst_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "triage_alert",
            "enrich_alert",
            "correlate_events",
            "map_attack_chain",
            "generate_narrative",
            "recommend_containment",
            "execute_playbook",
            "finalize",
        }
        assert expected.issubset(node_names)

    def test_graph_compiles_without_error(self):
        graph = create_soc_analyst_graph()
        app = graph.compile()
        assert app is not None


# -- TestRunner --------------------------------------------------------------


class TestRunner:
    def test_runner_initialization(self):
        with patch("shieldops.agents.soc_analyst.runner.create_soc_analyst_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = SOCAnalystRunner()
            assert runner._results == {}

    def test_list_results_empty(self):
        with patch("shieldops.agents.soc_analyst.runner.create_soc_analyst_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = SOCAnalystRunner()
            assert runner.list_results() == []

    def test_list_results_returns_summaries(self):
        with patch("shieldops.agents.soc_analyst.runner.create_soc_analyst_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = SOCAnalystRunner()
            runner._results["soc-abc"] = SOCAnalystState(
                alert_id="alert-001",
                tier=2,
                triage_score=75.0,
                current_step="complete",
            )
            summaries = runner.list_results()
            assert len(summaries) == 1
            assert summaries[0]["alert_id"] == "alert-001"
            assert summaries[0]["tier"] == 2

    @pytest.mark.asyncio
    async def test_analyze_success(self):
        mock_app = AsyncMock()
        final_state = SOCAnalystState(
            alert_id="alert-001",
            tier=2,
            triage_score=80.0,
            current_step="complete",
        ).model_dump()
        mock_app.ainvoke.return_value = final_state

        with patch("shieldops.agents.soc_analyst.runner.create_soc_analyst_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = SOCAnalystRunner()
            result = await runner.analyze(alert_id="alert-001")

        assert isinstance(result, SOCAnalystState)
        assert result.current_step == "complete"

    @pytest.mark.asyncio
    async def test_analyze_handles_exception(self):
        mock_app = AsyncMock()
        mock_app.ainvoke.side_effect = RuntimeError("Graph exploded")

        with patch("shieldops.agents.soc_analyst.runner.create_soc_analyst_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = SOCAnalystRunner()
            result = await runner.analyze(alert_id="alert-x")

        assert result.error == "Graph exploded"
        assert result.current_step == "failed"


# -- TestNodes ---------------------------------------------------------------


class TestNodes:
    @pytest.mark.asyncio
    async def test_triage_alert_critical(self):
        state = SOCAnalystState(
            alert_id="alert-crit",
            alert_data={"severity": "critical"},
        )
        result = await triage_alert(state)
        assert result["triage_score"] == pytest.approx(95.0)
        assert result["tier"] == 3
        assert result["should_suppress"] is False
        assert result["current_step"] == "triage_alert"
        assert len(result["reasoning_chain"]) == 1

    @pytest.mark.asyncio
    async def test_triage_alert_low(self):
        state = SOCAnalystState(
            alert_id="alert-low",
            alert_data={"severity": "low"},
        )
        result = await triage_alert(state)
        assert result["triage_score"] == pytest.approx(25.0)
        assert result["tier"] == 1

    @pytest.mark.asyncio
    async def test_triage_alert_info_suppressed(self):
        state = SOCAnalystState(
            alert_id="alert-info",
            alert_data={"severity": "info"},
        )
        result = await triage_alert(state)
        assert result["triage_score"] == pytest.approx(10.0)
        assert result["should_suppress"] is True

    @pytest.mark.asyncio
    async def test_triage_alert_known_false_positive(self):
        state = SOCAnalystState(
            alert_id="alert-fp",
            alert_data={"severity": "high", "known_false_positive": True},
        )
        result = await triage_alert(state)
        assert result["should_suppress"] is True

    @pytest.mark.asyncio
    async def test_enrich_alert_returns_enrichment(self, base_state: SOCAnalystState):
        result = await enrich_alert(base_state)
        assert "threat_intel_enrichment" in result
        assert isinstance(result["threat_intel_enrichment"], ThreatIntelEnrichment)
        assert result["current_step"] == "enrich_alert"

    @pytest.mark.asyncio
    async def test_correlate_events_returns_list(self, base_state: SOCAnalystState):
        result = await correlate_events(base_state)
        assert isinstance(result["correlated_events"], list)
        assert result["current_step"] == "correlate_events"

    @pytest.mark.asyncio
    async def test_map_attack_chain(self, enriched_state: SOCAnalystState):
        result = await map_attack_chain(enriched_state)
        assert "mitre_techniques" in result
        assert "attack_chain" in result
        assert result["current_step"] == "map_attack_chain"

    @pytest.mark.asyncio
    async def test_generate_narrative(self, enriched_state: SOCAnalystState):
        enriched_state.mitre_techniques = ["T1059", "T1566"]
        result = await generate_narrative(enriched_state)
        assert "attack_narrative" in result
        assert "T1059" in result["attack_narrative"]
        assert result["current_step"] == "generate_narrative"

    @pytest.mark.asyncio
    async def test_recommend_containment_tier2(self):
        state = SOCAnalystState(
            alert_id="alert-t2",
            alert_data={"source_ip": "10.0.0.5"},
            tier=2,
        )
        result = await recommend_containment(state)
        recs = result["containment_recommendations"]
        assert len(recs) >= 1
        assert recs[0].action == "isolate_host"
        assert recs[0].automated is True  # tier 2 auto-executes

    @pytest.mark.asyncio
    async def test_recommend_containment_tier3_not_auto(self):
        state = SOCAnalystState(
            alert_id="alert-t3",
            alert_data={"source_ip": "10.0.0.5"},
            tier=3,
        )
        result = await recommend_containment(state)
        recs = result["containment_recommendations"]
        assert recs[0].automated is False  # tier 3 requires manual approval

    @pytest.mark.asyncio
    async def test_execute_playbook_with_auto_actions(self):
        state = SOCAnalystState(
            alert_id="alert-auto",
            containment_recommendations=[
                ContainmentRecommendation(action="block_iocs", target="firewall", automated=True),
            ],
        )
        result = await execute_playbook(state)
        assert result["playbook_executed"] is True
        assert result["current_step"] == "execute_playbook"

    @pytest.mark.asyncio
    async def test_execute_playbook_no_auto_actions(self):
        state = SOCAnalystState(
            alert_id="alert-manual",
            containment_recommendations=[
                ContainmentRecommendation(action="isolate_host", target="host-1", automated=False),
            ],
        )
        result = await execute_playbook(state)
        assert result["playbook_executed"] is False

    @pytest.mark.asyncio
    async def test_finalize_records_duration(self):
        state = SOCAnalystState(
            alert_id="alert-final",
            tier=2,
            session_start=datetime.now(UTC),
        )
        result = await finalize(state)
        assert result["session_duration_ms"] >= 0
        assert result["current_step"] == "complete"

    @pytest.mark.asyncio
    async def test_finalize_no_session_start(self):
        state = SOCAnalystState(alert_id="alert-no-start")
        result = await finalize(state)
        assert result["session_duration_ms"] == 0


# -- TestConditionalEdges ----------------------------------------------------


class TestConditionalEdges:
    def test_should_suppress_true(self):
        state = SOCAnalystState(should_suppress=True)
        assert should_suppress(state) == "__end__"

    def test_should_suppress_false(self):
        state = SOCAnalystState(should_suppress=False)
        assert should_suppress(state) == "enrich_alert"

    def test_should_map_attack_chain_tier1(self):
        state = SOCAnalystState(tier=1)
        assert should_map_attack_chain(state) == "recommend_containment"

    def test_should_map_attack_chain_tier2(self):
        state = SOCAnalystState(tier=2)
        assert should_map_attack_chain(state) == "map_attack_chain"

    def test_should_map_attack_chain_tier3(self):
        state = SOCAnalystState(tier=3)
        assert should_map_attack_chain(state) == "map_attack_chain"

    def test_should_map_attack_chain_error(self):
        state = SOCAnalystState(tier=3, error="failed")
        assert should_map_attack_chain(state) == "finalize"

    def test_should_auto_execute_with_auto_actions(self):
        state = SOCAnalystState(
            containment_recommendations=[
                ContainmentRecommendation(action="block", automated=True),
            ]
        )
        assert should_auto_execute(state) == "execute_playbook"

    def test_should_auto_execute_no_auto_actions(self):
        state = SOCAnalystState(
            containment_recommendations=[
                ContainmentRecommendation(action="isolate", automated=False),
            ]
        )
        assert should_auto_execute(state) == "finalize"

    def test_should_auto_execute_empty_recommendations(self):
        state = SOCAnalystState(containment_recommendations=[])
        assert should_auto_execute(state) == "finalize"


# -- TestToolkitManagement ---------------------------------------------------


class TestToolkitManagement:
    def test_get_toolkit_returns_default_when_none_set(self):
        toolkit = _get_toolkit()
        assert isinstance(toolkit, SOCAnalystToolkit)

    def test_set_toolkit_is_used_by_get_toolkit(self):
        custom = SOCAnalystToolkit(mitre_mapper=MagicMock())
        set_toolkit(custom)
        assert _get_toolkit() is custom


# -- TestIntegration ---------------------------------------------------------


class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_workflow_low_severity(self):
        """Low-severity alert goes through triage and is suppressed (info level)."""
        state = SOCAnalystState(
            alert_id="alert-int-1",
            alert_data={"severity": "info"},
        )
        result = await triage_alert(state)
        assert result["should_suppress"] is True
        assert result["tier"] == 1

    @pytest.mark.asyncio
    async def test_full_workflow_high_severity_path(self):
        """High-severity alert goes through triage -> enrich -> correlate -> containment."""
        state = SOCAnalystState(
            alert_id="alert-int-2",
            alert_data={"severity": "high", "source_ip": "10.0.0.99"},
        )
        triage_result = await triage_alert(state)
        assert triage_result["tier"] == 2
        assert triage_result["should_suppress"] is False

        state_after_triage = SOCAnalystState(**{**state.model_dump(), **triage_result})
        enrich_result = await enrich_alert(state_after_triage)
        assert "threat_intel_enrichment" in enrich_result

        state_after_enrich = SOCAnalystState(**{**state_after_triage.model_dump(), **enrich_result})
        correlate_result = await correlate_events(state_after_enrich)
        assert "correlated_events" in correlate_result

    @pytest.mark.asyncio
    async def test_full_workflow_critical_with_containment(self):
        """Critical alert generates containment recs with no auto-execute (tier 3)."""
        state = SOCAnalystState(
            alert_id="alert-int-3",
            alert_data={"severity": "critical", "source_ip": "10.0.0.50"},
            tier=3,
            triage_score=95.0,
        )
        result = await recommend_containment(state)
        recs = result["containment_recommendations"]
        assert len(recs) >= 1
        # Tier 3 recs should not be automated
        assert recs[0].automated is False

        state_with_recs = SOCAnalystState(**{**state.model_dump(), **result})
        assert should_auto_execute(state_with_recs) == "finalize"
