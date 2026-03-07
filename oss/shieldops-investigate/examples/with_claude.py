"""Investigation with Claude-powered root cause analysis.

When an Anthropic API key is provided, the investigator uses Claude to
generate a nuanced, context-aware root cause summary instead of the
default rule-based approach.

Usage::

    export PROMETHEUS_URL=http://localhost:9090
    export ANTHROPIC_API_KEY=sk-ant-...
    python examples/with_claude.py
"""

import asyncio
import os
import sys

from shieldops_investigate import Investigator


async def main() -> None:
    prometheus_url = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if not anthropic_key:
        print("Set ANTHROPIC_API_KEY to enable AI-powered root cause analysis.")
        print("Falling back to rule-based mode.\n")

    investigator = Investigator(
        prometheus_url=prometheus_url,
        anthropic_api_key=anthropic_key,
    )

    # You can investigate any alert -- the toolkit adapts its queries
    # based on the namespace and service you provide.
    alerts_to_investigate = [
        ("HighErrorRate", "production", "checkout-service"),
        ("PodCrashLooping", "staging", None),
        ("HighLatency", "production", "api-gateway"),
    ]

    try:
        for alert_name, namespace, service in alerts_to_investigate:
            print(f"{'=' * 60}")
            print(f"Investigating: {alert_name}")
            print(f"  Namespace: {namespace}")
            print(f"  Service:   {service or 'all'}")
            print(f"{'=' * 60}\n")

            result = await investigator.investigate(
                alert_name=alert_name,
                namespace=namespace,
                service=service,
            )

            if result.hypotheses:
                top = result.hypotheses[0]
                print(f"Top hypothesis: {top.title} ({top.confidence:.0%} confidence)")
                print(f"Evidence: {len(top.evidence)} signals")
            else:
                print("No hypotheses generated.")

            print(f"\nSummary:\n{result.summary}\n")
            print(f"Duration: {result.duration_seconds:.2f}s\n")
    finally:
        await investigator.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
