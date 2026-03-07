"""Basic investigation example.

Runs an investigation against a local Prometheus and Kubernetes cluster.
No AI features -- purely rule-based correlation.

Usage::

    export PROMETHEUS_URL=http://localhost:9090
    python examples/basic_investigation.py
"""

import asyncio
import os

from shieldops_investigate import Investigator


async def main() -> None:
    prometheus_url = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")

    investigator = Investigator(prometheus_url=prometheus_url)

    try:
        result = await investigator.investigate(
            alert_name="HighErrorRate",
            namespace="production",
            service="payment-service",
        )
    finally:
        await investigator.close()

    # --- Print results ---
    print(f"Investigation completed in {result.duration_seconds:.2f}s")
    print(f"Evidence collected: {len(result.evidence)}")
    print()

    for i, hypothesis in enumerate(result.hypotheses, 1):
        print(f"{i}. [{hypothesis.confidence:.0%}] {hypothesis.title}")
        print(f"   {hypothesis.description}")
        if hypothesis.suggested_action:
            print(f"   -> {hypothesis.suggested_action}")
        print()

    print("Summary:")
    print(result.summary)

    # --- Programmatic access ---
    top = result.top_hypothesis
    if top and top.confidence >= 0.8:
        print(f"\nHigh-confidence root cause found: {top.title}")
        print(f"Take action: {top.suggested_action}")


if __name__ == "__main__":
    asyncio.run(main())
