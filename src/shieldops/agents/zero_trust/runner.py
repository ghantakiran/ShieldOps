"""Zero Trust Agent runner — entry point for executing zero trust assessment workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.zero_trust.graph import create_zero_trust_graph
from shieldops.agents.zero_trust.models import ZeroTrustState
from shieldops.agents.zero_trust.nodes import set_toolkit
from shieldops.agents.zero_trust.tools import ZeroTrustToolkit

logger = structlog.get_logger()


class ZeroTrustRunner:
    """Runner for the Zero Trust Agent."""

    def __init__(
        self,
        identity_provider: Any | None = None,
        device_manager: Any | None = None,
        policy_engine: Any | None = None,
        access_controller: Any | None = None,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = ZeroTrustToolkit(
            identity_provider=identity_provider,
            device_manager=device_manager,
            policy_engine=policy_engine,
            access_controller=access_controller,
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_zero_trust_graph()
        self._app = graph.compile()
        self._results: dict[str, ZeroTrustState] = {}
        logger.info("zero_trust_runner.initialized")

    async def assess(
        self,
        session_id: str,
        assessment_config: dict[str, Any] | None = None,
    ) -> ZeroTrustState:
        """Run zero trust assessment workflow."""
        internal_id = f"zt-{uuid4().hex[:12]}"
        initial_state = ZeroTrustState(
            session_id=session_id,
            assessment_config=assessment_config or {},
        )

        logger.info(
            "zero_trust_runner.starting",
            internal_id=internal_id,
            session_id=session_id,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": internal_id, "agent": "zero_trust"}},
            )
            final_state = ZeroTrustState.model_validate(final_state_dict)
            self._results[internal_id] = final_state

            logger.info(
                "zero_trust_runner.completed",
                internal_id=internal_id,
                identity_verified=final_state.identity_verified,
                violation_count=final_state.violation_count,
                trust_score=final_state.trust_score,
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error("zero_trust_runner.failed", internal_id=internal_id, error=str(e))
            error_state = ZeroTrustState(
                session_id=session_id,
                assessment_config=assessment_config or {},
                error=str(e),
                current_step="failed",
            )
            self._results[internal_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> ZeroTrustState | None:
        return self._results.get(session_id)

    def list_results(self) -> list[dict[str, Any]]:
        return [
            {
                "session_id": sid,
                "identity_verified": state.identity_verified,
                "violation_count": state.violation_count,
                "trust_score": state.trust_score,
                "policy_enforced": state.policy_enforced,
                "current_step": state.current_step,
                "error": state.error,
            }
            for sid, state in self._results.items()
        ]
