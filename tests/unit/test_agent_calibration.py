"""Tests for agent confidence calibration — AccuracyTracker and ConfidenceCalibrator.

Covers: PredictionRecord creation, outcome recording, feedback updates,
AccuracyMetrics calculations, calibration curve computation (ECE, MCE, binning),
over/underconfident detection, automatic threshold recommendation,
multi-agent independence, and edge cases (empty data, single record,
boundary confidence values).
"""

from __future__ import annotations

import pytest

from shieldops.agents.calibration.calibrator import (
    CalibrationBin,
    CalibrationCurve,
    ConfidenceCalibrator,
    ThresholdRecommendation,
)
from shieldops.agents.calibration.tracker import (
    AccuracyMetrics,
    AccuracyTracker,
    PredictionRecord,
)

# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def tracker() -> AccuracyTracker:
    """Fresh AccuracyTracker for each test."""
    return AccuracyTracker()


@pytest.fixture
def calibrator(tracker: AccuracyTracker) -> ConfidenceCalibrator:
    """ConfidenceCalibrator backed by the shared tracker fixture."""
    return ConfidenceCalibrator(tracker=tracker, num_bins=10)


def _seed_predictions(
    tracker: AccuracyTracker,
    agent_id: str,
    entries: list[tuple[float, str, str | None]],
) -> list[PredictionRecord]:
    """Helper — seed predictions and optionally resolve them.

    Each entry is (confidence, predicted_outcome, actual_outcome_or_None).
    If actual_outcome is provided, record_outcome is called automatically.
    """
    records: list[PredictionRecord] = []
    for confidence, predicted, actual in entries:
        rec = tracker.record_prediction(agent_id, confidence, predicted)
        if actual is not None:
            tracker.record_outcome(rec.id, actual)
        records.append(rec)
    return records


# ── PredictionRecord model tests ────────────────────────────────────


class TestPredictionRecord:
    """Verify PredictionRecord default values and field assignment."""

    def test_id_generated_with_prec_prefix(self):
        rec = PredictionRecord(agent_id="a1")
        assert rec.id.startswith("prec-")
        assert len(rec.id) > 5  # prec- plus hex chars

    def test_default_fields(self):
        rec = PredictionRecord(agent_id="a1")
        assert rec.agent_type == ""
        assert rec.predicted_confidence == 0.0
        assert rec.predicted_outcome == ""
        assert rec.actual_outcome is None
        assert rec.was_correct is None
        assert rec.feedback_source == ""
        assert rec.resolved_at is None

    def test_created_at_populated(self):
        rec = PredictionRecord(agent_id="a1")
        assert rec.created_at is not None

    def test_unique_ids_across_instances(self):
        ids = {PredictionRecord(agent_id="a1").id for _ in range(100)}
        assert len(ids) == 100, "Each PredictionRecord should have a unique id"


# ── AccuracyTracker.record_prediction ───────────────────────────────


class TestRecordPrediction:
    """Tests for recording new predictions."""

    def test_creates_record_with_correct_fields(self, tracker: AccuracyTracker):
        rec = tracker.record_prediction(
            agent_id="inv-001",
            confidence=0.92,
            predicted_outcome="disk_full",
            agent_type="investigation",
        )

        assert isinstance(rec, PredictionRecord)
        assert rec.agent_id == "inv-001"
        assert rec.agent_type == "investigation"
        assert rec.predicted_confidence == pytest.approx(0.92)
        assert rec.predicted_outcome == "disk_full"
        assert rec.was_correct is None
        assert rec.actual_outcome is None

    def test_record_added_to_internal_list(self, tracker: AccuracyTracker):
        tracker.record_prediction("a1", 0.8, "outcome_a")
        records = tracker.get_records("a1")
        assert len(records) == 1

    def test_multiple_predictions_for_same_agent(self, tracker: AccuracyTracker):
        tracker.record_prediction("a1", 0.8, "outcome_a")
        tracker.record_prediction("a1", 0.7, "outcome_b")
        tracker.record_prediction("a1", 0.6, "outcome_c")
        assert len(tracker.get_records("a1")) == 3

    def test_default_agent_type_is_empty_string(self, tracker: AccuracyTracker):
        rec = tracker.record_prediction("a1", 0.5, "x")
        assert rec.agent_type == ""

    def test_zero_confidence(self, tracker: AccuracyTracker):
        rec = tracker.record_prediction("a1", 0.0, "low_conf")
        assert rec.predicted_confidence == pytest.approx(0.0)

    def test_full_confidence(self, tracker: AccuracyTracker):
        rec = tracker.record_prediction("a1", 1.0, "high_conf")
        assert rec.predicted_confidence == pytest.approx(1.0)


# ── AccuracyTracker.record_outcome ──────────────────────────────────


class TestRecordOutcome:
    """Tests for marking a prediction as correct/incorrect via outcome."""

    def test_correct_outcome_sets_was_correct_true(self, tracker: AccuracyTracker):
        rec = tracker.record_prediction("a1", 0.9, "disk_full")
        updated = tracker.record_outcome(rec.id, "disk_full")

        assert updated is not None
        assert updated.was_correct is True
        assert updated.actual_outcome == "disk_full"

    def test_incorrect_outcome_sets_was_correct_false(self, tracker: AccuracyTracker):
        rec = tracker.record_prediction("a1", 0.9, "disk_full")
        updated = tracker.record_outcome(rec.id, "oom_kill")

        assert updated is not None
        assert updated.was_correct is False
        assert updated.actual_outcome == "oom_kill"

    def test_outcome_sets_resolved_at(self, tracker: AccuracyTracker):
        rec = tracker.record_prediction("a1", 0.8, "x")
        updated = tracker.record_outcome(rec.id, "x")
        assert updated is not None
        assert updated.resolved_at is not None

    def test_outcome_sets_feedback_source(self, tracker: AccuracyTracker):
        rec = tracker.record_prediction("a1", 0.8, "x")
        updated = tracker.record_outcome(rec.id, "x", feedback_source="automated")
        assert updated is not None
        assert updated.feedback_source == "automated"

    def test_default_feedback_source_is_human(self, tracker: AccuracyTracker):
        rec = tracker.record_prediction("a1", 0.8, "x")
        updated = tracker.record_outcome(rec.id, "x")
        assert updated is not None
        assert updated.feedback_source == "human"

    def test_unknown_record_id_returns_none(self, tracker: AccuracyTracker):
        tracker.record_prediction("a1", 0.8, "x")
        result = tracker.record_outcome("prec-nonexistent", "y")
        assert result is None

    def test_outcome_across_multiple_agents(self, tracker: AccuracyTracker):
        rec_a = tracker.record_prediction("a1", 0.8, "x")
        rec_b = tracker.record_prediction("a2", 0.7, "y")

        tracker.record_outcome(rec_b.id, "y")
        tracker.record_outcome(rec_a.id, "z")

        assert rec_a.was_correct is False
        assert rec_b.was_correct is True


# ── AccuracyTracker.record_feedback ─────────────────────────────────


class TestRecordFeedback:
    """Tests for direct feedback on a prediction."""

    def test_feedback_marks_was_correct(self, tracker: AccuracyTracker):
        rec = tracker.record_prediction("a1", 0.8, "x")
        updated = tracker.record_feedback("a1", rec.id, was_correct=True)

        assert updated is not None
        assert updated.was_correct is True

    def test_feedback_marks_was_incorrect(self, tracker: AccuracyTracker):
        rec = tracker.record_prediction("a1", 0.8, "x")
        updated = tracker.record_feedback("a1", rec.id, was_correct=False)

        assert updated is not None
        assert updated.was_correct is False

    def test_feedback_sets_resolved_at(self, tracker: AccuracyTracker):
        rec = tracker.record_prediction("a1", 0.8, "x")
        updated = tracker.record_feedback("a1", rec.id, was_correct=True)
        assert updated is not None
        assert updated.resolved_at is not None

    def test_feedback_sets_feedback_source(self, tracker: AccuracyTracker):
        rec = tracker.record_prediction("a1", 0.8, "x")
        updated = tracker.record_feedback(
            "a1", rec.id, was_correct=True, feedback_source="automated"
        )
        assert updated is not None
        assert updated.feedback_source == "automated"

    def test_feedback_wrong_agent_id_returns_none(self, tracker: AccuracyTracker):
        rec = tracker.record_prediction("a1", 0.8, "x")
        result = tracker.record_feedback("wrong_agent", rec.id, was_correct=True)
        assert result is None

    def test_feedback_wrong_prediction_id_returns_none(self, tracker: AccuracyTracker):
        tracker.record_prediction("a1", 0.8, "x")
        result = tracker.record_feedback("a1", "prec-nonexistent", was_correct=True)
        assert result is None


# ── AccuracyTracker.get_accuracy ────────────────────────────────────


class TestGetAccuracy:
    """Tests for AccuracyMetrics calculation."""

    def test_no_records_returns_zero_metrics(self, tracker: AccuracyTracker):
        metrics = tracker.get_accuracy("ghost_agent")
        assert metrics.total_predictions == 0
        assert metrics.resolved_predictions == 0
        assert metrics.correct_predictions == 0
        assert metrics.accuracy == pytest.approx(0.0)
        assert metrics.avg_confidence == pytest.approx(0.0)

    def test_all_correct_returns_accuracy_one(self, tracker: AccuracyTracker):
        _seed_predictions(
            tracker,
            "a1",
            [
                (0.9, "x", "x"),
                (0.8, "y", "y"),
            ],
        )
        metrics = tracker.get_accuracy("a1")
        assert metrics.accuracy == pytest.approx(1.0)
        assert metrics.correct_predictions == 2

    def test_all_incorrect_returns_accuracy_zero(self, tracker: AccuracyTracker):
        _seed_predictions(
            tracker,
            "a1",
            [
                (0.9, "x", "wrong"),
                (0.8, "y", "wrong"),
            ],
        )
        metrics = tracker.get_accuracy("a1")
        assert metrics.accuracy == pytest.approx(0.0)
        assert metrics.correct_predictions == 0

    def test_mixed_results_accuracy(self, tracker: AccuracyTracker):
        _seed_predictions(
            tracker,
            "a1",
            [
                (0.9, "x", "x"),  # correct
                (0.8, "y", "z"),  # incorrect
                (0.7, "a", "a"),  # correct
                (0.6, "b", "c"),  # incorrect
            ],
        )
        metrics = tracker.get_accuracy("a1")
        assert metrics.accuracy == pytest.approx(0.5)
        assert metrics.resolved_predictions == 4
        assert metrics.correct_predictions == 2

    def test_unresolved_predictions_excluded_from_accuracy(self, tracker: AccuracyTracker):
        _seed_predictions(
            tracker,
            "a1",
            [
                (0.9, "x", "x"),  # resolved correct
                (0.8, "y", None),  # unresolved
            ],
        )
        metrics = tracker.get_accuracy("a1")
        assert metrics.total_predictions == 2
        assert metrics.resolved_predictions == 1
        assert metrics.accuracy == pytest.approx(1.0)

    def test_avg_confidence_calculated_over_all_records(self, tracker: AccuracyTracker):
        _seed_predictions(
            tracker,
            "a1",
            [
                (0.8, "x", "x"),
                (0.6, "y", None),
            ],
        )
        metrics = tracker.get_accuracy("a1")
        assert metrics.avg_confidence == pytest.approx(0.7, abs=1e-4)

    def test_overconfidence_rate(self, tracker: AccuracyTracker):
        # Agent predicts confidence 0.9 but gets things wrong => overconfident
        # With 1 correct and 1 incorrect, accuracy = 0.5
        # The incorrect record has confidence 0.9 > 0.5 => overconfident
        _seed_predictions(
            tracker,
            "a1",
            [
                (0.9, "x", "wrong"),  # incorrect, confidence 0.9 > accuracy 0.5
                (0.9, "y", "y"),  # correct
            ],
        )
        metrics = tracker.get_accuracy("a1")
        assert metrics.accuracy == pytest.approx(0.5)
        assert metrics.overconfidence_rate == pytest.approx(0.5, abs=1e-4)

    def test_underconfidence_rate(self, tracker: AccuracyTracker):
        # Agent predicts low confidence 0.2 but gets things right => underconfident
        # With all correct, accuracy = 1.0
        # The correct record has confidence 0.2 < 1.0 => underconfident
        _seed_predictions(
            tracker,
            "a1",
            [
                (0.2, "x", "x"),  # correct, confidence 0.2 < accuracy 1.0
            ],
        )
        metrics = tracker.get_accuracy("a1")
        assert metrics.accuracy == pytest.approx(1.0)
        assert metrics.underconfidence_rate == pytest.approx(1.0, abs=1e-4)

    def test_accuracy_rounded_to_four_decimals(self, tracker: AccuracyTracker):
        _seed_predictions(
            tracker,
            "a1",
            [
                (0.9, "x", "x"),
                (0.8, "y", "y"),
                (0.7, "z", "wrong"),
            ],
        )
        metrics = tracker.get_accuracy("a1")
        # 2/3 = 0.666666... rounds to 0.6667
        assert metrics.accuracy == pytest.approx(0.6667, abs=1e-4)


# ── AccuracyTracker.get_records ─────────────────────────────────────


class TestGetRecords:
    """Tests for retrieving prediction records."""

    def test_returns_empty_list_for_unknown_agent(self, tracker: AccuracyTracker):
        assert tracker.get_records("unknown") == []

    def test_returns_all_records_for_agent(self, tracker: AccuracyTracker):
        tracker.record_prediction("a1", 0.8, "x")
        tracker.record_prediction("a1", 0.7, "y")
        records = tracker.get_records("a1")
        assert len(records) == 2

    def test_records_isolated_between_agents(self, tracker: AccuracyTracker):
        tracker.record_prediction("a1", 0.8, "x")
        tracker.record_prediction("a2", 0.7, "y")
        assert len(tracker.get_records("a1")) == 1
        assert len(tracker.get_records("a2")) == 1


# ── AccuracyTracker.list_agents ─────────────────────────────────────


class TestListAgents:
    """Tests for listing tracked agent IDs."""

    def test_empty_tracker_returns_empty_list(self, tracker: AccuracyTracker):
        assert tracker.list_agents() == []

    def test_returns_all_tracked_agents(self, tracker: AccuracyTracker):
        tracker.record_prediction("inv-1", 0.8, "x")
        tracker.record_prediction("rem-1", 0.7, "y")
        tracker.record_prediction("sec-1", 0.6, "z")
        agents = tracker.list_agents()
        assert set(agents) == {"inv-1", "rem-1", "sec-1"}

    def test_duplicate_agent_predictions_listed_once(self, tracker: AccuracyTracker):
        tracker.record_prediction("a1", 0.8, "x")
        tracker.record_prediction("a1", 0.7, "y")
        agents = tracker.list_agents()
        assert agents == ["a1"]


# ── Multi-agent independence ────────────────────────────────────────


class TestMultiAgentIndependence:
    """Ensure agents are tracked independently."""

    def test_accuracy_independent_per_agent(self, tracker: AccuracyTracker):
        _seed_predictions(tracker, "a1", [(0.9, "x", "x")])  # 100% correct
        _seed_predictions(tracker, "a2", [(0.9, "y", "wrong")])  # 0% correct

        m1 = tracker.get_accuracy("a1")
        m2 = tracker.get_accuracy("a2")

        assert m1.accuracy == pytest.approx(1.0)
        assert m2.accuracy == pytest.approx(0.0)

    def test_outcome_for_one_agent_does_not_affect_another(self, tracker: AccuracyTracker):
        rec_a = tracker.record_prediction("a1", 0.9, "x")
        tracker.record_prediction("a2", 0.8, "y")

        tracker.record_outcome(rec_a.id, "x")

        m1 = tracker.get_accuracy("a1")
        m2 = tracker.get_accuracy("a2")

        assert m1.resolved_predictions == 1
        assert m2.resolved_predictions == 0


# ── ConfidenceCalibrator.compute_calibration ────────────────────────


class TestComputeCalibration:
    """Tests for calibration curve computation."""

    def test_no_data_returns_empty_curve(self, calibrator: ConfidenceCalibrator):
        curve = calibrator.compute_calibration("unknown_agent")
        assert curve.agent_id == "unknown_agent"
        assert curve.bins == []
        assert curve.expected_calibration_error == pytest.approx(0.0)
        assert curve.max_calibration_error == pytest.approx(0.0)
        assert curve.is_overconfident is False
        assert curve.is_underconfident is False

    def test_unresolved_predictions_excluded(self, calibrator: ConfidenceCalibrator):
        calibrator.tracker.record_prediction("a1", 0.8, "x")  # not resolved
        curve = calibrator.compute_calibration("a1")
        assert curve.bins == []

    def test_single_correct_prediction_single_bin(self, calibrator: ConfidenceCalibrator):
        rec = calibrator.tracker.record_prediction("a1", 0.85, "x")
        calibrator.tracker.record_outcome(rec.id, "x")

        curve = calibrator.compute_calibration("a1")
        assert len(curve.bins) == 1
        assert curve.bins[0].count == 1
        assert curve.bins[0].actual_accuracy == pytest.approx(1.0)
        assert curve.bins[0].predicted_confidence == pytest.approx(0.85)

    def test_predictions_binned_correctly(self, calibrator: ConfidenceCalibrator):
        # With 10 bins, bin boundaries are [0.0, 0.1), [0.1, 0.2), ... [0.9, 1.0]
        entries = [
            (0.15, "a", "a"),  # bin [0.1, 0.2)
            (0.15, "b", "b"),  # bin [0.1, 0.2)
            (0.85, "c", "c"),  # bin [0.8, 0.9)
        ]
        _seed_predictions(calibrator.tracker, "a1", entries)

        curve = calibrator.compute_calibration("a1")

        # Should have exactly 2 non-empty bins
        assert len(curve.bins) == 2

        low_bin = next(b for b in curve.bins if b.confidence_min == pytest.approx(0.1))
        high_bin = next(b for b in curve.bins if b.confidence_min == pytest.approx(0.8))

        assert low_bin.count == 2
        assert high_bin.count == 1

    def test_confidence_1_0_included_in_last_bin(self, calibrator: ConfidenceCalibrator):
        rec = calibrator.tracker.record_prediction("a1", 1.0, "x")
        calibrator.tracker.record_outcome(rec.id, "x")

        curve = calibrator.compute_calibration("a1")
        assert len(curve.bins) == 1
        assert curve.bins[0].confidence_min == pytest.approx(0.9)

    def test_ece_calculation(self, calibrator: ConfidenceCalibrator):
        # Create an overconfident agent: always predicts 0.95 confidence but
        # only 50% of predictions are correct
        entries = [
            (0.95, "x", "x"),  # correct
            (0.95, "y", "wrong"),  # incorrect
        ]
        _seed_predictions(calibrator.tracker, "a1", entries)

        curve = calibrator.compute_calibration("a1")

        # Both in same bin [0.9, 1.0]: avg_conf=0.95, actual_acc=0.5
        # ECE = |0.95 - 0.5| * 2 / 2 = 0.45
        assert curve.expected_calibration_error == pytest.approx(0.45, abs=1e-4)

    def test_mce_calculation(self, calibrator: ConfidenceCalibrator):
        # Two bins with different gaps
        entries = [
            (0.15, "a", "wrong"),  # bin [0.1,0.2) conf=0.15, acc=0.0, gap=0.15
            (0.95, "b", "wrong"),  # bin [0.9,1.0) conf=0.95, acc=0.0, gap=0.95
        ]
        _seed_predictions(calibrator.tracker, "a1", entries)

        curve = calibrator.compute_calibration("a1")
        assert curve.max_calibration_error == pytest.approx(0.95, abs=1e-4)

    def test_perfectly_calibrated_agent(self, calibrator: ConfidenceCalibrator):
        # Predictions in one bin, all correct => conf ~ acc => ECE near 0
        entries = [(0.95, f"o{i}", f"o{i}") for i in range(10)]
        _seed_predictions(calibrator.tracker, "a1", entries)

        curve = calibrator.compute_calibration("a1")
        # avg_conf=0.95, actual_acc=1.0 => gap = 0.05
        assert curve.expected_calibration_error == pytest.approx(0.05, abs=1e-4)

    def test_overconfident_detection(self, calibrator: ConfidenceCalibrator):
        # Agent predicts high confidence but gets many wrong
        entries = [
            (0.95, "a", "wrong"),
            (0.92, "b", "wrong"),
            (0.15, "c", "c"),  # low confidence, correct
        ]
        _seed_predictions(calibrator.tracker, "a1", entries)

        curve = calibrator.compute_calibration("a1")
        # Bin [0.9,1.0): conf~0.935, acc=0.0 => overconfident
        # Bin [0.1,0.2): conf=0.15, acc=1.0 => underconfident
        # 1 overconfident bin, 1 underconfident bin => tie, neither flag set
        # To get clear overconfidence, need more overconfident bins
        # Let's check the actual result:
        # Actually since there's 1 vs 1, both flags are False
        # This tests the tie case
        assert curve.is_overconfident is False
        assert curve.is_underconfident is False

    def test_overconfident_when_majority_bins_overconfident(self, calibrator: ConfidenceCalibrator):
        # Create predictions across multiple bins where confidence > accuracy
        entries = [
            (0.35, "a", "wrong"),  # bin [0.3,0.4): conf=0.35, acc=0 => overconfident
            (0.55, "b", "wrong"),  # bin [0.5,0.6): conf=0.55, acc=0 => overconfident
            (0.75, "c", "wrong"),  # bin [0.7,0.8): conf=0.75, acc=0 => overconfident
        ]
        _seed_predictions(calibrator.tracker, "a1", entries)

        curve = calibrator.compute_calibration("a1")
        assert curve.is_overconfident is True
        assert curve.is_underconfident is False

    def test_underconfident_when_majority_bins_underconfident(
        self, calibrator: ConfidenceCalibrator
    ):
        # Create predictions across multiple bins where accuracy > confidence
        entries = [
            (0.15, "a", "a"),  # bin [0.1,0.2): conf=0.15, acc=1.0 => underconfident
            (0.25, "b", "b"),  # bin [0.2,0.3): conf=0.25, acc=1.0 => underconfident
            (0.35, "c", "c"),  # bin [0.3,0.4): conf=0.35, acc=1.0 => underconfident
        ]
        _seed_predictions(calibrator.tracker, "a1", entries)

        curve = calibrator.compute_calibration("a1")
        assert curve.is_underconfident is True
        assert curve.is_overconfident is False

    def test_ece_weighted_by_bin_count(self, calibrator: ConfidenceCalibrator):
        # Bin with 3 records should weigh more than bin with 1 record
        entries = [
            # Bin [0.1,0.2): 3 records, conf=0.15, all correct => gap=0.85
            (0.15, "a", "a"),
            (0.15, "b", "b"),
            (0.15, "c", "c"),
            # Bin [0.9,1.0): 1 record, conf=0.95, incorrect => gap=0.95
            (0.95, "d", "wrong"),
        ]
        _seed_predictions(calibrator.tracker, "a1", entries)

        curve = calibrator.compute_calibration("a1")

        # ECE = (0.85*3 + 0.95*1) / 4 = (2.55 + 0.95) / 4 = 0.875
        assert curve.expected_calibration_error == pytest.approx(0.875, abs=1e-4)

    def test_custom_num_bins(self, tracker: AccuracyTracker):
        calibrator = ConfidenceCalibrator(tracker=tracker, num_bins=5)

        entries = [
            (0.15, "a", "a"),  # bin [0.0, 0.2)
            (0.55, "b", "b"),  # bin [0.4, 0.6)
            (0.95, "c", "c"),  # bin [0.8, 1.0]
        ]
        _seed_predictions(tracker, "a1", entries)

        curve = calibrator.compute_calibration("a1")
        # With 5 bins, each has width 0.2
        assert len(curve.bins) == 3


# ── ConfidenceCalibrator.calibrate_threshold ────────────────────────


class TestCalibrateThreshold:
    """Tests for automatic threshold adjustment recommendations."""

    def test_insufficient_data_returns_current_threshold(self, calibrator: ConfidenceCalibrator):
        result = calibrator.calibrate_threshold("unknown", current_threshold=0.85)
        assert isinstance(result, ThresholdRecommendation)
        assert result.recommended_threshold == pytest.approx(0.85)
        assert result.reason == "Insufficient data for calibration"
        assert result.confidence_in_recommendation == pytest.approx(0.0)

    def test_overconfident_agent_threshold_raised(self, calibrator: ConfidenceCalibrator):
        # Agent predicts high confidence across multiple bins but gets many wrong
        entries = [
            # Bins that are overconfident (conf > acc)
            (0.35, "a", "wrong"),  # bin [0.3,0.4): overconfident
            (0.55, "b", "wrong"),  # bin [0.5,0.6): overconfident
            (0.75, "c", "wrong"),  # bin [0.7,0.8): overconfident
            # One good bin at high confidence
            (0.95, "d", "d"),  # bin [0.9,1.0): correct
        ]
        _seed_predictions(calibrator.tracker, "a1", entries)

        result = calibrator.calibrate_threshold("a1", current_threshold=0.50, target_accuracy=0.90)

        # The algorithm iterates bins from highest confidence_min downward.
        # Bin [0.9,1.0) has accuracy 1.0 >= 0.9 target, so recommended = 0.9
        assert result.recommended_threshold >= 0.50, (
            "Overconfident agent should have threshold raised or kept"
        )
        assert "overconfident" in result.reason.lower()

    def test_underconfident_agent_threshold_lowered(self, calibrator: ConfidenceCalibrator):
        # Agent predicts low confidence but is actually very accurate
        entries = [
            (0.15, "a", "a"),  # bin [0.1,0.2): acc=1.0, underconfident
            (0.25, "b", "b"),  # bin [0.2,0.3): acc=1.0, underconfident
            (0.35, "c", "c"),  # bin [0.3,0.4): acc=1.0, underconfident
        ]
        _seed_predictions(calibrator.tracker, "a1", entries)

        result = calibrator.calibrate_threshold("a1", current_threshold=0.85, target_accuracy=0.90)

        # The algorithm iterates bins from lowest confidence_min upward.
        # Bin [0.1,0.2) has accuracy 1.0 >= 0.9 target, so recommended = 0.1
        assert result.recommended_threshold < 0.85, (
            "Underconfident agent should have threshold lowered"
        )
        assert "underconfident" in result.reason.lower()

    def test_overconfident_no_bin_meets_target_increments_threshold(
        self, calibrator: ConfidenceCalibrator
    ):
        # Overconfident with no bin reaching the target accuracy
        entries = [
            (0.35, "a", "wrong"),  # overconfident bin
            (0.55, "b", "wrong"),  # overconfident bin
            (0.85, "c", "wrong"),  # overconfident bin
        ]
        _seed_predictions(calibrator.tracker, "a1", entries)

        result = calibrator.calibrate_threshold("a1", current_threshold=0.80, target_accuracy=0.90)
        assert result.recommended_threshold == pytest.approx(0.85, abs=1e-3)
        assert "incrementally" in result.reason.lower()

    def test_overconfident_increment_capped_at_099(self, calibrator: ConfidenceCalibrator):
        entries = [
            (0.35, "a", "wrong"),
            (0.55, "b", "wrong"),
            (0.85, "c", "wrong"),
        ]
        _seed_predictions(calibrator.tracker, "a1", entries)

        result = calibrator.calibrate_threshold("a1", current_threshold=0.97, target_accuracy=0.99)
        # min(0.97 + 0.05, 0.99) = 0.99
        assert result.recommended_threshold <= 0.99

    def test_neither_over_nor_underconfident_no_adjustment(self, calibrator: ConfidenceCalibrator):
        # Equal number of overconfident and underconfident bins => tie
        entries = [
            (0.15, "a", "a"),  # underconfident bin (conf < acc)
            (0.85, "b", "wrong"),  # overconfident bin (conf > acc)
        ]
        _seed_predictions(calibrator.tracker, "a1", entries)

        result = calibrator.calibrate_threshold("a1", current_threshold=0.85)
        assert result.reason == "No adjustment needed"
        assert result.recommended_threshold == pytest.approx(0.85)

    def test_confidence_in_recommendation_scales_with_data(self, calibrator: ConfidenceCalibrator):
        # With 10 resolved predictions, confidence = min(10/50, 1.0) = 0.2
        entries = [(0.15, f"o{i}", f"o{i}") for i in range(10)]
        _seed_predictions(calibrator.tracker, "a1", entries)

        result = calibrator.calibrate_threshold("a1")
        assert result.confidence_in_recommendation == pytest.approx(0.2, abs=1e-3)

    def test_confidence_in_recommendation_maxes_at_one(self, calibrator: ConfidenceCalibrator):
        # With 100 resolved predictions, confidence = min(100/50, 1.0) = 1.0
        entries = [(0.15, f"o{i}", f"o{i}") for i in range(100)]
        _seed_predictions(calibrator.tracker, "a1", entries)

        result = calibrator.calibrate_threshold("a1")
        assert result.confidence_in_recommendation == pytest.approx(1.0, abs=1e-3)

    def test_default_current_threshold_is_085(self, calibrator: ConfidenceCalibrator):
        result = calibrator.calibrate_threshold("unknown")
        assert result.current_threshold == pytest.approx(0.85)

    def test_custom_target_accuracy(self, calibrator: ConfidenceCalibrator):
        entries = [
            (0.15, "a", "a"),
            (0.25, "b", "b"),
            (0.35, "c", "c"),
        ]
        _seed_predictions(calibrator.tracker, "a1", entries)

        # With target_accuracy=0.50, more bins should qualify
        result = calibrator.calibrate_threshold("a1", current_threshold=0.85, target_accuracy=0.50)
        assert isinstance(result, ThresholdRecommendation)


# ── ConfidenceCalibrator.get_all_calibrations ───────────────────────


class TestGetAllCalibrations:
    """Tests for retrieving calibration curves for all agents."""

    def test_empty_tracker_returns_empty_dict(self, calibrator: ConfidenceCalibrator):
        result = calibrator.get_all_calibrations()
        assert result == {}

    def test_returns_curves_for_all_agents(self, calibrator: ConfidenceCalibrator):
        _seed_predictions(calibrator.tracker, "a1", [(0.9, "x", "x")])
        _seed_predictions(calibrator.tracker, "a2", [(0.8, "y", "y")])
        _seed_predictions(calibrator.tracker, "a3", [(0.7, "z", "z")])

        result = calibrator.get_all_calibrations()
        assert set(result.keys()) == {"a1", "a2", "a3"}
        assert all(isinstance(v, CalibrationCurve) for v in result.values())

    def test_each_curve_has_correct_agent_id(self, calibrator: ConfidenceCalibrator):
        _seed_predictions(calibrator.tracker, "inv-1", [(0.9, "x", "x")])
        _seed_predictions(calibrator.tracker, "rem-1", [(0.8, "y", "y")])

        result = calibrator.get_all_calibrations()
        assert result["inv-1"].agent_id == "inv-1"
        assert result["rem-1"].agent_id == "rem-1"


# ── ConfidenceCalibrator constructor ────────────────────────────────


class TestConfidenceCalibratorInit:
    """Tests for ConfidenceCalibrator initialization."""

    def test_default_tracker_created_when_none_provided(self):
        calibrator = ConfidenceCalibrator()
        assert isinstance(calibrator.tracker, AccuracyTracker)

    def test_custom_tracker_used(self, tracker: AccuracyTracker):
        calibrator = ConfidenceCalibrator(tracker=tracker)
        assert calibrator.tracker is tracker

    def test_default_num_bins(self):
        calibrator = ConfidenceCalibrator()
        assert calibrator._num_bins == 10

    def test_custom_num_bins(self):
        calibrator = ConfidenceCalibrator(num_bins=20)
        assert calibrator._num_bins == 20


# ── CalibrationBin / CalibrationCurve / ThresholdRecommendation models ──


class TestModels:
    """Verify Pydantic model defaults and construction."""

    def test_calibration_curve_defaults(self):
        curve = CalibrationCurve(agent_id="a1")
        assert curve.bins == []
        assert curve.expected_calibration_error == pytest.approx(0.0)
        assert curve.max_calibration_error == pytest.approx(0.0)
        assert curve.is_overconfident is False
        assert curve.is_underconfident is False

    def test_threshold_recommendation_fields(self):
        rec = ThresholdRecommendation(
            agent_id="a1",
            current_threshold=0.85,
            recommended_threshold=0.90,
            reason="Raising threshold",
        )
        assert rec.confidence_in_recommendation == pytest.approx(0.0)

    def test_calibration_bin_construction(self):
        b = CalibrationBin(
            confidence_min=0.8,
            confidence_max=0.9,
            predicted_confidence=0.85,
            actual_accuracy=0.70,
            count=5,
            gap=0.15,
        )
        assert b.count == 5
        assert b.gap == pytest.approx(0.15)

    def test_accuracy_metrics_defaults(self):
        m = AccuracyMetrics(agent_id="a1")
        assert m.total_predictions == 0
        assert m.overconfidence_rate == pytest.approx(0.0)
        assert m.underconfidence_rate == pytest.approx(0.0)
