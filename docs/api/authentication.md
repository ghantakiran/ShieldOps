# Authentication

ShieldOps uses JWT (JSON Web Tokens) for API authentication. All endpoints except
`/health`, `/ready`, and `/metrics` require a valid token.

---

## Auth Flow

```
1. POST /api/v1/auth/login  -->  JWT access token
2. Include token in Authorization header for all subsequent requests
3. POST /api/v1/auth/refresh  -->  New token (before expiry)
4. POST /api/v1/auth/revoke  -->  Invalidate current token
```

---

## Roles

ShieldOps defines three user roles with cascading permissions:

| Role | Description | Permissions |
|------|-------------|-------------|
| `admin` | Full platform access | All operations, user management, agent config |
| `operator` | Day-to-day operations | Trigger investigations/remediations, approve actions |
| `viewer` | Read-only access | View investigations, agents, analytics |

---

## Endpoints

### Login

```
POST /api/v1/auth/login
```

Authenticate with email and password. Returns a JWT access token.

**Request:**

```json
{
  "email": "admin@shieldops.dev",
  "password": "shieldops-admin"
}
```

**Response (200):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Errors:**

| Status | Description |
|--------|-------------|
| 401 | Invalid email or password |
| 403 | Account disabled |
| 503 | Database unavailable |

---

### Register (admin only)

```
POST /api/v1/auth/register
```

Create a new user account. Requires admin role.

**Request:**

```json
{
  "email": "engineer@company.com",
  "name": "Jane Engineer",
  "password": "secure-password",
  "role": "operator"
}
```

**Response (201):**

```json
{
  "id": "usr-abc123",
  "email": "engineer@company.com",
  "name": "Jane Engineer",
  "role": "operator",
  "is_active": true
}
```

**Errors:**

| Status | Description |
|--------|-------------|
| 401 | Not authenticated |
| 403 | Requires admin role |
| 409 | Email already registered |

---

### Get Current User

```
GET /api/v1/auth/me
```

Return the currently authenticated user.

**Response (200):**

```json
{
  "id": "usr-abc123",
  "email": "admin@shieldops.dev",
  "name": "Admin",
  "role": "admin",
  "is_active": true
}
```

---

### Refresh Token

```
POST /api/v1/auth/refresh
```

Issue a new access token for the currently authenticated user.

**Response (200):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### Revoke Token

```
POST /api/v1/auth/revoke
```

Revoke the current token by adding its JTI (JWT ID) to a Redis blocklist.
The token will be rejected for all subsequent requests until its natural expiry.

**Response:** 204 No Content

---

## Using Tokens

Include the access token in the `Authorization` header:

```bash
curl http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## Token Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SHIELDOPS_JWT_SECRET_KEY` | `change-me-in-production` | HMAC signing secret |
| `SHIELDOPS_JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `SHIELDOPS_JWT_EXPIRE_MINUTES` | `60` | Token lifetime in minutes |

!!! warning
    Always set a strong, unique `JWT_SECRET_KEY` in production. The default value
    is intentionally weak and will be flagged in security scans.

---

## OIDC / SSO

ShieldOps supports OpenID Connect for enterprise SSO integration. When enabled,
users can authenticate via their identity provider (Okta, Azure AD, Google, etc.).

### Configuration

| Variable | Description |
|----------|-------------|
| `SHIELDOPS_OIDC_ENABLED` | Set to `true` to enable OIDC |
| `SHIELDOPS_OIDC_ISSUER_URL` | OIDC provider issuer URL |
| `SHIELDOPS_OIDC_CLIENT_ID` | Application client ID |
| `SHIELDOPS_OIDC_CLIENT_SECRET` | Application client secret |
| `SHIELDOPS_OIDC_REDIRECT_URI` | OAuth callback URL |
| `SHIELDOPS_OIDC_SCOPES` | Requested scopes (default: `openid email profile`) |

### Flow

1. User navigates to `/api/v1/auth/oidc/login`
2. Redirected to the identity provider
3. After authentication, redirected back to `/api/v1/auth/oidc/callback`
4. ShieldOps issues a JWT token and redirects to the dashboard

---

## Rate Limiting

Auth endpoints have stricter rate limits:

| Endpoint | Limit |
|----------|-------|
| `/auth/login` | 10 requests per minute |
| `/auth/register` | 5 requests per minute |
| Other endpoints | Role-based (60-300 per minute) |
