# Performance Tests

## Load Testing with Locust

### Prerequisites
```bash
pip install "shieldops[dev]"
```

### Running locally (headless)
```bash
locust -f tests/performance/locustfile.py --headless -u 50 -r 10 -t 60s \
    --host http://localhost:8000
```

### Running with web UI
```bash
locust -f tests/performance/locustfile.py --host http://localhost:8000
# Open http://localhost:8089
```

### Environment variables
| Variable | Default | Description |
|----------|---------|-------------|
| `LOCUST_HOST` | `http://localhost:8000` | Target API host |
| `TEST_USER_EMAIL` | `admin@shieldops.dev` | Login email |
| `TEST_USER_PASSWORD` | `shieldops-admin` | Login password |

## Micro-benchmarks with pytest-benchmark

```bash
pytest tests/performance/test_benchmarks.py -v --benchmark-only
```

### What's benchmarked
- JWT token creation/verification
- Pydantic model serialization (InvestigationState)
- Metrics registry `collect()` with 1000 entries
- Policy evaluation latency (mocked)

## Target SLOs

| Metric | Target |
|--------|--------|
| p50 latency | < 100ms |
| p95 latency | < 500ms |
| p99 latency | < 1s |
| Error rate | < 0.1% |
| Health check p99 | < 50ms |
