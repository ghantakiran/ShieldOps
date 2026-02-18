"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shieldops.agents.cost.runner import CostRunner
from shieldops.agents.investigation.runner import InvestigationRunner
from shieldops.agents.learning.runner import LearningRunner
from shieldops.agents.remediation.runner import RemediationRunner
from shieldops.agents.security.runner import SecurityRunner
from shieldops.agents.supervisor.runner import SupervisorRunner
from shieldops.api.routes import agents, analytics, cost, investigations, learning, remediations, security, supervisor
from shieldops.config import settings
from shieldops.connectors.factory import create_connector_router
from shieldops.observability.factory import create_observability_sources
from shieldops.policy.approval.workflow import ApprovalWorkflow
from shieldops.policy.opa.client import PolicyEngine

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown lifecycle."""
    logger.info("shieldops_starting", environment=settings.environment)

    # Infrastructure layer
    obs_sources = create_observability_sources(settings)
    router = create_connector_router(settings)

    # Wire investigation runner with live dependencies
    inv_runner = InvestigationRunner(
        connector_router=router,
        log_sources=obs_sources.log_sources,
        metric_sources=obs_sources.metric_sources,
        trace_sources=obs_sources.trace_sources,
    )
    investigations.set_runner(inv_runner)

    # Policy layer
    policy_engine = PolicyEngine(opa_url=settings.opa_endpoint)
    approval_workflow = ApprovalWorkflow()

    # Remediation runner
    rem_runner = RemediationRunner(
        connector_router=router,
        policy_engine=policy_engine,
        approval_workflow=approval_workflow,
    )
    remediations.set_runner(rem_runner)

    # Security runner — cve_sources/credential_stores left empty until integrations land
    sec_runner = SecurityRunner(connector_router=router)
    security.set_runner(sec_runner)

    # Cost runner — billing_sources left empty until integrations land
    cost_runner = CostRunner(connector_router=router)
    cost.set_runner(cost_runner)

    # Learning runner — stores left empty until DB layer is wired
    learn_runner = LearningRunner()
    learning.set_runner(learn_runner)

    # Supervisor — orchestrates all specialist agents
    sup_runner = SupervisorRunner(agent_runners={
        "investigation": inv_runner,
        "remediation": rem_runner,
        "security": sec_runner,
        "cost": cost_runner,
        "learning": learn_runner,
    })
    supervisor.set_runner(sup_runner)

    # TODO: Initialize database connections, Kafka consumers, agent registry
    yield
    logger.info("shieldops_shutting_down")
    await obs_sources.close_all()
    await policy_engine.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ShieldOps API",
        description="AI-Powered Autonomous SRE Platform",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register route modules
    app.include_router(agents.router, prefix=settings.api_prefix, tags=["Agents"])
    app.include_router(
        investigations.router, prefix=settings.api_prefix, tags=["Investigations"]
    )
    app.include_router(
        remediations.router, prefix=settings.api_prefix, tags=["Remediations"]
    )
    app.include_router(analytics.router, prefix=settings.api_prefix, tags=["Analytics"])
    app.include_router(security.router, prefix=settings.api_prefix, tags=["Security"])
    app.include_router(cost.router, prefix=settings.api_prefix, tags=["Cost"])
    app.include_router(learning.router, prefix=settings.api_prefix, tags=["Learning"])
    app.include_router(supervisor.router, prefix=settings.api_prefix, tags=["Supervisor"])

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "healthy", "version": settings.app_version}

    return app


app = create_app()
