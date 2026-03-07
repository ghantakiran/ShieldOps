"""Command-line interface for ShieldOps Investigate.

Usage::

    shieldops-investigate --alert HighErrorRate --namespace production --service payment-service
    shieldops-investigate --alert PodCrashLooping --namespace staging --json
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from shieldops_investigate.investigator import Investigator
from shieldops_investigate.models import Confidence, InvestigationResult

# ---------------------------------------------------------------------------
# ANSI colour helpers (disabled when output is not a TTY)
# ---------------------------------------------------------------------------

_NO_COLOR = os.environ.get("NO_COLOR") is not None or not sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    if _NO_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def _bold(text: str) -> str:
    return _c("1", text)


def _green(text: str) -> str:
    return _c("32", text)


def _yellow(text: str) -> str:
    return _c("33", text)


def _red(text: str) -> str:
    return _c("31", text)


def _dim(text: str) -> str:
    return _c("2", text)


def _cyan(text: str) -> str:
    return _c("36", text)


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------

_CONFIDENCE_COLORS = {
    Confidence.HIGH: _red,
    Confidence.MEDIUM: _yellow,
    Confidence.LOW: _dim,
}


def _print_result(result: InvestigationResult) -> None:
    """Pretty-print an investigation result to stdout."""
    print()
    print(_bold("=" * 72))
    print(_bold(f"  ShieldOps Investigate  --  {result.alert_name}"))
    print(_bold("=" * 72))
    print()
    print(f"  Namespace:  {_cyan(result.namespace)}")
    if result.service:
        print(f"  Service:    {_cyan(result.service)}")
    print(f"  Duration:   {result.duration_seconds:.2f}s")
    print(f"  Evidence:   {len(result.evidence)} signals collected")
    print()

    if not result.hypotheses:
        print(_yellow("  No hypotheses generated. Manual investigation recommended."))
        print()
        return

    print(_bold("  HYPOTHESES (ranked by confidence)"))
    print(_bold("  " + "-" * 48))
    print()

    for i, h in enumerate(result.hypotheses, 1):
        color_fn = _CONFIDENCE_COLORS.get(h.confidence_level, _dim)
        conf_label = f"{h.confidence:.0%} {h.confidence_level.value}"

        print(f"  {_bold(f'{i}.')} {_bold(h.title)}  [{color_fn(conf_label)}]")
        print(f"     {h.description}")
        if h.suggested_action:
            print(f"     {_green('Action:')} {h.suggested_action}")
        if h.evidence:
            print(f"     {_dim(f'Evidence: {len(h.evidence)} signal(s)')}")
            for ev in h.evidence[:3]:
                print(f"       {_dim('-')} [{ev.source.value}] {ev.value}")
        print()

    print(_bold("  SUMMARY"))
    print(_bold("  " + "-" * 48))
    # Wrap summary text
    words = result.summary.split()
    line = "  "
    for word in words:
        if len(line) + len(word) + 1 > 74:
            print(line)
            line = "  " + word
        else:
            line += " " + word if line.strip() else "  " + word
    if line.strip():
        print(line)
    print()
    print(_dim("  Powered by ShieldOps  |  https://shieldops.dev"))
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shieldops-investigate",
        description="AI-powered root cause analysis for Kubernetes incidents.",
    )
    parser.add_argument(
        "--alert",
        "-a",
        required=True,
        help="Name of the alert to investigate (e.g. HighErrorRate).",
    )
    parser.add_argument(
        "--namespace",
        "-n",
        required=True,
        help="Kubernetes namespace to investigate.",
    )
    parser.add_argument(
        "--service",
        "-s",
        default=None,
        help="Optional service name to narrow the investigation scope.",
    )
    parser.add_argument(
        "--prometheus-url",
        "-p",
        default=os.environ.get("PROMETHEUS_URL", "http://localhost:9090"),
        help="Prometheus server URL (default: $PROMETHEUS_URL or http://localhost:9090).",
    )
    parser.add_argument(
        "--kubeconfig",
        default=os.environ.get("KUBECONFIG"),
        help="Path to kubeconfig file (default: $KUBECONFIG or in-cluster).",
    )
    parser.add_argument(
        "--anthropic-api-key",
        default=os.environ.get("ANTHROPIC_API_KEY"),
        help="Anthropic API key for AI-powered summaries (default: $ANTHROPIC_API_KEY).",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output results as JSON instead of pretty-printed text.",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    investigator = Investigator(
        prometheus_url=args.prometheus_url,
        kubeconfig_path=args.kubeconfig,
        anthropic_api_key=args.anthropic_api_key,
    )

    try:
        result = await investigator.investigate(
            alert_name=args.alert,
            namespace=args.namespace,
            service=args.service,
        )
    finally:
        await investigator.close()

    if args.json_output:
        print(result.model_dump_json(indent=2))
    else:
        _print_result(result)


def main() -> None:
    """CLI entry point for ``shieldops-investigate``."""
    parser = _build_parser()
    args = parser.parse_args()

    try:
        asyncio.run(_run(args))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
    except Exception as exc:
        print(f"\n{_red('Error:')} {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
