"""Bot Orchestrator: Executes the end-to-end 30-minute scanning and posting pipeline."""
import logging
from typing import Optional, Dict, Any
from config.settings import Settings
from src.binance_client import BinanceClient
from src.database import Database
from src.market_scanner import MarketScanner
from src.technical_analysis import TechnicalAnalyzer
from src.chart_generator import ChartGenerator
from src.ai_writer import AIWriter
from src.square_publisher import SquarePublisher, SquareAPIError
from src.notifier import Notifier

logger = logging.getLogger(__name__)


class PostingBot:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = Database(settings.db_path)
        self.client = BinanceClient(
            max_retries=settings.max_retries,
            retry_delay_base=settings.retry_delay_base,
        )
        self.scanner = MarketScanner(self.client, self.db)
        self.analyzer = TechnicalAnalyzer()
        self.chart_gen = ChartGenerator(
            output_dir=settings.charts_dir,
            watermark_text=settings.watermark_text,
            default_style=getattr(settings, "chart_style", "both"),
        )
        self.ai_writer = AIWriter(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            max_retries=settings.max_retries,
            retry_delay_base=settings.retry_delay_base,
            disable_api=settings.disable_claude_api,
        )
        self.publisher = SquarePublisher(
            api_key=settings.square_openapi_key,
            dry_run=settings.dry_run,
            max_retries=settings.max_retries,
            retry_delay_base=settings.retry_delay_base,
        )
        self.notifier = Notifier(
            webhook_url=settings.webhook_url,
            telegram_bot_token=settings.telegram_bot_token,
            telegram_chat_id=settings.telegram_chat_id,
        )

    def _resolve_binance_symbol(self, symbol: str) -> Optional[str]:
        """
        Validates that a USDT symbol exists on Binance Spot or Futures.
        Tries exact match first, then '1000X' prefix variant (for meme coins like SHIB, PEPE, FLOKI).
        Returns the correct symbol string, or None if not found anywhere.
        """
        try:
            all_tickers = self.client.get_24h_tickers()
            valid_symbols = {t["symbol"] for t in all_tickers}

            # 1. Exact match on Spot (e.g. BTCUSDT, ETHUSDT, SOLUSDT)
            if symbol in valid_symbols:
                return symbol

            # 2. Try 1000X prefix variant on Spot (e.g. SHIBUSDT -> 1000SHIBUSDT)
            base = symbol[:-4]  # strip USDT
            alt_symbol = f"1000{base}USDT"
            if alt_symbol in valid_symbols:
                logger.info(f"Coin resolved: {symbol} -> {alt_symbol} (Binance 1000x prefix)")
                return alt_symbol

            # 3. Try Futures exchange info (coins like BTW may only be on Futures/Perp)
            try:
                orig_urls = self.client.base_urls
                self.client.base_urls = ["https://fapi.binance.com"]
                futures_info = self.client._request("/fapi/v1/exchangeInfo", timeout=15.0)
                self.client.base_urls = orig_urls
                futures_symbols = {s["symbol"] for s in futures_info.get("symbols", [])}
                if symbol in futures_symbols:
                    logger.info(f"Coin {symbol} found on Futures (not Spot) — using Futures data.")
                    return symbol
                if alt_symbol in futures_symbols:
                    logger.info(f"Coin resolved on Futures: {symbol} -> {alt_symbol}")
                    return alt_symbol
            except Exception as fe:
                self.client.base_urls = orig_urls
                logger.warning(f"Could not check Futures exchange info: {fe}")

            # 4. Not found anywhere — return as-is and let it fail with clear error
            logger.warning(
                f"'{symbol}' not found on Binance Spot or Futures. "
                f"Check exact ticker at binance.com/trade"
            )
            # Return symbol anyway — klines fetch will give the actual error
            return symbol

        except Exception as exc:
            logger.warning(f"Could not validate symbol {symbol} against Binance: {exc}")
            return symbol

    def run_cycle(self, force: bool = False, coin: str = None) -> Optional[Dict[str, Any]]:
        """
        Executes one full iteration of the automated posting pipeline:
        1. Enforces daily posting limit (max 100/day).
        2. Scans Binance market & scores coins (skips cooldown coins unless force=True).
           OR uses a specific coin if provided via --coin argument.
        3. Fetches 1h & 4h klines and performs rule-based technical analysis.
        4. Validates setup direction: skips if NO_TRADE.
        5. Generates dark-theme candlestick chart PNG with watermark.
        6. Drafts high-impact post text with varied competitor-style templates.
        7. Publishes to Binance Square via OpenAPI.
        8. Records details and levels to SQLite.
        """
        logger.info("=" * 60)
        logger.info("Starting Automated Binance Square Posting Cycle...")
        logger.info(f"Mode: {'DRY_RUN (Simulation)' if self.settings.dry_run else 'LIVE POSTING'}")
        if coin:
            logger.info(f"Specific Coin Mode: Posting about {coin} (auto-scan skipped).")
        elif force:
            logger.info("Force mode active: ignoring cooldown to prioritize immediate post creation.")

        # 1. Daily Post Limit Check
        daily_count = self.db.get_daily_post_count()
        logger.info(f"Today's Published Posts: {daily_count}/{self.settings.daily_post_limit}")
        if daily_count >= self.settings.daily_post_limit:
            logger.warning(
                f"Daily post limit reached ({daily_count}/{self.settings.daily_post_limit}). "
                "Skipping cycle gracefully to avoid error 220009."
            )
            return None

        # 2. Pick Top Promising Candidates (up to 20-25 candidates across pool)
        cooldown = 0.0 if force else self.settings.cooldown_hours

        if coin:
            # Specific coin mode: skip market scanner, go straight to this coin
            symbol = coin.upper().strip()
            if not symbol.endswith("USDT"):
                symbol = symbol + "USDT"

            # Auto-detect correct Binance symbol (some coins use 1000X prefix e.g. 1000SHIBUSDT)
            symbol = self._resolve_binance_symbol(symbol)
            if not symbol:
                logger.error(
                    f"Coin '{coin}' not found on Binance as a USDT pair. "
                    "Please use exact Binance symbol (e.g. BTC, ETH, SOL, 1000SHIB)."
                )
                return None

            logger.info(f"Specific coin requested: {symbol} — skipping market scan.")
            candidates = [{"symbol": symbol, "score": 100.0, "metrics": {}}]
        else:
            candidates = self.scanner.get_top_candidates(
                min_quote_volume=self.settings.min_24h_quote_volume,
                cooldown_hours=cooldown,
                candidate_pool_limit=75,
                top_n=30,
            )
        if not candidates:
            logger.info("Market Scanner: No eligible coins qualified this cycle. Skipping.")
            return None

        # 3. Evaluate multi-timeframe setups in rank order
        selected_candidate = None
        setup = None

        for candidate in candidates:
            symbol = candidate["symbol"]
            logger.info(f"Evaluating Candidate: {symbol} (Score: {candidate['score']})")

            try:
                df_1h = self.client.get_klines(symbol, interval="1h", limit=100)
                df_4h = self.client.get_klines(symbol, interval="4h", limit=80)
            except Exception as exc:
                logger.warning(f"Failed to fetch klines for {symbol}: {exc}")
                continue

            candidate_setup = self.analyzer.analyze(symbol, df_1h, df_4h)
            logger.info(
                f"Setup for {symbol}: Direction = {candidate_setup.direction} | "
                f"RSI(1h) = {candidate_setup.rsi_1h:.1f} | MA20 = {candidate_setup.ma20_1h:.4f} | R:R = {candidate_setup.risk_reward:.2f}"
            )

            # Specific coin mode: ALWAYS post regardless of direction or R:R
            # Force direction based on RSI if NO_TRADE, then recalculate proper levels
            if coin and candidate_setup.direction != "LONG" and candidate_setup.direction != "SHORT":
                forced_dir = "LONG" if candidate_setup.rsi_1h >= 50 else "SHORT"
                candidate_setup.direction = forced_dir
                logger.info(
                    f"Specific coin mode: direction forced to {forced_dir} "
                    f"(RSI={candidate_setup.rsi_1h:.1f}, R:R was {candidate_setup.risk_reward:.2f})"
                )
                # Recalculate entry/target/stop with relaxed R:R for forced mode
                price = candidate_setup.current_price
                if forced_dir == "LONG":
                    candidate_setup.stop_loss = round(price * 0.97, 6)
                    candidate_setup.target_price = round(price * 1.06, 6)
                else:
                    candidate_setup.stop_loss = round(price * 1.03, 6)
                    candidate_setup.target_price = round(price * 0.94, 6)
                risk = abs(price - candidate_setup.stop_loss)
                reward = abs(candidate_setup.target_price - price)
                candidate_setup.risk_reward = round(reward / risk, 2) if risk > 0 else 2.0
                candidate_setup.reasons = [
                    f"Specific coin requested by user — {forced_dir} bias (RSI: {candidate_setup.rsi_1h:.1f})",
                    "Key levels calculated from current price structure."
                ]

            if candidate_setup.direction in ("LONG", "SHORT"):
                selected_candidate = candidate
                setup = candidate_setup
                logger.info(f"Confirmed valid {setup.direction} setup on {symbol}!")
                break
            else:
                logger.info(f"No clean setup on {symbol}. Checking next candidate...")

        if not setup or not selected_candidate:
            logger.info("No candidates exhibited a confirmed clean trade setup. Skipping cycle.")
            return None

        symbol = setup.coin

        # 5. Generate Candlestick Chart PNG
        try:
            chart_path = self.chart_gen.generate_chart(setup)
            logger.info(f"Chart generated at: {chart_path}")
        except Exception as exc:
            logger.error(f"Failed to generate candlestick chart for {symbol}: {exc}", exc_info=True)
            return None

        # 6. Draft Text with Claude API (or Fallback Template)
        try:
            post_text = self.ai_writer.generate_post_text(setup)
            logger.info(f"Generated Post Content ({len(post_text)} chars):\n{post_text}")
        except Exception as exc:
            logger.error(f"Failed to draft post text for {symbol}: {exc}", exc_info=True)
            return None

        # 7. Publish to Binance Square via OpenAPI
        publish_result = {}
        post_status = "DRY_RUN" if self.settings.dry_run else "PUBLISHED"
        post_id = None
        share_link = None

        try:
            publish_result = self.publisher.publish_post(
                text=post_text,
                image_paths=[chart_path],
            )
            post_id = publish_result.get("id")
            share_link = publish_result.get("shareLink")
            logger.info(f"Square OpenAPI response: ID={post_id}, Link={share_link}")

        except SquareAPIError as err:
            logger.error(f"Binance Square API Error: {err}")
            self.notifier.notify_critical_error(err.code, err.message)
            post_status = "FAILED"
            # If daily limit error (220009), return gracefully
            if err.code == "220009":
                logger.warning("Halting further posts for today due to Square daily limit.")
                return None

        except Exception as exc:
            logger.error(f"Unexpected error publishing to Square OpenAPI: {exc}", exc_info=True)
            self.notifier.send_alert("Publishing Failed", str(exc), level="ERROR")
            post_status = "FAILED"

        # 8. Record to SQLite Database
        db_id = self.db.record_post(
            coin=symbol,
            direction=setup.direction,
            entry_price=setup.current_price,
            target_price=setup.target_price,
            stop_loss=setup.stop_loss,
            post_text=post_text,
            post_id=post_id,
            share_link=share_link,
            chart_path=str(chart_path),
            status=post_status,
            risk_reward=setup.risk_reward,
        )
        logger.info(f"Recorded post entry to database (ID: {db_id}, Status: {post_status})")
        logger.info("Cycle completed successfully.\n")

        return {
            "db_id": db_id,
            "coin": symbol,
            "direction": setup.direction,
            "status": post_status,
            "post_id": post_id,
            "share_link": share_link,
            "chart_path": str(chart_path),
            "text": post_text,
        }
