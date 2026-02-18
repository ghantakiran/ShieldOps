"""Node implementations for the Learning Agent LangGraph workflow.

Each node is an async function that:
1. Gathers or analyzes incident outcome data via the LearningToolkit
2. Uses the LLM to identify patterns and recommend improvements
3. Updates the learning state with results
4. Records its reasoning step in the audit trail
"""

from datetime import UTC, datetime
from uuid import uuid4

import structlog

from shieldops.agents.learning.models import (
    IncidentOutcome,
    LearningState,
    LearningStep,
    PatternInsight,
    PlaybookUpdate,
    ThresholdAdjustment,
)
from shieldops.agents.learning.prompts import (
    SYSTEM_IMPROVEMENT_SYNTHESIS,
    SYSTEM_PATTERN_ANALYSIS,
    SYSTEM_PLAYBOOK_RECOMMENDATION,
    SYSTEM_THRESHOLD_RECOMMENDATION,
    ImprovementSynthesisResult,
    PatternAnalysisResult,
    PlaybookRecommendationResult,
    ThresholdRecommendationResult,
)
from shieldops.agents.learning.tools import LearningToolkit
from shieldops.utils.llm import llm_structured

logger = structlog.get_logger()

# Module-level toolkit reference, set by the runner at graph construction time.
_toolkit: LearningToolkit | None = None


def set_toolkit(toolkit: LearningToolkit | None) -> None:
    """Configure the toolkit used by all nodes. Called once at startup."""
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> LearningToolkit:
    if _toolkit is None:
        return LearningToolkit()
    return _toolkit


def _elapsed_ms(start: datetime) -> int:
    return int((datetime.now(UTC) - start).total_seconds() * 1000)


async def gather_outcomes(state: LearningState) -> dict:
    """Gather incident outcomes and compute effectiveness metrics."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "learning_gathering_outcomes",
        learning_id=state.learning_id,
        period=state.target_period,
    )

    outcome_data = await toolkit.get_incident_outcomes(period=state.target_period)

    outcomes: list[IncidentOutcome] = []
    for raw in outcome_data.get("outcomes", []):
        outcomes.append(
            IncidentOutcome(
                incident_id=raw.get("incident_id", "unknown"),
                alert_type=raw.get("alert_type", "unknown"),
                environment=raw.get("environment", "production"),
                root_cause=raw.get("root_cause", ""),
                resolution_action=raw.get("resolution_action", ""),
                investigation_duration_ms=raw.get("investigation_duration_ms", 0),
                remediation_duration_ms=raw.get("remediation_duration_ms", 0),
                was_automated=raw.get("was_automated", False),
                was_correct=raw.get("was_correct", True),
                feedback=raw.get("feedback", ""),
            )
        )

    # Compute effectiveness metrics
    metrics = await toolkit.compute_effectiveness_metrics(outcome_data.get("outcomes", []))

    step = LearningStep(
        step_number=1,
        action="gather_outcomes",
        input_summary=f"Gathering incident outcomes for {state.target_period}",
        output_summary=(
            f"Analyzed {len(outcomes)} incidents. "
            f"Automation rate: {metrics['automation_rate']:.0f}%, "
            f"Accuracy: {metrics['accuracy']:.0f}%"
        ),
        duration_ms=_elapsed_ms(start),
        tool_used="incident_store",
    )

    return {
        "learning_start": start,
        "incident_outcomes": outcomes,
        "total_incidents_analyzed": len(outcomes),
        "automation_accuracy": metrics["accuracy"],
        "avg_resolution_time_ms": metrics["avg_investigation_ms"] + metrics["avg_remediation_ms"],
        "reasoning_chain": [step],
        "current_step": "gather_outcomes",
    }


async def analyze_patterns(state: LearningState) -> dict:
    """Analyze incident patterns to identify recurring issues."""
    start = datetime.now(UTC)

    logger.info(
        "learning_analyzing_patterns",
        learning_id=state.learning_id,
        incident_count=len(state.incident_outcomes),
    )

    # Group incidents by alert type for pattern detection
    by_type: dict[str, list[IncidentOutcome]] = {}
    for outcome in state.incident_outcomes:
        by_type.setdefault(outcome.alert_type, []).append(outcome)

    # Build pattern insights from raw data
    insights: list[PatternInsight] = []
    for alert_type, incidents in by_type.items():
        if len(incidents) >= 2:  # recurring if 2+ incidents
            # Find most common root cause
            root_causes: dict[str, int] = {}
            resolutions: dict[str, int] = {}
            envs: set[str] = set()
            total_time = 0

            for inc in incidents:
                root_causes[inc.root_cause] = root_causes.get(inc.root_cause, 0) + 1
                resolutions[inc.resolution_action] = resolutions.get(inc.resolution_action, 0) + 1
                envs.add(
                    inc.environment if isinstance(inc.environment, str) else inc.environment.value
                )
                total_time += inc.investigation_duration_ms + inc.remediation_duration_ms

            common_cause = max(root_causes, key=root_causes.get) if root_causes else ""
            common_resolution = max(resolutions, key=resolutions.get) if resolutions else ""

            insights.append(
                PatternInsight(
                    pattern_id=f"pat-{uuid4().hex[:8]}",
                    alert_type=alert_type,
                    description=(
                        f"Recurring {alert_type}: {len(incidents)} "
                        f"incidents, common cause: {common_cause}"
                    ),
                    frequency=len(incidents),
                    avg_resolution_time_ms=total_time // len(incidents),
                    common_root_cause=common_cause,
                    common_resolution=common_resolution,
                    confidence=min(0.95, 0.5 + len(incidents) * 0.1),
                    environments=sorted(envs),
                )
            )

    recurring_count = sum(1 for p in insights if p.frequency >= 2)
    output_summary = f"{len(insights)} patterns found, {recurring_count} recurring"

    # LLM assessment
    if state.incident_outcomes:
        context_lines = [
            "## Incident Outcomes",
            f"Total incidents: {len(state.incident_outcomes)}",
            f"Automation accuracy: {state.automation_accuracy:.0f}%",
            "",
            "## Incidents by Type",
        ]
        for alert_type, incidents in by_type.items():
            automated = sum(1 for i in incidents if i.was_automated)
            incorrect = sum(1 for i in incidents if i.was_automated and not i.was_correct)
            context_lines.append(
                f"- {alert_type}: {len(incidents)} incidents, "
                f"{automated} automated, {incorrect} incorrect"
            )
            for inc in incidents[:3]:
                context_lines.append(
                    f"  - {inc.incident_id}: cause={inc.root_cause}, fix={inc.resolution_action}"
                )
                if inc.feedback:
                    context_lines.append(f"    Feedback: {inc.feedback}")

        try:
            assessment: PatternAnalysisResult = await llm_structured(
                system_prompt=SYSTEM_PATTERN_ANALYSIS,
                user_prompt="\n".join(context_lines),
                schema=PatternAnalysisResult,
            )
            output_summary = (
                f"{assessment.summary}. "
                f"Patterns: {len(assessment.recurring_patterns)}, "
                f"Automation gaps: {len(assessment.automation_gaps)}"
            )
        except Exception as e:
            logger.error("llm_pattern_analysis_failed", error=str(e))

    step = LearningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="analyze_patterns",
        input_summary=f"Analyzing patterns across {len(state.incident_outcomes)} incidents",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="pattern_analyzer + llm",
    )

    return {
        "pattern_insights": insights,
        "recurring_pattern_count": recurring_count,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "analyze_patterns",
    }


async def recommend_playbooks(state: LearningState) -> dict:
    """Generate playbook updates based on patterns and outcomes."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "learning_recommending_playbooks",
        learning_id=state.learning_id,
        pattern_count=len(state.pattern_insights),
    )

    current_playbooks = await toolkit.get_current_playbooks()

    # Generate playbook updates from patterns
    updates: list[PlaybookUpdate] = []
    existing_types = {pb["alert_type"] for pb in current_playbooks.get("playbooks", [])}

    for pattern in state.pattern_insights:
        if pattern.alert_type not in existing_types:
            # New playbook needed
            updates.append(
                PlaybookUpdate(
                    playbook_id=f"pb-{uuid4().hex[:8]}",
                    alert_type=pattern.alert_type,
                    update_type="new_playbook",
                    title=f"Automated response for {pattern.alert_type}",
                    description=(
                        f"Based on {pattern.frequency} incidents. "
                        f"Common cause: {pattern.common_root_cause}"
                    ),
                    steps=[
                        f"Investigate {pattern.alert_type} via automated analysis",
                        (
                            f"Apply {pattern.common_resolution} if root "
                            f"cause matches: {pattern.common_root_cause}"
                        ),
                        "Validate service health post-remediation",
                        "Escalate to on-call if automated fix fails",
                    ],
                    priority="high" if pattern.frequency >= 3 else "medium",
                    based_on_incidents=[],
                )
            )
        elif pattern.frequency >= 3:
            # Existing playbook needs improvement
            updates.append(
                PlaybookUpdate(
                    playbook_id=f"pb-{uuid4().hex[:8]}",
                    alert_type=pattern.alert_type,
                    update_type="modify_step",
                    title=f"Improve {pattern.alert_type} playbook",
                    description=(
                        f"Recurring pattern ({pattern.frequency}x) "
                        "suggests current playbook is insufficient"
                    ),
                    steps=[
                        f"Add root cause check for: {pattern.common_root_cause}",
                        f"Auto-apply {pattern.common_resolution} when pattern matches",
                    ],
                    priority="high",
                    based_on_incidents=[],
                )
            )

    # Check for incorrect automation — suggest playbook fixes
    for outcome in state.incident_outcomes:
        if outcome.was_automated and not outcome.was_correct:
            updates.append(
                PlaybookUpdate(
                    playbook_id=f"pb-{uuid4().hex[:8]}",
                    alert_type=outcome.alert_type,
                    update_type="modify_step",
                    title=f"Fix incorrect automation for {outcome.alert_type}",
                    description=(
                        f"Automated action '{outcome.resolution_action}' "
                        f"was incorrect for incident {outcome.incident_id}. "
                        f"Root cause: {outcome.root_cause}"
                    ),
                    steps=[
                        (
                            f"Add pre-check to distinguish '{outcome.root_cause}' "
                            f"from other {outcome.alert_type} causes"
                        ),
                        f"Only apply {outcome.resolution_action} when root cause is confirmed",
                    ],
                    priority="high",
                    based_on_incidents=[outcome.incident_id],
                )
            )

    output_summary = f"{len(updates)} playbook updates recommended"

    # LLM assessment
    if updates:
        context_lines = [
            "## Current Playbooks",
            f"Total: {current_playbooks.get('total', 0)}",
            "",
            "## Patterns Identified",
        ]
        for pattern in state.pattern_insights[:10]:
            context_lines.append(
                f"- {pattern.alert_type}: {pattern.frequency}x, "
                f"cause={pattern.common_root_cause}, fix={pattern.common_resolution}"
            )
        context_lines.extend(["", "## Proposed Updates"])
        for update in updates[:10]:
            context_lines.append(f"- {update.update_type}: {update.title}")

        try:
            assessment: PlaybookRecommendationResult = await llm_structured(
                system_prompt=SYSTEM_PLAYBOOK_RECOMMENDATION,
                user_prompt="\n".join(context_lines),
                schema=PlaybookRecommendationResult,
            )
            output_summary = (
                f"{assessment.summary}. "
                f"New: {len(assessment.new_playbooks)}, "
                f"Improved: {len(assessment.playbook_improvements)}"
            )
        except Exception as e:
            logger.error("llm_playbook_recommendation_failed", error=str(e))

    step = LearningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="recommend_playbooks",
        input_summary=f"Generating playbook updates from {len(state.pattern_insights)} patterns",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="playbook_store + llm",
    )

    return {
        "playbook_updates": updates,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "recommend_playbooks",
    }


async def recommend_thresholds(state: LearningState) -> dict:
    """Recommend alerting threshold adjustments based on incident data."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "learning_recommending_thresholds",
        learning_id=state.learning_id,
    )

    current_thresholds = await toolkit.get_alert_thresholds()

    adjustments: list[ThresholdAdjustment] = []
    threshold_map = {t["metric_name"]: t for t in current_thresholds.get("thresholds", [])}

    # Analyze false positives: incidents where automated action was wrong
    incorrect_by_type: dict[str, int] = {}
    total_by_type: dict[str, int] = {}
    for outcome in state.incident_outcomes:
        total_by_type[outcome.alert_type] = total_by_type.get(outcome.alert_type, 0) + 1
        if outcome.was_automated and not outcome.was_correct:
            incorrect_by_type[outcome.alert_type] = incorrect_by_type.get(outcome.alert_type, 0) + 1

    # Map alert types to metrics
    alert_metric_map = {
        "high_cpu": "cpu_usage_percent",
        "oom_kill": "memory_usage_percent",
        "disk_full": "disk_usage_percent",
        "high_error_rate": "error_rate_percent",
        "latency_spike": "p99_latency_ms",
    }

    for alert_type, incorrect_count in incorrect_by_type.items():
        total = total_by_type.get(alert_type, 1)
        error_rate = incorrect_count / total

        metric = alert_metric_map.get(alert_type)
        if metric and metric in threshold_map and error_rate > 0.1:
            current = threshold_map[metric]["threshold"]
            # Suggest tightening threshold if false positives are high
            recommended = current * 1.1  # increase by 10%
            adjustments.append(
                ThresholdAdjustment(
                    adjustment_id=f"adj-{uuid4().hex[:8]}",
                    metric_name=metric,
                    current_threshold=current,
                    recommended_threshold=round(recommended, 1),
                    direction="increase",
                    reason=(
                        f"{incorrect_count}/{total} automated actions for "
                        f"{alert_type} were incorrect — threshold may be "
                        "too sensitive"
                    ),
                    false_positive_reduction=round(error_rate * 50, 1),  # estimate
                    based_on_incidents=[],
                )
            )

    est_fp_reduction = sum(a.false_positive_reduction for a in adjustments) / max(
        len(adjustments), 1
    )
    output_summary = (
        f"{len(adjustments)} threshold adjustments, est. {est_fp_reduction:.0f}% FP reduction"
    )

    # LLM assessment
    if state.incident_outcomes:
        context_lines = [
            "## Current Thresholds",
        ]
        for t in current_thresholds.get("thresholds", []):
            context_lines.append(
                f"- {t['metric_name']}: {t['threshold']} ({t['severity']}, {t['duration']})"
            )
        context_lines.extend(
            [
                "",
                "## Incident Analysis",
                f"Total incidents: {len(state.incident_outcomes)}",
            ]
        )
        for at, count in total_by_type.items():
            incorrect = incorrect_by_type.get(at, 0)
            context_lines.append(f"- {at}: {count} total, {incorrect} incorrect automations")

        try:
            assessment: ThresholdRecommendationResult = await llm_structured(
                system_prompt=SYSTEM_THRESHOLD_RECOMMENDATION,
                user_prompt="\n".join(context_lines),
                schema=ThresholdRecommendationResult,
            )
            est_fp_reduction = assessment.estimated_noise_reduction
            output_summary = (
                f"{assessment.summary}. "
                f"Adjustments: {len(assessment.adjustments)}, "
                f"Est. noise reduction: {assessment.estimated_noise_reduction:.0f}%"
            )
        except Exception as e:
            logger.error("llm_threshold_recommendation_failed", error=str(e))

    step = LearningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="recommend_thresholds",
        input_summary="Analyzing thresholds based on incident outcomes",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="alert_config + llm",
    )

    return {
        "threshold_adjustments": adjustments,
        "estimated_false_positive_reduction": est_fp_reduction,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "recommend_thresholds",
    }


async def synthesize_improvements(state: LearningState) -> dict:
    """Synthesize all findings into an improvement summary."""
    start = datetime.now(UTC)

    logger.info("learning_synthesizing_improvements", learning_id=state.learning_id)

    # Build context for LLM
    context_lines = [
        "## Incident Analysis Summary",
        f"Incidents analyzed: {state.total_incidents_analyzed}",
        f"Automation accuracy: {state.automation_accuracy:.0f}%",
        f"Avg resolution time: {state.avg_resolution_time_ms}ms",
        "",
        "## Pattern Insights",
        f"Patterns found: {len(state.pattern_insights)}",
        f"Recurring: {state.recurring_pattern_count}",
    ]
    for p in state.pattern_insights[:10]:
        context_lines.append(f"- {p.alert_type}: {p.frequency}x, cause={p.common_root_cause}")
    context_lines.extend(
        [
            "",
            "## Playbook Updates",
            f"Recommended: {len(state.playbook_updates)}",
        ]
    )
    for pb in state.playbook_updates[:10]:
        context_lines.append(f"- {pb.update_type}: {pb.title}")
    context_lines.extend(
        [
            "",
            "## Threshold Adjustments",
            f"Recommended: {len(state.threshold_adjustments)}",
            f"Est. FP reduction: {state.estimated_false_positive_reduction:.0f}%",
            "",
            "## Learning Chain",
        ]
    )
    for step in state.reasoning_chain:
        context_lines.append(f"Step {step.step_number} ({step.action}): {step.output_summary}")

    # Compute default improvement score
    improvement_score = 50.0
    if state.automation_accuracy > 90:
        improvement_score += 20
    elif state.automation_accuracy > 75:
        improvement_score += 10
    if state.recurring_pattern_count == 0:
        improvement_score += 15
    if len(state.playbook_updates) > 0:
        improvement_score += 10  # having actionable improvements is good
    improvement_score = max(0, min(100, improvement_score))

    output_summary = f"Improvement score: {improvement_score:.1f}/100"

    try:
        assessment: ImprovementSynthesisResult = await llm_structured(
            system_prompt=SYSTEM_IMPROVEMENT_SYNTHESIS,
            user_prompt="\n".join(context_lines),
            schema=ImprovementSynthesisResult,
        )
        improvement_score = assessment.improvement_score
        output_summary = (
            f"Score: {assessment.improvement_score:.1f}/100. {assessment.summary[:200]}"
        )
    except Exception as e:
        logger.error("llm_improvement_synthesis_failed", error=str(e))

    step = LearningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="synthesize_improvements",
        input_summary="Synthesizing learning cycle improvements",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="llm",
    )

    return {
        "improvement_score": improvement_score,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
        "learning_duration_ms": int(
            (datetime.now(UTC) - state.learning_start).total_seconds() * 1000
        )
        if state.learning_start
        else 0,
    }
