"""Tests for the Prediction Agent module.

Covers:
- PredictionState model creation, defaults, and field types
- Prediction model with severity levels and field defaults
- TrendAnomaly model construction and defaults
- CorrelatedChange model construction and defaults
- PredictionSeverity enum values
- PredictionToolkit methods (collect_metric_baselines, detect_trend_anomalies,
  get_recent_changes, estimate_blast_radius)
- Node functions (collect_baselines, detect_trends, correlate_changes,
  assess_risk, generate_predictions)
- PredictionRunner.predict() with mocked graph
- PredictionRunner.get_prediction(), list_predictions(), get_active_predictions()
- Graph conditional routing (should_generate)
- Edge cases: empty resources, no anomalies, no correlations, error handling
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.agents.prediction.graph import should_generate
from shieldops.agents.prediction.models import (
    CorrelatedChange,
    Prediction,
    PredictionSeverity,
    PredictionState,
    TrendAnomaly,
)
from shieldops.agents.prediction.nodes import (
    _get_toolkit,
    assess_risk,
    collect_baselines,
    correlate_changes,
    detect_trends,
    generate_predictions,
    set_toolkit,
)
from shieldops.agents.prediction.runner import PredictionRunner
from shieldops.agents.prediction.tools import PredictionToolkit

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_toolkit():
    """Reset the module-level toolkit singleton between tests."""
    import shieldops.agents.prediction.nodes as nodes_mod

    original = nodes_mod._toolkit
    nodes_mod._toolkit = None
    yield
    nodes_mod._toolkit = original


@pytest.fixture
def sample_anomaly() -> TrendAnomaly:
    return TrendAnomaly(
        metric_name="cpu_usage",
        resource_id="svc-api-01",
        trend_direction="increasing",
        deviation_percent=60.0,
        baseline_value=45.0,
        current_value=72.0,
    )


@pytest.fixture
def sample_change() -> CorrelatedChange:
    return CorrelatedChange(
        change_id="chg-abc123",
        change_type="deployment",
        description="Deployed v2.3.0 of api-service",
        correlation_score=0.85,
    )


@pytest.fixture
def sample_prediction() -> Prediction:
    return Prediction(
        id="pred-test001",
        title="CPU spike predicted",
        description="CPU is trending up on svc-api-01",
        severity=PredictionSeverity.HIGH,
        confidence=0.8,
        predicted_impact="API latency degradation",
        affected_resources=["svc-api-01"],
        recommended_actions=["Scale horizontally", "Check deployment"],
        evidence=["Baseline: 45, Current: 72", "Deviation: 60%"],
        estimated_time_to_incident="2-4 hours",
    )


@pytest.fixture
def base_state() -> PredictionState:
    return PredictionState(
        prediction_id="pred-test-run",
        target_resources=["svc-api-01", "svc-db-01"],
        lookback_hours=12,
    )


@pytest.fixture
def mock_toolkit() -> PredictionToolkit:
    """Create a PredictionToolkit with mocked dependencies."""
    detector = MagicMock()
    detector.detect.return_value = [
        {
            "metric_name": "cpu_usage",
            "resource_id": "svc-api-01",
            "trend_direction": "increasing",
            "deviation_percent": 65.0,
            "baseline_value": 45.0,
            "current_value": 74.0,
        }
    ]
    tracker = MagicMock()
    tracker.get_recent.return_value = [
        {
            "change_id": "chg-001",
            "change_type": "deployment",
            "description": "v2.3.0 rollout",
            "correlation_score": 0.9,
        }
    ]
    topo = MagicMock()
    topo.get_dependents.return_value = {
        "resource": "svc-api-01",
        "dependents": ["svc-frontend", "svc-worker"],
        "blast_radius": "medium",
    }
    return PredictionToolkit(
        anomaly_detector=detector,
        change_tracker=tracker,
        topology_builder=topo,
    )


# ── PredictionSeverity Enum ─────────────────────────────────────


class TestPredictionSeverity:
    def test_severity_values(self):
        assert PredictionSeverity.LOW == "low"
        assert PredictionSeverity.MEDIUM == "medium"
        assert PredictionSeverity.HIGH == "high"
        assert PredictionSeverity.CRITICAL == "critical"

    def test_severity_is_string_enum(self):
        assert isinstance(PredictionSeverity.LOW, str)
        assert f"Severity: {PredictionSeverity.HIGH}" == "Severity: high"


# ── TrendAnomaly Model ──────────────────────────────────────────


class TestTrendAnomaly:
    def test_creation_with_all_fields(self, sample_anomaly: TrendAnomaly):
        assert sample_anomaly.metric_name == "cpu_usage"
        assert sample_anomaly.resource_id == "svc-api-01"
        assert sample_anomaly.trend_direction == "increasing"
        assert sample_anomaly.deviation_percent == pytest.approx(60.0)
        assert sample_anomaly.baseline_value == pytest.approx(45.0)
        assert sample_anomaly.current_value == pytest.approx(72.0)

    def test_defaults(self):
        anomaly = TrendAnomaly(metric_name="latency")
        assert anomaly.resource_id == ""
        assert anomaly.trend_direction == ""
        assert anomaly.deviation_percent == pytest.approx(0.0)
        assert anomaly.baseline_value == pytest.approx(0.0)
        assert anomaly.current_value == pytest.approx(0.0)
        assert isinstance(anomaly.detected_at, datetime)

    def test_detected_at_auto_populated(self):
        before = datetime.now(UTC)
        anomaly = TrendAnomaly(metric_name="mem")
        after = datetime.now(UTC)
        assert before <= anomaly.detected_at <= after


# ── CorrelatedChange Model ──────────────────────────────────────


class TestCorrelatedChange:
    def test_creation_with_all_fields(self, sample_change: CorrelatedChange):
        assert sample_change.change_id == "chg-abc123"
        assert sample_change.change_type == "deployment"
        assert sample_change.description == "Deployed v2.3.0 of api-service"
        assert sample_change.correlation_score == pytest.approx(0.85)

    def test_defaults(self):
        change = CorrelatedChange()
        assert change.change_id == ""
        assert change.change_type == ""
        assert change.description == ""
        assert change.correlation_score == pytest.approx(0.0)
        assert isinstance(change.timestamp, datetime)


# ── Prediction Model ────────────────────────────────────────────


class TestPrediction:
    def test_creation_with_all_fields(self, sample_prediction: Prediction):
        assert sample_prediction.id == "pred-test001"
        assert sample_prediction.severity == PredictionSeverity.HIGH
        assert sample_prediction.confidence == pytest.approx(0.8)
        assert len(sample_prediction.affected_resources) == 1
        assert len(sample_prediction.recommended_actions) == 2
        assert len(sample_prediction.evidence) == 2
        assert sample_prediction.estimated_time_to_incident == "2-4 hours"

    def test_defaults(self):
        pred = Prediction()
        assert pred.id == ""
        assert pred.title == ""
        assert pred.description == ""
        assert pred.severity == PredictionSeverity.LOW
        assert pred.confidence == pytest.approx(0.0)
        assert pred.predicted_impact == ""
        assert pred.affected_resources == []
        assert pred.recommended_actions == []
        assert pred.evidence == []
        assert pred.estimated_time_to_incident == ""
        assert isinstance(pred.created_at, datetime)

    @pytest.mark.parametrize(
        "severity",
        [
            PredictionSeverity.LOW,
            PredictionSeverity.MEDIUM,
            PredictionSeverity.HIGH,
            PredictionSeverity.CRITICAL,
        ],
    )
    def test_all_severity_levels_assignable(self, severity: PredictionSeverity):
        pred = Prediction(severity=severity)
        assert pred.severity == severity


# ── PredictionState Model ───────────────────────────────────────


class TestPredictionState:
    def test_creation_with_defaults(self):
        state = PredictionState()
        assert state.prediction_id == ""
        assert state.current_step == "started"
        assert state.target_resources == []
        assert state.lookback_hours == 24
        assert state.trend_anomalies == []
        assert state.correlated_changes == []
        assert state.risk_score == pytest.approx(0.0)
        assert state.predictions == []
        assert state.prediction_start is None
        assert state.prediction_duration_ms == 0
        assert state.reasoning_chain == []
        assert state.error is None

    def test_creation_with_custom_values(self, base_state: PredictionState):
        assert base_state.prediction_id == "pred-test-run"
        assert base_state.target_resources == ["svc-api-01", "svc-db-01"]
        assert base_state.lookback_hours == 12

    def test_state_with_nested_models(
        self, sample_anomaly: TrendAnomaly, sample_change: CorrelatedChange
    ):
        state = PredictionState(
            trend_anomalies=[sample_anomaly],
            correlated_changes=[sample_change],
        )
        assert len(state.trend_anomalies) == 1
        assert state.trend_anomalies[0].metric_name == "cpu_usage"
        assert len(state.correlated_changes) == 1
        assert state.correlated_changes[0].change_id == "chg-abc123"

    def test_state_with_error(self):
        state = PredictionState(error="Something broke", current_step="failed")
        assert state.error == "Something broke"
        assert state.current_step == "failed"

    def test_list_fields_are_independent_instances(self):
        """Each PredictionState instance must have its own list instances."""
        s1 = PredictionState()
        s2 = PredictionState()
        s1.target_resources.append("svc-x")
        assert s2.target_resources == []


# ── PredictionToolkit ───────────────────────────────────────────


class TestPredictionToolkit:
    @pytest.mark.asyncio
    async def test_collect_metric_baselines_returns_one_entry_per_resource(self):
        toolkit = PredictionToolkit()
        baselines = await toolkit.collect_metric_baselines(
            resources=["svc-a", "svc-b"], lookback_hours=6
        )
        assert len(baselines) == 2
        assert "svc-a" in baselines
        assert "svc-b" in baselines

    @pytest.mark.asyncio
    async def test_collect_metric_baselines_contains_expected_keys(self):
        toolkit = PredictionToolkit()
        baselines = await toolkit.collect_metric_baselines(resources=["svc-a"])
        entry = baselines["svc-a"]
        assert "cpu_avg" in entry
        assert "memory_avg" in entry
        assert "error_rate_avg" in entry
        assert "latency_p99_avg" in entry
        assert "collected_at" in entry
        assert entry["lookback_hours"] == 24

    @pytest.mark.asyncio
    async def test_collect_metric_baselines_empty_resources(self):
        toolkit = PredictionToolkit()
        baselines = await toolkit.collect_metric_baselines(resources=[])
        assert baselines == {}

    @pytest.mark.asyncio
    async def test_collect_metric_baselines_custom_lookback(self):
        toolkit = PredictionToolkit()
        baselines = await toolkit.collect_metric_baselines(resources=["svc-a"], lookback_hours=48)
        assert baselines["svc-a"]["lookback_hours"] == 48

    @pytest.mark.asyncio
    async def test_detect_trend_anomalies_no_detector_returns_empty(self):
        toolkit = PredictionToolkit()
        result = await toolkit.detect_trend_anomalies(baselines={"svc-a": {"cpu_avg": 50}})
        assert result == []

    @pytest.mark.asyncio
    async def test_detect_trend_anomalies_with_detector(self, mock_toolkit: PredictionToolkit):
        result = await mock_toolkit.detect_trend_anomalies(
            baselines={"svc-api-01": {"cpu_avg": 74}}
        )
        assert len(result) == 1
        assert result[0]["metric_name"] == "cpu_usage"

    @pytest.mark.asyncio
    async def test_detect_trend_anomalies_detector_exception_returns_empty(self):
        bad_detector = MagicMock()
        bad_detector.detect.side_effect = RuntimeError("detector crashed")
        toolkit = PredictionToolkit(anomaly_detector=bad_detector)
        result = await toolkit.detect_trend_anomalies(baselines={"svc-a": {"cpu_avg": 50}})
        assert result == []

    @pytest.mark.asyncio
    async def test_get_recent_changes_no_tracker_returns_empty(self):
        toolkit = PredictionToolkit()
        result = await toolkit.get_recent_changes(lookback_hours=12)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_recent_changes_with_tracker(self, mock_toolkit: PredictionToolkit):
        result = await mock_toolkit.get_recent_changes(lookback_hours=24)
        assert len(result) == 1
        assert result[0]["change_type"] == "deployment"

    @pytest.mark.asyncio
    async def test_get_recent_changes_tracker_exception_returns_empty(self):
        bad_tracker = MagicMock()
        bad_tracker.get_recent.side_effect = RuntimeError("tracker down")
        toolkit = PredictionToolkit(change_tracker=bad_tracker)
        result = await toolkit.get_recent_changes()
        assert result == []

    @pytest.mark.asyncio
    async def test_estimate_blast_radius_no_topology_returns_default(self):
        toolkit = PredictionToolkit()
        result = await toolkit.estimate_blast_radius(resource_id="svc-api-01")
        assert result["resource"] == "svc-api-01"
        assert result["dependents"] == []
        assert result["blast_radius"] == "unknown"

    @pytest.mark.asyncio
    async def test_estimate_blast_radius_with_topology(self, mock_toolkit: PredictionToolkit):
        result = await mock_toolkit.estimate_blast_radius(resource_id="svc-api-01")
        assert "svc-frontend" in result["dependents"]
        assert result["blast_radius"] == "medium"

    @pytest.mark.asyncio
    async def test_estimate_blast_radius_topology_exception_returns_default(self):
        bad_topo = MagicMock()
        bad_topo.get_dependents.side_effect = RuntimeError("topo failure")
        toolkit = PredictionToolkit(topology_builder=bad_topo)
        result = await toolkit.estimate_blast_radius(resource_id="svc-x")
        assert result["blast_radius"] == "unknown"


# ── Node: set_toolkit / _get_toolkit ────────────────────────────


class TestToolkitManagement:
    def test_get_toolkit_returns_default_when_none_set(self):
        toolkit = _get_toolkit()
        assert isinstance(toolkit, PredictionToolkit)

    def test_set_toolkit_is_used_by_get_toolkit(self, mock_toolkit: PredictionToolkit):
        set_toolkit(mock_toolkit)
        assert _get_toolkit() is mock_toolkit


# ── Node: collect_baselines ─────────────────────────────────────


class TestCollectBaselinesNode:
    @pytest.mark.asyncio
    async def test_returns_expected_keys(self, base_state: PredictionState):
        result = await collect_baselines(base_state)
        assert "prediction_start" in result
        assert "reasoning_chain" in result
        assert result["current_step"] == "collect_baselines"

    @pytest.mark.asyncio
    async def test_reasoning_chain_has_step_entry(self, base_state: PredictionState):
        result = await collect_baselines(base_state)
        chain = result["reasoning_chain"]
        assert len(chain) == 1
        assert chain[0]["step"] == "collect_baselines"
        assert "resources_checked" in chain[0]
        assert "duration_ms" in chain[0]

    @pytest.mark.asyncio
    async def test_uses_default_resource_when_empty(self):
        state = PredictionState(prediction_id="pred-empty", target_resources=[])
        result = await collect_baselines(state)
        # Should still succeed with the "default" fallback
        assert result["reasoning_chain"][0]["resources_checked"] >= 1

    @pytest.mark.asyncio
    async def test_prediction_start_is_set(self, base_state: PredictionState):
        before = datetime.now(UTC)
        result = await collect_baselines(base_state)
        after = datetime.now(UTC)
        assert before <= result["prediction_start"] <= after


# ── Node: detect_trends ─────────────────────────────────────────


class TestDetectTrendsNode:
    @pytest.mark.asyncio
    async def test_no_detector_returns_empty_anomalies(self, base_state: PredictionState):
        result = await detect_trends(base_state)
        assert result["trend_anomalies"] == []
        assert result["current_step"] == "detect_trends"

    @pytest.mark.asyncio
    async def test_with_detector_returns_anomalies(self, mock_toolkit: PredictionToolkit):
        # Use a single-resource state so the detector returns exactly 1 anomaly
        state = PredictionState(
            prediction_id="pred-single",
            target_resources=["svc-api-01"],
        )
        set_toolkit(mock_toolkit)
        result = await detect_trends(state)
        assert len(result["trend_anomalies"]) == 1
        assert result["trend_anomalies"][0].metric_name == "cpu_usage"

    @pytest.mark.asyncio
    async def test_with_detector_multiple_resources(
        self, base_state: PredictionState, mock_toolkit: PredictionToolkit
    ):
        # base_state has 2 resources; detector returns 1 anomaly per resource
        set_toolkit(mock_toolkit)
        result = await detect_trends(base_state)
        assert len(result["trend_anomalies"]) == 2

    @pytest.mark.asyncio
    async def test_appends_to_reasoning_chain(self, base_state: PredictionState):
        base_state.reasoning_chain = [{"step": "collect_baselines", "resources_checked": 2}]
        result = await detect_trends(base_state)
        assert len(result["reasoning_chain"]) == 2
        assert result["reasoning_chain"][1]["step"] == "detect_trends"
        assert "anomalies_found" in result["reasoning_chain"][1]


# ── Node: correlate_changes ─────────────────────────────────────


class TestCorrelateChangesNode:
    @pytest.mark.asyncio
    async def test_no_tracker_returns_empty_correlations(self, base_state: PredictionState):
        result = await correlate_changes(base_state)
        assert result["correlated_changes"] == []
        assert result["current_step"] == "correlate_changes"

    @pytest.mark.asyncio
    async def test_with_tracker_returns_correlations(
        self, base_state: PredictionState, mock_toolkit: PredictionToolkit
    ):
        set_toolkit(mock_toolkit)
        result = await correlate_changes(base_state)
        assert len(result["correlated_changes"]) == 1
        assert result["correlated_changes"][0].change_type == "deployment"

    @pytest.mark.asyncio
    async def test_uses_state_lookback_hours(self, mock_toolkit: PredictionToolkit):
        set_toolkit(mock_toolkit)
        state = PredictionState(lookback_hours=6)
        await correlate_changes(state)
        mock_toolkit._change_tracker.get_recent.assert_called_once_with(hours=6)

    @pytest.mark.asyncio
    async def test_appends_to_reasoning_chain(self, base_state: PredictionState):
        base_state.reasoning_chain = [{"step": "detect_trends"}]
        result = await correlate_changes(base_state)
        assert len(result["reasoning_chain"]) == 2
        assert result["reasoning_chain"][1]["step"] == "correlate_changes"
        assert "changes_found" in result["reasoning_chain"][1]


# ── Node: assess_risk ───────────────────────────────────────────


class TestAssessRiskNode:
    @pytest.mark.asyncio
    async def test_zero_anomalies_zero_changes_gives_zero_risk(self):
        state = PredictionState()
        result = await assess_risk(state)
        assert result["risk_score"] == pytest.approx(0.0)
        assert result["current_step"] == "assess_risk"

    @pytest.mark.asyncio
    async def test_single_anomaly_no_high_deviation(self, sample_anomaly: TrendAnomaly):
        # deviation_percent=60 > 50, so high_deviation boost applies
        state = PredictionState(trend_anomalies=[sample_anomaly])
        result = await assess_risk(state)
        # anomaly_score = min(1*0.15, 0.6) = 0.15, then +0.2 = 0.35
        # change_score = 0
        assert result["risk_score"] == pytest.approx(0.35)

    @pytest.mark.asyncio
    async def test_low_deviation_anomaly_no_boost(self):
        low_anomaly = TrendAnomaly(metric_name="cpu", deviation_percent=30.0)
        state = PredictionState(trend_anomalies=[low_anomaly])
        result = await assess_risk(state)
        # anomaly_score = 0.15, no high_deviation boost (30 <= 50)
        assert result["risk_score"] == pytest.approx(0.15)

    @pytest.mark.asyncio
    async def test_many_anomalies_capped_at_max(self):
        anomalies = [TrendAnomaly(metric_name=f"m{i}", deviation_percent=10.0) for i in range(10)]
        state = PredictionState(trend_anomalies=anomalies)
        result = await assess_risk(state)
        # anomaly_score = min(10*0.15, 0.6) = 0.6, no high_deviation boost
        assert result["risk_score"] == pytest.approx(0.6)

    @pytest.mark.asyncio
    async def test_changes_contribute_to_risk(self, sample_change: CorrelatedChange):
        state = PredictionState(correlated_changes=[sample_change])
        result = await assess_risk(state)
        # anomaly_score=0, change_score = min(1*0.1, 0.4) = 0.1
        assert result["risk_score"] == pytest.approx(0.1)

    @pytest.mark.asyncio
    async def test_combined_anomalies_and_changes(
        self, sample_anomaly: TrendAnomaly, sample_change: CorrelatedChange
    ):
        state = PredictionState(
            trend_anomalies=[sample_anomaly],
            correlated_changes=[sample_change],
        )
        result = await assess_risk(state)
        # anomaly_score = 0.15 + 0.2 (high dev boost) = 0.35
        # change_score = 0.1
        assert result["risk_score"] == pytest.approx(0.45)

    @pytest.mark.asyncio
    async def test_risk_capped_at_one(self):
        anomalies = [TrendAnomaly(metric_name=f"m{i}", deviation_percent=90.0) for i in range(10)]
        changes = [CorrelatedChange() for _ in range(10)]
        state = PredictionState(trend_anomalies=anomalies, correlated_changes=changes)
        result = await assess_risk(state)
        assert result["risk_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_reasoning_chain_includes_contributions(self):
        state = PredictionState(reasoning_chain=[{"step": "correlate_changes"}])
        result = await assess_risk(state)
        chain = result["reasoning_chain"]
        risk_step = chain[-1]
        assert risk_step["step"] == "assess_risk"
        assert "risk_score" in risk_step
        assert "anomaly_contribution" in risk_step
        assert "change_contribution" in risk_step


# ── Node: generate_predictions ──────────────────────────────────


class TestGeneratePredictionsNode:
    @pytest.mark.asyncio
    async def test_no_anomalies_low_risk_generates_nothing(self):
        state = PredictionState(risk_score=0.1, prediction_start=datetime.now(UTC))
        result = await generate_predictions(state)
        assert result["predictions"] == []
        assert result["current_step"] == "complete"

    @pytest.mark.asyncio
    async def test_anomaly_generates_prediction(self, sample_anomaly: TrendAnomaly):
        state = PredictionState(
            trend_anomalies=[sample_anomaly],
            risk_score=0.5,
            prediction_start=datetime.now(UTC),
        )
        result = await generate_predictions(state)
        preds = result["predictions"]
        assert len(preds) == 1
        assert preds[0].severity == PredictionSeverity.HIGH  # deviation_percent=60 > 50
        assert "cpu_usage" in preds[0].title
        assert preds[0].id.startswith("pred-")

    @pytest.mark.parametrize(
        "deviation,expected_severity",
        [
            (10.0, PredictionSeverity.LOW),
            (30.0, PredictionSeverity.MEDIUM),
            (60.0, PredictionSeverity.HIGH),
            (90.0, PredictionSeverity.CRITICAL),
        ],
    )
    @pytest.mark.asyncio
    async def test_severity_levels_by_deviation(
        self, deviation: float, expected_severity: PredictionSeverity
    ):
        anomaly = TrendAnomaly(
            metric_name="cpu",
            resource_id="svc-x",
            deviation_percent=deviation,
        )
        state = PredictionState(
            trend_anomalies=[anomaly],
            risk_score=0.5,
            prediction_start=datetime.now(UTC),
        )
        result = await generate_predictions(state)
        assert result["predictions"][0].severity == expected_severity

    @pytest.mark.asyncio
    async def test_confidence_calculation(self):
        anomaly = TrendAnomaly(metric_name="cpu", deviation_percent=100.0)
        state = PredictionState(
            trend_anomalies=[anomaly],
            prediction_start=datetime.now(UTC),
        )
        result = await generate_predictions(state)
        # confidence = min(0.5 + 100/200, 0.95) = min(1.0, 0.95) = 0.95
        assert result["predictions"][0].confidence == pytest.approx(0.95)

    @pytest.mark.asyncio
    async def test_confidence_low_deviation(self):
        anomaly = TrendAnomaly(metric_name="cpu", deviation_percent=20.0)
        state = PredictionState(
            trend_anomalies=[anomaly],
            prediction_start=datetime.now(UTC),
        )
        result = await generate_predictions(state)
        # confidence = min(0.5 + 20/200, 0.95) = 0.6
        assert result["predictions"][0].confidence == pytest.approx(0.6)

    @pytest.mark.asyncio
    async def test_elevated_risk_no_anomalies_generates_summary_prediction(self):
        state = PredictionState(
            risk_score=0.6,
            trend_anomalies=[],
            correlated_changes=[CorrelatedChange()],
            prediction_start=datetime.now(UTC),
        )
        result = await generate_predictions(state)
        preds = result["predictions"]
        assert len(preds) == 1
        assert preds[0].title == "Elevated system risk detected"
        assert preds[0].severity == PredictionSeverity.MEDIUM
        assert preds[0].confidence == pytest.approx(0.6)

    @pytest.mark.asyncio
    async def test_risk_below_threshold_no_anomalies_no_predictions(self):
        state = PredictionState(
            risk_score=0.4,
            trend_anomalies=[],
            prediction_start=datetime.now(UTC),
        )
        result = await generate_predictions(state)
        assert result["predictions"] == []

    @pytest.mark.asyncio
    async def test_anomaly_without_resource_id_omits_from_affected(self):
        anomaly = TrendAnomaly(metric_name="error_rate", resource_id="")
        state = PredictionState(
            trend_anomalies=[anomaly],
            prediction_start=datetime.now(UTC),
        )
        result = await generate_predictions(state)
        assert result["predictions"][0].affected_resources == []

    @pytest.mark.asyncio
    async def test_prediction_duration_calculated(self):
        start = datetime.now(UTC)
        state = PredictionState(prediction_start=start)
        result = await generate_predictions(state)
        assert result["prediction_duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_no_prediction_start_uses_step_duration(self):
        state = PredictionState(prediction_start=None)
        result = await generate_predictions(state)
        assert result["prediction_duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_multiple_anomalies_generate_multiple_predictions(self):
        anomalies = [
            TrendAnomaly(metric_name="cpu", resource_id="svc-a", deviation_percent=40.0),
            TrendAnomaly(metric_name="mem", resource_id="svc-b", deviation_percent=70.0),
        ]
        state = PredictionState(
            trend_anomalies=anomalies,
            prediction_start=datetime.now(UTC),
        )
        result = await generate_predictions(state)
        assert len(result["predictions"]) == 2

    @pytest.mark.asyncio
    async def test_reasoning_chain_records_predictions_generated(self):
        state = PredictionState(
            reasoning_chain=[{"step": "assess_risk"}],
            prediction_start=datetime.now(UTC),
        )
        result = await generate_predictions(state)
        last_step = result["reasoning_chain"][-1]
        assert last_step["step"] == "generate_predictions"
        assert last_step["predictions_generated"] == 0


# ── Graph Conditional: should_generate ──────────────────────────


class TestShouldGenerate:
    def test_error_state_returns_end(self):
        state = PredictionState(error="boom")
        result = should_generate(state)
        assert result == "__end__"

    def test_risk_above_threshold_returns_generate(self):
        state = PredictionState(risk_score=0.5)
        result = should_generate(state)
        assert result == "generate_predictions"

    def test_has_anomalies_returns_generate(self, sample_anomaly: TrendAnomaly):
        state = PredictionState(
            risk_score=0.0,
            trend_anomalies=[sample_anomaly],
        )
        result = should_generate(state)
        assert result == "generate_predictions"

    def test_low_risk_no_anomalies_returns_end(self):
        state = PredictionState(risk_score=0.05, trend_anomalies=[])
        result = should_generate(state)
        assert result == "__end__"

    def test_risk_exactly_at_threshold(self):
        # risk_score=0.1 is NOT > 0.1, so should return END
        state = PredictionState(risk_score=0.1, trend_anomalies=[])
        result = should_generate(state)
        assert result == "__end__"


# ── PredictionRunner ────────────────────────────────────────────


class TestPredictionRunner:
    @pytest.mark.asyncio
    async def test_predict_success(self):
        """Test full predict flow by mocking the compiled graph."""
        mock_app = AsyncMock()
        final_state = PredictionState(
            prediction_id="pred-abc",
            current_step="complete",
            risk_score=0.4,
            predictions=[Prediction(id="pred-001", title="CPU spike", confidence=0.8)],
            prediction_start=datetime.now(UTC),
        ).model_dump()
        mock_app.ainvoke.return_value = final_state

        with patch("shieldops.agents.prediction.runner.create_prediction_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph

            runner = PredictionRunner()
            result = await runner.predict(
                target_resources=["svc-api-01"],
                lookback_hours=12,
            )

        assert isinstance(result, PredictionState)
        assert result.current_step == "complete"
        assert len(result.predictions) == 1

    @pytest.mark.asyncio
    async def test_predict_handles_exception(self):
        """When the graph raises, predict should return an error state."""
        mock_app = AsyncMock()
        mock_app.ainvoke.side_effect = RuntimeError("Graph exploded")

        with patch("shieldops.agents.prediction.runner.create_prediction_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph

            runner = PredictionRunner()
            result = await runner.predict(target_resources=["svc-x"])

        assert result.error == "Graph exploded"
        assert result.current_step == "failed"

    def test_get_prediction_found(self):
        with patch("shieldops.agents.prediction.runner.create_prediction_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph

            runner = PredictionRunner()
            state = PredictionState(prediction_id="pred-abc")
            runner._predictions["pred-abc"] = state
            result = runner.get_prediction("pred-abc")
            assert result is state

    def test_get_prediction_not_found(self):
        with patch("shieldops.agents.prediction.runner.create_prediction_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph

            runner = PredictionRunner()
            assert runner.get_prediction("pred-nonexistent") is None

    def test_list_predictions_empty(self):
        with patch("shieldops.agents.prediction.runner.create_prediction_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph

            runner = PredictionRunner()
            assert runner.list_predictions() == []

    def test_list_predictions_returns_summaries(self):
        with patch("shieldops.agents.prediction.runner.create_prediction_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph

            runner = PredictionRunner()
            runner._predictions["pred-1"] = PredictionState(
                prediction_id="pred-1",
                current_step="complete",
                risk_score=0.5,
                predictions=[Prediction(id="p1", confidence=0.8)],
                prediction_duration_ms=120,
            )
            runner._predictions["pred-2"] = PredictionState(
                prediction_id="pred-2",
                current_step="failed",
                error="timeout",
            )
            summaries = runner.list_predictions()
            assert len(summaries) == 2

            complete = next(s for s in summaries if s["prediction_id"] == "pred-1")
            assert complete["status"] == "complete"
            assert complete["predictions_count"] == 1
            assert complete["risk_score"] == pytest.approx(0.5)
            assert complete["duration_ms"] == 120
            assert complete["error"] is None

            failed = next(s for s in summaries if s["prediction_id"] == "pred-2")
            assert failed["status"] == "failed"
            assert failed["error"] == "timeout"

    def test_get_active_predictions_filters_by_confidence(self):
        with patch("shieldops.agents.prediction.runner.create_prediction_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph

            runner = PredictionRunner()
            runner._predictions["pred-1"] = PredictionState(
                predictions=[
                    Prediction(id="p1", confidence=0.9, title="High confidence"),
                    Prediction(id="p2", confidence=0.3, title="Low confidence"),
                    Prediction(id="p3", confidence=0.6, title="Medium confidence"),
                ]
            )
            active = runner.get_active_predictions(min_confidence=0.5)
            assert len(active) == 2
            # Should be sorted by confidence descending
            assert active[0]["confidence"] == pytest.approx(0.9)
            assert active[1]["confidence"] == pytest.approx(0.6)

    def test_get_active_predictions_default_min_confidence(self):
        with patch("shieldops.agents.prediction.runner.create_prediction_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph

            runner = PredictionRunner()
            runner._predictions["pred-1"] = PredictionState(
                predictions=[
                    Prediction(id="p1", confidence=0.5, title="Exactly at threshold"),
                    Prediction(id="p2", confidence=0.49, title="Below threshold"),
                ]
            )
            active = runner.get_active_predictions()
            assert len(active) == 1
            assert active[0]["id"] == "p1"

    def test_get_active_predictions_empty_when_no_predictions(self):
        with patch("shieldops.agents.prediction.runner.create_prediction_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph

            runner = PredictionRunner()
            assert runner.get_active_predictions() == []

    def test_get_active_predictions_across_multiple_cycles(self):
        with patch("shieldops.agents.prediction.runner.create_prediction_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph

            runner = PredictionRunner()
            runner._predictions["pred-1"] = PredictionState(
                predictions=[Prediction(id="p1", confidence=0.7)]
            )
            runner._predictions["pred-2"] = PredictionState(
                predictions=[Prediction(id="p2", confidence=0.85)]
            )
            active = runner.get_active_predictions(min_confidence=0.5)
            assert len(active) == 2
            # Highest confidence first
            assert active[0]["id"] == "p2"
            assert active[1]["id"] == "p1"
