"""Unit tests for AI post writing and character constraints."""
from src.ai_writer import AIWriter
from src.technical_analysis import TechnicalAnalyzer
from tests.test_technical_analysis import _generate_synthetic_candles


def test_template_fallback_and_length():
    writer = AIWriter(api_key=None)  # forces fallback template
    analyzer = TechnicalAnalyzer()

    df_1h = _generate_synthetic_candles(60, "bullish")
    df_4h = _generate_synthetic_candles(60, "bullish")
    setup = analyzer.analyze("BTCUSDT", df_1h, df_4h)

    text = writer.generate_post_text(setup)
    assert "$BTC" in text
    assert "not financial advice" not in text.lower()
    assert "nfa" not in text.lower()
    assert any(term in text.lower() for term in ["trade", "entry", "position", "targets", "print"])
    assert len(text) <= 600


def test_enforce_length_and_cta():
    writer = AIWriter(api_key=None)
    long_text = "Bullish momentum on $ETH. Not financial advice. " * 30
    cleaned = writer._enforce_length_and_cta(long_text)
    assert "not financial advice" not in cleaned.lower()
    assert len(cleaned) <= 600
    assert any(term in cleaned.lower() for term in ["trade", "position", "entry", "targets"])


def test_clean_disclaimers():
    writer = AIWriter(api_key=None)
    dirty_text = "$SOL setup.\nNot financial advice.\nDYOR!\nThis is not financial advice."
    cleaned = writer._clean_disclaimers(dirty_text)
    assert "financial advice" not in cleaned.lower()
    assert "dyor" not in cleaned.lower()
    assert "$SOL setup." in cleaned
