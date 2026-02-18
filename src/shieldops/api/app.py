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
from shieldops.api.routes import (
    agents,
    analytics,
    cost,
    investigations,
    learning,
    remediations,
    security,
    supervisor,
)
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

    # ── Database layer ──────────────────────────────────────────
    repository = None
    engine = None
    try:
        from shieldops.db.models import Base
        from shieldops.db.repository import Repository
        from shieldops.db.session import create_async_engine, get_session_factory

        engine = create_async_engine(
            settings.database_url, pool_size=settings.database_pool_size
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        repository = Repository(get_session_factory())
        logger.info("database_initialized")
    except Exception as e:
        logger.warning("database_init_failed", error=str(e), detail="falling back to in-memory")

    # ── Infrastructure layer ────────────────────────────────────
    obs_sources = create_observability_sources(settings)
    router = create_connector_router(settings)

    # Wire investigation runner with live dependencies
    inv_runner = InvestigationRunner(
        connector_router=router,
        log_sources=obs_sources.log_sources,
        metric_sources=obs_sources.metric_sources,
        trace_sources=obs_sources.trace_sources,
        repository=repository,
    )
    investigations.set_runner(inv_runner)
    investigations.set_repository(repository)

    # Policy layer with rate limiting
    rate_limiter = None
    try:
        from shieldops.policy.opa.rate_limiter import ActionRateLimiter

        rate_limiter = ActionRateLimiter(redis_url=settings.redis_url)
    except Exception as e:
        logger.warning("rate_limiter_init_failed", error=str(e))

    policy_engine = PolicyEngine(opa_url=settings.opa_endpoint, rate_limiter=rate_limiter)
    approval_workflow = ApprovalWorkflow()

    # Remediation runner
    rem_runner = RemediationRunner(
        connector_router=router,
        policy_engine=policy_engine,
        approval_workflow=approval_workflow,
        repository=repository,
    )
    remediations.set_runner(rem_runner)
    remediations.set_repository(repository)

    # Security runner — cve_sources/credential_stores left empty until integrations land
    sec_runner = SecurityRunner(connector_router=router)
    security.set_runner(sec_runner)

    # Cost runner — billing_sources left empty until integrations land
    cost_runner = CostRunner(connector_router=router)
    cost.set_runner(cost_runner)

    # Learning runner — stores left empty until DB layer is wired
    learn_runner = LearningRunner()
    learning.set_runner(learn_runner)

    # ── Playbook loader ─────────────────────────────────────────
    playbook_loader = None
    try:
        from shieldops.playbooks.loader import PlaybookLoader

        playbook_loader = PlaybookLoader()
        playbook_loader.load_all()
        logger.info("playbooks_loaded", count=len(playbook_loader.all()))
    except Exception as e:
        logger.warning("playbook_load_failed", error=str(e))

    # Supervisor — orchestrates all specialist agents
    sup_runner = SupervisorRunner(agent_runners={
        "investigation": inv_runner,
        "remediation": rem_runner,
        "security": sec_runner,
        "cost": cost_runner,
        "learning": learn_runner,
    }, playbook_loader=playbook_loader)
    supervisor.set_runner(sup_runner)

    # Register playbooks router
    try:
        from shieldops.api.routes import playbooks
        playbooks.set_loader(playbook_loader)
        app.include_router(
            playbooks.router, prefix=settings.api_prefix, tags=["Playbooks"]
        )
    except Exception as e:
        logger.warning("playbooks_router_failed", error=str(e))

    yield

    logger.info("shieldops_shutting_down")
    await obs_sources.close_all()
    await policy_engine.close()
    if engine:
        await engine.dispose()


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
