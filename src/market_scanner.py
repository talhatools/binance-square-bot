"""Market Scanner: Analyzes liquid USDT pairs and scores promising coins."""
import logging
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from src.binance_client import BinanceClient
from src.database import Database

logger = logging.getLogger(__name__)


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Compute Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    # Wilder's smoothing
    for i in range(period, len(series)):
        avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


class MarketScanner:
    def __init__(self, binance_client: BinanceClient, database: Database):
        self.client = binance_client
        self.db = database

    def score_symbol_technicals(self, df_1h: pd.DataFrame) -> Tuple[float, Dict[str, Any]]:
        """
        Calculates a technical score (0 - 100) based on:
        - Volume spike vs 20-period average volume
        - MA20 / MA50 position and trend alignment
        - RSI momentum
        - Support / Resistance breakout or bounce
        """
        if len(df_1h) < 50:
            return 0.0, {}

        close = df_1h["close"]
        volume = df_1h["volume"]
        high = df_1h["high"]
        low = df_1h["low"]

        # 1. Moving Averages
        ma20 = close.rolling(20).mean()
        ma50 = close.rolling(50).mean()

        current_close = close.iloc[-1]
        current_ma20 = ma20.iloc[-1]
        current_ma50 = ma50.iloc[-1]
        prev_close = close.iloc[-2]

        # Ignore flat pegged assets / stablecoins with less than 2.0% price range across 50 bars
        candle_range = (high.max() - low.min()) / current_close if current_close > 0 else 0
        if candle_range < 0.02:
            return 0.0, {}

        # 2. Volume Spike
        vol_ma20 = volume.rolling(20).mean()
        current_vol = volume.iloc[-1]
        avg_vol = vol_ma20.iloc[-1] if vol_ma20.iloc[-1] > 0 else 1.0
        vol_ratio = current_vol / avg_vol

        # 3. RSI
        rsi_series = compute_rsi(close, 14)
        current_rsi = float(rsi_series.iloc[-1])

        # 4. Support and Resistance detection from recent 40 bars (excluding last candle)
        recent_high = high.iloc[-40:-1].max()
        recent_low = low.iloc[-40:-1].min()

        score = 0.0
        bias = "NEUTRAL"
        reasons = []

        # Trend Analysis
        is_bullish_ma = current_close > current_ma20 > current_ma50
        is_bearish_ma = current_close < current_ma20 < current_ma50
        ma_cross_bull = (close.iloc[-2] <= ma20.iloc[-2]) and (current_close > current_ma20)
        ma_cross_bear = (close.iloc[-2] >= ma20.iloc[-2]) and (current_close < current_ma20)

        # Volume Score (0 to 30 pts)
        if vol_ratio >= 2.0:
            score += 30
            reasons.append(f"Massive volume spike ({vol_ratio:.1f}x 20MA)")
        elif vol_ratio >= 1.4:
            score += 20
            reasons.append(f"Notable volume expansion ({vol_ratio:.1f}x 20MA)")
        elif vol_ratio >= 1.0:
            score += 10

        # Breakout / Rejection / Bounce (0 to 30 pts)
        # Resistance Breakout: current close > recent high
        if current_close > recent_high:
            score += 30
            bias = "LONG"
            reasons.append(f"Breakout above recent resistance ({recent_high:.4f})")
        # Support Breakdown: current close < recent low
        elif current_close < recent_low:
            score += 30
            bias = "SHORT"
            reasons.append(f"Breakdown below recent support ({recent_low:.4f})")
        # Near Support with Bullish Bounce
        elif abs(current_close - recent_low) / current_close < 0.02 and current_close > prev_close:
            score += 25
            bias = "LONG"
            reasons.append("Bullish defense & bounce off key support")
        # Near Resistance with Bearish Rejection
        elif abs(recent_high - current_close) / current_close < 0.02 and current_close < prev_close:
            score += 25
            bias = "SHORT"
            reasons.append("Bearish rejection at key resistance")

        # MA Structure (0 to 25 pts)
        if is_bullish_ma or ma_cross_bull:
            score += 25
            if bias == "NEUTRAL":
                bias = "LONG"
            reasons.append("Strong bullish MA20 > MA50 structure")
        elif is_bearish_ma or ma_cross_bear:
            score += 25
            if bias == "NEUTRAL":
                bias = "SHORT"
            reasons.append("Bearish MA20 < MA50 alignment")

        # RSI Momentum (0 to 15 pts)
        if bias == "LONG":
            if 50 <= current_rsi <= 68:
                score += 15
                reasons.append(f"RSI in optimal bullish momentum zone ({current_rsi:.1f})")
            elif 40 <= current_rsi < 50:
                score += 8
            elif current_rsi > 75:
                score -= 15  # Penalize severely overbought
                reasons.append(f"Overbought RSI warning ({current_rsi:.1f})")
        elif bias == "SHORT":
            if 32 <= current_rsi <= 50:
                score += 15
                reasons.append(f"RSI in optimal bearish continuation zone ({current_rsi:.1f})")
            elif 50 < current_rsi <= 60:
                score += 8
            elif current_rsi < 25:
                score -= 15  # Penalize severely oversold
                reasons.append(f"Oversold RSI warning ({current_rsi:.1f})")

        metrics = {
            "score": round(max(0.0, score), 2),
            "bias": bias,
            "current_price": current_close,
            "ma20": current_ma20,
            "ma50": current_ma50,
            "rsi": current_rsi,
            "vol_ratio": vol_ratio,
            "support": recent_low,
            "resistance": recent_high,
            "reasons": reasons,
        }
        return metrics["score"], metrics

    def get_top_candidates(
        self,
        min_quote_volume: float = 10_000_000.0,
        cooldown_hours: float = 6.0,
        candidate_pool_limit: int = 25,
        top_n: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Scans all 24h USDT pairs, filters by volume, checks cooldown,
        scores candidates with 1h klines, and returns the top N ranked candidates.
        """
        logger.info("Scanning Binance market for promising coins...")
        usdt_pairs = self.client.get_usdt_pairs_24h(min_quote_volume=min_quote_volume)

        if not usdt_pairs:
            logger.warning("No USDT pairs found meeting the volume requirement.")
            return []

        # Filter out coins currently on cooldown in SQLite (unless cooldown_hours <= 0 for force mode)
        eligible_pairs = []
        for pair in usdt_pairs:
            sym = pair["symbol"]
            if cooldown_hours > 0 and self.db.is_coin_on_cooldown(sym, cooldown_hours=cooldown_hours):
                continue
            eligible_pairs.append(pair)

        if not eligible_pairs:
            logger.warning("All active high-volume coins are currently on cooldown.")
            return []

        # Sort candidate pool by preliminary volatility & liquidity
        eligible_pairs.sort(
            key=lambda p: abs(p["price_change_percent"]) * np.log10(max(p["quote_volume"], 1.0)),
            reverse=True,
        )
        pool = eligible_pairs[:candidate_pool_limit]

        scored_candidates = []
        for pair in pool:
            sym = pair["symbol"]
            try:
                df_1h = self.client.get_klines(sym, interval="1h", limit=60)
                score, metrics = self.score_symbol_technicals(df_1h)

                if metrics.get("bias") != "NEUTRAL" and score >= 30.0:
                    scored_candidates.append(
                        {
                            "symbol": sym,
                            "base_asset": pair["base_asset"],
                            "quote_volume": pair["quote_volume"],
                            "price_change_percent": pair["price_change_percent"],
                            "score": score,
                            "metrics": metrics,
                            "df_1h": df_1h,
                        }
                    )
            except Exception as exc:
                logger.warning(f"Error evaluating candidate {sym}: {exc}")
                continue

        scored_candidates.sort(key=lambda c: c["score"], reverse=True)
        return scored_candidates[:top_n]

    def pick_promising_coin(
        self,
        min_quote_volume: float = 10_000_000.0,
        cooldown_hours: float = 6.0,
        top_candidates_limit: int = 25,
    ) -> Optional[Dict[str, Any]]:
        """Picks the single top scored coin."""
        candidates = self.get_top_candidates(
            min_quote_volume=min_quote_volume,
            cooldown_hours=cooldown_hours,
            candidate_pool_limit=top_candidates_limit,
            top_n=1,
        )
        if not candidates:
            return None
        winner = candidates[0]
        logger.info(
            f"Picked top coin: {winner['symbol']} (Score: {winner['score']}, "
            f"Bias: {winner['metrics']['bias']}, 24h Vol: ${winner['quote_volume']:,.0f})"
        )
        return winner
