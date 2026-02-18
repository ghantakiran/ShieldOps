# ---------------------------------------------------------------------------
# Stage 1: Build — install Python dependencies in an isolated layer
# ---------------------------------------------------------------------------
FROM python:3.12-slim@sha256:aeb78c04060c3eff1ab37ab1e8be788ccd01abedc5b77f4b8a0e8d3a4cc8c3ec AS builder

WORKDIR /build

# Copy project metadata and source needed for hatchling build
COPY pyproject.toml ./
COPY src/ src/

# Install project + dependencies into a prefix we can copy later
RUN pip install --no-cache-dir --prefix=/install .

# ---------------------------------------------------------------------------
# Stage 2: Runtime — minimal image with only what's needed to run
# ---------------------------------------------------------------------------
FROM python:3.12-slim@sha256:aeb78c04060c3eff1ab37ab1e8be788ccd01abedc5b77f4b8a0e8d3a4cc8c3ec

WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user before copying files
RUN groupadd -r shieldops && useradd -r -g shieldops shieldops

# Copy installed Python packages (project + deps) from builder
COPY --from=builder /install /usr/local

# Copy runtime assets with proper ownership
COPY --chown=shieldops:shieldops playbooks/ playbooks/
COPY --chown=shieldops:shieldops alembic.ini ./
COPY --chown=shieldops:shieldops alembic/ alembic/

USER shieldops

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn shieldops.api.app:app --host 0.0.0.0 --port 8000"]
