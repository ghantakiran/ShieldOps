# Local Development

This page covers setting up ShieldOps for local development.
For the fastest path, see the [Quick Start](../getting-started/quickstart.md).

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Docker | 24+ | Infrastructure containers |
| Python | 3.12+ | Backend runtime |
| Node.js | 20+ | Frontend build tooling |
| Git | 2.40+ | Version control |

---

## Infrastructure Services

The `docker-compose.yml` at `infrastructure/docker/docker-compose.yml` provisions:

| Service | Port | Details |
|---------|------|---------|
| PostgreSQL 16 | 5432 | User: `shieldops` / Pass: `shieldops` |
| Redis 7 | 6379 | No authentication |
| Kafka (KRaft) | 9092 | No ZooKeeper required |
| OPA | 8181 | Policies loaded from `playbooks/policies/` |

Start infrastructure:

```bash
make dev
# or manually:
docker compose -f infrastructure/docker/docker-compose.yml up -d postgres redis kafka opa
```

Verify health:

```bash
docker compose -f infrastructure/docker/docker-compose.yml ps
```

---

## Application Setup

```bash
# Create venv, install deps, run migrations, seed data
make setup

# Or step by step:
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cd dashboard-ui && npm install && cd ..
alembic upgrade head
python -m shieldops.db.seed
```

---

## Running the Application

```bash
# Both API + frontend
make run

# API only (port 8000)
make run-api

# Frontend only (port 3000)
make run-frontend
```

---

## Verification Endpoints

| URL | Description |
|-----|-------------|
| http://localhost:8000/health | Health check |
| http://localhost:8000/ready | Dependency readiness (DB, Redis, OPA) |
| http://localhost:8000/api/v1/docs | Swagger UI |
| http://localhost:8000/metrics | Prometheus metrics |
| http://localhost:3000 | Dashboard |

---

## Database Management

```bash
# Open psql shell
make db-shell

# Open redis-cli
make redis-cli

# Create a new migration
make migration MSG="add users table"

# Run migrations
make migrate
```

---

## Troubleshooting

### Database connection failures

The `SHIELDOPS_DATABASE_URL` must use the `postgresql+asyncpg://` scheme:

```bash
python -c "
import asyncio, asyncpg
asyncio.run(asyncpg.connect('postgresql://shieldops:shieldops@localhost:5432/shieldops'))
print('OK')
"
```

### OPA policy loading

Verify policies are loaded:

```bash
curl http://localhost:8181/v1/policies
```

### Kafka connectivity

If Kafka connectivity fails, ensure the advertised listener matches your host.
The docker-compose config uses `kafka:9092` internally. For host access, check
that `localhost:9092` is reachable.

---

## Clean Up

```bash
make clean
```

This stops all containers and removes volumes (data is lost).
