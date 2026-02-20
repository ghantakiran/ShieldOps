# Security Agent

The Security Agent continuously monitors and enforces security posture across your
infrastructure. It scans for vulnerabilities, checks credential health, evaluates
compliance, and can optionally execute patches and rotations.

---

## Purpose

- Scan for CVEs using NVD and Trivy
- Check credential expiration and rotation status (via HashiCorp Vault)
- Evaluate compliance against frameworks (SOC 2, PCI-DSS, HIPAA)
- Synthesize an overall security posture score
- Optionally execute patches and credential rotations (policy-gated)
- Support extended scan types: containers, IaC, git secrets, Kubernetes, network

---

## Graph Workflow

```
[route by scan_type]
      |
      +-- [full/cve_only] --> scan_vulnerabilities
      +-- [container] --> scan_containers
      +-- [git_secrets/git_deps] --> scan_secrets
      +-- [iac] --> scan_iac
      +-- [network] --> scan_network
      +-- [k8s_security] --> scan_k8s_security
      |
      v
assess_findings
      |
      +-- [not cve_only] --> check_credentials
      |                           |
      |                    +-- [not cve_only/creds_only] --> evaluate_compliance
      |                    |
      |                    +-- [skip] --> synthesize_posture
      |
      +-- [cve_only/extended] --> synthesize_posture
                                       |
                                       v
                              [persist_findings?] --> persist_findings
                                       |
                                       v
                              [execute_actions?]
                                       |
                                +-- [no] --> END
                                |
                                +-- [yes] --> evaluate_action_policy
                                                    |
                                              +-- [denied] --> END
                                              |
                                              +-- [allowed] --> execute_patches
                                                                    |
                                                              +-- [rotations needed] --> rotate_credentials --> END
                                                              |
                                                              +-- [none] --> END
```

### Nodes

| Node | Description |
|------|-------------|
| `scan_vulnerabilities` | Query CVE sources (NVD, Trivy) for known vulnerabilities |
| `scan_containers` | Trivy container image scanning |
| `scan_secrets` | Gitleaks secret detection + osv-scanner dependency audit |
| `scan_iac` | Checkov infrastructure-as-code scanning |
| `scan_network` | Network security scanning |
| `scan_k8s_security` | Kubernetes security configuration audit |
| `assess_findings` | Prioritize and categorize scan findings |
| `check_credentials` | Check credential status via Vault and cloud IAM |
| `evaluate_compliance` | Evaluate controls against compliance frameworks |
| `synthesize_posture` | Calculate overall security posture score |
| `persist_findings` | Write findings to the vulnerability lifecycle database |
| `evaluate_action_policy` | Check OPA policies for remediation actions |
| `execute_patches` | Apply security patches (if policy-allowed) |
| `rotate_credentials` | Rotate expiring/compromised credentials |

---

## Scan Types

| Scan Type | Description |
|-----------|-------------|
| `full` | CVEs + credentials + compliance (default) |
| `cve_only` | Only CVE vulnerability scanning |
| `credentials_only` | Only credential health checks |
| `compliance_only` | Only compliance framework evaluation |
| `container` | Container image vulnerability scanning |
| `git_secrets` | Git repository secret detection |
| `git_deps` | Dependency vulnerability scanning |
| `iac` | Infrastructure-as-code security scanning |
| `network` | Network security scanning |
| `k8s_security` | Kubernetes security configuration |

---

## Example Usage

### Trigger a full security scan

```bash
curl -X POST http://localhost:8000/api/v1/security/scans \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "environment": "production",
    "scan_type": "full",
    "compliance_frameworks": ["soc2", "pci-dss"]
  }'
```

### Get security posture

```bash
curl http://localhost:8000/api/v1/security/posture \
  -H "Authorization: Bearer $TOKEN"
```

### List CVEs from latest scan

```bash
curl "http://localhost:8000/api/v1/security/cves?severity=critical" \
  -H "Authorization: Bearer $TOKEN"
```

### Check compliance status

```bash
curl http://localhost:8000/api/v1/security/compliance/soc2 \
  -H "Authorization: Bearer $TOKEN"
```

---

## Scheduled Scanning

The security agent runs automatically via the job scheduler:

- **Every 6 hours:** Periodic security scan
- **Daily:** Security newsletter generation
- **Weekly:** Weekly security digest

These are configured in `src/shieldops/api/app.py` during startup.

---

## Scanner Configuration

Enable optional scanners via environment variables:

| Scanner | Variable | Tool |
|---------|----------|------|
| IaC | `SHIELDOPS_IAC_SCANNER_ENABLED=true` | Checkov |
| Git secrets | `SHIELDOPS_GIT_SCANNER_ENABLED=true` | Gitleaks |
| Git dependencies | `SHIELDOPS_GIT_SCANNER_ENABLED=true` | osv-scanner |
| Kubernetes | `SHIELDOPS_K8S_SCANNER_ENABLED=true` | Built-in |
| Network | `SHIELDOPS_NETWORK_SCANNER_ENABLED=true` | Built-in |
| Containers | `SHIELDOPS_TRIVY_SERVER_URL=...` | Trivy |
