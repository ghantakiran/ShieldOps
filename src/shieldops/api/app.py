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
