"""Cost Agent runner — entry point for executing cost analysis workflows.

Takes analysis parameters, constructs the LangGraph, runs it end-to-end,
and returns the completed cost analysis state.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.cost.graph import create_cost_graph
from shieldops.agents.cost.models import CostAnalysisState
from shieldops.agents.cost.nodes import set_toolkit
from shieldops.agents.cost.tools import CostToolkit
from shieldops.connectors.base import ConnectorRouter
from shieldops.models.base import Environment

logger = structlog.get_logger()


class CostRunner:
    """Runs cost analysis agent workflows.

    Usage:
        runner = CostRunner(
            connector_router=router,
            billing_sources=[aws_billing],
        )
        result = await runner.analyze(environment=Environment.PRODUCTION)
    """

    def __init__(
        self,
        connector_router: ConnectorRouter | None = None,
        billing_sources: list[Any] | None = None,
    ) -> None:
        self._toolkit = CostToolkit(
            connector_router=connector_router,
            billing_sources=billing_sources or [],
        )
        set_toolkit(self._toolkit)

        graph = create_cost_graph()
        self._app = graph.compile()

        self._analyses: dict[str, CostAnalysisState] = {}

    async def analyze(
        self,
        environment: Environment = Environment.PRODUCTION,
        analysis_type: str = "full",
        target_services: list[str] | None = None,
        period: str = "30d",
    ) -> CostAnalysisState:
        """Run a cost analysis.

        Args:
            environment: Target environment to analyze.
            analysis_type: Type of analysis — full, anomaly_only, optimization_only, savings_only.
            target_services: Specific services to analyze (all if empty).
            period: Analysis period (e.g. 7d, 30d, 90d).

        Returns:
            The completed CostAnalysisState with all findings.
        """
        analysis_id = f"cost-{uuid4().hex[:12]}"

        logger.info(
            "cost_analysis_started",
            analysis_id=analysis_id,
            environment=environment.value,
            analysis_type=analysis_type,
        )

        initial_state = CostAnalysisState(
            analysis_id=analysis_id,
            analysis_type=analysis_type,
            target_environment=environment,
            target_services=target_services or [],
            period=period,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),
                config={
                    "metadata": {
                        "analysis_id": analysis_id,
                        "analysis_type": analysis_type,
                    },
                },
            )

            final_state = CostAnalysisState.model_validate(final_state_dict)

            if final_state.analysis_start:
                final_state.analysis_duration_ms = int(
                    (datetime.now(timezone.utc) - final_state.analysis_start).total_seconds()
                    * 1000
                )

            logger.info(
                "cost_analysis_completed",
                analysis_id=analysis_id,
                duration_ms=final_state.analysis_duration_ms,
                monthly_spend=final_state.total_monthly_spend,
                anomalies=len(final_state.cost_anomalies),
                recommendations=len(final_state.optimization_recommendations),
                potential_savings=final_state.total_potential_savings,
                steps=len(final_state.reasoning_chain),
            )

            self._analyses[analysis_id] = final_state
            return final_state

        except Exception as e:
            logger.error(
                "cost_analysis_failed",
                analysis_id=analysis_id,
                error=str(e),
            )
            error_state = CostAnalysisState(
                analysis_id=analysis_id,
                analysis_type=analysis_type,
                target_environment=environment,
                error=str(e),
                current_step="failed",
            )
            self._analyses[analysis_id] = error_state
            return error_state

    def get_analysis(self, analysis_id: str) -> CostAnalysisState | None:
        """Retrieve a completed analysis by ID."""
        return self._analyses.get(analysis_id)

    def list_analyses(self) -> list[dict]:
        """List all analyses with summary info."""
        return [
            {
                "analysis_id": analysis_id,
                "analysis_type": state.analysis_type,
                "environment": state.target_environment.value,
                "status": state.current_step,
                "monthly_spend": state.total_monthly_spend,
                "anomaly_count": len(state.cost_anomalies),
                "critical_anomalies": state.critical_anomaly_count,
                "recommendation_count": len(state.optimization_recommendations),
                "potential_savings": state.total_potential_savings,
                "duration_ms": state.analysis_duration_ms,
                "error": state.error,
            }
            for analysis_id, state in self._analyses.items()
        ]
