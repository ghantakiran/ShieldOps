# Security Scan Skill

Run security audits on ShieldOps codebase and agent configurations.

## Usage
`/scan-security [--scope <area>] [--severity <level>]`

## Scopes
- `code` — Static analysis of Python code (ruff, bandit, safety)
- `deps` — Dependency vulnerability scan
- `policies` — OPA policy completeness check
- `agents` — Agent blast-radius and permission audit
- `infra` — Infrastructure-as-code security scan (checkov, tfsec)
- `all` — Full security audit

## Process

1. **Code Security**: Run bandit for Python security issues, check for hardcoded secrets
2. **Dependency Audit**: Check all dependencies against CVE databases
3. **OPA Policy Review**: Verify all agent actions have corresponding policy rules
4. **Agent Permissions**: Audit blast-radius limits per environment
5. **Infrastructure**: Scan Terraform/K8s configs for misconfigurations
6. **Generate Report**: Severity-rated findings with remediation guidance

## Severity Levels
- **CRITICAL**: Hardcoded secrets, SQL injection, unauthenticated endpoints
- **HIGH**: Missing OPA policies, overly permissive agent actions
- **MEDIUM**: Outdated dependencies with known CVEs
- **LOW**: Code style issues, missing type hints

## Output
Security report saved to `docs/security/scan-{date}.md`
