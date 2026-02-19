"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

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
    security_chat,
    supervisor,
    teams,
    vulnerabilities,
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

    # ── OpenTelemetry tracing ────────────────────────────────────
    try:
        from shieldops.observability.tracing import init_tracing

        init_tracing(settings)
        logger.info("otel_tracing_started")
    except Exception as e:
        logger.warning("otel_tracing_init_failed", error=str(e))

    # ── Database layer ──────────────────────────────────────────
    repository = None
    session_factory = None
    engine = None
    try:
        from sqlalchemy import text

        from shieldops.db.repository import Repository
        from shieldops.db.session import create_async_engine, get_session_factory

        engine = create_async_engine(settings.database_url, pool_size=settings.database_pool_size)
        session_factory = get_session_factory()
        # Verify DB connectivity with a test query
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        repository = Repository(session_factory)
        logger.info("database_initialized")
    except Exception as e:
        logger.warning("database_init_failed", error=str(e), detail="falling back to in-memory")
        session_factory = None
        repository = None
        if engine:
            try:
                await engine.dispose()
            except Exception:
                logger.debug("engine_dispose_failed_on_fallback")
            engine = None

    # Store on app.state for readiness checks and analytics
    app.state.session_factory = session_factory
    app.state.repository = repository
    app.state.engine = engine

    # ── Agent registry ─────────────────────────────────────────────
    if session_factory:
        try:
            from shieldops.agents.registry import AgentRegistry

            agent_registry = AgentRegistry(session_factory)
            agents.set_registry(agent_registry)
            # Auto-register the 6 agent types
            for atype in (
                "investigation",
                "remediation",
                "security",
                "cost",
                "learning",
                "supervisor",
            ):
                try:
                    await agent_registry.register(
                        agent_type=atype, environment=settings.environment
                    )
                except Exception:
                    logger.debug("agent_register_skipped", agent_type=atype)
            logger.info("agent_registry_initialized")
        except Exception as e:
            logger.warning("agent_registry_init_failed", error=str(e))

    # ── Analytics engine ───────────────────────────────────────────
    if session_factory:
        from shieldops.analytics.engine import AnalyticsEngine

        analytics_engine = AnalyticsEngine(session_factory)
        analytics.set_engine(analytics_engine)
        logger.info("analytics_engine_initialized")

    # ── WebSocket manager (singleton shared with routes) ──────
    from shieldops.api.ws.manager import get_ws_manager

    ws_manager = get_ws_manager()

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
        ws_manager=ws_manager,
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
        ws_manager=ws_manager,
    )
    remediations.set_runner(rem_runner)
    remediations.set_repository(repository)

    # Security runner — wire CVE sources and security scanners
    cve_sources: list[Any] = []
    security_scanners: list[Any] = []
    credential_stores: list[Any] = []

    # NVD CVE source
    try:
        from shieldops.integrations.cve.nvd import NVDCVESource

        cve_sources.append(NVDCVESource(api_key=settings.nvd_api_key))
        logger.info("nvd_cve_source_initialized")
    except Exception as e:
        logger.warning("nvd_cve_source_init_failed", error=str(e))

    # Trivy container scanner
    if settings.trivy_server_url:
        try:
            from shieldops.integrations.scanners.trivy import TrivyCVESource

            cve_sources.append(
                TrivyCVESource(
                    server_url=settings.trivy_server_url,
                    timeout=settings.trivy_timeout,
                )
            )
            logger.info("trivy_cve_source_initialized")
        except Exception as e:
            logger.warning("trivy_cve_source_init_failed", error=str(e))

    # HashiCorp Vault credential store
    try:
        from shieldops.integrations.credentials.vault import VaultCredentialStore

        credential_stores.append(VaultCredentialStore())
        logger.info("vault_credential_store_initialized")
    except Exception as e:
        logger.debug("vault_credential_store_skipped", error=str(e))

    sec_runner = SecurityRunner(
        connector_router=router,
        cve_sources=cve_sources or None,
        credential_stores=credential_stores or None,
        security_scanners=security_scanners or None,
        policy_engine=policy_engine,
        approval_workflow=approval_workflow,
        repository=repository,
    )
    security.set_runner(sec_runner)

    # Vulnerability management route wiring
    vulnerabilities.set_repository(repository)
    teams.set_repository(repository)

    # Security chat — build chat agent from runner + repository
    try:
        from shieldops.agents.security.chat import SecurityChatAgent

        chat_agent = SecurityChatAgent(
            repository=repository,
            security_runner=sec_runner,
            policy_engine=policy_engine,
        )
        security_chat.set_chat_agent(chat_agent)
        security_chat.set_repository(repository)
        logger.info("security_chat_agent_initialized")
    except Exception as e:
        logger.warning("security_chat_init_failed", error=str(e))

    # Cost runner — wire billing sources when credentials are available
    billing_sources: list[Any] = []
    if settings.aws_region:
        try:
            from shieldops.integrations.billing.aws_cost_explorer import (
                AWSCostExplorerSource,
            )

            billing_sources.append(AWSCostExplorerSource(region=settings.aws_region))
            logger.info("aws_billing_source_initialized")
        except Exception as e:
            logger.warning("aws_billing_init_failed", error=str(e))

    cost_runner = CostRunner(
        connector_router=router,
        billing_sources=billing_sources or None,
    )
    cost.set_runner(cost_runner)

    # ── Playbook loader ─────────────────────────────────────────
    playbook_loader = None
    try:
        from shieldops.playbooks.loader import PlaybookLoader

        playbook_loader = PlaybookLoader()
        playbook_loader.load_all()
        logger.info("playbooks_loaded", count=len(playbook_loader.all()))
    except Exception as e:
        logger.warning("playbook_load_failed", error=str(e))

    # Learning runner — wired to DB + playbook stores
    learn_runner = LearningRunner(
        repository=repository,
        playbook_loader=playbook_loader,
    )
    learning.set_runner(learn_runner)

    # ── Notification channels ─────────────────────────────────────
    notification_channels: dict[str, Any] = {}
    if settings.pagerduty_routing_key:
        from shieldops.integrations.notifications.pagerduty import PagerDutyNotifier

        notification_channels["pagerduty"] = PagerDutyNotifier(
            routing_key=settings.pagerduty_routing_key,
        )
        logger.info("pagerduty_notifier_initialized")

    if settings.slack_bot_token:
        from shieldops.integrations.notifications.slack import SlackNotifier

        notification_channels["slack"] = SlackNotifier(
            bot_token=settings.slack_bot_token,
            default_channel=settings.slack_approval_channel,
        )
        logger.info("slack_notifier_initialized")

    if settings.webhook_url:
        from shieldops.integrations.notifications.webhook import (
            WebhookNotifier,
        )

        notification_channels["webhook"] = WebhookNotifier(
            url=settings.webhook_url,
            secret=settings.webhook_secret,
            timeout=settings.webhook_timeout,
        )
        logger.info("webhook_notifier_initialized")

    if settings.smtp_host and settings.smtp_to_addresses:
        from shieldops.integrations.notifications.email import EmailNotifier

        notification_channels["email"] = EmailNotifier(
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
            from_address=settings.smtp_from_address,
            to_addresses=settings.smtp_to_addresses,
        )
        logger.info("email_notifier_initialized")

    # Supervisor — orchestrates all specialist agents
    sup_runner = SupervisorRunner(
        agent_runners={
            "investigation": inv_runner,
            "remediation": rem_runner,
            "security": sec_runner,
            "cost": cost_runner,
            "learning": learn_runner,
        },
        playbook_loader=playbook_loader,
        notification_channels=notification_channels,
    )
    supervisor.set_runner(sup_runner)

    # ── Scheduler ─────────────────────────────────────────────────
    from shieldops.scheduler import JobScheduler
    from shieldops.scheduler.jobs import (
        daily_cost_analysis,
        daily_security_newsletter,
        escalation_check_job,
        nightly_learning_cycle,
        periodic_security_scan,
        sla_check_job,
        vulnerability_dedup_job,
        weekly_security_newsletter,
    )

    # Build notification dispatcher for newsletter/escalation
    notification_dispatcher = None
    try:
        from shieldops.integrations.notifications.dispatcher import (
            NotificationDispatcher,
        )

        notification_dispatcher = NotificationDispatcher(
            channels=notification_channels,
        )
    except Exception as e:
        logger.warning("notification_dispatcher_init_failed", error=str(e))

    scheduler = JobScheduler(redis_url=settings.redis_url)
    scheduler.add_job(
        "nightly_learning",
        nightly_learning_cycle,
        interval_seconds=86400,  # 24 hours
        learning_runner=learn_runner,
    )
    scheduler.add_job(
        "security_scan",
        periodic_security_scan,
        interval_seconds=21600,  # 6 hours
        security_runner=sec_runner,
        environment=settings.environment,
    )
    scheduler.add_job(
        "cost_analysis",
        daily_cost_analysis,
        interval_seconds=86400,  # 24 hours
        cost_runner=cost_runner,
        environment=settings.environment,
    )
    scheduler.add_job(
        "sla_check",
        sla_check_job,
        interval_seconds=3600,  # 1 hour
        repository=repository,
    )
    scheduler.add_job(
        "vuln_dedup",
        vulnerability_dedup_job,
        interval_seconds=86400,  # 24 hours
        repository=repository,
    )
    scheduler.add_job(
        "daily_newsletter",
        daily_security_newsletter,
        interval_seconds=86400,  # 24 hours
        repository=repository,
        notification_dispatcher=notification_dispatcher,
    )
    scheduler.add_job(
        "weekly_newsletter",
        weekly_security_newsletter,
        interval_seconds=604800,  # 7 days
        repository=repository,
        notification_dispatcher=notification_dispatcher,
    )
    scheduler.add_job(
        "escalation_check",
        escalation_check_job,
        interval_seconds=3600,  # 1 hour
        repository=repository,
        notification_dispatcher=notification_dispatcher,
    )
    await scheduler.start()
    app.state.scheduler = scheduler
    logger.info("scheduler_initialized", jobs=len(scheduler.list_jobs()))

    # ── Newsletter service ─────────────────────────────────────────
    try:
        from shieldops.api.routes import newsletters
        from shieldops.vulnerability.newsletter import SecurityNewsletterService

        newsletter_service = SecurityNewsletterService(
            repository=repository,
            notification_dispatcher=notification_dispatcher,
        )
        newsletters.set_service(newsletter_service)
        newsletters.set_repository(repository)
        app.include_router(newsletters.router, prefix=settings.api_prefix, tags=["Newsletters"])
        logger.info("newsletter_service_initialized")
    except Exception as e:
        logger.warning("newsletter_init_failed", error=str(e))

    # Register playbooks router
    try:
        from shieldops.api.routes import playbooks

        playbooks.set_loader(playbook_loader)
        app.include_router(playbooks.router, prefix=settings.api_prefix, tags=["Playbooks"])
    except Exception as e:
        logger.warning("playbooks_router_failed", error=str(e))

    yield

    logger.info("shieldops_shutting_down")

    # ── Graceful request draining ──────────────────────────────
    from shieldops.api.middleware.shutdown import get_shutdown_state

    shutdown_state = get_shutdown_state()
    shutdown_state.signal_shutdown()
    logger.info("shutdown_signaled", in_flight=shutdown_state.in_flight)

    drained = await shutdown_state.wait_for_drain(timeout=30.0)
    if drained:
        logger.info("shutdown_drain_complete")
    else:
        logger.warning(
            "shutdown_drain_timeout",
            remaining=shutdown_state.in_flight,
        )

    # ── Resource cleanup ───────────────────────────────────────
    _scheduler = getattr(getattr(app, "state", None), "scheduler", None)
    if _scheduler:
        await _scheduler.stop()
    await obs_sources.close_all()
    await policy_engine.close()
    if engine:
        await engine.dispose()

    # Flush OTEL spans
    try:
        from shieldops.observability.tracing import shutdown_tracing

        shutdown_tracing()
    except Exception as exc:
        logger.debug("otel_shutdown_error", error=str(exc))


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

    # CORS (restricted methods/headers for production security)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    # OpenTelemetry automatic HTTP span creation
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception:  # noqa: S110
        pass  # OTEL instrumentation is optional — may not be installed

    # Middleware stack (order matters: outermost first)
    from shieldops.api.middleware import (
        ErrorHandlerMiddleware,
        GracefulShutdownMiddleware,
        MetricsMiddleware,
        RateLimitMiddleware,
        RequestIDMiddleware,
        RequestLoggingMiddleware,
        SecurityHeadersMiddleware,
    )

    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    # SecurityHeadersMiddleware adds HSTS, CSP, X-Frame-Options, etc.
    app.add_middleware(SecurityHeadersMiddleware)
    # MetricsMiddleware is added last so it wraps all other
    # middleware (Starlette processes add_middleware in LIFO order).
    app.add_middleware(MetricsMiddleware)
    # GracefulShutdownMiddleware outermost: rejects requests early
    # during shutdown and tracks in-flight count for draining.
    app.add_middleware(GracefulShutdownMiddleware)

    # Auth router (no prefix — routes are /auth/*)
    from shieldops.api.auth.routes import router as auth_router

    app.include_router(auth_router, prefix=settings.api_prefix, tags=["Auth"])

    # Register route modules
    app.include_router(agents.router, prefix=settings.api_prefix, tags=["Agents"])
    app.include_router(investigations.router, prefix=settings.api_prefix, tags=["Investigations"])
    app.include_router(remediations.router, prefix=settings.api_prefix, tags=["Remediations"])
    app.include_router(analytics.router, prefix=settings.api_prefix, tags=["Analytics"])
    app.include_router(security.router, prefix=settings.api_prefix, tags=["Security"])
    app.include_router(vulnerabilities.router, prefix=settings.api_prefix, tags=["Vulnerabilities"])
    app.include_router(teams.router, prefix=settings.api_prefix, tags=["Teams"])
    app.include_router(security_chat.router, prefix=settings.api_prefix, tags=["Security Chat"])
    app.include_router(cost.router, prefix=settings.api_prefix, tags=["Cost"])
    app.include_router(learning.router, prefix=settings.api_prefix, tags=["Learning"])
    app.include_router(supervisor.router, prefix=settings.api_prefix, tags=["Supervisor"])

    # WebSocket routes
    from shieldops.api.ws.routes import router as ws_router

    app.include_router(ws_router, tags=["WebSocket"])

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "healthy", "version": settings.app_version}

    @app.get("/metrics", response_class=PlainTextResponse)
    async def prometheus_metrics() -> PlainTextResponse:
        """Expose collected metrics in Prometheus text format."""
        from shieldops.api.middleware.metrics import (
            get_metrics_registry,
        )

        body = get_metrics_registry().collect()
        return PlainTextResponse(
            content=body,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.get("/ready", response_model=None)
    async def readiness_check() -> dict[str, Any] | JSONResponse:
        """Check readiness of all dependencies (DB, Redis, OPA)."""
        import httpx as _httpx

        checks: dict[str, str] = {}
        all_ok = True

        # Database check
        sf = getattr(app.state, "session_factory", None)
        if sf:
            try:
                from sqlalchemy import text

                async with sf() as session:
                    await session.execute(text("SELECT 1"))
                checks["database"] = "ok"
            except Exception as e:
                checks["database"] = f"error: {e}"
                all_ok = False
        else:
            checks["database"] = "not_configured"
            all_ok = False

        # Redis check
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(  # type: ignore[no-untyped-call]
                settings.redis_url, socket_connect_timeout=2
            )
            await r.ping()  # type: ignore[misc]
            await r.aclose()
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = f"error: {e}"
            all_ok = False

        # OPA check
        try:
            async with _httpx.AsyncClient(timeout=2) as client:
                resp = await client.get(f"{settings.opa_endpoint}/health")
                checks["opa"] = "ok" if resp.status_code == 200 else f"status:{resp.status_code}"
                if resp.status_code != 200:
                    all_ok = False
        except Exception as e:
            checks["opa"] = f"error: {e}"
            all_ok = False

        status_code = 200 if all_ok else 503
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ready" if all_ok else "degraded",
                "version": settings.app_version,
                "checks": checks,
            },
        )

    return app


app = create_app()
