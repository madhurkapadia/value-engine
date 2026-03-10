"""V3 Value Engine - Configuration Constants.

All tunable parameters for the value investing engine in one place.
Override via environment variables or by importing and patching.
"""

import os

# ---------------------------------------------------------------------------
# VIX Regime Thresholds
# ---------------------------------------------------------------------------
VIX_GREEN = 18       # VIX < 18  -> GREEN (risk-on)
VIX_YELLOW = 25      # 18 <= VIX < 25 -> YELLOW (caution)
# VIX >= 25 -> RED (risk-off)

# ---------------------------------------------------------------------------
# Portfolio Defaults (Madhur's real positions as of 2026-03-09)
# ---------------------------------------------------------------------------
INITIAL_CASH = 0.0
INITIAL_HOLDINGS = {
    # Mega-cap core (~72%)
    "TSLA":  10.74,
    "AAPL":  13.42,
    "GOOGL": 11.69,
    "AMZN":  14.61,
    "MSFT":  5.60,
    "TSM":   6.78,
    "ADBE":  5.57,
    "V":     3.76,
    "UNH":   3.84,
    "META":  1.23,
    # Growth / Mid-cap (~5%)
    "NFLX":  5.75,
    "BABA":  2.11,
    "ISMD":  11.08,
    # Speculative / Small-cap (~5%)
    "PAYO":  85.0,
    "KULR":  105.0,
    "NVCT":  14.81,
    "COCH":  150.0,
    "RIVN":  5.0,
    "QQQM":  0.80,    # Invesco Nasdaq 100 ETF
    "RVPH":  15.0,
}

# Average cost basis per share (for P&L tracking)
AVG_COST_BASIS = {
    "TSLA":  277.53,
    "AAPL":  191.15,
    "GOOGL": 161.79,
    "AMZN":  194.89,
    "MSFT":  416.51,
    "TSM":   159.51,
    "ADBE":  324.10,
    "V":     307.21,
    "UNH":   269.99,
    "META":  527.41,
    "NFLX":  84.64,
    "BABA":  98.66,
    "ISMD":  51.85,
    "PAYO":  6.39,
    "KULR":  4.23,
    "NVCT":  6.75,
    "COCH":  0.87,
    "RIVN":  10.57,
    "QQQM":  62.30,
    "RVPH":  12.57,
}
RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# Trading Rules - Active Strategy (V1/V2/V3)
# ---------------------------------------------------------------------------
TRIM_GAIN_THRESHOLD = 0.30
TRIM_SELL_FRACTION = 0.50
CUT_LOSS_THRESHOLD = -0.25
REDEPLOY_RSI_THRESHOLD = 35

# ---------------------------------------------------------------------------
# V3 Guarded Value - Scanner Guardrails
# ---------------------------------------------------------------------------
MAX_FORWARD_PE = 30.0
MIN_FCF_YIELD = -0.05
MIN_MOM_3M = 0.0
MAX_RSI_ENTRY = 50
MAX_VALUE_PICKS_PER_MONTH = 3

# ---------------------------------------------------------------------------
# V3 Guarded Value - Trailing Stop
# ---------------------------------------------------------------------------
TRAILING_STOP_PCT = 0.10
TRAILING_STOP_DAYS = 5

# ---------------------------------------------------------------------------
# V3 Position Sizing
# ---------------------------------------------------------------------------
VALUE_POSITION_SIZE_PCT = 0.03

# ---------------------------------------------------------------------------
# Quarterly Rescore Noise (for backtest simulation)
# ---------------------------------------------------------------------------
QUARTERLY_RESCORE_NOISE = 0.05

# ---------------------------------------------------------------------------
# Stock Universes
# ---------------------------------------------------------------------------
UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "AMD", "AVGO", "INTC", "QCOM", "ON",
    "ORCL", "CRM", "ADBE", "NFLX",
    "JPM", "BAC", "GS", "V", "MA",
    "JNJ", "UNH", "PFE", "BMY", "LLY",
    "GE", "CAT", "LMT", "BA", "RTX",
    "NKE", "PEP", "KO", "WMT", "COST",
    "XOM", "CVX", "COP",
    "NEM", "FCX",
    "RIVN", "KULR", "PAYO", "RVPH",
    "TSM", "BABA", "ISMD", "NVCT", "COCH", "QQQM",
]

QUALITY_REDEPLOY_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NFLX",
    "JNJ", "UNH", "PEP", "KO", "WMT",
    "JPM", "V", "MA",
    "PAYO", "KULR",
]

SP100_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
    "JPM", "V", "UNH", "JNJ", "XOM", "PG", "MA", "HD", "CVX", "ABBV",
    "MRK", "LLY", "KO", "PEP", "COST", "AVGO", "BAC", "WMT", "MCD",
    "CSCO", "TMO", "ABT", "CRM", "ACN", "ADBE", "AMD", "ORCL", "NFLX",
    "NKE", "INTC", "IBM", "GE", "CAT", "BA", "RTX", "GS", "LOW",
    "QCOM", "TXN", "SBUX", "GIS", "COP", "FCX", "NEM", "LMT",
    "BMY", "PFE", "GILD", "MDT", "SYK", "ISRG", "AMGN",
    "CME", "BLK", "SPGI", "ICE", "AXP", "MMM", "HON", "DE",
    "UPS", "FDX", "DIS", "CMCSA", "TMUS", "VZ", "T",
    "NEE", "DUK", "SO", "D", "AEP",
    "PLD", "AMT", "SPG", "CCI", "EQIX",
]

SECTOR_ETFS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLV": "Healthcare",
    "XLE": "Energy",
    "XLI": "Industrials",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLC": "Communication Services",
}

OUTPUT_DIR = os.environ.get("VALUE_ENGINE_OUTPUT", "output")
DATA_DIR = os.path.join(OUTPUT_DIR, "data")
CHART_DIR = os.path.join(OUTPUT_DIR, "charts")
