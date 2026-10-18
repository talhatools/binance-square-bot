"""Main CLI Entrypoint: Configures logging, CLI commands, and APScheduler."""
import os
import sys
import argparse
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from config.settings import get_settings
from src.bot import PostingBot
from src.performance_tracker import PerformanceTracker
from src.database import Database
from src.notifier import Notifier


def setup_logging(logs_dir, log_level: str = "INFO"):
    """Sets up unified console and rotating file logging."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "square_bot.log"

    level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Ensure UTF-8 console output
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    # Rotating File Handler (10MB max, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Silence chatty third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)


def print_daily_summary(settings):
    """Outputs today's posts summary to console and notifier."""
    db = Database(settings.db_path)
    notifier = Notifier(settings.webhook_url)
    summary = db.get_daily_summary()

    print("\n" + "=" * 50)
    print(f"📊 BINANCE SQUARE BOT - DAILY SUMMARY ({summary.get('date')})")
    print("=" * 50)
    print(f"Total Attempts : {summary.get('total_attempts', 0)}")
    print(f"Published Posts: {summary.get('published_count', 0)}")
    print(f"Dry Run Posts  : {summary.get('dry_run_count', 0)}")
    print(f"Failed Posts   : {summary.get('failed_count', 0)}")
    print(f"Long Setups    : {summary.get('long_count', 0)}")
    print(f"Short Setups   : {summary.get('short_count', 0)}")
    print("-" * 50)

    posts = summary.get("posts", [])
    if posts:
        print("Coins Handled Today:")
        for p in posts:
            print(f"  • {p['coin']:<10} | {p['direction']:<5} | Status: {p['status']:<10} | {p['created_at']}")
    else:
        print("No posts recorded yet today.")
    print("=" * 50 + "\n")

    notifier.notify_daily_summary(summary)


def main():
    parser = argparse.ArgumentParser(
        description="Automated Binance Square Posting Bot - Talha Sniper"
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Execute a single cycle immediately and exit (useful for cron/testing).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Force simulation mode (no live publishing to Binance Square).",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Display and send today's posting summary report and exit.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Display historical accuracy, win-rate, and realized PnL metrics.",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Display the most recent post history with trade setups and outcomes.",
    )
    parser.add_argument(
        "--track-signals",
        action="store_true",
        help="Evaluate pending signals against market prices (TP / SL hit) and exit.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Posting interval in minutes (e.g. 15, 30, 60). Overrides .env setting.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force immediate post generation by bypassing coin cooldown.",
    )
    parser.add_argument(
        "--chart-style",
        choices=["both", "binance", "tradingview", "binance_app"],
        default=None,
        help="Chart visual style: 'binance' (Competitor App style), 'tradingview' (Pro dark style), or 'both' (alternating).",
    )
    args = parser.parse_args()

    settings = get_settings()
    if args.chart_style:
        settings.chart_style = args.chart_style

    if args.dry_run:
        settings.dry_run = True

    if args.interval and args.interval > 0:
        settings.post_interval_minutes = args.interval

    setup_logging(settings.logs_dir, settings.log_level)
    logger = logging.getLogger("main")

    logger.info("Initializing Binance Square Posting Bot...")
    bot = PostingBot(settings)
    tracker = PerformanceTracker(bot.client, bot.db)

    # 1. Summary mode
    if args.summary:
        print_daily_summary(settings)
        return

    # 2. Stats mode
    if args.stats:
        stats = bot.db.get_accuracy_stats()
        print("\n" + "=" * 55)
        print("🎯 BINANCE SQUARE BOT - HISTORICAL ACCURACY STATS")
        print("=" * 55)
        print(f"Total Signals Recorded : {stats.get('total_signals', 0)}")
        print(f"Resolved Signals       : {stats.get('resolved_signals', 0)}")
        print(f"Target Hits (TP)       : {stats.get('target_hits', 0)}")
        print(f"Stop-Loss Hits (SL)    : {stats.get('stop_hits', 0)}")
        print(f"Pending Active Signals : {stats.get('pending_count', 0)}")
        print(f"Win Rate %             : {stats.get('win_rate_percent', 0.0)}%")
        print(f"Avg PnL per Trade      : {stats.get('avg_pnl', 0.0):+.2f}%")
        print(f"Total Realized PnL     : {stats.get('total_pnl', 0.0):+.2f}%")
        print("=" * 55 + "\n")
        return

    # 3. History mode
    if args.history:
        recent = bot.db.get_recent_posts(limit=15)
        print("\n" + "=" * 80)
        print("📜 RECENT POSTING HISTORY & SIGNAL OUTCOMES")
        print("=" * 80)
        header = f"{'ID':<4} | {'COIN':<9} | {'BIAS':<5} | {'ENTRY':<9} | {'TP':<9} | {'SL':<9} | {'OUTCOME':<10} | {'PNL %':<7} | {'STATUS'}"
        print(header)
        print("-" * 80)
        for p in recent:
            pnl_str = f"{p['pnl_percent']:+.1f}%" if p['pnl_percent'] is not None else "--"
            print(
                f"{p['id']:<4} | {p['coin']:<9} | {p['direction']:<5} | {p['entry_price']:<9.4f} | "
                f"{p['target_price']:<9.4f} | {p['stop_loss']:<9.4f} | {p['result']:<10} | {pnl_str:<7} | {p['status']}"
            )
        print("=" * 80 + "\n")
        return

    # 4. Track signals mode
    if args.track_signals:
        resolved = tracker.evaluate_pending_signals()
        print(f"Evaluated signals: {resolved} resolved.")
        return

    # 3. Run-once mode
    if args.run_once:
        logger.info(f"Executing single posting cycle (--run-once, force={args.force})...")
        result = bot.run_cycle(force=args.force)
        tracker.evaluate_pending_signals()
        if result:
            print(f"\nCompleted cycle for {result['coin']} [{result['direction']}]. Status: {result['status']}")
            print(f"Post text:\n{result['text']}\n")
        else:
            print("\nCycle finished with no post generated (market criteria not met or cooldown active).")
        return

    # 4. Continuous Scheduled Service Mode (APScheduler)
    interval_mins = settings.post_interval_minutes
    logger.info(f"Starting scheduler. Posting cycle will run every {interval_mins} minutes.")

    scheduler = BlockingScheduler()

    # Job 1: Main posting pipeline every 30 minutes
    scheduler.add_job(
        bot.run_cycle,
        trigger=IntervalTrigger(minutes=interval_mins),
        id="square_posting_cycle",
        name="Binance Square 30-Minute Posting Job",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    # Job 2: Performance accuracy tracker every 15 minutes
    scheduler.add_job(
        tracker.evaluate_pending_signals,
        trigger=IntervalTrigger(minutes=15),
        id="signal_performance_tracker",
        name="Signal TP/SL Accuracy Tracker",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    # Job 3: Daily summary at 23:55 UTC
    scheduler.add_job(
        lambda: print_daily_summary(settings),
        trigger=CronTrigger(hour=23, minute=55, timezone="UTC"),
        id="daily_posting_summary",
        name="Daily Midnight Posting Summary",
        max_instances=1,
        misfire_grace_time=3600,
    )

    # Execute first cycle immediately upon startup
    logger.info("Triggering initial cycle on startup...")
    try:
        bot.run_cycle()
    except Exception as exc:
        logger.error(f"Error during initial startup cycle: {exc}", exc_info=True)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot shutting down gracefully.")


if __name__ == "__main__":
    main()
