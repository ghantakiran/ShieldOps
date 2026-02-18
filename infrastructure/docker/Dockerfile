FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir .

# Copy source code and migrations
COPY src/ src/
COPY playbooks/ playbooks/
COPY alembic.ini ./
COPY alembic/ alembic/

# Create non-root user
RUN groupadd -r shieldops && useradd -r -g shieldops shieldops
USER shieldops

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn shieldops.api.app:app --host 0.0.0.0 --port 8000"]
