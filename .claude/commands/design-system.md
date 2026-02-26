# System Design Skill

Design new ShieldOps components, APIs, or agent workflows.

## Usage
`/design-system <component> [--depth <shallow|deep>]`

## Process

1. **Requirements Gathering**:
   - Read relevant PRDs from `docs/prd/`
   - Identify stakeholders and constraints
   - Map dependencies on existing components

2. **Architecture Design**:
   - Define component boundaries and interfaces
   - Choose patterns (event-driven, request-response, CQRS)
   - Design data models (Pydantic schemas)
   - Plan LangGraph workflow (if agent-related)

3. **API Design** (if applicable):
   - Define REST endpoints with OpenAPI spec
   - Design request/response schemas
   - Plan authentication and authorization
   - Define rate limits and quotas

4. **Safety Analysis**:
   - Identify failure modes and blast radius
   - Design circuit breakers and fallbacks
   - Plan OPA policies needed (leverage `PolicyCodeGenerator` for Rego stubs)
   - Define rollback procedures
   - Assess deployment risk via `DeploymentRiskPredictor`
   - Verify compliance gaps via `ComplianceGapAnalyzer`
   - Simulate service dependency impact via `ServiceDependencyImpactAnalyzer` (`src/shieldops/topology/impact_analyzer.py`)
   - Evaluate compliance automation rules via `ComplianceAutomationEngine` (`src/shieldops/compliance/automation_rules.py`)
   - Check license compliance via `DependencyLicenseScanner` (`src/shieldops/compliance/license_scanner.py`)
   - Verify service catalog completeness via `ServiceCatalogManager` (`src/shieldops/topology/service_catalog.py`)
   - Validate API contracts via `APIContractTestingEngine` (`src/shieldops/api/contract_testing.py`)
   - Detect orphaned resources via `OrphanedResourceDetector` (`src/shieldops/billing/orphan_detector.py`)
   - Score change risk via `ChangeIntelligenceAnalyzer` (`src/shieldops/changes/change_intelligence.py`)
   - Predict SLO burn rate via `SLOBurnRatePredictor` (`src/shieldops/sla/burn_predictor.py`)
   - Score dependency health via `DependencyHealthScorer` (`src/shieldops/topology/dependency_scorer.py`)
   - Enforce tag governance via `ResourceTagGovernanceEngine` (`src/shieldops/billing/tag_governance.py`)
   - Analyze team performance via `TeamPerformanceAnalyzer` (`src/shieldops/analytics/team_performance.py`)
   - Analyze DB performance via `DatabasePerformanceAnalyzer` (`src/shieldops/analytics/db_performance.py`)
   - Monitor queue health via `QueueHealthMonitor` (`src/shieldops/observability/queue_health.py`)
   - Right-size resources via `CapacityRightSizer` (`src/shieldops/billing/right_sizer.py`)
   - Optimize storage tiers via `StorageTierOptimizer` (`src/shieldops/billing/storage_optimizer.py`)
   - Track resource lifecycle via `ResourceLifecycleTracker` (`src/shieldops/billing/resource_lifecycle.py`)
   - Optimize alert routing via `AlertRoutingOptimizer` (`src/shieldops/observability/alert_routing.py`)
   - Advise on SLO targets via `SLOTargetAdvisor` (`src/shieldops/sla/slo_advisor.py`)
   - Predict cascade failures via `CascadingFailurePredictor` (`src/shieldops/topology/cascade_predictor.py`)
   - Score service resilience via `ResilienceScoreCalculator` (`src/shieldops/observability/resilience_scorer.py`)
   - Optimize reserved instances via `ReservedInstanceOptimizer` (`src/shieldops/billing/reserved_instance_optimizer.py`)
   - Allocate shared spend via `SpendAllocationEngine` (`src/shieldops/billing/spend_allocation.py`)
   - Monitor dependency freshness via `DependencyFreshnessMonitor` (`src/shieldops/analytics/dependency_freshness.py`)
   - Plan cloud commitments via `CloudCommitmentPlanner` (`src/shieldops/billing/commitment_planner.py`)
   - Simulate cost scenarios via `CostSimulationEngine` (`src/shieldops/billing/cost_simulator.py`)
   - Calculate SLIs via `SLICalculationPipeline` (`src/shieldops/sla/sli_pipeline.py`)
   - Check failure modes via `FailureModeCatalog` (`src/shieldops/topology/failure_mode_catalog.py`)
   - Detect resource waste via `ResourceWasteDetector` (`src/shieldops/billing/resource_waste.py`)
   - Forecast capacity via `CapacityForecastEngine` (`src/shieldops/analytics/capacity_forecast_engine.py`)
   - Plan dependency updates via `DependencyUpdatePlanner` (`src/shieldops/topology/dependency_update_planner.py`)
   - Aggregate service health via `ServiceHealthAggregator` (`src/shieldops/topology/service_health_agg.py`)
   - Map service dependencies via `ServiceDependencyMapper` (`src/shieldops/topology/dependency_mapper.py`)
   - Assess service maturity via `ServiceMaturityModel` (`src/shieldops/topology/service_maturity.py`)
   - Allocate cost chargebacks via `CostChargebackEngine` (`src/shieldops/billing/chargeback_engine.py`)
   - Reconcile infrastructure drift via `InfrastructureDriftReconciler` (`src/shieldops/operations/infra_drift_reconciler.py`)
   - Predict cost anomalies via `CostAnomalyPredictor` (`src/shieldops/billing/cost_anomaly_predictor.py`)
   - Advise capacity right-timing via `CapacityRightTimingAdvisor` (`src/shieldops/operations/capacity_right_timing.py`)
   - Analyze runbook gaps via `RunbookGapAnalyzer` (`src/shieldops/operations/runbook_gap_analyzer.py`)
   - Compute unit economics via `CostUnitEconomicsEngine` (`src/shieldops/billing/unit_economics.py`)
   - Forecast resource exhaustion via `ResourceExhaustionForecaster` (`src/shieldops/analytics/resource_exhaustion.py`)
   - Detect idle resources via `IdleResourceDetector` (`src/shieldops/billing/idle_resource_detector.py`)
   - Advise incident response via `IncidentResponseAdvisor` (`src/shieldops/incidents/response_advisor.py`)
   - Analyze metric root cause via `MetricRootCauseAnalyzer` (`src/shieldops/analytics/metric_rca.py`)
   - Forecast SLO compliance via `SLOComplianceForecaster` (`src/shieldops/sla/slo_forecast.py`)
   - Evaluate remediation decisions via `AutoRemediationDecisionEngine` (`src/shieldops/operations/remediation_decision.py`)
   - Monitor dependency lag via `DependencyLagMonitor` (`src/shieldops/topology/dependency_lag.py`)
   - Track escalation effectiveness via `EscalationEffectivenessTracker` (`src/shieldops/incidents/escalation_effectiveness.py`)
   - Optimize cloud discounts via `CloudDiscountOptimizer` (`src/shieldops/billing/discount_optimizer.py`)
   - Analyze audit trails via `ComplianceAuditTrailAnalyzer` (`src/shieldops/compliance/audit_trail_analyzer.py`)
   - Throttle change velocity via `ChangeVelocityThrottle` (`src/shieldops/changes/velocity_throttle.py`)
   - Tune alerts via feedback via `AlertTuningFeedbackLoop` (`src/shieldops/observability/alert_tuning_feedback.py`)
   - Detect knowledge decay via `KnowledgeDecayDetector` (`src/shieldops/knowledge/knowledge_decay.py`)
   - Score observability coverage via `ObservabilityCoverageScorer` (`src/shieldops/observability/coverage_scorer.py`)
   - Manage metric cardinality via `MetricCardinalityManager` (`src/shieldops/observability/cardinality_manager.py`)
   - Optimize log retention via `LogRetentionOptimizer` (`src/shieldops/observability/log_retention_optimizer.py`)
   - Score dashboard quality via `DashboardQualityScorer` (`src/shieldops/observability/dashboard_quality.py`)
   - Track post-incident actions via `PostIncidentActionTracker` (`src/shieldops/incidents/action_tracker.py`)
   - Score deployment confidence via `DeploymentConfidenceScorer` (`src/shieldops/changes/deployment_confidence.py`)
   - Detect reliability regressions via `ReliabilityRegressionDetector` (`src/shieldops/sla/reliability_regression.py`)
   - Detect permission drift via `PermissionDriftDetector` (`src/shieldops/security/permission_drift.py`)
   - Manage feature flag lifecycle via `FeatureFlagLifecycleManager` (`src/shieldops/config/flag_lifecycle.py`)
   - Monitor API version health via `APIVersionHealthMonitor` (`src/shieldops/topology/api_version_health.py`)
   - Assess SRE maturity via `SREMaturityAssessor` (`src/shieldops/operations/sre_maturity.py`)
   - Track incident lessons via `IncidentLearningTracker` (`src/shieldops/incidents/learning_tracker.py`)
   - Analyze cache effectiveness via `CacheEffectivenessAnalyzer` (`src/shieldops/analytics/cache_effectiveness.py`)
   - Analyze build pipelines via `BuildPipelineAnalyzer` (`src/shieldops/analytics/build_pipeline.py`)
   - Track code review velocity via `CodeReviewVelocityTracker` (`src/shieldops/analytics/review_velocity.py`)
   - Monitor dev environments via `DevEnvironmentHealthMonitor` (`src/shieldops/operations/dev_environment.py`)
   - Analyze traffic patterns via `TrafficPatternAnalyzer` (`src/shieldops/topology/traffic_pattern.py`)
   - Manage rate limit policies via `RateLimitPolicyManager` (`src/shieldops/topology/rate_limit_policy.py`)
   - Monitor circuit breaker health via `CircuitBreakerHealthMonitor` (`src/shieldops/topology/circuit_breaker_health.py`)
   - Monitor data pipeline reliability via `DataPipelineReliabilityMonitor` (`src/shieldops/observability/data_pipeline.py`)
   - Forecast queue depth via `QueueDepthForecaster` (`src/shieldops/observability/queue_depth_forecast.py`)
   - Monitor connection pools via `ConnectionPoolMonitor` (`src/shieldops/analytics/connection_pool.py`)
   - Analyze license risk via `DependencyLicenseRiskAnalyzer` (`src/shieldops/compliance/license_risk.py`)
   - Analyze communication effectiveness via `CommEffectivenessAnalyzer` (`src/shieldops/incidents/comm_effectiveness.py`)
   - Score operational readiness via `OperationalReadinessScorer` (`src/shieldops/operations/readiness_scorer.py`)
   - Auto-triage incidents via `IncidentAutoTriageEngine` (`src/shieldops/incidents/auto_triage.py`)
   - Orchestrate self-healing via `SelfHealingOrchestrator` (`src/shieldops/operations/self_healing.py`)
   - Detect recurrence patterns via `RecurrencePatternDetector` (`src/shieldops/incidents/recurrence_pattern.py`)
   - Score policy impact via `PolicyImpactScorer` (`src/shieldops/compliance/policy_impact.py`)
   - Analyze audit intelligence via `AuditIntelligenceAnalyzer` (`src/shieldops/audit/audit_intelligence.py`)
   - Identify automation gaps via `AutomationGapIdentifier` (`src/shieldops/operations/automation_gap.py`)
   - Model capacity demand via `CapacityDemandModeler` (`src/shieldops/analytics/capacity_demand.py`)
   - Advise on spot instances via `SpotInstanceAdvisor` (`src/shieldops/billing/spot_advisor.py`)
   - Track scaling efficiency via `ScalingEfficiencyTracker` (`src/shieldops/operations/scaling_efficiency.py`)
   - Detect reliability antipatterns via `ReliabilityAntiPatternDetector` (`src/shieldops/topology/reliability_antipattern.py`)
   - Forecast error budgets via `ErrorBudgetForecaster` (`src/shieldops/sla/error_budget_forecast.py`)
   - Score dependency risk via `DependencyRiskScorer` (`src/shieldops/topology/dependency_risk.py`)
   - Match similar incidents via `IncidentSimilarityEngine` (`src/shieldops/incidents/incident_similarity.py`)
   - Calculate incident costs via `IncidentCostCalculator` (`src/shieldops/incidents/incident_cost.py`)
   - Track post-incident follow-ups via `PostIncidentFollowupTracker` (`src/shieldops/incidents/followup_tracker.py`)
   - Track team cognitive load via `TeamCognitiveLoadTracker` (`src/shieldops/operations/cognitive_load.py`)
   - Score cross-team collaboration via `CrossTeamCollaborationScorer` (`src/shieldops/analytics/collaboration_scorer.py`)
   - Track knowledge contributions via `KnowledgeContributionTracker` (`src/shieldops/knowledge/contribution_tracker.py`)
   - Profile API performance via `APIPerformanceProfiler` (`src/shieldops/analytics/api_performance.py`)
   - Detect resource contention via `ResourceContentionDetector` (`src/shieldops/analytics/resource_contention.py`)
   - Analyze deployment rollbacks via `DeploymentRollbackAnalyzer` (`src/shieldops/changes/rollback_analyzer.py`)
   - Monitor attack surface via `AttackSurfaceMonitor` (`src/shieldops/security/attack_surface.py`)
   - Recommend runbooks via `RunbookRecommendationEngine` (`src/shieldops/operations/runbook_recommender.py`)
   - Score platform reliability via `PlatformReliabilityScorecard` (`src/shieldops/sla/reliability_scorecard.py`)

5. **Documentation**:
   - Write Architecture Decision Record (ADR) in `docs/architecture/`
   - Include diagrams (Mermaid format)
   - Document trade-offs and alternatives considered

## Output
- ADR document in `docs/architecture/adr-{number}-{name}.md`
- Updated component diagram
- API spec (if applicable)
