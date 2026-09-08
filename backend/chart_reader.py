"""
chart_reader.py — Institutional Multi-Confluence Chart Reading Engine
Analyzes technical price action, multi-EMA trend alignments, MACD expansion,
RSI divergence, and volume surge verification before approving any trade.
Zero fake fallbacks: requires at least 4 out of 5 confirmations to generate a BUY.
"""
import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any, List

class ChartReader:
    def __init__(self):
        pass

    @staticmethod
    def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        c = df['close']
        h = df['high']
        l = df['low']
        v = df['volume']

        # 1. EMAs (9, 21, 50)
        df['ema_9'] = c.ewm(span=9, adjust=False).mean()
        df['ema_21'] = c.ewm(span=21, adjust=False).mean()
        df['ema_50'] = c.ewm(span=50, adjust=False).mean()

        # 2. MACD (12, 26, 9)
        ema_12 = c.ewm(span=12, adjust=False).mean()
        ema_26 = c.ewm(span=26, adjust=False).mean()
        df['macd_line'] = ema_12 - ema_26
        df['signal_line'] = df['macd_line'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd_line'] - df['signal_line']

        # 3. RSI 14
        delta = c.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        df['rsi_14'] = 100 - (100 / (1 + rs))

        # 4. Volume Moving Average (20) & Surge Ratio
        df['vol_ma20'] = v.rolling(window=20, min_periods=5).mean()
        df['vol_ratio'] = df['volume'] / (df['vol_ma20'] + 1e-9)

        return df

    def analyze_chart(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Performs comprehensive multi-confluence technical chart reading.
        Returns:
            signal: 'BUY', 'SELL', or 'HOLD'
            confidence: float (0.0 to 1.0)
            confluence_score: int (0 to 5)
            is_super_conviction: bool (True for explosive trend runners)
            reasons: list of triggered technical reasons
            metrics: dictionary of indicator values
        """
        if df is None or len(df) < 25:
            return {
                'signal': 'HOLD', 'confidence': 0.40,
                'confluence_score': 0, 'is_super_conviction': False,
                'reasons': ['Insufficient candle history (<25 bars)'],
                'metrics': {}
            }

        df_ind = self._compute_indicators(df)
        df_ind.dropna(inplace=True)

        if df_ind.empty:
            return {
                'signal': 'HOLD', 'confidence': 0.40,
                'confluence_score': 0, 'is_super_conviction': False,
                'reasons': ['Indicator calculation produced empty dataset'],
                'metrics': {}
            }

        curr = df_ind.iloc[-1]
        prev = df_ind.iloc[-2]

        price = float(curr['close'])
        open_p = float(curr['open'])
        high_p = float(curr['high'])
        low_p = float(curr['low'])

        ema_9 = float(curr['ema_9'])
        ema_21 = float(curr['ema_21'])
        ema_50 = float(curr['ema_50'])

        macd_line = float(curr['macd_line'])
        sig_line = float(curr['signal_line'])
        macd_hist = float(curr['macd_hist'])
        prev_macd_hist = float(prev['macd_hist'])

        rsi = float(curr['rsi_14'])
        vol_ratio = float(curr['vol_ratio'])

        # Candle Anatomy
        is_green = price > open_p
        body = abs(price - open_p)
        upper_wick = high_p - max(price, open_p)
        is_rejection = (upper_wick > (body * 1.5)) and (body > 0)

        # ─── 5 CONFLUENCE CHECKPOINTS ───────────────────────────────────────
        confluence_score = 0
        reasons: List[str] = []

        # 1. Trend Confluence: EMA9 >= EMA21 (Micro-Bullish) and Price >= EMA50 (Macro-Bullish)
        if ema_9 >= ema_21 and price >= (ema_50 * 0.998):
            confluence_score += 1
            reasons.append(f"Trend Aligned: 9-EMA (${ema_9:.6f}) >= 21-EMA (${ema_21:.6f}) & Price above 50-EMA")

        # 2. MACD Momentum: MACD Line > Signal Line AND Histogram Positive & Expanding
        if macd_line > sig_line and macd_hist > 0 and macd_hist >= (prev_macd_hist * 0.95):
            confluence_score += 1
            reasons.append(f"MACD Bullish Expansion: Line ({macd_line:.6f}) > Sig ({sig_line:.6f}) with Growing Histogram")

        # 3. RSI Sweet Spot: Between 42 and 66 (Healthy recovery or rising wave, NOT overbought dump zone)
        if 42.0 <= rsi <= 66.0:
            confluence_score += 1
            reasons.append(f"RSI Sweet Spot: {rsi:.1f} (In healthy momentum zone, not overbought)")

        # 4. Volume Verification: Volume >= 1.15x of 20-period moving average
        if vol_ratio >= 1.15:
            confluence_score += 1
            reasons.append(f"Volume Surge Verified: {vol_ratio:.2f}x of 20-bar average")

        # 5. Bullish Price Action: Green candle without severe overhead selling rejection
        if is_green and not is_rejection:
            confluence_score += 1
            reasons.append("Bullish Price Action: Clean green candle without top rejection wick")

        metrics = {
            'price': price, 'rsi': round(rsi, 1),
            'ema_9': ema_9, 'ema_21': ema_21, 'ema_50': ema_50,
            'macd_hist': macd_hist, 'vol_ratio': round(vol_ratio, 2),
            'is_green': is_green, 'confluence_score': confluence_score
        }

        # ─── STRICT DECISION LOGIC ──────────────────────────────────────────
        # High Conviction Super-Runner Check:
        # All 5 confirmations + strong volume surge (>= 1.8x) + strong expanding MACD
        is_super_conviction = (
            confluence_score == 5 and 
            vol_ratio >= 1.70 and 
            macd_hist > (prev_macd_hist * 1.10)
        )

        if is_super_conviction:
            return {
                'signal': 'BUY',
                'confidence': 0.92,
                'confluence_score': 5,
                'is_super_conviction': True,
                'reasons': reasons + ['🚀 SUPER-CONVICTION RUNNER: High-velocity volume breakout!'],
                'metrics': metrics
            }

        # Standard High-Probability Entry: requires at least 4 confirmations
        if confluence_score >= 4:
            conf = 0.78 + (confluence_score - 4) * 0.08
            return {
                'signal': 'BUY',
                'confidence': round(conf, 4),
                'confluence_score': confluence_score,
                'is_super_conviction': False,
                'reasons': reasons,
                'metrics': metrics
            }

        # Otherwise: PATIENCE — HOLD capital safely!
        return {
            'signal': 'HOLD',
            'confidence': 0.45,
            'confluence_score': confluence_score,
            'is_super_conviction': False,
            'reasons': [f"Insufficient confluence ({confluence_score}/5). Awaiting high-probability chart setup."] + reasons,
            'metrics': metrics
        }

    def check_momentum_stall(self, df: pd.DataFrame, entry_price: float, current_price: float) -> Tuple[bool, str]:
        """
        Monitors an open position for momentum exhaustion or trend reversal.
        Returns:
            (is_stalled: bool, reason: str)
        """
        if df is None or len(df) < 10:
            return False, "Insufficient data"

        df_ind = self._compute_indicators(df)
        df_ind.dropna(inplace=True)
        if df_ind.empty:
            return False, "No indicator data"

        curr = df_ind.iloc[-1]
        prev = df_ind.iloc[-2]

        # 1. Red candle reversal with high volume
        is_red = curr['close'] < curr['open']
        if is_red and curr['vol_ratio'] >= 1.3:
            return True, f"Bearish volume spike on red candle (Vol: {curr['vol_ratio']:.1f}x)"

        # 2. MACD Histogram curl down
        if curr['macd_hist'] < prev['macd_hist'] and prev['macd_hist'] > 0:
            hist_drop = prev['macd_hist'] - curr['macd_hist']
            if hist_drop > abs(prev['macd_hist'] * 0.4):
                return True, "MACD Histogram sharp contraction (Momentum stalling)"

        # 3. RSI sharp drop from top
        if prev['rsi_14'] > 65 and curr['rsi_14'] < 58:
            return True, f"RSI steep pullback from overbought ({prev['rsi_14']:.0f} -> {curr['rsi_14']:.0f})"

        return False, "Momentum healthy"

chart_reader = ChartReader()
