#!/usr/bin/env python3
"""CLI Runner - V3 Market Analyzer.

Analyzes US stock market conditions across three time windows:
  - pre_market : Overnight gaps, futures, VIX setup (9:00 AM EST)
  - intraday   : Live momentum, sector rotation, breadth (market hours)
  - eod        : End-of-day summary, regime classification (4:15 PM EST)
  - full       : Run all three analyses

Usage:
    # Auto-detect time window
    python run_market_analyzer.py

    # Force a specific analysis mode
    python run_market_analyzer.py --mode pre_market
    python run_market_analyzer.py --mode intraday
    python run_market_analyzer.py --mode eod
    python run_market_analyzer.py --mode full

    # Output as JSON
    python run_market_analyzer.py --json

    # Telegram-formatted output
    python run_market_analyzer.py --telegram
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Ensure engine package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from engine.market_analyzer import MarketAnalyzer
from engine.regime import RegimeClassifier


EST = ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------
# Time-based mode detection
# ---------------------------------------------------------------------------

def detect_mode() -> str:
    """Detect the appropriate analysis mode based on current EST time."""
    now_est = datetime.now(EST)
    hour = now_est.hour
    minute = now_est.minute

    if hour < 9 or (hour == 9 and minute < 30):
        return "pre_market"
    elif hour < 16:
        return "intraday"
    else:
        return "eod"


def mode_description(mode: str) -> str:
    """Human-readable description of each mode."""
    descriptions = {
        "pre_market": "Pre-Market Scan (overnight gaps, VIX, futures)",
        "intraday": "Intraday Check (momentum, sector rotation, breadth)",
        "eod": "End-of-Day Summary (daily performance, regime update)",
        "full": "Full Analysis (all three modes combined)",
    }
    return descriptions.get(mode, mode)


# ---------------------------------------------------------------------------
# JSON serialization helper
# ---------------------------------------------------------------------------

def make_json_safe(obj):
    """Recursively convert numpy types and other non-JSON types."""
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_safe(v) for v in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return obj


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def print_analysis_text(analysis: dict, mode: str) -> None:
    """Pretty-print analysis results to the terminal."""
    if mode == "full":
        for sub_mode in ["pre_market", "intraday", "eod"]:
            if sub_mode in analysis:
                print(f"\n{'=' * 60}")
                print(f"  {mode_description(sub_mode).upper()}")
                print(f"{'=' * 60}")
                _print_section(analysis[sub_mode], sub_mode)
    else:
        _print_section(analysis, mode)


def _print_section(data: dict, mode: str) -> None:
    """Print a single analysis section."""
    # Regime info
    regime = data.get("regime", data.get("vix_regime", {}))
    if isinstance(regime, dict):
        r = regime.get("regime", "UNKNOWN")
        v = regime.get("vix", "N/A")
        print(f"\n  VIX: {v}  |  Regime: {r}")
    elif isinstance(regime, str):
        print(f"\n  Regime: {regime}")

    # Index performance
    indices = data.get("indices", data.get("index_changes", {}))
    if indices:
        print(f"\n  {'Index':<8} {'Change':>8} {'Close':>10}")
        print(f"  {'-'*30}")
        for idx, info in indices.items():
            if isinstance(info, dict):
                chg = info.get("change_pct", info.get("pct_change", 0))
                close = info.get("close", info.get("last", 0))
                pct_str = f"{chg:+.2f}%" if isinstance(chg, (int, float)) else str(chg)
                close_str = f"${close:,.2f}" if isinstance(close, (int, float)) else str(close)
                print(f"  {idx:<8} {pct_str:>8} {close_str:>10}")
            else:
                print(f"  {idx}: {info}")

    # Sector performance
    sectors = data.get("sectors", data.get("sector_performance", {}))
    if sectors:
        print(f"\n  {'Sector':<25} {'Change':>8}")
        print(f"  {'-'*35}")
        # Sort by performance
        sorted_sectors = sorted(
            sectors.items(),
            key=lambda x: x[1].get("change_pct", 0) if isinstance(x[1], dict) else x[1],
            reverse=True,
        )
        for name, info in sorted_sectors:
            if isinstance(info, dict):
                chg = info.get("change_pct", 0)
                print(f"  {name:<25} {chg:+.2f}%")
            else:
                print(f"  {name:<25} {info}")

    # Momentum / Breadth
    momentum = data.get("momentum_score", data.get("intraday_momentum"))
    if momentum is not None:
        print(f"\n  Momentum Score: {momentum} / 5")

    breadth = data.get("breadth", data.get("market_breadth", {}))
    if breadth:
        adv = breadth.get("advancing", breadth.get("advancers", 0))
        dec = breadth.get("declining", breadth.get("decliners", 0))
        print(f"  Breadth: {adv} advancing / {dec} declining")

    # Signals / Alerts
    signals = data.get("signals", data.get("alerts", []))
    if signals:
        print(f"\n  Signals:")
        for sig in signals:
            if isinstance(sig, dict):
                print(f"    - {sig.get('message', sig)}")
            else:
                print(f"    - {sig}")


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="V3 Value Engine - Market Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_market_analyzer.py                  # Auto-detect mode based on EST time
  python run_market_analyzer.py --mode pre_market # Force pre-market analysis
  python run_market_analyzer.py --mode intraday   # Intraday momentum check
  python run_market_analyzer.py --mode eod        # End-of-day summary
  python run_market_analyzer.py --mode full        # All three analyses
  python run_market_analyzer.py --json            # Output as JSON
  python run_market_analyzer.py --telegram        # Telegram-formatted output
  python run_market_analyzer.py --output report/  # Save to directory
""",
    )

    parser.add_argument(
        "--mode",
        type=str,
        default=None,
        choices=["pre_market", "intraday", "eod", "full"],
        help="Analysis mode. Default: auto-detect based on current EST time.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw analysis as JSON to stdout.",
    )
    parser.add_argument(
        "--telegram",
        action="store_true",
        help="Output Telegram-formatted report.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Directory to save analysis JSON and report.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal console output.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    start_time = time.time()
    now_est = datetime.now(EST)

    # Auto-detect mode
    mode = args.mode or detect_mode()

    if not args.quiet and not args.json:
        print("=" * 60)
        print("V3 VALUE ENGINE - MARKET ANALYZER")
        print(f"Time: {now_est.strftime('%Y-%m-%d %H:%M %Z')}")
        print(f"Mode: {mode_description(mode)}")
        print("=" * 60)

    # ---------------------------------------------------------------
    # Run analysis
    # ---------------------------------------------------------------
    analyzer = MarketAnalyzer()

    if not args.quiet and not args.json:
        print("\nFetching market data...")

    try:
        if mode == "pre_market":
            analysis = analyzer.pre_market_scan()
        elif mode == "intraday":
            analysis = analyzer.intraday_check()
        elif mode == "eod":
            analysis = analyzer.eod_summary()
        elif mode == "full":
            analysis = analyzer.full_analysis()
        else:
            print(f"Error: Unknown mode '{mode}'")
            sys.exit(1)
    except Exception as e:
        print(f"\nError running analysis: {e}")
        print("This may be due to market being closed or data unavailability.")
        sys.exit(1)

    # ---------------------------------------------------------------
    # Output
    # ---------------------------------------------------------------
    elapsed = time.time() - start_time

    if args.json:
        safe_output = make_json_safe(analysis)
        safe_output["_meta"] = {
            "mode": mode,
            "timestamp": now_est.isoformat(),
            "elapsed_seconds": round(elapsed, 2),
        }
        print(json.dumps(safe_output, indent=2, default=str))

    elif args.telegram:
        if mode == "full":
            for sub_mode in ["pre_market", "intraday", "eod"]:
                if sub_mode in analysis:
                    report = analyzer.format_telegram_report(analysis[sub_mode], sub_mode)
                    print(report)
                    print()
        else:
            report = analyzer.format_telegram_report(analysis, mode)
            print(report)

    else:
        print_analysis_text(analysis, mode)
        if not args.quiet:
            print(f"\nCompleted in {elapsed:.1f}s")

    # ---------------------------------------------------------------
    # Save to file (optional)
    # ---------------------------------------------------------------
    if args.output:
        os.makedirs(args.output, exist_ok=True)
        timestamp = now_est.strftime("%Y%m%d_%H%M")

        # Save JSON
        json_path = os.path.join(args.output, f"analysis_{mode}_{timestamp}.json")
        safe_output = make_json_safe(analysis)
        with open(json_path, "w") as f:
            json.dump(safe_output, f, indent=2, default=str)
        if not args.quiet:
            print(f"Saved: {json_path}")

        # Save Telegram report
        if mode == "full":
            for sub_mode in ["pre_market", "intraday", "eod"]:
                if sub_mode in analysis:
                    report = analyzer.format_telegram_report(analysis[sub_mode], sub_mode)
                    report_path = os.path.join(args.output, f"report_{sub_mode}_{timestamp}.txt")
                    with open(report_path, "w") as f:
                        f.write(report)
                    if not args.quiet:
                        print(f"Saved: {report_path}")
        else:
            report = analyzer.format_telegram_report(analysis, mode)
            report_path = os.path.join(args.output, f"report_{mode}_{timestamp}.txt")
            with open(report_path, "w") as f:
                f.write(report)
            if not args.quiet:
                print(f"Saved: {report_path}")


if __name__ == "__main__":
    main()
