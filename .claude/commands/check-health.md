# Check Health Skill

Run health checks on all ShieldOps platform dependencies.

## Usage
`/check-health [--fix]`

## Process

1. **Check Python environment**:
   - Verify Python 3.12+: `python3 --version`
   - Check virtual env: verify `.venv` or `VIRTUAL_ENV` is set
   - Validate dependencies: `pip check` for conflicts

2. **Check service dependencies**:
   - PostgreSQL: `pg_isready -h localhost -p 5432` or connect test
   - Redis: `redis-cli ping`
   - OPA: `curl http://localhost:8181/health`
   - Kafka: Check `docker ps` for kafka container

3. **Check code quality**:
   - Lint: `python3 -m ruff check src/ tests/`
   - Format: `python3 -m ruff format --check src/ tests/`
   - Type check: `python3 -m mypy src/shieldops/ --ignore-missing-imports`

4. **Run test suite**:
   - Unit tests: `python3 -m pytest tests/unit/ -v --tb=short`
   - Integration tests: `python3 -m pytest tests/integration/ -v --tb=short`
   - Report: total tests, passed, failed, coverage

5. **Platform feature health** (Phase 11–20 modules):
   - Capacity trends: `src/shieldops/analytics/capacity_trends.py` — CapacityTrendAnalyzer
   - SRE metrics: `src/shieldops/analytics/sre_metrics.py` — SREMetricsAggregator
   - Health reports: `src/shieldops/observability/health_report.py` — ServiceHealthReportGenerator
   - Cost forecasts: `src/shieldops/billing/cost_forecast.py` — CostForecastEngine
   - Deployment risk: `src/shieldops/changes/deployment_risk.py` — DeploymentRiskPredictor
   - Incident clustering: `src/shieldops/analytics/incident_clustering.py` — IncidentClusteringEngine
   - Tenant isolation: `src/shieldops/policy/tenant_isolation.py` — TenantResourceIsolationManager
   - Alert noise: `src/shieldops/observability/alert_noise.py` — AlertNoiseAnalyzer
   - Threshold tuner: `src/shieldops/observability/threshold_tuner.py` — ThresholdTuningEngine
   - Severity predictor: `src/shieldops/incidents/severity_predictor.py` — IncidentSeverityPredictor
   - Impact analyzer: `src/shieldops/topology/impact_analyzer.py` — ServiceDependencyImpactAnalyzer
   - Config audit: `src/shieldops/audit/config_audit.py` — ConfigurationAuditTrail
   - Deployment velocity: `src/shieldops/analytics/deployment_velocity.py` — DeploymentVelocityTracker
   - Compliance automation: `src/shieldops/compliance/automation_rules.py` — ComplianceAutomationEngine
   - Knowledge base: `src/shieldops/knowledge/article_manager.py` — KnowledgeBaseManager
   - On-call fatigue: `src/shieldops/incidents/oncall_fatigue.py` — OnCallFatigueAnalyzer
   - Backup verification: `src/shieldops/observability/backup_verification.py` — BackupVerificationEngine
   - Cost tag enforcer: `src/shieldops/billing/cost_tag_enforcer.py` — CostAllocationTagEnforcer
   - Verify each module initializes in `src/shieldops/api/app.py` lifespan

6. **Check configuration**:
   - Verify `.env` file exists (warn if missing)
   - Check required env vars are set (DATABASE_URL, REDIS_URL, etc.)
   - Validate OPA policies: check `playbooks/policies/` for syntax

## Output Format
Report each check as PASS/FAIL/WARN with details.
If `--fix` is passed, auto-fix what's possible (format, install missing deps).
