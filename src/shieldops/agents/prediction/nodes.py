"""Node implementations for the Prediction Agent LangGraph workflow."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.prediction.models import (
    CorrelatedChange,
    Prediction,
    PredictionSeverity,
    PredictionState,
    TrendAnomaly,
)
from shieldops.agents.prediction.tools import PredictionToolkit

logger = structlog.get_logger()

_toolkit: PredictionToolkit | None = None


def set_toolkit(toolkit: PredictionToolkit) -> None:
    """Configure the toolkit used by all nodes."""
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> PredictionToolkit:
    if _toolkit is None:
        return PredictionToolkit()
    return _toolkit


def _elapsed_ms(start: datetime) -> int:
    return int((datetime.now(UTC) - start).total_seconds() * 1000)


async def collect_baselines(state: PredictionState) -> dict[str, Any]:
    """Collect metric baselines for target resources."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "prediction_collecting_baselines",
        prediction_id=state.prediction_id,
        resources=len(state.target_resources),
    )

    baselines = await toolkit.collect_metric_baselines(
        resources=state.target_resources or ["default"],
        lookback_hours=state.lookback_hours,
    )

    step = {
        "step": "collect_baselines",
        "resources_checked": len(baselines),
        "duration_ms": _elapsed_ms(start),
    }

    return {
        "prediction_start": start,
        "reasoning_chain": [step],
        "current_step": "collect_baselines",
    }


async def detect_trends(state: PredictionState) -> dict[str, Any]:
    """Detect trend anomalies in collected baselines."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info("prediction_detecting_trends", prediction_id=state.prediction_id)

    raw_anomalies = await toolkit.detect_trend_anomalies(
        baselines={r: {} for r in (state.target_resources or ["default"])}
    )

    anomalies = [
        TrendAnomaly(
            metric_name=a.get("metric_name", "unknown"),
            resource_id=a.get("resource_id", ""),
            trend_direction=a.get("trend_direction", "increasing"),
            deviation_percent=a.get("deviation_percent", 0.0),
            baseline_value=a.get("baseline_value", 0.0),
            current_value=a.get("current_value", 0.0),
        )
        for a in raw_anomalies
    ]

    step = {
        "step": "detect_trends",
        "anomalies_found": len(anomalies),
        "duration_ms": _elapsed_ms(start),
    }

    return {
        "trend_anomalies": anomalies,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "detect_trends",
    }


async def correlate_changes(state: PredictionState) -> dict[str, Any]:
    """Correlate detected trends with recent infrastructure changes."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info("prediction_correlating_changes", prediction_id=state.prediction_id)

    raw_changes = await toolkit.get_recent_changes(lookback_hours=state.lookback_hours)

    correlated = [
        CorrelatedChange(
            change_id=c.get("change_id", f"chg-{uuid4().hex[:8]}"),
            change_type=c.get("change_type", "unknown"),
            description=c.get("description", ""),
            correlation_score=c.get("correlation_score", 0.5),
        )
        for c in raw_changes
    ]

    step = {
        "step": "correlate_changes",
        "changes_found": len(correlated),
        "duration_ms": _elapsed_ms(start),
    }

    return {
        "correlated_changes": correlated,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "correlate_changes",
    }


async def assess_risk(state: PredictionState) -> dict[str, Any]:
    """Assess overall risk based on anomalies and correlated changes."""
    start = datetime.now(UTC)

    logger.info("prediction_assessing_risk", prediction_id=state.prediction_id)

    # Risk scoring: weighted combination of anomaly severity and change correlation
    anomaly_score = min(len(state.trend_anomalies) * 0.15, 0.6)
    change_score = min(len(state.correlated_changes) * 0.1, 0.4)

    # Boost risk if any anomaly has high deviation
    high_deviation = any(a.deviation_percent > 50 for a in state.trend_anomalies)
    if high_deviation:
        anomaly_score = min(anomaly_score + 0.2, 0.8)

    risk_score = min(anomaly_score + change_score, 1.0)

    step = {
        "step": "assess_risk",
        "risk_score": risk_score,
        "anomaly_contribution": anomaly_score,
        "change_contribution": change_score,
        "duration_ms": _elapsed_ms(start),
    }

    return {
        "risk_score": risk_score,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "assess_risk",
    }


async def generate_predictions(state: PredictionState) -> dict[str, Any]:
    """Generate predictions based on all collected evidence."""
    start = datetime.now(UTC)

    logger.info(
        "prediction_generating",
        prediction_id=state.prediction_id,
        risk_score=state.risk_score,
    )

    predictions: list[Prediction] = []

    # Generate predictions based on trend anomalies
    for anomaly in state.trend_anomalies:
        severity = PredictionSeverity.LOW
        if anomaly.deviation_percent > 80:
            severity = PredictionSeverity.CRITICAL
        elif anomaly.deviation_percent > 50:
            severity = PredictionSeverity.HIGH
        elif anomaly.deviation_percent > 25:
            severity = PredictionSeverity.MEDIUM

        confidence = min(0.5 + anomaly.deviation_percent / 200, 0.95)

        predictions.append(
            Prediction(
                id=f"pred-{uuid4().hex[:12]}",
                title=f"Potential {anomaly.trend_direction} trend in {anomaly.metric_name}",
                description=(
                    f"{anomaly.metric_name} on {anomaly.resource_id} is "
                    f"{anomaly.trend_direction} with {anomaly.deviation_percent:.1f}% deviation "
                    f"from baseline"
                ),
                severity=severity,
                confidence=confidence,
                predicted_impact=f"Resource {anomaly.resource_id} may experience degradation",
                affected_resources=[anomaly.resource_id] if anomaly.resource_id else [],
                recommended_actions=[
                    f"Monitor {anomaly.metric_name} closely",
                    f"Review recent changes to {anomaly.resource_id}",
                ],
                evidence=[
                    f"Baseline: {anomaly.baseline_value}, Current: {anomaly.current_value}",
                    f"Deviation: {anomaly.deviation_percent:.1f}%",
                ],
                estimated_time_to_incident="2-6 hours",
            )
        )

    # Generate risk-based summary prediction if risk is elevated
    if state.risk_score > 0.5 and not predictions:
        predictions.append(
            Prediction(
                id=f"pred-{uuid4().hex[:12]}",
                title="Elevated system risk detected",
                description=(
                    f"Overall risk score of {state.risk_score:.2f} with "
                    f"{len(state.trend_anomalies)} anomalies and "
                    f"{len(state.correlated_changes)} correlated changes"
                ),
                severity=PredictionSeverity.MEDIUM,
                confidence=state.risk_score,
                predicted_impact="Potential service degradation",
                recommended_actions=["Review system dashboards", "Check recent deployments"],
                evidence=[f"Risk score: {state.risk_score:.2f}"],
            )
        )

    duration_ms = _elapsed_ms(start)
    total_duration = (
        int((datetime.now(UTC) - state.prediction_start).total_seconds() * 1000)
        if state.prediction_start
        else duration_ms
    )

    step = {
        "step": "generate_predictions",
        "predictions_generated": len(predictions),
        "duration_ms": duration_ms,
    }

    return {
        "predictions": predictions,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
        "prediction_duration_ms": total_duration,
    }
