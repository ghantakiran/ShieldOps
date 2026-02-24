# Security Scan Skill

Run security audits on ShieldOps codebase and agent configurations.

## Usage
`/scan-security [--scope <area>] [--severity <level>]`

## Scopes
- `code` — Static analysis of Python code (ruff, bandit, safety)
- `deps` — Dependency vulnerability scan
- `policies` — OPA policy completeness check (includes PolicyCodeGenerator output)
- `agents` — Agent blast-radius and permission audit (includes AgentDecisionExplainer)
- `compliance` — Compliance gap analysis via `ComplianceGapAnalyzer` + `ComplianceAutomationEngine`
- `audit` — Configuration audit trail via `ConfigurationAuditTrail`
- `isolation` — Tenant resource isolation checks via `TenantResourceIsolationManager`
- `licenses` — Dependency license compliance via `DependencyLicenseScanner`
- `access` — Access certification review via `AccessCertificationManager`
- `contracts` — API contract drift and breaking changes via `APIContractTestingEngine`
- `incidents` — Security incident response tracking via `SecurityIncidentResponseTracker`
- `vulns` — Vulnerability lifecycle and exploit risk via `VulnerabilityLifecycleManager`
- `api-threats` — API endpoint threat detection via `APISecurityMonitor`
- `infra` — Infrastructure-as-code security scan (checkov, tfsec)
- `all` — Full security audit

## Process

1. **Code Security**: Run bandit for Python security issues, check for hardcoded secrets
2. **Dependency Audit**: Check all dependencies against CVE databases
3. **OPA Policy Review**: Verify all agent actions have corresponding policy rules
4. **Agent Permissions**: Audit blast-radius limits per environment
5. **Compliance Gap Analysis**: Run `ComplianceGapAnalyzer` from `src/shieldops/compliance/gap_analyzer.py`
6. **Compliance Automation**: Check auto-remediation rules via `ComplianceAutomationEngine` (`src/shieldops/compliance/automation_rules.py`)
7. **Configuration Audit**: Review config change trail via `ConfigurationAuditTrail` (`src/shieldops/audit/config_audit.py`)
8. **Tenant Isolation**: Verify resource boundaries via `TenantResourceIsolationManager` (`src/shieldops/policy/tenant_isolation.py`)
9. **Infrastructure**: Scan Terraform/K8s configs for misconfigurations
10. **License Compliance**: Scan dependency licenses via `DependencyLicenseScanner` (`src/shieldops/compliance/license_scanner.py`)
11. **Access Certification**: Review expired/uncertified grants via `AccessCertificationManager` (`src/shieldops/compliance/access_certification.py`)
12. **API Contract Testing**: Detect breaking changes and schema drift via `APIContractTestingEngine` (`src/shieldops/api/contract_testing.py`)
13. **Security Incident Review**: Check active incidents via `SecurityIncidentResponseTracker` (`src/shieldops/security/incident_response.py`)
14. **Vulnerability Lifecycle**: Review overdue patches and exploit risk via `VulnerabilityLifecycleManager` (`src/shieldops/security/vuln_lifecycle.py`)
15. **API Threat Detection**: Assess endpoint risk and suspicious patterns via `APISecurityMonitor` (`src/shieldops/security/api_security.py`)
16. **Generate Report**: Severity-rated findings with remediation guidance

## Severity Levels
- **CRITICAL**: Hardcoded secrets, SQL injection, unauthenticated endpoints
- **HIGH**: Missing OPA policies, overly permissive agent actions
- **MEDIUM**: Outdated dependencies with known CVEs
- **LOW**: Code style issues, missing type hints

## Output
Security report saved to `docs/security/scan-{date}.md`
