# Review Agent Skill

Review ShieldOps agent code for correctness, safety, and reliability.

## Usage
`/review-agent [--scope <file|module|all>]`

## Review Checklist

### Safety (Critical)
- [ ] All infrastructure-modifying actions pass through OPA policy evaluation
- [ ] Rollback capability exists for every write operation
- [ ] Confidence thresholds correctly gate autonomous vs. approval-required actions
- [ ] Blast radius limits enforced per environment
- [ ] No hardcoded credentials or secrets
- [ ] Audit trail logging for every action

### Reliability
- [ ] Error handling at every external call (APIs, connectors, LLM)
- [ ] Timeout configuration for all async operations
- [ ] Graceful degradation (agent fails safe, not destructive)
- [ ] State persistence across retries (LangGraph checkpointing)
- [ ] Idempotent actions (safe to retry)

### Agent Architecture
- [ ] LangGraph state schema matches PRD requirements
- [ ] Node functions are pure (input → output, no hidden side effects)
- [ ] Conditional edges have complete coverage (no missing branches)
- [ ] Tool functions properly typed and documented
- [ ] Reasoning chain captures every decision point
- [ ] Decision explainability via `AgentDecisionExplainer` (`src/shieldops/agents/decision_explainer.py`)
- [ ] Approval delegation rules respected (`src/shieldops/policy/approval/approval_delegation.py`)
- [ ] Tenant isolation boundaries enforced (`src/shieldops/policy/tenant_isolation.py`)
- [ ] Configuration changes tracked via `ConfigurationAuditTrail` (`src/shieldops/audit/config_audit.py`)
- [ ] Configuration parity validated across environments via `ConfigurationParityValidator` (`src/shieldops/config/parity_validator.py`)
- [ ] Release approval gates enforced via `ReleaseManagementTracker` (`src/shieldops/changes/release_manager.py`)
- [ ] DR readiness verified for affected services via `DisasterRecoveryReadinessTracker` (`src/shieldops/observability/dr_readiness.py`)
- [ ] Incident deduplication active via `IncidentDeduplicationEngine` (`src/shieldops/incidents/dedup_engine.py`)
- [ ] Change risk scored via `ChangeIntelligenceAnalyzer` (`src/shieldops/changes/change_intelligence.py`)
- [ ] Safety gate evaluated before deployment via `ChangeIntelligenceAnalyzer.evaluate_safety_gate()`
- [ ] Security incidents tracked via `SecurityIncidentResponseTracker` (`src/shieldops/security/incident_response.py`)
- [ ] API endpoint threats monitored via `APISecurityMonitor` (`src/shieldops/security/api_security.py`)
- [ ] Vulnerability patches tracked via `VulnerabilityLifecycleManager` (`src/shieldops/security/vuln_lifecycle.py`)
- [ ] Runbook executions logged via `RunbookExecutionEngine` (`src/shieldops/operations/runbook_engine.py`)
- [ ] Certificate expiry tracked via `CertificateExpiryMonitor` (`src/shieldops/security/cert_monitor.py`)
- [ ] Network flows monitored via `NetworkFlowAnalyzer` (`src/shieldops/security/network_flow.py`)
- [ ] Database performance analyzed via `DatabasePerformanceAnalyzer` (`src/shieldops/analytics/db_performance.py`)
- [ ] Escalation patterns detected via `EscalationPatternAnalyzer` (`src/shieldops/incidents/escalation_analyzer.py`)
- [ ] Container images scanned via `ContainerImageScanner` (`src/shieldops/security/container_scanner.py`)
- [ ] Cloud posture evaluated via `CloudSecurityPostureManager` (`src/shieldops/security/cloud_posture_manager.py`)
- [ ] Secrets sprawl checked via `SecretsSprawlDetector` (`src/shieldops/security/secrets_detector.py`)
- [ ] Cascade failures predicted via `CascadingFailurePredictor` (`src/shieldops/topology/cascade_predictor.py`)
- [ ] Chaos experiments designed via `ChaosExperimentDesigner` (`src/shieldops/observability/chaos_designer.py`)
- [ ] Change failure rates tracked via `ChangeFailureRateTracker` (`src/shieldops/changes/change_failure_tracker.py`)
- [ ] SLI calculations verified via `SLICalculationPipeline` (`src/shieldops/sla/sli_pipeline.py`)
- [ ] FinOps maturity assessed via `FinOpsMaturityScorer` (`src/shieldops/billing/finops_maturity.py`)
- [ ] Deployment cadence analyzed via `DeploymentCadenceAnalyzer` (`src/shieldops/analytics/deployment_cadence.py`)
- [ ] Capacity forecasts verified via `CapacityForecastEngine` (`src/shieldops/analytics/capacity_forecast_engine.py`)
- [ ] Metric baselines tracked via `MetricBaselineManager` (`src/shieldops/observability/metric_baseline.py`)
- [ ] Team skills assessed via `TeamSkillMatrix` (`src/shieldops/operations/team_skill_matrix.py`)
- [ ] Reliability targets advised via `ReliabilityTargetAdvisor` (`src/shieldops/sla/reliability_target.py`)
- [ ] Incident severity calibrated via `IncidentSeverityCalibrator` (`src/shieldops/incidents/severity_calibrator.py`)
- [ ] Service dependencies mapped via `ServiceDependencyMapper` (`src/shieldops/topology/dependency_mapper.py`)
- [ ] Billing reconciled via `CloudBillingReconciler` (`src/shieldops/billing/billing_reconciler.py`)
- [ ] Deploy health scored via `DeploymentHealthScorer` (`src/shieldops/changes/deploy_health_scorer.py`)
- [ ] Latency budgets tracked via `LatencyBudgetTracker` (`src/shieldops/analytics/latency_budget_tracker.py`)
- [ ] Change conflicts detected via `ChangeConflictDetector` (`src/shieldops/changes/change_conflict_detector.py`)
- [ ] SLA cascading computed via `ServiceSLACascader` (`src/shieldops/sla/sla_cascader.py`)
- [ ] SLA penalties calculated via `SLAPenaltyCalculator` (`src/shieldops/sla/penalty_calculator.py`)
- [ ] Canary deployments analyzed via `DeploymentCanaryAnalyzer` (`src/shieldops/changes/canary_analyzer.py`)

### Testing
- [ ] Unit tests for all node functions
- [ ] Integration tests for connector operations
- [ ] Agent simulation tests with historical incidents
- [ ] Policy evaluation tests for all action types
- [ ] Edge cases: timeout, partial failure, concurrent operations

## Severity Levels
- **P0 (Block):** Safety violation, missing policy check, data loss risk
- **P1 (Must Fix):** Missing error handling, untested code path, reliability gap
- **P2 (Should Fix):** Code style, missing type hints, documentation gaps
- **P3 (Nice to Have):** Performance optimization, refactoring suggestions
