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
        binance_path = chart_gen.generate_chart(setup, bars_count=40, style="competitor")
        assert Path(binance_path).exists()
        assert Path(binance_path).stat().st_size > 1000

        # 3. Test Binance App Sada (clean, no lines, no logo) style
        sada_path = chart_gen.generate_chart(setup, bars_count=40, style="sada")
        assert Path(sada_path).exists()
        assert "sada" in Path(sada_path).name
        assert Path(sada_path).stat().st_size > 1000

        # 4. Test Binance Mobile App Portrait Screenshot style
        mobile_path = chart_gen.generate_chart(setup, bars_count=35, style="mobile")
        assert Path(mobile_path).exists()
        assert "mobile" in Path(mobile_path).name
        assert Path(mobile_path).stat().st_size > 1000

        # 5. Test TradingView 4H default style
        tv_4h_path = chart_gen.generate_chart(setup, bars_count=40, style="tradingview", timeframe="4h")
        assert Path(tv_4h_path).exists()
        assert "4h" in Path(tv_4h_path).name.lower()
        assert Path(tv_4h_path).stat().st_size > 1000

        # 6. Test alternating default style
        alt_path = chart_gen.generate_chart(setup, bars_count=40)
        assert Path(alt_path).exists()
        assert Path(alt_path).stat().st_size > 1000
