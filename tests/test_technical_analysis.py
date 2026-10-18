"""Unit tests for Technical Analysis calculations and setups."""
import pandas as pd
import numpy as np
from src.market_scanner import compute_rsi
from src.technical_analysis import (
    compute_atr,
    find_support_resistance,
    TechnicalAnalyzer,
    TradeSetup,
)


def _generate_synthetic_candles(n: int = 60, trend: str = "bullish") -> pd.DataFrame:
    base_price = 100.0
    dates = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    data = []

    price = base_price
    for i in range(n):
        if trend == "bullish":
            price += np.random.uniform(-0.3, 0.8)
        elif trend == "bearish":
            price -= np.random.uniform(-0.3, 0.8)
        else:
            price += np.random.uniform(-0.5, 0.5)

        high = price + np.random.uniform(0.1, 0.5)
        low = price - np.random.uniform(0.1, 0.5)
        close = price + np.random.uniform(-0.2, 0.2)
        open_ = price - np.random.uniform(-0.2, 0.2)
        vol = np.random.uniform(1000, 5000)

        data.append({
            "timestamp": dates[i],
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
        })

    df = pd.DataFrame(data).set_index("timestamp")
    return df


def test_compute_rsi():
    # Uptrend prices should produce RSI > 50
    df = _generate_synthetic_candles(60, "bullish")
    rsi = compute_rsi(df["close"], 14)
    assert len(rsi) == 60
    assert 0 <= rsi.iloc[-1] <= 100
    assert rsi.iloc[-1] > 50


def test_compute_atr():
    df = _generate_synthetic_candles(60, "bullish")
    atr = compute_atr(df, 14)
    assert atr > 0.0


def test_find_support_resistance():
    df = _generate_synthetic_candles(60, "flat")
    sup, res = find_support_resistance(df)
    current_price = df["close"].iloc[-1]
    assert sup < current_price
    assert res > current_price


def test_analyzer_trade_setup():
    analyzer = TechnicalAnalyzer()
    df_1h = _generate_synthetic_candles(60, "bullish")
    df_4h = _generate_synthetic_candles(60, "bullish")

    setup = analyzer.analyze("TESTUSDT", df_1h, df_4h)
    assert isinstance(setup, TradeSetup)
    assert setup.direction in ("LONG", "SHORT", "NO_TRADE")
    if setup.direction == "LONG":
        assert setup.target_price > setup.current_price
        assert setup.stop_loss < setup.current_price
        assert setup.risk_reward >= 1.4
