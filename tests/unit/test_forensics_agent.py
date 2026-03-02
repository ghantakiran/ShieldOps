"""Tests for the Forensics Agent LangGraph workflow.

Covers:
- ForensicsState model creation, defaults, and field types
- Sub-models: ForensicArtifact, ReasoningStep
- Prompt schemas: ForensicSynthesisOutput
- ForensicsToolkit initialization and async methods
- Graph creation (create_forensics_graph returns a StateGraph)
- ForensicsRunner initialization and list_results
- Node functions (preserve_evidence, verify_integrity, collect_artifacts,
  analyze_memory, analyze_disk, analyze_network, reconstruct_timeline,
  extract_iocs, synthesize, generate_report) with mock state
- Conditional edges (should_continue_after_integrity)
- Integration: full workflow with simple inputs
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.agents.forensics.graph import (
    create_forensics_graph,
    should_continue_after_integrity,
)
from shieldops.agents.forensics.models import (
    ForensicArtifact,
    ForensicsState,
    ReasoningStep,
)
from shieldops.agents.forensics.nodes import (
    _get_toolkit,
    analyze_disk,
    analyze_memory,
    analyze_network,
    collect_artifacts,
    extract_iocs,
    generate_report,
    preserve_evidence,
    reconstruct_timeline,
    set_toolkit,
    synthesize,
    verify_integrity,
)
from shieldops.agents.forensics.prompts import ForensicSynthesisOutput
from shieldops.agents.forensics.runner import ForensicsRunner
from shieldops.agents.forensics.tools import ForensicsToolkit

# -- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_toolkit():
    """Reset the module-level toolkit singleton between tests."""
    import shieldops.agents.forensics.nodes as nodes_mod

    original = nodes_mod._toolkit
    nodes_mod._toolkit = None
    yield
    nodes_mod._toolkit = original


@pytest.fixture
def base_state() -> ForensicsState:
    return ForensicsState(
        incident_id="inc-001",
        evidence_ids=["ev-disk-01", "ev-mem-01", "ev-net-01"],
    )


@pytest.fixture
def analyzed_state() -> ForensicsState:
    return ForensicsState(
        incident_id="inc-002",
        evidence_ids=["ev-01", "ev-02"],
        integrity_verified=True,
        artifacts=[
            {"artifact_id": "art-1", "source_type": "memory"},
            {"artifact_id": "art-2", "source_type": "disk"},
            {"artifact_id": "art-3", "source_type": "network"},
        ],
        memory_findings=[{"artifact_id": "art-1", "analysis_type": "memory"}],
        disk_findings=[{"artifact_id": "art-2", "analysis_type": "disk"}],
        network_findings=[{"artifact_id": "art-3", "analysis_type": "network"}],
    )


# -- TestState ---------------------------------------------------------------


class TestState:
    def test_default_values(self):
        state = ForensicsState()
        assert state.incident_id == ""
        assert state.evidence_ids == []
        assert state.preservation_status == {}
        assert state.integrity_verified is False
        assert state.artifacts == []
        assert state.memory_findings == []
        assert state.disk_findings == []
        assert state.network_findings == []
        assert state.timeline == []
        assert state.extracted_iocs == []
        assert state.synthesis == ""
        assert state.report == {}
        assert state.session_start is None
        assert state.session_duration_ms == 0
        assert state.reasoning_chain == []
        assert state.current_step == "init"
        assert state.error is None

    def test_creation_with_custom_values(self, base_state: ForensicsState):
        assert base_state.incident_id == "inc-001"
        assert len(base_state.evidence_ids) == 3

    def test_list_fields_are_independent(self):
        s1 = ForensicsState()
        s2 = ForensicsState()
        s1.evidence_ids.append("ev-x")
        assert s2.evidence_ids == []

    def test_state_with_error(self):
        state = ForensicsState(error="evidence corrupted", current_step="failed")
        assert state.error == "evidence corrupted"
        assert state.current_step == "failed"


# -- TestSubModels -----------------------------------------------------------


class TestSubModels:
    def test_forensic_artifact_defaults(self):
        artifact = ForensicArtifact()
        assert artifact.artifact_id == ""
        assert artifact.source == ""
        assert artifact.artifact_type == ""
        assert artifact.hash_sha256 == ""
        assert artifact.integrity_verified is False
        assert artifact.metadata == {}

    def test_forensic_artifact_with_values(self):
        artifact = ForensicArtifact(
            artifact_id="art-001",
            source="disk",
            artifact_type="filesystem_image",
            hash_sha256="abc123",
            integrity_verified=True,
            metadata={"size_bytes": 1024},
        )
        assert artifact.artifact_id == "art-001"
        assert artifact.integrity_verified is True
        assert artifact.metadata["size_bytes"] == 1024

    def test_reasoning_step_creation(self):
        step = ReasoningStep(
            step_number=1,
            action="preserve_evidence",
            input_summary="3 evidence items",
            output_summary="All preserved",
        )
        assert step.step_number == 1
        assert step.duration_ms == 0
        assert step.tool_used is None

    def test_reasoning_step_with_tool(self):
        step = ReasoningStep(
            step_number=2,
            action="collect_artifacts",
            input_summary="Collecting",
            output_summary="Collected 5 artifacts",
            duration_ms=300,
            tool_used="memory_analyzer",
        )
        assert step.tool_used == "memory_analyzer"
        assert step.duration_ms == 300


# -- TestPromptSchemas -------------------------------------------------------


class TestPromptSchemas:
    def test_forensic_synthesis_output_fields(self):
        output = ForensicSynthesisOutput(
            summary="Malware infection via phishing email",
            key_findings=["Malware installed at /tmp/evil", "C2 callback observed"],
            timeline_summary="Initial access at 14:00, lateral movement at 14:30",
            iocs=["evil.exe", "10.0.0.99"],
            confidence=0.85,
        )
        assert output.confidence == pytest.approx(0.85)
        assert len(output.key_findings) == 2
        assert len(output.iocs) == 2


# -- TestToolkit -------------------------------------------------------------


class TestToolkit:
    def test_toolkit_initialization_with_no_deps(self):
        toolkit = ForensicsToolkit()
        assert toolkit._evidence_store is None
        assert toolkit._memory_analyzer is None
        assert toolkit._disk_analyzer is None
        assert toolkit._network_analyzer is None

    def test_toolkit_initialization_with_deps(self):
        mock_store = MagicMock()
        toolkit = ForensicsToolkit(evidence_store=mock_store)
        assert toolkit._evidence_store is mock_store

    @pytest.mark.asyncio
    async def test_preserve_evidence_returns_status(self):
        toolkit = ForensicsToolkit()
        result = await toolkit.preserve_evidence(["ev-1", "ev-2"])
        assert result["status"] == "preserved"
        assert "ev-1" in result["preserved"]

    @pytest.mark.asyncio
    async def test_verify_integrity_returns_verified(self):
        toolkit = ForensicsToolkit()
        result = await toolkit.verify_integrity(["ev-1"])
        assert result["verified"] is True
        assert result["discrepancies"] == []

    @pytest.mark.asyncio
    async def test_collect_memory_returns_list(self):
        toolkit = ForensicsToolkit()
        result = await toolkit.collect_memory(["ev-1"])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_collect_disk_returns_list(self):
        toolkit = ForensicsToolkit()
        result = await toolkit.collect_disk(["ev-1"])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_collect_network_returns_list(self):
        toolkit = ForensicsToolkit()
        result = await toolkit.collect_network(["ev-1"])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_reconstruct_timeline_returns_list(self):
        toolkit = ForensicsToolkit()
        result = await toolkit.reconstruct_timeline([{"finding": "test"}])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_extract_iocs_returns_list(self):
        toolkit = ForensicsToolkit()
        result = await toolkit.extract_iocs([{"artifact": "test"}])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_generate_report_returns_draft(self):
        toolkit = ForensicsToolkit()
        result = await toolkit.generate_report({"incident_id": "inc-1"})
        assert result["status"] == "draft"


# -- TestGraph ---------------------------------------------------------------


class TestGraph:
    def test_create_forensics_graph_returns_state_graph(self):
        graph = create_forensics_graph()
        assert graph is not None
        assert hasattr(graph, "compile")

    def test_graph_has_expected_nodes(self):
        graph = create_forensics_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "preserve_evidence",
            "verify_integrity",
            "collect_artifacts",
            "analyze_memory",
            "analyze_disk",
            "analyze_network",
            "reconstruct_timeline",
            "extract_iocs",
            "synthesize",
            "generate_report",
        }
        assert expected.issubset(node_names)

    def test_graph_compiles_without_error(self):
        graph = create_forensics_graph()
        app = graph.compile()
        assert app is not None


# -- TestRunner --------------------------------------------------------------


class TestRunner:
    def test_runner_initialization(self):
        with patch("shieldops.agents.forensics.runner.create_forensics_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = ForensicsRunner()
            assert runner._results == {}

    def test_list_results_empty(self):
        with patch("shieldops.agents.forensics.runner.create_forensics_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = ForensicsRunner()
            assert runner.list_results() == []

    def test_list_results_returns_summaries(self):
        with patch("shieldops.agents.forensics.runner.create_forensics_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = ForensicsRunner()
            runner._results["forensics-abc"] = ForensicsState(
                incident_id="inc-001",
                integrity_verified=True,
                artifacts=[{"id": "art-1"}, {"id": "art-2"}],
                extracted_iocs=["evil.exe"],
                current_step="complete",
            )
            summaries = runner.list_results()
            assert len(summaries) == 1
            assert summaries[0]["incident_id"] == "inc-001"
            assert summaries[0]["integrity_verified"] is True
            assert summaries[0]["artifact_count"] == 2
            assert summaries[0]["ioc_count"] == 1

    @pytest.mark.asyncio
    async def test_investigate_success(self):
        mock_app = AsyncMock()
        final_state = ForensicsState(
            incident_id="inc-001",
            integrity_verified=True,
            current_step="complete",
        ).model_dump()
        mock_app.ainvoke.return_value = final_state

        with patch("shieldops.agents.forensics.runner.create_forensics_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = ForensicsRunner()
            result = await runner.investigate(
                incident_id="inc-001",
                evidence_ids=["ev-1"],
            )

        assert isinstance(result, ForensicsState)
        assert result.current_step == "complete"

    @pytest.mark.asyncio
    async def test_investigate_handles_exception(self):
        mock_app = AsyncMock()
        mock_app.ainvoke.side_effect = RuntimeError("Investigation failed")

        with patch("shieldops.agents.forensics.runner.create_forensics_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = ForensicsRunner()
            result = await runner.investigate(incident_id="inc-x")

        assert result.error == "Investigation failed"
        assert result.current_step == "failed"


# -- TestNodes ---------------------------------------------------------------


class TestNodes:
    @pytest.mark.asyncio
    async def test_preserve_evidence(self, base_state: ForensicsState):
        result = await preserve_evidence(base_state)
        assert "preservation_status" in result
        assert result["current_step"] == "preserve_evidence"
        assert "session_start" in result
        assert len(result["reasoning_chain"]) == 1

    @pytest.mark.asyncio
    async def test_verify_integrity_default_toolkit(self, base_state: ForensicsState):
        result = await verify_integrity(base_state)
        assert result["integrity_verified"] is True
        assert result["current_step"] == "verify_integrity"

    @pytest.mark.asyncio
    async def test_collect_artifacts(self, base_state: ForensicsState):
        result = await collect_artifacts(base_state)
        assert isinstance(result["artifacts"], list)
        assert result["current_step"] == "collect_artifacts"

    @pytest.mark.asyncio
    async def test_analyze_memory_with_artifacts(self):
        state = ForensicsState(
            artifacts=[
                {"artifact_id": "art-1", "source_type": "memory"},
                {"artifact_id": "art-2", "source_type": "disk"},
            ]
        )
        result = await analyze_memory(state)
        assert len(result["memory_findings"]) == 1
        assert result["memory_findings"][0]["analysis_type"] == "memory"
        assert result["current_step"] == "analyze_memory"

    @pytest.mark.asyncio
    async def test_analyze_memory_no_memory_artifacts(self):
        state = ForensicsState(artifacts=[{"artifact_id": "art-1", "source_type": "disk"}])
        result = await analyze_memory(state)
        assert result["memory_findings"] == []

    @pytest.mark.asyncio
    async def test_analyze_disk_with_artifacts(self):
        state = ForensicsState(
            artifacts=[
                {"artifact_id": "art-1", "source_type": "disk"},
                {"artifact_id": "art-2", "source_type": "disk"},
            ]
        )
        result = await analyze_disk(state)
        assert len(result["disk_findings"]) == 2
        assert result["current_step"] == "analyze_disk"

    @pytest.mark.asyncio
    async def test_analyze_disk_no_disk_artifacts(self):
        state = ForensicsState(artifacts=[{"artifact_id": "art-1", "source_type": "memory"}])
        result = await analyze_disk(state)
        assert result["disk_findings"] == []

    @pytest.mark.asyncio
    async def test_analyze_network_with_artifacts(self):
        state = ForensicsState(artifacts=[{"artifact_id": "art-1", "source_type": "network"}])
        result = await analyze_network(state)
        assert len(result["network_findings"]) == 1
        assert result["current_step"] == "analyze_network"

    @pytest.mark.asyncio
    async def test_reconstruct_timeline(self, analyzed_state: ForensicsState):
        result = await reconstruct_timeline(analyzed_state)
        assert isinstance(result["timeline"], list)
        assert result["current_step"] == "reconstruct_timeline"

    @pytest.mark.asyncio
    async def test_extract_iocs(self, analyzed_state: ForensicsState):
        result = await extract_iocs(analyzed_state)
        assert isinstance(result["extracted_iocs"], list)
        assert result["current_step"] == "extract_iocs"

    @pytest.mark.asyncio
    async def test_synthesize(self, analyzed_state: ForensicsState):
        result = await synthesize(analyzed_state)
        assert "synthesis" in result
        assert "inc-002" in result["synthesis"]
        assert "Memory findings: 1" in result["synthesis"]
        assert "Disk findings: 1" in result["synthesis"]
        assert "Network findings: 1" in result["synthesis"]
        assert result["current_step"] == "synthesize"

    @pytest.mark.asyncio
    async def test_synthesize_minimal_state(self):
        state = ForensicsState(
            incident_id="inc-min",
            evidence_ids=["ev-1"],
            integrity_verified=False,
        )
        result = await synthesize(state)
        assert "inc-min" in result["synthesis"]
        assert "Integrity verified: False" in result["synthesis"]

    @pytest.mark.asyncio
    async def test_generate_report(self, analyzed_state: ForensicsState):
        analyzed_state.session_start = datetime.now(UTC)
        result = await generate_report(analyzed_state)
        assert "report" in result
        assert result["report"]["status"] == "draft"
        assert result["session_duration_ms"] >= 0
        assert result["current_step"] == "complete"

    @pytest.mark.asyncio
    async def test_generate_report_no_session_start(self):
        state = ForensicsState(incident_id="inc-no-start")
        result = await generate_report(state)
        assert result["session_duration_ms"] == 0


# -- TestConditionalEdges ----------------------------------------------------


class TestConditionalEdges:
    def test_integrity_verified_continues(self):
        state = ForensicsState(integrity_verified=True)
        assert should_continue_after_integrity(state) == "collect_artifacts"

    def test_integrity_not_verified_goes_to_report(self):
        state = ForensicsState(integrity_verified=False)
        assert should_continue_after_integrity(state) == "generate_report"

    def test_error_state_goes_to_report(self):
        state = ForensicsState(integrity_verified=True, error="hash mismatch")
        assert should_continue_after_integrity(state) == "generate_report"


# -- TestToolkitManagement ---------------------------------------------------


class TestToolkitManagement:
    def test_get_toolkit_returns_default_when_none_set(self):
        toolkit = _get_toolkit()
        assert isinstance(toolkit, ForensicsToolkit)

    def test_set_toolkit_is_used_by_get_toolkit(self):
        custom = ForensicsToolkit(evidence_store=MagicMock())
        set_toolkit(custom)
        assert _get_toolkit() is custom


# -- TestIntegration ---------------------------------------------------------


class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_workflow_integrity_passes(self, base_state: ForensicsState):
        """Full workflow: preserve -> verify -> collect -> analyze -> timeline -> IOCs
        -> synthesize -> report."""
        r1 = await preserve_evidence(base_state)
        state = ForensicsState(**{**base_state.model_dump(), **r1})
        assert state.current_step == "preserve_evidence"

        r2 = await verify_integrity(state)
        state = ForensicsState(**{**state.model_dump(), **r2})
        assert state.integrity_verified is True

        # Conditional: should continue
        assert should_continue_after_integrity(state) == "collect_artifacts"

        r3 = await collect_artifacts(state)
        state = ForensicsState(**{**state.model_dump(), **r3})

        r4 = await analyze_memory(state)
        state = ForensicsState(**{**state.model_dump(), **r4})

        r5 = await analyze_disk(state)
        state = ForensicsState(**{**state.model_dump(), **r5})

        r6 = await analyze_network(state)
        state = ForensicsState(**{**state.model_dump(), **r6})

        r7 = await reconstruct_timeline(state)
        state = ForensicsState(**{**state.model_dump(), **r7})

        r8 = await extract_iocs(state)
        state = ForensicsState(**{**state.model_dump(), **r8})

        r9 = await synthesize(state)
        state = ForensicsState(**{**state.model_dump(), **r9})
        assert "inc-001" in state.synthesis

        state.session_start = datetime.now(UTC)
        r10 = await generate_report(state)
        assert r10["current_step"] == "complete"
        assert r10["report"]["status"] == "draft"

    @pytest.mark.asyncio
    async def test_full_workflow_integrity_fails(self):
        """When integrity check fails, skip analysis and go straight to report."""
        state = ForensicsState(
            incident_id="inc-bad",
            evidence_ids=["ev-corrupted"],
            integrity_verified=False,
        )
        assert should_continue_after_integrity(state) == "generate_report"
        result = await generate_report(state)
        assert result["current_step"] == "complete"
