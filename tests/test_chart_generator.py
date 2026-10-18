"""Unit tests for Candlestick Chart generation (Dual Style: TradingView & Binance App)."""
import tempfile
from pathlib import Path
from src.chart_generator import ChartGenerator
from src.technical_analysis import TechnicalAnalyzer
from tests.test_technical_analysis import _generate_synthetic_candles


def test_chart_generation_both_styles():
    with tempfile.TemporaryDirectory() as tmp_dir:
        chart_gen = ChartGenerator(output_dir=tmp_dir, watermark_text="Talha Sniper", default_style="both")
        analyzer = TechnicalAnalyzer()

        df_1h = _generate_synthetic_candles(60, "bullish")
        df_4h = _generate_synthetic_candles(60, "bullish")
        setup = analyzer.analyze("SOLUSDT", df_1h, df_4h)

        # 1. Test TradingView style
        tv_path = chart_gen.generate_chart(setup, bars_count=40, style="tradingview")
        assert Path(tv_path).exists()
        assert Path(tv_path).stat().st_size > 1000

        # 2. Test Binance App competitor style
        binance_path = chart_gen.generate_chart(setup, bars_count=40, style="binance_app")
        assert Path(binance_path).exists()
        assert Path(binance_path).stat().st_size > 1000

        # 3. Test alternating default style
        alt_path = chart_gen.generate_chart(setup, bars_count=40)
        assert Path(alt_path).exists()
        assert Path(alt_path).stat().st_size > 1000
