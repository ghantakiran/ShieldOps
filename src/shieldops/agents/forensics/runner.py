"""Forensics Agent runner — entry point for executing forensic investigation workflows."""

from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.forensics.graph import create_forensics_graph
from shieldops.agents.forensics.models import ForensicsState
from shieldops.agents.forensics.nodes import set_toolkit
from shieldops.agents.forensics.tools import ForensicsToolkit

logger = structlog.get_logger()


class ForensicsRunner:
    """Runner for the Forensics Agent."""

    def __init__(
        self,
        evidence_store: Any | None = None,
        memory_analyzer: Any | None = None,
        disk_analyzer: Any | None = None,
        network_analyzer: Any | None = None,
        timeline_engine: Any | None = None,
        ioc_extractor: Any | None = None,
        policy_engine: Any | None = None,
        repository: Any | None = None,
    ) -> None:
        self._toolkit = ForensicsToolkit(
            evidence_store=evidence_store,
            memory_analyzer=memory_analyzer,
            disk_analyzer=disk_analyzer,
            network_analyzer=network_analyzer,
            timeline_engine=timeline_engine,
            ioc_extractor=ioc_extractor,
            policy_engine=policy_engine,
            repository=repository,
        )
        set_toolkit(self._toolkit)
        graph = create_forensics_graph()
        self._app = graph.compile()
        self._results: dict[str, ForensicsState] = {}
        logger.info("forensics_runner.initialized")

    async def investigate(
        self,
        incident_id: str,
        evidence_ids: list[str] | None = None,
    ) -> ForensicsState:
        """Run a forensic investigation on an incident."""
        session_id = f"forensics-{uuid4().hex[:12]}"
        initial_state = ForensicsState(
            incident_id=incident_id,
            evidence_ids=evidence_ids or [],
        )

        logger.info(
            "forensics_runner.starting",
            session_id=session_id,
            incident_id=incident_id,
            evidence_count=len(initial_state.evidence_ids),
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"session_id": session_id, "agent": "forensics"}},
            )
            final_state = ForensicsState.model_validate(final_state_dict)
            self._results[session_id] = final_state

            logger.info(
                "forensics_runner.completed",
                session_id=session_id,
                integrity_verified=final_state.integrity_verified,
                artifact_count=len(final_state.artifacts),
                ioc_count=len(final_state.extracted_iocs),
                duration_ms=final_state.session_duration_ms,
            )
            return final_state

        except Exception as e:
            logger.error("forensics_runner.failed", session_id=session_id, error=str(e))
            error_state = ForensicsState(
                incident_id=incident_id,
                evidence_ids=evidence_ids or [],
                error=str(e),
                current_step="failed",
            )
            self._results[session_id] = error_state
            return error_state

    def get_result(self, session_id: str) -> ForensicsState | None:
        return self._results.get(session_id)

    def list_results(self) -> list[dict[str, Any]]:
        return [
            {
                "session_id": sid,
                "incident_id": state.incident_id,
                "integrity_verified": state.integrity_verified,
                "artifact_count": len(state.artifacts),
                "ioc_count": len(state.extracted_iocs),
                "current_step": state.current_step,
                "error": state.error,
            }
            for sid, state in self._results.items()
        ]
