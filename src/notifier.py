"""Alert Notifier: Sends critical alerts and daily performance summaries."""
import logging
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(
        self,
        webhook_url: Optional[str] = None,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
    ):
        self.webhook_url = webhook_url
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id

    def send_alert(self, title: str, message: str, level: str = "WARNING") -> bool:
        """
        Logs alert and sends webhook notification (Discord/Slack)
        and/or Telegram notification if configured.
        """
        log_msg = f"[ALERT - {level}] {title}: {message}"
        if level in ("CRITICAL", "ERROR"):
            logger.critical(log_msg)
        else:
            logger.warning(log_msg)

        delivered = False

        # 1. Discord / Slack Webhook
        if self.webhook_url:
            try:
                payload = {
                    "content": f"🚨 **{title}** [{level}]\n{message}",
                    "text": f"🚨 *{title}* [{level}]\n{message}",
                }
                res = requests.post(self.webhook_url, json=payload, timeout=8)
                if res.ok:
                    delivered = True
            except Exception as exc:
                logger.error(f"Failed to send webhook alert: {exc}")

        # 2. Telegram Bot
        if self.telegram_bot_token and self.telegram_chat_id:
            try:
                tg_url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
                tg_payload = {
                    "chat_id": self.telegram_chat_id,
                    "text": f"🚨 *{title}* [{level}]\n\n{message}",
                    "parse_mode": "Markdown",
                }
                tg_res = requests.post(tg_url, json=tg_payload, timeout=8)
                if tg_res.ok:
                    delivered = True
            except Exception as exc:
                logger.error(f"Failed to send Telegram alert: {exc}")

        return delivered

    def notify_critical_error(self, code: str, detail: str) -> None:
        """Handles specific Binance Square OpenAPI error codes."""
        if code == "220003":
            self.send_alert(
                "Square API Key Not Found (220003)",
                f"The provided Binance Square OpenAPI key was rejected.\nDetail: {detail}",
                level="CRITICAL",
            )
        elif code == "220004":
            self.send_alert(
                "Square API Key Expired (220004)",
                f"The Binance Square OpenAPI key has expired.\nDetail: {detail}",
                level="CRITICAL",
            )
        elif code == "220009":
            self.send_alert(
                "Square Daily Post Limit Hit (220009)",
                "You reached the 100 posts/day limit on Binance Square. Bot pausing posts until reset.",
                level="WARNING",
            )
        else:
            self.send_alert(f"Square API Error ({code})", detail, level="ERROR")

    def notify_daily_summary(self, summary: Dict[str, Any]) -> None:
        """Sends daily posting summary."""
        date_str = summary.get("date", "Today")
        published = summary.get("published_count", 0)
        dry_runs = summary.get("dry_run_count", 0)
        longs = summary.get("long_count", 0)
        shorts = summary.get("short_count", 0)

        msg = (
            f"📅 Date: {date_str}\n"
            f"✅ Published: {published}\n"
            f"🧪 Dry Runs: {dry_runs}\n"
            f"📈 Longs: {longs} | 📉 Shorts: {shorts}"
        )
        self.send_alert("Daily Binance Square Summary", msg, level="INFO")
