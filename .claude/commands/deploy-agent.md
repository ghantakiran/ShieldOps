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
