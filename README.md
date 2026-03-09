# V3 Value Engine

Automated value investing engine with VIX regime detection, 5-guardrail stock scanning, and 4-strategy backtesting.

## Architecture

```
value-engine/
|-- engine/                    # Core library
|   |-- __init__.py            # Package init with lazy imports
|   |-- config.py              # All tunable parameters
|   |-- utils.py               # RSI, Sharpe, Sortino, drawdown helpers
|   |-- regime.py              # VIX-based regime classifier (GREEN/YELLOW/RED)
|   |-- scanner.py             # Value stock scanner with guardrails
|   |-- backtest.py            # Multi-strategy backtest engine
|   |-- market_analyzer.py     # Hourly US market analyzer
|
|-- run_backtest.py            # CLI: Run full backtest
|-- run_scanner.py             # CLI: Scan for value picks
|-- run_market_analyzer.py     # CLI: Market analysis reports
|
|-- data/                      # Sample/cached data files
|   |-- sample_fundamentals.csv
|
|-- output/                    # Generated output (gitignored)
|   |-- data/                  # CSV exports
|   |-- charts/                # PNG charts
|
|-- requirements.txt
|-- README.md
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run a full backtest (fetches live data from yfinance)
python run_backtest.py

# Scan for value stocks right now
python run_scanner.py

# Get market analysis
python run_market_analyzer.py
```

## VIX Regime System

The engine classifies market conditions using the CBOE VIX index:

| Regime | VIX Range | Behavior |
|--------|-----------|----------|
| GREEN  | < 18      | Risk-on: buy value picks, full allocation |
| YELLOW | 18 - 25   | Caution: trim winners, no new picks |
| RED    | >= 25     | Risk-off: cut losers, raise cash, no new entries |

## Four Strategies Compared

### 1. Buy & Hold (Baseline)
Hold initial portfolio unchanged for the entire period.

### 2. V1 Active
Monthly rebalancing with:
- Trim winners above +30% gain (sell 50%)
- Cut losers below -25% loss
- Redeploy cash into quality stocks with low RSI

### 3. V2 Value+Active
V1 rules plus naive value picking:
- Monthly scans for cheap stocks (low PE)
- No sector diversification guardrails
- Simple momentum filter

### 4. V3 Guarded Value (Best)
Full engine with 5 guardrails:
- **Forward PE < 30**: No overvalued entries
- **FCF Yield > -5%**: Cash flow positive (allows growth)
- **3-month Momentum > 0%**: Only stocks in uptrend
- **RSI < 50**: Entry only when not overbought
- **Sector Cap**: Max 2 picks per sector (diversification)

Plus:
- Regime-aware buying (GREEN only)
- 10% trailing stops on value picks
- Quarterly fundamental rescore
- Quality redeployment into blue chips

## CLI Usage

### run_backtest.py

```bash
# Default: live data, all strategies
python run_backtest.py

# From local CSVs
python run_backtest.py --prices data/prices.csv --fundamentals data/fundamentals.csv

# Custom portfolio
python run_backtest.py --cash 10000 --holdings '{"AAPL": 10, "MSFT": 5}'

# Run only V3 vs Buy & Hold
python run_backtest.py --strategies v3 buyhold

# 2-year backtest
python run_backtest.py --period 2y

# JSON metrics output
python run_backtest.py --json
```

### run_scanner.py

```bash
# Full universe scan
python run_scanner.py

# Force GREEN regime
python run_scanner.py --regime GREEN

# Top 5 picks
python run_scanner.py --top 5

# Custom tickers
python run_scanner.py --tickers AAPL MSFT GOOGL AMZN NVDA META

# Exclude sectors you already hold
python run_scanner.py --exclude-sectors Technology "Financial Services"

# Save to CSV
python run_scanner.py --output picks.csv

# JSON output
python run_scanner.py --json
```

### run_market_analyzer.py

```bash
# Auto-detect mode based on EST time
python run_market_analyzer.py

# Force specific mode
python run_market_analyzer.py --mode pre_market
python run_market_analyzer.py --mode intraday
python run_market_analyzer.py --mode eod
python run_market_analyzer.py --mode full

# Telegram-formatted output
python run_market_analyzer.py --telegram

# Save analysis to files
python run_market_analyzer.py --output reports/

# JSON output
python run_market_analyzer.py --json
```

## Configuration

All tunable parameters are in `engine/config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `VIX_GREEN` | 18 | VIX threshold for GREEN regime |
| `VIX_YELLOW` | 25 | VIX threshold for YELLOW regime |
| `INITIAL_CASH` | $5,000 | Starting cash balance |
| `TRIM_GAIN_THRESHOLD` | 30% | Trim winners above this gain |
| `CUT_LOSS_THRESHOLD` | -25% | Cut losers below this loss |
| `TRAILING_STOP_PCT` | 10% | Trailing stop on value picks |
| `MAX_FORWARD_PE` | 30 | Guardrail: max forward PE |
| `MIN_FCF_YIELD` | -5% | Guardrail: min FCF yield |
| `MAX_RSI_ENTRY` | 50 | Guardrail: max RSI for entry |
| `VALUE_POSITION_SIZE_PCT` | 3% | Position size per value pick |

## V3 Backtest Results (Mar 2025 - Mar 2026)

| Metric | Buy & Hold | V1 Active | V2 Value | **V3 Guarded** |
|--------|-----------|-----------|----------|----------------|
| Return | +11.81% | +14.55% | +14.61% | **+21.53%** |
| Max DD | -17.43% | -17.29% | -17.29% | **-12.95%** |
| Sharpe | 0.554 | 0.662 | 0.665 | **1.054** |
| Sortino | 0.790 | 0.949 | 0.950 | **1.485** |
| Trades | - | 40 | 42 | 37 |

## Stock Universe

44 tickers spanning:
- **Mega-cap tech**: AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA
- **Semiconductors**: AMD, AVGO, INTC, QCOM, ON
- **Software/Cloud**: ORCL, CRM, ADBE, NFLX
- **Financials**: JPM, BAC, GS, V, MA
- **Healthcare**: JNJ, UNH, PFE, BMY, LLY
- **Industrials**: GE, CAT, LMT, BA, RTX
- **Consumer**: NKE, PEP, KO, WMT, COST
- **Energy**: XOM, CVX, COP
- **Materials**: NEM, FCX
- **Growth/Speculative**: RIVN, KULR, PAYO, RVPH

## Python API

```python
from engine.regime import RegimeClassifier
from engine.scanner import ValueScanner
from engine.backtest import BacktestEngine
from engine.market_analyzer import MarketAnalyzer

# Check current regime
regime = RegimeClassifier.get_current_regime()
print(regime)  # {'regime': 'GREEN', 'vix': 15.2, 'description': '...'}

# Scan for value picks
scanner = ValueScanner()
picks = scanner.scan(regime='GREEN', top_n=5)

# Run backtest
engine = BacktestEngine(prices_df, fundamentals_df, vix_series)
results = engine.run_all()
print(engine.format_metrics_table(results['metrics']))

# Market analysis
analyzer = MarketAnalyzer()
report = analyzer.eod_summary()
print(analyzer.format_telegram_report(report, 'eod'))
```

## License

Private / Personal Use - Madhur Kapadia
