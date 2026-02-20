# Development Setup

This page covers setting up a complete development environment for contributing
to ShieldOps.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12+ | [python.org](https://www.python.org/downloads/) |
| Docker | 24+ | [docker.com](https://docs.docker.com/get-docker/) |
| Node.js | 20+ | [nodejs.org](https://nodejs.org/) |
| Git | 2.40+ | [git-scm.com](https://git-scm.com/) |

---

## Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/ShieldOps.git
cd ShieldOps
git remote add upstream https://github.com/ghantakiran/ShieldOps.git
```

---

## Environment Setup

### 1. Start infrastructure

```bash
make dev
```

### 2. Install dependencies

```bash
make setup
```

This creates a virtual environment, installs Python and Node dependencies,
runs database migrations, and seeds demo data.

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and add your `SHIELDOPS_ANTHROPIC_API_KEY` if you want live agent
functionality. Without it, agents return simulated results.

### 4. Verify

```bash
make run
```

Visit http://localhost:3000 for the dashboard and http://localhost:8000/api/v1/docs
for the API.

---

## Development Workflow

### Create a feature branch

```bash
git checkout -b feat/your-feature
```

Branch naming conventions:

| Prefix | Purpose |
|--------|---------|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `chore/` | Maintenance tasks |
| `docs/` | Documentation changes |

### Make changes and test

```bash
# Run tests
make test

# Run linting
make lint

# Format code
make format

# Run all checks
make check
```

### Commit with conventional commits

```bash
git commit -m "feat: add support for PagerDuty escalation"
git commit -m "fix: handle null response from OPA during circuit break"
git commit -m "docs: add Helm chart configuration reference"
```

### Submit a PR

```bash
git push origin feat/your-feature
# Open a PR on GitHub targeting the main branch
```

PRs require:

- Passing CI (lint, typecheck, tests, security scan)
- At least one review approval

---

## Useful Commands

```bash
make help              # Show all available commands
make dev               # Start infrastructure
make setup             # Install deps + migrate + seed
make run               # Start API + frontend
make run-api           # Start API only
make run-frontend      # Start frontend only
make test              # Run full test suite
make test-unit         # Run unit tests only
make test-integration  # Run integration tests
make lint              # Ruff + mypy
make format            # Auto-format code
make db-shell          # Open psql shell
make redis-cli         # Open redis-cli
make clean             # Stop all and remove volumes
```

---

## IDE Configuration

### VS Code

Recommended extensions:

- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Ruff (charliermarsh.ruff)
- ESLint (dbaeumer.vscode-eslint)
- Tailwind CSS IntelliSense (bradlc.vscode-tailwindcss)

### PyCharm

- Set the project interpreter to `.venv/bin/python`
- Enable Ruff integration in Settings > Tools > Ruff
- Set pytest as the default test runner
