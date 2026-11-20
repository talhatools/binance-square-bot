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


def test_post_style_selection():
    writer = AIWriter(api_key=None)
    analyzer = TechnicalAnalyzer()
    df_1h = _generate_synthetic_candles(60, "bullish")
    df_4h = _generate_synthetic_candles(60, "bullish")
    setup = analyzer.analyze("ETHUSDT", df_1h, df_4h)

    styles = ["sniper", "technical", "clean", "conversational", "danger_zone", "whale", "reversal"]
    for style in styles:
        text = writer.generate_post_text(setup, post_style=style)
        assert "$ETH" in text
        assert len(text) > 20
        assert "not financial advice" not in text.lower()
        assert "dyor" not in text.lower()


def test_verbose_dropdown_normalization_and_samples():
    from src.ai_writer import normalize_post_style, get_sample_posts

    # Test normalization of full verbose dropdown labels
    assert normalize_post_style("sniper - 🚀 Guys, LONG $BTC Now! Entry: 91k | TP1: 93k | SL: 89k") == "sniper"
    assert normalize_post_style("technical - 📊 Multi-TF TA | MA20 + RSI | Multi-TPs with %") == "technical"
    assert normalize_post_style("clean - ✨ Clean setup | $BTC BIG LONG : Testing support") == "clean"
    assert normalize_post_style("conversational - 💬 guys, have you seen what is happening with $BTC? 🚨") == "conversational"
    assert normalize_post_style("danger_zone - ⚠️ $BTC ENTERING CRITICAL DANGER ZONE ... UNWIND") == "danger_zone"
    assert normalize_post_style("whale - 🐋 Orderbook whale trap | Don't fight smart money") == "whale"
    assert normalize_post_style("reversal - 🔄 Big reversal recovery | Flush already happened") == "reversal"
    assert normalize_post_style("auto - (Har bar naya style rotate karega)") == "auto"

    # Test sample posts generation
    samples = get_sample_posts()
    assert len(samples) == 7
    for name, sample_text in samples.items():
        assert "$BTC" in sample_text
        assert len(sample_text) > 40
        assert "not financial advice" not in sample_text.lower()


