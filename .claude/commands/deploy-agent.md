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
   - Orchestrate self-healing via `SelfHealingOrchestrator` (`src/shieldops/operations/self_healing.py`)
   - Track scaling efficiency via `ScalingEfficiencyTracker` (`src/shieldops/operations/scaling_efficiency.py`)
   - Detect reliability antipatterns via `ReliabilityAntiPatternDetector` (`src/shieldops/topology/reliability_antipattern.py`)
   - Auto-triage incidents via `IncidentAutoTriageEngine` (`src/shieldops/incidents/auto_triage.py`)
   - Forecast error budget via `ErrorBudgetForecaster` (`src/shieldops/sla/error_budget_forecast.py`)
   - Recommend runbooks via `RunbookRecommendationEngine` (`src/shieldops/operations/runbook_recommender.py`)
   - Track cognitive load via `TeamCognitiveLoadTracker` (`src/shieldops/operations/cognitive_load.py`)
   - Monitor attack surface via `AttackSurfaceMonitor` (`src/shieldops/security/attack_surface.py`)
   - Score platform reliability via `PlatformReliabilityScorecard` (`src/shieldops/sla/reliability_scorecard.py`)
   - Analyze rollback patterns via `DeploymentRollbackAnalyzer` (`src/shieldops/changes/rollback_analyzer.py`)
   - Track LLM token costs via `LLMTokenCostTracker` (`src/shieldops/billing/llm_cost_tracker.py`)
   - Track DR drill readiness via `DRDrillTracker` (`src/shieldops/operations/dr_drill_tracker.py`)
   - Enforce tenant resource quotas via `TenantResourceQuotaManager` (`src/shieldops/operations/tenant_quota.py`)
   - Log agent decisions via `DecisionAuditLogger` (`src/shieldops/audit/decision_audit.py`)
   - Track deployment dependencies via `DeploymentDependencyTracker` (`src/shieldops/changes/deployment_dependency.py`)
   - Aggregate risk signals via `RiskSignalAggregator` (`src/shieldops/security/risk_aggregator.py`)
   - Score dynamic risk via `DynamicRiskScorer` (`src/shieldops/analytics/dynamic_risk_scorer.py`)
   - Optimize agent token usage via `AgentTokenOptimizer` (`src/shieldops/agents/token_optimizer.py`)
   - Route agent tasks via `AgentRoutingOptimizer` (`src/shieldops/agents/routing_optimizer.py`)
   - Verify zero trust posture via `ZeroTrustVerifier` (`src/shieldops/security/zero_trust_verifier.py`)
   - Orchestrate remediation pipelines via `RemediationPipelineOrchestrator` (`src/shieldops/operations/remediation_pipeline.py`)
   - Coordinate recovery across services via `RecoveryCoordinator` (`src/shieldops/operations/recovery_coordinator.py`)
   - Enforce cross-agent policies via `CrossAgentPolicyEnforcer` (`src/shieldops/policy/cross_agent_enforcer.py`)
   - Coordinate multi-region failover via `MultiRegionFailoverCoordinator` (`src/shieldops/operations/failover_coordinator.py`)
   - Manage capacity bursts via `CapacityBurstManager` (`src/shieldops/operations/burst_manager.py`)
   - Predict security breaches via `BreachPredictor` (`src/shieldops/security/breach_predictor.py`)
   - Allocate error budgets via `ErrorBudgetAllocator` (`src/shieldops/sla/error_budget_allocator.py`)
   - Analyze dependency topology via `DependencyTopologyAnalyzer` (`src/shieldops/topology/dependency_topology.py`)
   - Plan infra capacity via `InfraCapacityPlanner` (`src/shieldops/operations/infra_capacity_planner.py`)
   - Monitor DNS health via `DNSHealthMonitor` (`src/shieldops/observability/dns_health_monitor.py`)
   - Analyze configuration drift via `DriftAnalyzer` (`src/shieldops/operations/drift_analyzer.py`)
   - Assess deployment impact via `DeploymentImpactAnalyzer` (`src/shieldops/changes/deployment_impact.py`)
   - Monitor governance posture via `GovernanceDashboard` (`src/shieldops/compliance/governance_dashboard.py`)
   - Replay incidents via `IncidentReplayEngine` (`src/shieldops/incidents/incident_replay.py`)
   - Track response timing via `IncidentResponseTimer` (`src/shieldops/incidents/response_timer.py`)
   - Aggregate SLO data via `SLOAggregationEngine` (`src/shieldops/sla/slo_aggregator.py`)
   - Analyze network latency via `NetworkLatencyAnalyzer` (`src/shieldops/analytics/network_latency.py`)
   - Enforce change freeze via `ChangeFreezePolicyManager` (`src/shieldops/changes/change_freeze.py`)
   - Analyze pipeline performance via `PipelinePerformanceAnalyzer` (`src/shieldops/analytics/pipeline_analyzer.py`)
   - Validate release readiness via `ReleaseReadinessValidator` (`src/shieldops/changes/release_readiness.py`)
   - Track service ownership via `ServiceOwnershipTracker` (`src/shieldops/operations/ownership_tracker.py`)
   - Validate configuration via `ConfigurationValidator` (`src/shieldops/config/config_validator.py`)
   - Detect observability gaps via `ObservabilityGapAnalyzer` (`src/shieldops/observability/observability_gap.py`)
   - Score platform governance via `PlatformGovernanceScorer` (`src/shieldops/policy/governance_scorer.py`)
   - Classify operational toil via `OperationalToilClassifier` (`src/shieldops/operations/toil_classifier.py`)
   - Track service deprecation status via `ServiceDeprecationTracker` (`src/shieldops/topology/deprecation_tracker.py`)
   - Analyze change approval workflow via `ChangeApprovalAnalyzer` (`src/shieldops/changes/approval_analyzer.py`)
   - Verify SLO compliance via `SLOComplianceChecker` (`src/shieldops/sla/slo_compliance.py`)
   - Advise predictive scaling via `PredictiveScalingAdvisor` (`src/shieldops/operations/scaling_advisor.py`)
   - Analyze deployment frequency via `DeploymentFrequencyAnalyzer` (`src/shieldops/changes/deploy_frequency.py`)
   - Track team velocity via `TeamVelocityTracker` (`src/shieldops/analytics/team_velocity.py`)
   - Score capacity utilization via `CapacityUtilizationScorer` (`src/shieldops/analytics/utilization_scorer.py`)
   - Map service communications via `ServiceCommunicationMapper` (`src/shieldops/topology/comm_mapper.py`)
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
