# Installation

This page covers all methods for setting up ShieldOps locally.

---

## Option 1: Make-based setup (recommended)

The fastest path uses the project Makefile, which wraps Docker Compose and Python tooling.

```bash
git clone https://github.com/ghantakiran/ShieldOps.git
cd ShieldOps

# Start PostgreSQL, Redis, Kafka, OPA
make dev

# Install all deps, run migrations, seed demo data
make setup

# Start the API + frontend
make run
```

---

## Option 2: Docker Compose (full stack)

Run the entire stack in containers without installing Python or Node locally.

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
```

This starts:

| Service    | Port | Notes |
|------------|------|-------|
| PostgreSQL | 5432 | User: `shieldops` / Pass: `shieldops` |
| Redis      | 6379 | No authentication |
| Kafka      | 9092 | KRaft mode (no ZooKeeper) |
| OPA        | 8181 | Policies from `playbooks/policies/` |

---

## Option 3: Manual setup

### 1. Start infrastructure services

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d postgres redis kafka opa
```

Wait for health checks to pass:

```bash
docker compose -f infrastructure/docker/docker-compose.yml ps
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```bash
SHIELDOPS_ENVIRONMENT=development
SHIELDOPS_DATABASE_URL=postgresql+asyncpg://shieldops:shieldops@localhost:5432/shieldops
SHIELDOPS_REDIS_URL=redis://localhost:6379/0
SHIELDOPS_KAFKA_BROKERS=localhost:9092
SHIELDOPS_OPA_ENDPOINT=http://localhost:8181
SHIELDOPS_JWT_SECRET_KEY=local-dev-secret-key
```

For agent functionality, add your LLM provider key:

```bash
SHIELDOPS_ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 4. Install frontend dependencies

```bash
cd dashboard-ui
npm install
cd ..
```

### 5. Run database migrations

```bash
alembic upgrade head
```

### 6. Seed demo data (optional)

```bash
python -m shieldops.db.seed
```

Creates a default admin user (`admin@shieldops.dev` / `shieldops-admin`), sample agents,
and historical investigation data.

### 7. Start the application

**API server** (port 8000):

```bash
uvicorn shieldops.api.app:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend dev server** (port 3000):

```bash
cd dashboard-ui
npm run dev
```

### 8. Verify

- API docs: http://localhost:8000/api/v1/docs
- Health check: http://localhost:8000/health
- Readiness check: http://localhost:8000/ready
- Dashboard: http://localhost:3000

---

## Environment variables reference

See the [Configuration](configuration.md) page for the complete list of all
`SHIELDOPS_*` environment variables with descriptions and defaults.
