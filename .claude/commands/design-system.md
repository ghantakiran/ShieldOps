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

5. **Documentation**:
   - Write Architecture Decision Record (ADR) in `docs/architecture/`
   - Include diagrams (Mermaid format)
   - Document trade-offs and alternatives considered

## Output
- ADR document in `docs/architecture/adr-{number}-{name}.md`
- Updated component diagram
- API spec (if applicable)
