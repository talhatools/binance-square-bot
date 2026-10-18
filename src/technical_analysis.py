"""Technical Analysis Engine: 4h + 1h multi-timeframe analysis, levels, and trade setups."""
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
import pandas as pd
import numpy as np
from src.market_scanner import compute_rsi

logger = logging.getLogger(__name__)


@dataclass
class TradeSetup:
    coin: str
    direction: str  # 'LONG', 'SHORT', 'NO_TRADE'
    current_price: float
    entry_low: float
    entry_high: float
    target_price: float
    stop_loss: float
    risk_reward: float
    support_level: float
    resistance_level: float
    rsi_1h: float
    ma20_1h: float
    ma50_1h: float
    ma50_4h: float
    timeframe: str
    reasons: list
    df_1h: pd.DataFrame
    df_4h: pd.DataFrame


def compute_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculates Average True Range."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean().iloc[-1]
    return float(atr) if not np.isnan(atr) else float(close.iloc[-1] * 0.02)


def find_support_resistance(
    df: pd.DataFrame, window: int = 5
) -> Tuple[float, float]:
    """Finds immediate support and resistance using swing highs and lows."""
    highs = df["high"].values
    lows = df["low"].values
    current_price = df["close"].iloc[-1]

    resistance_levels = []
    support_levels = []

    for i in range(window, len(df) - window):
        # Local peak
        if highs[i] == max(highs[i - window : i + window + 1]):
            resistance_levels.append(highs[i])
        # Local trough
        if lows[i] == min(lows[i - window : i + window + 1]):
            support_levels.append(lows[i])

    # Resistance: lowest peak above current price, or max of recent bars
    above = [r for r in resistance_levels if r > current_price * 1.002]
    resistance = min(above) if above else float(highs[-20:].max())

    # Support: highest trough below current price, or min of recent bars
    below = [s for s in support_levels if s < current_price * 0.998]
    support = max(below) if below else float(lows[-20:].min())

    # Safeguard sanity
    if resistance <= current_price:
        resistance = current_price * 1.03
    if support >= current_price:
        support = current_price * 0.97

    return float(support), float(resistance)


class TechnicalAnalyzer:
    def __init__(self, min_risk_reward: float = 1.4):
        self.min_risk_reward = min_risk_reward

    def analyze(
        self, coin: str, df_1h: pd.DataFrame, df_4h: pd.DataFrame
    ) -> TradeSetup:
        """
        Performs rule-based multi-timeframe analysis on 1h and 4h data.
        Returns a TradeSetup with direction LONG, SHORT, or NO_TRADE.
        """
        close_1h = df_1h["close"]
        close_4h = df_4h["close"]

        current_price = float(close_1h.iloc[-1])

        # 1H Moving Averages & RSI
        ma20_1h = float(close_1h.rolling(20).mean().iloc[-1])
        ma50_1h = float(close_1h.rolling(50).mean().iloc[-1])
        rsi_1h = float(compute_rsi(close_1h, 14).iloc[-1])
        atr_1h = compute_atr(df_1h, 14)

        # 4H Moving Average (Trend filter)
        ma50_4h = float(close_4h.rolling(50).mean().iloc[-1]) if len(df_4h) >= 50 else ma50_1h
        trend_4h_bull = close_4h.iloc[-1] >= ma50_4h

        # Support & Resistance levels from 1h & 4h composite
        sup_1h, res_1h = find_support_resistance(df_1h)
        sup_4h, res_4h = find_support_resistance(df_4h)
        support = max(sup_1h, sup_4h * 0.98)
        resistance = min(res_1h, res_4h * 1.02)

        direction = "NO_TRADE"
        reasons = []

        # --- Rule-Based LONG Conditions ---
        # 1. 4H trend is supportive (Price >= 4H MA50) OR strong 1H momentum
        # 2. 1H Price above MA20 and MA20 >= MA50
        # 3. 1H RSI in bullish territory (45 <= RSI <= 68)
        # 4. Reaction: Bouncing off support or breakout above resistance
        # --- Rule-Based LONG Conditions ---
        # 1. 4H trend is supportive (Price >= 4H MA50 * 0.985) OR strong 1H momentum
        # 2. 1H Price holding near/above MA20 and MA20 >= MA50 * 0.99
        # 3. 1H RSI in bullish territory (40 <= RSI <= 74)
        is_long_trend = current_price >= (ma20_1h * 0.998) and ma20_1h >= (ma50_1h * 0.99)
        is_long_rsi = 40.0 <= rsi_1h <= 74.0
        trend_4h_bull_adjusted = trend_4h_bull or (current_price >= ma50_4h * 0.985)

        # --- Rule-Based SHORT Conditions ---
        # 1. 4H trend is bearish (Price <= 4H MA50 * 1.015)
        # 2. 1H Price below/near MA20 and MA20 <= MA50 * 1.01
        # 3. 1H RSI in bearish territory (26 <= RSI <= 60)
        is_short_trend = current_price <= (ma20_1h * 1.002) and ma20_1h <= (ma50_1h * 1.01)
        is_short_rsi = 26.0 <= rsi_1h <= 60.0
        trend_4h_bear_adjusted = (not trend_4h_bull) or (current_price <= ma50_4h * 1.015)

        if is_long_trend and is_long_rsi and trend_4h_bull_adjusted:
            direction = "LONG"
            reasons.append(f"Bullish 4H & 1H trend alignment (Price > MA20: {ma20_1h:.4f})")
            reasons.append(f"Healthy RSI momentum ({rsi_1h:.1f})")
            if current_price >= resistance * 0.995:
                reasons.append("Breakout pressure against resistance")
            else:
                reasons.append("Holding above key support level")

        elif is_short_trend and is_short_rsi and trend_4h_bear_adjusted:
            direction = "SHORT"
            reasons.append(f"Bearish 4H & 1H trend alignment (Price < MA20: {ma20_1h:.4f})")
            reasons.append(f"Bearish RSI continuation ({rsi_1h:.1f})")
            if current_price <= support * 1.005:
                reasons.append("Breakdown pressure under support")
            else:
                reasons.append("Rejection below key resistance level")

        # --- Calculate Entry, Target, and Stop-Loss ---
        if direction == "LONG":
            entry_low = round(current_price * 0.996, 4)
            entry_high = round(current_price * 1.004, 4)

            # Stop loss: below support or 1.5 * ATR
            sl_candidate = max(support - (0.5 * atr_1h), current_price - (2.0 * atr_1h))
            stop_loss = round(min(sl_candidate, current_price * 0.98), 4)

            # Target: near resistance or 2x risk
            risk = current_price - stop_loss
            tp_candidate = max(resistance, current_price + (risk * 1.8))
            target_price = round(tp_candidate, 4)

            reward = target_price - current_price
            risk_reward = round(reward / risk, 2) if risk > 0 else 0.0

        elif direction == "SHORT":
            entry_low = round(current_price * 0.996, 4)
            entry_high = round(current_price * 1.004, 4)

            # Stop loss: above resistance or 1.5 * ATR
            sl_candidate = min(resistance + (0.5 * atr_1h), current_price + (2.0 * atr_1h))
            stop_loss = round(max(sl_candidate, current_price * 1.02), 4)

            # Target: near support or 2x risk
            risk = stop_loss - current_price
            tp_candidate = min(support, current_price - (risk * 1.8))
            target_price = round(tp_candidate, 4)

            reward = current_price - target_price
            risk_reward = round(reward / risk, 2) if risk > 0 else 0.0

        else:
            # NO_TRADE
            entry_low = current_price
            entry_high = current_price
            target_price = current_price
            stop_loss = current_price
            risk_reward = 0.0
            reasons.append("Market in consolidation / conflicting multi-timeframe signals")

        # Check Risk/Reward sanity: if R:R < min_risk_reward, downgrade to NO_TRADE
        if direction in ("LONG", "SHORT") and risk_reward < self.min_risk_reward:
            logger.info(
                f"Downgrading {coin} to NO_TRADE: Risk/Reward ({risk_reward:.2f}) < threshold ({self.min_risk_reward:.2f})"
            )
            direction = "NO_TRADE"
            reasons.append(f"Insufficient Risk-to-Reward ratio ({risk_reward:.2f} < {self.min_risk_reward})")

        return TradeSetup(
            coin=coin,
            direction=direction,
            current_price=current_price,
            entry_low=entry_low,
            entry_high=entry_high,
            target_price=target_price,
            stop_loss=stop_loss,
            risk_reward=risk_reward,
            support_level=support,
            resistance_level=resistance,
            rsi_1h=rsi_1h,
            ma20_1h=ma20_1h,
            ma50_1h=ma50_1h,
            ma50_4h=ma50_4h,
            timeframe="1H / 4H",
            reasons=reasons,
            df_1h=df_1h,
            df_4h=df_4h,
        )
