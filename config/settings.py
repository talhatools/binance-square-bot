"""Application configuration and environment settings."""
import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Base directory of the repository
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file from root if present
load_dotenv(BASE_DIR / ".env")


def get_bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


def get_int_env(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return int(val.strip())
    except ValueError:
        return default


def get_float_env(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return float(val.strip())
    except ValueError:
        return default


@dataclass
class Settings:
    # Environment & Paths
    base_dir: Path = BASE_DIR
    data_dir: Path = field(default_factory=lambda: BASE_DIR / "data")
    logs_dir: Path = field(default_factory=lambda: BASE_DIR / "logs")
    charts_dir: Path = field(default_factory=lambda: BASE_DIR / "charts")

    # API Keys (Strictly posting-only for Square OpenAPI)
    square_openapi_key: str = field(
        default_factory=lambda: os.getenv("BINANCE_SQUARE_OPENAPI_KEY", "").strip()
    )
    anthropic_api_key: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "").strip()
    )
    anthropic_model: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022").strip()
    )
    disable_claude_api: bool = field(
        default_factory=lambda: get_bool_env("DISABLE_CLAUDE_API", default=True)
    )

    # Operational Controls
    dry_run: bool = field(
        default_factory=lambda: get_bool_env("DRY_RUN", default=True)
    )
    post_interval_minutes: int = field(
        default_factory=lambda: get_int_env("POST_INTERVAL_MINUTES", 30)
    )
    min_24h_quote_volume: float = field(
        default_factory=lambda: get_float_env("MIN_24H_QUOTE_VOLUME", 10_000_000.0)
    )
    cooldown_hours: float = field(
        default_factory=lambda: get_float_env("COOLDOWN_HOURS", 6.0)
    )
    daily_post_limit: int = field(
        default_factory=lambda: get_int_env("DAILY_POST_LIMIT", 100)
    )
    max_retries: int = field(
        default_factory=lambda: get_int_env("MAX_RETRIES", 3)
    )
    retry_delay_base: float = field(
        default_factory=lambda: get_float_env("RETRY_DELAY_BASE", 2.0)
    )

    # Watermark & Visuals
    watermark_text: str = field(
        default_factory=lambda: os.getenv("WATERMARK_TEXT", "Talha Sniper").strip()
    )
    chart_style: str = field(
        default_factory=lambda: os.getenv("CHART_STYLE", "both").strip().lower()
    )

    # Notifications & Alerts (Discord/Slack Webhook or Telegram Bot)
    webhook_url: str = field(
        default_factory=lambda: os.getenv("ALERT_WEBHOOK_URL", "").strip()
    )
    telegram_bot_token: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    )
    telegram_chat_id: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", "").strip()
    )

    # Logging
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").strip().upper()
    )

    # Database
    db_path: Path = field(
        default_factory=lambda: BASE_DIR / "data" / "square_bot.db"
    )

    def __post_init__(self):
        # Auto-create necessary directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.charts_dir.mkdir(parents=True, exist_ok=True)


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
