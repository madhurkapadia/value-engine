"""V3 Value Engine - Hourly US Market Analyzer.

Provides three analysis modes aligned with the trading day:
- Pre-market (9:00 AM EST): Overnight assessment, regime check, action recommendation
- Intraday (9:30 AM - 4:00 PM EST): Hourly momentum, sector rotation, breadth
- EOD (4:15 PM EST): Daily summary, regime alerts, next-day outlook

Each mode returns a structured dictionary that can be formatted for
Telegram, CLI, or JSON output.
"""

from datetime import datetime, time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from engine import config
from engine.regime import RegimeClassifier
from engine.utils import compute_rsi, compute_momentum


class MarketAnalyzer:
    """Analyzes US stock market conditions at different times of day.

    Uses yfinance for real-time data on SPY, QQQ, IWM, VIX, and sector ETFs.

    Attributes:
        indices: List of index tickers to track.
        sector_etfs: Dict mapping ETF ticker to sector name.
    """

    def __init__(self) -> None:
        """Initialize the market analyzer."""
        self.indices = ['SPY', 'QQQ', 'IWM', '^VIX']
        self.sector_etfs = config.SECTOR_ETFS

    # ------------------------------------------------------------------
    # Data fetching helpers
    # ------------------------------------------------------------------

    def _fetch_index_data(self, period: str = '5d', interval: str = '1d') -> Dict[str, pd.DataFrame]:
        """Fetch price data for major indices.

        Args:
            period: yfinance period string.
            interval: yfinance interval string.

        Returns:
            Dict mapping ticker to DataFrame of OHLCV data.
        """
        data = {}
        for ticker in self.indices:
            try:
                df = yf.download(ticker, period=period, interval=interval, progress=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                if not df.empty:
                    data[ticker] = df
            except Exception as e:
                print(f"Warning: Could not fetch {ticker}: {e}")
        return data

    def _fetch_sector_data(self, period: str = '5d', interval: str = '1d') -> Dict[str, pd.DataFrame]:
        """Fetch price data for sector ETFs.

        Args:
            period: yfinance period string.
            interval: yfinance interval string.

        Returns:
            Dict mapping ETF ticker to DataFrame.
        """
        data = {}
        tickers = list(self.sector_etfs.keys())
        try:
            raw = yf.download(tickers, period=period, interval=interval, progress=False)
            if isinstance(raw.columns, pd.MultiIndex):
                for ticker in tickers:
                    try:
                        df = raw.xs(ticker, level=1, axis=1)
                        if not df.empty:
                            data[ticker] = df
                    except (KeyError, TypeError):
                        pass
            else:
                # Single ticker case
                if not raw.empty:
                    data[tickers[0]] = raw
        except Exception as e:
            print(f"Warning: Could not fetch sector data: {e}")
        return data

    def _compute_daily_change(self, df: pd.DataFrame) -> Dict[str, float]:
        """Compute daily price change metrics from OHLCV data.

        Args:
            df: DataFrame with at least 'Open', 'Close', 'High', 'Low' columns.

        Returns:
            Dict with 'close', 'change_pct', 'high', 'low', 'range_pct'.
        """
        if df.empty or len(df) < 1:
            return {'close': 0, 'change_pct': 0, 'high': 0, 'low': 0, 'range_pct': 0}

        latest = df.iloc[-1]
        close = float(latest.get('Close', 0))

        if len(df) >= 2:
            prev_close = float(df.iloc[-2].get('Close', close))
            change_pct = ((close - prev_close) / prev_close * 100) if prev_close != 0 else 0
        else:
            open_price = float(latest.get('Open', close))
            change_pct = ((close - open_price) / open_price * 100) if open_price != 0 else 0

        high = float(latest.get('High', close))
        low = float(latest.get('Low', close))
        range_pct = ((high - low) / low * 100) if low != 0 else 0

        return {
            'close': round(close, 2),
            'change_pct': round(change_pct, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'range_pct': round(range_pct, 2),
        }

    def _compute_intraday_momentum(self, index_data: Dict[str, pd.DataFrame]) -> int:
        """Compute intraday momentum score on a -5 to +5 scale.

        Factors: SPY change, QQQ change, VIX direction, breadth.

        Args:
            index_data: Dict of index DataFrames.

        Returns:
            Integer score from -5 to +5.
        """
        score = 0

        # SPY direction
        if 'SPY' in index_data:
            spy_change = self._compute_daily_change(index_data['SPY'])
            if spy_change['change_pct'] > 0.5:
                score += 2
            elif spy_change['change_pct'] > 0:
                score += 1
            elif spy_change['change_pct'] < -0.5:
                score -= 2
            elif spy_change['change_pct'] < 0:
                score -= 1

        # QQQ direction (tech leadership)
        if 'QQQ' in index_data:
            qqq_change = self._compute_daily_change(index_data['QQQ'])
            if qqq_change['change_pct'] > 0.5:
                score += 1
            elif qqq_change['change_pct'] < -0.5:
                score -= 1

        # VIX direction (fear gauge - inverse)
        if '^VIX' in index_data:
            vix_change = self._compute_daily_change(index_data['^VIX'])
            if vix_change['change_pct'] < -3:
                score += 1
            elif vix_change['change_pct'] > 3:
                score -= 1

        # IWM (small caps - risk appetite)
        if 'IWM' in index_data:
            iwm_change = self._compute_daily_change(index_data['IWM'])
            if iwm_change['change_pct'] > 0.5:
                score += 1
            elif iwm_change['change_pct'] < -0.5:
                score -= 1

        return max(-5, min(5, score))

    def _fetch_portfolio_snapshot(self) -> Dict[str, Any]:
        """Fetch live prices for portfolio holdings and compute P&L.

        Returns:
            Dict with portfolio_value, daily_change_pct, cost_basis_total,
            total_unrealized_pnl, unrealized_pnl_pct, positions list, 
            top_gainers, top_losers.
        """
        holdings = config.INITIAL_HOLDINGS
        cost_basis = getattr(config, 'AVG_COST_BASIS', {})
        tickers = list(holdings.keys())
        
        if not tickers:
            return {}
        
        try:
            raw = yf.download(tickers, period='2d', interval='1d', progress=False)
        except Exception as e:
            print(f"Warning: Could not fetch portfolio data: {e}")
            return {}
        
        positions = []
        total_value = 0.0
        total_cost = 0.0
        total_daily_change = 0.0
        
        for ticker in tickers:
            shares = holdings[ticker]
            avg_cost = cost_basis.get(ticker, 0)
            
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    df = raw.xs(ticker, level=1, axis=1)
                else:
                    df = raw  # single ticker
                
                if df.empty or len(df) < 1:
                    continue
                
                current_price = float(df['Close'].iloc[-1])
                if len(df) >= 2:
                    prev_close = float(df['Close'].iloc[-2])
                    daily_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0
                else:
                    daily_pct = 0.0
                
                position_value = shares * current_price
                position_cost = shares * avg_cost if avg_cost else 0
                unrealized = position_value - position_cost if avg_cost else 0
                unrealized_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost else 0
                daily_dollar = shares * (current_price - prev_close) if len(df) >= 2 else 0
                
                positions.append({
                    'ticker': ticker,
                    'shares': shares,
                    'price': round(current_price, 2),
                    'avg_cost': avg_cost,
                    'value': round(position_value, 2),
                    'daily_pct': round(daily_pct, 2),
                    'daily_dollar': round(daily_dollar, 2),
                    'unrealized': round(unrealized, 2),
                    'unrealized_pct': round(unrealized_pct, 2),
                })
                
                total_value += position_value
                total_cost += position_cost
                total_daily_change += daily_dollar
            except Exception:
                continue
        
        if not positions:
            return {}
        
        # Sort for top movers
        by_daily = sorted(positions, key=lambda p: p['daily_pct'], reverse=True)
        by_unrealized = sorted(positions, key=lambda p: p['unrealized'], reverse=True)
        
        total_unrealized = total_value - total_cost
        daily_pct = (total_daily_change / (total_value - total_daily_change) * 100) if (total_value - total_daily_change) else 0
        
        return {
            'portfolio_value': round(total_value, 2),
            'cost_basis_total': round(total_cost, 2),
            'daily_change_dollar': round(total_daily_change, 2),
            'daily_change_pct': round(daily_pct, 2),
            'total_unrealized': round(total_unrealized, 2),
            'total_unrealized_pct': round((total_unrealized / total_cost * 100) if total_cost else 0, 2),
            'positions': positions,
            'top_gainers': [p for p in by_daily[:3] if p['daily_pct'] > 0],
            'top_losers': [p for p in by_daily[-3:] if p['daily_pct'] < 0],
            'biggest_winners': by_unrealized[:3],
            'biggest_losers': by_unrealized[-3:],
            'num_positions': len(positions),
        }

    # ------------------------------------------------------------------
    # Pre-market scan
    # ------------------------------------------------------------------

    def pre_market_scan(self) -> Dict[str, Any]:
        """Run pre-market analysis (designed for 9:00 AM EST).

        Returns:
            Dictionary with:
            - regime: Current VIX regime + overnight change
            - futures_direction: SPY pre-market direction
            - recommended_action: AGGRESSIVE, DEFENSIVE, or HOLD
            - value_picks: Scanner picks if GREEN regime
        """
        result: Dict[str, Any] = {
            'report_type': 'pre_market',
            'timestamp': datetime.now().isoformat(),
        }

        # --- VIX regime ---
        regime_info = RegimeClassifier.get_current_regime()
        result['vix'] = regime_info.get('vix')
        result['regime'] = regime_info.get('regime', 'UNKNOWN')
        result['regime_description'] = regime_info.get('description', '')

        # --- Overnight VIX change ---
        try:
            vix_hist = yf.download('^VIX', period='5d', progress=False)
            if isinstance(vix_hist.columns, pd.MultiIndex):
                vix_hist.columns = vix_hist.columns.get_level_values(0)
            if len(vix_hist) >= 2:
                vix_today = float(vix_hist['Close'].iloc[-1])
                vix_prev = float(vix_hist['Close'].iloc[-2])
                result['vix_change'] = round(vix_today - vix_prev, 2)
                result['vix_change_pct'] = round((vix_today - vix_prev) / vix_prev * 100, 2)
            else:
                result['vix_change'] = 0
                result['vix_change_pct'] = 0
        except Exception:
            result['vix_change'] = 0
            result['vix_change_pct'] = 0

        # --- SPY pre-market direction ---
        try:
            spy = yf.download('SPY', period='2d', interval='1d', progress=False)
            if isinstance(spy.columns, pd.MultiIndex):
                spy.columns = spy.columns.get_level_values(0)
            if len(spy) >= 2:
                spy_prev = float(spy['Close'].iloc[-2])
                spy_last = float(spy['Close'].iloc[-1])
                result['spy_level'] = round(spy_last, 2)
                result['spy_change_pct'] = round((spy_last - spy_prev) / spy_prev * 100, 2)
            else:
                result['spy_level'] = 0
                result['spy_change_pct'] = 0
        except Exception:
            result['spy_level'] = 0
            result['spy_change_pct'] = 0

        # --- Recommended action ---
        regime = result['regime']
        vix_change = result.get('vix_change_pct', 0)

        if regime == 'GREEN' and vix_change < 5:
            result['recommended_action'] = 'AGGRESSIVE'
            result['action_detail'] = 'Safe to buy value picks. Run scanner for opportunities.'
        elif regime == 'YELLOW':
            result['recommended_action'] = 'DEFENSIVE'
            result['action_detail'] = 'Trim winners with >50% gain. Redeploy into oversold quality.'
        elif regime == 'RED':
            result['recommended_action'] = 'HOLD'
            result['action_detail'] = 'Full defensive mode. No buying. Preserve capital.'
        else:
            result['recommended_action'] = 'HOLD'
            result['action_detail'] = 'Unable to determine regime. Stay cautious.'


        # --- Portfolio snapshot ---
        result['portfolio'] = self._fetch_portfolio_snapshot()
        return result

    # ------------------------------------------------------------------
    # Intraday check
    # ------------------------------------------------------------------

    def intraday_check(self) -> Dict[str, Any]:
        """Run intraday analysis (for 9:30 AM - 4:00 PM EST).

        Returns:
            Dictionary with:
            - index_levels: Current SPY/QQQ/VIX levels and % change
            - momentum_score: -5 to +5 scale
            - sector_rotation: Leading and lagging sectors today
            - breadth: Market breadth indicators
        """
        result: Dict[str, Any] = {
            'report_type': 'intraday',
            'timestamp': datetime.now().isoformat(),
        }

        # --- Index levels ---
        index_data = self._fetch_index_data(period='2d', interval='1d')
        result['indices'] = {}
        for ticker, df in index_data.items():
            label = ticker.replace('^', '')
            result['indices'][label] = self._compute_daily_change(df)

        # --- Momentum score ---
        result['momentum_score'] = self._compute_intraday_momentum(index_data)
        momentum = result['momentum_score']
        if momentum >= 3:
            result['momentum_label'] = 'Strong Bullish'
        elif momentum >= 1:
            result['momentum_label'] = 'Mildly Bullish'
        elif momentum == 0:
            result['momentum_label'] = 'Neutral'
        elif momentum >= -2:
            result['momentum_label'] = 'Mildly Bearish'
        else:
            result['momentum_label'] = 'Strong Bearish'

        # --- Sector rotation ---
        sector_data = self._fetch_sector_data(period='2d', interval='1d')
        sector_perf: List[Tuple[str, str, float]] = []
        for etf, df in sector_data.items():
            sector_name = self.sector_etfs.get(etf, etf)
            change = self._compute_daily_change(df)
            sector_perf.append((etf, sector_name, change['change_pct']))

        sector_perf.sort(key=lambda x: x[2], reverse=True)
        result['sector_leaders'] = [
            {'etf': s[0], 'sector': s[1], 'change_pct': s[2]}
            for s in sector_perf[:3]
        ]
        result['sector_laggards'] = [
            {'etf': s[0], 'sector': s[1], 'change_pct': s[2]}
            for s in sector_perf[-3:]
        ]

        # --- Regime check ---
        regime_info = RegimeClassifier.get_current_regime()
        result['vix'] = regime_info.get('vix')
        result['regime'] = regime_info.get('regime', 'UNKNOWN')

        # --- Breadth estimate ---
        # Check how many of our universe tickers are up today
        try:
            sample_tickers = config.SP100_TICKERS[:20]  # Sample for speed
            sample_data = yf.download(
                sample_tickers, period='2d', interval='1d', progress=False,
            )
            if isinstance(sample_data.columns, pd.MultiIndex):
                up_count = 0
                total = 0
                for ticker in sample_tickers:
                    try:
                        closes = sample_data.xs(ticker, level=1, axis=1)['Close']
                        if len(closes) >= 2:
                            total += 1
                            if closes.iloc[-1] > closes.iloc[-2]:
                                up_count += 1
                    except (KeyError, TypeError):
                        pass
                result['breadth_up_pct'] = round(up_count / max(total, 1) * 100, 1)
                result['breadth_sample_size'] = total
            else:
                result['breadth_up_pct'] = 50.0
                result['breadth_sample_size'] = 0
        except Exception:
            result['breadth_up_pct'] = 50.0
            result['breadth_sample_size'] = 0


        # --- Portfolio snapshot ---
        result['portfolio'] = self._fetch_portfolio_snapshot()
        return result

    # ------------------------------------------------------------------
    # End-of-day summary
    # ------------------------------------------------------------------

    def eod_summary(self) -> Dict[str, Any]:
        """Run end-of-day analysis (designed for 4:15 PM EST).

        Returns:
            Dictionary with:
            - daily_performance: SPY, QQQ, IWM, VIX changes
            - sector_ranking: Best to worst sectors
            - regime: Current regime + threshold alerts
            - next_day_outlook: Momentum-based direction indicator
        """
        result: Dict[str, Any] = {
            'report_type': 'eod',
            'timestamp': datetime.now().isoformat(),
        }

        # --- Daily performance ---
        index_data = self._fetch_index_data(period='5d', interval='1d')
        result['daily_performance'] = {}
        for ticker, df in index_data.items():
            label = ticker.replace('^', '')
            result['daily_performance'][label] = self._compute_daily_change(df)

        # --- Sector performance ranking ---
        sector_data = self._fetch_sector_data(period='5d', interval='1d')
        sector_perf: List[Dict[str, Any]] = []
        for etf, df in sector_data.items():
            sector_name = self.sector_etfs.get(etf, etf)
            change = self._compute_daily_change(df)
            sector_perf.append({
                'etf': etf,
                'sector': sector_name,
                'change_pct': change['change_pct'],
                'close': change['close'],
            })
        sector_perf.sort(key=lambda x: x['change_pct'], reverse=True)
        result['sector_ranking'] = sector_perf

        # --- Regime + threshold alerts ---
        regime_info = RegimeClassifier.get_current_regime()
        result['vix'] = regime_info.get('vix')
        result['regime'] = regime_info.get('regime', 'UNKNOWN')

        vix_val = regime_info.get('vix', 0) or 0
        result['regime_alerts'] = []
        if abs(vix_val - config.VIX_GREEN) < 2:
            result['regime_alerts'].append(
                f"VIX ({vix_val}) near GREEN/YELLOW threshold ({config.VIX_GREEN})"
            )
        if abs(vix_val - config.VIX_YELLOW) < 2:
            result['regime_alerts'].append(
                f"VIX ({vix_val}) near YELLOW/RED threshold ({config.VIX_YELLOW})"
            )

        # --- Next day outlook ---
        momentum = self._compute_intraday_momentum(index_data)
        result['momentum_score'] = momentum

        # Check 5-day SPY RSI for context
        if 'SPY' in index_data:
            spy_df = index_data['SPY']
            if len(spy_df) >= 5:
                rsi_val = compute_rsi(spy_df['Close'], window=5)
                if rsi_val is not None:
                    rsi_val = float(rsi_val)
                    result['spy_rsi_5d'] = round(rsi_val, 1)
                    if rsi_val > 70:
                        result['next_day_outlook'] = 'Overbought - potential pullback'
                    elif rsi_val < 30:
                        result['next_day_outlook'] = 'Oversold - potential bounce'
                    elif momentum >= 2:
                        result['next_day_outlook'] = 'Bullish momentum continues'
                    elif momentum <= -2:
                        result['next_day_outlook'] = 'Bearish pressure persists'
                    else:
                        result['next_day_outlook'] = 'Neutral/Choppy - wait for direction'
                else:
                    result['next_day_outlook'] = 'Insufficient data'
            else:
                result['next_day_outlook'] = 'Insufficient data'
        else:
            result['next_day_outlook'] = 'SPY data unavailable'


        # --- Portfolio snapshot ---
        result['portfolio'] = self._fetch_portfolio_snapshot()
        return result

    # ------------------------------------------------------------------
    # Full analysis (all modes)
    # ------------------------------------------------------------------

    def full_analysis(self) -> Dict[str, Any]:
        """Run all three analysis modes.

        Returns:
            Dict with keys 'pre_market', 'intraday', 'eod'.
        """
        return {
            'pre_market': self.pre_market_scan(),
            'intraday': self.intraday_check(),
            'eod': self.eod_summary(),
        }

    # ------------------------------------------------------------------
    # Telegram formatting
    # ------------------------------------------------------------------

    def format_telegram_report(self, analysis: Dict[str, Any], report_type: str) -> str:
        """Format analysis as a clean Telegram message.

        Uses ASCII-safe formatting (no emoji/unicode).

        Args:
            analysis: Analysis dictionary from any of the three modes.
            report_type: One of 'pre_market', 'intraday', 'eod'.

        Returns:
            Formatted multi-line string suitable for Telegram.
        """
        if report_type == 'pre_market':
            return self._format_pre_market(analysis)
        elif report_type == 'intraday':
            return self._format_intraday(analysis)
        elif report_type == 'eod':
            return self._format_eod(analysis)
        else:
            return f"Unknown report type: {report_type}"

    def _format_pre_market(self, data: Dict[str, Any]) -> str:
        """Format pre-market analysis for Telegram."""
        lines = [
            "=== PRE-MARKET SCAN ===",
            f"Time: {data.get('timestamp', 'N/A')}",
            "",
            f"VIX:     {data.get('vix', 'N/A')} ({data.get('vix_change_pct', 0):+.1f}%)",
            f"Regime:  {data.get('regime', 'UNKNOWN')}",
            f"SPY:     {data.get('spy_level', 'N/A')} ({data.get('spy_change_pct', 0):+.2f}%)",
            "",
            f"Action:  {data.get('recommended_action', 'N/A')}",
            f"Detail:  {data.get('action_detail', '')}",
        ]

        # Portfolio section
        pf = data.get('portfolio', {})
        if pf:
            lines.extend([
                "",
                "--- Your Portfolio ---",
                f"Value:   ${pf.get('portfolio_value', 0):,.0f} ({pf.get('daily_change_pct', 0):+.2f}% today)",
                f"Day P&L: ${pf.get('daily_change_dollar', 0):+,.0f}",
                f"Total P&L: ${pf.get('total_unrealized', 0):+,.0f} ({pf.get('total_unrealized_pct', 0):+.1f}%)",
            ])
            gainers = pf.get('top_gainers', [])
            losers = pf.get('top_losers', [])
            if gainers:
                lines.append("Movers+: " + ", ".join(f"{p['ticker']} {p['daily_pct']:+.1f}%" for p in gainers))
            if losers:
                lines.append("Movers-: " + ", ".join(f"{p['ticker']} {p['daily_pct']:+.1f}%" for p in losers))
        return "\n".join(lines)

    def _format_intraday(self, data: Dict[str, Any]) -> str:
        """Format intraday analysis for Telegram."""
        lines = [
            "=== INTRADAY CHECK ===",
            f"Time: {data.get('timestamp', 'N/A')}",
            "",
            "--- Indices ---",
        ]
        for label, info in data.get('indices', {}).items():
            lines.append(
                f"  {label:>5}: {info['close']:>8.2f} ({info['change_pct']:+.2f}%)"
            )

        lines.extend([
            "",
            f"Momentum: {data.get('momentum_score', 0):+d}/5 ({data.get('momentum_label', 'N/A')})",
            f"Regime:   {data.get('regime', 'UNKNOWN')} (VIX: {data.get('vix', 'N/A')})",
            f"Breadth:  {data.get('breadth_up_pct', 50):.0f}% up (n={data.get('breadth_sample_size', 0)})",
            "",
            "--- Sector Leaders ---",
        ])
        for s in data.get('sector_leaders', []):
            lines.append(f"  {s['sector']:<25} {s['change_pct']:+.2f}%")

        lines.append("")
        lines.append("--- Sector Laggards ---")
        for s in data.get('sector_laggards', []):
            lines.append(f"  {s['sector']:<25} {s['change_pct']:+.2f}%")


        # Portfolio section
        pf = data.get('portfolio', {})
        if pf:
            lines.extend([
                "",
                "--- Your Portfolio ---",
                f"Value:   ${pf.get('portfolio_value', 0):,.0f} ({pf.get('daily_change_pct', 0):+.2f}% today)",
                f"Day P&L: ${pf.get('daily_change_dollar', 0):+,.0f}",
                f"Total P&L: ${pf.get('total_unrealized', 0):+,.0f} ({pf.get('total_unrealized_pct', 0):+.1f}%)",
            ])
            gainers = pf.get('top_gainers', [])
            losers = pf.get('top_losers', [])
            if gainers:
                lines.append("Movers+: " + ", ".join(f"{p['ticker']} {p['daily_pct']:+.1f}%" for p in gainers))
            if losers:
                lines.append("Movers-: " + ", ".join(f"{p['ticker']} {p['daily_pct']:+.1f}%" for p in losers))
        return "\n".join(lines)

    def _format_eod(self, data: Dict[str, Any]) -> str:
        """Format end-of-day summary for Telegram."""
        lines = [
            "=== END OF DAY SUMMARY ===",
            f"Time: {data.get('timestamp', 'N/A')}",
            "",
            "--- Daily Performance ---",
        ]
        for label, info in data.get('daily_performance', {}).items():
            lines.append(
                f"  {label:>5}: {info['close']:>8.2f} ({info['change_pct']:+.2f}%)"
            )

        lines.extend([
            "",
            f"VIX:     {data.get('vix', 'N/A')}",
            f"Regime:  {data.get('regime', 'UNKNOWN')}",
        ])

        alerts = data.get('regime_alerts', [])
        if alerts:
            lines.append("")
            lines.append("--- Regime Alerts ---")
            for alert in alerts:
                lines.append(f"  [!] {alert}")

        lines.extend([
            "",
            "--- Sector Ranking (Best to Worst) ---",
        ])
        for i, s in enumerate(data.get('sector_ranking', []), 1):
            lines.append(f"  {i:>2}. {s['sector']:<25} {s['change_pct']:+.2f}%")

        lines.extend([
            "",
            f"Momentum:  {data.get('momentum_score', 0):+d}/5",
            f"SPY RSI5:  {data.get('spy_rsi_5d', 'N/A')}",
            f"Outlook:   {data.get('next_day_outlook', 'N/A')}",
        ])


        # Portfolio section
        pf = data.get('portfolio', {})
        if pf:
            lines.extend([
                "",
                "--- Your Portfolio ---",
                f"Value:     ${pf.get('portfolio_value', 0):,.0f} ({pf.get('daily_change_pct', 0):+.2f}% today)",
                f"Day P&L:   ${pf.get('daily_change_dollar', 0):+,.0f}",
                f"Total P&L: ${pf.get('total_unrealized', 0):+,.0f} ({pf.get('total_unrealized_pct', 0):+.1f}%)",
                f"Positions: {pf.get('num_positions', 0)}",
            ])
            gainers = pf.get('top_gainers', [])
            losers = pf.get('top_losers', [])
            if gainers:
                lines.append("Movers+: " + ", ".join(f"{p['ticker']} {p['daily_pct']:+.1f}%" for p in gainers))
            if losers:
                lines.append("Movers-: " + ", ".join(f"{p['ticker']} {p['daily_pct']:+.1f}%" for p in losers))
            winners = pf.get('biggest_winners', [])[:3]
            losers_total = pf.get('biggest_losers', [])[:3]
            if winners:
                lines.append("Best Total: " + ", ".join(f"{p['ticker']} ${p['unrealized']:+,.0f}" for p in winners))
            if losers_total:
                lines.append("Worst Total: " + ", ".join(f"{p['ticker']} ${p['unrealized']:+,.0f}" for p in losers_total))
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"MarketAnalyzer(indices={self.indices}, sectors={len(self.sector_etfs)})"
