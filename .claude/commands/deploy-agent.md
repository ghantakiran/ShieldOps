# Deploy Agent Skill

Deploy ShieldOps agents to target environments.

## Usage
`/deploy-agent <environment> [--agent <type>] [--dry-run]`

## Environments
- `dev` — Local/dev Kubernetes cluster
- `staging` — Staging environment (shadow mode by default)
- `production` — Production (requires approval workflow)

## Process

1. **Pre-flight checks**:
   - Run full test suite: `pytest tests/ -v`
   - Security scan: `ruff check` + dependency audit
   - Verify OPA policies are loaded for target environment
2. **Build artifacts**:
   - Build Docker image: `docker build -t shieldops-agent:{version}`
   - Push to container registry
3. **Pre-deploy risk assessment**:
   - Run `DeploymentRiskPredictor` from `src/shieldops/changes/deployment_risk.py`
   - Check `ChangeAdvisoryBoard` approval status from `src/shieldops/changes/change_advisory.py`
   - Verify deployment freeze windows via `DeploymentFreezeManager`
   - Record deployment event via `DeploymentVelocityTracker` (`src/shieldops/analytics/deployment_velocity.py`)
   - Verify backup readiness via `BackupVerificationEngine` (`src/shieldops/observability/backup_verification.py`)
   - Check service dependency impact via `ServiceDependencyImpactAnalyzer` (`src/shieldops/topology/impact_analyzer.py`)
   - Verify DR readiness via `DisasterRecoveryReadinessTracker` (`src/shieldops/observability/dr_readiness.py`)
   - Check release approval via `ReleaseManagementTracker` (`src/shieldops/changes/release_manager.py`)
   - Validate config parity via `ConfigurationParityValidator` (`src/shieldops/config/parity_validator.py`)
   - Predict change risk via `ChangeIntelligenceAnalyzer` (`src/shieldops/changes/change_intelligence.py`)
   - Evaluate safety gate via `ChangeIntelligenceAnalyzer.evaluate_safety_gate()`
   - Predict SLO burn rate via `SLOBurnRatePredictor` (`src/shieldops/sla/burn_predictor.py`)
   - Check dependency health via `DependencyHealthScorer` (`src/shieldops/topology/dependency_scorer.py`)
   - Analyze workload conflicts via `WorkloadSchedulingOptimizer` (`src/shieldops/operations/workload_scheduler.py`)
   - Check certificate expiry via `CertificateExpiryMonitor` (`src/shieldops/security/cert_monitor.py`)
   - Validate SLO targets via `SLOTargetAdvisor` (`src/shieldops/sla/slo_advisor.py`)
   - Predict cascade failures via `CascadingFailurePredictor` (`src/shieldops/topology/cascade_predictor.py`)
   - Scan container images via `ContainerImageScanner` (`src/shieldops/security/container_scanner.py`)
   - Detect secrets sprawl via `SecretsSprawlDetector` (`src/shieldops/security/secrets_detector.py`)
   - Design chaos experiments via `ChaosExperimentDesigner` (`src/shieldops/observability/chaos_designer.py`)
   - Plan game day exercises via `GameDayPlanner` (`src/shieldops/operations/game_day_planner.py`)
   - Check failure modes via `FailureModeCatalog` (`src/shieldops/topology/failure_mode_catalog.py`)
   - Analyze deployment cadence via `DeploymentCadenceAnalyzer` (`src/shieldops/analytics/deployment_cadence.py`)
   - Optimize change windows via `ChangeWindowOptimizer` (`src/shieldops/changes/change_window.py`)
   - Verify service health aggregation via `ServiceHealthAggregator` (`src/shieldops/topology/service_health_agg.py`)
   - Enforce deployment approval gate via `DeploymentApprovalGate` (`src/shieldops/changes/deployment_gate.py`)
   - Validate error budget policy via `ErrorBudgetPolicyEngine` (`src/shieldops/sla/error_budget_policy.py`)
   - Assess service maturity via `ServiceMaturityModel` (`src/shieldops/topology/service_maturity.py`)
   - Predict outages via `PredictiveOutageDetector` (`src/shieldops/observability/outage_predictor.py`)
   - Score deployment health via `DeploymentHealthScorer` (`src/shieldops/changes/deploy_health_scorer.py`)
   - Detect change conflicts via `ChangeConflictDetector` (`src/shieldops/changes/change_conflict_detector.py`)
   - Analyze canary metrics via `DeploymentCanaryAnalyzer` (`src/shieldops/changes/canary_analyzer.py`)
   - Enforce velocity throttling via `ChangeVelocityThrottle` (`src/shieldops/changes/velocity_throttle.py`)
   - Evaluate remediation decisions via `AutoRemediationDecisionEngine` (`src/shieldops/operations/remediation_decision.py`)
   - Monitor dependency lag via `DependencyLagMonitor` (`src/shieldops/topology/dependency_lag.py`)
   - Forecast SLO compliance via `SLOComplianceForecaster` (`src/shieldops/sla/slo_forecast.py`)
   - Score observability coverage via `ObservabilityCoverageScorer` (`src/shieldops/observability/coverage_scorer.py`)
   - Score deployment confidence via `DeploymentConfidenceScorer` (`src/shieldops/changes/deployment_confidence.py`)
   - Detect reliability regressions via `ReliabilityRegressionDetector` (`src/shieldops/sla/reliability_regression.py`)
   - Track post-incident actions via `PostIncidentActionTracker` (`src/shieldops/incidents/action_tracker.py`)
   - Check feature flag lifecycle via `FeatureFlagLifecycleManager` (`src/shieldops/config/flag_lifecycle.py`)
   - Monitor API version health via `APIVersionHealthMonitor` (`src/shieldops/topology/api_version_health.py`)
   - Analyze build pipeline health via `BuildPipelineAnalyzer` (`src/shieldops/analytics/build_pipeline.py`)
   - Analyze traffic patterns via `TrafficPatternAnalyzer` (`src/shieldops/topology/traffic_pattern.py`)
   - Monitor circuit breaker health via `CircuitBreakerHealthMonitor` (`src/shieldops/topology/circuit_breaker_health.py`)
   - Score operational readiness via `OperationalReadinessScorer` (`src/shieldops/operations/readiness_scorer.py`)
   - Score deployment confidence via `DeploymentConfidenceScorer` (`src/shieldops/changes/deployment_confidence.py`)
4. **Deploy**:
   - Apply Kubernetes manifests from `infrastructure/kubernetes/`
   - For production: trigger approval workflow via Slack/Teams
4. **Validate deployment**:
   - Health check endpoints responding
   - Agent connects to message queue
   - OPA policy evaluation working
   - Rollback ready (previous version tagged)
5. **Shadow mode** (staging/production):
   - Agent runs in read-only mode for 24h
   - Compare agent decisions against human actions
   - Generate accuracy report

## Safety
- Production deploys ALWAYS require explicit user confirmation
- Rollback plan must exist before any production deploy
- Monitor agent error rate for 1 hour post-deploy
