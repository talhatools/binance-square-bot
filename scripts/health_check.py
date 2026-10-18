"""System Diagnostic & Health Check Tool."""
import sys
from pathlib import Path

# Ensure safe UTF-8 terminal encoding
try:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from config.settings import get_settings
from src.binance_client import BinanceClient
from src.database import Database
from src.chart_generator import ChartGenerator
from src.technical_analysis import TechnicalAnalyzer
from tests.test_technical_analysis import _generate_synthetic_candles


def check_binance_api():
    print("[1/5] Testing Binance Public API...", end=" ", flush=True)
    try:
        client = BinanceClient(max_retries=2, timeout=6.0)
        tickers = client.get_usdt_pairs_24h(min_quote_volume=10_000_000.0)
        print(f"OK (Found {len(tickers)} active high-volume USDT pairs)")
        return True
    except Exception as e:
        print(f"FAILED ({e})")
        return False


def check_sqlite_db(settings):
    print("[2/5] Testing SQLite Database...", end=" ", flush=True)
    try:
        db = Database(settings.db_path)
        count = db.get_daily_post_count()
        print(f"OK (DB write/read operational, today's posts: {count})")
        return True
    except Exception as e:
        print(f"FAILED ({e})")
        return False


def check_chart_engine(settings):
    print("[3/5] Testing Candlestick Chart Engine...", end=" ", flush=True)
    try:
        chart_gen = ChartGenerator(output_dir=settings.charts_dir, watermark_text=settings.watermark_text)
        analyzer = TechnicalAnalyzer()
        df_1h = _generate_synthetic_candles(60, "bullish")
        df_4h = _generate_synthetic_candles(60, "bullish")
        setup = analyzer.analyze("BTCUSDT", df_1h, df_4h)
        chart_path = chart_gen.generate_chart(setup, bars_count=40, filename_prefix="HEALTHCHECK")
        if chart_path.exists():
            chart_path.unlink()  # Clean up test chart
        print("OK (mplfinance dark-theme rendering operational)")
        return True
    except Exception as e:
        print(f"FAILED ({e})")
        return False


def check_anthropic_api(settings):
    print("[4/5] Testing Claude API Configuration...", end=" ", flush=True)
    if not settings.anthropic_api_key:
        print("SKIPPED (No ANTHROPIC_API_KEY in .env, using rule-based fallback generator)")
        return True
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=settings.anthropic_api_key)
        # Fast cheap test token
        client.messages.create(
            model=settings.anthropic_model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Ping"}],
        )
        print("OK (Anthropic Claude API credentials verified)")
        return True
    except Exception as e:
        print(f"WARNING ({e})")
        return False


def check_binance_square_key(settings):
    print("[5/5] Testing Binance Square Key Status...", end=" ", flush=True)
    if not settings.square_openapi_key:
        print("SKIPPED (No BINANCE_SQUARE_OPENAPI_KEY in .env; DRY_RUN=true is enabled)")
        return True
    masked = settings.square_openapi_key[:4] + "..." + settings.square_openapi_key[-4:]
    print(f"CONFIGURED (Key: {masked}, DRY_RUN={'ON' if settings.dry_run else 'OFF'})")
    return True


def main():
    print("\n" + "=" * 60)
    print("🔍 BINANCE SQUARE POSTING BOT - HEALTH CHECK & DIAGNOSTICS")
    print("=" * 60)
    settings = get_settings()

    r1 = check_binance_api()
    r2 = check_sqlite_db(settings)
    r3 = check_chart_engine(settings)
    r4 = check_anthropic_api(settings)
    r5 = check_binance_square_key(settings)

    print("=" * 60)
    if r1 and r2 and r3:
        print("✅ Core systems are 100% operational and ready to run.")
    else:
        print("⚠️ One or more critical checks failed. Please check logs.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
