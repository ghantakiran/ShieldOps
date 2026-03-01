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
    batch,
    cost,
    investigations,
    learning,
    remediations,
    search,
    security,
    security_chat,
    supervisor,
    teams,
    usage,
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

    # ── OTel metrics pipeline ────────────────────────────────────
    try:
        from shieldops.observability.otel.metrics import init_metrics

        init_metrics(settings.otel_exporter_endpoint)
        logger.info("otel_metrics_started")
    except Exception as e:
        logger.warning("otel_metrics_init_failed", error=str(e))

    # ── LangSmith agent tracing ──────────────────────────────────
    if settings.langsmith_enabled and settings.langsmith_api_key:
        try:
            from shieldops.observability.langsmith import (
                init_langsmith,
            )

            init_langsmith(
                api_key=settings.langsmith_api_key,
                project=settings.langsmith_project,
                enabled=True,
            )
        except Exception as e:
            logger.warning("langsmith_init_failed", error=str(e))

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
                "prediction",
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

    # Build approval notifier for Slack (no-op when token is empty)
    approval_notifier = None
    try:
        from shieldops.policy.approval.notifier import ApprovalNotifier

        approval_notifier = ApprovalNotifier(
            slack_bot_token=settings.slack_bot_token,
            slack_channel=settings.slack_approval_channel,
        )
        if approval_notifier.enabled:
            logger.info("approval_notifier_initialized", channel=settings.slack_approval_channel)
    except Exception as e:
        logger.warning("approval_notifier_init_failed", error=str(e))

    approval_workflow = ApprovalWorkflow(notifier=approval_notifier)

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

    # GCP Secret Manager credential store
    if settings.gcp_project_id and settings.gcp_secret_manager_enabled:
        try:
            from shieldops.integrations.credentials.gcp_secrets import GCPSecretManagerStore

            credential_stores.append(GCPSecretManagerStore(project_id=settings.gcp_project_id))
            logger.info("gcp_secret_manager_initialized")
        except Exception as e:
            logger.debug("gcp_secret_manager_skipped", error=str(e))

    # Azure Key Vault credential store
    if settings.azure_keyvault_url:
        try:
            from shieldops.integrations.credentials.azure_keyvault import AzureKeyVaultStore

            credential_stores.append(AzureKeyVaultStore(vault_url=settings.azure_keyvault_url))
            logger.info("azure_keyvault_initialized")
        except Exception as e:
            logger.debug("azure_keyvault_skipped", error=str(e))

    # GitHub Advisory Database (GHSA) CVE source
    if settings.ghsa_enabled:
        try:
            from shieldops.integrations.cve.ghsa import GHSACVESource

            cve_sources.append(GHSACVESource(token=settings.github_advisory_token))
            logger.info("ghsa_cve_source_initialized")
        except Exception as e:
            logger.warning("ghsa_cve_source_init_failed", error=str(e))

    # OS Advisory Feeds (Ubuntu USN + Red Hat RHSA)
    if settings.os_advisory_feeds_enabled:
        try:
            from shieldops.integrations.cve.os_advisories import (
                RedHatRHSASource,
                UbuntuUSNSource,
            )

            cve_sources.append(UbuntuUSNSource())
            cve_sources.append(RedHatRHSASource())
            logger.info("os_advisory_feeds_initialized")
        except Exception as e:
            logger.warning("os_advisory_feeds_init_failed", error=str(e))

    # IaC Scanner (Checkov)
    if settings.iac_scanner_enabled:
        try:
            from shieldops.integrations.scanners.iac_scanner import (
                IaCScanner,
            )

            security_scanners.append(IaCScanner(checkov_path=settings.checkov_path))
            logger.info("iac_scanner_initialized")
        except Exception as e:
            logger.warning("iac_scanner_init_failed", error=str(e))

    # Git Scanners (gitleaks + osv-scanner)
    if settings.git_scanner_enabled:
        try:
            from shieldops.integrations.scanners.git_scanner import (
                GitDependencyScanner,
                GitSecretScanner,
            )

            security_scanners.append(
                GitSecretScanner(
                    gitleaks_path=settings.gitleaks_path,
                )
            )
            security_scanners.append(
                GitDependencyScanner(
                    osv_scanner_path=settings.osv_scanner_path,
                )
            )
            logger.info("git_scanners_initialized")
        except Exception as e:
            logger.warning("git_scanners_init_failed", error=str(e))

    # Kubernetes Security Scanner
    if settings.k8s_scanner_enabled:
        try:
            from shieldops.integrations.scanners.k8s_security import (
                K8sSecurityScanner,
            )

            security_scanners.append(K8sSecurityScanner(connector_router=router))
            logger.info("k8s_scanner_initialized")
        except Exception as e:
            logger.warning("k8s_scanner_init_failed", error=str(e))

    # Network Scanner
    if settings.network_scanner_enabled:
        try:
            from shieldops.integrations.scanners.network_scanner import (
                NetworkSecurityScanner,
            )

            security_scanners.append(NetworkSecurityScanner(connector_router=router))
            logger.info("network_scanner_initialized")
        except Exception as e:
            logger.warning("network_scanner_init_failed", error=str(e))

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

    # Search route wiring
    search.set_repository(repository)

    # Batch operations route wiring
    batch.set_repository(repository)

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

    # GCP Cloud Billing
    if settings.gcp_project_id:
        try:
            from shieldops.integrations.billing.gcp_billing import (
                GCPBillingSource,
            )

            billing_sources.append(
                GCPBillingSource(
                    project_id=settings.gcp_project_id,
                    dataset=settings.gcp_billing_dataset,
                    table=settings.gcp_billing_table,
                )
            )
            logger.info("gcp_billing_source_initialized")
        except Exception as e:
            logger.warning("gcp_billing_init_failed", error=str(e))

    # Azure Cost Management
    if settings.azure_subscription_id:
        try:
            from shieldops.integrations.billing.azure_cost import (
                AzureCostManagementSource,
            )

            billing_sources.append(
                AzureCostManagementSource(
                    subscription_id=settings.azure_subscription_id,
                    resource_group=(settings.azure_resource_group or None),
                )
            )
            logger.info("azure_billing_source_initialized")
        except Exception as e:
            logger.warning(
                "azure_billing_init_failed",
                error=str(e),
            )

    # Stripe SaaS billing
    if settings.stripe_api_key:
        try:
            from shieldops.api.routes import billing as billing_routes
            from shieldops.integrations.billing.stripe_billing import (
                StripeClient,
            )

            stripe_client = StripeClient(
                api_key=settings.stripe_api_key,
                webhook_secret=settings.stripe_webhook_secret,
            )
            billing_routes.set_stripe_client(stripe_client)
            app.include_router(
                billing_routes.router,
                prefix=settings.api_prefix,
                tags=["Billing"],
            )
            logger.info("stripe_billing_initialized")
        except Exception as e:
            logger.warning("stripe_billing_init_failed", error=str(e))

    # ── Billing enforcement service ──────────────────────────────
    try:
        from shieldops.api.middleware.billing_enforcement import (
            BillingEnforcementMiddleware,
        )
        from shieldops.billing.enforcement import PlanEnforcementService

        enforcement_service = PlanEnforcementService(
            session_factory=session_factory,
        )
        BillingEnforcementMiddleware.set_enforcement_service(enforcement_service)

        # Also wire into billing routes for /billing/usage endpoint
        try:
            from shieldops.api.routes import billing as billing_routes

            billing_routes.set_enforcement_service(enforcement_service)
        except Exception:  # noqa: S110
            pass  # billing routes may not be loaded yet

        logger.info("billing_enforcement_initialized")
    except Exception as e:
        logger.warning("billing_enforcement_init_failed", error=str(e))

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

    # ── Template loader (Marketplace) ────────────────────────────
    template_loader = None
    try:
        from shieldops.api.routes import marketplace
        from shieldops.playbooks.template_loader import TemplateLoader

        template_loader = TemplateLoader()
        template_loader.load_all()
        marketplace.set_template_loader(template_loader)
        app.include_router(
            marketplace.router,
            prefix=settings.api_prefix,
            tags=["Marketplace"],
        )
        logger.info("marketplace_initialized", templates=len(template_loader.all_templates()))
    except Exception as e:
        logger.warning("marketplace_init_failed", error=str(e))

    # Learning runner — wired to DB + playbook stores
    learn_runner = LearningRunner(
        repository=repository,
        playbook_loader=playbook_loader,
    )
    learning.set_runner(learn_runner)

    # ── Notification config CRUD ──────────────────────────────────
    if session_factory:
        try:
            from shieldops.api.routes import notification_config

            notification_config.set_session_factory(session_factory)
            app.include_router(
                notification_config.router,
                prefix=settings.api_prefix,
                tags=["Notification Config"],
            )
            logger.info("notification_config_routes_initialized")
        except Exception as e:
            logger.warning("notification_config_routes_failed", error=str(e))

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

    # ── Kafka Event Bus ──────────────────────────────────────────────
    event_bus = None
    try:
        from shieldops.messaging.alert_handler import AlertEventHandler
        from shieldops.messaging.bus import EventBus

        event_bus = EventBus(
            brokers=settings.kafka_brokers,
            group_id=settings.kafka_consumer_group,
        )
        alert_handler = AlertEventHandler(investigation_runner=inv_runner)
        await event_bus.start()

        import asyncio

        asyncio.create_task(event_bus.consumer.consume(alert_handler.handle))
        app.state.event_bus = event_bus
        logger.info("event_bus_started")
    except Exception as e:
        logger.warning("event_bus_init_failed", error=str(e))

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

    # Agent context store
    if repository:
        try:
            from shieldops.agents.context_store import AgentContextStore
            from shieldops.api.routes import agent_context

            ctx_store = AgentContextStore(repository=repository)
            agent_context.set_store(ctx_store)
            app.include_router(
                agent_context.router,
                prefix=settings.api_prefix,
                tags=["Agent Context"],
            )
            logger.info("agent_context_store_initialized")
        except Exception as e:
            logger.warning("agent_context_init_failed", error=str(e))

    # Audit log routes
    try:
        from shieldops.api.routes import audit

        audit.set_repository(repository)
        app.include_router(audit.router, prefix=settings.api_prefix, tags=["Audit"])
        logger.info("audit_routes_initialized")
    except Exception as e:
        logger.warning("audit_routes_failed", error=str(e))

    # Data export / compliance report routes
    try:
        from shieldops.api.routes import exports

        exports.set_repository(repository)
        app.include_router(exports.router, prefix=settings.api_prefix, tags=["Export"])
        logger.info("export_routes_initialized")
    except Exception as e:
        logger.warning("export_routes_failed", error=str(e))

    # Register playbooks router
    try:
        from shieldops.api.routes import playbooks

        playbooks.set_loader(playbook_loader)
        app.include_router(
            playbooks.router,
            prefix=settings.api_prefix,
            tags=["Playbooks"],
        )
    except Exception as e:
        logger.warning("playbooks_router_failed", error=str(e))

    # Playbook CRUD router (custom playbook editor)
    try:
        from shieldops.api.routes import playbook_crud

        playbook_crud.set_repository(repository)
        app.include_router(
            playbook_crud.router,
            prefix=settings.api_prefix,
            tags=["Playbook Editor"],
        )
        logger.info("playbook_crud_routes_initialized")
    except Exception as e:
        logger.warning(
            "playbook_crud_routes_failed",
            error=str(e),
        )

    # User management routes
    try:
        from shieldops.api.routes import users

        app.include_router(
            users.router,
            prefix=settings.api_prefix,
            tags=["Users"],
        )
        logger.info("user_management_routes_initialized")
    except Exception as e:
        logger.warning("user_routes_failed", error=str(e))

    # API key management routes
    try:
        from shieldops.api.routes import api_keys as api_keys_routes

        api_keys_routes.set_repository(repository)
        app.include_router(
            api_keys_routes.router,
            prefix=settings.api_prefix,
            tags=["API Keys"],
        )
        logger.info("api_key_routes_initialized")
    except Exception as e:
        logger.warning("api_key_routes_failed", error=str(e))

    # Notification preferences routes (per-user)
    try:
        from shieldops.api.routes import notification_prefs

        notification_prefs.set_repository(repository)
        app.include_router(
            notification_prefs.router,
            prefix=settings.api_prefix,
            tags=["Notification Preferences"],
        )
        logger.info("notification_prefs_routes_initialized")
    except Exception as e:
        logger.warning("notification_prefs_routes_failed", error=str(e))

    # Permissions routes (RBAC matrix inspection)
    try:
        from shieldops.api.routes import permissions as permissions_routes

        app.include_router(
            permissions_routes.router,
            prefix=settings.api_prefix,
            tags=["Permissions"],
        )
        logger.info("permissions_routes_initialized")
    except Exception as e:
        logger.warning("permissions_routes_failed", error=str(e))

    # Organization management routes (multi-tenant)
    try:
        from shieldops.api.routes import organizations

        organizations.set_repository(repository)
        app.include_router(
            organizations.router,
            prefix=settings.api_prefix,
            tags=["Organizations"],
        )
        logger.info("organization_routes_initialized")
    except Exception as e:
        logger.warning("organization_routes_failed", error=str(e))

    # Onboarding wizard routes
    try:
        from shieldops.api.routes import onboarding

        onboarding.set_repository(repository)
        app.include_router(
            onboarding.router,
            prefix=settings.api_prefix,
            tags=["Onboarding"],
        )
        logger.info("onboarding_routes_initialized")
    except Exception as e:
        logger.warning("onboarding_routes_failed", error=str(e))

    # ── Redis Cache Layer ──────────────────────────────────────────
    redis_cache = None
    try:
        from shieldops.api.routes import cache as cache_routes
        from shieldops.cache import RedisCache
        from shieldops.cache import set_cache as set_decorator_cache

        redis_cache = RedisCache(redis_url=settings.redis_url)
        await redis_cache.connect()
        cache_routes.set_cache(redis_cache)
        set_decorator_cache(redis_cache)
        app.include_router(
            cache_routes.router,
            prefix=settings.api_prefix,
            tags=["Cache"],
        )
        logger.info("redis_cache_initialized")
    except Exception as e:
        logger.warning("redis_cache_init_failed", error=str(e))
    app.state.redis_cache = redis_cache

    # ── Background Task Queue ────────────────────────────────────────
    task_queue = None
    try:
        from shieldops.api.routes import task_queue as task_queue_routes
        from shieldops.workers import TaskQueue

        task_queue = TaskQueue(max_workers=4)
        await task_queue.start()
        task_queue_routes.set_task_queue(task_queue)
        app.include_router(
            task_queue_routes.router,
            prefix=settings.api_prefix,
            tags=["Task Queue"],
        )
        logger.info("task_queue_initialized")
    except Exception as e:
        logger.warning("task_queue_init_failed", error=str(e))
    app.state.task_queue = task_queue

    # ── Database Migrations API ─────────────────────────────────
    try:
        from shieldops.api.routes import migrations as migrations_routes
        from shieldops.db import migrate as migrate_module

        migrations_routes.set_migrator(migrate_module)
        logger.info("migration_service_initialized")
    except Exception as e:
        logger.warning("migration_service_init_failed", error=str(e))

    # ── Incident Correlation Engine ──────────────────────────────
    try:
        from shieldops.agents.investigation.correlation import CorrelationEngine
        from shieldops.api.routes import incidents as incidents_routes

        correlation_engine = CorrelationEngine(
            time_window_minutes=30,
            similarity_threshold=0.5,
        )
        incidents_routes.set_engine(correlation_engine)
        incidents_routes.set_repository(repository)
        app.include_router(
            incidents_routes.router,
            prefix=settings.api_prefix,
            tags=["Incidents"],
        )
        logger.info("incident_correlation_initialized")
    except Exception as e:
        logger.warning("incident_correlation_init_failed", error=str(e))

    # ── Git Playbook Sync (Runbook-as-Code) ──────────────────────
    if getattr(settings, "playbook_git_repo_url", None):
        try:
            from shieldops.api.routes import git_playbooks
            from shieldops.playbooks.git_sync import GitPlaybookSync

            git_sync = GitPlaybookSync(
                repo_url=getattr(settings, "playbook_git_repo_url", ""),
                branch=getattr(settings, "playbook_git_branch", "main"),
            )
            git_playbooks.set_git_sync(git_sync)
            app.include_router(
                git_playbooks.router,
                prefix=settings.api_prefix,
                tags=["Git Playbooks"],
            )
            logger.info("git_playbook_sync_initialized")
        except Exception as e:
            logger.warning("git_playbook_sync_init_failed", error=str(e))

    # ── Custom Webhook Triggers ──────────────────────────────────
    try:
        from shieldops.api.routes import webhook_triggers

        webhook_triggers.set_investigation_runner(inv_runner)
        if getattr(settings, "webhook_trigger_secret", None):
            webhook_triggers.set_webhook_secret(getattr(settings, "webhook_trigger_secret", ""))
        app.include_router(
            webhook_triggers.router,
            prefix=settings.api_prefix,
            tags=["Webhook Triggers"],
        )
        logger.info("webhook_triggers_initialized")
    except Exception as e:
        logger.warning("webhook_triggers_init_failed", error=str(e))

    # OIDC / SSO authentication
    if settings.oidc_enabled and settings.oidc_issuer_url:
        try:
            from shieldops.auth import routes as oidc_routes
            from shieldops.auth.oidc import OIDCClient

            oidc_client = OIDCClient(
                issuer_url=settings.oidc_issuer_url,
                client_id=settings.oidc_client_id,
                client_secret=settings.oidc_client_secret,
                redirect_uri=settings.oidc_redirect_uri,
                scopes=settings.oidc_scopes,
            )
            oidc_routes.set_oidc_client(oidc_client)
            app.include_router(
                oidc_routes.router,
                prefix=settings.api_prefix,
                tags=["Auth"],
            )
            logger.info(
                "oidc_authentication_initialized",
                issuer=settings.oidc_issuer_url,
            )
        except Exception as e:
            logger.warning("oidc_init_failed", error=str(e))

    # ── Agent Simulation Mode (dry-run remediations) ──────────────
    try:
        from shieldops.agents.remediation.simulator import RemediationSimulator
        from shieldops.api.routes import simulations

        sim = RemediationSimulator(policy_engine=policy_engine)
        simulations.set_simulator(sim)
        app.include_router(
            simulations.router,
            prefix=settings.api_prefix,
            tags=["Simulations"],
        )
        logger.info("remediation_simulator_initialized")
    except Exception as e:
        logger.warning("remediation_simulator_init_failed", error=str(e))

    # ── Cost Optimization Autopilot ──────────────────────────────
    try:
        from shieldops.agents.cost.autopilot import CostAutopilot
        from shieldops.api.routes import autopilot as autopilot_routes

        cost_autopilot = CostAutopilot()
        autopilot_routes.set_autopilot(cost_autopilot)
        app.include_router(
            autopilot_routes.router,
            prefix=settings.api_prefix,
            tags=["Cost Autopilot"],
        )
        logger.info("cost_autopilot_initialized")
    except Exception as e:
        logger.warning("cost_autopilot_init_failed", error=str(e))

    # ── Mobile Push Notifications ────────────────────────────────
    try:
        from shieldops.api.routes import devices as devices_routes
        from shieldops.integrations.notifications.push import PushNotifier

        push_notifier = PushNotifier(
            fcm_server_key=getattr(settings, "fcm_server_key", ""),
            apns_key=getattr(settings, "apns_key", ""),
        )
        devices_routes.set_push_notifier(push_notifier)
        app.include_router(
            devices_routes.router,
            prefix=settings.api_prefix,
            tags=["Devices"],
        )
        notification_channels["push"] = push_notifier
        logger.info("push_notifications_initialized")
    except Exception as e:
        logger.warning("push_notifications_init_failed", error=str(e))

    # ── GraphQL API Layer ────────────────────────────────────────
    try:
        from shieldops.api.graphql.routes import router as graphql_router
        from shieldops.api.graphql.routes import set_resolver
        from shieldops.api.graphql.schema import QueryResolver

        gql_resolver = QueryResolver(repository=repository)
        set_resolver(gql_resolver)
        app.include_router(
            graphql_router,
            prefix=settings.api_prefix,
            tags=["GraphQL"],
        )
        logger.info("graphql_api_initialized")
    except Exception as e:
        logger.warning("graphql_api_init_failed", error=str(e))

    # ── SOC2 Compliance Engine ────────────────────────────────────
    try:
        from shieldops.api.routes import compliance as compliance_routes
        from shieldops.compliance.soc2 import SOC2ComplianceEngine

        soc2_engine = SOC2ComplianceEngine()
        compliance_routes.set_engine(soc2_engine)
        app.include_router(
            compliance_routes.router,
            prefix=settings.api_prefix,
            tags=["Compliance"],
        )
        logger.info("soc2_compliance_engine_initialized")
    except Exception as e:
        logger.warning("soc2_compliance_init_failed", error=str(e))

    # ── Jira ITSM Integration ───────────────────────────────────
    if getattr(settings, "jira_base_url", None):
        try:
            from shieldops.api.routes import jira as jira_routes
            from shieldops.integrations.itsm.jira import JiraClient, JiraConfig

            jira_config = JiraConfig(
                base_url=getattr(settings, "jira_base_url", ""),
                email=getattr(settings, "jira_email", ""),
                api_token=getattr(settings, "jira_api_token", ""),
                project_key=getattr(settings, "jira_project_key", "OPS"),
            )
            jira_client = JiraClient(
                base_url=jira_config.base_url,
                email=jira_config.email,
                api_token=jira_config.api_token,
                project_key=jira_config.project_key,
            )
            jira_routes.set_client(jira_client)
            jira_routes.set_config(jira_config)
            app.include_router(
                jira_routes.router,
                prefix=settings.api_prefix,
                tags=["Jira"],
            )
            logger.info("jira_integration_initialized")
        except Exception as e:
            logger.warning("jira_integration_init_failed", error=str(e))

    # ── ServiceNow ITSM Integration ─────────────────────────────
    if getattr(settings, "servicenow_instance_url", None):
        try:
            from shieldops.api.routes import servicenow as servicenow_routes
            from shieldops.integrations.itsm.servicenow import ServiceNowClient

            snow_client = ServiceNowClient(
                instance_url=getattr(settings, "servicenow_instance_url", ""),
                username=getattr(settings, "servicenow_username", ""),
                password=getattr(settings, "servicenow_password", ""),
            )
            servicenow_routes.set_client(snow_client)
            app.include_router(
                servicenow_routes.router,
                prefix=settings.api_prefix,
                tags=["ServiceNow"],
            )
            logger.info("servicenow_integration_initialized")
        except Exception as e:
            logger.warning("servicenow_integration_init_failed", error=str(e))

    # ── Terraform Drift Detection ───────────────────────────────
    try:
        from shieldops.agents.security.drift import DriftDetector
        from shieldops.api.routes import drift as drift_routes

        drift_detector = DriftDetector(connector_router=router)
        drift_routes.set_detector(drift_detector)
        app.include_router(
            drift_routes.router,
            prefix=settings.api_prefix,
            tags=["Drift Detection"],
        )
        logger.info("drift_detection_initialized")
    except Exception as e:
        logger.warning("drift_detection_init_failed", error=str(e))

    # ── SLA Management Engine ───────────────────────────────────
    try:
        from shieldops.api.routes import sla as sla_routes
        from shieldops.sla.engine import SLAEngine

        sla_engine = SLAEngine()
        sla_routes.set_engine(sla_engine)
        app.include_router(
            sla_routes.router,
            prefix=settings.api_prefix,
            tags=["SLA"],
        )
        logger.info("sla_engine_initialized")
    except Exception as e:
        logger.warning("sla_engine_init_failed", error=str(e))

    # ── Anomaly Detection Engine ────────────────────────────────
    try:
        from shieldops.analytics.anomaly import AnomalyDetector
        from shieldops.api.routes import anomaly as anomaly_routes

        anomaly_detector = AnomalyDetector()
        anomaly_routes.set_detector(anomaly_detector)
        app.include_router(
            anomaly_routes.router,
            prefix=settings.api_prefix,
            tags=["Anomaly Detection"],
        )
        logger.info("anomaly_detection_initialized")
    except Exception as e:
        logger.warning("anomaly_detection_init_failed", error=str(e))

    # ── Service Dependency Map ──────────────────────────────────
    try:
        from shieldops.api.routes import topology as topology_routes
        from shieldops.topology.graph import ServiceGraphBuilder

        graph_builder = ServiceGraphBuilder()
        topology_routes.set_builder(graph_builder)
        app.include_router(
            topology_routes.router,
            prefix=settings.api_prefix,
            tags=["Topology"],
        )
        logger.info("service_topology_initialized")
    except Exception as e:
        logger.warning("service_topology_init_failed", error=str(e))

    # ── Change Tracking / Deployment Correlation ────────────────
    try:
        from shieldops.api.routes import changes as changes_routes
        from shieldops.changes.tracker import ChangeTracker

        change_tracker = ChangeTracker()
        changes_routes.set_tracker(change_tracker)
        app.include_router(
            changes_routes.router,
            prefix=settings.api_prefix,
            tags=["Changes"],
        )
        logger.info("change_tracking_initialized")
    except Exception as e:
        logger.warning("change_tracking_init_failed", error=str(e))

    # ── Custom Agent Builder ────────────────────────────────────
    # Registered BEFORE the agents router to prevent /agents/{agent_id}
    # from capturing /agents/custom paths.
    try:
        from shieldops.agents.custom.builder import CustomAgentBuilder
        from shieldops.api.routes import custom_agents as custom_agents_routes

        agent_builder = CustomAgentBuilder()
        custom_agents_routes.set_builder(agent_builder)
        app.include_router(
            custom_agents_routes.router,
            prefix=settings.api_prefix,
            tags=["Custom Agents"],
        )
        logger.info("custom_agent_builder_initialized")
    except Exception as e:
        logger.warning("custom_agent_builder_init_failed", error=str(e))

    # ── Phase 11: Chat Session Store ─────────────────────────────
    try:
        from shieldops.api.routes.chat_session_store import (
            InMemoryChatStore,
            RedisChatSessionStore,
        )

        chat_store: Any = None
        if redis_cache is not None:
            try:
                chat_store = RedisChatSessionStore(
                    redis_url=settings.redis_url,
                    ttl=settings.chat_session_ttl_seconds,
                    max_messages=settings.chat_max_messages_per_session,
                )
                await chat_store.connect()
                logger.info("redis_chat_session_store_initialized")
            except Exception as e:
                logger.warning("redis_chat_store_failed_fallback", error=str(e))
                chat_store = InMemoryChatStore(
                    max_messages=settings.chat_max_messages_per_session,
                )
        else:
            chat_store = InMemoryChatStore(
                max_messages=settings.chat_max_messages_per_session,
            )

        security_chat.set_session_store(chat_store)
        app.state.chat_session_store = chat_store
        logger.info("chat_session_store_initialized", store=getattr(chat_store, "store_name", ""))
    except Exception as e:
        logger.warning("chat_session_store_init_failed", error=str(e))

    # ── Phase 11: SBOM Generator ─────────────────────────────────
    sbom_generator = None
    if settings.sbom_enabled:
        try:
            from shieldops.api.routes import sbom as sbom_routes
            from shieldops.integrations.scanners.sbom_generator import SBOMGenerator

            sbom_generator = SBOMGenerator(syft_path=settings.syft_path)
            sbom_routes.set_generator(sbom_generator)
            app.include_router(
                sbom_routes.router,
                prefix=settings.api_prefix,
                tags=["SBOM"],
            )
            logger.info("sbom_generator_initialized")
        except Exception as e:
            logger.warning("sbom_generator_init_failed", error=str(e))

    # ── Phase 11: Threat Intelligence (MITRE ATT&CK + EPSS) ─────
    try:
        from shieldops.api.routes import threat_intel as threat_intel_routes
        from shieldops.integrations.threat_intel.epss import EPSSScorer
        from shieldops.integrations.threat_intel.mitre_attack import MITREAttackMapper

        mitre_mapper = MITREAttackMapper()
        threat_intel_routes.set_mitre_mapper(mitre_mapper)

        epss_scorer = EPSSScorer()
        threat_intel_routes.set_epss_scorer(epss_scorer)

        app.include_router(
            threat_intel_routes.router,
            prefix=settings.api_prefix,
            tags=["Threat Intel"],
        )
        logger.info("threat_intel_initialized")
    except Exception as e:
        logger.warning("threat_intel_init_failed", error=str(e))

    # ── Phase 11: AI Playbook Generator ──────────────────────────
    try:
        from shieldops.api.routes import ai_playbooks as ai_playbook_routes
        from shieldops.playbooks.ai_generator import AIPlaybookGenerator

        ai_playbook_gen = AIPlaybookGenerator(repository=repository)
        ai_playbook_routes.set_generator(ai_playbook_gen)
        app.include_router(
            ai_playbook_routes.router,
            prefix=settings.api_prefix,
            tags=["AI Playbooks"],
        )
        logger.info("ai_playbook_generator_initialized")
    except Exception as e:
        logger.warning("ai_playbook_generator_init_failed", error=str(e))

    # ── Phase 11: Security Posture Dashboard ─────────────────────
    posture_aggregator = None
    try:
        from shieldops.api.routes import security_posture as posture_routes
        from shieldops.vulnerability.posture_aggregator import PostureAggregator

        posture_aggregator = PostureAggregator(repository=repository)
        posture_routes.set_aggregator(posture_aggregator)
        app.include_router(
            posture_routes.router,
            prefix=settings.api_prefix,
            tags=["Security Posture"],
        )
        logger.info("security_posture_initialized")
    except Exception as e:
        logger.warning("security_posture_init_failed", error=str(e))

    # ── Phase 11: Security Report Generator ──────────────────────
    try:
        from shieldops.api.routes import security_reports as report_routes
        from shieldops.vulnerability.report_generator import SecurityReportGenerator

        report_gen = SecurityReportGenerator(
            posture_aggregator=posture_aggregator,
            repository=repository,
        )
        report_routes.set_generator(report_gen)
        app.include_router(
            report_routes.router,
            prefix=settings.api_prefix,
            tags=["Security Reports"],
        )
        logger.info("security_report_generator_initialized")
    except Exception as e:
        logger.warning("security_report_generator_init_failed", error=str(e))

    # ── Phase 11: Attack Surface Mapping ─────────────────────────
    try:
        from shieldops.api.routes import attack_surface as attack_surface_routes
        from shieldops.vulnerability.attack_surface import AttackSurfaceMapper

        attack_mapper = AttackSurfaceMapper(
            connector_router=router,
            repository=repository,
            credential_stores=credential_stores,
        )
        attack_surface_routes.set_mapper(attack_mapper)
        app.include_router(
            attack_surface_routes.router,
            prefix=settings.api_prefix,
            tags=["Attack Surface"],
        )
        logger.info("attack_surface_mapper_initialized")
    except Exception as e:
        logger.warning("attack_surface_mapper_init_failed", error=str(e))

    # ── Phase 12: Playbook Auto-Applier ─────────────────────────
    try:
        from shieldops.api.routes import learning_approvals
        from shieldops.playbooks.auto_applier import PlaybookAutoApplier

        auto_applier = PlaybookAutoApplier(playbook_loader=playbook_loader)
        learning_approvals.set_applier(auto_applier)
        app.include_router(
            learning_approvals.router,
            prefix=settings.api_prefix,
            tags=["Learning Approvals"],
        )
        logger.info("playbook_auto_applier_initialized")
    except Exception as e:
        logger.warning("playbook_auto_applier_init_failed", error=str(e))

    # ── Phase 12: Prediction Agent ────────────────────────────
    try:
        from shieldops.agents.prediction.runner import PredictionRunner
        from shieldops.api.routes import predictions as predictions_routes

        prediction_runner = PredictionRunner()
        predictions_routes.set_runner(prediction_runner)
        app.include_router(
            predictions_routes.router,
            prefix=settings.api_prefix,
            tags=["Predictions"],
        )
        logger.info("prediction_agent_initialized")
    except Exception as e:
        logger.warning("prediction_agent_init_failed", error=str(e))

    # ── Phase 12: RAG Knowledge Store ─────────────────────────
    try:
        from shieldops.agents.knowledge.rag_store import RAGStore
        from shieldops.api.routes import knowledge as knowledge_routes

        rag_store = RAGStore()
        knowledge_routes.set_store(rag_store)
        app.include_router(
            knowledge_routes.router,
            prefix=settings.api_prefix,
            tags=["Knowledge"],
        )
        logger.info("rag_knowledge_store_initialized")
    except Exception as e:
        logger.warning("rag_knowledge_store_init_failed", error=str(e))

    # ── Phase 12: LLM Router ─────────────────────────────────
    try:
        from shieldops.api.routes import llm_usage as llm_usage_routes
        from shieldops.utils.llm_router import LLMRouter, ModelTier, TaskComplexity

        model_tiers = {
            TaskComplexity.SIMPLE: ModelTier(
                provider="anthropic",
                model=settings.llm_simple_model,
                cost_per_1k_input=0.001,
                cost_per_1k_output=0.005,
            ),
            TaskComplexity.MODERATE: ModelTier(
                provider="anthropic",
                model=settings.llm_moderate_model,
                cost_per_1k_input=0.003,
                cost_per_1k_output=0.015,
            ),
            TaskComplexity.COMPLEX: ModelTier(
                provider="anthropic",
                model=settings.llm_complex_model,
                cost_per_1k_input=0.015,
                cost_per_1k_output=0.075,
            ),
        }
        llm_router = LLMRouter(
            model_tiers=model_tiers,
            enabled=settings.llm_routing_enabled,
        )
        llm_usage_routes.set_llm_router(llm_router)
        app.include_router(
            llm_usage_routes.router,
            prefix=settings.api_prefix,
            tags=["LLM Usage"],
        )
        logger.info("llm_router_initialized")
    except Exception as e:
        logger.warning("llm_router_init_failed", error=str(e))

    # ── Phase 12: Capacity Planner ────────────────────────────
    try:
        from shieldops.analytics.capacity_planner import CapacityPlanner
        from shieldops.api.routes import capacity as capacity_routes

        capacity_planner = CapacityPlanner()
        capacity_routes.set_planner(capacity_planner)
        app.include_router(
            capacity_routes.router,
            prefix=settings.api_prefix,
            tags=["Capacity Planning"],
        )
        logger.info("capacity_planner_initialized")
    except Exception as e:
        logger.warning("capacity_planner_init_failed", error=str(e))

    # ── Phase 12: PCI-DSS + HIPAA Compliance ──────────────────
    try:
        from shieldops.api.routes import compliance_reports
        from shieldops.compliance.hipaa import HIPAAEngine
        from shieldops.compliance.pci_dss import PCIDSSEngine

        pci_engine = PCIDSSEngine()
        hipaa_engine = HIPAAEngine()
        compliance_reports.set_pci_engine(pci_engine)
        compliance_reports.set_hipaa_engine(hipaa_engine)
        app.include_router(
            compliance_reports.router,
            prefix=settings.api_prefix,
            tags=["Compliance Reports"],
        )
        logger.info("pci_hipaa_compliance_initialized")
    except Exception as e:
        logger.warning("pci_hipaa_compliance_init_failed", error=str(e))

    # ── Phase 12: Outbound Webhooks ───────────────────────────
    try:
        from shieldops.api.routes import webhook_subscriptions
        from shieldops.integrations.outbound.webhook_dispatcher import (
            OutboundWebhookDispatcher,
        )

        webhook_dispatcher = OutboundWebhookDispatcher()
        webhook_subscriptions.set_dispatcher(webhook_dispatcher)
        app.include_router(
            webhook_subscriptions.router,
            prefix=settings.api_prefix,
            tags=["Outbound Webhooks"],
        )
        logger.info("outbound_webhooks_initialized")
    except Exception as e:
        logger.warning("outbound_webhooks_init_failed", error=str(e))

    # ── Phase 12: Agent Calibration ───────────────────────────
    try:
        from shieldops.agents.calibration.calibrator import ConfidenceCalibrator
        from shieldops.agents.calibration.tracker import AccuracyTracker
        from shieldops.api.routes import calibration as calibration_routes

        accuracy_tracker = AccuracyTracker()
        confidence_calibrator = ConfidenceCalibrator(tracker=accuracy_tracker)
        calibration_routes.set_calibration(accuracy_tracker, confidence_calibrator)
        app.include_router(
            calibration_routes.router,
            prefix=settings.api_prefix,
            tags=["Calibration"],
        )
        logger.info("agent_calibration_initialized")
    except Exception as e:
        logger.warning("agent_calibration_init_failed", error=str(e))

    # ── Phase 12: Plugin System ───────────────────────────────
    plugin_registry = None
    try:
        from shieldops.api.routes import plugins as plugin_routes
        from shieldops.plugins.loader import PluginLoader
        from shieldops.plugins.registry import PluginRegistry

        plugin_registry = PluginRegistry()
        plugin_loader = PluginLoader(registry=plugin_registry)
        plugin_routes.set_plugin_registry(plugin_registry, plugin_loader)
        app.include_router(
            plugin_routes.router,
            prefix=settings.api_prefix,
            tags=["Plugins"],
        )
        logger.info("plugin_system_initialized")
    except Exception as e:
        logger.warning("plugin_system_init_failed", error=str(e))

    # ── Phase 12: Terraform API ───────────────────────────────
    try:
        from shieldops.api.routes import terraform as terraform_routes
        from shieldops.api.routes import terraform_state as tf_state_routes

        app.include_router(
            terraform_routes.router,
            prefix=settings.api_prefix,
            tags=["Terraform"],
        )
        app.include_router(
            tf_state_routes.router,
            prefix=settings.api_prefix,
            tags=["Terraform State"],
        )
        logger.info("terraform_api_initialized")
    except Exception as e:
        logger.warning("terraform_api_init_failed", error=str(e))

    # ── Phase 13: Circuit Breaker Registry ──────────────────
    try:
        from shieldops.api.routes import circuit_breakers as cb_routes
        from shieldops.utils.circuit_breaker import CircuitBreakerRegistry

        cb_registry = CircuitBreakerRegistry()
        # Pre-register breakers for external dependencies
        cb_registry.register("opa", failure_threshold=5, reset_timeout=30.0)
        cb_registry.register("llm", failure_threshold=3, reset_timeout=60.0)
        cb_registry.register("observability", failure_threshold=5, reset_timeout=45.0)
        cb_routes.set_registry(cb_registry)
        app.include_router(
            cb_routes.router,
            prefix=settings.api_prefix,
            tags=["Circuit Breakers"],
        )
        app.state.circuit_breaker_registry = cb_registry
        logger.info("circuit_breaker_registry_initialized")
    except Exception as e:
        logger.warning("circuit_breaker_registry_init_failed", error=str(e))

    # ── Phase 13: Startup Secret Validator ───────────────────
    try:
        from shieldops.config.startup_validator import StartupValidator

        startup_validator = StartupValidator()
        validation_result = startup_validator.validate()
        if not validation_result.valid:
            for err in validation_result.errors:
                logger.error(
                    "startup_validation_error",
                    category=err.category,
                    key=err.key,
                    message=err.message,
                )
        for warn in validation_result.warnings:
            logger.warning(
                "startup_validation_warning",
                category=warn.category,
                key=warn.key,
                message=warn.message,
            )
        logger.info(
            "startup_validation_complete",
            valid=validation_result.valid,
            errors=len(validation_result.errors),
            warnings=len(validation_result.warnings),
        )
    except Exception as e:
        logger.warning("startup_validator_init_failed", error=str(e))

    # ── Phase 13: Exception Handlers ─────────────────────────
    try:
        from shieldops.api.exceptions import register_exception_handlers

        register_exception_handlers(app)
        logger.info("exception_handlers_registered")
    except Exception as e:
        logger.warning("exception_handlers_init_failed", error=str(e))

    # ── Phase 13: SLO Monitor ────────────────────────────────
    try:
        from shieldops.api.routes import slo as slo_routes
        from shieldops.observability.slo_monitor import SLOMonitor

        slo_monitor = SLOMonitor(
            burn_rate_threshold=settings.slo_burn_rate_threshold,
        )
        slo_routes.set_monitor(slo_monitor)
        app.include_router(
            slo_routes.router,
            prefix=settings.api_prefix,
            tags=["SLO"],
        )
        app.state.slo_monitor = slo_monitor
        logger.info("slo_monitor_initialized")
    except Exception as e:
        logger.warning("slo_monitor_init_failed", error=str(e))

    # ── Phase 13: Audit Event Bus ────────────────────────────
    try:
        from shieldops.api.routes import audit_events as audit_event_routes
        from shieldops.audit.event_bus import AuditEventBus

        audit_event_bus = AuditEventBus()
        audit_event_routes.set_bus(audit_event_bus)
        app.include_router(
            audit_event_routes.router,
            prefix=settings.api_prefix,
            tags=["Audit Events"],
        )
        app.state.audit_event_bus = audit_event_bus
        logger.info("audit_event_bus_initialized")
    except Exception as e:
        logger.warning("audit_event_bus_init_failed", error=str(e))

    # ── Phase 13: Token Manager ──────────────────────────────
    try:
        from shieldops.api.auth.token_manager import TokenManager
        from shieldops.api.routes import token as token_routes

        token_manager = TokenManager(access_ttl=settings.jwt_expire_minutes * 60)
        token_routes.set_manager(token_manager)
        app.include_router(
            token_routes.router,
            prefix=settings.api_prefix,
            tags=["Token Management"],
        )
        app.state.token_manager = token_manager
        logger.info("token_manager_initialized")
    except Exception as e:
        logger.warning("token_manager_init_failed", error=str(e))

    # ── Phase 13: GDPR Processor ─────────────────────────────
    try:
        from shieldops.api.routes import gdpr as gdpr_routes
        from shieldops.compliance.gdpr import GDPRProcessor

        gdpr_processor = GDPRProcessor()
        gdpr_routes.set_processor(gdpr_processor)
        app.include_router(
            gdpr_routes.router,
            prefix=settings.api_prefix,
            tags=["GDPR"],
        )
        logger.info("gdpr_processor_initialized")
    except Exception as e:
        logger.warning("gdpr_processor_init_failed", error=str(e))

    # ── Phase 13: Hot Reload Manager ─────────────────────────
    try:
        from shieldops.api.routes import config as config_routes
        from shieldops.config.hot_reload import HotReloadManager

        hot_reload_manager = HotReloadManager(
            initial_config={
                "environment": settings.environment,
                "debug": settings.debug,
                "rate_limit_default": settings.rate_limit_default,
                "agent_confidence_threshold_auto": settings.agent_confidence_threshold_auto,
            }
        )
        config_routes.set_manager(hot_reload_manager)
        app.include_router(
            config_routes.router,
            prefix=settings.api_prefix,
            tags=["Configuration"],
        )
        app.state.hot_reload_manager = hot_reload_manager
        logger.info("hot_reload_manager_initialized")
    except Exception as e:
        logger.warning("hot_reload_manager_init_failed", error=str(e))

    # ── Phase 14: Multi-Level Cache ─────────────────────────────
    multilevel_cache = None
    try:
        from shieldops.api.routes.cache import set_multilevel_cache
        from shieldops.cache.multilevel_cache import MultiLevelCache

        if redis_cache is not None:
            multilevel_cache = MultiLevelCache(
                l2_cache=redis_cache,
                l1_max_size=settings.cache_l1_max_size,
                l1_ttl_seconds=settings.cache_l1_ttl_seconds,
                l1_enabled=settings.cache_l1_enabled,
            )
            set_multilevel_cache(multilevel_cache)
            logger.info("multilevel_cache_initialized")
    except Exception as e:
        logger.warning("multilevel_cache_init_failed", error=str(e))

    # ── Phase 14: Feature Flag Manager ───────────────────────────
    try:
        from shieldops.api.routes import feature_flags as ff_routes
        from shieldops.config.feature_flags import FeatureFlagManager

        ff_manager = FeatureFlagManager(
            redis_cache=redis_cache,
            sync_interval_seconds=settings.feature_flags_sync_interval_seconds,
        )
        ff_routes.set_manager(ff_manager)
        app.include_router(
            ff_routes.router,
            prefix=settings.api_prefix,
            tags=["Feature Flags"],
        )
        logger.info("feature_flag_manager_initialized")
    except Exception as e:
        logger.warning("feature_flag_manager_init_failed", error=str(e))

    # ── Phase 14: Health Aggregator ──────────────────────────────
    try:
        from shieldops.api.routes import health_aggregate as ha_routes
        from shieldops.observability.health_aggregator import HealthAggregator

        health_aggregator = HealthAggregator(
            history_size=settings.health_history_size,
            degraded_threshold=settings.health_degraded_threshold,
            unhealthy_threshold=settings.health_unhealthy_threshold,
        )
        # Register known components
        health_aggregator.register("database", weight=2.0, is_critical=True)
        health_aggregator.register("redis", weight=1.5, is_critical=True)
        health_aggregator.register("kafka", weight=1.0)
        health_aggregator.register("opa", weight=1.0)
        ha_routes.set_aggregator(health_aggregator)
        app.include_router(
            ha_routes.router,
            prefix=settings.api_prefix,
            tags=["Health Aggregate"],
        )
        logger.info("health_aggregator_initialized")
    except Exception as e:
        logger.warning("health_aggregator_init_failed", error=str(e))

    # ── Phase 14: Request Correlator ─────────────────────────────
    request_correlator = None
    try:
        from shieldops.api.routes import correlation as corr_routes
        from shieldops.observability.request_correlation import RequestCorrelator

        request_correlator = RequestCorrelator(
            max_traces=settings.correlation_max_traces,
            trace_ttl_minutes=settings.correlation_trace_ttl_minutes,
        )
        corr_routes.set_correlator(request_correlator)
        app.include_router(
            corr_routes.router,
            prefix=settings.api_prefix,
            tags=["Correlation"],
        )
        logger.info("request_correlator_initialized")
    except Exception as e:
        logger.warning("request_correlator_init_failed", error=str(e))

    # ── Phase 14: Escalation Engine ──────────────────────────────
    try:
        from shieldops.api.routes import escalation_policies as esc_routes
        from shieldops.integrations.notifications.escalation import EscalationEngine

        escalation_engine = EscalationEngine(
            dispatcher=notification_dispatcher,
            default_timeout=settings.escalation_default_timeout_seconds,
            max_retries=settings.escalation_max_retries,
        )
        esc_routes.set_engine(escalation_engine)
        app.include_router(
            esc_routes.router,
            prefix=settings.api_prefix,
            tags=["Escalation Policies"],
        )
        logger.info("escalation_engine_initialized")
    except Exception as e:
        logger.warning("escalation_engine_init_failed", error=str(e))

    # ── Phase 14: Agent Resource Quotas ──────────────────────────
    try:
        from shieldops.agents.resource_quotas import ResourceQuotaManager
        from shieldops.api.routes import agent_quotas as aq_routes

        quota_manager = ResourceQuotaManager(
            global_max_concurrent=settings.agent_global_max_concurrent,
            enabled=settings.agent_quota_enabled,
        )
        aq_routes.set_manager(quota_manager)
        app.include_router(
            aq_routes.router,
            prefix=settings.api_prefix,
            tags=["Agent Quotas"],
        )
        logger.info("agent_quota_manager_initialized")
    except Exception as e:
        logger.warning("agent_quota_manager_init_failed", error=str(e))

    # ── Phase 14: Batch Engine ───────────────────────────────────
    try:
        from shieldops.api.batch_engine import BatchEngine
        from shieldops.api.routes import batch_operations as bo_routes

        batch_engine = BatchEngine(
            max_batch_size=settings.batch_max_size,
            max_parallel=settings.batch_max_parallel,
            job_ttl_hours=settings.batch_job_ttl_hours,
        )
        bo_routes.set_engine(batch_engine)
        app.include_router(
            bo_routes.router,
            prefix=settings.api_prefix,
            tags=["Batch Operations"],
        )
        logger.info("batch_engine_initialized")
    except Exception as e:
        logger.warning("batch_engine_init_failed", error=str(e))

    # ── Phase 14: Incident Timeline ──────────────────────────────
    try:
        from shieldops.agents.investigation.timeline import TimelineBuilder
        from shieldops.api.routes import timeline as tl_routes

        timeline_builder = TimelineBuilder(
            max_events_per_incident=settings.timeline_max_events_per_incident,
            retention_days=settings.timeline_retention_days,
        )
        tl_routes.set_builder(timeline_builder)
        app.include_router(
            tl_routes.router,
            prefix=settings.api_prefix,
            tags=["Incident Timeline"],
        )
        logger.info("timeline_builder_initialized")
    except Exception as e:
        logger.warning("timeline_builder_init_failed", error=str(e))

    # ── Phase 14: Export Engine ──────────────────────────────────
    try:
        from shieldops.api.routes import export_engine as exp_routes
        from shieldops.utils.export_engine import ExportEngine

        export_engine = ExportEngine(
            max_rows=settings.export_max_rows,
            pdf_enabled=settings.export_pdf_enabled,
            xlsx_enabled=settings.export_xlsx_enabled,
        )
        exp_routes.set_engine(export_engine)
        app.include_router(
            exp_routes.router,
            prefix=settings.api_prefix,
            tags=["Exports"],
        )
        logger.info("export_engine_initialized")
    except Exception as e:
        logger.warning("export_engine_init_failed", error=str(e))

    # ── Phase 14: Environment Promotion ──────────────────────────
    try:
        from shieldops.api.routes import environment_promotion as ep_routes
        from shieldops.config.environment_promotion import PromotionManager

        promotion_manager = PromotionManager(
            require_approval_for_prod=settings.promotion_require_approval_for_prod,
            allowed_source_envs=settings.promotion_allowed_source_envs,
        )
        ep_routes.set_manager(promotion_manager)
        app.include_router(
            ep_routes.router,
            prefix=settings.api_prefix,
            tags=["Environment Promotion"],
        )
        logger.info("promotion_manager_initialized")
    except Exception as e:
        logger.warning("promotion_manager_init_failed", error=str(e))

    # ── Phase 14: API Lifecycle Manager ──────────────────────────
    try:
        from shieldops.api.routes import api_lifecycle as al_routes
        from shieldops.api.versioning.lifecycle import APILifecycleManager

        api_lifecycle = APILifecycleManager(
            deprecation_header_enabled=settings.api_deprecation_header_enabled,
            sunset_warning_days=settings.api_sunset_warning_days,
        )
        api_lifecycle.scan_routes(app)
        al_routes.set_manager(api_lifecycle)
        app.include_router(
            al_routes.router,
            prefix=settings.api_prefix,
            tags=["API Lifecycle"],
        )
        logger.info("api_lifecycle_manager_initialized")
    except Exception as e:
        logger.warning("api_lifecycle_manager_init_failed", error=str(e))

    # ── Phase 14: Agent Collaboration Protocol ───────────────────
    try:
        from shieldops.agents.collaboration import AgentCollaborationProtocol
        from shieldops.api.routes import agent_collaboration as ac_routes

        collaboration_protocol = AgentCollaborationProtocol(
            max_messages=settings.agent_collaboration_max_messages,
            session_timeout_minutes=settings.agent_collaboration_session_timeout_minutes,
        )
        ac_routes.set_protocol(collaboration_protocol)
        app.include_router(
            ac_routes.router,
            prefix=settings.api_prefix,
            tags=["Agent Collaboration"],
        )
        logger.info("agent_collaboration_initialized")
    except Exception as e:
        logger.warning("agent_collaboration_init_failed", error=str(e))

    # ── Phase 15: Post-Mortem Generator ────────────────────────────
    try:
        from shieldops.agents.investigation.postmortem import PostMortemGenerator
        from shieldops.api.routes import postmortem as postmortem_routes

        postmortem_gen = PostMortemGenerator(
            max_reports=settings.postmortem_max_reports,
        )
        postmortem_routes.set_generator(postmortem_gen)
        app.include_router(
            postmortem_routes.router,
            prefix=settings.api_prefix,
            tags=["Post-Mortems"],
        )
        logger.info("postmortem_generator_initialized")
    except Exception as e:
        logger.warning("postmortem_generator_init_failed", error=str(e))

    # ── Phase 15: DORA Metrics Engine ────────────────────────────────
    try:
        from shieldops.analytics.dora_metrics import DORAMetricsEngine
        from shieldops.api.routes import dora_metrics as dora_routes

        dora_engine = DORAMetricsEngine(
            default_period_days=settings.dora_default_period_days,
            max_records=settings.dora_max_records,
        )
        dora_routes.set_engine(dora_engine)
        app.include_router(
            dora_routes.router,
            prefix=settings.api_prefix,
            tags=["DORA Metrics"],
        )
        logger.info("dora_metrics_engine_initialized")
    except Exception as e:
        logger.warning("dora_metrics_init_failed", error=str(e))

    # ── Phase 15: Alert Suppression Engine ───────────────────────────
    try:
        from shieldops.api.routes import alert_suppression as suppression_routes
        from shieldops.observability.alert_suppression import AlertSuppressionEngine

        suppression_engine = AlertSuppressionEngine(
            max_rules=settings.alert_suppression_max_rules,
            max_window_duration_hours=settings.maintenance_window_max_duration_hours,
        )
        suppression_routes.set_engine(suppression_engine)
        app.include_router(
            suppression_routes.router,
            prefix=settings.api_prefix,
            tags=["Alert Suppression"],
        )
        logger.info("alert_suppression_initialized")
    except Exception as e:
        logger.warning("alert_suppression_init_failed", error=str(e))

    # ── Phase 15: On-Call Schedule Manager ───────────────────────────
    try:
        from shieldops.api.routes import oncall as oncall_routes
        from shieldops.integrations.oncall.schedule import OnCallScheduleManager

        oncall_manager = OnCallScheduleManager(
            default_rotation=settings.oncall_default_rotation,
            max_schedules=settings.oncall_max_schedules,
        )
        oncall_routes.set_manager(oncall_manager)
        app.include_router(
            oncall_routes.router,
            prefix=settings.api_prefix,
            tags=["On-Call"],
        )
        logger.info("oncall_schedule_manager_initialized")
    except Exception as e:
        logger.warning("oncall_schedule_init_failed", error=str(e))

    # ── Phase 15: Service Ownership Registry ─────────────────────────
    try:
        from shieldops.api.routes import service_ownership as ownership_routes
        from shieldops.topology.ownership import ServiceOwnershipRegistry

        ownership_registry = ServiceOwnershipRegistry(
            max_entries=settings.service_ownership_max_entries,
        )
        ownership_routes.set_registry(ownership_registry)
        app.include_router(
            ownership_routes.router,
            prefix=settings.api_prefix,
            tags=["Service Ownership"],
        )
        logger.info("service_ownership_registry_initialized")
    except Exception as e:
        logger.warning("service_ownership_init_failed", error=str(e))

    # ── Phase 15: Runbook Execution Tracker ──────────────────────────
    try:
        from shieldops.api.routes import runbook_executions as runbook_exec_routes
        from shieldops.playbooks.execution_tracker import RunbookExecutionTracker

        runbook_tracker = RunbookExecutionTracker(
            max_executions=settings.runbook_max_executions,
            execution_ttl_days=settings.runbook_execution_ttl_days,
        )
        runbook_exec_routes.set_tracker(runbook_tracker)
        app.include_router(
            runbook_exec_routes.router,
            prefix=settings.api_prefix,
            tags=["Runbook Executions"],
        )
        logger.info("runbook_execution_tracker_initialized")
    except Exception as e:
        logger.warning("runbook_execution_tracker_init_failed", error=str(e))

    # ── Phase 15: Incident Impact Scorer ─────────────────────────────
    try:
        from shieldops.agents.investigation.impact_scorer import IncidentImpactScorer
        from shieldops.api.routes import incident_impact as impact_routes

        impact_scorer = IncidentImpactScorer(
            max_records=settings.impact_max_records,
        )
        impact_routes.set_scorer(impact_scorer)
        app.include_router(
            impact_routes.router,
            prefix=settings.api_prefix,
            tags=["Incident Impact"],
        )
        logger.info("incident_impact_scorer_initialized")
    except Exception as e:
        logger.warning("incident_impact_scorer_init_failed", error=str(e))

    # ── Phase 15: Configuration Drift Detector ───────────────────────
    try:
        from shieldops.api.routes import drift_detection as drift_det_routes
        from shieldops.observability.drift_detector import ConfigDriftDetector

        config_drift_detector = ConfigDriftDetector(
            max_snapshots_per_env=settings.drift_max_snapshots_per_env,
            retention_days=settings.drift_retention_days,
        )
        drift_det_routes.set_detector(config_drift_detector)
        app.include_router(
            drift_det_routes.router,
            prefix=settings.api_prefix,
            tags=["Config Drift Detection"],
        )
        logger.info("config_drift_detector_initialized")
    except Exception as e:
        logger.warning("config_drift_detector_init_failed", error=str(e))

    # ── Phase 15: Cost Anomaly Detector ──────────────────────────────
    try:
        from shieldops.analytics.cost_anomaly import CostAnomalyDetector
        from shieldops.api.routes import cost_anomaly as cost_anomaly_routes

        cost_anomaly_detector = CostAnomalyDetector(
            z_threshold=settings.cost_anomaly_z_threshold,
            lookback_days=settings.cost_anomaly_lookback_days,
        )
        cost_anomaly_routes.set_detector(cost_anomaly_detector)
        app.include_router(
            cost_anomaly_routes.router,
            prefix=settings.api_prefix,
            tags=["Cost Anomaly"],
        )
        logger.info("cost_anomaly_detector_initialized")
    except Exception as e:
        logger.warning("cost_anomaly_detector_init_failed", error=str(e))

    # ── Phase 15: Compliance Report Generator ────────────────────────
    try:
        from shieldops.api.routes import compliance_report_gen as comp_gen_routes
        from shieldops.compliance.report_generator import ComplianceReportGenerator

        compliance_gen = ComplianceReportGenerator(
            max_reports=settings.compliance_max_reports,
        )
        comp_gen_routes.set_generator(compliance_gen)
        app.include_router(
            comp_gen_routes.router,
            prefix=settings.api_prefix,
            tags=["Compliance Report Generator"],
        )
        logger.info("compliance_report_generator_initialized")
    except Exception as e:
        logger.warning("compliance_report_generator_init_failed", error=str(e))

    # ── Phase 15: Agent Performance Benchmarker ──────────────────────
    try:
        from shieldops.agents.benchmarker import AgentPerformanceBenchmarker
        from shieldops.api.routes import agent_benchmarks as bench_routes

        agent_benchmarker = AgentPerformanceBenchmarker(
            baseline_days=settings.agent_benchmark_baseline_days,
            regression_threshold=settings.agent_benchmark_regression_threshold,
        )
        bench_routes.set_benchmarker(agent_benchmarker)
        app.include_router(
            bench_routes.router,
            prefix=settings.api_prefix,
            tags=["Agent Benchmarks"],
        )
        logger.info("agent_benchmarker_initialized")
    except Exception as e:
        logger.warning("agent_benchmarker_init_failed", error=str(e))

    # ── Phase 15: Webhook Replay Engine ──────────────────────────────
    try:
        from shieldops.api.routes import webhook_replay as replay_routes
        from shieldops.integrations.outbound.replay_engine import WebhookReplayEngine

        webhook_replay = WebhookReplayEngine(
            max_retries=settings.webhook_replay_max_retries,
            max_deliveries=settings.webhook_replay_max_deliveries,
        )
        replay_routes.set_engine(webhook_replay)
        app.include_router(
            replay_routes.router,
            prefix=settings.api_prefix,
            tags=["Webhook Replay"],
        )
        logger.info("webhook_replay_engine_initialized")
    except Exception as e:
        logger.warning("webhook_replay_engine_init_failed", error=str(e))

    # ── Phase 16: Dependency Health Tracker ────────────────────────
    try:
        from shieldops.api.routes import dependency_health as dep_health_routes
        from shieldops.observability.dependency_health import DependencyHealthTracker

        dep_health_tracker = DependencyHealthTracker(
            max_checks=settings.dependency_health_max_checks,
            cascade_threshold=settings.dependency_cascade_threshold,
        )
        dep_health_routes.set_tracker(dep_health_tracker)
        app.include_router(
            dep_health_routes.router,
            prefix=settings.api_prefix,
            tags=["Dependency Health"],
        )
        logger.info("dependency_health_tracker_initialized")
    except Exception as e:
        logger.warning("dependency_health_tracker_init_failed", error=str(e))

    # ── Phase 16: Deployment Freeze Manager ────────────────────────
    try:
        from shieldops.api.routes import deployment_freeze as freeze_routes
        from shieldops.config.deployment_freeze import DeploymentFreezeManager

        deployment_freeze_mgr = DeploymentFreezeManager(
            max_windows=settings.deployment_freeze_max_windows,
            max_duration_days=settings.deployment_freeze_max_duration_days,
        )
        freeze_routes.set_manager(deployment_freeze_mgr)
        app.include_router(
            freeze_routes.router,
            prefix=settings.api_prefix,
            tags=["Deployment Freezes"],
        )
        logger.info("deployment_freeze_manager_initialized")
    except Exception as e:
        logger.warning("deployment_freeze_manager_init_failed", error=str(e))

    # ── Phase 16: Error Budget Tracker ─────────────────────────────
    try:
        from shieldops.api.routes import error_budget as budget_routes
        from shieldops.sla.error_budget import ErrorBudgetTracker

        error_budget_tracker = ErrorBudgetTracker(
            warning_threshold=settings.error_budget_warning_threshold,
            critical_threshold=settings.error_budget_critical_threshold,
        )
        budget_routes.set_tracker(error_budget_tracker)
        app.include_router(
            budget_routes.router,
            prefix=settings.api_prefix,
            tags=["Error Budgets"],
        )
        logger.info("error_budget_tracker_initialized")
    except Exception as e:
        logger.warning("error_budget_tracker_init_failed", error=str(e))

    # ── Phase 16: Alert Grouping Engine ────────────────────────────
    try:
        from shieldops.api.routes import alert_grouping as grouping_routes
        from shieldops.observability.alert_grouping import AlertGroupingEngine

        alert_grouping_engine = AlertGroupingEngine(
            window_seconds=settings.alert_grouping_window_seconds,
            max_groups=settings.alert_grouping_max_groups,
        )
        grouping_routes.set_engine(alert_grouping_engine)
        app.include_router(
            grouping_routes.router,
            prefix=settings.api_prefix,
            tags=["Alert Grouping"],
        )
        logger.info("alert_grouping_engine_initialized")
    except Exception as e:
        logger.warning("alert_grouping_engine_init_failed", error=str(e))

    # ── Phase 16: Status Page Manager ──────────────────────────────
    try:
        from shieldops.api.routes import status_page as status_routes
        from shieldops.observability.status_page import StatusPageManager

        status_page_mgr = StatusPageManager(
            max_components=settings.status_page_max_components,
            max_incidents=settings.status_page_max_incidents,
        )
        status_routes.set_manager(status_page_mgr)
        app.include_router(
            status_routes.router,
            prefix=settings.api_prefix,
            tags=["Status Page"],
        )
        logger.info("status_page_manager_initialized")
    except Exception as e:
        logger.warning("status_page_manager_init_failed", error=str(e))

    # ── Phase 16: Rollback Registry ────────────────────────────────
    try:
        from shieldops.api.routes import rollback_registry as rollback_routes
        from shieldops.policy.rollback.registry import RollbackRegistry

        rollback_registry = RollbackRegistry(
            max_events=settings.rollback_registry_max_events,
            pattern_lookback_days=settings.rollback_pattern_lookback_days,
        )
        rollback_routes.set_registry(rollback_registry)
        app.include_router(
            rollback_routes.router,
            prefix=settings.api_prefix,
            tags=["Rollback Registry"],
        )
        logger.info("rollback_registry_initialized")
    except Exception as e:
        logger.warning("rollback_registry_init_failed", error=str(e))

    # ── Phase 16: Capacity Reservation System ──────────────────────
    try:
        from shieldops.analytics.capacity_reservation import CapacityReservationManager
        from shieldops.api.routes import capacity_reservation as cap_routes

        capacity_reservation_mgr = CapacityReservationManager(
            max_active=settings.capacity_reservation_max_active,
            max_duration_days=settings.capacity_reservation_max_duration_days,
        )
        cap_routes.set_manager(capacity_reservation_mgr)
        app.include_router(
            cap_routes.router,
            prefix=settings.api_prefix,
            tags=["Capacity Reservations"],
        )
        logger.info("capacity_reservation_manager_initialized")
    except Exception as e:
        logger.warning("capacity_reservation_manager_init_failed", error=str(e))

    # ── Phase 16: Dependency Vulnerability Mapper ──────────────────
    try:
        from shieldops.api.routes import dependency_vuln_map as vuln_map_routes
        from shieldops.vulnerability.dependency_mapper import DependencyVulnerabilityMapper

        dep_vuln_mapper = DependencyVulnerabilityMapper(
            max_services=settings.dep_vuln_max_services,
            max_depth=settings.dep_vuln_max_depth,
        )
        vuln_map_routes.set_mapper(dep_vuln_mapper)
        app.include_router(
            vuln_map_routes.router,
            prefix=settings.api_prefix,
            tags=["Dependency Vulnerability Map"],
        )
        logger.info("dependency_vuln_mapper_initialized")
    except Exception as e:
        logger.warning("dependency_vuln_mapper_init_failed", error=str(e))

    # ── Phase 16: Operational Readiness Reviewer ───────────────────
    try:
        from shieldops.agents.investigation.readiness_review import (
            OperationalReadinessReviewer,
        )
        from shieldops.api.routes import readiness_review as readiness_routes

        readiness_reviewer = OperationalReadinessReviewer(
            max_checklists=settings.readiness_review_max_checklists,
            passing_threshold=settings.readiness_review_passing_threshold,
        )
        readiness_routes.set_reviewer(readiness_reviewer)
        app.include_router(
            readiness_routes.router,
            prefix=settings.api_prefix,
            tags=["Readiness Reviews"],
        )
        logger.info("readiness_reviewer_initialized")
    except Exception as e:
        logger.warning("readiness_reviewer_init_failed", error=str(e))

    # ── Phase 16: Rate Limit Analytics Engine ──────────────────────
    try:
        from shieldops.analytics.rate_limit_analytics import RateLimitAnalyticsEngine
        from shieldops.api.routes import rate_limit_analytics as rl_routes

        rate_limit_analytics = RateLimitAnalyticsEngine(
            max_events=settings.rate_limit_analytics_max_events,
            retention_hours=settings.rate_limit_analytics_retention_hours,
        )
        rl_routes.set_engine(rate_limit_analytics)
        app.include_router(
            rl_routes.router,
            prefix=settings.api_prefix,
            tags=["Rate Limit Analytics"],
        )
        logger.info("rate_limit_analytics_initialized")
    except Exception as e:
        logger.warning("rate_limit_analytics_init_failed", error=str(e))

    # ── Phase 16: Agent Decision Explainer ─────────────────────────
    try:
        from shieldops.agents.decision_explainer import AgentDecisionExplainer
        from shieldops.api.routes import agent_decisions as decision_routes

        agent_decision_explainer = AgentDecisionExplainer(
            max_records=settings.agent_decision_max_records,
            retention_days=settings.agent_decision_retention_days,
        )
        decision_routes.set_explainer(agent_decision_explainer)
        app.include_router(
            decision_routes.router,
            prefix=settings.api_prefix,
            tags=["Agent Decisions"],
        )
        logger.info("agent_decision_explainer_initialized")
    except Exception as e:
        logger.warning("agent_decision_explainer_init_failed", error=str(e))

    # ── Phase 16: Runbook Scheduler ────────────────────────────────
    try:
        from shieldops.api.routes import runbook_scheduler as rb_sched_routes
        from shieldops.playbooks.runbook_scheduler import RunbookScheduler

        runbook_scheduler = RunbookScheduler(
            max_schedules=settings.runbook_scheduler_max_schedules,
            lookahead_minutes=settings.runbook_scheduler_lookahead_minutes,
        )
        rb_sched_routes.set_scheduler(runbook_scheduler)
        app.include_router(
            rb_sched_routes.router,
            prefix=settings.api_prefix,
            tags=["Runbook Scheduler"],
        )
        logger.info("runbook_scheduler_initialized")
    except Exception as e:
        logger.warning("runbook_scheduler_init_failed", error=str(e))

    # ── Phase 17: War Room ──────────────────────────────────
    try:
        from shieldops.api.routes import war_room as war_room_route
        from shieldops.incidents.war_room import WarRoomManager

        war_room_mgr = WarRoomManager(
            max_rooms=settings.war_room_max_rooms,
            auto_escalate_minutes=settings.war_room_auto_escalate_minutes,
        )
        war_room_route.set_manager(war_room_mgr)
        app.include_router(
            war_room_route.router,
            prefix=settings.api_prefix,
            tags=["War Rooms"],
        )
        logger.info("war_room_initialized")
    except Exception as e:
        logger.warning("war_room_init_failed", error=str(e))

    # ── Phase 17: Retrospective ─────────────────────────────
    try:
        from shieldops.api.routes import retrospective as retro_route
        from shieldops.incidents.retrospective import RetrospectiveManager

        retro_mgr = RetrospectiveManager(
            max_retros=settings.retrospective_max_retros,
        )
        retro_route.set_manager(retro_mgr)
        app.include_router(
            retro_route.router,
            prefix=settings.api_prefix,
            tags=["Retrospectives"],
        )
        logger.info("retrospective_initialized")
    except Exception as e:
        logger.warning("retrospective_init_failed", error=str(e))

    # ── Phase 17: Change Risk Scorer ────────────────────────
    try:
        from shieldops.analytics.change_risk_scorer import ChangeRiskScorer
        from shieldops.api.routes import change_risk as change_risk_route

        change_risk_scorer = ChangeRiskScorer(
            max_records=settings.change_risk_max_records,
            high_risk_threshold=settings.change_risk_high_threshold,
            critical_risk_threshold=settings.change_risk_critical_threshold,
        )
        change_risk_route.set_scorer(change_risk_scorer)
        app.include_router(
            change_risk_route.router,
            prefix=settings.api_prefix,
            tags=["Change Risk"],
        )
        logger.info("change_risk_scorer_initialized")
    except Exception as e:
        logger.warning("change_risk_scorer_init_failed", error=str(e))

    # ── Phase 17: SLA Violation Tracker ─────────────────────
    try:
        from shieldops.api.routes import sla_violations as sla_viol_route
        from shieldops.sla.violation_tracker import SLAViolationTracker

        sla_violation_tracker = SLAViolationTracker(
            max_targets=settings.sla_violation_max_targets,
            max_violations=settings.sla_violation_max_violations,
        )
        sla_viol_route.set_tracker(sla_violation_tracker)
        app.include_router(
            sla_viol_route.router,
            prefix=settings.api_prefix,
            tags=["SLA Violations"],
        )
        logger.info("sla_violation_tracker_initialized")
    except Exception as e:
        logger.warning("sla_violation_tracker_init_failed", error=str(e))

    # ── Phase 17: Tagging Compliance ────────────────────────
    try:
        from shieldops.analytics.tagging_compliance import TaggingComplianceEngine
        from shieldops.api.routes import tagging_compliance as tag_route

        tagging_engine = TaggingComplianceEngine(
            max_policies=settings.tagging_compliance_max_policies,
            max_records=settings.tagging_compliance_max_records,
        )
        tag_route.set_engine(tagging_engine)
        app.include_router(
            tag_route.router,
            prefix=settings.api_prefix,
            tags=["Tagging Compliance"],
        )
        logger.info("tagging_compliance_initialized")
    except Exception as e:
        logger.warning("tagging_compliance_init_failed", error=str(e))

    # ── Phase 17: Cost Attribution ──────────────────────────
    try:
        from shieldops.api.routes import cost_attribution as cost_attr_route
        from shieldops.billing.cost_attribution import CostAttributionEngine

        cost_attr_engine = CostAttributionEngine(
            max_rules=settings.cost_attribution_max_rules,
            max_entries=settings.cost_attribution_max_entries,
        )
        cost_attr_route.set_engine(cost_attr_engine)
        app.include_router(
            cost_attr_route.router,
            prefix=settings.api_prefix,
            tags=["Cost Attribution"],
        )
        logger.info("cost_attribution_initialized")
    except Exception as e:
        logger.warning("cost_attribution_init_failed", error=str(e))

    # ── Phase 17: Cost Normalizer ───────────────────────────
    try:
        from shieldops.analytics.cost_normalizer import CostNormalizer
        from shieldops.api.routes import cost_normalizer as cost_norm_route

        cost_norm = CostNormalizer(
            max_pricing_entries=settings.cost_normalizer_max_pricing,
        )
        cost_norm_route.set_normalizer(cost_norm)
        app.include_router(
            cost_norm_route.router,
            prefix=settings.api_prefix,
            tags=["Cost Normalizer"],
        )
        logger.info("cost_normalizer_initialized")
    except Exception as e:
        logger.warning("cost_normalizer_init_failed", error=str(e))

    # ── Phase 17: Temporal Patterns ─────────────────────────
    try:
        from shieldops.analytics.temporal_patterns import TemporalPatternEngine
        from shieldops.api.routes import temporal_patterns as temporal_route

        temporal_engine = TemporalPatternEngine(
            max_events=settings.temporal_patterns_max_events,
            min_occurrences=settings.temporal_patterns_min_occurrences,
        )
        temporal_route.set_engine(temporal_engine)
        app.include_router(
            temporal_route.router,
            prefix=settings.api_prefix,
            tags=["Temporal Patterns"],
        )
        logger.info("temporal_patterns_initialized")
    except Exception as e:
        logger.warning("temporal_patterns_init_failed", error=str(e))

    # ── Phase 17: Continuous Compliance ─────────────────────
    try:
        from shieldops.api.routes import continuous_compliance as cc_route
        from shieldops.compliance.continuous_validator import (
            ContinuousComplianceValidator,
        )

        cc_validator = ContinuousComplianceValidator(
            max_controls=settings.continuous_compliance_max_controls,
            max_records=settings.continuous_compliance_max_records,
        )
        cc_route.set_validator(cc_validator)
        app.include_router(
            cc_route.router,
            prefix=settings.api_prefix,
            tags=["Continuous Compliance"],
        )
        logger.info("continuous_compliance_initialized")
    except Exception as e:
        logger.warning("continuous_compliance_init_failed", error=str(e))

    # ── Phase 17: Third-Party Risk ──────────────────────────
    try:
        from shieldops.api.routes import third_party_risk as tpr_route
        from shieldops.vulnerability.third_party_risk import ThirdPartyRiskTracker

        tpr_tracker = ThirdPartyRiskTracker(
            max_vendors=settings.third_party_risk_max_vendors,
            assessment_interval_days=settings.third_party_risk_reassessment_days,
        )
        tpr_route.set_tracker(tpr_tracker)
        app.include_router(
            tpr_route.router,
            prefix=settings.api_prefix,
            tags=["Third Party Risk"],
        )
        logger.info("third_party_risk_initialized")
    except Exception as e:
        logger.warning("third_party_risk_init_failed", error=str(e))

    # ── Phase 17: ROI Tracker ───────────────────────────────
    try:
        from shieldops.agents.roi_tracker import AgentROITracker
        from shieldops.api.routes import roi_tracker as roi_route

        roi_tracker = AgentROITracker(
            max_entries=settings.roi_tracker_max_entries,
        )
        roi_route.set_tracker(roi_tracker)
        app.include_router(
            roi_route.router,
            prefix=settings.api_prefix,
            tags=["ROI Tracker"],
        )
        logger.info("roi_tracker_initialized")
    except Exception as e:
        logger.warning("roi_tracker_init_failed", error=str(e))

    # ── Phase 17: Infrastructure Map ────────────────────────
    try:
        from shieldops.api.routes import infrastructure_map as infra_route
        from shieldops.topology.infrastructure_map import (
            InfrastructureTopologyMapper,
        )

        infra_mapper = InfrastructureTopologyMapper(
            max_nodes=settings.infrastructure_map_max_nodes,
            max_relationships=settings.infrastructure_map_max_relationships,
        )
        infra_route.set_mapper(infra_mapper)
        app.include_router(
            infra_route.router,
            prefix=settings.api_prefix,
            tags=["Infrastructure Map"],
        )
        logger.info("infrastructure_map_initialized")
    except Exception as e:
        logger.warning("infrastructure_map_init_failed", error=str(e))

    # ── Phase 18: Secret Rotation ───────────────────────────
    try:
        from shieldops.api.routes import secret_rotation as secret_rot_route
        from shieldops.auth.secret_rotation import SecretRotationScheduler

        secret_scheduler = SecretRotationScheduler(
            max_secrets=settings.secret_rotation_max_secrets,
            default_rotation_days=settings.secret_rotation_default_days,
        )
        secret_rot_route.set_scheduler(secret_scheduler)
        app.include_router(
            secret_rot_route.router,
            prefix=settings.api_prefix,
            tags=["Secret Rotation"],
        )
        logger.info("secret_rotation_initialized")
    except Exception as e:
        logger.warning("secret_rotation_init_failed", error=str(e))

    # ── Phase 18: Anomaly Correlation ───────────────────────
    try:
        from shieldops.analytics.anomaly_correlation import (
            AnomalyCorrelationEngine,
        )
        from shieldops.api.routes import anomaly_correlation as anomaly_corr_route

        anomaly_engine = AnomalyCorrelationEngine(
            max_events=settings.anomaly_correlation_max_events,
            correlation_window_seconds=settings.anomaly_correlation_window_seconds,
        )
        anomaly_corr_route.set_engine(anomaly_engine)
        app.include_router(
            anomaly_corr_route.router,
            prefix=settings.api_prefix,
            tags=["Anomaly Correlation"],
        )
        logger.info("anomaly_correlation_initialized")
    except Exception as e:
        logger.warning("anomaly_correlation_init_failed", error=str(e))

    # ── Phase 18: Synthetic Monitor ─────────────────────────
    try:
        from shieldops.api.routes import synthetic_monitor as synth_route
        from shieldops.observability.synthetic_monitor import (
            SyntheticMonitorManager,
        )

        synth_mgr = SyntheticMonitorManager(
            max_monitors=settings.synthetic_monitor_max_monitors,
            max_results=settings.synthetic_monitor_max_results,
            failure_threshold=settings.synthetic_monitor_failure_threshold,
        )
        synth_route.set_manager(synth_mgr)
        app.include_router(
            synth_route.router,
            prefix=settings.api_prefix,
            tags=["Synthetic Monitors"],
        )
        logger.info("synthetic_monitor_initialized")
    except Exception as e:
        logger.warning("synthetic_monitor_init_failed", error=str(e))

    # ── Phase 18: Chaos Experiments ─────────────────────────
    try:
        from shieldops.api.routes import chaos_experiments as chaos_route
        from shieldops.observability.chaos_experiments import (
            ChaosExperimentTracker,
        )

        chaos_tracker = ChaosExperimentTracker(
            max_experiments=settings.chaos_experiments_max_experiments,
            max_results=settings.chaos_experiments_max_results,
        )
        chaos_route.set_tracker(chaos_tracker)
        app.include_router(
            chaos_route.router,
            prefix=settings.api_prefix,
            tags=["Chaos Experiments"],
        )
        logger.info("chaos_experiments_initialized")
    except Exception as e:
        logger.warning("chaos_experiments_init_failed", error=str(e))

    # ── Phase 18: Data Quality ──────────────────────────────
    try:
        from shieldops.api.routes import data_quality as dq_route
        from shieldops.compliance.data_quality import DataQualityMonitor

        dq_monitor = DataQualityMonitor(
            max_rules=settings.data_quality_max_rules,
            max_results=settings.data_quality_max_results,
            alert_cooldown_seconds=settings.data_quality_alert_cooldown,
        )
        dq_route.set_monitor(dq_monitor)
        app.include_router(
            dq_route.router,
            prefix=settings.api_prefix,
            tags=["Data Quality"],
        )
        logger.info("data_quality_initialized")
    except Exception as e:
        logger.warning("data_quality_init_failed", error=str(e))

    # ── Phase 18: Canary Tracker ────────────────────────────
    try:
        from shieldops.api.routes import canary_tracker as canary_route
        from shieldops.policy.rollback.canary_tracker import (
            CanaryDeploymentTracker,
        )

        canary_trk = CanaryDeploymentTracker(
            max_deployments=settings.canary_tracker_max_deployments,
            max_metrics=settings.canary_tracker_max_metrics,
        )
        canary_route.set_tracker(canary_trk)
        app.include_router(
            canary_route.router,
            prefix=settings.api_prefix,
            tags=["Canary Deployments"],
        )
        logger.info("canary_tracker_initialized")
    except Exception as e:
        logger.warning("canary_tracker_init_failed", error=str(e))

    # ── Phase 18: Incident Communications ───────────────────
    try:
        from shieldops.api.routes import incident_comms as comms_route
        from shieldops.incidents.incident_comms import (
            IncidentCommunicationManager,
        )

        comms_mgr = IncidentCommunicationManager(
            max_templates=settings.incident_comms_max_templates,
            max_messages=settings.incident_comms_max_messages,
        )
        comms_route.set_manager(comms_mgr)
        app.include_router(
            comms_route.router,
            prefix=settings.api_prefix,
            tags=["Incident Communications"],
        )
        logger.info("incident_comms_initialized")
    except Exception as e:
        logger.warning("incident_comms_init_failed", error=str(e))

    # ── Phase 18: Dependency SLA ────────────────────────────
    try:
        from shieldops.api.routes import dependency_sla as dep_sla_route
        from shieldops.sla.dependency_sla import DependencySLATracker

        dep_sla_trk = DependencySLATracker(
            max_slas=settings.dependency_sla_max_slas,
            max_evaluations=settings.dependency_sla_max_evaluations,
        )
        dep_sla_route.set_tracker(dep_sla_trk)
        app.include_router(
            dep_sla_route.router,
            prefix=settings.api_prefix,
            tags=["Dependency SLAs"],
        )
        logger.info("dependency_sla_initialized")
    except Exception as e:
        logger.warning("dependency_sla_init_failed", error=str(e))

    # ── Phase 18: Security Posture Scorer ───────────────────
    try:
        from shieldops.api.routes import posture_scorer as posture_route
        from shieldops.vulnerability.posture_scorer import (
            SecurityPostureScorer,
        )

        posture_scr = SecurityPostureScorer(
            max_checks=settings.posture_scorer_max_checks,
            max_scores=settings.posture_scorer_max_scores,
        )
        posture_route.set_scorer(posture_scr)
        app.include_router(
            posture_route.router,
            prefix=settings.api_prefix,
            tags=["Security Posture"],
        )
        logger.info("posture_scorer_initialized")
    except Exception as e:
        logger.warning("posture_scorer_init_failed", error=str(e))

    # ── Phase 18: Workload Fingerprint ──────────────────────
    try:
        from shieldops.analytics.workload_fingerprint import (
            WorkloadFingerprintEngine,
        )
        from shieldops.api.routes import workload_fingerprint as wf_route

        wf_engine = WorkloadFingerprintEngine(
            max_samples=settings.workload_fingerprint_max_samples,
            min_samples_for_stable=settings.workload_fingerprint_min_stable,
            drift_threshold_pct=settings.workload_fingerprint_drift_threshold,
        )
        wf_route.set_engine(wf_engine)
        app.include_router(
            wf_route.router,
            prefix=settings.api_prefix,
            tags=["Workload Fingerprints"],
        )
        logger.info("workload_fingerprint_initialized")
    except Exception as e:
        logger.warning("workload_fingerprint_init_failed", error=str(e))

    # ── Phase 18: Maintenance Window ────────────────────────
    try:
        from shieldops.api.routes import maintenance_window as mw_route
        from shieldops.scheduler.maintenance_window import (
            MaintenanceWindowManager,
        )

        mw_mgr = MaintenanceWindowManager(
            max_windows=settings.maintenance_window_max_windows,
            max_duration_hours=settings.maintenance_window_max_duration_hours,
        )
        mw_route.set_manager(mw_mgr)
        app.include_router(
            mw_route.router,
            prefix=settings.api_prefix,
            tags=["Maintenance Windows"],
        )
        logger.info("maintenance_window_initialized")
    except Exception as e:
        logger.warning("maintenance_window_init_failed", error=str(e))

    # ── Phase 18: Compliance Evidence ───────────────────────
    try:
        from shieldops.api.routes import evidence_collector as ev_route
        from shieldops.compliance.evidence_collector import (
            ComplianceEvidenceCollector,
        )

        ev_collector = ComplianceEvidenceCollector(
            max_evidence=settings.evidence_collector_max_evidence,
            max_packages=settings.evidence_collector_max_packages,
        )
        ev_route.set_collector(ev_collector)
        app.include_router(
            ev_route.router,
            prefix=settings.api_prefix,
            tags=["Compliance Evidence"],
        )
        logger.info("evidence_collector_initialized")
    except Exception as e:
        logger.warning("evidence_collector_init_failed", error=str(e))

    # ── Phase 19 ────────────────────────────────────────────

    try:
        from shieldops.api.routes import runbook_recommender as rb_rec_route
        from shieldops.playbooks.runbook_recommender import RunbookRecommender

        rb_rec = RunbookRecommender(
            max_profiles=settings.runbook_recommender_max_profiles,
            max_candidates=settings.runbook_recommender_max_candidates,
            min_score=settings.runbook_recommender_min_score,
        )
        rb_rec_route.set_recommender(rb_rec)
        app.include_router(
            rb_rec_route.router,
            prefix=settings.api_prefix,
            tags=["Runbook Recommender"],
        )
        logger.info("runbook_recommender_initialized")
    except Exception as e:
        logger.warning("runbook_recommender_init_failed", error=str(e))

    try:
        from shieldops.analytics.incident_clustering import (
            IncidentClusteringEngine,
        )
        from shieldops.api.routes import incident_clustering as ic_route

        ic_engine = IncidentClusteringEngine(
            max_incidents=settings.incident_clustering_max_incidents,
            max_clusters=settings.incident_clustering_max_clusters,
            similarity_threshold=settings.incident_clustering_similarity,
        )
        ic_route.set_engine(ic_engine)
        app.include_router(
            ic_route.router,
            prefix=settings.api_prefix,
            tags=["Incident Clustering"],
        )
        logger.info("incident_clustering_initialized")
    except Exception as e:
        logger.warning("incident_clustering_init_failed", error=str(e))

    try:
        from shieldops.api.routes import policy_generator as pg_route
        from shieldops.policy.policy_generator import PolicyCodeGenerator

        pg_engine = PolicyCodeGenerator(
            max_requirements=settings.policy_generator_max_requirements,
            max_policies=settings.policy_generator_max_policies,
        )
        pg_route.set_generator(pg_engine)
        app.include_router(
            pg_route.router,
            prefix=settings.api_prefix,
            tags=["Policy Generator"],
        )
        logger.info("policy_generator_initialized")
    except Exception as e:
        logger.warning("policy_generator_init_failed", error=str(e))

    try:
        from shieldops.api.routes import change_advisory as cab_route
        from shieldops.changes.change_advisory import ChangeAdvisoryBoard

        cab = ChangeAdvisoryBoard(
            max_requests=settings.change_advisory_max_requests,
            max_votes=settings.change_advisory_max_votes,
            auto_approve_threshold=settings.change_advisory_auto_approve,
        )
        cab_route.set_board(cab)
        app.include_router(
            cab_route.router,
            prefix=settings.api_prefix,
            tags=["Change Advisory"],
        )
        logger.info("change_advisory_initialized")
    except Exception as e:
        logger.warning("change_advisory_init_failed", error=str(e))

    try:
        from shieldops.analytics.sre_metrics import SREMetricsAggregator
        from shieldops.api.routes import sre_metrics as sre_route

        sre_agg = SREMetricsAggregator(
            max_datapoints=settings.sre_metrics_max_datapoints,
            max_scorecards=settings.sre_metrics_max_scorecards,
        )
        sre_route.set_aggregator(sre_agg)
        app.include_router(
            sre_route.router,
            prefix=settings.api_prefix,
            tags=["SRE Metrics"],
        )
        logger.info("sre_metrics_initialized")
    except Exception as e:
        logger.warning("sre_metrics_init_failed", error=str(e))

    try:
        from shieldops.api.routes import health_report as hr_route
        from shieldops.observability.health_report import (
            ServiceHealthReportGenerator,
        )

        hr_gen = ServiceHealthReportGenerator(
            max_reports=settings.health_report_max_reports,
        )
        hr_route.set_generator(hr_gen)
        app.include_router(
            hr_route.router,
            prefix=settings.api_prefix,
            tags=["Health Reports"],
        )
        logger.info("health_report_initialized")
    except Exception as e:
        logger.warning("health_report_init_failed", error=str(e))

    try:
        from shieldops.api.routes import approval_delegation as ad_route
        from shieldops.policy.approval.approval_delegation import (
            ApprovalDelegationEngine,
        )

        ad_engine = ApprovalDelegationEngine(
            max_rules=settings.approval_delegation_max_rules,
            max_audit=settings.approval_delegation_max_audit,
        )
        ad_route.set_engine(ad_engine)
        app.include_router(
            ad_route.router,
            prefix=settings.api_prefix,
            tags=["Approval Delegation"],
        )
        logger.info("approval_delegation_initialized")
    except Exception as e:
        logger.warning("approval_delegation_init_failed", error=str(e))

    try:
        from shieldops.api.routes import gap_analyzer as ga_route
        from shieldops.compliance.gap_analyzer import ComplianceGapAnalyzer

        ga = ComplianceGapAnalyzer(
            max_controls=settings.gap_analyzer_max_controls,
            max_gaps=settings.gap_analyzer_max_gaps,
        )
        ga_route.set_analyzer(ga)
        app.include_router(
            ga_route.router,
            prefix=settings.api_prefix,
            tags=["Compliance Gaps"],
        )
        logger.info("gap_analyzer_initialized")
    except Exception as e:
        logger.warning("gap_analyzer_init_failed", error=str(e))

    try:
        from shieldops.api.routes import cost_forecast as cf_route
        from shieldops.billing.cost_forecast import CostForecastEngine

        cf_engine = CostForecastEngine(
            max_datapoints=settings.cost_forecast_max_datapoints,
            max_forecasts=settings.cost_forecast_max_forecasts,
            budget_alert_threshold=settings.cost_forecast_alert_threshold,
        )
        cf_route.set_engine(cf_engine)
        app.include_router(
            cf_route.router,
            prefix=settings.api_prefix,
            tags=["Cost Forecast"],
        )
        logger.info("cost_forecast_initialized")
    except Exception as e:
        logger.warning("cost_forecast_init_failed", error=str(e))

    try:
        from shieldops.api.routes import deployment_risk as dr_route
        from shieldops.changes.deployment_risk import (
            DeploymentRiskPredictor,
        )

        dr_pred = DeploymentRiskPredictor(
            max_records=settings.deployment_risk_max_records,
            max_assessments=settings.deployment_risk_max_assessments,
        )
        dr_route.set_predictor(dr_pred)
        app.include_router(
            dr_route.router,
            prefix=settings.api_prefix,
            tags=["Deployment Risk"],
        )
        logger.info("deployment_risk_initialized")
    except Exception as e:
        logger.warning("deployment_risk_init_failed", error=str(e))

    try:
        from shieldops.analytics.capacity_trends import (
            CapacityTrendAnalyzer,
        )
        from shieldops.api.routes import capacity_trends as ct_route

        ct_analyzer = CapacityTrendAnalyzer(
            max_snapshots=settings.capacity_trends_max_snapshots,
            max_analyses=settings.capacity_trends_max_analyses,
            exhaustion_threshold=settings.capacity_trends_exhaustion_threshold,
        )
        ct_route.set_analyzer(ct_analyzer)
        app.include_router(
            ct_route.router,
            prefix=settings.api_prefix,
            tags=["Capacity Trends"],
        )
        logger.info("capacity_trends_initialized")
    except Exception as e:
        logger.warning("capacity_trends_init_failed", error=str(e))

    try:
        from shieldops.agents.incident_learning import (
            IncidentLearningTracker,
        )
        from shieldops.api.routes import incident_learning as il_route

        il_tracker = IncidentLearningTracker(
            max_lessons=settings.incident_learning_max_lessons,
            max_applications=settings.incident_learning_max_applications,
        )
        il_route.set_tracker(il_tracker)
        app.include_router(
            il_route.router,
            prefix=settings.api_prefix,
            tags=["Incident Learning"],
        )
        logger.info("incident_learning_initialized")
    except Exception as e:
        logger.warning("incident_learning_init_failed", error=str(e))

    # ── Phase 20: Tenant Resource Isolation ────────────────────
    if settings.tenant_isolation_enabled:
        try:
            from shieldops.api.routes import tenant_isolation as ti_route
            from shieldops.policy.tenant_isolation import (
                TenantResourceIsolationManager,
            )

            ti_mgr = TenantResourceIsolationManager(
                max_tenants=settings.tenant_isolation_max_tenants,
                max_violations=settings.tenant_isolation_max_violations,
            )
            ti_route.set_manager(ti_mgr)
            app.include_router(
                ti_route.router,
                prefix=settings.api_prefix,
                tags=["Tenant Isolation"],
            )
            logger.info("tenant_isolation_initialized")
        except Exception as e:
            logger.warning("tenant_isolation_init_failed", error=str(e))

    # ── Phase 20: Alert Noise Analyzer ─────────────────────────
    if settings.alert_noise_enabled:
        try:
            from shieldops.api.routes import alert_noise as an_route
            from shieldops.observability.alert_noise import (
                AlertNoiseAnalyzer,
            )

            an_analyzer = AlertNoiseAnalyzer(
                max_records=settings.alert_noise_max_records,
                noise_threshold=settings.alert_noise_threshold,
            )
            an_route.set_analyzer(an_analyzer)
            app.include_router(
                an_route.router,
                prefix=settings.api_prefix,
                tags=["Alert Noise"],
            )
            logger.info("alert_noise_initialized")
        except Exception as e:
            logger.warning("alert_noise_init_failed", error=str(e))

    # ── Phase 20: Automated Threshold Tuner ────────────────────
    if settings.threshold_tuner_enabled:
        try:
            from shieldops.api.routes import threshold_tuner as tt_route
            from shieldops.observability.threshold_tuner import (
                ThresholdTuningEngine,
            )

            tt_engine = ThresholdTuningEngine(
                max_thresholds=settings.threshold_tuner_max_thresholds,
                max_samples=settings.threshold_tuner_max_samples,
            )
            tt_route.set_engine(tt_engine)
            app.include_router(
                tt_route.router,
                prefix=settings.api_prefix,
                tags=["Threshold Tuner"],
            )
            logger.info("threshold_tuner_initialized")
        except Exception as e:
            logger.warning("threshold_tuner_init_failed", error=str(e))

    # ── Phase 20: Incident Severity Predictor ──────────────────
    if settings.severity_predictor_enabled:
        try:
            from shieldops.api.routes import severity_predictor as sp_route
            from shieldops.incidents.severity_predictor import (
                IncidentSeverityPredictor,
            )

            sp_predictor = IncidentSeverityPredictor(
                max_predictions=settings.severity_predictor_max_predictions,
                max_profiles=settings.severity_predictor_max_profiles,
            )
            sp_route.set_predictor(sp_predictor)
            app.include_router(
                sp_route.router,
                prefix=settings.api_prefix,
                tags=["Severity Predictor"],
            )
            logger.info("severity_predictor_initialized")
        except Exception as e:
            logger.warning("severity_predictor_init_failed", error=str(e))

    # ── Phase 20: Service Dependency Impact Analyzer ───────────
    if settings.impact_analyzer_enabled:
        try:
            from shieldops.api.routes import impact_analyzer as ia_route
            from shieldops.topology.impact_analyzer import (
                ServiceDependencyImpactAnalyzer,
            )

            ia_analyzer = ServiceDependencyImpactAnalyzer(
                max_dependencies=settings.impact_analyzer_max_dependencies,
                max_simulations=settings.impact_analyzer_max_simulations,
            )
            ia_route.set_analyzer(ia_analyzer)
            app.include_router(
                ia_route.router,
                prefix=settings.api_prefix,
                tags=["Impact Analyzer"],
            )
            logger.info("impact_analyzer_initialized")
        except Exception as e:
            logger.warning("impact_analyzer_init_failed", error=str(e))

    # ── Phase 20: Configuration Audit Trail ────────────────────
    if settings.config_audit_enabled:
        try:
            from shieldops.api.routes import config_audit as ca_route
            from shieldops.audit.config_audit import (
                ConfigurationAuditTrail,
            )

            ca_trail = ConfigurationAuditTrail(
                max_entries=settings.config_audit_max_entries,
                max_versions_per_key=settings.config_audit_max_versions_per_key,
            )
            ca_route.set_trail(ca_trail)
            app.include_router(
                ca_route.router,
                prefix=settings.api_prefix,
                tags=["Config Audit"],
            )
            logger.info("config_audit_initialized")
        except Exception as e:
            logger.warning("config_audit_init_failed", error=str(e))

    # ── Phase 20: Deployment Velocity Tracker ──────────────────
    if settings.deployment_velocity_enabled:
        try:
            from shieldops.analytics.deployment_velocity import (
                DeploymentVelocityTracker,
            )
            from shieldops.api.routes import deployment_velocity as dv_route

            dv_tracker = DeploymentVelocityTracker(
                max_events=settings.deployment_velocity_max_events,
                default_period_days=settings.deployment_velocity_default_period_days,
            )
            dv_route.set_tracker(dv_tracker)
            app.include_router(
                dv_route.router,
                prefix=settings.api_prefix,
                tags=["Deployment Velocity"],
            )
            logger.info("deployment_velocity_initialized")
        except Exception as e:
            logger.warning("deployment_velocity_init_failed", error=str(e))

    # ── Phase 20: Compliance Automation Rule Engine ─────────────
    if settings.compliance_automation_enabled:
        try:
            from shieldops.api.routes import compliance_automation as cam_route
            from shieldops.compliance.automation_rules import (
                ComplianceAutomationEngine,
            )

            cam_engine = ComplianceAutomationEngine(
                max_rules=settings.compliance_automation_max_rules,
                max_executions=settings.compliance_automation_max_executions,
            )
            cam_route.set_engine(cam_engine)
            app.include_router(
                cam_route.router,
                prefix=settings.api_prefix,
                tags=["Compliance Automation"],
            )
            logger.info("compliance_automation_initialized")
        except Exception as e:
            logger.warning("compliance_automation_init_failed", error=str(e))

    # ── Phase 20: Knowledge Base Article Manager ───────────────
    if settings.knowledge_base_enabled:
        try:
            from shieldops.api.routes import knowledge_articles as ka_route
            from shieldops.knowledge.article_manager import (
                KnowledgeBaseManager,
            )

            ka_mgr = KnowledgeBaseManager(
                max_articles=settings.knowledge_base_max_articles,
                max_votes=settings.knowledge_base_max_votes,
            )
            ka_route.set_manager(ka_mgr)
            app.include_router(
                ka_route.router,
                prefix=settings.api_prefix,
                tags=["Knowledge Articles"],
            )
            logger.info("knowledge_base_initialized")
        except Exception as e:
            logger.warning("knowledge_base_init_failed", error=str(e))

    # ── Phase 20: On-Call Fatigue Analyzer ─────────────────────
    if settings.oncall_fatigue_enabled:
        try:
            from shieldops.api.routes import oncall_fatigue as of_route
            from shieldops.incidents.oncall_fatigue import (
                OnCallFatigueAnalyzer,
            )

            of_analyzer = OnCallFatigueAnalyzer(
                max_events=settings.oncall_fatigue_max_events,
                burnout_threshold=settings.oncall_fatigue_burnout_threshold,
            )
            of_route.set_analyzer(of_analyzer)
            app.include_router(
                of_route.router,
                prefix=settings.api_prefix,
                tags=["On-Call Fatigue"],
            )
            logger.info("oncall_fatigue_initialized")
        except Exception as e:
            logger.warning("oncall_fatigue_init_failed", error=str(e))

    # ── Phase 20: Backup Verification Engine ───────────────────
    if settings.backup_verification_enabled:
        try:
            from shieldops.api.routes import backup_verification as bv_route
            from shieldops.observability.backup_verification import (
                BackupVerificationEngine,
            )

            bv_engine = BackupVerificationEngine(
                max_backups=settings.backup_verification_max_backups,
                stale_hours=settings.backup_verification_stale_hours,
            )
            bv_route.set_engine(bv_engine)
            app.include_router(
                bv_route.router,
                prefix=settings.api_prefix,
                tags=["Backup Verification"],
            )
            logger.info("backup_verification_initialized")
        except Exception as e:
            logger.warning("backup_verification_init_failed", error=str(e))

    # ── Phase 20: Cost Allocation Tag Enforcer ─────────────────
    if settings.cost_tag_enforcer_enabled:
        try:
            from shieldops.api.routes import cost_tag_enforcer as cte_route
            from shieldops.billing.cost_tag_enforcer import (
                CostAllocationTagEnforcer,
            )

            cte_enforcer = CostAllocationTagEnforcer(
                max_policies=settings.cost_tag_enforcer_max_policies,
                max_checks=settings.cost_tag_enforcer_max_checks,
            )
            cte_route.set_enforcer(cte_enforcer)
            app.include_router(
                cte_route.router,
                prefix=settings.api_prefix,
                tags=["Cost Tag Enforcer"],
            )
            logger.info("cost_tag_enforcer_initialized")
        except Exception as e:
            logger.warning("cost_tag_enforcer_init_failed", error=str(e))

    # --- Phase 21 ---

    if settings.dr_readiness_enabled:
        try:
            from shieldops.api.routes import dr_readiness as drr_route
            from shieldops.observability.dr_readiness import (
                DisasterRecoveryReadinessTracker,
            )

            dr_tracker = DisasterRecoveryReadinessTracker(
                max_plans=settings.dr_readiness_max_plans,
                drill_max_age_days=settings.dr_readiness_drill_max_age_days,
            )
            drr_route.set_tracker(dr_tracker)
            app.include_router(
                drr_route.router,
                prefix=settings.api_prefix,
                tags=["DR Readiness"],
            )
            logger.info("dr_readiness_initialized")
        except Exception as e:
            logger.warning("dr_readiness_init_failed", error=str(e))

    if settings.service_catalog_enabled:
        try:
            from shieldops.api.routes import service_catalog as sc_route
            from shieldops.topology.service_catalog import (
                ServiceCatalogManager,
            )

            sc_manager = ServiceCatalogManager(
                max_services=settings.service_catalog_max_services,
                stale_days=settings.service_catalog_stale_days,
            )
            sc_route.set_manager(sc_manager)
            app.include_router(
                sc_route.router,
                prefix=settings.api_prefix,
                tags=["Service Catalog"],
            )
            logger.info("service_catalog_initialized")
        except Exception as e:
            logger.warning("service_catalog_init_failed", error=str(e))

    if settings.contract_testing_enabled:
        try:
            from shieldops.api.contract_testing import (
                APIContractTestingEngine,
            )
            from shieldops.api.routes import contract_testing as ctest_route

            ct_engine = APIContractTestingEngine(
                max_schemas=settings.contract_testing_max_schemas,
                max_checks=settings.contract_testing_max_checks,
            )
            ctest_route.set_engine(ct_engine)
            app.include_router(
                ctest_route.router,
                prefix=settings.api_prefix,
                tags=["Contract Testing"],
            )
            logger.info("contract_testing_initialized")
        except Exception as e:
            logger.warning("contract_testing_init_failed", error=str(e))

    if settings.orphan_detector_enabled:
        try:
            from shieldops.api.routes import orphan_detector as od_route
            from shieldops.billing.orphan_detector import (
                OrphanedResourceDetector,
            )

            od_detector = OrphanedResourceDetector(
                max_resources=settings.orphan_detector_max_resources,
                stale_days=settings.orphan_detector_stale_days,
            )
            od_route.set_detector(od_detector)
            app.include_router(
                od_route.router,
                prefix=settings.api_prefix,
                tags=["Orphan Detector"],
            )
            logger.info("orphan_detector_initialized")
        except Exception as e:
            logger.warning("orphan_detector_init_failed", error=str(e))

    if settings.latency_profiler_enabled:
        try:
            from shieldops.analytics.latency_profiler import (
                ServiceLatencyProfiler,
            )
            from shieldops.api.routes import latency_profiler as lp_route

            lp_profiler = ServiceLatencyProfiler(
                max_samples=settings.latency_profiler_max_samples,
                regression_threshold=settings.latency_profiler_regression_threshold,
            )
            lp_route.set_profiler(lp_profiler)
            app.include_router(
                lp_route.router,
                prefix=settings.api_prefix,
                tags=["Latency Profiler"],
            )
            logger.info("latency_profiler_initialized")
        except Exception as e:
            logger.warning("latency_profiler_init_failed", error=str(e))

    if settings.license_scanner_enabled:
        try:
            from shieldops.api.routes import license_scanner as ls_route
            from shieldops.compliance.license_scanner import (
                DependencyLicenseScanner,
            )

            ls_scanner = DependencyLicenseScanner(
                max_dependencies=settings.license_scanner_max_dependencies,
                max_violations=settings.license_scanner_max_violations,
            )
            ls_route.set_scanner(ls_scanner)
            app.include_router(
                ls_route.router,
                prefix=settings.api_prefix,
                tags=["License Scanner"],
            )
            logger.info("license_scanner_initialized")
        except Exception as e:
            logger.warning("license_scanner_init_failed", error=str(e))

    if settings.release_manager_enabled:
        try:
            from shieldops.api.routes import release_manager as rm_route
            from shieldops.changes.release_manager import (
                ReleaseManagementTracker,
            )

            rm_tracker = ReleaseManagementTracker(
                max_releases=settings.release_manager_max_releases,
                require_approval=settings.release_manager_require_approval,
            )
            rm_route.set_tracker(rm_tracker)
            app.include_router(
                rm_route.router,
                prefix=settings.api_prefix,
                tags=["Release Manager"],
            )
            logger.info("release_manager_initialized")
        except Exception as e:
            logger.warning("release_manager_init_failed", error=str(e))

    if settings.budget_manager_enabled:
        try:
            from shieldops.api.routes import budget_manager as bm_route
            from shieldops.billing.budget_manager import (
                InfrastructureCostBudgetManager,
            )

            bm_manager = InfrastructureCostBudgetManager(
                max_budgets=settings.budget_manager_max_budgets,
                warning_threshold=settings.budget_manager_warning_threshold,
            )
            bm_route.set_manager(bm_manager)
            app.include_router(
                bm_route.router,
                prefix=settings.api_prefix,
                tags=["Budget Manager"],
            )
            logger.info("budget_manager_initialized")
        except Exception as e:
            logger.warning("budget_manager_init_failed", error=str(e))

    if settings.config_parity_enabled:
        try:
            from shieldops.api.routes import config_parity as cp_route
            from shieldops.config.parity_validator import (
                ConfigurationParityValidator,
            )

            cp_validator = ConfigurationParityValidator(
                max_configs=settings.config_parity_max_configs,
                max_violations=settings.config_parity_max_violations,
            )
            cp_route.set_validator(cp_validator)
            app.include_router(
                cp_route.router,
                prefix=settings.api_prefix,
                tags=["Config Parity"],
            )
            logger.info("config_parity_initialized")
        except Exception as e:
            logger.warning("config_parity_init_failed", error=str(e))

    if settings.incident_dedup_enabled:
        try:
            from shieldops.api.routes import incident_dedup as id_route
            from shieldops.incidents.dedup_engine import (
                IncidentDeduplicationEngine,
            )

            id_engine = IncidentDeduplicationEngine(
                max_incidents=settings.incident_dedup_max_incidents,
                similarity_threshold=settings.incident_dedup_similarity_threshold,
            )
            id_route.set_engine(id_engine)
            app.include_router(
                id_route.router,
                prefix=settings.api_prefix,
                tags=["Incident Dedup"],
            )
            logger.info("incident_dedup_initialized")
        except Exception as e:
            logger.warning("incident_dedup_init_failed", error=str(e))

    if settings.access_certification_enabled:
        try:
            from shieldops.api.routes import access_certification as ac_route
            from shieldops.compliance.access_certification import (
                AccessCertificationManager,
            )

            ac_manager = AccessCertificationManager(
                max_grants=settings.access_certification_max_grants,
                default_expiry_days=settings.access_certification_default_expiry_days,
            )
            ac_route.set_manager(ac_manager)
            app.include_router(
                ac_route.router,
                prefix=settings.api_prefix,
                tags=["Access Certification"],
            )
            logger.info("access_certification_initialized")
        except Exception as e:
            logger.warning("access_certification_init_failed", error=str(e))

    if settings.toil_tracker_enabled:
        try:
            from shieldops.analytics.toil_tracker import (
                ToilMeasurementTracker,
            )
            from shieldops.api.routes import toil_tracker as toil_route

            tt_tracker = ToilMeasurementTracker(
                max_entries=settings.toil_tracker_max_entries,
                automation_min_occurrences=settings.toil_tracker_automation_min_occurrences,
            )
            toil_route.set_tracker(tt_tracker)
            app.include_router(
                toil_route.router,
                prefix=settings.api_prefix,
                tags=["Toil Tracker"],
            )
            logger.info("toil_tracker_initialized")
        except Exception as e:
            logger.warning("toil_tracker_init_failed", error=str(e))

    # ── Phase 22: Distributed Trace Analyzer ──
    if settings.trace_analyzer_enabled:
        try:
            from shieldops.analytics.trace_analyzer import (
                DistributedTraceAnalyzer,
            )
            from shieldops.api.routes import trace_analyzer as ta_route

            ta_analyzer = DistributedTraceAnalyzer(
                max_traces=settings.trace_analyzer_max_traces,
                bottleneck_threshold=settings.trace_analyzer_bottleneck_threshold,
            )
            ta_route.set_analyzer(ta_analyzer)
            app.include_router(
                ta_route.router,
                prefix=settings.api_prefix,
                tags=["Trace Analyzer"],
            )
            logger.info("trace_analyzer_initialized")
        except Exception as e:
            logger.warning("trace_analyzer_init_failed", error=str(e))

    # ── Phase 22: Log Anomaly Detector ──
    if settings.log_anomaly_enabled:
        try:
            from shieldops.analytics.log_anomaly import (
                LogAnomalyDetector,
            )
            from shieldops.api.routes import log_anomaly as la_route

            la_detector = LogAnomalyDetector(
                max_patterns=settings.log_anomaly_max_patterns,
                sensitivity=settings.log_anomaly_sensitivity,
            )
            la_route.set_detector(la_detector)
            app.include_router(
                la_route.router,
                prefix=settings.api_prefix,
                tags=["Log Anomaly"],
            )
            logger.info("log_anomaly_initialized")
        except Exception as e:
            logger.warning("log_anomaly_init_failed", error=str(e))

    # ── Phase 22: Event Correlation Engine ──
    if settings.event_correlation_enabled:
        try:
            from shieldops.analytics.event_correlation import (
                EventCorrelationEngine,
            )
            from shieldops.api.routes import event_correlation as ec_route

            ec_engine = EventCorrelationEngine(
                max_events=settings.event_correlation_max_events,
                window_minutes=settings.event_correlation_window_minutes,
            )
            ec_route.set_engine(ec_engine)
            app.include_router(
                ec_route.router,
                prefix=settings.api_prefix,
                tags=["Event Correlation"],
            )
            logger.info("event_correlation_initialized")
        except Exception as e:
            logger.warning("event_correlation_init_failed", error=str(e))

    # ── Phase 22: Security Incident Response Tracker ──
    if settings.security_incident_enabled:
        try:
            from shieldops.api.routes import security_incident as sir_route
            from shieldops.security.incident_response import (
                SecurityIncidentResponseTracker,
            )

            sir_tracker = SecurityIncidentResponseTracker(
                max_incidents=settings.security_incident_max_incidents,
                auto_escalate_minutes=settings.security_incident_auto_escalate_minutes,
            )
            sir_route.set_tracker(sir_tracker)
            app.include_router(
                sir_route.router,
                prefix=settings.api_prefix,
                tags=["Security Incidents"],
            )
            logger.info("security_incident_initialized")
        except Exception as e:
            logger.warning("security_incident_init_failed", error=str(e))

    # ── Phase 22: Vulnerability Lifecycle Manager ──
    if settings.vuln_lifecycle_enabled:
        try:
            from shieldops.api.routes import vuln_lifecycle as vl_route
            from shieldops.security.vuln_lifecycle import (
                VulnerabilityLifecycleManager,
            )

            vl_manager = VulnerabilityLifecycleManager(
                max_records=settings.vuln_lifecycle_max_records,
                patch_sla_days=settings.vuln_lifecycle_patch_sla_days,
            )
            vl_route.set_manager(vl_manager)
            app.include_router(
                vl_route.router,
                prefix=settings.api_prefix,
                tags=["Vulnerability Lifecycle"],
            )
            logger.info("vuln_lifecycle_initialized")
        except Exception as e:
            logger.warning("vuln_lifecycle_init_failed", error=str(e))

    # ── Phase 22: API Security Monitor ──
    if settings.api_security_enabled:
        try:
            from shieldops.api.routes import api_security as as_route
            from shieldops.security.api_security import (
                APISecurityMonitor,
            )

            as_monitor = APISecurityMonitor(
                max_endpoints=settings.api_security_max_endpoints,
                alert_threshold=settings.api_security_alert_threshold,
            )
            as_route.set_monitor(as_monitor)
            app.include_router(
                as_route.router,
                prefix=settings.api_prefix,
                tags=["API Security"],
            )
            logger.info("api_security_initialized")
        except Exception as e:
            logger.warning("api_security_init_failed", error=str(e))

    # ── Phase 22: Resource Tag Governance Engine ──
    if settings.tag_governance_enabled:
        try:
            from shieldops.api.routes import tag_governance as tg_route
            from shieldops.billing.tag_governance import (
                ResourceTagGovernanceEngine,
            )

            tg_engine = ResourceTagGovernanceEngine(
                max_policies=settings.tag_governance_max_policies,
                max_reports=settings.tag_governance_max_reports,
            )
            tg_route.set_engine(tg_engine)
            app.include_router(
                tg_route.router,
                prefix=settings.api_prefix,
                tags=["Tag Governance"],
            )
            logger.info("tag_governance_initialized")
        except Exception as e:
            logger.warning("tag_governance_init_failed", error=str(e))

    # ── Phase 22: Team Performance Analyzer ──
    if settings.team_performance_enabled:
        try:
            from shieldops.analytics.team_performance import (
                TeamPerformanceAnalyzer,
            )
            from shieldops.api.routes import team_performance as tp_route

            tp_analyzer = TeamPerformanceAnalyzer(
                max_members=settings.team_performance_max_members,
                burnout_threshold=settings.team_performance_burnout_threshold,
            )
            tp_route.set_analyzer(tp_analyzer)
            app.include_router(
                tp_route.router,
                prefix=settings.api_prefix,
                tags=["Team Performance"],
            )
            logger.info("team_performance_initialized")
        except Exception as e:
            logger.warning("team_performance_init_failed", error=str(e))

    # ── Phase 22: Runbook Execution Engine ──
    if settings.runbook_engine_enabled:
        try:
            from shieldops.api.routes import runbook_engine as re_route
            from shieldops.operations.runbook_engine import (
                RunbookExecutionEngine,
            )

            re_engine = RunbookExecutionEngine(
                max_executions=settings.runbook_engine_max_executions,
                step_timeout=settings.runbook_engine_step_timeout,
            )
            re_route.set_engine(re_engine)
            app.include_router(
                re_route.router,
                prefix=settings.api_prefix,
                tags=["Runbook Engine"],
            )
            logger.info("runbook_engine_initialized")
        except Exception as e:
            logger.warning("runbook_engine_init_failed", error=str(e))

    # ── Phase 22: Dependency Health Scorer ──
    if settings.dependency_scorer_enabled:
        try:
            from shieldops.api.routes import dependency_scorer as ds_route
            from shieldops.topology.dependency_scorer import (
                DependencyHealthScorer,
            )

            ds_scorer = DependencyHealthScorer(
                max_dependencies=settings.dependency_scorer_max_dependencies,
                check_interval=settings.dependency_scorer_check_interval,
            )
            ds_route.set_scorer(ds_scorer)
            app.include_router(
                ds_route.router,
                prefix=settings.api_prefix,
                tags=["Dependency Scorer"],
            )
            logger.info("dependency_scorer_initialized")
        except Exception as e:
            logger.warning("dependency_scorer_init_failed", error=str(e))

    # ── Phase 22: SLO Burn Rate Predictor ──
    if settings.burn_predictor_enabled:
        try:
            from shieldops.api.routes import burn_predictor as bp_route
            from shieldops.sla.burn_predictor import (
                SLOBurnRatePredictor,
            )

            bp_predictor = SLOBurnRatePredictor(
                max_slos=settings.burn_predictor_max_slos,
                forecast_hours=settings.burn_predictor_forecast_hours,
            )
            bp_route.set_predictor(bp_predictor)
            app.include_router(
                bp_route.router,
                prefix=settings.api_prefix,
                tags=["Burn Predictor"],
            )
            logger.info("burn_predictor_initialized")
        except Exception as e:
            logger.warning("burn_predictor_init_failed", error=str(e))

    # ── Phase 22: Change Intelligence Analyzer ──
    if settings.change_intelligence_enabled:
        try:
            from shieldops.api.routes import change_intelligence as ci_route
            from shieldops.changes.change_intelligence import (
                ChangeIntelligenceAnalyzer,
            )

            ci_analyzer = ChangeIntelligenceAnalyzer(
                max_records=settings.change_intelligence_max_records,
                risk_threshold=settings.change_intelligence_risk_threshold,
            )
            ci_route.set_analyzer(ci_analyzer)
            app.include_router(
                ci_route.router,
                prefix=settings.api_prefix,
                tags=["Change Intelligence"],
            )
            logger.info("change_intelligence_initialized")
        except Exception as e:
            logger.warning("change_intelligence_init_failed", error=str(e))

    # ── Phase 23: Database Performance Analyzer ──
    if settings.db_performance_enabled:
        try:
            from shieldops.analytics.db_performance import (
                DatabasePerformanceAnalyzer,
            )
            from shieldops.api.routes import db_performance as db_perf_route

            db_perf_analyzer = DatabasePerformanceAnalyzer(
                max_queries=settings.db_performance_max_queries,
                slow_threshold_ms=settings.db_performance_slow_threshold_ms,
            )
            db_perf_route.set_analyzer(db_perf_analyzer)
            app.include_router(
                db_perf_route.router,
                prefix=settings.api_prefix,
                tags=["Database Performance"],
            )
            logger.info("db_performance_initialized")
        except Exception as e:
            logger.warning("db_performance_init_failed", error=str(e))

    # ── Phase 23: Queue Health Monitor ──
    if settings.queue_health_enabled:
        try:
            from shieldops.api.routes import queue_health as qh_route
            from shieldops.observability.queue_health import (
                QueueHealthMonitor,
            )

            qh_monitor = QueueHealthMonitor(
                max_metrics=settings.queue_health_max_metrics,
                stall_threshold_seconds=settings.queue_health_stall_threshold_seconds,
            )
            qh_route.set_monitor(qh_monitor)
            app.include_router(
                qh_route.router,
                prefix=settings.api_prefix,
                tags=["Queue Health"],
            )
            logger.info("queue_health_initialized")
        except Exception as e:
            logger.warning("queue_health_init_failed", error=str(e))

    # ── Phase 23: Certificate Expiry Monitor ──
    if settings.cert_monitor_enabled:
        try:
            from shieldops.api.routes import cert_monitor as cm_route
            from shieldops.security.cert_monitor import (
                CertificateExpiryMonitor,
            )

            cm_monitor = CertificateExpiryMonitor(
                max_certificates=settings.cert_monitor_max_certificates,
                expiry_warning_days=settings.cert_monitor_expiry_warning_days,
            )
            cm_route.set_monitor(cm_monitor)
            app.include_router(
                cm_route.router,
                prefix=settings.api_prefix,
                tags=["Certificate Monitor"],
            )
            logger.info("cert_monitor_initialized")
        except Exception as e:
            logger.warning("cert_monitor_init_failed", error=str(e))

    # ── Phase 23: Network Flow Analyzer ──
    if settings.network_flow_enabled:
        try:
            from shieldops.api.routes import network_flow as nf_route
            from shieldops.security.network_flow import (
                NetworkFlowAnalyzer,
            )

            nf_analyzer = NetworkFlowAnalyzer(
                max_records=settings.network_flow_max_records,
                anomaly_threshold=settings.network_flow_anomaly_threshold,
            )
            nf_route.set_analyzer(nf_analyzer)
            app.include_router(
                nf_route.router,
                prefix=settings.api_prefix,
                tags=["Network Flow"],
            )
            logger.info("network_flow_initialized")
        except Exception as e:
            logger.warning("network_flow_init_failed", error=str(e))

    # ── Phase 23: DNS Health Monitor ──
    if settings.dns_health_enabled:
        try:
            from shieldops.api.routes import dns_health as dh_route
            from shieldops.observability.dns_health import (
                DNSHealthMonitor,
            )

            dh_monitor = DNSHealthMonitor(
                max_checks=settings.dns_health_max_checks,
                timeout_ms=settings.dns_health_timeout_ms,
            )
            dh_route.set_monitor(dh_monitor)
            app.include_router(
                dh_route.router,
                prefix=settings.api_prefix,
                tags=["DNS Health"],
            )
            logger.info("dns_health_initialized")
        except Exception as e:
            logger.warning("dns_health_init_failed", error=str(e))

    # ── Phase 23: Escalation Pattern Analyzer ──
    if settings.escalation_analyzer_enabled:
        try:
            from shieldops.api.routes import escalation_analyzer as ea_route
            from shieldops.incidents.escalation_analyzer import (
                EscalationPatternAnalyzer,
            )

            ea_analyzer = EscalationPatternAnalyzer(
                max_events=settings.escalation_analyzer_max_events,
                false_alarm_threshold=settings.escalation_analyzer_false_alarm_threshold,
            )
            ea_route.set_analyzer(ea_analyzer)
            app.include_router(
                ea_route.router,
                prefix=settings.api_prefix,
                tags=["Escalation Analyzer"],
            )
            logger.info("escalation_analyzer_initialized")
        except Exception as e:
            logger.warning("escalation_analyzer_init_failed", error=str(e))

    # ── Phase 23: Capacity Right-Sizing Recommender ──
    if settings.right_sizer_enabled:
        try:
            from shieldops.api.routes import right_sizer as rs_route
            from shieldops.billing.right_sizer import (
                CapacityRightSizer,
            )

            rs_engine = CapacityRightSizer(
                max_samples=settings.right_sizer_max_samples,
                underutil_threshold=settings.right_sizer_underutil_threshold,
            )
            rs_route.set_right_sizer(rs_engine)
            app.include_router(
                rs_route.router,
                prefix=settings.api_prefix,
                tags=["Right Sizer"],
            )
            logger.info("right_sizer_initialized")
        except Exception as e:
            logger.warning("right_sizer_init_failed", error=str(e))

    # ── Phase 23: Storage Tier Optimizer ──
    if settings.storage_optimizer_enabled:
        try:
            from shieldops.api.routes import storage_optimizer as so_route
            from shieldops.billing.storage_optimizer import (
                StorageTierOptimizer,
            )

            so_engine = StorageTierOptimizer(
                max_assets=settings.storage_optimizer_max_assets,
                cold_threshold_days=settings.storage_optimizer_cold_threshold_days,
            )
            so_route.set_optimizer(so_engine)
            app.include_router(
                so_route.router,
                prefix=settings.api_prefix,
                tags=["Storage Optimizer"],
            )
            logger.info("storage_optimizer_initialized")
        except Exception as e:
            logger.warning("storage_optimizer_init_failed", error=str(e))

    # ── Phase 23: Resource Lifecycle Tracker ──
    if settings.resource_lifecycle_enabled:
        try:
            from shieldops.api.routes import resource_lifecycle as rl_route
            from shieldops.billing.resource_lifecycle import (
                ResourceLifecycleTracker,
            )

            rl_tracker = ResourceLifecycleTracker(
                max_resources=settings.resource_lifecycle_max_resources,
                stale_days=settings.resource_lifecycle_stale_days,
            )
            rl_route.set_tracker(rl_tracker)
            app.include_router(
                rl_route.router,
                prefix=settings.api_prefix,
                tags=["Resource Lifecycle"],
            )
            logger.info("resource_lifecycle_initialized")
        except Exception as e:
            logger.warning("resource_lifecycle_init_failed", error=str(e))

    # ── Phase 23: Alert Routing Optimizer ──
    if settings.alert_routing_enabled:
        try:
            from shieldops.api.routes import alert_routing as ar_route
            from shieldops.observability.alert_routing import (
                AlertRoutingOptimizer,
            )

            ar_optimizer = AlertRoutingOptimizer(
                max_records=settings.alert_routing_max_records,
                reroute_threshold=settings.alert_routing_reroute_threshold,
            )
            ar_route.set_optimizer(ar_optimizer)
            app.include_router(
                ar_route.router,
                prefix=settings.api_prefix,
                tags=["Alert Routing"],
            )
            logger.info("alert_routing_initialized")
        except Exception as e:
            logger.warning("alert_routing_init_failed", error=str(e))

    # ── Phase 23: SLO Target Advisor ──
    if settings.slo_advisor_enabled:
        try:
            from shieldops.api.routes import slo_advisor as sa_route
            from shieldops.sla.slo_advisor import (
                SLOTargetAdvisor,
            )

            sa_advisor = SLOTargetAdvisor(
                max_samples=settings.slo_advisor_max_samples,
                min_sample_count=settings.slo_advisor_min_sample_count,
            )
            sa_route.set_advisor(sa_advisor)
            app.include_router(
                sa_route.router,
                prefix=settings.api_prefix,
                tags=["SLO Advisor"],
            )
            logger.info("slo_advisor_initialized")
        except Exception as e:
            logger.warning("slo_advisor_init_failed", error=str(e))

    # ── Phase 23: Workload Scheduling Optimizer ──
    if settings.workload_scheduler_enabled:
        try:
            from shieldops.api.routes import workload_scheduler as ws_route
            from shieldops.operations.workload_scheduler import (
                WorkloadSchedulingOptimizer,
            )

            ws_optimizer = WorkloadSchedulingOptimizer(
                max_workloads=settings.workload_scheduler_max_workloads,
                conflict_window_seconds=settings.workload_scheduler_conflict_window_seconds,
            )
            ws_route.set_optimizer(ws_optimizer)
            app.include_router(
                ws_route.router,
                prefix=settings.api_prefix,
                tags=["Workload Scheduler"],
            )
            logger.info("workload_scheduler_initialized")
        except Exception as e:
            logger.warning("workload_scheduler_init_failed", error=str(e))

    # ── Phase 24: Cascading Failure Predictor ──
    if settings.cascade_predictor_enabled:
        try:
            from shieldops.api.routes import cascade_predictor as cascade_route
            from shieldops.topology.cascade_predictor import (
                CascadingFailurePredictor,
            )

            cp_predictor = CascadingFailurePredictor(
                max_services=settings.cascade_predictor_max_services,
                max_cascade_depth=settings.cascade_predictor_max_cascade_depth,
            )
            cascade_route.set_predictor(cp_predictor)
            app.include_router(
                cascade_route.router,
                prefix=settings.api_prefix,
                tags=["Cascade Predictor"],
            )
            logger.info("cascade_predictor_initialized")
        except Exception as e:
            logger.warning("cascade_predictor_init_failed", error=str(e))

    # ── Phase 24: Resilience Score Calculator ──
    if settings.resilience_scorer_enabled:
        try:
            from shieldops.api.routes import resilience_scorer as rsc_route
            from shieldops.observability.resilience_scorer import (
                ResilienceScoreCalculator,
            )

            rsc_calculator = ResilienceScoreCalculator(
                max_profiles=settings.resilience_scorer_max_profiles,
                minimum_score_threshold=settings.resilience_scorer_minimum_score_threshold,
            )
            rsc_route.set_scorer(rsc_calculator)
            app.include_router(
                rsc_route.router,
                prefix=settings.api_prefix,
                tags=["Resilience Scorer"],
            )
            logger.info("resilience_scorer_initialized")
        except Exception as e:
            logger.warning("resilience_scorer_init_failed", error=str(e))

    # ── Phase 24: Incident Timeline Reconstructor ──
    if settings.timeline_reconstructor_enabled:
        try:
            from shieldops.api.routes import timeline_reconstructor as tr_route
            from shieldops.incidents.timeline_reconstructor import (
                IncidentTimelineReconstructor,
            )

            tr_reconstructor = IncidentTimelineReconstructor(
                max_events=settings.timeline_reconstructor_max_events,
                correlation_window_seconds=settings.timeline_reconstructor_correlation_window_seconds,
            )
            tr_route.set_reconstructor(tr_reconstructor)
            app.include_router(
                tr_route.router,
                prefix=settings.api_prefix,
                tags=["Timeline Reconstructor"],
            )
            logger.info("timeline_reconstructor_initialized")
        except Exception as e:
            logger.warning("timeline_reconstructor_init_failed", error=str(e))

    # ── Phase 24: Reserved Instance Optimizer ──
    if settings.reserved_instance_optimizer_enabled:
        try:
            from shieldops.api.routes import reserved_instance_optimizer as ri_route
            from shieldops.billing.reserved_instance_optimizer import (
                ReservedInstanceOptimizer,
            )

            ri_optimizer = ReservedInstanceOptimizer(
                max_reservations=settings.reserved_instance_optimizer_max_reservations,
                expiry_warning_days=settings.reserved_instance_optimizer_expiry_warning_days,
            )
            ri_route.set_optimizer(ri_optimizer)
            app.include_router(
                ri_route.router,
                prefix=settings.api_prefix,
                tags=["Reserved Instance Optimizer"],
            )
            logger.info("reserved_instance_optimizer_initialized")
        except Exception as e:
            logger.warning("reserved_instance_optimizer_init_failed", error=str(e))

    # ── Phase 24: Cost Anomaly Root Cause Analyzer ──
    if settings.cost_anomaly_rca_enabled:
        try:
            from shieldops.api.routes import cost_anomaly_rca as cr_route
            from shieldops.billing.cost_anomaly_rca import (
                CostAnomalyRootCauseAnalyzer,
            )

            cr_analyzer = CostAnomalyRootCauseAnalyzer(
                max_spikes=settings.cost_anomaly_rca_max_spikes,
                deviation_threshold_pct=settings.cost_anomaly_rca_deviation_threshold_pct,
            )
            cr_route.set_analyzer(cr_analyzer)
            app.include_router(
                cr_route.router,
                prefix=settings.api_prefix,
                tags=["Cost Anomaly RCA"],
            )
            logger.info("cost_anomaly_rca_initialized")
        except Exception as e:
            logger.warning("cost_anomaly_rca_init_failed", error=str(e))

    # ── Phase 24: Spend Allocation Engine ──
    if settings.spend_allocation_enabled:
        try:
            from shieldops.api.routes import spend_allocation as spa_route
            from shieldops.billing.spend_allocation import (
                SpendAllocationEngine,
            )

            spa_engine = SpendAllocationEngine(
                max_pools=settings.spend_allocation_max_pools,
                min_allocation_threshold=settings.spend_allocation_min_allocation_threshold,
            )
            spa_route.set_engine(spa_engine)
            app.include_router(
                spa_route.router,
                prefix=settings.api_prefix,
                tags=["Spend Allocation"],
            )
            logger.info("spend_allocation_initialized")
        except Exception as e:
            logger.warning("spend_allocation_init_failed", error=str(e))

    # ── Phase 24: Container Image Scanner ──
    if settings.container_scanner_enabled:
        try:
            from shieldops.api.routes import container_scanner as cs_route
            from shieldops.security.container_scanner import (
                ContainerImageScanner,
            )

            cs_scanner = ContainerImageScanner(
                max_images=settings.container_scanner_max_images,
                stale_threshold_days=settings.container_scanner_stale_threshold_days,
            )
            cs_route.set_scanner(cs_scanner)
            app.include_router(
                cs_route.router,
                prefix=settings.api_prefix,
                tags=["Container Scanner"],
            )
            logger.info("container_scanner_initialized")
        except Exception as e:
            logger.warning("container_scanner_init_failed", error=str(e))

    # ── Phase 24: Cloud Security Posture Manager ──
    if settings.cloud_posture_manager_enabled:
        try:
            from shieldops.api.routes import cloud_posture_manager as cpm_route
            from shieldops.security.cloud_posture_manager import (
                CloudSecurityPostureManager,
            )

            cpm_manager = CloudSecurityPostureManager(
                max_resources=settings.cloud_posture_manager_max_resources,
                auto_resolve_days=settings.cloud_posture_manager_auto_resolve_days,
            )
            cpm_route.set_manager(cpm_manager)
            app.include_router(
                cpm_route.router,
                prefix=settings.api_prefix,
                tags=["Cloud Posture Manager"],
            )
            logger.info("cloud_posture_manager_initialized")
        except Exception as e:
            logger.warning("cloud_posture_manager_init_failed", error=str(e))

    # ── Phase 24: Secrets Sprawl Detector ──
    if settings.secrets_detector_enabled:
        try:
            from shieldops.api.routes import secrets_detector as sd_route
            from shieldops.security.secrets_detector import (
                SecretsSprawlDetector,
            )

            sd_detector = SecretsSprawlDetector(
                max_findings=settings.secrets_detector_max_findings,
                high_severity_threshold=settings.secrets_detector_high_severity_threshold,
            )
            sd_route.set_detector(sd_detector)
            app.include_router(
                sd_route.router,
                prefix=settings.api_prefix,
                tags=["Secrets Detector"],
            )
            logger.info("secrets_detector_initialized")
        except Exception as e:
            logger.warning("secrets_detector_init_failed", error=str(e))

    # ── Phase 24: Runbook Effectiveness Analyzer ──
    if settings.runbook_effectiveness_enabled:
        try:
            from shieldops.api.routes import runbook_effectiveness as ref_route
            from shieldops.operations.runbook_effectiveness import (
                RunbookEffectivenessAnalyzer,
            )

            ref_analyzer = RunbookEffectivenessAnalyzer(
                max_outcomes=settings.runbook_effectiveness_max_outcomes,
                decay_window_days=settings.runbook_effectiveness_decay_window_days,
            )
            ref_route.set_analyzer(ref_analyzer)
            app.include_router(
                ref_route.router,
                prefix=settings.api_prefix,
                tags=["Runbook Effectiveness"],
            )
            logger.info("runbook_effectiveness_initialized")
        except Exception as e:
            logger.warning("runbook_effectiveness_init_failed", error=str(e))

    # ── Phase 24: API Deprecation Tracker ──
    if settings.api_deprecation_tracker_enabled:
        try:
            from shieldops.analytics.api_deprecation_tracker import (
                APIDeprecationTracker,
            )
            from shieldops.api.routes import api_deprecation_tracker as adt_route

            adt_tracker = APIDeprecationTracker(
                max_records=settings.api_deprecation_tracker_max_records,
                sunset_warning_days=settings.api_deprecation_tracker_sunset_warning_days,
            )
            adt_route.set_tracker(adt_tracker)
            app.include_router(
                adt_route.router,
                prefix=settings.api_prefix,
                tags=["API Deprecation Tracker"],
            )
            logger.info("api_deprecation_tracker_initialized")
        except Exception as e:
            logger.warning("api_deprecation_tracker_init_failed", error=str(e))

    # ── Phase 24: Dependency Freshness Monitor ──
    if settings.dependency_freshness_enabled:
        try:
            from shieldops.analytics.dependency_freshness import (
                DependencyFreshnessMonitor,
            )
            from shieldops.api.routes import dependency_freshness as df_route

            df_monitor = DependencyFreshnessMonitor(
                max_dependencies=settings.dependency_freshness_max_dependencies,
                stale_version_threshold=settings.dependency_freshness_stale_version_threshold,
            )
            df_route.set_monitor(df_monitor)
            app.include_router(
                df_route.router,
                prefix=settings.api_prefix,
                tags=["Dependency Freshness"],
            )
            logger.info("dependency_freshness_initialized")
        except Exception as e:
            logger.warning("dependency_freshness_init_failed", error=str(e))

    # ── Phase 25: Chaos Experiment Designer ──────────────────────
    if settings.chaos_designer_enabled:
        try:
            from shieldops.api.routes import chaos_designer as cd_route
            from shieldops.observability.chaos_designer import (
                ChaosExperimentDesigner,
            )

            cd_designer = ChaosExperimentDesigner(
                max_experiments=settings.chaos_designer_max_experiments,
                max_blast_radius=settings.chaos_designer_max_blast_radius,
            )
            cd_route.set_designer(cd_designer)
            app.include_router(
                cd_route.router,
                prefix=settings.api_prefix,
                tags=["Chaos Designer"],
            )
            logger.info("chaos_designer_initialized")
        except Exception as e:
            logger.warning("chaos_designer_init_failed", error=str(e))

    # ── Phase 25: Game Day Planner ───────────────────────────────
    if settings.game_day_planner_enabled:
        try:
            from shieldops.api.routes import game_day_planner as gdp_route
            from shieldops.operations.game_day_planner import (
                GameDayPlanner,
            )

            gdp_planner = GameDayPlanner(
                max_game_days=settings.game_day_planner_max_game_days,
                min_scenarios_per_day=settings.game_day_planner_min_scenarios_per_day,
            )
            gdp_route.set_planner(gdp_planner)
            app.include_router(
                gdp_route.router,
                prefix=settings.api_prefix,
                tags=["Game Day Planner"],
            )
            logger.info("game_day_planner_initialized")
        except Exception as e:
            logger.warning("game_day_planner_init_failed", error=str(e))

    # ── Phase 25: Failure Mode Catalog ───────────────────────────
    if settings.failure_mode_catalog_enabled:
        try:
            from shieldops.api.routes import failure_mode_catalog as fmc_route
            from shieldops.topology.failure_mode_catalog import (
                FailureModeCatalog,
            )

            fmc_catalog = FailureModeCatalog(
                max_modes=settings.failure_mode_catalog_max_modes,
                mtbf_window_days=settings.failure_mode_catalog_mtbf_window_days,
            )
            fmc_route.set_catalog(fmc_catalog)
            app.include_router(
                fmc_route.router,
                prefix=settings.api_prefix,
                tags=["Failure Mode Catalog"],
            )
            logger.info("failure_mode_catalog_initialized")
        except Exception as e:
            logger.warning("failure_mode_catalog_init_failed", error=str(e))

    # ── Phase 25: On-Call Rotation Optimizer ─────────────────────
    if settings.oncall_optimizer_enabled:
        try:
            from shieldops.api.routes import oncall_optimizer as oo_route
            from shieldops.incidents.oncall_optimizer import (
                OnCallRotationOptimizer,
            )

            oo_optimizer = OnCallRotationOptimizer(
                max_members=settings.oncall_optimizer_max_members,
                max_consecutive_days=settings.oncall_optimizer_max_consecutive_days,
            )
            oo_route.set_optimizer(oo_optimizer)
            app.include_router(
                oo_route.router,
                prefix=settings.api_prefix,
                tags=["On-Call Optimizer"],
            )
            logger.info("oncall_optimizer_initialized")
        except Exception as e:
            logger.warning("oncall_optimizer_init_failed", error=str(e))

    # ── Phase 25: Alert Correlation Rule Engine ──────────────────
    if settings.alert_correlation_rules_enabled:
        try:
            from shieldops.api.routes import alert_correlation_rules as acr_route
            from shieldops.observability.alert_correlation_rules import (
                AlertCorrelationRuleEngine,
            )

            acr_engine = AlertCorrelationRuleEngine(
                max_rules=settings.alert_correlation_rules_max_rules,
                time_window_seconds=settings.alert_correlation_rules_time_window_seconds,
            )
            acr_route.set_engine(acr_engine)
            app.include_router(
                acr_route.router,
                prefix=settings.api_prefix,
                tags=["Alert Correlation Rules"],
            )
            logger.info("alert_correlation_rules_initialized")
        except Exception as e:
            logger.warning("alert_correlation_rules_init_failed", error=str(e))

    # ── Phase 25: Incident Review Board ──────────────────────────
    if settings.review_board_enabled:
        try:
            from shieldops.api.routes import review_board as rb_route
            from shieldops.incidents.review_board import (
                IncidentReviewBoard,
            )

            rb_board = IncidentReviewBoard(
                max_reviews=settings.review_board_max_reviews,
                action_sla_days=settings.review_board_action_sla_days,
            )
            rb_route.set_board(rb_board)
            app.include_router(
                rb_route.router,
                prefix=settings.api_prefix,
                tags=["Review Board"],
            )
            logger.info("review_board_initialized")
        except Exception as e:
            logger.warning("review_board_init_failed", error=str(e))

    # ── Phase 25: Cloud Commitment Planner ───────────────────────
    if settings.commitment_planner_enabled:
        try:
            from shieldops.api.routes import commitment_planner as cpl_route
            from shieldops.billing.commitment_planner import (
                CloudCommitmentPlanner,
            )

            cpl_planner = CloudCommitmentPlanner(
                max_workloads=settings.commitment_planner_max_workloads,
                min_savings_threshold_pct=settings.commitment_planner_min_savings_threshold_pct,
            )
            cpl_route.set_planner(cpl_planner)
            app.include_router(
                cpl_route.router,
                prefix=settings.api_prefix,
                tags=["Commitment Planner"],
            )
            logger.info("commitment_planner_initialized")
        except Exception as e:
            logger.warning("commitment_planner_init_failed", error=str(e))

    # ── Phase 25: Cost Simulation Engine ─────────────────────────
    if settings.cost_simulator_enabled:
        try:
            from shieldops.api.routes import cost_simulator as csim_route
            from shieldops.billing.cost_simulator import (
                CostSimulationEngine,
            )

            csim_engine = CostSimulationEngine(
                max_scenarios=settings.cost_simulator_max_scenarios,
                budget_breach_threshold_pct=settings.cost_simulator_budget_breach_threshold_pct,
            )
            csim_route.set_engine(csim_engine)
            app.include_router(
                csim_route.router,
                prefix=settings.api_prefix,
                tags=["Cost Simulator"],
            )
            logger.info("cost_simulator_initialized")
        except Exception as e:
            logger.warning("cost_simulator_init_failed", error=str(e))

    # ── Phase 25: FinOps Maturity Scorer ─────────────────────────
    if settings.finops_maturity_enabled:
        try:
            from shieldops.api.routes import finops_maturity as fm_route
            from shieldops.billing.finops_maturity import (
                FinOpsMaturityScorer,
            )

            fm_scorer = FinOpsMaturityScorer(
                max_assessments=settings.finops_maturity_max_assessments,
                target_level=settings.finops_maturity_target_level,
            )
            fm_route.set_scorer(fm_scorer)
            app.include_router(
                fm_route.router,
                prefix=settings.api_prefix,
                tags=["FinOps Maturity"],
            )
            logger.info("finops_maturity_initialized")
        except Exception as e:
            logger.warning("finops_maturity_init_failed", error=str(e))

    # ── Phase 25: Change Failure Rate Tracker ────────────────────
    if settings.change_failure_tracker_enabled:
        try:
            from shieldops.api.routes import change_failure_tracker as cft_route
            from shieldops.changes.change_failure_tracker import (
                ChangeFailureRateTracker,
            )

            cft_tracker = ChangeFailureRateTracker(
                max_deployments=settings.change_failure_tracker_max_deployments,
                trend_window_days=settings.change_failure_tracker_trend_window_days,
            )
            cft_route.set_tracker(cft_tracker)
            app.include_router(
                cft_route.router,
                prefix=settings.api_prefix,
                tags=["Change Failure Tracker"],
            )
            logger.info("change_failure_tracker_initialized")
        except Exception as e:
            logger.warning("change_failure_tracker_init_failed", error=str(e))

    # ── Phase 25: Toil Automation Recommender ────────────────────
    if settings.toil_recommender_enabled:
        try:
            from shieldops.api.routes import toil_recommender as trec_route
            from shieldops.operations.toil_recommender import (
                ToilAutomationRecommender,
            )

            trec_recommender = ToilAutomationRecommender(
                max_patterns=settings.toil_recommender_max_patterns,
                min_roi_multiplier=settings.toil_recommender_min_roi_multiplier,
            )
            trec_route.set_recommender(trec_recommender)
            app.include_router(
                trec_route.router,
                prefix=settings.api_prefix,
                tags=["Toil Recommender"],
            )
            logger.info("toil_recommender_initialized")
        except Exception as e:
            logger.warning("toil_recommender_init_failed", error=str(e))

    # ── Phase 25: SLI Calculation Pipeline ───────────────────────
    if settings.sli_pipeline_enabled:
        try:
            from shieldops.api.routes import sli_pipeline as sli_route
            from shieldops.sla.sli_pipeline import (
                SLICalculationPipeline,
            )

            sli_pipe = SLICalculationPipeline(
                max_definitions=settings.sli_pipeline_max_definitions,
                data_retention_hours=settings.sli_pipeline_data_retention_hours,
            )
            sli_route.set_pipeline(sli_pipe)
            app.include_router(
                sli_route.router,
                prefix=settings.api_prefix,
                tags=["SLI Pipeline"],
            )
            logger.info("sli_pipeline_initialized")
        except Exception as e:
            logger.warning("sli_pipeline_init_failed", error=str(e))

    # ── Phase 26: Platform Intelligence & Operational Excellence ──

    if settings.deployment_cadence_enabled:
        try:
            from shieldops.analytics.deployment_cadence import (
                DeploymentCadenceAnalyzer,
            )
            from shieldops.api.routes import (
                deployment_cadence as dca_route,
            )

            dca = DeploymentCadenceAnalyzer(
                max_deployments=settings.deployment_cadence_max_deployments,
            )
            dca_route.set_analyzer(dca)
            app.include_router(
                dca_route.router,
                prefix=settings.api_prefix,
                tags=["Deployment Cadence"],
            )
            logger.info("deployment_cadence_initialized")
        except Exception as e:
            logger.warning("deployment_cadence_init_failed", error=str(e))

    if settings.metric_baseline_enabled:
        try:
            from shieldops.api.routes import (
                metric_baseline as mb_route,
            )
            from shieldops.observability.metric_baseline import (
                MetricBaselineManager,
            )

            mb = MetricBaselineManager(
                max_baselines=settings.metric_baseline_max_baselines,
                deviation_threshold_pct=settings.metric_baseline_deviation_threshold_pct,
            )
            mb_route.set_manager(mb)
            app.include_router(
                mb_route.router,
                prefix=settings.api_prefix,
                tags=["Metric Baseline"],
            )
            logger.info("metric_baseline_initialized")
        except Exception as e:
            logger.warning("metric_baseline_init_failed", error=str(e))

    if settings.incident_timeline_enabled:
        try:
            from shieldops.api.routes import (
                incident_timeline as itl_route,
            )
            from shieldops.incidents.incident_timeline import (
                IncidentTimelineAnalyzer,
            )

            itl = IncidentTimelineAnalyzer(
                max_entries=settings.incident_timeline_max_entries,
                target_resolution_minutes=settings.incident_timeline_target_resolution_minutes,
            )
            itl_route.set_analyzer(itl)
            app.include_router(
                itl_route.router,
                prefix=settings.api_prefix,
                tags=["Incident Timeline"],
            )
            logger.info("incident_timeline_initialized")
        except Exception as e:
            logger.warning("incident_timeline_init_failed", error=str(e))

    if settings.service_health_agg_enabled:
        try:
            from shieldops.api.routes import (
                service_health_agg as sha_route,
            )
            from shieldops.topology.service_health_agg import (
                ServiceHealthAggregator,
            )

            sha = ServiceHealthAggregator(
                max_signals=settings.service_health_agg_max_signals,
                health_threshold=settings.service_health_agg_health_threshold,
            )
            sha_route.set_aggregator(sha)
            app.include_router(
                sha_route.router,
                prefix=settings.api_prefix,
                tags=["Service Health Aggregator"],
            )
            logger.info("service_health_agg_initialized")
        except Exception as e:
            logger.warning("service_health_agg_init_failed", error=str(e))

    if settings.alert_fatigue_enabled:
        try:
            from shieldops.api.routes import (
                alert_fatigue as af_route,
            )
            from shieldops.observability.alert_fatigue import (
                AlertFatigueScorer,
            )

            af = AlertFatigueScorer(
                max_records=settings.alert_fatigue_max_records,
                fatigue_threshold=settings.alert_fatigue_threshold,
            )
            af_route.set_scorer(af)
            app.include_router(
                af_route.router,
                prefix=settings.api_prefix,
                tags=["Alert Fatigue"],
            )
            logger.info("alert_fatigue_initialized")
        except Exception as e:
            logger.warning("alert_fatigue_init_failed", error=str(e))

    if settings.change_window_enabled:
        try:
            from shieldops.api.routes import (
                change_window as cw_route,
            )
            from shieldops.changes.change_window import (
                ChangeWindowOptimizer,
            )

            cw = ChangeWindowOptimizer(
                max_records=settings.change_window_max_records,
                min_success_rate=settings.change_window_min_success_rate,
            )
            cw_route.set_optimizer(cw)
            app.include_router(
                cw_route.router,
                prefix=settings.api_prefix,
                tags=["Change Window"],
            )
            logger.info("change_window_initialized")
        except Exception as e:
            logger.warning("change_window_init_failed", error=str(e))

    if settings.resource_waste_enabled:
        try:
            from shieldops.api.routes import (
                resource_waste as rw_route,
            )
            from shieldops.billing.resource_waste import (
                ResourceWasteDetector,
            )

            rw = ResourceWasteDetector(
                max_records=settings.resource_waste_max_records,
                idle_threshold_pct=settings.resource_waste_idle_threshold_pct,
            )
            rw_route.set_detector(rw)
            app.include_router(
                rw_route.router,
                prefix=settings.api_prefix,
                tags=["Resource Waste"],
            )
            logger.info("resource_waste_initialized")
        except Exception as e:
            logger.warning("resource_waste_init_failed", error=str(e))

    if settings.evidence_chain_enabled:
        try:
            from shieldops.api.routes import (
                evidence_chain as ech_route,
            )
            from shieldops.compliance.evidence_chain import (
                ComplianceEvidenceChain,
            )

            ech = ComplianceEvidenceChain(
                max_chains=settings.evidence_chain_max_chains,
                max_items_per_chain=settings.evidence_chain_max_items_per_chain,
            )
            ech_route.set_chain_manager(ech)
            app.include_router(
                ech_route.router,
                prefix=settings.api_prefix,
                tags=["Evidence Chain"],
            )
            logger.info("evidence_chain_initialized")
        except Exception as e:
            logger.warning("evidence_chain_init_failed", error=str(e))

    if settings.dependency_update_planner_enabled:
        try:
            from shieldops.api.routes import (
                dependency_update_planner as dup_route,
            )
            from shieldops.topology.dependency_update_planner import (
                DependencyUpdatePlanner,
            )

            dup = DependencyUpdatePlanner(
                max_updates=settings.dependency_update_planner_max_updates,
                max_risk_threshold=settings.dependency_update_planner_max_risk_threshold,
            )
            dup_route.set_planner(dup)
            app.include_router(
                dup_route.router,
                prefix=settings.api_prefix,
                tags=["Dependency Update Planner"],
            )
            logger.info("dependency_update_planner_initialized")
        except Exception as e:
            logger.warning(
                "dependency_update_planner_init_failed",
                error=str(e),
            )

    if settings.capacity_forecast_engine_enabled:
        try:
            from shieldops.analytics.capacity_forecast_engine import (
                CapacityForecastEngine,
            )
            from shieldops.api.routes import (
                capacity_forecast_engine as cfe_route,
            )

            cfe = CapacityForecastEngine(
                max_data_points=settings.capacity_forecast_engine_max_data_points,
                headroom_target_pct=settings.capacity_forecast_engine_headroom_target_pct,
            )
            cfe_route.set_engine(cfe)
            app.include_router(
                cfe_route.router,
                prefix=settings.api_prefix,
                tags=["Capacity Forecast Engine"],
            )
            logger.info("capacity_forecast_engine_initialized")
        except Exception as e:
            logger.warning(
                "capacity_forecast_engine_init_failed",
                error=str(e),
            )

    if settings.runbook_versioner_enabled:
        try:
            from shieldops.api.routes import (
                runbook_versioner as rv_route,
            )
            from shieldops.operations.runbook_versioner import (
                RunbookVersionManager,
            )

            rv = RunbookVersionManager(
                max_versions=settings.runbook_versioner_max_versions,
                stale_age_days=settings.runbook_versioner_stale_age_days,
            )
            rv_route.set_manager(rv)
            app.include_router(
                rv_route.router,
                prefix=settings.api_prefix,
                tags=["Runbook Versioner"],
            )
            logger.info("runbook_versioner_initialized")
        except Exception as e:
            logger.warning("runbook_versioner_init_failed", error=str(e))

    if settings.team_skill_matrix_enabled:
        try:
            from shieldops.api.routes import (
                team_skill_matrix as tsm_route,
            )
            from shieldops.operations.team_skill_matrix import (
                TeamSkillMatrix,
            )

            tsm = TeamSkillMatrix(
                max_entries=settings.team_skill_matrix_max_entries,
                min_coverage_per_domain=settings.team_skill_matrix_min_coverage_per_domain,
            )
            tsm_route.set_matrix(tsm)
            app.include_router(
                tsm_route.router,
                prefix=settings.api_prefix,
                tags=["Team Skill Matrix"],
            )
            logger.info("team_skill_matrix_initialized")
        except Exception as e:
            logger.warning("team_skill_matrix_init_failed", error=str(e))

    # ── Phase 27: Advanced Reliability & Cost Governance ─────────

    if settings.error_budget_policy_enabled:
        try:
            from shieldops.api.routes import (
                error_budget_policy as ebp_route,
            )
            from shieldops.sla.error_budget_policy import (
                ErrorBudgetPolicyEngine,
            )

            ebp = ErrorBudgetPolicyEngine(
                max_policies=settings.error_budget_policy_max_policies,
                warning_threshold_pct=settings.error_budget_policy_warning_threshold_pct,
            )
            ebp_route.set_engine(ebp)
            app.include_router(
                ebp_route.router,
                prefix=settings.api_prefix,
                tags=["Error Budget Policy"],
            )
            logger.info("error_budget_policy_initialized")
        except Exception as e:
            logger.warning("error_budget_policy_init_failed", error=str(e))

    if settings.reliability_target_enabled:
        try:
            from shieldops.api.routes import (
                reliability_target as rta_route,
            )
            from shieldops.sla.reliability_target import (
                ReliabilityTargetAdvisor,
            )

            rta = ReliabilityTargetAdvisor(
                max_targets=settings.reliability_target_max_targets,
                default_target_pct=settings.reliability_target_default_target_pct,
            )
            rta_route.set_advisor(rta)
            app.include_router(
                rta_route.router,
                prefix=settings.api_prefix,
                tags=["Reliability Target"],
            )
            logger.info("reliability_target_initialized")
        except Exception as e:
            logger.warning("reliability_target_init_failed", error=str(e))

    if settings.severity_calibrator_enabled:
        try:
            from shieldops.api.routes import (
                severity_calibrator as scal_route,
            )
            from shieldops.incidents.severity_calibrator import (
                IncidentSeverityCalibrator,
            )

            scal = IncidentSeverityCalibrator(
                max_records=settings.severity_calibrator_max_records,
                accuracy_target_pct=settings.severity_calibrator_accuracy_target_pct,
            )
            scal_route.set_calibrator(scal)
            app.include_router(
                scal_route.router,
                prefix=settings.api_prefix,
                tags=["Severity Calibrator"],
            )
            logger.info("severity_calibrator_initialized")
        except Exception as e:
            logger.warning("severity_calibrator_init_failed", error=str(e))

    if settings.dependency_mapper_enabled:
        try:
            from shieldops.api.routes import (
                dependency_mapper as dm_route,
            )
            from shieldops.topology.dependency_mapper import (
                ServiceDependencyMapper,
            )

            dm = ServiceDependencyMapper(
                max_edges=settings.dependency_mapper_max_edges,
                max_chain_depth=settings.dependency_mapper_max_chain_depth,
            )
            dm_route.set_mapper(dm)
            app.include_router(
                dm_route.router,
                prefix=settings.api_prefix,
                tags=["Dependency Mapper"],
            )
            logger.info("dependency_mapper_initialized")
        except Exception as e:
            logger.warning("dependency_mapper_init_failed", error=str(e))

    if settings.alert_rule_linter_enabled:
        try:
            from shieldops.api.routes import (
                alert_rule_linter as arl_route,
            )
            from shieldops.observability.alert_rule_linter import (
                AlertRuleLinter,
            )

            arl = AlertRuleLinter(
                max_rules=settings.alert_rule_linter_max_rules,
                min_quality_score=settings.alert_rule_linter_min_quality_score,
            )
            arl_route.set_linter(arl)
            app.include_router(
                arl_route.router,
                prefix=settings.api_prefix,
                tags=["Alert Rule Linter"],
            )
            logger.info("alert_rule_linter_initialized")
        except Exception as e:
            logger.warning("alert_rule_linter_init_failed", error=str(e))

    if settings.deployment_gate_enabled:
        try:
            from shieldops.api.routes import (
                deployment_gate as dg_route,
            )
            from shieldops.changes.deployment_gate import (
                DeploymentApprovalGate,
            )

            dg = DeploymentApprovalGate(
                max_gates=settings.deployment_gate_max_gates,
                gate_expiry_hours=settings.deployment_gate_expiry_hours,
            )
            dg_route.set_gate_manager(dg)
            app.include_router(
                dg_route.router,
                prefix=settings.api_prefix,
                tags=["Deployment Gate"],
            )
            logger.info("deployment_gate_initialized")
        except Exception as e:
            logger.warning("deployment_gate_init_failed", error=str(e))

    if settings.billing_reconciler_enabled:
        try:
            from shieldops.api.routes import (
                billing_reconciler as br_route,
            )
            from shieldops.billing.billing_reconciler import (
                CloudBillingReconciler,
            )

            br = CloudBillingReconciler(
                max_records=settings.billing_reconciler_max_records,
                discrepancy_threshold_pct=settings.billing_reconciler_discrepancy_threshold_pct,
            )
            br_route.set_reconciler(br)
            app.include_router(
                br_route.router,
                prefix=settings.api_prefix,
                tags=["Billing Reconciler"],
            )
            logger.info("billing_reconciler_initialized")
        except Exception as e:
            logger.warning("billing_reconciler_init_failed", error=str(e))

    if settings.chargeback_engine_enabled:
        try:
            from shieldops.api.routes import (
                chargeback_engine as cbe_route,
            )
            from shieldops.billing.chargeback_engine import (
                CostChargebackEngine,
            )

            cbe = CostChargebackEngine(
                max_records=settings.chargeback_engine_max_records,
                unallocated_threshold_pct=settings.chargeback_engine_unallocated_threshold_pct,
            )
            cbe_route.set_engine(cbe)
            app.include_router(
                cbe_route.router,
                prefix=settings.api_prefix,
                tags=["Chargeback Engine"],
            )
            logger.info("chargeback_engine_initialized")
        except Exception as e:
            logger.warning("chargeback_engine_init_failed", error=str(e))

    if settings.compliance_drift_enabled:
        try:
            from shieldops.api.routes import (
                compliance_drift as cdrift_route,
            )
            from shieldops.compliance.compliance_drift import (
                ComplianceDriftDetector,
            )

            cdrift = ComplianceDriftDetector(
                max_records=settings.compliance_drift_max_records,
                max_drift_rate_pct=settings.compliance_drift_max_drift_rate_pct,
            )
            cdrift_route.set_detector(cdrift)
            app.include_router(
                cdrift_route.router,
                prefix=settings.api_prefix,
                tags=["Compliance Drift"],
            )
            logger.info("compliance_drift_initialized")
        except Exception as e:
            logger.warning("compliance_drift_init_failed", error=str(e))

    if settings.comm_planner_enabled:
        try:
            from shieldops.api.routes import (
                comm_planner as cpl2_route,
            )
            from shieldops.incidents.comm_planner import (
                IncidentCommPlanner,
            )

            cpl2 = IncidentCommPlanner(
                max_plans=settings.comm_planner_max_plans,
                max_overdue_minutes=settings.comm_planner_max_overdue_minutes,
            )
            cpl2_route.set_planner(cpl2)
            app.include_router(
                cpl2_route.router,
                prefix=settings.api_prefix,
                tags=["Comm Planner"],
            )
            logger.info("comm_planner_initialized")
        except Exception as e:
            logger.warning("comm_planner_init_failed", error=str(e))

    if settings.infra_drift_reconciler_enabled:
        try:
            from shieldops.api.routes import (
                infra_drift_reconciler as idr_route,
            )
            from shieldops.operations.infra_drift_reconciler import (
                InfraDriftReconciler,
            )

            idr = InfraDriftReconciler(
                max_drifts=settings.infra_drift_reconciler_max_drifts,
                auto_reconcile_enabled=settings.infra_drift_reconciler_auto_reconcile_enabled,
            )
            idr_route.set_reconciler(idr)
            app.include_router(
                idr_route.router,
                prefix=settings.api_prefix,
                tags=["Infra Drift Reconciler"],
            )
            logger.info("infra_drift_reconciler_initialized")
        except Exception as e:
            logger.warning(
                "infra_drift_reconciler_init_failed",
                error=str(e),
            )

    if settings.service_maturity_enabled:
        try:
            from shieldops.api.routes import (
                service_maturity as sm_route,
            )
            from shieldops.topology.service_maturity import (
                ServiceMaturityModel,
            )

            sm = ServiceMaturityModel(
                max_assessments=settings.service_maturity_max_assessments,
                target_maturity_level=settings.service_maturity_target_level,
            )
            sm_route.set_model(sm)
            app.include_router(
                sm_route.router,
                prefix=settings.api_prefix,
                tags=["Service Maturity"],
            )
            logger.info("service_maturity_initialized")
        except Exception as e:
            logger.warning("service_maturity_init_failed", error=str(e))

    # Phase 28: Capacity Right-Timing Advisor
    if settings.capacity_right_timing_enabled:
        try:
            from shieldops.api.routes import (
                capacity_right_timing as crt_mod,
            )
            from shieldops.operations.capacity_right_timing import (
                CapacityRightTimingAdvisor,
            )

            crt = CapacityRightTimingAdvisor(
                max_records=settings.capacity_right_timing_max_records,
                lookahead_hours=settings.capacity_right_timing_lookahead_hours,
            )
            crt_mod.set_engine(crt)
            app.include_router(
                crt_mod.crt_route,
                prefix=settings.api_prefix,
                tags=["Capacity Right-Timing"],
            )
            logger.info("capacity_right_timing_initialized")
        except Exception as e:
            logger.warning("capacity_right_timing_init_failed", error=str(e))

    # Phase 28: Predictive Outage Detector
    if settings.outage_predictor_enabled:
        try:
            from shieldops.api.routes import (
                outage_predictor as op_mod,
            )
            from shieldops.observability.outage_predictor import (
                PredictiveOutageDetector,
            )

            op = PredictiveOutageDetector(
                max_records=settings.outage_predictor_max_records,
                composite_threshold=settings.outage_predictor_composite_threshold,
            )
            op_mod.set_engine(op)
            app.include_router(
                op_mod.op_route,
                prefix=settings.api_prefix,
                tags=["Outage Predictor"],
            )
            logger.info("outage_predictor_initialized")
        except Exception as e:
            logger.warning("outage_predictor_init_failed", error=str(e))

    # Phase 28: Incident Impact Quantifier
    if settings.impact_quantifier_enabled:
        try:
            from shieldops.api.routes import (
                impact_quantifier as iq_mod,
            )
            from shieldops.incidents.impact_quantifier import (
                IncidentImpactQuantifier,
            )

            iq = IncidentImpactQuantifier(
                max_assessments=settings.impact_quantifier_max_assessments,
                default_hourly_rate_usd=settings.impact_quantifier_default_hourly_rate_usd,
            )
            iq_mod.set_engine(iq)
            app.include_router(
                iq_mod.iq_route,
                prefix=settings.api_prefix,
                tags=["Impact Quantifier"],
            )
            logger.info("impact_quantifier_initialized")
        except Exception as e:
            logger.warning("impact_quantifier_init_failed", error=str(e))

    # Phase 28: Policy Violation Tracker
    if settings.policy_violation_tracker_enabled:
        try:
            from shieldops.api.routes import (
                policy_violation_tracker as pvt_mod,
            )
            from shieldops.compliance.policy_violation_tracker import (
                PolicyViolationTracker,
            )

            pvt = PolicyViolationTracker(
                max_records=settings.policy_violation_tracker_max_records,
                repeat_threshold=settings.policy_violation_tracker_repeat_threshold,
            )
            pvt_mod.set_engine(pvt)
            app.include_router(
                pvt_mod.pvt_route,
                prefix=settings.api_prefix,
                tags=["Policy Violation Tracker"],
            )
            logger.info("policy_violation_tracker_initialized")
        except Exception as e:
            logger.warning("policy_violation_tracker_init_failed", error=str(e))

    # Phase 28: Deployment Health Scorer
    if settings.deploy_health_scorer_enabled:
        try:
            from shieldops.api.routes import (
                deploy_health_scorer as dhs_mod,
            )
            from shieldops.changes.deploy_health_scorer import (
                DeploymentHealthScorer,
            )

            dhs = DeploymentHealthScorer(
                max_records=settings.deploy_health_scorer_max_records,
                failing_threshold=settings.deploy_health_scorer_failing_threshold,
            )
            dhs_mod.set_engine(dhs)
            app.include_router(
                dhs_mod.dhs_route,
                prefix=settings.api_prefix,
                tags=["Deploy Health Scorer"],
            )
            logger.info("deploy_health_scorer_initialized")
        except Exception as e:
            logger.warning("deploy_health_scorer_init_failed", error=str(e))

    # Phase 28: Runbook Gap Analyzer
    if settings.runbook_gap_analyzer_enabled:
        try:
            from shieldops.api.routes import (
                runbook_gap_analyzer as rga_mod,
            )
            from shieldops.operations.runbook_gap_analyzer import (
                RunbookGapAnalyzer,
            )

            rga = RunbookGapAnalyzer(
                max_gaps=settings.runbook_gap_analyzer_max_gaps,
                critical_incident_threshold=settings.runbook_gap_analyzer_critical_incident_threshold,
            )
            rga_mod.set_engine(rga)
            app.include_router(
                rga_mod.rga_route,
                prefix=settings.api_prefix,
                tags=["Runbook Gap Analyzer"],
            )
            logger.info("runbook_gap_analyzer_initialized")
        except Exception as e:
            logger.warning("runbook_gap_analyzer_init_failed", error=str(e))

    # Phase 28: Credential Expiry Forecaster
    if settings.credential_expiry_forecaster_enabled:
        try:
            from shieldops.api.routes import (
                credential_expiry_forecaster as cef_mod,
            )
            from shieldops.security.credential_expiry_forecaster import (
                CredentialExpiryForecaster,
            )

            cef = CredentialExpiryForecaster(
                max_records=settings.credential_expiry_forecaster_max_records,
                warning_days=settings.credential_expiry_forecaster_warning_days,
            )
            cef_mod.set_engine(cef)
            app.include_router(
                cef_mod.cef_route,
                prefix=settings.api_prefix,
                tags=["Credential Expiry Forecaster"],
            )
            logger.info("credential_expiry_forecaster_initialized")
        except Exception as e:
            logger.warning("credential_expiry_forecaster_init_failed", error=str(e))

    # Phase 28: On-Call Workload Balancer
    if settings.oncall_workload_balancer_enabled:
        try:
            from shieldops.api.routes import (
                oncall_workload_balancer as owb_mod,
            )
            from shieldops.incidents.oncall_workload_balancer import (
                OnCallWorkloadBalancer,
            )

            owb = OnCallWorkloadBalancer(
                max_records=settings.oncall_workload_balancer_max_records,
                imbalance_threshold_pct=settings.oncall_workload_balancer_imbalance_threshold_pct,
            )
            owb_mod.set_engine(owb)
            app.include_router(
                owb_mod.owb_route,
                prefix=settings.api_prefix,
                tags=["On-Call Workload Balancer"],
            )
            logger.info("oncall_workload_balancer_initialized")
        except Exception as e:
            logger.warning("oncall_workload_balancer_init_failed", error=str(e))

    # Phase 28: Cost Anomaly Predictor
    if settings.cost_anomaly_predictor_enabled:
        try:
            from shieldops.api.routes import (
                cost_anomaly_predictor as cap_mod,
            )
            from shieldops.billing.cost_anomaly_predictor import (
                CostAnomalyPredictor,
            )

            cap = CostAnomalyPredictor(
                max_records=settings.cost_anomaly_predictor_max_records,
                spike_threshold_usd=settings.cost_anomaly_predictor_spike_threshold_usd,
            )
            cap_mod.set_engine(cap)
            app.include_router(
                cap_mod.cap_route,
                prefix=settings.api_prefix,
                tags=["Cost Anomaly Predictor"],
            )
            logger.info("cost_anomaly_predictor_initialized")
        except Exception as e:
            logger.warning("cost_anomaly_predictor_init_failed", error=str(e))

    # Phase 28: Compliance Evidence Scheduler
    if settings.evidence_scheduler_enabled:
        try:
            from shieldops.api.routes import (
                evidence_scheduler as es_mod,
            )
            from shieldops.compliance.evidence_scheduler import (
                ComplianceEvidenceScheduler,
            )

            es = ComplianceEvidenceScheduler(
                max_schedules=settings.evidence_scheduler_max_schedules,
                overdue_grace_days=settings.evidence_scheduler_overdue_grace_days,
            )
            es_mod.set_engine(es)
            app.include_router(
                es_mod.es_route,
                prefix=settings.api_prefix,
                tags=["Evidence Scheduler"],
            )
            logger.info("evidence_scheduler_initialized")
        except Exception as e:
            logger.warning("evidence_scheduler_init_failed", error=str(e))

    # Phase 28: API Latency Budget Tracker
    if settings.latency_budget_tracker_enabled:
        try:
            from shieldops.analytics.latency_budget_tracker import (
                LatencyBudgetTracker,
            )
            from shieldops.api.routes import (
                latency_budget_tracker as lbt_mod,
            )

            lbt = LatencyBudgetTracker(
                max_records=settings.latency_budget_tracker_max_records,
                chronic_violation_threshold=settings.latency_budget_tracker_chronic_violation_threshold,
            )
            lbt_mod.set_engine(lbt)
            app.include_router(
                lbt_mod.lbt_route,
                prefix=settings.api_prefix,
                tags=["Latency Budget Tracker"],
            )
            logger.info("latency_budget_tracker_initialized")
        except Exception as e:
            logger.warning("latency_budget_tracker_init_failed", error=str(e))

    # Phase 28: Change Conflict Detector
    if settings.change_conflict_detector_enabled:
        try:
            from shieldops.api.routes import (
                change_conflict_detector as ccd_mod,
            )
            from shieldops.changes.change_conflict_detector import (
                ChangeConflictDetector,
            )

            ccd = ChangeConflictDetector(
                max_records=settings.change_conflict_detector_max_records,
                lookahead_hours=settings.change_conflict_detector_lookahead_hours,
            )
            ccd_mod.set_engine(ccd)
            app.include_router(
                ccd_mod.ccd_route,
                prefix=settings.api_prefix,
                tags=["Change Conflict Detector"],
            )
            logger.info("change_conflict_detector_initialized")
        except Exception as e:
            logger.warning("change_conflict_detector_init_failed", error=str(e))

    # ── Phase 29 ────────────────────────────────────────────────

    if settings.duration_predictor_enabled:
        try:
            from shieldops.api.routes import (
                duration_predictor as dp_mod,
            )
            from shieldops.incidents.duration_predictor import (
                IncidentDurationPredictor,
            )

            dp = IncidentDurationPredictor(
                max_records=settings.duration_predictor_max_records,
                accuracy_target_pct=settings.duration_predictor_accuracy_target_pct,
            )
            dp_mod.set_engine(dp)
            app.include_router(
                dp_mod.dp_route,
                prefix=settings.api_prefix,
                tags=["Duration Predictor"],
            )
            logger.info("duration_predictor_initialized")
        except Exception as e:
            logger.warning("duration_predictor_init_failed", error=str(e))

    if settings.resource_exhaustion_enabled:
        try:
            from shieldops.analytics.resource_exhaustion import (
                ResourceExhaustionForecaster,
            )
            from shieldops.api.routes import (
                resource_exhaustion as rex_mod,
            )

            rex = ResourceExhaustionForecaster(
                max_records=settings.resource_exhaustion_max_records,
                default_critical_hours=settings.resource_exhaustion_default_critical_hours,
            )
            rex_mod.set_engine(rex)
            app.include_router(
                rex_mod.rex_route,
                prefix=settings.api_prefix,
                tags=["Resource Exhaustion"],
            )
            logger.info("resource_exhaustion_initialized")
        except Exception as e:
            logger.warning("resource_exhaustion_init_failed", error=str(e))

    if settings.alert_storm_correlator_enabled:
        try:
            from shieldops.api.routes import (
                alert_storm_correlator as asc_mod,
            )
            from shieldops.observability.alert_storm_correlator import (
                AlertStormCorrelator,
            )

            asc = AlertStormCorrelator(
                max_records=settings.alert_storm_correlator_max_records,
                storm_window_seconds=settings.alert_storm_correlator_storm_window_seconds,
            )
            asc_mod.set_engine(asc)
            app.include_router(
                asc_mod.asc_route,
                prefix=settings.api_prefix,
                tags=["Alert Storm Correlator"],
            )
            logger.info("alert_storm_correlator_initialized")
        except Exception as e:
            logger.warning("alert_storm_correlator_init_failed", error=str(e))

    if settings.canary_analyzer_enabled:
        try:
            from shieldops.api.routes import (
                canary_analyzer as ca_mod,
            )
            from shieldops.changes.canary_analyzer import (
                DeploymentCanaryAnalyzer,
            )

            ca = DeploymentCanaryAnalyzer(
                max_records=settings.canary_analyzer_max_records,
                deviation_threshold_pct=settings.canary_analyzer_deviation_threshold_pct,
            )
            ca_mod.set_engine(ca)
            app.include_router(
                ca_mod.ca_route,
                prefix=settings.api_prefix,
                tags=["Canary Analyzer"],
            )
            logger.info("canary_analyzer_initialized")
        except Exception as e:
            logger.warning("canary_analyzer_init_failed", error=str(e))

    if settings.sla_cascader_enabled:
        try:
            from shieldops.api.routes import (
                sla_cascader as sc_mod,
            )
            from shieldops.sla.sla_cascader import (
                ServiceSLACascader,
            )

            sc = ServiceSLACascader(
                max_records=settings.sla_cascader_max_records,
                min_acceptable_sla_pct=settings.sla_cascader_min_acceptable_sla_pct,
            )
            sc_mod.set_cascader(sc)
            app.include_router(
                sc_mod.sc_route,
                prefix=settings.api_prefix,
                tags=["SLA Cascader"],
            )
            logger.info("sla_cascader_initialized")
        except Exception as e:
            logger.warning("sla_cascader_init_failed", error=str(e))

    if settings.handoff_tracker_enabled:
        try:
            from shieldops.api.routes import (
                handoff_tracker as ht_mod,
            )
            from shieldops.incidents.handoff_tracker import (
                IncidentHandoffTracker,
            )

            ht = IncidentHandoffTracker(
                max_records=settings.handoff_tracker_max_records,
                quality_threshold=settings.handoff_tracker_quality_threshold,
            )
            ht_mod.set_tracker(ht)
            app.include_router(
                ht_mod.ht_route,
                prefix=settings.api_prefix,
                tags=["Handoff Tracker"],
            )
            logger.info("handoff_tracker_initialized")
        except Exception as e:
            logger.warning("handoff_tracker_init_failed", error=str(e))

    if settings.unit_economics_enabled:
        try:
            from shieldops.api.routes import (
                unit_economics as ue_mod,
            )
            from shieldops.billing.unit_economics import (
                CostUnitEconomicsEngine,
            )

            ue = CostUnitEconomicsEngine(
                max_records=settings.unit_economics_max_records,
                high_cost_threshold=settings.unit_economics_high_cost_threshold,
            )
            ue_mod.set_engine(ue)
            app.include_router(
                ue_mod.ue_route,
                prefix=settings.api_prefix,
                tags=["Unit Economics"],
            )
            logger.info("unit_economics_initialized")
        except Exception as e:
            logger.warning("unit_economics_init_failed", error=str(e))

    if settings.idle_resource_detector_enabled:
        try:
            from shieldops.api.routes import (
                idle_resource_detector as ird_mod,
            )
            from shieldops.billing.idle_resource_detector import (
                IdleResourceDetector,
            )

            ird = IdleResourceDetector(
                max_records=settings.idle_resource_detector_max_records,
                idle_threshold_pct=settings.idle_resource_detector_idle_threshold_pct,
            )
            ird_mod.set_detector(ird)
            app.include_router(
                ird_mod.ird_route,
                prefix=settings.api_prefix,
                tags=["Idle Resource Detector"],
            )
            logger.info("idle_resource_detector_initialized")
        except Exception as e:
            logger.warning("idle_resource_detector_init_failed", error=str(e))

    if settings.penalty_calculator_enabled:
        try:
            from shieldops.api.routes import (
                penalty_calculator as pc_mod,
            )
            from shieldops.sla.penalty_calculator import (
                SLAPenaltyCalculator,
            )

            pc = SLAPenaltyCalculator(
                max_records=settings.penalty_calculator_max_records,
                default_credit_multiplier=settings.penalty_calculator_default_credit_multiplier,
            )
            pc_mod.set_engine(pc)
            app.include_router(
                pc_mod.pc_route,
                prefix=settings.api_prefix,
                tags=["Penalty Calculator"],
            )
            logger.info("penalty_calculator_initialized")
        except Exception as e:
            logger.warning("penalty_calculator_init_failed", error=str(e))

    if settings.posture_trend_enabled:
        try:
            from shieldops.api.routes import (
                posture_trend as pt_mod,
            )
            from shieldops.security.posture_trend import (
                SecurityPostureTrendAnalyzer,
            )

            pt = SecurityPostureTrendAnalyzer(
                max_records=settings.posture_trend_max_records,
                regression_threshold=settings.posture_trend_regression_threshold,
            )
            pt_mod.set_engine(pt)
            app.include_router(
                pt_mod.pt_route,
                prefix=settings.api_prefix,
                tags=["Posture Trend"],
            )
            logger.info("posture_trend_initialized")
        except Exception as e:
            logger.warning("posture_trend_init_failed", error=str(e))

    if settings.evidence_freshness_enabled:
        try:
            from shieldops.api.routes import (
                evidence_freshness as ef_mod,
            )
            from shieldops.compliance.evidence_freshness import (
                EvidenceFreshnessMonitor,
            )

            ef = EvidenceFreshnessMonitor(
                max_records=settings.evidence_freshness_max_records,
                stale_days=settings.evidence_freshness_stale_days,
            )
            ef_mod.set_engine(ef)
            app.include_router(
                ef_mod.ef_route,
                prefix=settings.api_prefix,
                tags=["Evidence Freshness"],
            )
            logger.info("evidence_freshness_initialized")
        except Exception as e:
            logger.warning("evidence_freshness_init_failed", error=str(e))

    if settings.access_anomaly_enabled:
        try:
            from shieldops.api.routes import (
                access_anomaly as aa_mod,
            )
            from shieldops.security.access_anomaly import (
                AccessAnomalyDetector,
            )

            aa = AccessAnomalyDetector(
                max_records=settings.access_anomaly_max_records,
                threat_threshold=settings.access_anomaly_threat_threshold,
            )
            aa_mod.set_engine(aa)
            app.include_router(
                aa_mod.aa_route,
                prefix=settings.api_prefix,
                tags=["Access Anomaly"],
            )
            logger.info("access_anomaly_initialized")
        except Exception as e:
            logger.warning("access_anomaly_init_failed", error=str(e))

    # ── Phase 30 ────────────────────────────────────────────────

    if settings.response_advisor_enabled:
        try:
            from shieldops.api.routes import (
                response_advisor as rad_mod,
            )
            from shieldops.incidents.response_advisor import (
                IncidentResponseAdvisor,
            )

            rad = IncidentResponseAdvisor(
                max_records=settings.response_advisor_max_records,
                confidence_threshold=settings.response_advisor_confidence_threshold,
            )
            rad_mod.set_engine(rad)
            app.include_router(
                rad_mod.rad_route,
                prefix=settings.api_prefix,
                tags=["Response Advisor"],
            )
            logger.info("response_advisor_initialized")
        except Exception as e:
            logger.warning("response_advisor_init_failed", error=str(e))

    if settings.metric_rca_enabled:
        try:
            from shieldops.analytics.metric_rca import (
                MetricRootCauseAnalyzer,
            )
            from shieldops.api.routes import (
                metric_rca as mrc_mod,
            )

            mrc = MetricRootCauseAnalyzer(
                max_records=settings.metric_rca_max_records,
                deviation_threshold_pct=settings.metric_rca_deviation_threshold_pct,
            )
            mrc_mod.set_engine(mrc)
            app.include_router(
                mrc_mod.mrc_route,
                prefix=settings.api_prefix,
                tags=["Metric RCA"],
            )
            logger.info("metric_rca_initialized")
        except Exception as e:
            logger.warning("metric_rca_init_failed", error=str(e))

    if settings.slo_forecast_enabled:
        try:
            from shieldops.api.routes import (
                slo_forecast as sf_mod,
            )
            from shieldops.sla.slo_forecast import (
                SLOComplianceForecaster,
            )

            sf = SLOComplianceForecaster(
                max_records=settings.slo_forecast_max_records,
                risk_threshold_pct=settings.slo_forecast_risk_threshold_pct,
            )
            sf_mod.set_engine(sf)
            app.include_router(
                sf_mod.sf_route,
                prefix=settings.api_prefix,
                tags=["SLO Forecast"],
            )
            logger.info("slo_forecast_initialized")
        except Exception as e:
            logger.warning("slo_forecast_init_failed", error=str(e))

    if settings.remediation_decision_enabled:
        try:
            from shieldops.api.routes import (
                remediation_decision as rde_mod,
            )
            from shieldops.operations.remediation_decision import (
                AutoRemediationDecisionEngine,
            )

            rde = AutoRemediationDecisionEngine(
                max_records=settings.remediation_decision_max_records,
                max_risk_score=settings.remediation_decision_max_risk_score,
            )
            rde_mod.set_engine(rde)
            app.include_router(
                rde_mod.rde_route,
                prefix=settings.api_prefix,
                tags=["Remediation Decision"],
            )
            logger.info("remediation_decision_initialized")
        except Exception as e:
            logger.warning("remediation_decision_init_failed", error=str(e))

    if settings.dependency_lag_enabled:
        try:
            from shieldops.api.routes import (
                dependency_lag as dl_mod,
            )
            from shieldops.topology.dependency_lag import (
                DependencyLagMonitor,
            )

            dl = DependencyLagMonitor(
                max_records=settings.dependency_lag_max_records,
                degradation_threshold_pct=settings.dependency_lag_degradation_threshold_pct,
            )
            dl_mod.set_engine(dl)
            app.include_router(
                dl_mod.dl_route,
                prefix=settings.api_prefix,
                tags=["Dependency Lag"],
            )
            logger.info("dependency_lag_initialized")
        except Exception as e:
            logger.warning("dependency_lag_init_failed", error=str(e))

    if settings.escalation_effectiveness_enabled:
        try:
            from shieldops.api.routes import (
                escalation_effectiveness as ee_mod,
            )
            from shieldops.incidents.escalation_effectiveness import (
                EscalationEffectivenessTracker,
            )

            ee = EscalationEffectivenessTracker(
                max_records=settings.escalation_effectiveness_max_records,
                false_rate_threshold=settings.escalation_effectiveness_false_rate_threshold,
            )
            ee_mod.set_engine(ee)
            app.include_router(
                ee_mod.ee_route,
                prefix=settings.api_prefix,
                tags=["Escalation Effectiveness"],
            )
            logger.info("escalation_effectiveness_initialized")
        except Exception as e:
            logger.warning("escalation_effectiveness_init_failed", error=str(e))

    if settings.discount_optimizer_enabled:
        try:
            from shieldops.api.routes import (
                discount_optimizer as do_mod,
            )
            from shieldops.billing.discount_optimizer import (
                CloudDiscountOptimizer,
            )

            do = CloudDiscountOptimizer(
                max_records=settings.discount_optimizer_max_records,
                min_coverage_pct=settings.discount_optimizer_min_coverage_pct,
            )
            do_mod.set_engine(do)
            app.include_router(
                do_mod.do_route,
                prefix=settings.api_prefix,
                tags=["Discount Optimizer"],
            )
            logger.info("discount_optimizer_initialized")
        except Exception as e:
            logger.warning("discount_optimizer_init_failed", error=str(e))

    if settings.audit_trail_analyzer_enabled:
        try:
            from shieldops.api.routes import (
                audit_trail_analyzer as ata_mod,
            )
            from shieldops.compliance.audit_trail_analyzer import (
                ComplianceAuditTrailAnalyzer,
            )

            ata = ComplianceAuditTrailAnalyzer(
                max_records=settings.audit_trail_analyzer_max_records,
                min_completeness_pct=settings.audit_trail_analyzer_min_completeness_pct,
            )
            ata_mod.set_engine(ata)
            app.include_router(
                ata_mod.ata_route,
                prefix=settings.api_prefix,
                tags=["Audit Trail Analyzer"],
            )
            logger.info("audit_trail_analyzer_initialized")
        except Exception as e:
            logger.warning("audit_trail_analyzer_init_failed", error=str(e))

    if settings.velocity_throttle_enabled:
        try:
            from shieldops.api.routes import (
                velocity_throttle as vt_mod,
            )
            from shieldops.changes.velocity_throttle import (
                ChangeVelocityThrottle,
            )

            vt = ChangeVelocityThrottle(
                max_records=settings.velocity_throttle_max_records,
                max_changes_per_hour=settings.velocity_throttle_max_changes_per_hour,
            )
            vt_mod.set_engine(vt)
            app.include_router(
                vt_mod.vt_route,
                prefix=settings.api_prefix,
                tags=["Velocity Throttle"],
            )
            logger.info("velocity_throttle_initialized")
        except Exception as e:
            logger.warning("velocity_throttle_init_failed", error=str(e))

    if settings.alert_tuning_feedback_enabled:
        try:
            from shieldops.api.routes import (
                alert_tuning_feedback as atf_mod,
            )
            from shieldops.observability.alert_tuning_feedback import (
                AlertTuningFeedbackLoop,
            )

            atf = AlertTuningFeedbackLoop(
                max_records=settings.alert_tuning_feedback_max_records,
                precision_threshold=settings.alert_tuning_feedback_precision_threshold,
            )
            atf_mod.set_engine(atf)
            app.include_router(
                atf_mod.atf_route,
                prefix=settings.api_prefix,
                tags=["Alert Tuning Feedback"],
            )
            logger.info("alert_tuning_feedback_initialized")
        except Exception as e:
            logger.warning("alert_tuning_feedback_init_failed", error=str(e))

    if settings.knowledge_decay_enabled:
        try:
            from shieldops.api.routes import (
                knowledge_decay as kd_mod,
            )
            from shieldops.knowledge.knowledge_decay import (
                KnowledgeDecayDetector,
            )

            kd = KnowledgeDecayDetector(
                max_records=settings.knowledge_decay_max_records,
                stale_days=settings.knowledge_decay_stale_days,
            )
            kd_mod.set_engine(kd)
            app.include_router(
                kd_mod.kd_route,
                prefix=settings.api_prefix,
                tags=["Knowledge Decay"],
            )
            logger.info("knowledge_decay_initialized")
        except Exception as e:
            logger.warning("knowledge_decay_init_failed", error=str(e))

    if settings.coverage_scorer_enabled:
        try:
            from shieldops.api.routes import (
                coverage_scorer as ocs_mod,
            )
            from shieldops.observability.coverage_scorer import (
                ObservabilityCoverageScorer,
            )

            ocs = ObservabilityCoverageScorer(
                max_records=settings.coverage_scorer_max_records,
                min_coverage_pct=settings.coverage_scorer_min_coverage_pct,
            )
            ocs_mod.set_engine(ocs)
            app.include_router(
                ocs_mod.ocs_route,
                prefix=settings.api_prefix,
                tags=["Observability Coverage"],
            )
            logger.info("coverage_scorer_initialized")
        except Exception as e:
            logger.warning("coverage_scorer_init_failed", error=str(e))

    if settings.cardinality_manager_enabled:
        try:
            from shieldops.api.routes import (
                cardinality_manager as cm_mod,
            )
            from shieldops.observability.cardinality_manager import (
                MetricCardinalityManager,
            )

            cm_engine = MetricCardinalityManager(
                max_records=settings.cardinality_manager_max_records,
                max_cardinality_threshold=settings.cardinality_manager_max_cardinality_threshold,
            )
            cm_mod.set_engine(cm_engine)
            app.include_router(
                cm_mod.cm_route,
                prefix=settings.api_prefix,
                tags=["Metric Cardinality"],
            )
            logger.info("cardinality_manager_initialized")
        except Exception as e:
            logger.warning("cardinality_manager_init_failed", error=str(e))

    if settings.log_retention_optimizer_enabled:
        try:
            from shieldops.api.routes import (
                log_retention_optimizer as lro_mod,
            )
            from shieldops.observability.log_retention_optimizer import (
                LogRetentionOptimizer,
            )

            lro_engine = LogRetentionOptimizer(
                max_records=settings.log_retention_optimizer_max_records,
                default_retention_days=settings.log_retention_optimizer_default_retention_days,
            )
            lro_mod.set_engine(lro_engine)
            app.include_router(
                lro_mod.lro_route,
                prefix=settings.api_prefix,
                tags=["Log Retention"],
            )
            logger.info("log_retention_optimizer_initialized")
        except Exception as e:
            logger.warning("log_retention_optimizer_init_failed", error=str(e))

    if settings.dashboard_quality_enabled:
        try:
            from shieldops.api.routes import (
                dashboard_quality as dq_mod,
            )
            from shieldops.observability.dashboard_quality import (
                DashboardQualityScorer,
            )

            dq_engine = DashboardQualityScorer(
                max_records=settings.dashboard_quality_max_records,
                min_quality_score=settings.dashboard_quality_min_quality_score,
            )
            dq_mod.set_engine(dq_engine)
            app.include_router(
                dq_mod.dq_route,
                prefix=settings.api_prefix,
                tags=["Dashboard Quality"],
            )
            logger.info("dashboard_quality_initialized")
        except Exception as e:
            logger.warning("dashboard_quality_init_failed", error=str(e))

    if settings.action_tracker_enabled:
        try:
            from shieldops.api.routes import (
                action_tracker as pia_mod,
            )
            from shieldops.incidents.action_tracker import (
                PostIncidentActionTracker,
            )

            pia_engine = PostIncidentActionTracker(
                max_records=settings.action_tracker_max_records,
                overdue_threshold_days=settings.action_tracker_overdue_threshold_days,
            )
            pia_mod.set_engine(pia_engine)
            app.include_router(
                pia_mod.pia_route,
                prefix=settings.api_prefix,
                tags=["Post-Incident Actions"],
            )
            logger.info("action_tracker_initialized")
        except Exception as e:
            logger.warning("action_tracker_init_failed", error=str(e))

    if settings.deployment_confidence_enabled:
        try:
            from shieldops.api.routes import (
                deployment_confidence as dc_mod,
            )
            from shieldops.changes.deployment_confidence import (
                DeploymentConfidenceScorer,
            )

            dc_engine = DeploymentConfidenceScorer(
                max_records=settings.deployment_confidence_max_records,
                min_confidence_score=settings.deployment_confidence_min_confidence_score,
            )
            dc_mod.set_engine(dc_engine)
            app.include_router(
                dc_mod.dc_route,
                prefix=settings.api_prefix,
                tags=["Deployment Confidence"],
            )
            logger.info("deployment_confidence_initialized")
        except Exception as e:
            logger.warning("deployment_confidence_init_failed", error=str(e))

    if settings.reliability_regression_enabled:
        try:
            from shieldops.api.routes import (
                reliability_regression as rr_mod,
            )
            from shieldops.sla.reliability_regression import (
                ReliabilityRegressionDetector,
            )

            rr_engine = ReliabilityRegressionDetector(
                max_records=settings.reliability_regression_max_records,
                deviation_threshold_pct=settings.reliability_regression_deviation_threshold_pct,
            )
            rr_mod.set_engine(rr_engine)
            app.include_router(
                rr_mod.rr_route,
                prefix=settings.api_prefix,
                tags=["Reliability Regression"],
            )
            logger.info("reliability_regression_initialized")
        except Exception as e:
            logger.warning("reliability_regression_init_failed", error=str(e))

    if settings.permission_drift_enabled:
        try:
            from shieldops.api.routes import (
                permission_drift as pd_mod,
            )
            from shieldops.security.permission_drift import (
                PermissionDriftDetector,
            )

            pd_engine = PermissionDriftDetector(
                max_records=settings.permission_drift_max_records,
                unused_days_threshold=settings.permission_drift_unused_days_threshold,
            )
            pd_mod.set_engine(pd_engine)
            app.include_router(
                pd_mod.pd_route,
                prefix=settings.api_prefix,
                tags=["Permission Drift"],
            )
            logger.info("permission_drift_initialized")
        except Exception as e:
            logger.warning("permission_drift_init_failed", error=str(e))

    if settings.flag_lifecycle_enabled:
        try:
            from shieldops.api.routes import (
                flag_lifecycle as fl_mod,
            )
            from shieldops.config.flag_lifecycle import (
                FeatureFlagLifecycleManager,
            )

            fl_engine = FeatureFlagLifecycleManager(
                max_records=settings.flag_lifecycle_max_records,
                stale_days_threshold=settings.flag_lifecycle_stale_days_threshold,
            )
            fl_mod.set_engine(fl_engine)
            app.include_router(
                fl_mod.fl_route,
                prefix=settings.api_prefix,
                tags=["Flag Lifecycle"],
            )
            logger.info("flag_lifecycle_initialized")
        except Exception as e:
            logger.warning("flag_lifecycle_init_failed", error=str(e))

    if settings.api_version_health_enabled:
        try:
            from shieldops.api.routes import (
                api_version_health as avh_mod,
            )
            from shieldops.topology.api_version_health import (
                APIVersionHealthMonitor,
            )

            avh_engine = APIVersionHealthMonitor(
                max_records=settings.api_version_health_max_records,
                sunset_warning_days=settings.api_version_health_sunset_warning_days,
            )
            avh_mod.set_engine(avh_engine)
            app.include_router(
                avh_mod.avh_route,
                prefix=settings.api_prefix,
                tags=["API Version Health"],
            )
            logger.info("api_version_health_initialized")
        except Exception as e:
            logger.warning("api_version_health_init_failed", error=str(e))

    if settings.sre_maturity_enabled:
        try:
            from shieldops.api.routes import (
                sre_maturity as sm_mod,
            )
            from shieldops.operations.sre_maturity import (
                SREMaturityAssessor,
            )

            sm_engine = SREMaturityAssessor(
                max_records=settings.sre_maturity_max_records,
                target_maturity_score=settings.sre_maturity_target_maturity_score,
            )
            sm_mod.set_engine(sm_engine)
            app.include_router(
                sm_mod.sm_route,
                prefix=settings.api_prefix,
                tags=["SRE Maturity"],
            )
            logger.info("sre_maturity_initialized")
        except Exception as e:
            logger.warning("sre_maturity_init_failed", error=str(e))

    if settings.learning_tracker_enabled:
        try:
            from shieldops.api.routes import (
                learning_tracker as lt_mod,
            )
            from shieldops.incidents.learning_tracker import (
                IncidentLearningTracker as LTEngine,
            )

            lt_engine = LTEngine(
                max_records=settings.learning_tracker_max_records,
                min_adoption_rate_pct=settings.learning_tracker_min_adoption_rate_pct,
            )
            lt_mod.set_engine(lt_engine)
            app.include_router(
                lt_mod.lt_route,
                prefix=settings.api_prefix,
                tags=["Incident Learning"],
            )
            logger.info("learning_tracker_initialized")
        except Exception as e:
            logger.warning("learning_tracker_init_failed", error=str(e))

    if settings.cache_effectiveness_enabled:
        try:
            from shieldops.analytics.cache_effectiveness import (
                CacheEffectivenessAnalyzer,
            )
            from shieldops.api.routes import (
                cache_effectiveness as ce_mod,
            )

            ce_engine = CacheEffectivenessAnalyzer(
                max_records=settings.cache_effectiveness_max_records,
                min_hit_rate_pct=settings.cache_effectiveness_min_hit_rate_pct,
            )
            ce_mod.set_engine(ce_engine)
            app.include_router(
                ce_mod.ce_route,
                prefix=settings.api_prefix,
                tags=["Cache Effectiveness"],
            )
            logger.info("cache_effectiveness_initialized")
        except Exception as e:
            logger.warning("cache_effectiveness_init_failed", error=str(e))

    if settings.build_pipeline_enabled:
        try:
            from shieldops.analytics.build_pipeline import (
                BuildPipelineAnalyzer,
            )
            from shieldops.api.routes import (
                build_pipeline as bp_mod,
            )

            bp_engine = BuildPipelineAnalyzer(
                max_records=settings.build_pipeline_max_records,
                min_success_rate_pct=settings.build_pipeline_min_success_rate_pct,
            )
            bp_mod.set_engine(bp_engine)
            app.include_router(
                bp_mod.bp_route,
                prefix=settings.api_prefix,
                tags=["Build Pipeline"],
            )
            logger.info("build_pipeline_initialized")
        except Exception as e:
            logger.warning("build_pipeline_init_failed", error=str(e))

    if settings.review_velocity_enabled:
        try:
            from shieldops.analytics.review_velocity import (
                CodeReviewVelocityTracker,
            )
            from shieldops.api.routes import (
                review_velocity as rv_mod,
            )

            rv_engine = CodeReviewVelocityTracker(
                max_records=settings.review_velocity_max_records,
                max_cycle_hours=settings.review_velocity_max_cycle_hours,
            )
            rv_mod.set_engine(rv_engine)
            app.include_router(
                rv_mod.rv_route,
                prefix=settings.api_prefix,
                tags=["Review Velocity"],
            )
            logger.info("review_velocity_initialized")
        except Exception as e:
            logger.warning("review_velocity_init_failed", error=str(e))

    if settings.dev_environment_enabled:
        try:
            from shieldops.api.routes import (
                dev_environment as deh_mod,
            )
            from shieldops.operations.dev_environment import (
                DevEnvironmentHealthMonitor,
            )

            deh_engine = DevEnvironmentHealthMonitor(
                max_records=settings.dev_environment_max_records,
                max_drift_days=settings.dev_environment_max_drift_days,
            )
            deh_mod.set_engine(deh_engine)
            app.include_router(
                deh_mod.deh_route,
                prefix=settings.api_prefix,
                tags=["Dev Environment"],
            )
            logger.info("dev_environment_initialized")
        except Exception as e:
            logger.warning("dev_environment_init_failed", error=str(e))

    if settings.traffic_pattern_enabled:
        try:
            from shieldops.api.routes import (
                traffic_pattern as tp_mod,
            )
            from shieldops.topology.traffic_pattern import (
                TrafficPatternAnalyzer,
            )

            tp_engine = TrafficPatternAnalyzer(
                max_records=settings.traffic_pattern_max_records,
                error_threshold_pct=settings.traffic_pattern_error_threshold_pct,
            )
            tp_mod.set_engine(tp_engine)
            app.include_router(
                tp_mod.tp_route,
                prefix=settings.api_prefix,
                tags=["Traffic Pattern"],
            )
            logger.info("traffic_pattern_initialized")
        except Exception as e:
            logger.warning("traffic_pattern_init_failed", error=str(e))

    if settings.rate_limit_policy_enabled:
        try:
            from shieldops.api.routes import (
                rate_limit_policy as rlp_mod,
            )
            from shieldops.topology.rate_limit_policy import (
                RateLimitPolicyManager,
            )

            rlp_engine = RateLimitPolicyManager(
                max_records=settings.rate_limit_policy_max_records,
                violation_threshold=settings.rate_limit_policy_violation_threshold,
            )
            rlp_mod.set_engine(rlp_engine)
            app.include_router(
                rlp_mod.rlp_route,
                prefix=settings.api_prefix,
                tags=["Rate Limit Policy"],
            )
            logger.info("rate_limit_policy_initialized")
        except Exception as e:
            logger.warning("rate_limit_policy_init_failed", error=str(e))

    if settings.circuit_breaker_health_enabled:
        try:
            from shieldops.api.routes import (
                circuit_breaker_health as cbh_mod,
            )
            from shieldops.topology.circuit_breaker_health import (
                CircuitBreakerHealthMonitor,
            )

            cbh_engine = CircuitBreakerHealthMonitor(
                max_records=settings.circuit_breaker_health_max_records,
                max_trip_count_24h=settings.circuit_breaker_health_max_trip_count_24h,
            )
            cbh_mod.set_engine(cbh_engine)
            app.include_router(
                cbh_mod.cbh_route,
                prefix=settings.api_prefix,
                tags=["Circuit Breaker Health"],
            )
            logger.info("circuit_breaker_health_initialized")
        except Exception as e:
            logger.warning("circuit_breaker_health_init_failed", error=str(e))

    if settings.data_pipeline_enabled:
        try:
            from shieldops.api.routes import (
                data_pipeline as dpr_mod,
            )
            from shieldops.observability.data_pipeline import (
                DataPipelineReliabilityMonitor,
            )

            dpr_engine = DataPipelineReliabilityMonitor(
                max_records=settings.data_pipeline_max_records,
                freshness_threshold_seconds=settings.data_pipeline_freshness_threshold_seconds,
            )
            dpr_mod.set_engine(dpr_engine)
            app.include_router(
                dpr_mod.dpr_route,
                prefix=settings.api_prefix,
                tags=["Data Pipeline"],
            )
            logger.info("data_pipeline_initialized")
        except Exception as e:
            logger.warning("data_pipeline_init_failed", error=str(e))

    if settings.queue_depth_forecast_enabled:
        try:
            from shieldops.api.routes import (
                queue_depth_forecast as qdf_mod,
            )
            from shieldops.observability.queue_depth_forecast import (
                QueueDepthForecaster,
            )

            qdf_engine = QueueDepthForecaster(
                max_records=settings.queue_depth_forecast_max_records,
                overflow_threshold=settings.queue_depth_forecast_overflow_threshold,
            )
            qdf_mod.set_engine(qdf_engine)
            app.include_router(
                qdf_mod.qdf_route,
                prefix=settings.api_prefix,
                tags=["Queue Depth Forecast"],
            )
            logger.info("queue_depth_forecast_initialized")
        except Exception as e:
            logger.warning("queue_depth_forecast_init_failed", error=str(e))

    if settings.connection_pool_enabled:
        try:
            from shieldops.analytics.connection_pool import (
                ConnectionPoolMonitor,
            )
            from shieldops.api.routes import (
                connection_pool as cpm_mod,
            )

            cpm_engine = ConnectionPoolMonitor(
                max_records=settings.connection_pool_max_records,
                saturation_threshold_pct=settings.connection_pool_saturation_threshold_pct,
            )
            cpm_mod.set_engine(cpm_engine)
            app.include_router(
                cpm_mod.cpm_route,
                prefix=settings.api_prefix,
                tags=["Connection Pool"],
            )
            logger.info("connection_pool_initialized")
        except Exception as e:
            logger.warning("connection_pool_init_failed", error=str(e))

    if settings.license_risk_enabled:
        try:
            from shieldops.api.routes import (
                license_risk as lr_mod,
            )
            from shieldops.compliance.license_risk import (
                DependencyLicenseRiskAnalyzer,
            )

            lr_engine = DependencyLicenseRiskAnalyzer(
                max_records=settings.license_risk_max_records,
                max_transitive_depth=settings.license_risk_max_transitive_depth,
            )
            lr_mod.set_engine(lr_engine)
            app.include_router(
                lr_mod.lr_route,
                prefix=settings.api_prefix,
                tags=["License Risk"],
            )
            logger.info("license_risk_initialized")
        except Exception as e:
            logger.warning("license_risk_init_failed", error=str(e))

    if settings.comm_effectiveness_enabled:
        try:
            from shieldops.api.routes import (
                comm_effectiveness as comeff_mod,
            )
            from shieldops.incidents.comm_effectiveness import (
                CommEffectivenessAnalyzer,
            )

            comeff_engine = CommEffectivenessAnalyzer(
                max_records=settings.comm_effectiveness_max_records,
                min_delivery_rate_pct=settings.comm_effectiveness_min_delivery_rate_pct,
            )
            comeff_mod.set_engine(comeff_engine)
            app.include_router(
                comeff_mod.cef_route,
                prefix=settings.api_prefix,
                tags=["Comm Effectiveness"],
            )
            logger.info("comm_effectiveness_initialized")
        except Exception as e:
            logger.warning("comm_effectiveness_init_failed", error=str(e))

    if settings.readiness_scorer_enabled:
        try:
            from shieldops.api.routes import (
                readiness_scorer as ors_mod,
            )
            from shieldops.operations.readiness_scorer import (
                OperationalReadinessScorer,
            )

            ors_engine = OperationalReadinessScorer(
                max_records=settings.readiness_scorer_max_records,
                min_readiness_score=settings.readiness_scorer_min_readiness_score,
            )
            ors_mod.set_engine(ors_engine)
            app.include_router(
                ors_mod.ors_route,
                prefix=settings.api_prefix,
                tags=["Readiness Scorer"],
            )
            logger.info("readiness_scorer_initialized")
        except Exception as e:
            logger.warning("readiness_scorer_init_failed", error=str(e))

    # ── Phase 33: Incident Self-Healing & Platform Governance ──

    if settings.auto_triage_enabled:
        try:
            from shieldops.api.routes import (
                auto_triage as iat_mod,
            )
            from shieldops.incidents.auto_triage import (
                IncidentAutoTriageEngine,
            )

            iat_engine = IncidentAutoTriageEngine(
                max_records=settings.auto_triage_max_records,
                min_confidence_pct=settings.auto_triage_min_confidence_pct,
            )
            iat_mod.set_engine(iat_engine)
            app.include_router(
                iat_mod.iat_route,
                prefix=settings.api_prefix,
                tags=["Auto Triage"],
            )
            logger.info("auto_triage_initialized")
        except Exception as e:
            logger.warning("auto_triage_init_failed", error=str(e))

    if settings.self_healing_enabled:
        try:
            from shieldops.api.routes import (
                self_healing as slh_mod,
            )
            from shieldops.operations.self_healing import (
                SelfHealingOrchestrator,
            )

            slh_engine = SelfHealingOrchestrator(
                max_records=settings.self_healing_max_records,
                min_success_rate_pct=settings.self_healing_min_success_rate_pct,
            )
            slh_mod.set_engine(slh_engine)
            app.include_router(
                slh_mod.slh_route,
                prefix=settings.api_prefix,
                tags=["Self Healing"],
            )
            logger.info("self_healing_initialized")
        except Exception as e:
            logger.warning("self_healing_init_failed", error=str(e))

    if settings.recurrence_pattern_enabled:
        try:
            from shieldops.api.routes import (
                recurrence_pattern as rpa_mod,
            )
            from shieldops.incidents.recurrence_pattern import (
                RecurrencePatternDetector,
            )

            rpa_engine = RecurrencePatternDetector(
                max_records=settings.recurrence_pattern_max_records,
                min_incidents=settings.recurrence_pattern_min_incidents,
            )
            rpa_mod.set_engine(rpa_engine)
            app.include_router(
                rpa_mod.rpa_route,
                prefix=settings.api_prefix,
                tags=["Recurrence Pattern"],
            )
            logger.info("recurrence_pattern_initialized")
        except Exception as e:
            logger.warning("recurrence_pattern_init_failed", error=str(e))

    if settings.policy_impact_enabled:
        try:
            from shieldops.api.routes import (
                policy_impact as pis_mod,
            )
            from shieldops.compliance.policy_impact import (
                PolicyImpactScorer,
            )

            pis_engine = PolicyImpactScorer(
                max_records=settings.policy_impact_max_records,
                max_conflict_count=settings.policy_impact_max_conflict_count,
            )
            pis_mod.set_engine(pis_engine)
            app.include_router(
                pis_mod.pis_route,
                prefix=settings.api_prefix,
                tags=["Policy Impact"],
            )
            logger.info("policy_impact_initialized")
        except Exception as e:
            logger.warning("policy_impact_init_failed", error=str(e))

    if settings.audit_intelligence_enabled:
        try:
            from shieldops.api.routes import (
                audit_intelligence as ais_mod,
            )
            from shieldops.audit.audit_intelligence import (
                AuditIntelligenceAnalyzer,
            )

            ais_engine = AuditIntelligenceAnalyzer(
                max_records=settings.audit_intelligence_max_records,
                anomaly_threshold_pct=settings.audit_intelligence_anomaly_threshold_pct,
            )
            ais_mod.set_engine(ais_engine)
            app.include_router(
                ais_mod.ais_route,
                prefix=settings.api_prefix,
                tags=["Audit Intelligence"],
            )
            logger.info("audit_intelligence_initialized")
        except Exception as e:
            logger.warning("audit_intelligence_init_failed", error=str(e))

    if settings.automation_gap_enabled:
        try:
            from shieldops.api.routes import (
                automation_gap as agp_mod,
            )
            from shieldops.operations.automation_gap import (
                AutomationGapIdentifier,
            )

            agp_engine = AutomationGapIdentifier(
                max_records=settings.automation_gap_max_records,
                min_roi_score=settings.automation_gap_min_roi_score,
            )
            agp_mod.set_engine(agp_engine)
            app.include_router(
                agp_mod.agp_route,
                prefix=settings.api_prefix,
                tags=["Automation Gap"],
            )
            logger.info("automation_gap_initialized")
        except Exception as e:
            logger.warning("automation_gap_init_failed", error=str(e))

    if settings.capacity_demand_enabled:
        try:
            from shieldops.analytics.capacity_demand import (
                CapacityDemandModeler,
            )
            from shieldops.api.routes import (
                capacity_demand as cdm_mod,
            )

            cdm_engine = CapacityDemandModeler(
                max_records=settings.capacity_demand_max_records,
                deficit_threshold_pct=settings.capacity_demand_deficit_threshold_pct,
            )
            cdm_mod.set_engine(cdm_engine)
            app.include_router(
                cdm_mod.cdm_route,
                prefix=settings.api_prefix,
                tags=["Capacity Demand"],
            )
            logger.info("capacity_demand_initialized")
        except Exception as e:
            logger.warning("capacity_demand_init_failed", error=str(e))

    if settings.spot_advisor_enabled:
        try:
            from shieldops.api.routes import (
                spot_advisor as spa_mod,
            )
            from shieldops.billing.spot_advisor import (
                SpotInstanceAdvisor,
            )

            spad_engine = SpotInstanceAdvisor(
                max_records=settings.spot_advisor_max_records,
                min_savings_pct=settings.spot_advisor_min_savings_pct,
            )
            spa_mod.set_engine(spad_engine)
            app.include_router(
                spa_mod.spa_route,
                prefix=settings.api_prefix,
                tags=["Spot Advisor"],
            )
            logger.info("spot_advisor_initialized")
        except Exception as e:
            logger.warning("spot_advisor_init_failed", error=str(e))

    if settings.scaling_efficiency_enabled:
        try:
            from shieldops.api.routes import (
                scaling_efficiency as sef_mod,
            )
            from shieldops.operations.scaling_efficiency import (
                ScalingEfficiencyTracker,
            )

            sef_engine = ScalingEfficiencyTracker(
                max_records=settings.scaling_efficiency_max_records,
                max_duration_seconds=settings.scaling_efficiency_max_duration_seconds,
            )
            sef_mod.set_engine(sef_engine)
            app.include_router(
                sef_mod.sef_route,
                prefix=settings.api_prefix,
                tags=["Scaling Efficiency"],
            )
            logger.info("scaling_efficiency_initialized")
        except Exception as e:
            logger.warning("scaling_efficiency_init_failed", error=str(e))

    if settings.reliability_antipattern_enabled:
        try:
            from shieldops.api.routes import (
                reliability_antipattern as rap_mod,
            )
            from shieldops.topology.reliability_antipattern import (
                ReliabilityAntiPatternDetector,
            )

            rap_engine = ReliabilityAntiPatternDetector(
                max_records=settings.reliability_antipattern_max_records,
                max_accepted_risks=settings.reliability_antipattern_max_accepted_risks,
            )
            rap_mod.set_engine(rap_engine)
            app.include_router(
                rap_mod.rap_route,
                prefix=settings.api_prefix,
                tags=["Reliability Antipattern"],
            )
            logger.info("reliability_antipattern_initialized")
        except Exception as e:
            logger.warning("reliability_antipattern_init_failed", error=str(e))

    if settings.error_budget_forecast_enabled:
        try:
            from shieldops.api.routes import (
                error_budget_forecast as ebf_mod,
            )
            from shieldops.sla.error_budget_forecast import (
                ErrorBudgetForecaster,
            )

            ebf_engine = ErrorBudgetForecaster(
                max_records=settings.error_budget_forecast_max_records,
                risk_threshold_pct=settings.error_budget_forecast_risk_threshold_pct,
            )
            ebf_mod.set_engine(ebf_engine)
            app.include_router(
                ebf_mod.ebf_route,
                prefix=settings.api_prefix,
                tags=["Error Budget Forecast"],
            )
            logger.info("error_budget_forecast_initialized")
        except Exception as e:
            logger.warning("error_budget_forecast_init_failed", error=str(e))

    if settings.dependency_risk_enabled:
        try:
            from shieldops.api.routes import (
                dependency_risk as drs_mod,
            )
            from shieldops.topology.dependency_risk import (
                DependencyRiskScorer,
            )

            drs_engine = DependencyRiskScorer(
                max_records=settings.dependency_risk_max_records,
                critical_threshold=settings.dependency_risk_critical_threshold,
            )
            drs_mod.set_engine(drs_engine)
            app.include_router(
                drs_mod.drs_route,
                prefix=settings.api_prefix,
                tags=["Dependency Risk"],
            )
            logger.info("dependency_risk_initialized")
        except Exception as e:
            logger.warning("dependency_risk_init_failed", error=str(e))

    if settings.incident_similarity_enabled:
        try:
            from shieldops.api.routes import (
                incident_similarity as ism_mod,
            )
            from shieldops.incidents.incident_similarity import (
                IncidentSimilarityEngine,
            )

            ism_engine = IncidentSimilarityEngine(
                max_records=settings.incident_similarity_max_records,
                min_confidence_pct=settings.incident_similarity_min_confidence_pct,
            )
            ism_mod.set_engine(ism_engine)
            app.include_router(
                ism_mod.ism_route,
                prefix=settings.api_prefix,
                tags=["Incident Similarity"],
            )
            logger.info("incident_similarity_initialized")
        except Exception as e:
            logger.warning("incident_similarity_init_failed", error=str(e))

    if settings.incident_cost_enabled:
        try:
            from shieldops.api.routes import (
                incident_cost as icl_mod,
            )
            from shieldops.incidents.incident_cost import (
                IncidentCostCalculator,
            )

            icl_engine = IncidentCostCalculator(
                max_records=settings.incident_cost_max_records,
                high_threshold=settings.incident_cost_high_threshold,
            )
            icl_mod.set_engine(icl_engine)
            app.include_router(
                icl_mod.icl_route,
                prefix=settings.api_prefix,
                tags=["Incident Cost"],
            )
            logger.info("incident_cost_initialized")
        except Exception as e:
            logger.warning("incident_cost_init_failed", error=str(e))

    if settings.followup_tracker_enabled:
        try:
            from shieldops.api.routes import (
                followup_tracker as fut_mod,
            )
            from shieldops.incidents.followup_tracker import (
                PostIncidentFollowupTracker,
            )

            fut_engine = PostIncidentFollowupTracker(
                max_records=settings.followup_tracker_max_records,
                overdue_days=settings.followup_tracker_overdue_days,
            )
            fut_mod.set_engine(fut_engine)
            app.include_router(
                fut_mod.fut_route,
                prefix=settings.api_prefix,
                tags=["Follow-up Tracker"],
            )
            logger.info("followup_tracker_initialized")
        except Exception as e:
            logger.warning("followup_tracker_init_failed", error=str(e))

    if settings.cognitive_load_enabled:
        try:
            from shieldops.api.routes import (
                cognitive_load as clt_mod,
            )
            from shieldops.operations.cognitive_load import (
                TeamCognitiveLoadTracker,
            )

            clt_engine = TeamCognitiveLoadTracker(
                max_records=settings.cognitive_load_max_records,
                critical_threshold=settings.cognitive_load_critical_threshold,
            )
            clt_mod.set_engine(clt_engine)
            app.include_router(
                clt_mod.clt_route,
                prefix=settings.api_prefix,
                tags=["Cognitive Load"],
            )
            logger.info("cognitive_load_initialized")
        except Exception as e:
            logger.warning("cognitive_load_init_failed", error=str(e))

    if settings.collaboration_scorer_enabled:
        try:
            from shieldops.analytics.collaboration_scorer import (
                CrossTeamCollaborationScorer,
            )
            from shieldops.api.routes import (
                collaboration_scorer as css_mod,
            )

            css_engine = CrossTeamCollaborationScorer(
                max_records=settings.collaboration_scorer_max_records,
                min_score=settings.collaboration_scorer_min_score,
            )
            css_mod.set_engine(css_engine)
            app.include_router(
                css_mod.css_route,
                prefix=settings.api_prefix,
                tags=["Collaboration Scorer"],
            )
            logger.info("collaboration_scorer_initialized")
        except Exception as e:
            logger.warning("collaboration_scorer_init_failed", error=str(e))

    if settings.contribution_tracker_enabled:
        try:
            from shieldops.api.routes import (
                contribution_tracker as kct_mod,
            )
            from shieldops.knowledge.contribution_tracker import (
                KnowledgeContributionTracker,
            )

            kct_engine = KnowledgeContributionTracker(
                max_records=settings.contribution_tracker_max_records,
                min_quality_score=settings.contribution_tracker_min_quality_score,
            )
            kct_mod.set_engine(kct_engine)
            app.include_router(
                kct_mod.kct_route,
                prefix=settings.api_prefix,
                tags=["Contribution Tracker"],
            )
            logger.info("contribution_tracker_initialized")
        except Exception as e:
            logger.warning("contribution_tracker_init_failed", error=str(e))

    if settings.api_performance_enabled:
        try:
            from shieldops.analytics.api_performance import (
                APIPerformanceProfiler,
            )
            from shieldops.api.routes import (
                api_performance as apf_mod,
            )

            apf_engine = APIPerformanceProfiler(
                max_records=settings.api_performance_max_records,
                slow_threshold_ms=settings.api_performance_slow_threshold_ms,
            )
            apf_mod.set_engine(apf_engine)
            app.include_router(
                apf_mod.apf_route,
                prefix=settings.api_prefix,
                tags=["API Performance"],
            )
            logger.info("api_performance_initialized")
        except Exception as e:
            logger.warning("api_performance_init_failed", error=str(e))

    if settings.resource_contention_enabled:
        try:
            from shieldops.analytics.resource_contention import (
                ResourceContentionDetector,
            )
            from shieldops.api.routes import (
                resource_contention as rcd_mod,
            )

            rcd_engine = ResourceContentionDetector(
                max_records=settings.resource_contention_max_records,
                critical_threshold_pct=settings.resource_contention_critical_threshold_pct,
            )
            rcd_mod.set_engine(rcd_engine)
            app.include_router(
                rcd_mod.rcd_route,
                prefix=settings.api_prefix,
                tags=["Resource Contention"],
            )
            logger.info("resource_contention_initialized")
        except Exception as e:
            logger.warning("resource_contention_init_failed", error=str(e))

    if settings.rollback_analyzer_enabled:
        try:
            from shieldops.api.routes import (
                rollback_analyzer as rba_mod,
            )
            from shieldops.changes.rollback_analyzer import (
                DeploymentRollbackAnalyzer,
            )

            rba_engine = DeploymentRollbackAnalyzer(
                max_records=settings.rollback_analyzer_max_records,
                max_rate_pct=settings.rollback_analyzer_max_rate_pct,
            )
            rba_mod.set_engine(rba_engine)
            app.include_router(
                rba_mod.rba_route,
                prefix=settings.api_prefix,
                tags=["Rollback Analyzer"],
            )
            logger.info("rollback_analyzer_initialized")
        except Exception as e:
            logger.warning("rollback_analyzer_init_failed", error=str(e))

    if settings.attack_surface_enabled:
        try:
            from shieldops.api.routes import (
                attack_surface_monitor as asm_mod,
            )
            from shieldops.security.attack_surface import (
                AttackSurfaceMonitor,
            )

            asm_engine = AttackSurfaceMonitor(
                max_records=settings.attack_surface_max_records,
                max_critical_exposures=settings.attack_surface_max_critical_exposures,
            )
            asm_mod.set_engine(asm_engine)
            app.include_router(
                asm_mod.asm_route,
                prefix=settings.api_prefix,
                tags=["Attack Surface Monitor"],
            )
            logger.info("attack_surface_monitor_initialized")
        except Exception as e:
            logger.warning("attack_surface_monitor_init_failed", error=str(e))

    if settings.runbook_recommendation_enabled:
        try:
            from shieldops.api.routes import (
                runbook_recommender as rbr_mod,
            )
            from shieldops.operations.runbook_recommender import (
                RunbookRecommendationEngine,
            )

            rbr_engine = RunbookRecommendationEngine(
                max_records=settings.runbook_recommendation_max_records,
                min_confidence_pct=settings.runbook_recommendation_min_confidence_pct,
            )
            rbr_mod.set_engine(rbr_engine)
            app.include_router(
                rbr_mod.rbr_route,
                prefix=settings.api_prefix,
                tags=["Runbook Recommender"],
            )
            logger.info("runbook_recommender_initialized")
        except Exception as e:
            logger.warning("runbook_recommender_init_failed", error=str(e))

    if settings.reliability_scorecard_enabled:
        try:
            from shieldops.api.routes import (
                reliability_scorecard as prs_mod,
            )
            from shieldops.sla.reliability_scorecard import (
                PlatformReliabilityScorecard,
            )

            prs_engine = PlatformReliabilityScorecard(
                max_records=settings.reliability_scorecard_max_records,
                min_grade_score=settings.reliability_scorecard_min_grade_score,
            )
            prs_mod.set_engine(prs_engine)
            app.include_router(
                prs_mod.prs_route,
                prefix=settings.api_prefix,
                tags=["Reliability Scorecard"],
            )
            logger.info("reliability_scorecard_initialized")
        except Exception as e:
            logger.warning("reliability_scorecard_init_failed", error=str(e))

    if settings.llm_cost_tracker_enabled:
        try:
            from shieldops.api.routes import (
                llm_cost_tracker as lct_mod,
            )
            from shieldops.billing.llm_cost_tracker import (
                LLMTokenCostTracker,
            )

            lct_engine = LLMTokenCostTracker(
                max_records=settings.llm_cost_tracker_max_records,
                high_cost_threshold=settings.llm_cost_tracker_high_cost_threshold,
            )
            lct_mod.set_engine(lct_engine)
            app.include_router(
                lct_mod.lct_route,
                prefix=settings.api_prefix,
                tags=["LLM Cost Tracker"],
            )
            logger.info("llm_cost_tracker_initialized")
        except Exception as e:
            logger.warning("llm_cost_tracker_init_failed", error=str(e))

    if settings.cloud_arbitrage_enabled:
        try:
            from shieldops.api.routes import (
                cloud_arbitrage as car_mod,
            )
            from shieldops.billing.cloud_arbitrage import (
                CloudCostArbitrageAnalyzer,
            )

            car_engine = CloudCostArbitrageAnalyzer(
                max_records=settings.cloud_arbitrage_max_records,
                min_savings_pct=settings.cloud_arbitrage_min_savings_pct,
            )
            car_mod.set_engine(car_engine)
            app.include_router(
                car_mod.car_route,
                prefix=settings.api_prefix,
                tags=["Cloud Arbitrage"],
            )
            logger.info("cloud_arbitrage_initialized")
        except Exception as e:
            logger.warning("cloud_arbitrage_init_failed", error=str(e))

    if settings.observability_cost_enabled:
        try:
            from shieldops.api.routes import (
                observability_cost as oca_mod,
            )
            from shieldops.observability.observability_cost import (
                ObservabilityCostAllocator,
            )

            oca_engine = ObservabilityCostAllocator(
                max_records=settings.observability_cost_max_records,
                high_cost_threshold=settings.observability_cost_high_cost_threshold,
            )
            oca_mod.set_engine(oca_engine)
            app.include_router(
                oca_mod.oca_route,
                prefix=settings.api_prefix,
                tags=["Observability Cost"],
            )
            logger.info("observability_cost_initialized")
        except Exception as e:
            logger.warning("observability_cost_init_failed", error=str(e))

    if settings.lead_time_analyzer_enabled:
        try:
            from shieldops.api.routes import (
                lead_time_analyzer as lta_mod,
            )
            from shieldops.changes.lead_time_analyzer import (
                ChangeLeadTimeAnalyzer,
            )

            lta_engine = ChangeLeadTimeAnalyzer(
                max_records=settings.lead_time_analyzer_max_records,
                max_lead_time_hours=settings.lead_time_analyzer_max_lead_time_hours,
            )
            lta_mod.set_engine(lta_engine)
            app.include_router(
                lta_mod.lta_route,
                prefix=settings.api_prefix,
                tags=["Lead Time Analyzer"],
            )
            logger.info("lead_time_analyzer_initialized")
        except Exception as e:
            logger.warning("lead_time_analyzer_init_failed", error=str(e))

    if settings.flag_impact_enabled:
        try:
            from shieldops.api.routes import (
                flag_impact as fia_mod,
            )
            from shieldops.config.flag_impact import (
                FeatureFlagImpactAnalyzer,
            )

            fia_engine = FeatureFlagImpactAnalyzer(
                max_records=settings.flag_impact_max_records,
                min_reliability_pct=settings.flag_impact_min_reliability_pct,
            )
            fia_mod.set_engine(fia_engine)
            app.include_router(
                fia_mod.fia_route,
                prefix=settings.api_prefix,
                tags=["Flag Impact"],
            )
            logger.info("flag_impact_initialized")
        except Exception as e:
            logger.warning("flag_impact_init_failed", error=str(e))

    if settings.deployment_dependency_enabled:
        try:
            from shieldops.api.routes import (
                deployment_dependency as ddy_mod,
            )
            from shieldops.changes.deployment_dependency import (
                DeploymentDependencyTracker,
            )

            ddy_engine = DeploymentDependencyTracker(
                max_records=settings.deployment_dependency_max_records,
                max_depth=settings.deployment_dependency_max_depth,
            )
            ddy_mod.set_engine(ddy_engine)
            app.include_router(
                ddy_mod.ddy_route,
                prefix=settings.api_prefix,
                tags=["Deployment Dependency"],
            )
            logger.info("deployment_dependency_initialized")
        except Exception as e:
            logger.warning("deployment_dependency_init_failed", error=str(e))

    if settings.postmortem_quality_enabled:
        try:
            from shieldops.api.routes import (
                postmortem_quality as pmq_mod,
            )
            from shieldops.incidents.postmortem_quality import (
                PostmortemQualityScorer,
            )

            pmq_engine = PostmortemQualityScorer(
                max_records=settings.postmortem_quality_max_records,
                min_score=settings.postmortem_quality_min_score,
            )
            pmq_mod.set_engine(pmq_engine)
            app.include_router(
                pmq_mod.pmq_route,
                prefix=settings.api_prefix,
                tags=["Postmortem Quality"],
            )
            logger.info("postmortem_quality_initialized")
        except Exception as e:
            logger.warning("postmortem_quality_init_failed", error=str(e))

    if settings.dr_drill_tracker_enabled:
        try:
            from shieldops.api.routes import (
                dr_drill_tracker as drt_mod,
            )
            from shieldops.operations.dr_drill_tracker import (
                DRDrillTracker,
            )

            drt_engine = DRDrillTracker(
                max_records=settings.dr_drill_tracker_max_records,
                min_success_rate_pct=settings.dr_drill_tracker_min_success_rate_pct,
            )
            drt_mod.set_engine(drt_engine)
            app.include_router(
                drt_mod.drt_route,
                prefix=settings.api_prefix,
                tags=["DR Drill Tracker"],
            )
            logger.info("dr_drill_tracker_initialized")
        except Exception as e:
            logger.warning("dr_drill_tracker_init_failed", error=str(e))

    if settings.escalation_optimizer_enabled:
        try:
            from shieldops.api.routes import (
                escalation_optimizer as epo_mod,
            )
            from shieldops.incidents.escalation_optimizer import (
                IncidentEscalationOptimizer,
            )

            epo_engine = IncidentEscalationOptimizer(
                max_records=settings.escalation_optimizer_max_records,
                max_escalation_time_min=settings.escalation_optimizer_max_escalation_time_min,
            )
            epo_mod.set_engine(epo_engine)
            app.include_router(
                epo_mod.epo_route,
                prefix=settings.api_prefix,
                tags=["Escalation Optimizer"],
            )
            logger.info("escalation_optimizer_initialized")
        except Exception as e:
            logger.warning("escalation_optimizer_init_failed", error=str(e))

    if settings.tenant_quota_enabled:
        try:
            from shieldops.api.routes import (
                tenant_quota as tqm_mod,
            )
            from shieldops.operations.tenant_quota import (
                TenantResourceQuotaManager,
            )

            tqm_engine = TenantResourceQuotaManager(
                max_records=settings.tenant_quota_max_records,
                max_utilization_pct=settings.tenant_quota_max_utilization_pct,
            )
            tqm_mod.set_engine(tqm_engine)
            app.include_router(
                tqm_mod.tqm_route,
                prefix=settings.api_prefix,
                tags=["Tenant Quota"],
            )
            logger.info("tenant_quota_initialized")
        except Exception as e:
            logger.warning("tenant_quota_init_failed", error=str(e))

    if settings.decision_audit_enabled:
        try:
            from shieldops.api.routes import (
                decision_audit as dal_mod,
            )
            from shieldops.audit.decision_audit import (
                DecisionAuditLogger,
            )

            dal_engine = DecisionAuditLogger(
                max_records=settings.decision_audit_max_records,
                min_confidence_pct=settings.decision_audit_min_confidence_pct,
            )
            dal_mod.set_engine(dal_engine)
            app.include_router(
                dal_mod.dal_route,
                prefix=settings.api_prefix,
                tags=["Decision Audit"],
            )
            logger.info("decision_audit_initialized")
        except Exception as e:
            logger.warning("decision_audit_init_failed", error=str(e))

    if settings.retention_policy_enabled:
        try:
            from shieldops.api.routes import (
                retention_policy as rpm_mod,
            )
            from shieldops.observability.retention_policy import (
                DataRetentionPolicyManager,
            )

            rpm_engine = DataRetentionPolicyManager(
                max_records=settings.retention_policy_max_records,
                max_retention_days=settings.retention_policy_max_retention_days,
            )
            rpm_mod.set_engine(rpm_engine)
            app.include_router(
                rpm_mod.rpm_route,
                prefix=settings.api_prefix,
                tags=["Retention Policy"],
            )
            logger.info("retention_policy_initialized")
        except Exception as e:
            logger.warning("retention_policy_init_failed", error=str(e))

    if settings.twilio_sms_enabled:
        try:
            from shieldops.api.routes import (
                twilio_sms as tsg_mod,
            )
            from shieldops.integrations.notifications.twilio_sms import (
                TwilioSMSGateway,
            )

            tsg_engine = TwilioSMSGateway(
                max_records=settings.twilio_sms_max_records,
                max_retries=settings.twilio_sms_max_retries,
            )
            tsg_mod.set_engine(tsg_engine)
            app.include_router(
                tsg_mod.tsg_route,
                prefix=settings.api_prefix,
                tags=["Twilio SMS"],
            )
            logger.info("twilio_sms_initialized")
        except Exception as e:
            logger.warning("twilio_sms_init_failed", error=str(e))

    if settings.twilio_voice_enabled:
        try:
            from shieldops.api.routes import (
                twilio_voice as tva_mod,
            )
            from shieldops.integrations.notifications.twilio_voice import (
                TwilioVoiceAlertSystem,
            )

            tva_engine = TwilioVoiceAlertSystem(
                max_records=settings.twilio_voice_max_records,
                max_ring_seconds=settings.twilio_voice_max_ring_seconds,
            )
            tva_mod.set_engine(tva_engine)
            app.include_router(
                tva_mod.tva_route,
                prefix=settings.api_prefix,
                tags=["Twilio Voice"],
            )
            logger.info("twilio_voice_initialized")
        except Exception as e:
            logger.warning("twilio_voice_init_failed", error=str(e))

    if settings.teams_notifier_enabled:
        try:
            from shieldops.api.routes import (
                teams_notifier as mtn_mod,
            )
            from shieldops.integrations.notifications.teams import (
                MicrosoftTeamsNotifier,
            )

            mtn_engine = MicrosoftTeamsNotifier(
                max_records=settings.teams_notifier_max_records,
                max_retries=settings.teams_notifier_max_retries,
            )
            mtn_mod.set_engine(mtn_engine)
            app.include_router(
                mtn_mod.mtn_route,
                prefix=settings.api_prefix,
                tags=["Teams Notifier"],
            )
            logger.info("teams_notifier_initialized")
        except Exception as e:
            logger.warning("teams_notifier_init_failed", error=str(e))

    if settings.swarm_coordinator_enabled:
        try:
            from shieldops.agents.swarm_coordinator import (
                AgentSwarmCoordinator,
            )
            from shieldops.api.routes import (
                swarm_coordinator as swc_mod,
            )

            swc_engine = AgentSwarmCoordinator(
                max_records=settings.swarm_coordinator_max_records,
                max_agents=settings.swarm_coordinator_max_agents,
            )
            swc_mod.set_engine(swc_engine)
            app.include_router(
                swc_mod.swc_route,
                prefix=settings.api_prefix,
                tags=["Swarm Coordinator"],
            )
            logger.info("swarm_coordinator_initialized")
        except Exception as e:
            logger.warning("swarm_coordinator_init_failed", error=str(e))

    if settings.consensus_engine_enabled:
        try:
            from shieldops.agents.consensus_engine import (
                AgentConsensusEngine,
            )
            from shieldops.api.routes import (
                consensus_engine as ace_mod,
            )

            ace_engine = AgentConsensusEngine(
                max_records=settings.consensus_engine_max_records,
                quorum_pct=settings.consensus_engine_quorum_pct,
            )
            ace_mod.set_engine(ace_engine)
            app.include_router(
                ace_mod.ace_route,
                prefix=settings.api_prefix,
                tags=["Consensus Engine"],
            )
            logger.info("consensus_engine_initialized")
        except Exception as e:
            logger.warning("consensus_engine_init_failed", error=str(e))

    if settings.knowledge_mesh_enabled:
        try:
            from shieldops.agents.knowledge_mesh import (
                AgentKnowledgeMesh,
            )
            from shieldops.api.routes import (
                knowledge_mesh as akm_mod,
            )

            akm_engine = AgentKnowledgeMesh(
                max_records=settings.knowledge_mesh_max_records,
                ttl_seconds=settings.knowledge_mesh_ttl_seconds,
            )
            akm_mod.set_engine(akm_engine)
            app.include_router(
                akm_mod.akm_route,
                prefix=settings.api_prefix,
                tags=["Knowledge Mesh"],
            )
            logger.info("knowledge_mesh_initialized")
        except Exception as e:
            logger.warning("knowledge_mesh_init_failed", error=str(e))

    if settings.risk_aggregator_enabled:
        try:
            from shieldops.api.routes import (
                risk_aggregator as rsa_mod,
            )
            from shieldops.security.risk_aggregator import (
                RiskSignalAggregator,
            )

            rsa_engine = RiskSignalAggregator(
                max_records=settings.risk_aggregator_max_records,
                critical_threshold=settings.risk_aggregator_critical_threshold,
            )
            rsa_mod.set_engine(rsa_engine)
            app.include_router(
                rsa_mod.rsa_route,
                prefix=settings.api_prefix,
                tags=["Risk Aggregator"],
            )
            logger.info("risk_aggregator_initialized")
        except Exception as e:
            logger.warning("risk_aggregator_init_failed", error=str(e))

    if settings.dynamic_risk_scorer_enabled:
        try:
            from shieldops.analytics.dynamic_risk_scorer import (
                DynamicRiskScorer,
            )
            from shieldops.api.routes import (
                dynamic_risk_scorer as dks_mod,
            )

            dks_engine = DynamicRiskScorer(
                max_records=settings.dynamic_risk_scorer_max_records,
                high_threshold=settings.dynamic_risk_scorer_high_threshold,
            )
            dks_mod.set_engine(dks_engine)
            app.include_router(
                dks_mod.drs_route,
                prefix=settings.api_prefix,
                tags=["Dynamic Risk Scorer"],
            )
            logger.info("dynamic_risk_scorer_initialized")
        except Exception as e:
            logger.warning("dynamic_risk_scorer_init_failed", error=str(e))

    if settings.predictive_alert_enabled:
        try:
            from shieldops.api.routes import (
                predictive_alert as pae_mod,
            )
            from shieldops.observability.predictive_alert import (
                PredictiveAlertEngine,
            )

            pae_engine = PredictiveAlertEngine(
                max_records=settings.predictive_alert_max_records,
                min_confidence_pct=settings.predictive_alert_min_confidence_pct,
            )
            pae_mod.set_engine(pae_engine)
            app.include_router(
                pae_mod.pae_route,
                prefix=settings.api_prefix,
                tags=["Predictive Alert"],
            )
            logger.info("predictive_alert_initialized")
        except Exception as e:
            logger.warning("predictive_alert_init_failed", error=str(e))

    if settings.token_optimizer_enabled:
        try:
            from shieldops.agents.token_optimizer import (
                AgentTokenOptimizer,
            )
            from shieldops.api.routes import (
                token_optimizer as ato_mod,
            )

            ato_engine = AgentTokenOptimizer(
                max_records=settings.token_optimizer_max_records,
                target_savings_pct=settings.token_optimizer_target_savings_pct,
            )
            ato_mod.set_engine(ato_engine)
            app.include_router(
                ato_mod.ato_route,
                prefix=settings.api_prefix,
                tags=["Token Optimizer"],
            )
            logger.info("token_optimizer_initialized")
        except Exception as e:
            logger.warning("token_optimizer_init_failed", error=str(e))

    if settings.prompt_cache_enabled:
        try:
            from shieldops.agents.prompt_cache import (
                PromptCacheManager,
            )
            from shieldops.api.routes import (
                prompt_cache as pcm_mod,
            )

            pcm_engine = PromptCacheManager(
                max_records=settings.prompt_cache_max_records,
                ttl_seconds=settings.prompt_cache_ttl_seconds,
            )
            pcm_mod.set_engine(pcm_engine)
            app.include_router(
                pcm_mod.pcm_route,
                prefix=settings.api_prefix,
                tags=["Prompt Cache"],
            )
            logger.info("prompt_cache_initialized")
        except Exception as e:
            logger.warning("prompt_cache_init_failed", error=str(e))

    if settings.routing_optimizer_enabled:
        try:
            from shieldops.agents.routing_optimizer import (
                AgentRoutingOptimizer,
            )
            from shieldops.api.routes import (
                routing_optimizer as aro_mod,
            )

            aro_engine = AgentRoutingOptimizer(
                max_records=settings.routing_optimizer_max_records,
                cost_limit=settings.routing_optimizer_cost_limit,
            )
            aro_mod.set_engine(aro_engine)
            app.include_router(
                aro_mod.aro_route,
                prefix=settings.api_prefix,
                tags=["Routing Optimizer"],
            )
            logger.info("routing_optimizer_initialized")
        except Exception as e:
            logger.warning("routing_optimizer_init_failed", error=str(e))

    if settings.threat_hunt_enabled:
        try:
            from shieldops.api.routes import threat_hunt as tho_mod
            from shieldops.security.threat_hunt import ThreatHuntOrchestrator

            tho_engine = ThreatHuntOrchestrator(
                max_records=settings.threat_hunt_max_records,
                min_detection_rate_pct=settings.threat_hunt_min_detection_rate_pct,
            )
            tho_mod.set_engine(tho_engine)
            app.include_router(tho_mod.tho_route, prefix=settings.api_prefix, tags=["Threat Hunt"])
            logger.info("threat_hunt_initialized")
        except Exception as e:
            logger.warning("threat_hunt_init_failed", error=str(e))

    if settings.response_automator_enabled:
        try:
            from shieldops.api.routes import response_automator as sra_mod
            from shieldops.security.response_automator import SecurityResponseAutomator

            sra_engine = SecurityResponseAutomator(
                max_records=settings.response_automator_max_records,
                min_success_rate_pct=settings.response_automator_min_success_rate_pct,
            )
            sra_mod.set_engine(sra_engine)
            app.include_router(
                sra_mod.sra_route, prefix=settings.api_prefix, tags=["Response Automator"]
            )
            logger.info("response_automator_initialized")
        except Exception as e:
            logger.warning("response_automator_init_failed", error=str(e))

    if settings.zero_trust_enabled:
        try:
            from shieldops.api.routes import zero_trust_verifier as ztv_mod
            from shieldops.security.zero_trust_verifier import ZeroTrustVerifier

            ztv_engine = ZeroTrustVerifier(
                max_records=settings.zero_trust_max_records,
                min_trust_score=settings.zero_trust_min_trust_score,
            )
            ztv_mod.set_engine(ztv_engine)
            app.include_router(ztv_mod.ztv_route, prefix=settings.api_prefix, tags=["Zero Trust"])
            logger.info("zero_trust_initialized")
        except Exception as e:
            logger.warning("zero_trust_init_failed", error=str(e))

    if settings.remediation_pipeline_enabled:
        try:
            from shieldops.api.routes import remediation_pipeline as rpo_mod
            from shieldops.operations.remediation_pipeline import (
                RemediationPipelineOrchestrator,
            )

            rpo_engine = RemediationPipelineOrchestrator(
                max_records=settings.remediation_pipeline_max_records,
                max_step_count=settings.remediation_pipeline_max_step_count,
            )
            rpo_mod.set_engine(rpo_engine)
            app.include_router(
                rpo_mod.rpo_route,
                prefix=settings.api_prefix,
                tags=["Remediation Pipeline"],
            )
            logger.info("remediation_pipeline_initialized")
        except Exception as e:
            logger.warning("remediation_pipeline_init_failed", error=str(e))

    if settings.recovery_coordinator_enabled:
        try:
            from shieldops.api.routes import recovery_coordinator as rcc_mod
            from shieldops.operations.recovery_coordinator import RecoveryCoordinator

            rcc_engine = RecoveryCoordinator(
                max_records=settings.recovery_coordinator_max_records,
                max_recovery_hours=settings.recovery_coordinator_max_recovery_hours,
            )
            rcc_mod.set_engine(rcc_engine)
            app.include_router(
                rcc_mod.rcc_route,
                prefix=settings.api_prefix,
                tags=["Recovery Coordinator"],
            )
            logger.info("recovery_coordinator_initialized")
        except Exception as e:
            logger.warning("recovery_coordinator_init_failed", error=str(e))

    if settings.runbook_chainer_enabled:
        try:
            from shieldops.api.routes import runbook_chainer as rce_mod
            from shieldops.operations.runbook_chainer import RunbookChainExecutor

            rce_engine = RunbookChainExecutor(
                max_records=settings.runbook_chainer_max_records,
                max_chain_length=settings.runbook_chainer_max_chain_length,
            )
            rce_mod.set_engine(rce_engine)
            app.include_router(
                rce_mod.rce_route, prefix=settings.api_prefix, tags=["Runbook Chainer"]
            )
            logger.info("runbook_chainer_initialized")
        except Exception as e:
            logger.warning("runbook_chainer_init_failed", error=str(e))

    if settings.slo_auto_scaler_enabled:
        try:
            from shieldops.api.routes import slo_auto_scaler as sas_mod
            from shieldops.sla.slo_auto_scaler import SLOAutoScaler

            sas_engine = SLOAutoScaler(
                max_records=settings.slo_auto_scaler_max_records,
                max_replica_delta=settings.slo_auto_scaler_max_replica_delta,
            )
            sas_mod.set_engine(sas_engine)
            app.include_router(
                sas_mod.sas_route, prefix=settings.api_prefix, tags=["SLO Auto-Scaler"]
            )
            logger.info("slo_auto_scaler_initialized")
        except Exception as e:
            logger.warning("slo_auto_scaler_init_failed", error=str(e))

    if settings.reliability_automator_enabled:
        try:
            from shieldops.api.routes import reliability_automator as rae_mod
            from shieldops.sla.reliability_automator import ReliabilityAutomationEngine

            rae_engine = ReliabilityAutomationEngine(
                max_records=settings.reliability_automator_max_records,
                min_impact_score=settings.reliability_automator_min_impact_score,
            )
            rae_mod.set_engine(rae_engine)
            app.include_router(
                rae_mod.rae_route,
                prefix=settings.api_prefix,
                tags=["Reliability Automator"],
            )
            logger.info("reliability_automator_initialized")
        except Exception as e:
            logger.warning("reliability_automator_init_failed", error=str(e))

    if settings.prevention_engine_enabled:
        try:
            from shieldops.api.routes import prevention_engine as ipe_mod
            from shieldops.incidents.prevention_engine import IncidentPreventionEngine

            ipe_engine = IncidentPreventionEngine(
                max_records=settings.prevention_engine_max_records,
                min_confidence_pct=settings.prevention_engine_min_confidence_pct,
            )
            ipe_mod.set_engine(ipe_engine)
            app.include_router(
                ipe_mod.ipe_route, prefix=settings.api_prefix, tags=["Prevention Engine"]
            )
            logger.info("prevention_engine_initialized")
        except Exception as e:
            logger.warning("prevention_engine_init_failed", error=str(e))

    if settings.cross_agent_enforcer_enabled:
        try:
            from shieldops.api.routes import cross_agent_enforcer as cae_mod
            from shieldops.policy.cross_agent_enforcer import CrossAgentPolicyEnforcer

            cae_engine = CrossAgentPolicyEnforcer(
                max_records=settings.cross_agent_enforcer_max_records,
                max_violations_per_agent=settings.cross_agent_enforcer_max_violations,
            )
            cae_mod.set_engine(cae_engine)
            app.include_router(
                cae_mod.cap_route,
                prefix=settings.api_prefix,
                tags=["Cross-Agent Enforcer"],
            )
            logger.info("cross_agent_enforcer_initialized")
        except Exception as e:
            logger.warning("cross_agent_enforcer_init_failed", error=str(e))

    if settings.telemetry_analyzer_enabled:
        try:
            from shieldops.agents.telemetry_analyzer import AgentTelemetryAnalyzer
            from shieldops.api.routes import telemetry_analyzer as tla_mod

            tla_engine = AgentTelemetryAnalyzer(
                max_records=settings.telemetry_analyzer_max_records,
                min_performance_pct=settings.telemetry_analyzer_min_performance_pct,
            )
            tla_mod.set_engine(tla_engine)
            app.include_router(
                tla_mod.ata_route,
                prefix=settings.api_prefix,
                tags=["Telemetry Analyzer"],
            )
            logger.info("telemetry_analyzer_initialized")
        except Exception as e:
            logger.warning("telemetry_analyzer_init_failed", error=str(e))

    if settings.compliance_auditor_enabled:
        try:
            from shieldops.agents.compliance_auditor import AgentComplianceAuditor
            from shieldops.api.routes import compliance_auditor as aca_mod

            aca_engine = AgentComplianceAuditor(
                max_records=settings.compliance_auditor_max_records,
                min_pass_rate_pct=settings.compliance_auditor_min_pass_rate_pct,
            )
            aca_mod.set_engine(aca_engine)
            app.include_router(
                aca_mod.aca_route,
                prefix=settings.api_prefix,
                tags=["Compliance Auditor"],
            )
            logger.info("compliance_auditor_initialized")
        except Exception as e:
            logger.warning("compliance_auditor_init_failed", error=str(e))

    # -- Phase 38 ----------------------------------------------------------

    if settings.war_room_orchestrator_enabled:
        try:
            from shieldops.api.routes import war_room_orchestrator as wro_mod
            from shieldops.incidents.war_room_orchestrator import (
                IncidentWarRoomOrchestrator,
            )

            wro_engine = IncidentWarRoomOrchestrator(
                max_records=settings.war_room_orchestrator_max_records,
                min_resolution_rate_pct=(settings.war_room_orchestrator_min_resolution_rate_pct),
            )
            wro_mod.set_engine(wro_engine)
            app.include_router(
                wro_mod.wro_route,
                prefix=settings.api_prefix,
                tags=["War Room"],
            )
            logger.info("war_room_initialized")
        except Exception as e:
            logger.warning("war_room_init_failed", error=str(e))

    if settings.root_cause_verifier_enabled:
        try:
            from shieldops.api.routes import root_cause_verifier as rcv_mod
            from shieldops.incidents.root_cause_verifier import (
                RootCauseVerificationEngine,
            )

            rcv_engine = RootCauseVerificationEngine(
                max_records=settings.root_cause_verifier_max_records,
                min_confidence_pct=settings.root_cause_verifier_min_confidence_pct,
            )
            rcv_mod.set_engine(rcv_engine)
            app.include_router(
                rcv_mod.rcv_route,
                prefix=settings.api_prefix,
                tags=["Root Cause Verifier"],
            )
            logger.info("root_cause_verifier_initialized")
        except Exception as e:
            logger.warning("root_cause_verifier_init_failed", error=str(e))

    if settings.comm_automator_enabled:
        try:
            from shieldops.api.routes import comm_automator as ica_mod
            from shieldops.incidents.comm_automator import (
                IncidentCommunicationAutomator,
            )

            ica_engine = IncidentCommunicationAutomator(
                max_records=settings.comm_automator_max_records,
                min_delivery_rate_pct=settings.comm_automator_min_delivery_rate_pct,
            )
            ica_mod.set_engine(ica_engine)
            app.include_router(
                ica_mod.ica_route,
                prefix=settings.api_prefix,
                tags=["Comm Automator"],
            )
            logger.info("comm_automator_initialized")
        except Exception as e:
            logger.warning("comm_automator_init_failed", error=str(e))

    if settings.posture_simulator_enabled:
        try:
            from shieldops.api.routes import posture_simulator as sps_mod
            from shieldops.security.posture_simulator import (
                SecurityPostureSimulator,
            )

            sps_engine = SecurityPostureSimulator(
                max_records=settings.posture_simulator_max_records,
                min_blocked_rate_pct=settings.posture_simulator_min_blocked_rate_pct,
            )
            sps_mod.set_engine(sps_engine)
            app.include_router(
                sps_mod.sps_route,
                prefix=settings.api_prefix,
                tags=["Posture Simulator"],
            )
            logger.info("posture_simulator_initialized")
        except Exception as e:
            logger.warning("posture_simulator_init_failed", error=str(e))

    if settings.credential_rotator_enabled:
        try:
            from shieldops.api.routes import credential_rotator as cro_mod
            from shieldops.security.credential_rotator import (
                CredentialRotationOrchestrator,
            )

            cro_engine = CredentialRotationOrchestrator(
                max_records=settings.credential_rotator_max_records,
                min_completion_rate_pct=(settings.credential_rotator_min_completion_rate_pct),
            )
            cro_mod.set_engine(cro_engine)
            app.include_router(
                cro_mod.cro_route,
                prefix=settings.api_prefix,
                tags=["Credential Rotator"],
            )
            logger.info("credential_rotator_initialized")
        except Exception as e:
            logger.warning("credential_rotator_init_failed", error=str(e))

    if settings.evidence_automator_enabled:
        try:
            from shieldops.api.routes import evidence_automator as cea_mod
            from shieldops.compliance.evidence_automator import (
                ComplianceEvidenceAutomator,
            )

            cea_engine = ComplianceEvidenceAutomator(
                max_records=settings.evidence_automator_max_records,
                min_freshness_pct=settings.evidence_automator_min_freshness_pct,
            )
            cea_mod.set_engine(cea_engine)
            app.include_router(
                cea_mod.cea_route,
                prefix=settings.api_prefix,
                tags=["Evidence Automator"],
            )
            logger.info("evidence_automator_initialized")
        except Exception as e:
            logger.warning("evidence_automator_init_failed", error=str(e))

    if settings.chaos_automator_enabled:
        try:
            from shieldops.api.routes import chaos_automator as cxa_mod
            from shieldops.observability.chaos_automator import (
                ChaosExperimentAutomator,
            )

            cxa_engine = ChaosExperimentAutomator(
                max_records=settings.chaos_automator_max_records,
                min_pass_rate_pct=settings.chaos_automator_min_pass_rate_pct,
            )
            cxa_mod.set_engine(cxa_engine)
            app.include_router(
                cxa_mod.cxa_route,
                prefix=settings.api_prefix,
                tags=["Chaos Automator"],
            )
            logger.info("chaos_automator_initialized")
        except Exception as e:
            logger.warning("chaos_automator_init_failed", error=str(e))

    if settings.failover_coordinator_enabled:
        try:
            from shieldops.api.routes import failover_coordinator as mfc_mod
            from shieldops.operations.failover_coordinator import (
                MultiRegionFailoverCoordinator,
            )

            mfc_engine = MultiRegionFailoverCoordinator(
                max_records=settings.failover_coordinator_max_records,
                max_rto_seconds=settings.failover_coordinator_max_rto_seconds,
            )
            mfc_mod.set_engine(mfc_engine)
            app.include_router(
                mfc_mod.mfc_route,
                prefix=settings.api_prefix,
                tags=["Failover Coordinator"],
            )
            logger.info("failover_coordinator_initialized")
        except Exception as e:
            logger.warning("failover_coordinator_init_failed", error=str(e))

    if settings.burst_manager_enabled:
        try:
            from shieldops.api.routes import burst_manager as cbm_mod
            from shieldops.operations.burst_manager import (
                CapacityBurstManager,
            )

            cbm_engine = CapacityBurstManager(
                max_records=settings.burst_manager_max_records,
                max_burst_budget=settings.burst_manager_max_burst_budget,
            )
            cbm_mod.set_engine(cbm_engine)
            app.include_router(
                cbm_mod.cbm_route,
                prefix=settings.api_prefix,
                tags=["Burst Manager"],
            )
            logger.info("burst_manager_initialized")
        except Exception as e:
            logger.warning("burst_manager_init_failed", error=str(e))

    if settings.platform_cost_enabled:
        try:
            from shieldops.api.routes import platform_cost_optimizer as pco_mod
            from shieldops.billing.platform_cost_optimizer import (
                PlatformCostOptimizer,
            )

            pco_engine = PlatformCostOptimizer(
                max_records=settings.platform_cost_max_records,
                min_savings_threshold=settings.platform_cost_min_savings_threshold,
            )
            pco_mod.set_engine(pco_engine)
            app.include_router(
                pco_mod.pco_route,
                prefix=settings.api_prefix,
                tags=["Platform Cost"],
            )
            logger.info("platform_cost_initialized")
        except Exception as e:
            logger.warning("platform_cost_init_failed", error=str(e))

    if settings.service_mesh_intel_enabled:
        try:
            from shieldops.api.routes import service_mesh_intel as smi_mod
            from shieldops.topology.service_mesh_intel import (
                ServiceMeshIntelligence,
            )

            smi_engine = ServiceMeshIntelligence(
                max_records=settings.service_mesh_intel_max_records,
                max_latency_ms=settings.service_mesh_intel_max_latency_ms,
            )
            smi_mod.set_engine(smi_engine)
            app.include_router(
                smi_mod.smi_route,
                prefix=settings.api_prefix,
                tags=["Service Mesh"],
            )
            logger.info("service_mesh_intel_initialized")
        except Exception as e:
            logger.warning("service_mesh_intel_init_failed", error=str(e))

    if settings.runbook_generator_enabled:
        try:
            from shieldops.api.routes import runbook_generator as org_mod
            from shieldops.operations.runbook_generator import (
                OperationalRunbookGenerator,
            )

            org_engine = OperationalRunbookGenerator(
                max_records=settings.runbook_generator_max_records,
                min_accuracy_pct=settings.runbook_generator_min_accuracy_pct,
            )
            org_mod.set_engine(org_engine)
            app.include_router(
                org_mod.org_route,
                prefix=settings.api_prefix,
                tags=["Runbook Generator"],
            )
            logger.info("runbook_generator_initialized")
        except Exception as e:
            logger.warning("runbook_generator_init_failed", error=str(e))

    # ── Phase 39: SLA Breach Predictor ──
    if settings.breach_predictor_enabled:
        try:
            from shieldops.api.routes import breach_predictor as sbp_mod
            from shieldops.sla.breach_predictor import SLABreachPredictor

            sbp_engine = SLABreachPredictor(
                max_records=settings.breach_predictor_max_records,
                min_confidence_pct=settings.breach_predictor_min_confidence_pct,
            )
            sbp_mod.set_engine(sbp_engine)
            app.include_router(
                sbp_mod.sbp_route,
                prefix=settings.api_prefix,
                tags=["SLA Breach Predictor"],
            )
            logger.info("breach_predictor_initialized")
        except Exception as e:
            logger.warning("breach_predictor_init_failed", error=str(e))

    # ── Phase 39: Error Budget Allocator ──
    if settings.error_budget_allocator_enabled:
        try:
            from shieldops.api.routes import error_budget_allocator as eba_mod
            from shieldops.sla.error_budget_allocator import ErrorBudgetAllocator

            eba_engine = ErrorBudgetAllocator(
                max_records=settings.error_budget_allocator_max_records,
                min_healthy_rate_pct=settings.error_budget_allocator_min_healthy_rate_pct,
            )
            eba_mod.set_engine(eba_engine)
            app.include_router(
                eba_mod.eba_route,
                prefix=settings.api_prefix,
                tags=["Error Budget Allocator"],
            )
            logger.info("error_budget_allocator_initialized")
        except Exception as e:
            logger.warning("error_budget_allocator_init_failed", error=str(e))

    # ── Phase 39: Dependency Topology Analyzer ──
    if settings.dependency_topology_enabled:
        try:
            from shieldops.api.routes import dependency_topology as dta_mod
            from shieldops.topology.dependency_topology import DependencyTopologyAnalyzer

            dta_engine = DependencyTopologyAnalyzer(
                max_records=settings.dependency_topology_max_records,
                max_coupling_depth=settings.dependency_topology_max_coupling_depth,
            )
            dta_mod.set_engine(dta_engine)
            app.include_router(
                dta_mod.dta_route,
                prefix=settings.api_prefix,
                tags=["Dependency Topology Analyzer"],
            )
            logger.info("dependency_topology_initialized")
        except Exception as e:
            logger.warning("dependency_topology_init_failed", error=str(e))

    # ── Phase 39: Infra Capacity Planner ──
    if settings.infra_capacity_planner_enabled:
        try:
            from shieldops.analytics.infra_capacity_planner import InfraCapacityPlanner
            from shieldops.api.routes import infra_capacity_planner as icp_mod

            icp_engine = InfraCapacityPlanner(
                max_records=settings.infra_capacity_planner_max_records,
                target_utilization_pct=settings.infra_capacity_planner_target_utilization_pct,
            )
            icp_mod.set_engine(icp_engine)
            app.include_router(
                icp_mod.icp_route,
                prefix=settings.api_prefix,
                tags=["Infra Capacity Planner"],
            )
            logger.info("infra_capacity_planner_initialized")
        except Exception as e:
            logger.warning("infra_capacity_planner_init_failed", error=str(e))

    # ── Phase 39: DNS Health Monitor ──
    if settings.dns_health_monitor_enabled:
        try:
            from shieldops.api.routes import dns_health_monitor as dhm_mod
            from shieldops.observability.dns_health_monitor import (
                DNSHealthMonitor as DNSHealthMonitorV2,
            )

            dhm_engine = DNSHealthMonitorV2(
                max_records=settings.dns_health_monitor_max_records,
                max_resolution_ms=settings.dns_health_monitor_max_resolution_ms,
            )
            dhm_mod.set_engine(dhm_engine)
            app.include_router(
                dhm_mod.dhm_route,
                prefix=settings.api_prefix,
                tags=["DNS Health Monitor"],
            )
            logger.info("dns_health_monitor_initialized")
        except Exception as e:
            logger.warning("dns_health_monitor_init_failed", error=str(e))

    # ── Phase 39: Config Drift Analyzer ──
    if settings.drift_analyzer_enabled:
        try:
            from shieldops.api.routes import drift_analyzer as cda_mod
            from shieldops.config.drift_analyzer import ConfigDriftAnalyzer

            cda_engine = ConfigDriftAnalyzer(
                max_records=settings.drift_analyzer_max_records,
                max_deviation_pct=settings.drift_analyzer_max_deviation_pct,
            )
            cda_mod.set_engine(cda_engine)
            app.include_router(
                cda_mod.cda_route,
                prefix=settings.api_prefix,
                tags=["Config Drift Analyzer"],
            )
            logger.info("drift_analyzer_initialized")
        except Exception as e:
            logger.warning("drift_analyzer_init_failed", error=str(e))

    # ── Phase 39: Incident Timeline Correlator ──
    if settings.timeline_correlator_enabled:
        try:
            from shieldops.api.routes import timeline_correlator as itc_mod
            from shieldops.incidents.timeline_correlator import IncidentTimelineCorrelator

            itc_engine = IncidentTimelineCorrelator(
                max_records=settings.timeline_correlator_max_records,
                min_confidence_pct=settings.timeline_correlator_min_confidence_pct,
            )
            itc_mod.set_engine(itc_engine)
            app.include_router(
                itc_mod.itc_route,
                prefix=settings.api_prefix,
                tags=["Incident Timeline Correlator"],
            )
            logger.info("timeline_correlator_initialized")
        except Exception as e:
            logger.warning("timeline_correlator_init_failed", error=str(e))

    # ── Phase 39: Deployment Impact Analyzer ──
    if settings.deployment_impact_enabled:
        try:
            from shieldops.api.routes import deployment_impact as dia_mod
            from shieldops.changes.deployment_impact import DeploymentImpactAnalyzer

            dia_engine = DeploymentImpactAnalyzer(
                max_records=settings.deployment_impact_max_records,
                max_impact_score=settings.deployment_impact_max_impact_score,
            )
            dia_mod.set_engine(dia_engine)
            app.include_router(
                dia_mod.dia_route,
                prefix=settings.api_prefix,
                tags=["Deployment Impact Analyzer"],
            )
            logger.info("deployment_impact_initialized")
        except Exception as e:
            logger.warning("deployment_impact_init_failed", error=str(e))

    # ── Phase 39: Alert Routing Optimizer ──
    if settings.alert_routing_optimizer_enabled:
        try:
            from shieldops.api.routes import alert_routing_optimizer as aop_mod
            from shieldops.observability.alert_routing_optimizer import (
                AlertRoutingOptimizer as AlertRoutingOptimizerV2,
            )

            aop_engine = AlertRoutingOptimizerV2(
                max_records=settings.alert_routing_optimizer_max_records,
                max_response_seconds=settings.alert_routing_optimizer_max_response_seconds,
            )
            aop_mod.set_engine(aop_engine)
            app.include_router(
                aop_mod.aop_route,
                prefix=settings.api_prefix,
                tags=["Alert Routing Optimizer"],
            )
            logger.info("alert_routing_optimizer_initialized")
        except Exception as e:
            logger.warning("alert_routing_optimizer_init_failed", error=str(e))

    # ── Phase 39: Compliance Posture Scorer ──
    if settings.compliance_posture_enabled:
        try:
            from shieldops.api.routes import compliance_posture as cps_mod
            from shieldops.compliance.posture_scorer import CompliancePostureScorer

            cps_engine = CompliancePostureScorer(
                max_records=settings.compliance_posture_max_records,
                min_score_pct=settings.compliance_posture_min_score_pct,
            )
            cps_mod.set_engine(cps_engine)
            app.include_router(
                cps_mod.cps_route,
                prefix=settings.api_prefix,
                tags=["Compliance Posture Scorer"],
            )
            logger.info("compliance_posture_initialized")
        except Exception as e:
            logger.warning("compliance_posture_init_failed", error=str(e))

    # ── Phase 39: Team Toil Quantifier ──
    if settings.toil_quantifier_enabled:
        try:
            from shieldops.api.routes import toil_quantifier as ttq_mod
            from shieldops.operations.toil_quantifier import TeamToilQuantifier

            ttq_engine = TeamToilQuantifier(
                max_records=settings.toil_quantifier_max_records,
                max_toil_hours_weekly=settings.toil_quantifier_max_toil_hours_weekly,
            )
            ttq_mod.set_engine(ttq_engine)
            app.include_router(
                ttq_mod.ttq_route,
                prefix=settings.api_prefix,
                tags=["Team Toil Quantifier"],
            )
            logger.info("toil_quantifier_initialized")
        except Exception as e:
            logger.warning("toil_quantifier_init_failed", error=str(e))

    # ── Phase 39: Platform Governance Dashboard ──
    if settings.governance_dashboard_enabled:
        try:
            from shieldops.api.routes import governance_dashboard as pgd_mod
            from shieldops.policy.governance_dashboard import PlatformGovernanceDashboard

            pgd_engine = PlatformGovernanceDashboard(
                max_records=settings.governance_dashboard_max_records,
                min_governance_score_pct=settings.governance_dashboard_min_governance_score_pct,
            )
            pgd_mod.set_engine(pgd_engine)
            app.include_router(
                pgd_mod.pgd_route,
                prefix=settings.api_prefix,
                tags=["Platform Governance Dashboard"],
            )
            logger.info("governance_dashboard_initialized")
        except Exception as e:
            logger.warning("governance_dashboard_init_failed", error=str(e))

    # ── Phase 40: Incident Replay Engine ──
    if settings.incident_replay_enabled:
        try:
            from shieldops.api.routes import incident_replay as ire_mod
            from shieldops.incidents.incident_replay import IncidentReplayEngine

            ire_engine = IncidentReplayEngine(
                max_records=settings.incident_replay_max_records,
                min_effectiveness_pct=settings.incident_replay_min_effectiveness_pct,
            )
            ire_mod.set_engine(ire_engine)
            app.include_router(
                ire_mod.ire_route,
                prefix=settings.api_prefix,
                tags=["Incident Replay Engine"],
            )
            logger.info("incident_replay_initialized")
        except Exception as e:
            logger.warning("incident_replay_init_failed", error=str(e))

    # ── Phase 40: Incident Response Timer ──
    if settings.response_timer_enabled:
        try:
            from shieldops.api.routes import response_timer as irt_mod
            from shieldops.incidents.response_timer import IncidentResponseTimer

            irt_engine = IncidentResponseTimer(
                max_records=settings.response_timer_max_records,
                target_minutes=settings.response_timer_target_minutes,
            )
            irt_mod.set_engine(irt_engine)
            app.include_router(
                irt_mod.irt_route,
                prefix=settings.api_prefix,
                tags=["Incident Response Timer"],
            )
            logger.info("response_timer_initialized")
        except Exception as e:
            logger.warning("response_timer_init_failed", error=str(e))

    # ── Phase 40: SLO Aggregation Dashboard ──
    if settings.slo_aggregator_enabled:
        try:
            from shieldops.api.routes import slo_aggregator as sad_mod
            from shieldops.sla.slo_aggregator import SLOAggregationDashboard

            sad_engine = SLOAggregationDashboard(
                max_records=settings.slo_aggregator_max_records,
                min_compliance_pct=settings.slo_aggregator_min_compliance_pct,
            )
            sad_mod.set_engine(sad_engine)
            app.include_router(
                sad_mod.sad_route,
                prefix=settings.api_prefix,
                tags=["SLO Aggregation Dashboard"],
            )
            logger.info("slo_aggregator_initialized")
        except Exception as e:
            logger.warning("slo_aggregator_init_failed", error=str(e))

    # ── Phase 40: Network Latency Mapper ──
    if settings.network_latency_enabled:
        try:
            from shieldops.api.routes import network_latency as nlm_mod
            from shieldops.topology.network_latency import NetworkLatencyMapper

            nlm_engine = NetworkLatencyMapper(
                max_records=settings.network_latency_max_records,
                max_acceptable_ms=settings.network_latency_max_acceptable_ms,
            )
            nlm_mod.set_engine(nlm_engine)
            app.include_router(
                nlm_mod.nlm_route,
                prefix=settings.api_prefix,
                tags=["Network Latency Mapper"],
            )
            logger.info("network_latency_initialized")
        except Exception as e:
            logger.warning("network_latency_init_failed", error=str(e))

    # ── Phase 40: Platform Health Index ──
    if settings.health_index_enabled:
        try:
            from shieldops.api.routes import health_index as phi_mod
            from shieldops.observability.health_index import PlatformHealthIndex

            phi_engine = PlatformHealthIndex(
                max_records=settings.health_index_max_records,
                min_score_pct=settings.health_index_min_score_pct,
            )
            phi_mod.set_engine(phi_engine)
            app.include_router(
                phi_mod.phi_route,
                prefix=settings.api_prefix,
                tags=["Platform Health Index"],
            )
            logger.info("health_index_initialized")
        except Exception as e:
            logger.warning("health_index_init_failed", error=str(e))

    # ── Phase 40: Observability Gap Detector ──
    if settings.observability_gap_enabled:
        try:
            from shieldops.api.routes import observability_gap as ogd_mod
            from shieldops.observability.observability_gap import ObservabilityGapDetector

            ogd_engine = ObservabilityGapDetector(
                max_records=settings.observability_gap_max_records,
                min_coverage_pct=settings.observability_gap_min_coverage_pct,
            )
            ogd_mod.set_engine(ogd_engine)
            app.include_router(
                ogd_mod.ogd_route,
                prefix=settings.api_prefix,
                tags=["Observability Gap Detector"],
            )
            logger.info("observability_gap_initialized")
        except Exception as e:
            logger.warning("observability_gap_init_failed", error=str(e))

    # ── Phase 40: Capacity Anomaly Detector ──
    if settings.capacity_anomaly_enabled:
        try:
            from shieldops.analytics.capacity_anomaly import CapacityAnomalyDetector
            from shieldops.api.routes import capacity_anomaly as cad_mod

            cad_engine = CapacityAnomalyDetector(
                max_records=settings.capacity_anomaly_max_records,
                min_confidence_pct=settings.capacity_anomaly_min_confidence_pct,
            )
            cad_mod.set_engine(cad_engine)
            app.include_router(
                cad_mod.cad_route,
                prefix=settings.api_prefix,
                tags=["Capacity Anomaly Detector"],
            )
            logger.info("capacity_anomaly_initialized")
        except Exception as e:
            logger.warning("capacity_anomaly_init_failed", error=str(e))

    # ── Phase 40: Change Freeze Manager ──
    if settings.change_freeze_enabled:
        try:
            from shieldops.api.routes import change_freeze as cfm_mod
            from shieldops.changes.change_freeze import ChangeFreezeManager

            cfm_engine = ChangeFreezeManager(
                max_records=settings.change_freeze_max_records,
                max_exception_rate_pct=settings.change_freeze_max_exception_rate_pct,
            )
            cfm_mod.set_engine(cfm_engine)
            app.include_router(
                cfm_mod.cfm_route,
                prefix=settings.api_prefix,
                tags=["Change Freeze Manager"],
            )
            logger.info("change_freeze_initialized")
        except Exception as e:
            logger.warning("change_freeze_init_failed", error=str(e))

    # ── Phase 40: Deployment Pipeline Analyzer ──
    if settings.pipeline_analyzer_enabled:
        try:
            from shieldops.api.routes import pipeline_analyzer as dpa_mod
            from shieldops.changes.pipeline_analyzer import DeploymentPipelineAnalyzer

            dpa_engine = DeploymentPipelineAnalyzer(
                max_records=settings.pipeline_analyzer_max_records,
                max_duration_minutes=settings.pipeline_analyzer_max_duration_minutes,
            )
            dpa_mod.set_engine(dpa_engine)
            app.include_router(
                dpa_mod.dpa_route,
                prefix=settings.api_prefix,
                tags=["Deployment Pipeline Analyzer"],
            )
            logger.info("pipeline_analyzer_initialized")
        except Exception as e:
            logger.warning("pipeline_analyzer_init_failed", error=str(e))

    # ── Phase 40: Release Readiness Checker ──
    if settings.release_readiness_enabled:
        try:
            from shieldops.api.routes import release_readiness as rrc_mod
            from shieldops.changes.release_readiness import ReleaseReadinessChecker

            rrc_engine = ReleaseReadinessChecker(
                max_records=settings.release_readiness_max_records,
                min_score_pct=settings.release_readiness_min_score_pct,
            )
            rrc_mod.set_engine(rrc_engine)
            app.include_router(
                rrc_mod.rrc_route,
                prefix=settings.api_prefix,
                tags=["Release Readiness Checker"],
            )
            logger.info("release_readiness_initialized")
        except Exception as e:
            logger.warning("release_readiness_init_failed", error=str(e))

    # ── Phase 40: Config Validation Engine ──
    if settings.config_validator_enabled:
        try:
            from shieldops.api.routes import config_validator as cvn_mod
            from shieldops.config.config_validator import ConfigValidationEngine

            cvn_engine = ConfigValidationEngine(
                max_records=settings.config_validator_max_records,
                max_failure_rate_pct=settings.config_validator_max_failure_rate_pct,
            )
            cvn_mod.set_engine(cvn_engine)
            app.include_router(
                cvn_mod.cvn_route,
                prefix=settings.api_prefix,
                tags=["Config Validation Engine"],
            )
            logger.info("config_validator_initialized")
        except Exception as e:
            logger.warning("config_validator_init_failed", error=str(e))

    # ── Phase 40: Service Ownership Tracker ──
    if settings.ownership_tracker_enabled:
        try:
            from shieldops.api.routes import ownership_tracker as sot_mod
            from shieldops.topology.ownership_tracker import ServiceOwnershipTracker

            sot_engine = ServiceOwnershipTracker(
                max_records=settings.ownership_tracker_max_records,
                max_orphan_days=settings.ownership_tracker_max_orphan_days,
            )
            sot_mod.set_engine(sot_engine)
            app.include_router(
                sot_mod.sot_route,
                prefix=settings.api_prefix,
                tags=["Service Ownership Tracker"],
            )
            logger.info("ownership_tracker_initialized")
        except Exception as e:
            logger.warning("ownership_tracker_init_failed", error=str(e))

    # ── Phase 41 ────────────────────────────────────────────

    if settings.vendor_lockin_enabled:
        try:
            from shieldops.api.routes import vendor_lockin as vla_mod
            from shieldops.billing.vendor_lockin import VendorLockinAnalyzer

            vla_engine = VendorLockinAnalyzer(
                max_records=settings.vendor_lockin_max_records,
                max_risk_score=settings.vendor_lockin_max_risk_score,
            )
            vla_mod.set_engine(vla_engine)
            app.include_router(
                vla_mod.vla_route,
                prefix=settings.api_prefix,
                tags=["Vendor Lock-in"],
            )
            logger.info("vendor_lockin_initialized")
        except Exception as e:
            logger.warning("vendor_lockin_init_failed", error=str(e))

    if settings.cost_efficiency_enabled:
        try:
            from shieldops.api.routes import cost_efficiency as ces_mod
            from shieldops.billing.cost_efficiency import CostEfficiencyScorer

            ces_engine = CostEfficiencyScorer(
                max_records=settings.cost_efficiency_max_records,
                min_efficiency_pct=settings.cost_efficiency_min_efficiency_pct,
            )
            ces_mod.set_engine(ces_engine)
            app.include_router(
                ces_mod.ces_route,
                prefix=settings.api_prefix,
                tags=["Cost Efficiency"],
            )
            logger.info("cost_efficiency_initialized")
        except Exception as e:
            logger.warning("cost_efficiency_init_failed", error=str(e))

    if settings.budget_variance_enabled:
        try:
            from shieldops.api.routes import budget_variance as bvt_mod
            from shieldops.billing.budget_variance import BudgetVarianceTracker

            bvt_engine = BudgetVarianceTracker(
                max_records=settings.budget_variance_max_records,
                max_variance_pct=settings.budget_variance_max_variance_pct,
            )
            bvt_mod.set_engine(bvt_engine)
            app.include_router(
                bvt_mod.bvt_route,
                prefix=settings.api_prefix,
                tags=["Budget Variance"],
            )
            logger.info("budget_variance_initialized")
        except Exception as e:
            logger.warning("budget_variance_init_failed", error=str(e))

    if settings.evidence_validator_enabled:
        try:
            from shieldops.api.routes import evidence_validator as evl_mod
            from shieldops.compliance.evidence_validator import (
                ComplianceEvidenceValidator,
            )

            evl_engine = ComplianceEvidenceValidator(
                max_records=settings.evidence_validator_max_records,
                min_validity_pct=settings.evidence_validator_min_validity_pct,
            )
            evl_mod.set_engine(evl_engine)
            app.include_router(
                evl_mod.evl_route,
                prefix=settings.api_prefix,
                tags=["Evidence Validator"],
            )
            logger.info("evidence_validator_initialized")
        except Exception as e:
            logger.warning("evidence_validator_init_failed", error=str(e))

    if settings.policy_enforcer_enabled:
        try:
            from shieldops.api.routes import policy_enforcer as pen_mod
            from shieldops.compliance.policy_enforcer import PolicyEnforcementMonitor

            pen_engine = PolicyEnforcementMonitor(
                max_records=settings.policy_enforcer_max_records,
                max_violation_rate_pct=settings.policy_enforcer_max_violation_rate_pct,
            )
            pen_mod.set_engine(pen_engine)
            app.include_router(
                pen_mod.pen_route,
                prefix=settings.api_prefix,
                tags=["Policy Enforcer"],
            )
            logger.info("policy_enforcer_initialized")
        except Exception as e:
            logger.warning("policy_enforcer_init_failed", error=str(e))

    if settings.audit_readiness_enabled:
        try:
            from shieldops.api.routes import audit_readiness as ard_mod
            from shieldops.audit.audit_readiness import AuditReadinessScorer

            ard_engine = AuditReadinessScorer(
                max_records=settings.audit_readiness_max_records,
                min_readiness_pct=settings.audit_readiness_min_readiness_pct,
            )
            ard_mod.set_engine(ard_engine)
            app.include_router(
                ard_mod.ard_route,
                prefix=settings.api_prefix,
                tags=["Audit Readiness"],
            )
            logger.info("audit_readiness_initialized")
        except Exception as e:
            logger.warning("audit_readiness_init_failed", error=str(e))

    if settings.toil_classifier_enabled:
        try:
            from shieldops.api.routes import toil_classifier as tcl_mod
            from shieldops.operations.toil_classifier import OperationalToilClassifier

            tcl_engine = OperationalToilClassifier(
                max_records=settings.toil_classifier_max_records,
                max_toil_hours_weekly=settings.toil_classifier_max_toil_hours_weekly,
            )
            tcl_mod.set_engine(tcl_engine)
            app.include_router(
                tcl_mod.tcl_route,
                prefix=settings.api_prefix,
                tags=["Toil Classifier"],
            )
            logger.info("toil_classifier_initialized")
        except Exception as e:
            logger.warning("toil_classifier_init_failed", error=str(e))

    if settings.governance_scorer_enabled:
        try:
            from shieldops.api.routes import governance_scorer as pgs_mod
            from shieldops.policy.governance_scorer import PlatformGovernanceScorer

            pgs_engine = PlatformGovernanceScorer(
                max_records=settings.governance_scorer_max_records,
                min_governance_score=settings.governance_scorer_min_governance_score,
            )
            pgs_mod.set_engine(pgs_engine)
            app.include_router(
                pgs_mod.pgs_route,
                prefix=settings.api_prefix,
                tags=["Governance Scorer"],
            )
            logger.info("governance_scorer_initialized")
        except Exception as e:
            logger.warning("governance_scorer_init_failed", error=str(e))

    if settings.deprecation_tracker_enabled:
        try:
            from shieldops.api.routes import deprecation_tracker as sdt_mod
            from shieldops.topology.deprecation_tracker import (
                ServiceDeprecationTracker,
            )

            sdt_engine = ServiceDeprecationTracker(
                max_records=settings.deprecation_tracker_max_records,
                max_overdue_days=settings.deprecation_tracker_max_overdue_days,
            )
            sdt_mod.set_engine(sdt_engine)
            app.include_router(
                sdt_mod.sdt_route,
                prefix=settings.api_prefix,
                tags=["Deprecation Tracker"],
            )
            logger.info("deprecation_tracker_initialized")
        except Exception as e:
            logger.warning("deprecation_tracker_init_failed", error=str(e))

    if settings.severity_validator_enabled:
        try:
            from shieldops.api.routes import severity_validator as svl_mod
            from shieldops.incidents.severity_validator import (
                IncidentSeverityValidator,
            )

            svl_engine = IncidentSeverityValidator(
                max_records=settings.severity_validator_max_records,
                min_accuracy_pct=settings.severity_validator_min_accuracy_pct,
            )
            svl_mod.set_engine(svl_engine)
            app.include_router(
                svl_mod.svl_route,
                prefix=settings.api_prefix,
                tags=["Severity Validator"],
            )
            logger.info("severity_validator_initialized")
        except Exception as e:
            logger.warning("severity_validator_init_failed", error=str(e))

    if settings.approval_analyzer_enabled:
        try:
            from shieldops.api.routes import approval_analyzer as caa_mod
            from shieldops.changes.approval_analyzer import ChangeApprovalAnalyzer

            caa_engine = ChangeApprovalAnalyzer(
                max_records=settings.approval_analyzer_max_records,
                max_approval_hours=settings.approval_analyzer_max_approval_hours,
            )
            caa_mod.set_engine(caa_engine)
            app.include_router(
                caa_mod.caa_route,
                prefix=settings.api_prefix,
                tags=["Approval Analyzer"],
            )
            logger.info("approval_analyzer_initialized")
        except Exception as e:
            logger.warning("approval_analyzer_init_failed", error=str(e))

    if settings.slo_compliance_enabled:
        try:
            from shieldops.api.routes import slo_compliance as scc_mod
            from shieldops.sla.slo_compliance import SLOComplianceChecker

            scc_engine = SLOComplianceChecker(
                max_records=settings.slo_compliance_max_records,
                min_compliance_pct=settings.slo_compliance_min_compliance_pct,
            )
            scc_mod.set_engine(scc_engine)
            app.include_router(
                scc_mod.scc_route,
                prefix=settings.api_prefix,
                tags=["SLO Compliance"],
            )
            logger.info("slo_compliance_initialized")
        except Exception as e:
            logger.warning("slo_compliance_init_failed", error=str(e))

    # ── Phase 42 ────────────────────────────────────────────

    if settings.alert_dedup_enabled:
        try:
            from shieldops.api.routes import alert_dedup as ade_mod
            from shieldops.observability.alert_dedup import (
                AlertDeduplicationEngine,
            )

            ade_engine = AlertDeduplicationEngine(
                max_records=settings.alert_dedup_max_records,
                min_dedup_ratio_pct=settings.alert_dedup_min_dedup_ratio_pct,
            )
            ade_mod.set_engine(ade_engine)
            app.include_router(
                ade_mod.ade_route,
                prefix=settings.api_prefix,
                tags=["Alert Dedup"],
            )
            logger.info("alert_dedup_initialized")
        except Exception as e:
            logger.warning("alert_dedup_init_failed", error=str(e))

    if settings.priority_ranker_enabled:
        try:
            from shieldops.api.routes import priority_ranker as ipr_mod
            from shieldops.incidents.priority_ranker import IncidentPriorityRanker

            ipr_engine = IncidentPriorityRanker(
                max_records=settings.priority_ranker_max_records,
                min_accuracy_pct=settings.priority_ranker_min_accuracy_pct,
            )
            ipr_mod.set_engine(ipr_engine)
            app.include_router(
                ipr_mod.ipr_route,
                prefix=settings.api_prefix,
                tags=["Priority Ranker"],
            )
            logger.info("priority_ranker_initialized")
        except Exception as e:
            logger.warning("priority_ranker_init_failed", error=str(e))

    if settings.deploy_frequency_enabled:
        try:
            from shieldops.api.routes import deploy_frequency as dfa_mod
            from shieldops.changes.deploy_frequency import (
                DeploymentFrequencyAnalyzer,
            )

            dfa_engine = DeploymentFrequencyAnalyzer(
                max_records=settings.deploy_frequency_max_records,
                min_deploy_per_week=settings.deploy_frequency_min_deploy_per_week,
            )
            dfa_mod.set_engine(dfa_engine)
            app.include_router(
                dfa_mod.dfa_route,
                prefix=settings.api_prefix,
                tags=["Deploy Frequency"],
            )
            logger.info("deploy_frequency_initialized")
        except Exception as e:
            logger.warning("deploy_frequency_init_failed", error=str(e))

    if settings.infra_cost_allocator_enabled:
        try:
            from shieldops.api.routes import infra_cost_allocator as icalloc_mod
            from shieldops.billing.infra_cost_allocator import (
                InfrastructureCostAllocator,
            )

            icalloc_engine = InfrastructureCostAllocator(
                max_records=settings.infra_cost_allocator_max_records,
                max_unallocated_pct=settings.infra_cost_allocator_max_unallocated_pct,
            )
            icalloc_mod.set_engine(icalloc_engine)
            app.include_router(
                icalloc_mod.ica_route,
                prefix=settings.api_prefix,
                tags=["Infra Cost Allocator"],
            )
            logger.info("infra_cost_allocator_initialized")
        except Exception as e:
            logger.warning("infra_cost_allocator_init_failed", error=str(e))

    if settings.team_velocity_enabled:
        try:
            from shieldops.analytics.team_velocity import TeamVelocityTracker
            from shieldops.api.routes import team_velocity as tvt_mod

            tvt_engine = TeamVelocityTracker(
                max_records=settings.team_velocity_max_records,
                min_velocity_score=settings.team_velocity_min_velocity_score,
            )
            tvt_mod.set_engine(tvt_engine)
            app.include_router(
                tvt_mod.tvt_route,
                prefix=settings.api_prefix,
                tags=["Team Velocity"],
            )
            logger.info("team_velocity_initialized")
        except Exception as e:
            logger.warning("team_velocity_init_failed", error=str(e))

    if settings.comm_mapper_enabled:
        try:
            from shieldops.api.routes import comm_mapper as scm_mod
            from shieldops.topology.comm_mapper import ServiceCommunicationMapper

            scm_engine = ServiceCommunicationMapper(
                max_records=settings.comm_mapper_max_records,
                max_unhealthy_links=settings.comm_mapper_max_unhealthy_links,
            )
            scm_mod.set_engine(scm_engine)
            app.include_router(
                scm_mod.scm_route,
                prefix=settings.api_prefix,
                tags=["Comm Mapper"],
            )
            logger.info("comm_mapper_initialized")
        except Exception as e:
            logger.warning("comm_mapper_init_failed", error=str(e))

    if settings.automation_scorer_enabled:
        try:
            from shieldops.api.routes import automation_scorer as cas_mod
            from shieldops.compliance.automation_scorer import (
                ComplianceAutomationScorer,
            )

            cas_engine = ComplianceAutomationScorer(
                max_records=settings.automation_scorer_max_records,
                min_automation_pct=settings.automation_scorer_min_automation_pct,
            )
            cas_mod.set_engine(cas_engine)
            app.include_router(
                cas_mod.cas_route,
                prefix=settings.api_prefix,
                tags=["Automation Scorer"],
            )
            logger.info("automation_scorer_initialized")
        except Exception as e:
            logger.warning("automation_scorer_init_failed", error=str(e))

    if settings.scaling_advisor_enabled:
        try:
            from shieldops.api.routes import scaling_advisor as psa_mod
            from shieldops.operations.scaling_advisor import PredictiveScalingAdvisor

            psa_engine = PredictiveScalingAdvisor(
                max_records=settings.scaling_advisor_max_records,
                min_confidence_pct=settings.scaling_advisor_min_confidence_pct,
            )
            psa_mod.set_engine(psa_engine)
            app.include_router(
                psa_mod.psa_route,
                prefix=settings.api_prefix,
                tags=["Scaling Advisor"],
            )
            logger.info("scaling_advisor_initialized")
        except Exception as e:
            logger.warning("scaling_advisor_init_failed", error=str(e))

    if settings.error_classifier_enabled:
        try:
            from shieldops.analytics.error_classifier import ErrorPatternClassifier
            from shieldops.api.routes import error_classifier as ecl_mod

            ecl_engine = ErrorPatternClassifier(
                max_records=settings.error_classifier_max_records,
                max_error_rate_pct=settings.error_classifier_max_error_rate_pct,
            )
            ecl_mod.set_engine(ecl_engine)
            app.include_router(
                ecl_mod.ecl_route,
                prefix=settings.api_prefix,
                tags=["Error Classifier"],
            )
            logger.info("error_classifier_initialized")
        except Exception as e:
            logger.warning("error_classifier_init_failed", error=str(e))

    if settings.compliance_bridge_enabled:
        try:
            from shieldops.api.routes import compliance_bridge as scb_mod
            from shieldops.security.compliance_bridge import (
                SecurityComplianceBridge,
            )

            scb_engine = SecurityComplianceBridge(
                max_records=settings.compliance_bridge_max_records,
                min_alignment_pct=settings.compliance_bridge_min_alignment_pct,
            )
            scb_mod.set_engine(scb_engine)
            app.include_router(
                scb_mod.scb_route,
                prefix=settings.api_prefix,
                tags=["Compliance Bridge"],
            )
            logger.info("compliance_bridge_initialized")
        except Exception as e:
            logger.warning("compliance_bridge_init_failed", error=str(e))

    if settings.utilization_scorer_enabled:
        try:
            from shieldops.analytics.utilization_scorer import (
                CapacityUtilizationScorer,
            )
            from shieldops.api.routes import utilization_scorer as cus_mod

            cus_engine = CapacityUtilizationScorer(
                max_records=settings.utilization_scorer_max_records,
                optimal_utilization_pct=settings.utilization_scorer_optimal_utilization_pct,
            )
            cus_mod.set_engine(cus_engine)
            app.include_router(
                cus_mod.cus_route,
                prefix=settings.api_prefix,
                tags=["Utilization Scorer"],
            )
            logger.info("utilization_scorer_initialized")
        except Exception as e:
            logger.warning("utilization_scorer_init_failed", error=str(e))

    if settings.knowledge_linker_enabled:
        try:
            from shieldops.api.routes import knowledge_linker as ikl_mod
            from shieldops.incidents.knowledge_linker import (
                IncidentKnowledgeLinker,
            )

            ikl_engine = IncidentKnowledgeLinker(
                max_records=settings.knowledge_linker_max_records,
                min_relevance_pct=settings.knowledge_linker_min_relevance_pct,
            )
            ikl_mod.set_engine(ikl_engine)
            app.include_router(
                ikl_mod.ikl_route,
                prefix=settings.api_prefix,
                tags=["Knowledge Linker"],
            )
            logger.info("knowledge_linker_initialized")
        except Exception as e:
            logger.warning("knowledge_linker_init_failed", error=str(e))

    # Phase 43: Dependency Vulnerability Mapper
    if settings.dep_vuln_mapper_enabled:
        try:
            from shieldops.api.routes import dep_vuln_mapper as dvm_mod
            from shieldops.topology.dep_vuln_mapper import (
                DependencyVulnerabilityMapper as TopoDependencyVulnMapper,
            )

            dvm_engine = TopoDependencyVulnMapper(
                max_records=settings.dep_vuln_mapper_max_records,
                max_critical_vulns=settings.dep_vuln_mapper_max_critical_vulns,
            )
            dvm_mod.set_engine(dvm_engine)
            app.include_router(
                dvm_mod.dvm_route,
                prefix=settings.api_prefix,
                tags=["Dependency Vulnerability Mapper"],
            )
            logger.info("dep_vuln_mapper_initialized")
        except Exception as e:
            logger.warning("dep_vuln_mapper_init_failed", error=str(e))

    # Phase 43: Incident Trend Forecaster
    if settings.trend_forecaster_enabled:
        try:
            from shieldops.api.routes import trend_forecaster as itf_mod
            from shieldops.incidents.trend_forecaster import IncidentTrendForecaster

            itf_engine = IncidentTrendForecaster(
                max_records=settings.trend_forecaster_max_records,
                max_growth_rate_pct=settings.trend_forecaster_max_growth_rate_pct,
            )
            itf_mod.set_engine(itf_engine)
            app.include_router(
                itf_mod.itf_route,
                prefix=settings.api_prefix,
                tags=["Incident Trend Forecaster"],
            )
            logger.info("trend_forecaster_initialized")
        except Exception as e:
            logger.warning("trend_forecaster_init_failed", error=str(e))

    # Phase 43: Change Risk Predictor
    if settings.risk_predictor_enabled:
        try:
            from shieldops.api.routes import risk_predictor as crp_mod
            from shieldops.changes.risk_predictor import ChangeRiskPredictor

            crp_engine = ChangeRiskPredictor(
                max_records=settings.risk_predictor_max_records,
                max_risk_threshold=settings.risk_predictor_max_risk_threshold,
            )
            crp_mod.set_engine(crp_engine)
            app.include_router(
                crp_mod.crp_route,
                prefix=settings.api_prefix,
                tags=["Change Risk Predictor"],
            )
            logger.info("risk_predictor_initialized")
        except Exception as e:
            logger.warning("risk_predictor_init_failed", error=str(e))

    # Phase 43: Cost Optimization Planner
    if settings.optimization_planner_enabled:
        try:
            from shieldops.api.routes import optimization_planner as cop_mod
            from shieldops.billing.optimization_planner import CostOptimizationPlanner

            cop_engine = CostOptimizationPlanner(
                max_records=settings.optimization_planner_max_records,
                min_savings_pct=settings.optimization_planner_min_savings_pct,
            )
            cop_mod.set_engine(cop_engine)
            app.include_router(
                cop_mod.cop_route,
                prefix=settings.api_prefix,
                tags=["Cost Optimization Planner"],
            )
            logger.info("optimization_planner_initialized")
        except Exception as e:
            logger.warning("optimization_planner_init_failed", error=str(e))

    # Phase 43: Alert Noise Classifier
    if settings.noise_classifier_enabled:
        try:
            from shieldops.api.routes import noise_classifier as anc_mod
            from shieldops.observability.noise_classifier import AlertNoiseClassifier

            anc_engine = AlertNoiseClassifier(
                max_records=settings.noise_classifier_max_records,
                max_noise_ratio_pct=settings.noise_classifier_max_noise_ratio_pct,
            )
            anc_mod.set_engine(anc_engine)
            app.include_router(
                anc_mod.anc_route,
                prefix=settings.api_prefix,
                tags=["Alert Noise Classifier"],
            )
            logger.info("noise_classifier_initialized")
        except Exception as e:
            logger.warning("noise_classifier_init_failed", error=str(e))

    # Phase 43: SLA Impact Analyzer
    if settings.sla_impact_analyzer_enabled:
        try:
            from shieldops.api.routes import sla_impact as sia_mod
            from shieldops.sla.impact_analyzer import SLAImpactAnalyzer

            sia_engine = SLAImpactAnalyzer(
                max_records=settings.sla_impact_analyzer_max_records,
                max_breach_count=settings.sla_impact_analyzer_max_breach_count,
            )
            sia_mod.set_engine(sia_engine)
            app.include_router(
                sia_mod.sia_route,
                prefix=settings.api_prefix,
                tags=["SLA Impact Analyzer"],
            )
            logger.info("sla_impact_analyzer_initialized")
        except Exception as e:
            logger.warning("sla_impact_analyzer_init_failed", error=str(e))

    # Phase 43: Runbook Coverage Analyzer
    if settings.runbook_coverage_enabled:
        try:
            from shieldops.api.routes import runbook_coverage as rca_mod
            from shieldops.operations.runbook_coverage import RunbookCoverageAnalyzer

            rca_engine = RunbookCoverageAnalyzer(
                max_records=settings.runbook_coverage_max_records,
                min_coverage_pct=settings.runbook_coverage_min_coverage_pct,
            )
            rca_mod.set_engine(rca_engine)
            app.include_router(
                rca_mod.rca_route,
                prefix=settings.api_prefix,
                tags=["Runbook Coverage Analyzer"],
            )
            logger.info("runbook_coverage_initialized")
        except Exception as e:
            logger.warning("runbook_coverage_init_failed", error=str(e))

    # Phase 43: Security Posture Benchmarker
    if settings.posture_benchmark_enabled:
        try:
            from shieldops.api.routes import posture_benchmark as spb_mod
            from shieldops.security.posture_benchmark import SecurityPostureBenchmarker

            spb_engine = SecurityPostureBenchmarker(
                max_records=settings.posture_benchmark_max_records,
                min_benchmark_score=settings.posture_benchmark_min_benchmark_score,
            )
            spb_mod.set_engine(spb_engine)
            app.include_router(
                spb_mod.spb_route,
                prefix=settings.api_prefix,
                tags=["Security Posture Benchmarker"],
            )
            logger.info("posture_benchmark_initialized")
        except Exception as e:
            logger.warning("posture_benchmark_init_failed", error=str(e))

    # Phase 43: Team Workload Balancer
    if settings.workload_balancer_enabled:
        try:
            from shieldops.api.routes import workload_balancer as twb_mod
            from shieldops.operations.workload_balancer import TeamWorkloadBalancer

            twb_engine = TeamWorkloadBalancer(
                max_records=settings.workload_balancer_max_records,
                max_imbalance_pct=settings.workload_balancer_max_imbalance_pct,
            )
            twb_mod.set_engine(twb_engine)
            app.include_router(
                twb_mod.twb_route,
                prefix=settings.api_prefix,
                tags=["Team Workload Balancer"],
            )
            logger.info("workload_balancer_initialized")
        except Exception as e:
            logger.warning("workload_balancer_init_failed", error=str(e))

    # Phase 43: Compliance Report Automator
    if settings.report_automator_enabled:
        try:
            from shieldops.api.routes import report_automator as cra_mod
            from shieldops.compliance.report_automator import ComplianceReportAutomator

            cra_engine = ComplianceReportAutomator(
                max_records=settings.report_automator_max_records,
                max_overdue_days=settings.report_automator_max_overdue_days,
            )
            cra_mod.set_engine(cra_engine)
            app.include_router(
                cra_mod.cra_route,
                prefix=settings.api_prefix,
                tags=["Compliance Report Automator"],
            )
            logger.info("report_automator_initialized")
        except Exception as e:
            logger.warning("report_automator_init_failed", error=str(e))

    # Phase 43: Infrastructure Health Scorer
    if settings.infra_health_scorer_enabled:
        try:
            from shieldops.api.routes import infra_health_scorer as ihs_mod
            from shieldops.topology.infra_health_scorer import InfrastructureHealthScorer

            ihs_engine = InfrastructureHealthScorer(
                max_records=settings.infra_health_scorer_max_records,
                min_health_score=settings.infra_health_scorer_min_health_score,
            )
            ihs_mod.set_engine(ihs_engine)
            app.include_router(
                ihs_mod.ihs_route,
                prefix=settings.api_prefix,
                tags=["Infrastructure Health Scorer"],
            )
            logger.info("infra_health_scorer_initialized")
        except Exception as e:
            logger.warning("infra_health_scorer_init_failed", error=str(e))

    # Phase 43: Deployment Impact Predictor
    if settings.impact_predictor_enabled:
        try:
            from shieldops.api.routes import impact_predictor as dip_mod
            from shieldops.changes.impact_predictor import DeploymentImpactPredictor

            dip_engine = DeploymentImpactPredictor(
                max_records=settings.impact_predictor_max_records,
                max_impact_score=settings.impact_predictor_max_impact_score,
            )
            dip_mod.set_engine(dip_engine)
            app.include_router(
                dip_mod.dip_route,
                prefix=settings.api_prefix,
                tags=["Deployment Impact Predictor"],
            )
            logger.info("impact_predictor_initialized")
        except Exception as e:
            logger.warning("impact_predictor_init_failed", error=str(e))

    # --- Phase 44: Incident Response Time Analyzer ---
    if settings.response_time_enabled:
        try:
            from shieldops.api.routes import response_time as rta_mod
            from shieldops.incidents.response_time import (
                IncidentResponseTimeAnalyzer,
            )

            rta_engine = IncidentResponseTimeAnalyzer(
                max_records=settings.response_time_max_records,
                max_response_time_minutes=settings.response_time_max_response_time_minutes,
            )
            rta_mod.set_engine(rta_engine)
            app.include_router(
                rta_mod.rta_route,
                prefix=settings.api_prefix,
                tags=["Response Time"],
            )
            logger.info("response_time_initialized")
        except Exception as e:
            logger.warning("response_time_init_failed", error=str(e))

    # --- Phase 44: Service Dependency Risk Scorer ---
    if settings.service_dep_risk_enabled:
        try:
            from shieldops.api.routes import service_dep_risk as sdr_mod
            from shieldops.topology.service_dep_risk import (
                ServiceDependencyRiskScorer,
            )

            sdr_engine = ServiceDependencyRiskScorer(
                max_records=settings.service_dep_risk_max_records,
                max_risk_score=settings.service_dep_risk_max_risk_score,
            )
            sdr_mod.set_engine(sdr_engine)
            app.include_router(
                sdr_mod.sdr_route,
                prefix=settings.api_prefix,
                tags=["Service Dependency Risk"],
            )
            logger.info("service_dep_risk_initialized")
        except Exception as e:
            logger.warning("service_dep_risk_init_failed", error=str(e))

    # --- Phase 44: Alert Escalation Analyzer ---
    if settings.alert_escalation_enabled:
        try:
            from shieldops.api.routes import alert_escalation as ean_mod
            from shieldops.observability.escalation_analyzer import (
                AlertEscalationAnalyzer,
            )

            ean_engine = AlertEscalationAnalyzer(
                max_records=settings.alert_escalation_max_records,
                max_escalation_rate_pct=settings.alert_escalation_max_escalation_rate_pct,
            )
            ean_mod.set_engine(ean_engine)
            app.include_router(
                ean_mod.ean_route,
                prefix=settings.api_prefix,
                tags=["Alert Escalation"],
            )
            logger.info("alert_escalation_initialized")
        except Exception as e:
            logger.warning("alert_escalation_init_failed", error=str(e))

    # --- Phase 44: Capacity Utilization Optimizer ---
    if settings.capacity_utilizer_enabled:
        try:
            from shieldops.api.routes import capacity_utilizer as cup_mod
            from shieldops.billing.capacity_utilizer import (
                CapacityUtilizationOptimizer,
            )

            cup_engine = CapacityUtilizationOptimizer(
                max_records=settings.capacity_utilizer_max_records,
                optimal_utilization_pct=settings.capacity_utilizer_optimal_utilization_pct,
            )
            cup_mod.set_engine(cup_engine)
            app.include_router(
                cup_mod.cup_route,
                prefix=settings.api_prefix,
                tags=["Capacity Utilization"],
            )
            logger.info("capacity_utilizer_initialized")
        except Exception as e:
            logger.warning("capacity_utilizer_init_failed", error=str(e))

    # --- Phase 44: Change Freeze Validator ---
    if settings.freeze_validator_enabled:
        try:
            from shieldops.api.routes import freeze_validator as cfv_mod
            from shieldops.changes.freeze_validator import (
                ChangeFreezeValidator,
            )

            cfv_engine = ChangeFreezeValidator(
                max_records=settings.freeze_validator_max_records,
                max_violation_rate_pct=settings.freeze_validator_max_violation_rate_pct,
            )
            cfv_mod.set_engine(cfv_engine)
            app.include_router(
                cfv_mod.cfv_route,
                prefix=settings.api_prefix,
                tags=["Change Freeze Validator"],
            )
            logger.info("freeze_validator_initialized")
        except Exception as e:
            logger.warning("freeze_validator_init_failed", error=str(e))

    # --- Phase 44: Platform Availability Tracker ---
    if settings.availability_tracker_enabled:
        try:
            from shieldops.api.routes import availability_tracker as pat_mod
            from shieldops.sla.availability_tracker import (
                PlatformAvailabilityTracker,
            )

            pat_engine = PlatformAvailabilityTracker(
                max_records=settings.availability_tracker_max_records,
                min_availability_pct=settings.availability_tracker_min_availability_pct,
            )
            pat_mod.set_engine(pat_engine)
            app.include_router(
                pat_mod.pat_route,
                prefix=settings.api_prefix,
                tags=["Platform Availability"],
            )
            logger.info("availability_tracker_initialized")
        except Exception as e:
            logger.warning("availability_tracker_init_failed", error=str(e))

    # --- Phase 44: Incident Root Cause Classifier ---
    if settings.root_cause_classifier_enabled:
        try:
            from shieldops.api.routes import root_cause_classifier as rcc2_mod
            from shieldops.incidents.root_cause_classifier import (
                IncidentRootCauseClassifier,
            )

            rcc2_engine = IncidentRootCauseClassifier(
                max_records=settings.root_cause_classifier_max_records,
                min_confidence_pct=settings.root_cause_classifier_min_confidence_pct,
            )
            rcc2_mod.set_engine(rcc2_engine)
            app.include_router(
                rcc2_mod.rcc_route,
                prefix=settings.api_prefix,
                tags=["Root Cause Classifier"],
            )
            logger.info("root_cause_classifier_initialized")
        except Exception as e:
            logger.warning("root_cause_classifier_init_failed", error=str(e))

    # --- Phase 44: Deployment Canary Scorer ---
    if settings.canary_scorer_enabled:
        try:
            from shieldops.api.routes import canary_scorer as dcs_mod
            from shieldops.changes.canary_scorer import (
                DeploymentCanaryScorer,
            )

            dcs_engine = DeploymentCanaryScorer(
                max_records=settings.canary_scorer_max_records,
                min_canary_score=settings.canary_scorer_min_canary_score,
            )
            dcs_mod.set_engine(dcs_engine)
            app.include_router(
                dcs_mod.dcs_route,
                prefix=settings.api_prefix,
                tags=["Canary Scorer"],
            )
            logger.info("canary_scorer_initialized")
        except Exception as e:
            logger.warning("canary_scorer_init_failed", error=str(e))

    # --- Phase 44: Config Drift Monitor ---
    if settings.config_drift_monitor_enabled:
        try:
            from shieldops.api.routes import config_drift_monitor as cdm2_mod
            from shieldops.operations.config_drift_monitor import (
                ConfigDriftMonitor,
            )

            cdm2_engine = ConfigDriftMonitor(
                max_records=settings.config_drift_monitor_max_records,
                max_drift_count=settings.config_drift_monitor_max_drift_count,
            )
            cdm2_mod.set_engine(cdm2_engine)
            app.include_router(
                cdm2_mod.cdm_route,
                prefix=settings.api_prefix,
                tags=["Config Drift Monitor"],
            )
            logger.info("config_drift_monitor_initialized")
        except Exception as e:
            logger.warning("config_drift_monitor_init_failed", error=str(e))

    # --- Phase 44: Security Compliance Mapper ---
    if settings.compliance_mapper_enabled:
        try:
            from shieldops.api.routes import compliance_mapper as scm2_mod
            from shieldops.security.compliance_mapper import (
                SecurityComplianceMapper,
            )

            scm2_engine = SecurityComplianceMapper(
                max_records=settings.compliance_mapper_max_records,
                min_compliance_score=settings.compliance_mapper_min_compliance_score,
            )
            scm2_mod.set_engine(scm2_engine)
            app.include_router(
                scm2_mod.scm2_route,
                prefix=settings.api_prefix,
                tags=["Security Compliance Mapper"],
            )
            logger.info("compliance_mapper_initialized")
        except Exception as e:
            logger.warning("compliance_mapper_init_failed", error=str(e))

    # --- Phase 44: Team On-Call Equity Analyzer ---
    if settings.oncall_equity_enabled:
        try:
            from shieldops.api.routes import oncall_equity as oce_mod
            from shieldops.operations.oncall_equity import (
                TeamOnCallEquityAnalyzer,
            )

            oce_engine = TeamOnCallEquityAnalyzer(
                max_records=settings.oncall_equity_max_records,
                max_inequity_pct=settings.oncall_equity_max_inequity_pct,
            )
            oce_mod.set_engine(oce_engine)
            app.include_router(
                oce_mod.oce_route,
                prefix=settings.api_prefix,
                tags=["On-Call Equity"],
            )
            logger.info("oncall_equity_initialized")
        except Exception as e:
            logger.warning("oncall_equity_init_failed", error=str(e))

    # --- Phase 45: Incident Clustering Engine ---
    if settings.incident_cluster_enabled:
        try:
            from shieldops.api.routes import incident_cluster as icr_mod
            from shieldops.incidents.incident_cluster import (
                IncidentClusterEngine,
            )

            icr_engine = IncidentClusterEngine(
                max_records=settings.incident_cluster_max_records,
                min_cluster_confidence=settings.incident_cluster_min_cluster_confidence,
            )
            icr_mod.set_engine(icr_engine)
            app.include_router(
                icr_mod.icr_route,
                prefix=settings.api_prefix,
                tags=["Incident Cluster"],
            )
            logger.info("incident_cluster_initialized")
        except Exception as e:
            logger.warning("incident_cluster_init_failed", error=str(e))

    # --- Phase 45: Dependency Latency Tracker ---
    if settings.dep_latency_enabled:
        try:
            from shieldops.api.routes import dep_latency as dlt_mod
            from shieldops.topology.dep_latency import (
                DependencyLatencyTracker,
            )

            dlt_engine = DependencyLatencyTracker(
                max_records=settings.dep_latency_max_records,
                max_latency_ms=settings.dep_latency_max_latency_ms,
            )
            dlt_mod.set_engine(dlt_engine)
            app.include_router(
                dlt_mod.dlt_route,
                prefix=settings.api_prefix,
                tags=["Dependency Latency"],
            )
            logger.info("dep_latency_initialized")
        except Exception as e:
            logger.warning("dep_latency_init_failed", error=str(e))

    # --- Phase 45: Alert Suppression Manager ---
    if settings.suppression_mgr_enabled:
        try:
            from shieldops.api.routes import (
                suppression_manager as asn_mod,
            )
            from shieldops.observability.suppression_manager import (
                AlertSuppressionManager,
            )

            asn_engine = AlertSuppressionManager(
                max_records=settings.suppression_mgr_max_records,
                max_suppression_rate_pct=settings.suppression_mgr_max_suppression_rate_pct,
            )
            asn_mod.set_engine(asn_engine)
            app.include_router(
                asn_mod.asn_route,
                prefix=settings.api_prefix,
                tags=["Suppression Manager"],
            )
            logger.info("suppression_mgr_initialized")
        except Exception as e:
            logger.warning("suppression_mgr_init_failed", error=str(e))

    # --- Phase 45: Cost Trend Forecaster ---
    if settings.cost_trend_enabled:
        try:
            from shieldops.api.routes import cost_trend as ctf_mod
            from shieldops.billing.cost_trend import (
                CostTrendForecaster,
            )

            ctf_engine = CostTrendForecaster(
                max_records=settings.cost_trend_max_records,
                max_growth_rate_pct=settings.cost_trend_max_growth_rate_pct,
            )
            ctf_mod.set_engine(ctf_engine)
            app.include_router(
                ctf_mod.ctf_route,
                prefix=settings.api_prefix,
                tags=["Cost Trend"],
            )
            logger.info("cost_trend_initialized")
        except Exception as e:
            logger.warning("cost_trend_init_failed", error=str(e))

    # --- Phase 45: Change Batch Analyzer ---
    if settings.batch_analyzer_enabled:
        try:
            from shieldops.api.routes import batch_analyzer as cba_mod
            from shieldops.changes.batch_analyzer import (
                ChangeBatchAnalyzer,
            )

            cba_engine = ChangeBatchAnalyzer(
                max_records=settings.batch_analyzer_max_records,
                max_batch_risk_score=settings.batch_analyzer_max_batch_risk_score,
            )
            cba_mod.set_engine(cba_engine)
            app.include_router(
                cba_mod.cba_route,
                prefix=settings.api_prefix,
                tags=["Change Batch Analyzer"],
            )
            logger.info("batch_analyzer_initialized")
        except Exception as e:
            logger.warning("batch_analyzer_init_failed", error=str(e))

    # --- Phase 45: SLO Alignment Validator ---
    if settings.slo_alignment_enabled:
        try:
            from shieldops.api.routes import slo_alignment as sal_mod
            from shieldops.sla.slo_alignment import (
                SLOAlignmentValidator,
            )

            sal_engine = SLOAlignmentValidator(
                max_records=settings.slo_alignment_max_records,
                min_alignment_score=settings.slo_alignment_min_alignment_score,
            )
            sal_mod.set_engine(sal_engine)
            app.include_router(
                sal_mod.sal_route,
                prefix=settings.api_prefix,
                tags=["SLO Alignment"],
            )
            logger.info("slo_alignment_initialized")
        except Exception as e:
            logger.warning("slo_alignment_init_failed", error=str(e))

    # --- Phase 45: Runbook Execution Tracker ---
    if settings.runbook_exec_tracker_enabled:
        try:
            from shieldops.api.routes import (
                runbook_exec_tracker as ret_mod,
            )
            from shieldops.operations.runbook_exec_tracker import (
                RunbookExecutionTracker as OpsRunbookExecTracker,
            )

            ret_engine = OpsRunbookExecTracker(
                max_records=settings.runbook_exec_tracker_max_records,
                min_success_rate_pct=settings.runbook_exec_tracker_min_success_rate_pct,
            )
            ret_mod.set_engine(ret_engine)
            app.include_router(
                ret_mod.ret_route,
                prefix=settings.api_prefix,
                tags=["Runbook Execution Tracker"],
            )
            logger.info("runbook_exec_tracker_initialized")
        except Exception as e:
            logger.warning("runbook_exec_tracker_init_failed", error=str(e))

    # --- Phase 45: Threat Intelligence Correlator ---
    if settings.threat_correlator_enabled:
        try:
            from shieldops.api.routes import (
                threat_correlator as tic_mod,
            )
            from shieldops.security.threat_correlator import (
                ThreatIntelligenceCorrelator,
            )

            tic_engine = ThreatIntelligenceCorrelator(
                max_records=settings.threat_correlator_max_records,
                min_relevance_score=settings.threat_correlator_min_relevance_score,
            )
            tic_mod.set_engine(tic_engine)
            app.include_router(
                tic_mod.tic_route,
                prefix=settings.api_prefix,
                tags=["Threat Correlator"],
            )
            logger.info("threat_correlator_initialized")
        except Exception as e:
            logger.warning("threat_correlator_init_failed", error=str(e))

    # --- Phase 45: Knowledge Freshness Monitor ---
    if settings.freshness_monitor_enabled:
        try:
            from shieldops.api.routes import (
                freshness_monitor as kfm_mod,
            )
            from shieldops.knowledge.freshness_monitor import (
                KnowledgeFreshnessMonitor,
            )

            kfm_engine = KnowledgeFreshnessMonitor(
                max_records=settings.freshness_monitor_max_records,
                max_stale_days=settings.freshness_monitor_max_stale_days,
            )
            kfm_mod.set_engine(kfm_engine)
            app.include_router(
                kfm_mod.kfm_route,
                prefix=settings.api_prefix,
                tags=["Knowledge Freshness"],
            )
            logger.info("freshness_monitor_initialized")
        except Exception as e:
            logger.warning("freshness_monitor_init_failed", error=str(e))

    # --- Phase 45: Compliance Control Tester ---
    if settings.control_tester_enabled:
        try:
            from shieldops.api.routes import (
                control_tester as cct_mod,
            )
            from shieldops.compliance.control_tester import (
                ComplianceControlTester,
            )

            cct_engine = ComplianceControlTester(
                max_records=settings.control_tester_max_records,
                min_pass_rate_pct=settings.control_tester_min_pass_rate_pct,
            )
            cct_mod.set_engine(cct_engine)
            app.include_router(
                cct_mod.cct_route,
                prefix=settings.api_prefix,
                tags=["Control Tester"],
            )
            logger.info("control_tester_initialized")
        except Exception as e:
            logger.warning("control_tester_init_failed", error=str(e))

    # --- Phase 45: Capacity Bottleneck Detector ---
    if settings.bottleneck_detector_enabled:
        try:
            from shieldops.analytics.bottleneck_detector import (
                CapacityBottleneckDetector,
            )
            from shieldops.api.routes import (
                bottleneck_detector as cbd_mod,
            )

            cbd_engine = CapacityBottleneckDetector(
                max_records=settings.bottleneck_detector_max_records,
                critical_utilization_pct=settings.bottleneck_detector_critical_utilization_pct,
            )
            cbd_mod.set_engine(cbd_engine)
            app.include_router(
                cbd_mod.cbd_route,
                prefix=settings.api_prefix,
                tags=["Bottleneck Detector"],
            )
            logger.info("bottleneck_detector_initialized")
        except Exception as e:
            logger.warning("bottleneck_detector_init_failed", error=str(e))

    # --- Phase 45: Metric Anomaly Scorer ---
    if settings.anomaly_scorer_enabled:
        try:
            from shieldops.analytics.anomaly_scorer import (
                MetricAnomalyScorer,
            )
            from shieldops.api.routes import anomaly_scorer as mas_mod

            mas_engine = MetricAnomalyScorer(
                max_records=settings.anomaly_scorer_max_records,
                min_anomaly_score=settings.anomaly_scorer_min_anomaly_score,
            )
            mas_mod.set_engine(mas_engine)
            app.include_router(
                mas_mod.mas_route,
                prefix=settings.api_prefix,
                tags=["Anomaly Scorer"],
            )
            logger.info("anomaly_scorer_initialized")
        except Exception as e:
            logger.warning("anomaly_scorer_init_failed", error=str(e))

    # -- Phase 46: Incident Noise Filter --
    if settings.noise_filter_enabled:
        try:
            from shieldops.api.routes import noise_filter as inf_mod
            from shieldops.incidents.noise_filter import (
                IncidentNoiseFilter,
            )

            _inf_engine = IncidentNoiseFilter(
                max_records=settings.noise_filter_max_records,
                max_false_alarm_rate_pct=settings.noise_filter_max_false_alarm_rate_pct,
            )
            inf_mod.set_engine(_inf_engine)
            app.include_router(
                inf_mod.inf_route,
                prefix=settings.api_prefix,
                tags=["Noise Filter"],
            )
            logger.info("noise_filter_initialized")
        except Exception as e:
            logger.warning("noise_filter_init_failed", error=str(e))

    # -- Phase 46: Service Dependency Validator --
    if settings.dep_validator_enabled:
        try:
            from shieldops.api.routes import dep_validator as dvl_mod
            from shieldops.topology.dep_validator import (
                ServiceDependencyValidator,
            )

            _dvl_engine = ServiceDependencyValidator(
                max_records=settings.dep_validator_max_records,
                max_invalid_pct=settings.dep_validator_max_invalid_pct,
            )
            dvl_mod.set_engine(_dvl_engine)
            app.include_router(
                dvl_mod.dvl_route,
                prefix=settings.api_prefix,
                tags=["Dependency Validator"],
            )
            logger.info("dep_validator_initialized")
        except Exception as e:
            logger.warning("dep_validator_init_failed", error=str(e))

    # -- Phase 46: Alert Priority Optimizer --
    if settings.alert_priority_enabled:
        try:
            from shieldops.api.routes import alert_priority as apo_mod
            from shieldops.observability.alert_priority import (
                AlertPriorityOptimizer,
            )

            _apo_engine = AlertPriorityOptimizer(
                max_records=settings.alert_priority_max_records,
                max_misalignment_pct=settings.alert_priority_max_misalignment_pct,
            )
            apo_mod.set_engine(_apo_engine)
            app.include_router(
                apo_mod.apo_route,
                prefix=settings.api_prefix,
                tags=["Alert Priority"],
            )
            logger.info("alert_priority_initialized")
        except Exception as e:
            logger.warning("alert_priority_init_failed", error=str(e))

    # -- Phase 46: Cost Allocation Validator --
    if settings.cost_alloc_validator_enabled:
        try:
            from shieldops.api.routes import cost_alloc_validator as cav_mod
            from shieldops.billing.cost_alloc_validator import (
                CostAllocationValidator,
            )

            _cav_engine = CostAllocationValidator(
                max_records=settings.cost_alloc_validator_max_records,
                max_variance_pct=settings.cost_alloc_validator_max_variance_pct,
            )
            cav_mod.set_engine(_cav_engine)
            app.include_router(
                cav_mod.cav_route,
                prefix=settings.api_prefix,
                tags=["Cost Allocation Validator"],
            )
            logger.info("cost_alloc_validator_initialized")
        except Exception as e:
            logger.warning("cost_alloc_validator_init_failed", error=str(e))

    # -- Phase 46: Change Correlation Engine --
    if settings.change_correlator_enabled:
        try:
            from shieldops.api.routes import change_correlator as ccr_mod
            from shieldops.changes.change_correlator import (
                ChangeCorrelationEngine,
            )

            _ccr_engine = ChangeCorrelationEngine(
                max_records=settings.change_correlator_max_records,
                min_correlation_strength_pct=settings.change_correlator_min_correlation_strength_pct,
            )
            ccr_mod.set_engine(_ccr_engine)
            app.include_router(
                ccr_mod.ccr_route,
                prefix=settings.api_prefix,
                tags=["Change Correlator"],
            )
            logger.info("change_correlator_initialized")
        except Exception as e:
            logger.warning("change_correlator_init_failed", error=str(e))

    # -- Phase 46: SLO Dependency Mapper --
    if settings.slo_dep_mapper_enabled:
        try:
            from shieldops.api.routes import slo_dep_mapper as sdm_mod
            from shieldops.sla.slo_dep_mapper import (
                SLODependencyMapper,
            )

            _sdm_engine = SLODependencyMapper(
                max_records=settings.slo_dep_mapper_max_records,
                min_slo_target_pct=settings.slo_dep_mapper_min_slo_target_pct,
            )
            sdm_mod.set_engine(_sdm_engine)
            app.include_router(
                sdm_mod.sdm_route,
                prefix=settings.api_prefix,
                tags=["SLO Dependency Mapper"],
            )
            logger.info("slo_dep_mapper_initialized")
        except Exception as e:
            logger.warning("slo_dep_mapper_init_failed", error=str(e))

    # -- Phase 46: Operational Metric Aggregator --
    if settings.metric_aggregator_enabled:
        try:
            from shieldops.api.routes import metric_aggregator as oma_mod
            from shieldops.operations.metric_aggregator import (
                OperationalMetricAggregator,
            )

            _oma_engine = OperationalMetricAggregator(
                max_records=settings.metric_aggregator_max_records,
                min_metric_health_pct=settings.metric_aggregator_min_metric_health_pct,
            )
            oma_mod.set_engine(_oma_engine)
            app.include_router(
                oma_mod.oma_route,
                prefix=settings.api_prefix,
                tags=["Metric Aggregator"],
            )
            logger.info("metric_aggregator_initialized")
        except Exception as e:
            logger.warning("metric_aggregator_init_failed", error=str(e))

    # -- Phase 46: Security Event Correlator --
    if settings.security_event_correlator_enabled:
        try:
            from shieldops.api.routes import event_correlator as sec_mod
            from shieldops.security.event_correlator import (
                SecurityEventCorrelator,
            )

            _sec_engine = SecurityEventCorrelator(
                max_records=settings.security_event_correlator_max_records,
                min_threat_confidence_pct=settings.security_event_correlator_min_threat_confidence_pct,
            )
            sec_mod.set_engine(_sec_engine)
            app.include_router(
                sec_mod.sec_route,
                prefix=settings.api_prefix,
                tags=["Event Correlator"],
            )
            logger.info("security_event_correlator_initialized")
        except Exception as e:
            logger.warning("security_event_correlator_init_failed", error=str(e))

    # -- Phase 46: Knowledge Search Optimizer --
    if settings.knowledge_search_enabled:
        try:
            from shieldops.api.routes import search_optimizer as kso_mod
            from shieldops.knowledge.search_optimizer import (
                KnowledgeSearchOptimizer,
            )

            _kso_engine = KnowledgeSearchOptimizer(
                max_records=settings.knowledge_search_max_records,
                min_relevance_score=settings.knowledge_search_min_relevance_score,
            )
            kso_mod.set_engine(_kso_engine)
            app.include_router(
                kso_mod.kso_route,
                prefix=settings.api_prefix,
                tags=["Search Optimizer"],
            )
            logger.info("knowledge_search_initialized")
        except Exception as e:
            logger.warning("knowledge_search_init_failed", error=str(e))

    # -- Phase 46: Compliance Evidence Consolidator --
    if settings.evidence_consolidator_enabled:
        try:
            from shieldops.api.routes import evidence_consolidator as ecn_mod
            from shieldops.compliance.evidence_consolidator import (
                ComplianceEvidenceConsolidator,
            )

            _ecn_engine = ComplianceEvidenceConsolidator(
                max_records=settings.evidence_consolidator_max_records,
                min_completeness_pct=settings.evidence_consolidator_min_completeness_pct,
            )
            ecn_mod.set_engine(_ecn_engine)
            app.include_router(
                ecn_mod.ecn_route,
                prefix=settings.api_prefix,
                tags=["Evidence Consolidator"],
            )
            logger.info("evidence_consolidator_initialized")
        except Exception as e:
            logger.warning("evidence_consolidator_init_failed", error=str(e))

    # -- Phase 46: Service Latency Analyzer --
    if settings.service_latency_enabled:
        try:
            from shieldops.analytics.service_latency import (
                ServiceLatencyAnalyzer,
            )
            from shieldops.api.routes import service_latency as slt_mod

            _slt_engine = ServiceLatencyAnalyzer(
                max_records=settings.service_latency_max_records,
                max_latency_threshold_ms=settings.service_latency_max_latency_threshold_ms,
            )
            slt_mod.set_engine(_slt_engine)
            app.include_router(
                slt_mod.slt_route,
                prefix=settings.api_prefix,
                tags=["Service Latency"],
            )
            logger.info("service_latency_initialized")
        except Exception as e:
            logger.warning("service_latency_init_failed", error=str(e))

    # -- Phase 46: Audit Compliance Reporter --
    if settings.audit_compliance_reporter_enabled:
        try:
            from shieldops.api.routes import compliance_reporter as acr_mod
            from shieldops.audit.compliance_reporter import (
                AuditComplianceReporter,
            )

            _acr_engine = AuditComplianceReporter(
                max_records=settings.audit_compliance_reporter_max_records,
                min_compliance_score=settings.audit_compliance_reporter_min_compliance_score,
            )
            acr_mod.set_engine(_acr_engine)
            app.include_router(
                acr_mod.acr_route,
                prefix=settings.api_prefix,
                tags=["Compliance Reporter"],
            )
            logger.info("audit_compliance_reporter_initialized")
        except Exception as e:
            logger.warning("audit_compliance_reporter_init_failed", error=str(e))

    # -- Phase 47: Incident Response Optimizer --
    if settings.response_optimizer_enabled:
        try:
            from shieldops.api.routes import response_optimizer as iro_mod
            from shieldops.incidents.response_optimizer import (
                IncidentResponseOptimizer,
            )

            _iro_engine = IncidentResponseOptimizer(
                max_records=settings.response_optimizer_max_records,
                max_response_time_minutes=settings.response_optimizer_max_response_time_minutes,
            )
            iro_mod.set_engine(_iro_engine)
            app.include_router(
                iro_mod.iro_route,
                prefix=settings.api_prefix,
                tags=["Response Optimizer"],
            )
            logger.info("response_optimizer_initialized")
        except Exception as e:
            logger.warning("response_optimizer_init_failed", error=str(e))

    # -- Phase 47: Dependency Change Tracker --
    if settings.dep_change_tracker_enabled:
        try:
            from shieldops.api.routes import dep_change_tracker as dct_mod
            from shieldops.topology.dep_change_tracker import (
                DependencyChangeTracker,
            )

            _dct_engine = DependencyChangeTracker(
                max_records=settings.dep_change_tracker_max_records,
                max_breaking_change_pct=settings.dep_change_tracker_max_breaking_change_pct,
            )
            dct_mod.set_engine(_dct_engine)
            app.include_router(
                dct_mod.dct_route,
                prefix=settings.api_prefix,
                tags=["Dependency Change Tracker"],
            )
            logger.info("dep_change_tracker_initialized")
        except Exception as e:
            logger.warning("dep_change_tracker_init_failed", error=str(e))

    # -- Phase 47: Alert Correlation Optimizer --
    if settings.alert_correlation_opt_enabled:
        try:
            from shieldops.api.routes import alert_correlation_opt as aco_mod
            from shieldops.observability.alert_correlation_opt import (
                AlertCorrelationOptimizer,
            )

            _aco_engine = AlertCorrelationOptimizer(
                max_records=settings.alert_correlation_opt_max_records,
                min_correlation_strength=settings.alert_correlation_opt_min_correlation_strength,
            )
            aco_mod.set_engine(_aco_engine)
            app.include_router(
                aco_mod.aco_route,
                prefix=settings.api_prefix,
                tags=["Alert Correlation Optimizer"],
            )
            logger.info("alert_correlation_opt_initialized")
        except Exception as e:
            logger.warning("alert_correlation_opt_init_failed", error=str(e))

    # -- Phase 47: Cost Forecast Validator --
    if settings.forecast_validator_enabled:
        try:
            from shieldops.api.routes import forecast_validator as fvl_mod
            from shieldops.billing.forecast_validator import (
                CostForecastValidator,
            )

            _fvl_engine = CostForecastValidator(
                max_records=settings.forecast_validator_max_records,
                max_forecast_error_pct=settings.forecast_validator_max_forecast_error_pct,
            )
            fvl_mod.set_engine(_fvl_engine)
            app.include_router(
                fvl_mod.fvl_route,
                prefix=settings.api_prefix,
                tags=["Forecast Validator"],
            )
            logger.info("forecast_validator_initialized")
        except Exception as e:
            logger.warning("forecast_validator_init_failed", error=str(e))

    # -- Phase 47: Deployment Rollback Tracker --
    if settings.rollback_tracker_enabled:
        try:
            from shieldops.api.routes import rollback_tracker as rbt_mod
            from shieldops.changes.rollback_tracker import (
                DeploymentRollbackTracker,
            )

            _rbt_engine = DeploymentRollbackTracker(
                max_records=settings.rollback_tracker_max_records,
                max_rollback_rate_pct=settings.rollback_tracker_max_rollback_rate_pct,
            )
            rbt_mod.set_engine(_rbt_engine)
            app.include_router(
                rbt_mod.rbt_route,
                prefix=settings.api_prefix,
                tags=["Rollback Tracker"],
            )
            logger.info("rollback_tracker_initialized")
        except Exception as e:
            logger.warning("rollback_tracker_init_failed", error=str(e))

    # -- Phase 47: SLO Health Dashboard --
    if settings.slo_health_enabled:
        try:
            from shieldops.api.routes import slo_health as shd_mod
            from shieldops.sla.slo_health import SLOHealthDashboard

            _shd_engine = SLOHealthDashboard(
                max_records=settings.slo_health_max_records,
                min_health_score=settings.slo_health_min_health_score,
            )
            shd_mod.set_engine(_shd_engine)
            app.include_router(
                shd_mod.shd_route,
                prefix=settings.api_prefix,
                tags=["SLO Health"],
            )
            logger.info("slo_health_initialized")
        except Exception as e:
            logger.warning("slo_health_init_failed", error=str(e))

    # -- Phase 47: Runbook Compliance Checker --
    if settings.runbook_compliance_enabled:
        try:
            from shieldops.api.routes import runbook_compliance as rcp_mod
            from shieldops.operations.runbook_compliance import (
                RunbookComplianceChecker,
            )

            _rcp_engine = RunbookComplianceChecker(
                max_records=settings.runbook_compliance_max_records,
                min_compliance_pct=settings.runbook_compliance_min_compliance_pct,
            )
            rcp_mod.set_engine(_rcp_engine)
            app.include_router(
                rcp_mod.rcp_route,
                prefix=settings.api_prefix,
                tags=["Runbook Compliance"],
            )
            logger.info("runbook_compliance_initialized")
        except Exception as e:
            logger.warning("runbook_compliance_init_failed", error=str(e))

    # -- Phase 47: Vulnerability Prioritizer --
    if settings.vuln_prioritizer_enabled:
        try:
            from shieldops.api.routes import vuln_prioritizer as vpr_mod
            from shieldops.security.vuln_prioritizer import (
                VulnerabilityPrioritizer,
            )

            _vpr_engine = VulnerabilityPrioritizer(
                max_records=settings.vuln_prioritizer_max_records,
                critical_cvss_threshold=settings.vuln_prioritizer_critical_cvss_threshold,
            )
            vpr_mod.set_engine(_vpr_engine)
            app.include_router(
                vpr_mod.vpr_route,
                prefix=settings.api_prefix,
                tags=["Vulnerability Prioritizer"],
            )
            logger.info("vuln_prioritizer_initialized")
        except Exception as e:
            logger.warning("vuln_prioritizer_init_failed", error=str(e))

    # -- Phase 47: Knowledge Usage Analyzer --
    if settings.usage_analyzer_enabled:
        try:
            from shieldops.api.routes import usage_analyzer as kua_mod
            from shieldops.knowledge.usage_analyzer import (
                KnowledgeUsageAnalyzer,
            )

            _kua_engine = KnowledgeUsageAnalyzer(
                max_records=settings.usage_analyzer_max_records,
                min_usage_score=settings.usage_analyzer_min_usage_score,
            )
            kua_mod.set_engine(_kua_engine)
            app.include_router(
                kua_mod.kua_route,
                prefix=settings.api_prefix,
                tags=["Usage Analyzer"],
            )
            logger.info("usage_analyzer_initialized")
        except Exception as e:
            logger.warning("usage_analyzer_init_failed", error=str(e))

    # -- Phase 47: Compliance Risk Scorer --
    if settings.compliance_risk_scorer_enabled:
        try:
            from shieldops.api.routes import risk_scorer as crs_mod
            from shieldops.compliance.risk_scorer import ComplianceRiskScorer

            _crs_engine = ComplianceRiskScorer(
                max_records=settings.compliance_risk_scorer_max_records,
                max_risk_score=settings.compliance_risk_scorer_max_risk_score,
            )
            crs_mod.set_engine(_crs_engine)
            app.include_router(
                crs_mod.crs_route,
                prefix=settings.api_prefix,
                tags=["Compliance Risk Scorer"],
            )
            logger.info("compliance_risk_scorer_initialized")
        except Exception as e:
            logger.warning("compliance_risk_scorer_init_failed", error=str(e))

    # -- Phase 47: Performance Benchmark Tracker --
    if settings.perf_benchmark_enabled:
        try:
            from shieldops.analytics.perf_benchmark import (
                PerformanceBenchmarkTracker,
            )
            from shieldops.api.routes import perf_benchmark as pbt_mod

            _pbt_engine = PerformanceBenchmarkTracker(
                max_records=settings.perf_benchmark_max_records,
                max_regression_pct=settings.perf_benchmark_max_regression_pct,
            )
            pbt_mod.set_engine(_pbt_engine)
            app.include_router(
                pbt_mod.pbt_route,
                prefix=settings.api_prefix,
                tags=["Performance Benchmark"],
            )
            logger.info("perf_benchmark_initialized")
        except Exception as e:
            logger.warning("perf_benchmark_init_failed", error=str(e))

    # -- Phase 47: Audit Evidence Tracker --
    if settings.evidence_tracker_enabled:
        try:
            from shieldops.api.routes import evidence_tracker as aet_mod
            from shieldops.audit.evidence_tracker import AuditEvidenceTracker

            _aet_engine = AuditEvidenceTracker(
                max_records=settings.evidence_tracker_max_records,
                min_completeness_pct=settings.evidence_tracker_min_completeness_pct,
            )
            aet_mod.set_engine(_aet_engine)
            app.include_router(
                aet_mod.aet_route,
                prefix=settings.api_prefix,
                tags=["Evidence Tracker"],
            )
            logger.info("evidence_tracker_initialized")
        except Exception as e:
            logger.warning("evidence_tracker_init_failed", error=str(e))

    # -- Phase 48: Triage Quality Analyzer --
    if settings.triage_quality_enabled:
        try:
            from shieldops.api.routes import triage_quality as tqa_mod
            from shieldops.incidents.triage_quality import TriageQualityAnalyzer

            _tqa_engine = TriageQualityAnalyzer(
                max_records=settings.triage_quality_max_records,
                min_triage_quality_pct=settings.triage_quality_min_triage_quality_pct,
            )
            tqa_mod.set_engine(_tqa_engine)
            app.include_router(
                tqa_mod.tqa_route,
                prefix=settings.api_prefix,
                tags=["Triage Quality"],
            )
            logger.info("triage_quality_initialized")
        except Exception as e:
            logger.warning("triage_quality_init_failed", error=str(e))

    # -- Phase 48: Service Health Trend Analyzer --
    if settings.health_trend_enabled:
        try:
            from shieldops.api.routes import health_trend as sht_mod
            from shieldops.topology.health_trend import (
                ServiceHealthTrendAnalyzer,
            )

            _sht_engine = ServiceHealthTrendAnalyzer(
                max_records=settings.health_trend_max_records,
                min_health_trend_score=settings.health_trend_min_health_trend_score,
            )
            sht_mod.set_engine(_sht_engine)
            app.include_router(
                sht_mod.sht_route,
                prefix=settings.api_prefix,
                tags=["Health Trend"],
            )
            logger.info("health_trend_initialized")
        except Exception as e:
            logger.warning("health_trend_init_failed", error=str(e))

    # -- Phase 48: Metric Quality Scorer --
    if settings.metric_quality_enabled:
        try:
            from shieldops.api.routes import metric_quality as mqs_mod
            from shieldops.observability.metric_quality import MetricQualityScorer

            _mqs_engine = MetricQualityScorer(
                max_records=settings.metric_quality_max_records,
                min_metric_quality_pct=settings.metric_quality_min_metric_quality_pct,
            )
            mqs_mod.set_engine(_mqs_engine)
            app.include_router(
                mqs_mod.mqs_route,
                prefix=settings.api_prefix,
                tags=["Metric Quality"],
            )
            logger.info("metric_quality_initialized")
        except Exception as e:
            logger.warning("metric_quality_init_failed", error=str(e))

    # -- Phase 48: Invoice Validation Engine --
    if settings.invoice_validator_enabled:
        try:
            from shieldops.api.routes import invoice_validator as ivl_mod
            from shieldops.billing.invoice_validator import (
                InvoiceValidationEngine,
            )

            _ivl_engine = InvoiceValidationEngine(
                max_records=settings.invoice_validator_max_records,
                max_discrepancy_pct=settings.invoice_validator_max_discrepancy_pct,
            )
            ivl_mod.set_engine(_ivl_engine)
            app.include_router(
                ivl_mod.ivl_route,
                prefix=settings.api_prefix,
                tags=["Invoice Validator"],
            )
            logger.info("invoice_validator_initialized")
        except Exception as e:
            logger.warning("invoice_validator_init_failed", error=str(e))

    # -- Phase 48: Deployment Stability Tracker --
    if settings.deploy_stability_enabled:
        try:
            from shieldops.api.routes import deploy_stability as dst_mod
            from shieldops.changes.deploy_stability import (
                DeploymentStabilityTracker,
            )

            _dst_engine = DeploymentStabilityTracker(
                max_records=settings.deploy_stability_max_records,
                min_stability_score=settings.deploy_stability_min_stability_score,
            )
            dst_mod.set_engine(_dst_engine)
            app.include_router(
                dst_mod.dst_route,
                prefix=settings.api_prefix,
                tags=["Deploy Stability"],
            )
            logger.info("deploy_stability_initialized")
        except Exception as e:
            logger.warning("deploy_stability_init_failed", error=str(e))

    # -- Phase 48: SLA Breach Impact Analyzer --
    if settings.breach_impact_enabled:
        try:
            from shieldops.api.routes import breach_impact as sbi_mod
            from shieldops.sla.breach_impact import SLABreachImpactAnalyzer

            _sbi_engine = SLABreachImpactAnalyzer(
                max_records=settings.breach_impact_max_records,
                max_breach_impact_score=settings.breach_impact_max_breach_impact_score,
            )
            sbi_mod.set_engine(_sbi_engine)
            app.include_router(
                sbi_mod.sbi_route,
                prefix=settings.api_prefix,
                tags=["Breach Impact"],
            )
            logger.info("breach_impact_initialized")
        except Exception as e:
            logger.warning("breach_impact_init_failed", error=str(e))

    # -- Phase 48: Shift Schedule Optimizer --
    if settings.shift_optimizer_enabled:
        try:
            from shieldops.api.routes import shift_optimizer as sso_mod
            from shieldops.operations.shift_optimizer import (
                ShiftScheduleOptimizer,
            )

            _sso_engine = ShiftScheduleOptimizer(
                max_records=settings.shift_optimizer_max_records,
                max_coverage_gap_pct=settings.shift_optimizer_max_coverage_gap_pct,
            )
            sso_mod.set_engine(_sso_engine)
            app.include_router(
                sso_mod.sso_route,
                prefix=settings.api_prefix,
                tags=["Shift Optimizer"],
            )
            logger.info("shift_optimizer_initialized")
        except Exception as e:
            logger.warning("shift_optimizer_init_failed", error=str(e))

    # -- Phase 48: Lateral Movement Detector --
    if settings.lateral_movement_enabled:
        try:
            from shieldops.api.routes import lateral_movement as lmd_mod
            from shieldops.security.lateral_movement import (
                LateralMovementDetector,
            )

            _lmd_engine = LateralMovementDetector(
                max_records=settings.lateral_movement_max_records,
                min_detection_confidence_pct=settings.lateral_movement_min_detection_confidence_pct,
            )
            lmd_mod.set_engine(_lmd_engine)
            app.include_router(
                lmd_mod.lmd_route,
                prefix=settings.api_prefix,
                tags=["Lateral Movement"],
            )
            logger.info("lateral_movement_initialized")
        except Exception as e:
            logger.warning("lateral_movement_init_failed", error=str(e))

    # -- Phase 48: Knowledge Coverage Analyzer --
    if settings.knowledge_coverage_enabled:
        try:
            from shieldops.api.routes import knowledge_coverage as kca_mod
            from shieldops.knowledge.knowledge_coverage import (
                KnowledgeCoverageAnalyzer,
            )

            _kca_engine = KnowledgeCoverageAnalyzer(
                max_records=settings.knowledge_coverage_max_records,
                min_coverage_pct=settings.knowledge_coverage_min_coverage_pct,
            )
            kca_mod.set_engine(_kca_engine)
            app.include_router(
                kca_mod.kca_route,
                prefix=settings.api_prefix,
                tags=["Knowledge Coverage"],
            )
            logger.info("knowledge_coverage_initialized")
        except Exception as e:
            logger.warning("knowledge_coverage_init_failed", error=str(e))

    # -- Phase 48: Regulatory Change Tracker --
    if settings.regulation_tracker_enabled:
        try:
            from shieldops.api.routes import regulation_tracker as rct_mod
            from shieldops.compliance.regulation_tracker import (
                RegulatoryChangeTracker,
            )

            _rct_engine = RegulatoryChangeTracker(
                max_records=settings.regulation_tracker_max_records,
                max_impact_score=settings.regulation_tracker_max_impact_score,
            )
            rct_mod.set_engine(_rct_engine)
            app.include_router(
                rct_mod.rct_route,
                prefix=settings.api_prefix,
                tags=["Regulation Tracker"],
            )
            logger.info("regulation_tracker_initialized")
        except Exception as e:
            logger.warning("regulation_tracker_init_failed", error=str(e))

    # -- Phase 48: Workflow Efficiency Analyzer --
    if settings.workflow_analyzer_enabled:
        try:
            from shieldops.analytics.workflow_analyzer import (
                WorkflowEfficiencyAnalyzer,
            )
            from shieldops.api.routes import workflow_analyzer as wea_mod

            _wea_engine = WorkflowEfficiencyAnalyzer(
                max_records=settings.workflow_analyzer_max_records,
                min_efficiency_score=settings.workflow_analyzer_min_efficiency_score,
            )
            wea_mod.set_engine(_wea_engine)
            app.include_router(
                wea_mod.wea_route,
                prefix=settings.api_prefix,
                tags=["Workflow Analyzer"],
            )
            logger.info("workflow_analyzer_initialized")
        except Exception as e:
            logger.warning("workflow_analyzer_init_failed", error=str(e))

    # -- Phase 48: Audit Finding Tracker --
    if settings.finding_tracker_enabled:
        try:
            from shieldops.api.routes import finding_tracker as aft_mod
            from shieldops.audit.finding_tracker import AuditFindingTracker

            _aft_engine = AuditFindingTracker(
                max_records=settings.finding_tracker_max_records,
                max_open_finding_pct=settings.finding_tracker_max_open_finding_pct,
            )
            aft_mod.set_engine(_aft_engine)
            app.include_router(
                aft_mod.aft_route,
                prefix=settings.api_prefix,
                tags=["Finding Tracker"],
            )
            logger.info("finding_tracker_initialized")
        except Exception as e:
            logger.warning("finding_tracker_init_failed", error=str(e))

    # -- Phase 49: Incident Blast Radius Analyzer --
    if settings.blast_radius_enabled:
        try:
            from shieldops.api.routes import blast_radius as ibr_mod
            from shieldops.incidents.blast_radius import (
                IncidentBlastRadiusAnalyzer,
            )

            _ibr_engine = IncidentBlastRadiusAnalyzer(
                max_records=settings.blast_radius_max_records,
                max_blast_radius_score=settings.blast_radius_max_blast_radius_score,
            )
            ibr_mod.set_engine(_ibr_engine)
            app.include_router(
                ibr_mod.ibr_route,
                prefix=settings.api_prefix,
                tags=["Blast Radius"],
            )
            logger.info("blast_radius_initialized")
        except Exception as e:
            logger.warning("blast_radius_init_failed", error=str(e))

    # -- Phase 49: API Gateway Health Monitor --
    if settings.api_gateway_health_enabled:
        try:
            from shieldops.api.routes import api_gateway_health as agh_mod
            from shieldops.topology.api_gateway_health import (
                APIGatewayHealthMonitor,
            )

            _agh_engine = APIGatewayHealthMonitor(
                max_records=settings.api_gateway_health_max_records,
                max_error_rate_pct=settings.api_gateway_health_max_error_rate_pct,
            )
            agh_mod.set_engine(_agh_engine)
            app.include_router(
                agh_mod.agh_route,
                prefix=settings.api_prefix,
                tags=["API Gateway Health"],
            )
            logger.info("api_gateway_health_initialized")
        except Exception as e:
            logger.warning("api_gateway_health_init_failed", error=str(e))

    # -- Phase 49: Log Quality Analyzer --
    if settings.log_quality_enabled:
        try:
            from shieldops.api.routes import log_quality as lqa_mod
            from shieldops.observability.log_quality import LogQualityAnalyzer

            _lqa_engine = LogQualityAnalyzer(
                max_records=settings.log_quality_max_records,
                min_log_quality_pct=settings.log_quality_min_log_quality_pct,
            )
            lqa_mod.set_engine(_lqa_engine)
            app.include_router(
                lqa_mod.lqa_route,
                prefix=settings.api_prefix,
                tags=["Log Quality"],
            )
            logger.info("log_quality_initialized")
        except Exception as e:
            logger.warning("log_quality_init_failed", error=str(e))

    # -- Phase 49: Commitment Utilization Tracker --
    if settings.commitment_tracker_enabled:
        try:
            from shieldops.api.routes import commitment_tracker as cut_mod
            from shieldops.billing.commitment_tracker import (
                CommitmentUtilizationTracker,
            )

            _cut_engine = CommitmentUtilizationTracker(
                max_records=settings.commitment_tracker_max_records,
                min_utilization_pct=settings.commitment_tracker_min_utilization_pct,
            )
            cut_mod.set_engine(_cut_engine)
            app.include_router(
                cut_mod.cut_route,
                prefix=settings.api_prefix,
                tags=["Commitment Tracker"],
            )
            logger.info("commitment_tracker_initialized")
        except Exception as e:
            logger.warning("commitment_tracker_init_failed", error=str(e))

    # -- Phase 49: Feature Flag Impact Analyzer --
    if settings.feature_flag_impact_enabled:
        try:
            from shieldops.api.routes import feature_flag_impact as ffi_mod
            from shieldops.changes.feature_flag_impact import (
                FeatureFlagImpactTracker,
            )

            _ffi_engine = FeatureFlagImpactTracker(
                max_records=settings.feature_flag_impact_max_records,
                max_negative_impact_pct=settings.feature_flag_impact_max_negative_impact_pct,
            )
            ffi_mod.set_engine(_ffi_engine)
            app.include_router(
                ffi_mod.ffi_route,
                prefix=settings.api_prefix,
                tags=["Feature Flag Impact"],
            )
            logger.info("feature_flag_impact_initialized")
        except Exception as e:
            logger.warning("feature_flag_impact_init_failed", error=str(e))

    # -- Phase 49: Customer Impact Scorer --
    if settings.customer_impact_enabled:
        try:
            from shieldops.api.routes import customer_impact as cis_mod
            from shieldops.sla.customer_impact import CustomerImpactScorer

            _cis_engine = CustomerImpactScorer(
                max_records=settings.customer_impact_max_records,
                max_impact_score=settings.customer_impact_max_impact_score,
            )
            cis_mod.set_engine(_cis_engine)
            app.include_router(
                cis_mod.cis_route,
                prefix=settings.api_prefix,
                tags=["Customer Impact"],
            )
            logger.info("customer_impact_initialized")
        except Exception as e:
            logger.warning("customer_impact_init_failed", error=str(e))

    # -- Phase 49: Toil Automation Tracker --
    if settings.toil_automator_enabled:
        try:
            from shieldops.api.routes import toil_automator as tat_mod
            from shieldops.operations.toil_automator import (
                ToilAutomationTracker,
            )

            _tat_engine = ToilAutomationTracker(
                max_records=settings.toil_automator_max_records,
                min_automation_pct=settings.toil_automator_min_automation_pct,
            )
            tat_mod.set_engine(_tat_engine)
            app.include_router(
                tat_mod.tat_route,
                prefix=settings.api_prefix,
                tags=["Toil Automator"],
            )
            logger.info("toil_automator_initialized")
        except Exception as e:
            logger.warning("toil_automator_init_failed", error=str(e))

    # -- Phase 49: Insider Threat Detector --
    if settings.insider_threat_enabled:
        try:
            from shieldops.api.routes import insider_threat as itd_mod
            from shieldops.security.insider_threat import InsiderThreatDetector

            _itd_engine = InsiderThreatDetector(
                max_records=settings.insider_threat_max_records,
                min_threat_confidence_pct=settings.insider_threat_min_threat_confidence_pct,
            )
            itd_mod.set_engine(_itd_engine)
            app.include_router(
                itd_mod.itd_route,
                prefix=settings.api_prefix,
                tags=["Insider Threat"],
            )
            logger.info("insider_threat_initialized")
        except Exception as e:
            logger.warning("insider_threat_init_failed", error=str(e))

    # -- Phase 49: Team Expertise Mapper --
    if settings.expertise_mapper_enabled:
        try:
            from shieldops.api.routes import expertise_mapper as tem_mod
            from shieldops.knowledge.expertise_mapper import TeamExpertiseMapper

            _tem_engine = TeamExpertiseMapper(
                max_records=settings.expertise_mapper_max_records,
                min_expertise_coverage_pct=settings.expertise_mapper_min_expertise_coverage_pct,
            )
            tem_mod.set_engine(_tem_engine)
            app.include_router(
                tem_mod.tem_route,
                prefix=settings.api_prefix,
                tags=["Expertise Mapper"],
            )
            logger.info("expertise_mapper_initialized")
        except Exception as e:
            logger.warning("expertise_mapper_init_failed", error=str(e))

    # -- Phase 49: Control Effectiveness Tracker --
    if settings.control_effectiveness_enabled:
        try:
            from shieldops.api.routes import control_effectiveness as cet_mod
            from shieldops.compliance.control_effectiveness import (
                ControlEffectivenessTracker,
            )

            _cet_engine = ControlEffectivenessTracker(
                max_records=settings.control_effectiveness_max_records,
                min_effectiveness_pct=settings.control_effectiveness_min_effectiveness_pct,
            )
            cet_mod.set_engine(_cet_engine)
            app.include_router(
                cet_mod.cet_route,
                prefix=settings.api_prefix,
                tags=["Control Effectiveness"],
            )
            logger.info("control_effectiveness_initialized")
        except Exception as e:
            logger.warning("control_effectiveness_init_failed", error=str(e))

    # -- Phase 49: Reliability Metrics Collector --
    if settings.reliability_metrics_enabled:
        try:
            from shieldops.analytics.reliability_metrics import (
                ReliabilityMetricsCollector,
            )
            from shieldops.api.routes import reliability_metrics as rmc_mod

            _rmc_engine = ReliabilityMetricsCollector(
                max_records=settings.reliability_metrics_max_records,
                min_reliability_score=settings.reliability_metrics_min_reliability_score,
            )
            rmc_mod.set_engine(_rmc_engine)
            app.include_router(
                rmc_mod.rmc_route,
                prefix=settings.api_prefix,
                tags=["Reliability Metrics"],
            )
            logger.info("reliability_metrics_initialized")
        except Exception as e:
            logger.warning("reliability_metrics_init_failed", error=str(e))

    # -- Phase 49: Audit Remediation Tracker --
    if settings.remediation_tracker_enabled:
        try:
            from shieldops.api.routes import remediation_tracker as art_mod
            from shieldops.audit.remediation_tracker import (
                AuditRemediationTracker,
            )

            _art_engine = AuditRemediationTracker(
                max_records=settings.remediation_tracker_max_records,
                max_overdue_pct=settings.remediation_tracker_max_overdue_pct,
            )
            art_mod.set_engine(_art_engine)
            app.include_router(
                art_mod.art_route,
                prefix=settings.api_prefix,
                tags=["Remediation Tracker"],
            )
            logger.info("remediation_tracker_initialized")
        except Exception as e:
            logger.warning("remediation_tracker_init_failed", error=str(e))

    # -- Phase 50: Incident Response Playbook Manager --
    if settings.response_playbook_enabled:
        try:
            from shieldops.api.routes import response_playbook as irp_mod
            from shieldops.incidents.response_playbook import IncidentResponsePlaybookManager

            _irp_engine = IncidentResponsePlaybookManager(
                max_records=settings.response_playbook_max_records,
                min_playbook_coverage_pct=settings.response_playbook_min_playbook_coverage_pct,
            )
            irp_mod.set_engine(_irp_engine)
            app.include_router(
                irp_mod.irp_route,
                prefix=settings.api_prefix,
                tags=["Response Playbook"],
            )
            logger.info("response_playbook_initialized")
        except Exception as e:
            logger.warning("response_playbook_init_failed", error=str(e))

    # -- Phase 50: Service Communication Analyzer --
    if settings.service_communication_enabled:
        try:
            from shieldops.api.routes import service_communication as sca_mod
            from shieldops.topology.service_communication import ServiceCommunicationAnalyzer

            _sca_engine = ServiceCommunicationAnalyzer(
                max_records=settings.service_communication_max_records,
                max_anomaly_rate_pct=settings.service_communication_max_anomaly_rate_pct,
            )
            sca_mod.set_engine(_sca_engine)
            app.include_router(
                sca_mod.sca_route,
                prefix=settings.api_prefix,
                tags=["Service Communication"],
            )
            logger.info("service_communication_initialized")
        except Exception as e:
            logger.warning("service_communication_init_failed", error=str(e))

    # -- Phase 50: Dashboard Effectiveness Scorer --
    if settings.dashboard_effectiveness_enabled:
        try:
            from shieldops.api.routes import dashboard_effectiveness as des_mod
            from shieldops.observability.dashboard_effectiveness import (
                DashboardEffectivenessScorer,
            )

            _des_engine = DashboardEffectivenessScorer(
                max_records=settings.dashboard_effectiveness_max_records,
                min_effectiveness_score=settings.dashboard_effectiveness_min_effectiveness_score,
            )
            des_mod.set_engine(_des_engine)
            app.include_router(
                des_mod.des_route,
                prefix=settings.api_prefix,
                tags=["Dashboard Effectiveness"],
            )
            logger.info("dashboard_effectiveness_initialized")
        except Exception as e:
            logger.warning("dashboard_effectiveness_init_failed", error=str(e))

    # -- Phase 50: Procurement Optimizer --
    if settings.procurement_optimizer_enabled:
        try:
            from shieldops.api.routes import procurement_optimizer as pro_mod
            from shieldops.billing.procurement_optimizer import ProcurementOptimizer

            _pro_engine = ProcurementOptimizer(
                max_records=settings.procurement_optimizer_max_records,
                max_waste_pct=settings.procurement_optimizer_max_waste_pct,
            )
            pro_mod.set_engine(_pro_engine)
            app.include_router(
                pro_mod.pro_route,
                prefix=settings.api_prefix,
                tags=["Procurement Optimizer"],
            )
            logger.info("procurement_optimizer_initialized")
        except Exception as e:
            logger.warning("procurement_optimizer_init_failed", error=str(e))

    # -- Phase 50: Merge Risk Assessor --
    if settings.merge_risk_enabled:
        try:
            from shieldops.api.routes import merge_risk as mra_mod
            from shieldops.changes.merge_risk import MergeRiskAssessor

            _mra_engine = MergeRiskAssessor(
                max_records=settings.merge_risk_max_records,
                max_risk_score=settings.merge_risk_max_risk_score,
            )
            mra_mod.set_engine(_mra_engine)
            app.include_router(
                mra_mod.mra_route,
                prefix=settings.api_prefix,
                tags=["Merge Risk"],
            )
            logger.info("merge_risk_initialized")
        except Exception as e:
            logger.warning("merge_risk_init_failed", error=str(e))

    # -- Phase 50: Service Degradation Tracker --
    if settings.degradation_tracker_enabled:
        try:
            from shieldops.api.routes import degradation_tracker as sdg_mod
            from shieldops.sla.degradation_tracker import ServiceDegradationTracker

            _sdg_engine = ServiceDegradationTracker(
                max_records=settings.degradation_tracker_max_records,
                max_degradation_minutes=settings.degradation_tracker_max_degradation_minutes,
            )
            sdg_mod.set_engine(_sdg_engine)
            app.include_router(
                sdg_mod.sdg_route,
                prefix=settings.api_prefix,
                tags=["Degradation Tracker"],
            )
            logger.info("degradation_tracker_initialized")
        except Exception as e:
            logger.warning("degradation_tracker_init_failed", error=str(e))

    # -- Phase 50: Handover Quality Tracker --
    if settings.handover_quality_enabled:
        try:
            from shieldops.api.routes import handover_quality as hqt_mod
            from shieldops.operations.handover_quality import HandoverQualityTracker

            _hqt_engine = HandoverQualityTracker(
                max_records=settings.handover_quality_max_records,
                min_handover_quality_pct=settings.handover_quality_min_handover_quality_pct,
            )
            hqt_mod.set_engine(_hqt_engine)
            app.include_router(
                hqt_mod.hqt_route,
                prefix=settings.api_prefix,
                tags=["Handover Quality"],
            )
            logger.info("handover_quality_initialized")
        except Exception as e:
            logger.warning("handover_quality_init_failed", error=str(e))

    # -- Phase 50: Data Classification Engine --
    if settings.data_classification_enabled:
        try:
            from shieldops.api.routes import data_classification as dce_mod
            from shieldops.security.data_classification import DataClassificationEngine

            _dce_engine = DataClassificationEngine(
                max_records=settings.data_classification_max_records,
                min_classification_coverage_pct=settings.data_classification_min_classification_coverage_pct,
            )
            dce_mod.set_engine(_dce_engine)
            app.include_router(
                dce_mod.dce_route,
                prefix=settings.api_prefix,
                tags=["Data Classification"],
            )
            logger.info("data_classification_initialized")
        except Exception as e:
            logger.warning("data_classification_init_failed", error=str(e))

    # -- Phase 50: Knowledge Feedback Analyzer --
    if settings.feedback_loop_enabled:
        try:
            from shieldops.api.routes import feedback_loop as kfa_mod
            from shieldops.knowledge.feedback_loop import KnowledgeFeedbackAnalyzer

            _kfa_engine = KnowledgeFeedbackAnalyzer(
                max_records=settings.feedback_loop_max_records,
                min_satisfaction_score=settings.feedback_loop_min_satisfaction_score,
            )
            kfa_mod.set_engine(_kfa_engine)
            app.include_router(
                kfa_mod.kfa_route,
                prefix=settings.api_prefix,
                tags=["Feedback Loop"],
            )
            logger.info("feedback_loop_initialized")
        except Exception as e:
            logger.warning("feedback_loop_init_failed", error=str(e))

    # -- Phase 50: Policy Coverage Analyzer --
    if settings.policy_coverage_enabled:
        try:
            from shieldops.api.routes import policy_coverage as pca_mod
            from shieldops.compliance.policy_coverage import PolicyCoverageAnalyzer

            _pca_engine = PolicyCoverageAnalyzer(
                max_records=settings.policy_coverage_max_records,
                min_policy_coverage_pct=settings.policy_coverage_min_policy_coverage_pct,
            )
            pca_mod.set_engine(_pca_engine)
            app.include_router(
                pca_mod.pca_route,
                prefix=settings.api_prefix,
                tags=["Policy Coverage"],
            )
            logger.info("policy_coverage_initialized")
        except Exception as e:
            logger.warning("policy_coverage_init_failed", error=str(e))

    # -- Phase 50: Alert Response Analyzer --
    if settings.alert_response_enabled:
        try:
            from shieldops.analytics.alert_response import AlertResponseAnalyzer
            from shieldops.api.routes import alert_response as ara_mod

            _ara_engine = AlertResponseAnalyzer(
                max_records=settings.alert_response_max_records,
                max_response_time_minutes=settings.alert_response_max_response_time_minutes,
            )
            ara_mod.set_engine(_ara_engine)
            app.include_router(
                ara_mod.ara_route,
                prefix=settings.api_prefix,
                tags=["Alert Response"],
            )
            logger.info("alert_response_initialized")
        except Exception as e:
            logger.warning("alert_response_init_failed", error=str(e))

    # -- Phase 50: Change Audit Analyzer --
    if settings.change_audit_enabled:
        try:
            from shieldops.api.routes import change_audit as cau_mod
            from shieldops.audit.change_audit import ChangeAuditAnalyzer

            _cau_engine = ChangeAuditAnalyzer(
                max_records=settings.change_audit_max_records,
                min_audit_compliance_pct=settings.change_audit_min_audit_compliance_pct,
            )
            cau_mod.set_engine(_cau_engine)
            app.include_router(
                cau_mod.cau_route,
                prefix=settings.api_prefix,
                tags=["Change Audit"],
            )
            logger.info("change_audit_initialized")
        except Exception as e:
            logger.warning("change_audit_init_failed", error=str(e))

    yield

    logger.info("shieldops_shutting_down")

    # Plugin teardown
    if plugin_registry:
        try:
            await plugin_registry.teardown_all()
        except Exception as e:
            logger.debug("plugin_teardown_error", error=str(e))

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
    _task_queue = getattr(getattr(app, "state", None), "task_queue", None)
    if _task_queue:
        await _task_queue.stop()
    _redis_cache = getattr(getattr(app, "state", None), "redis_cache", None)
    if _redis_cache:
        await _redis_cache.disconnect()
    _event_bus = getattr(getattr(app, "state", None), "event_bus", None)
    if _event_bus:
        await _event_bus.stop()
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
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-Organization-ID",
            "Idempotency-Key",
        ],
    )

    # OpenTelemetry automatic HTTP span creation
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception:  # noqa: S110
        pass  # OTEL instrumentation is optional — may not be installed

    # Middleware stack (order matters: outermost first)
    from shieldops.api.middleware import (
        APIVersionMiddleware,
        BillingEnforcementMiddleware,
        ErrorHandlerMiddleware,
        GracefulShutdownMiddleware,
        MetricsMiddleware,
        RateLimitMiddleware,
        RequestIDMiddleware,
        RequestLoggingMiddleware,
        SecurityHeadersMiddleware,
        SlidingWindowRateLimiter,
        UsageTrackerMiddleware,
    )

    app.add_middleware(ErrorHandlerMiddleware)
    # Phase 13: Idempotency middleware for POST/PUT/PATCH deduplication
    try:
        from shieldops.api.middleware.idempotency import IdempotencyMiddleware

        app.add_middleware(IdempotencyMiddleware, ttl=settings.idempotency_ttl_seconds)
    except Exception:  # noqa: S110
        pass  # Idempotency middleware is optional
    app.add_middleware(RateLimitMiddleware)
    # Sliding window rate limiter (activated after the fixed-window limiter)
    if settings.sliding_window_rate_limit_enabled:
        app.add_middleware(SlidingWindowRateLimiter)
    # BillingEnforcementMiddleware checks plan limits (agent count,
    # API quota) and returns 402 when exceeded.  Placed after rate
    # limiting so rate-limited requests are rejected before hitting
    # billing checks.  The enforcement service is injected at
    # startup via set_enforcement_service().
    app.add_middleware(BillingEnforcementMiddleware)
    # UsageTrackerMiddleware records per-endpoint call counts and
    # latencies.  Placed after auth/tenant so org_id is available
    # on request.state.
    app.add_middleware(UsageTrackerMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    # APIVersionMiddleware adds X-API-Version + X-Powered-By headers
    app.add_middleware(APIVersionMiddleware)
    # SecurityHeadersMiddleware adds HSTS, CSP, X-Frame-Options, etc.
    app.add_middleware(SecurityHeadersMiddleware)
    # MetricsMiddleware is added last so it wraps all other
    # middleware (Starlette processes add_middleware in LIFO order).
    app.add_middleware(MetricsMiddleware)
    # GracefulShutdownMiddleware outermost: rejects requests early
    # during shutdown and tracks in-flight count for draining.
    app.add_middleware(GracefulShutdownMiddleware)

    # Tenant isolation middleware — extracts org_id for multi-tenant
    try:
        from shieldops.api.middleware.tenant import TenantMiddleware

        app.add_middleware(TenantMiddleware)
    except Exception as e:
        logger.warning("tenant_middleware_init_failed", error=str(e))

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
    app.include_router(batch.router, prefix=settings.api_prefix, tags=["Batch"])
    app.include_router(search.router, prefix=settings.api_prefix, tags=["Search"])
    app.include_router(usage.router, prefix=settings.api_prefix, tags=["API Usage"])

    # Database migration management
    from shieldops.api.routes.migrations import router as migrations_router

    app.include_router(migrations_router, prefix=settings.api_prefix, tags=["Migrations"])

    # Health check (detailed, authenticated)
    from shieldops.api.routes.health import router as health_router

    app.include_router(health_router, prefix=settings.api_prefix, tags=["Health"])

    # API changelog
    from shieldops.api.routes.changelog import router as changelog_router

    app.include_router(changelog_router, prefix=settings.api_prefix, tags=["Changelog"])

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
