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
