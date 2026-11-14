"""Interactive client setup wizard for Binance Square Automated Posting Bot."""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
ENV_EXAMPLE = BASE_DIR / ".env.example"


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    print("=" * 65)
    print("  🚀 BINANCE SQUARE AUTOMATED POSTING BOT - CLIENT SETUP WIZARD")
    print("=" * 65)
    print("This setup wizard will configure your bot in 1 minute.")
    print("No coding knowledge required!\n")


def prompt_input(prompt_text: str, default: str = "", required: bool = False) -> str:
    while True:
        default_str = f" [{default}]" if default else ""
        try:
            val = input(f"{prompt_text}{default_str}: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSetup cancelled.")
            sys.exit(0)

        if not val and default:
            return default
        if val:
            return val
        if not required:
            return ""
        print("❌ This field is required. Please enter a valid value.\n")


def load_existing_env() -> dict:
    env_vars = {}
    source_file = ENV_FILE if ENV_FILE.exists() else ENV_EXAMPLE
    if source_file.exists():
        with open(source_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    env_vars[key.strip()] = value.strip()
    return env_vars


def save_env(config: dict):
    env_content = f"""# ==============================================================================
# Binance Square Automated Posting Bot - Configuration (.env)
# ==============================================================================

# 1. API Keys
BINANCE_SQUARE_OPENAPI_KEY={config.get('BINANCE_SQUARE_OPENAPI_KEY', '')}
DISABLE_CLAUDE_API=true
ANTHROPIC_API_KEY=

# 2. Operational Controls
DRY_RUN={config.get('DRY_RUN', 'false')}
POST_INTERVAL_MINUTES={config.get('POST_INTERVAL_MINUTES', '30')}
MIN_24H_QUOTE_VOLUME=25000000
COOLDOWN_HOURS={config.get('COOLDOWN_HOURS', '3')}
DAILY_POST_LIMIT=100
MAX_RETRIES=3
RETRY_DELAY_BASE=2.0

# 3. Branding & Visuals
WATERMARK_TEXT={config.get('WATERMARK_TEXT', 'Crypto Trader')}
CHART_STYLE={config.get('CHART_STYLE', 'both')}

# 4. Optional Notifications (Telegram Alerts)
ALERT_WEBHOOK_URL=
TELEGRAM_BOT_TOKEN={config.get('TELEGRAM_BOT_TOKEN', '')}
TELEGRAM_CHAT_ID={config.get('TELEGRAM_CHAT_ID', '')}
LOG_LEVEL=INFO
"""
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(env_content)


def main():
    clear_screen()
    print_banner()

    existing = load_existing_env()

    # Step 1: Binance Square OpenAPI Key
    print("-----------------------------------------------------------------")
    print("📌 STEP 1: Binance Square OpenAPI Key")
    print("Get your key from: Binance.com -> Square -> Creator Center -> OpenAPI")
    print("-----------------------------------------------------------------")
    existing_key = existing.get("BINANCE_SQUARE_OPENAPI_KEY", "")
    if existing_key and existing_key != "your_binance_square_openapi_key_here":
        masked_key = existing_key[:6] + "..." + existing_key[-4:]
        print(f"Current saved key: {masked_key}")
        change_key = prompt_input("Keep existing key? (Y/n)", default="y").lower()
        if change_key == "y":
            api_key = existing_key
        else:
            api_key = prompt_input("Enter your Binance Square OpenAPI Key", required=True)
    else:
        api_key = prompt_input("Enter your Binance Square OpenAPI Key", required=True)

    print("\n-----------------------------------------------------------------")
    print("📌 STEP 2: Branding & Watermark")
    print("Your profile/channel name displayed on all generated charts.")
    print("-----------------------------------------------------------------")
    curr_watermark = existing.get("WATERMARK_TEXT", "Crypto Trader")
    if curr_watermark == "your_channel_or_brand_name":
        curr_watermark = "Crypto Trader"
    watermark = prompt_input("Enter your Brand / Channel Name", default=curr_watermark, required=True)

    print("\n-----------------------------------------------------------------")
    print("📌 STEP 3: Chart Visual Style")
    print("Choose how trade setup charts will look:")
    print("  [1] Both / Alternate (Mix of TradingView Pro & Binance Mobile) [Recommended]")
    print("  [2] TradingView Pro Dark Style only")
    print("  [3] Binance Competitor Mobile App Style only")
    print("-----------------------------------------------------------------")
    style_choice = prompt_input("Select Chart Style [1, 2, or 3]", default="1")
    if style_choice == "2":
        chart_style = "tradingview"
    elif style_choice == "3":
        chart_style = "binance"
    else:
        chart_style = "both"

    print("\n-----------------------------------------------------------------")
    print("📌 STEP 4: Posting Interval")
    print("How often should the bot scan the market and publish a new post?")
    print("  [1] Every 15 Minutes (Maximum Growth - Recommended)")
    print("  [2] Every 30 Minutes (Standard)")
    print("  [3] Every 60 Minutes (1 Hour)")
    print("-----------------------------------------------------------------")
    interval_choice = prompt_input("Select Interval [1, 2, or 3]", default="1")
    if interval_choice == "2":
        post_interval = "30"
    elif interval_choice == "3":
        post_interval = "60"
    else:
        post_interval = "15"

    print("\n-----------------------------------------------------------------")
    print("📌 STEP 5: Operational Mode")
    print("  [1] LIVE POSTING (Publishes real posts to your Binance Square profile)")
    print("  [2] SIMULATION / DRY-RUN (Generates charts & text without publishing)")
    print("-----------------------------------------------------------------")
    mode_choice = prompt_input("Select Mode [1 or 2]", default="1")
    dry_run = "false" if mode_choice == "1" else "true"

    print("\n-----------------------------------------------------------------")
    print("📌 STEP 6 (Optional): Telegram Alerts")
    print("Receive instant notifications on your phone whenever the bot posts.")
    print("Press ENTER to skip if you do not want Telegram alerts.")
    print("-----------------------------------------------------------------")
    tg_token = prompt_input("Telegram Bot Token (optional)", default=existing.get("TELEGRAM_BOT_TOKEN", ""))
    tg_chat = prompt_input("Telegram Chat ID (optional)", default=existing.get("TELEGRAM_CHAT_ID", ""))

    # Save to .env
    config = {
        "BINANCE_SQUARE_OPENAPI_KEY": api_key,
        "WATERMARK_TEXT": watermark,
        "CHART_STYLE": chart_style,
        "POST_INTERVAL_MINUTES": post_interval,
        "COOLDOWN_HOURS": "3",
        "DRY_RUN": dry_run,
        "TELEGRAM_BOT_TOKEN": tg_token,
        "TELEGRAM_CHAT_ID": tg_chat,
    }
    save_env(config)

    print("\n" + "=" * 65)
    print("✅ Configuration saved successfully to .env!")
    print("=" * 65)
    print(f"  • Brand Watermark : {watermark}")
    print(f"  • Chart Style     : {chart_style.upper()}")
    print(f"  • Posting Interval: Every {post_interval} minutes")
    print(f"  • Mode            : {'LIVE POSTING' if dry_run == 'false' else 'SIMULATION (DRY-RUN)'}")
    if tg_token and tg_chat:
        print("  • Telegram Alerts : ENABLED")
    else:
        print("  • Telegram Alerts : DISABLED (Optional)")
    print("=" * 65)

    # Test Binance market connection
    print("\nTesting Binance public market API connection...")
    try:
        from src.binance_client import BinanceClient
        client = BinanceClient()
        tickers = client.get_24h_tickers()
        print(f"✅ Binance Market Connection: SUCCESS! ({len(tickers)} pairs active)")
    except Exception as exc:
        print(f"⚠️ Note: Could not reach Binance API directly: {exc}")

    print("\n🎉 SETUP IS COMPLETE! YOU ARE READY TO START POSTING:")
    print("  👉 Double-click 'run.bat'       -> To publish 1 post right now!")
    print("  👉 Double-click 'start_bot.bat' -> To start 24/7 automated posting!")
    print("  👉 Double-click 'check_stats.bat' -> To view win-rate & trade history!")
    print("=" * 65 + "\n")

    input("Press ENTER to exit wizard...")


if __name__ == "__main__":
    main()
