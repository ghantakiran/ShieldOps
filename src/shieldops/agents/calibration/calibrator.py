"""Confidence calibrator — computes calibration curves and auto-adjusts thresholds."""

from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

from shieldops.agents.calibration.tracker import AccuracyTracker

logger = structlog.get_logger()


class CalibrationBin(BaseModel):
    """A bin in the calibration curve."""

    confidence_min: float
    confidence_max: float
    predicted_confidence: float  # avg confidence in this bin
    actual_accuracy: float  # actual accuracy in this bin
    count: int
    gap: float  # |predicted - actual|


class CalibrationCurve(BaseModel):
    """Calibration curve data for an agent."""

    agent_id: str
    bins: list[CalibrationBin] = Field(default_factory=list)
    expected_calibration_error: float = 0.0  # ECE
    max_calibration_error: float = 0.0  # MCE
    is_overconfident: bool = False
    is_underconfident: bool = False


class ThresholdRecommendation(BaseModel):
    """Recommended threshold adjustment based on calibration."""

    agent_id: str
    current_threshold: float
    recommended_threshold: float
    reason: str
    confidence_in_recommendation: float = 0.0


class ConfidenceCalibrator:
    """Computes calibration curves and auto-adjusts confidence thresholds.

    Uses binned calibration: groups predictions by confidence ranges and
    compares predicted confidence to actual accuracy in each bin.
    """

    DEFAULT_NUM_BINS = 10

    def __init__(
        self,
        tracker: AccuracyTracker | None = None,
        num_bins: int = 10,
    ) -> None:
        self._tracker = tracker or AccuracyTracker()
        self._num_bins = num_bins

    @property
    def tracker(self) -> AccuracyTracker:
        return self._tracker

    def compute_calibration(self, agent_id: str) -> CalibrationCurve:
        """Compute the calibration curve for an agent.

        Groups predictions into confidence bins and compares
        average confidence vs actual accuracy per bin.
        """
        records = self._tracker.get_records(agent_id)
        resolved = [r for r in records if r.was_correct is not None]

        if not resolved:
            return CalibrationCurve(agent_id=agent_id)

        bin_size = 1.0 / self._num_bins
        bins: list[CalibrationBin] = []
        total_gap = 0.0
        max_gap = 0.0

        for i in range(self._num_bins):
            bin_min = i * bin_size
            bin_max = (i + 1) * bin_size

            bin_records = [
                r
                for r in resolved
                if bin_min <= r.predicted_confidence < bin_max
                or (i == self._num_bins - 1 and r.predicted_confidence == bin_max)
            ]

            if not bin_records:
                continue

            avg_confidence = sum(r.predicted_confidence for r in bin_records) / len(bin_records)
            actual_accuracy = sum(1 for r in bin_records if r.was_correct) / len(bin_records)
            gap = abs(avg_confidence - actual_accuracy)

            total_gap += gap * len(bin_records)
            max_gap = max(max_gap, gap)

            bins.append(
                CalibrationBin(
                    confidence_min=round(bin_min, 2),
                    confidence_max=round(bin_max, 2),
                    predicted_confidence=round(avg_confidence, 4),
                    actual_accuracy=round(actual_accuracy, 4),
                    count=len(bin_records),
                    gap=round(gap, 4),
                )
            )

        ece = total_gap / len(resolved) if resolved else 0.0

        # Determine over/under confidence
        overconfident_bins = sum(1 for b in bins if b.predicted_confidence > b.actual_accuracy)
        underconfident_bins = sum(1 for b in bins if b.predicted_confidence < b.actual_accuracy)

        return CalibrationCurve(
            agent_id=agent_id,
            bins=bins,
            expected_calibration_error=round(ece, 4),
            max_calibration_error=round(max_gap, 4),
            is_overconfident=overconfident_bins > underconfident_bins,
            is_underconfident=underconfident_bins > overconfident_bins,
        )

    def calibrate_threshold(
        self,
        agent_id: str,
        current_threshold: float = 0.85,
        target_accuracy: float = 0.90,
    ) -> ThresholdRecommendation:
        """Auto-adjust the confidence threshold for an agent.

        Finds the confidence level where actual accuracy meets the target.
        """
        curve = self.compute_calibration(agent_id)
        accuracy_metrics = self._tracker.get_accuracy(agent_id)

        if not curve.bins:
            return ThresholdRecommendation(
                agent_id=agent_id,
                current_threshold=current_threshold,
                recommended_threshold=current_threshold,
                reason="Insufficient data for calibration",
                confidence_in_recommendation=0.0,
            )

        # Find the confidence bin where actual accuracy >= target
        recommended = current_threshold
        reason = "No adjustment needed"

        if curve.is_overconfident:
            # Agent is overconfident — need higher threshold
            for b in sorted(curve.bins, key=lambda x: x.confidence_min, reverse=True):
                if b.actual_accuracy >= target_accuracy:
                    recommended = b.confidence_min
                    reason = (
                        f"Agent is overconfident (ECE={curve.expected_calibration_error:.3f}). "
                        f"Raising threshold to match {target_accuracy:.0%} accuracy target"
                    )
                    break
            else:
                recommended = min(current_threshold + 0.05, 0.99)
                reason = "Agent consistently overconfident; incrementally raising threshold"

        elif curve.is_underconfident:
            # Agent is underconfident — can lower threshold
            for b in sorted(curve.bins, key=lambda x: x.confidence_min):
                if b.actual_accuracy >= target_accuracy:
                    recommended = b.confidence_min
                    reason = (
                        f"Agent is underconfident (ECE={curve.expected_calibration_error:.3f}). "
                        f"Lowering threshold — accuracy exceeds confidence"
                    )
                    break

        data_confidence = min(accuracy_metrics.resolved_predictions / 50, 1.0)

        return ThresholdRecommendation(
            agent_id=agent_id,
            current_threshold=current_threshold,
            recommended_threshold=round(recommended, 3),
            reason=reason,
            confidence_in_recommendation=round(data_confidence, 3),
        )

    def get_all_calibrations(self) -> dict[str, CalibrationCurve]:
        """Get calibration curves for all tracked agents."""
        return {
            agent_id: self.compute_calibration(agent_id) for agent_id in self._tracker.list_agents()
        }
