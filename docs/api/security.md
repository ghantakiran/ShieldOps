# Security API

The Security API provides endpoints for managing security scans, viewing posture,
browsing CVEs, and checking compliance status.

---

## Endpoints

### Trigger Security Scan (async)

```
POST /api/v1/security/scans
```

Start a new security scan. Runs asynchronously.

**Required role:** `admin` or `operator`

**Request body:**

```json
{
  "environment": "production",
  "scan_type": "full",
  "target_resources": [],
  "compliance_frameworks": ["soc2", "pci-dss"],
  "execute_actions": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `environment` | string | no | Target environment (default: `production`) |
| `scan_type` | string | no | `full`, `cve_only`, `credentials_only`, `compliance_only`, `container`, `iac`, `git_secrets`, `network`, `k8s_security` (default: `full`) |
| `target_resources` | array | no | Specific resources to scan (empty = all) |
| `compliance_frameworks` | array | no | Frameworks to evaluate |
| `execute_actions` | bool | no | Auto-apply patches and rotations (default: `false`) |

!!! warning
    Setting `execute_actions: true` will attempt to apply patches and rotate credentials
    automatically. This is gated by OPA policy evaluation.

**Response (202):**

```json
{
  "status": "accepted",
  "scan_type": "full",
  "environment": "production",
  "message": "Security scan started. Use GET /security/scans to track progress."
}
```

---

### Trigger Security Scan (sync)

```
POST /api/v1/security/scans/sync
```

Same as above but waits for completion.

**Required role:** `admin` or `operator`

---

### List Security Scans

```
GET /api/v1/security/scans
```

List all security scans with pagination.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scan_type` | string | (all) | Filter by scan type |
| `limit` | int | 50 | Page size |
| `offset` | int | 0 | Page offset |

---

### Get Scan Detail

```
GET /api/v1/security/scans/{scan_id}
```

Get full security scan detail including findings.

**Errors:** 404 if not found.

---

### Get Scan Vulnerabilities

```
GET /api/v1/security/scans/{scan_id}/vulnerabilities
```

Get CVE findings for a specific scan.

**Query parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `severity` | string | Filter by severity (e.g., `critical`, `high`) |

---

### Get Security Posture

```
GET /api/v1/security/posture
```

Get overall security posture from the most recent completed full scan.

**Response (200):**

```json
{
  "overall_score": 87.5,
  "frameworks": {
    "soc2": 92.0,
    "pci-dss": 83.0
  },
  "critical_cves": 2,
  "pending_patches": 5,
  "credentials_expiring_soon": 1
}
```

---

### List CVEs

```
GET /api/v1/security/cves
```

List CVEs from the most recent scan.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `severity` | string | (all) | Filter by severity |
| `limit` | int | 50 | Max results |

**Response (200):**

```json
{
  "cves": [
    {
      "cve_id": "CVE-2024-1234",
      "severity": "critical",
      "affected_package": "openssl",
      "affected_version": "3.0.1",
      "fixed_version": "3.0.14",
      "description": "Buffer overflow in TLS handshake"
    }
  ],
  "total": 12
}
```

---

### Get Compliance Status

```
GET /api/v1/security/compliance/{framework}
```

Get compliance status for a specific framework.

**Path parameters:**

| Parameter | Description |
|-----------|-------------|
| `framework` | Framework name (e.g., `soc2`, `pci-dss`, `hipaa`) |

**Response (200):**

```json
{
  "framework": "soc2",
  "score": 92.0,
  "controls": [
    {
      "control_id": "CC6.1",
      "name": "Logical and Physical Access Controls",
      "status": "pass",
      "evidence": "All access requires MFA"
    }
  ]
}
```
