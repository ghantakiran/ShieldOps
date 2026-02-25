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

5. **Platform feature health** (Phase 11–28 modules):
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
   - DR readiness: `src/shieldops/observability/dr_readiness.py` — DisasterRecoveryReadinessTracker
   - Service catalog: `src/shieldops/topology/service_catalog.py` — ServiceCatalogManager
   - Contract testing: `src/shieldops/api/contract_testing.py` — APIContractTestingEngine
   - Orphan detector: `src/shieldops/billing/orphan_detector.py` — OrphanedResourceDetector
   - Latency profiler: `src/shieldops/analytics/latency_profiler.py` — ServiceLatencyProfiler
   - License scanner: `src/shieldops/compliance/license_scanner.py` — DependencyLicenseScanner
   - Release manager: `src/shieldops/changes/release_manager.py` — ReleaseManagementTracker
   - Budget manager: `src/shieldops/billing/budget_manager.py` — InfrastructureCostBudgetManager
   - Config parity: `src/shieldops/config/parity_validator.py` — ConfigurationParityValidator
   - Incident dedup: `src/shieldops/incidents/dedup_engine.py` — IncidentDeduplicationEngine
   - Access certification: `src/shieldops/compliance/access_certification.py` — AccessCertificationManager
   - Toil tracker: `src/shieldops/analytics/toil_tracker.py` — ToilMeasurementTracker
   - Trace analyzer: `src/shieldops/analytics/trace_analyzer.py` — DistributedTraceAnalyzer
   - Log anomaly: `src/shieldops/analytics/log_anomaly.py` — LogAnomalyDetector
   - Event correlation: `src/shieldops/analytics/event_correlation.py` — EventCorrelationEngine
   - Security incidents: `src/shieldops/security/incident_response.py` — SecurityIncidentResponseTracker
   - Vuln lifecycle: `src/shieldops/security/vuln_lifecycle.py` — VulnerabilityLifecycleManager
   - API security: `src/shieldops/security/api_security.py` — APISecurityMonitor
   - Tag governance: `src/shieldops/billing/tag_governance.py` — ResourceTagGovernanceEngine
   - Team performance: `src/shieldops/analytics/team_performance.py` — TeamPerformanceAnalyzer
   - Runbook engine: `src/shieldops/operations/runbook_engine.py` — RunbookExecutionEngine
   - Dependency scorer: `src/shieldops/topology/dependency_scorer.py` — DependencyHealthScorer
   - Burn predictor: `src/shieldops/sla/burn_predictor.py` — SLOBurnRatePredictor
   - Change intelligence: `src/shieldops/changes/change_intelligence.py` — ChangeIntelligenceAnalyzer
   - DB performance: `src/shieldops/analytics/db_performance.py` — DatabasePerformanceAnalyzer
   - Queue health: `src/shieldops/observability/queue_health.py` — QueueHealthMonitor
   - Cert monitor: `src/shieldops/security/cert_monitor.py` — CertificateExpiryMonitor
   - Network flow: `src/shieldops/security/network_flow.py` — NetworkFlowAnalyzer
   - DNS health: `src/shieldops/observability/dns_health.py` — DNSHealthMonitor
   - Escalation analyzer: `src/shieldops/incidents/escalation_analyzer.py` — EscalationPatternAnalyzer
   - Right sizer: `src/shieldops/billing/right_sizer.py` — CapacityRightSizer
   - Storage optimizer: `src/shieldops/billing/storage_optimizer.py` — StorageTierOptimizer
   - Resource lifecycle: `src/shieldops/billing/resource_lifecycle.py` — ResourceLifecycleTracker
   - Alert routing: `src/shieldops/observability/alert_routing.py` — AlertRoutingOptimizer
   - SLO advisor: `src/shieldops/sla/slo_advisor.py` — SLOTargetAdvisor
   - Workload scheduler: `src/shieldops/operations/workload_scheduler.py` — WorkloadSchedulingOptimizer
   - Cascade predictor: `src/shieldops/topology/cascade_predictor.py` — CascadingFailurePredictor
   - Resilience scorer: `src/shieldops/observability/resilience_scorer.py` — ResilienceScoreCalculator
   - Timeline reconstructor: `src/shieldops/incidents/timeline_reconstructor.py` — IncidentTimelineReconstructor
   - RI optimizer: `src/shieldops/billing/reserved_instance_optimizer.py` — ReservedInstanceOptimizer
   - Cost anomaly RCA: `src/shieldops/billing/cost_anomaly_rca.py` — CostAnomalyRootCauseAnalyzer
   - Spend allocation: `src/shieldops/billing/spend_allocation.py` — SpendAllocationEngine
   - Container scanner: `src/shieldops/security/container_scanner.py` — ContainerImageScanner
   - Cloud posture: `src/shieldops/security/cloud_posture_manager.py` — CloudSecurityPostureManager
   - Secrets detector: `src/shieldops/security/secrets_detector.py` — SecretsSprawlDetector
   - Runbook effectiveness: `src/shieldops/operations/runbook_effectiveness.py` — RunbookEffectivenessAnalyzer
   - API deprecation: `src/shieldops/analytics/api_deprecation_tracker.py` — APIDeprecationTracker
   - Dependency freshness: `src/shieldops/analytics/dependency_freshness.py` — DependencyFreshnessMonitor
   - Chaos designer: `src/shieldops/observability/chaos_designer.py` — ChaosExperimentDesigner
   - Game day planner: `src/shieldops/operations/game_day_planner.py` — GameDayPlanner
   - Failure mode catalog: `src/shieldops/topology/failure_mode_catalog.py` — FailureModeCatalog
   - On-call optimizer: `src/shieldops/incidents/oncall_optimizer.py` — OnCallRotationOptimizer
   - Alert correlation rules: `src/shieldops/observability/alert_correlation_rules.py` — AlertCorrelationRuleEngine
   - Incident review board: `src/shieldops/incidents/review_board.py` — IncidentReviewBoard
   - Commitment planner: `src/shieldops/billing/commitment_planner.py` — CloudCommitmentPlanner
   - Cost simulator: `src/shieldops/billing/cost_simulator.py` — CostSimulationEngine
   - FinOps maturity: `src/shieldops/billing/finops_maturity.py` — FinOpsMaturityScorer
   - Change failure tracker: `src/shieldops/changes/change_failure_tracker.py` — ChangeFailureRateTracker
   - Toil recommender: `src/shieldops/operations/toil_recommender.py` — ToilAutomationRecommender
   - SLI pipeline: `src/shieldops/sla/sli_pipeline.py` — SLICalculationPipeline
   - Deployment cadence: `src/shieldops/analytics/deployment_cadence.py` — DeploymentCadenceAnalyzer
   - Metric baseline: `src/shieldops/observability/metric_baseline.py` — MetricBaselineManager
   - Incident timeline: `src/shieldops/incidents/incident_timeline.py` — IncidentTimelineAnalyzer
   - Service health agg: `src/shieldops/topology/service_health_agg.py` — ServiceHealthAggregator
   - Alert fatigue: `src/shieldops/observability/alert_fatigue.py` — AlertFatigueScorer
   - Change window: `src/shieldops/changes/change_window.py` — ChangeWindowOptimizer
   - Resource waste: `src/shieldops/billing/resource_waste.py` — ResourceWasteDetector
   - Evidence chain: `src/shieldops/compliance/evidence_chain.py` — ComplianceEvidenceChain
   - Dependency update planner: `src/shieldops/topology/dependency_update_planner.py` — DependencyUpdatePlanner
   - Capacity forecast engine: `src/shieldops/analytics/capacity_forecast_engine.py` — CapacityForecastEngine
   - Runbook versioner: `src/shieldops/operations/runbook_versioner.py` — RunbookVersionManager
   - Team skill matrix: `src/shieldops/operations/team_skill_matrix.py` — TeamSkillMatrix
   - Error budget policy: `src/shieldops/sla/error_budget_policy.py` — ErrorBudgetPolicyEngine
   - Reliability target: `src/shieldops/sla/reliability_target.py` — ReliabilityTargetAdvisor
   - Severity calibrator: `src/shieldops/incidents/severity_calibrator.py` — IncidentSeverityCalibrator
   - Dependency mapper: `src/shieldops/topology/dependency_mapper.py` — ServiceDependencyMapper
   - Alert rule linter: `src/shieldops/observability/alert_rule_linter.py` — AlertRuleLinter
   - Deployment gate: `src/shieldops/changes/deployment_gate.py` — DeploymentApprovalGate
   - Billing reconciler: `src/shieldops/billing/billing_reconciler.py` — CloudBillingReconciler
   - Chargeback engine: `src/shieldops/billing/chargeback_engine.py` — CostChargebackEngine
   - Compliance drift: `src/shieldops/compliance/compliance_drift.py` — ComplianceDriftDetector
   - Comm planner: `src/shieldops/incidents/comm_planner.py` — IncidentCommunicationPlanner
   - Infra drift reconciler: `src/shieldops/operations/infra_drift_reconciler.py` — InfrastructureDriftReconciler
   - Service maturity: `src/shieldops/topology/service_maturity.py` — ServiceMaturityModel
   - Capacity right-timing: `src/shieldops/operations/capacity_right_timing.py` — CapacityRightTimingAdvisor
   - Outage predictor: `src/shieldops/observability/outage_predictor.py` — PredictiveOutageDetector
   - Impact quantifier: `src/shieldops/incidents/impact_quantifier.py` — IncidentImpactQuantifier
   - Policy violation tracker: `src/shieldops/compliance/policy_violation_tracker.py` — PolicyViolationTracker
   - Deploy health scorer: `src/shieldops/changes/deploy_health_scorer.py` — DeploymentHealthScorer
   - Runbook gap analyzer: `src/shieldops/operations/runbook_gap_analyzer.py` — RunbookGapAnalyzer
   - Credential expiry forecaster: `src/shieldops/security/credential_expiry_forecaster.py` — CredentialExpiryForecaster
   - On-call workload balancer: `src/shieldops/incidents/oncall_workload_balancer.py` — OnCallWorkloadBalancer
   - Cost anomaly predictor: `src/shieldops/billing/cost_anomaly_predictor.py` — CostAnomalyPredictor
   - Evidence scheduler: `src/shieldops/compliance/evidence_scheduler.py` — ComplianceEvidenceScheduler
   - Latency budget tracker: `src/shieldops/analytics/latency_budget_tracker.py` — LatencyBudgetTracker
   - Change conflict detector: `src/shieldops/changes/change_conflict_detector.py` — ChangeConflictDetector
   - Verify each module initializes in `src/shieldops/api/app.py` lifespan

6. **Check configuration**:
   - Verify `.env` file exists (warn if missing)
   - Check required env vars are set (DATABASE_URL, REDIS_URL, etc.)
   - Validate OPA policies: check `playbooks/policies/` for syntax

## Output Format
Report each check as PASS/FAIL/WARN with details.
If `--fix` is passed, auto-fix what's possible (format, install missing deps).
