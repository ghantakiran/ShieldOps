"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shieldops.agents.investigation.runner import InvestigationRunner
from shieldops.api.routes import agents, analytics, cost, investigations, learning, remediations, security, supervisor
from shieldops.config import settings
from shieldops.observability.factory import create_observability_sources

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown lifecycle."""
    logger.info("shieldops_starting", environment=settings.environment)

    # Initialize observability sources from config
    obs_sources = create_observability_sources(settings)

    # Wire investigation runner with live observability sources
    runner = InvestigationRunner(
        log_sources=obs_sources.log_sources,
        metric_sources=obs_sources.metric_sources,
        trace_sources=obs_sources.trace_sources,
    )
    investigations.set_runner(runner)

    # TODO: Initialize database connections, Kafka consumers, agent registry
    yield
    logger.info("shieldops_shutting_down")
    await obs_sources.close_all()
    # TODO: Graceful shutdown of agents, close connections


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
