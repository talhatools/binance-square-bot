"""Signal Performance Tracker: Evaluates open signals against Binance market price data."""
import logging
from datetime import datetime, timezone
import pandas as pd
from src.binance_client import BinanceClient
from src.database import Database

logger = logging.getLogger(__name__)


class PerformanceTracker:
    def __init__(self, binance_client: BinanceClient, database: Database):
        self.client = binance_client
        self.db = database

    def evaluate_pending_signals(self) -> int:
        """
        Retrieves pending signals from SQLite and checks subsequent candles
        to see if the target was hit or the stop-loss was triggered.
        Returns the number of resolved signals.
        """
        pending = self.db.get_pending_signals(max_age_days=7)
        if not pending:
            logger.debug("No pending signals to evaluate.")
            return 0

        logger.info(f"Evaluating {len(pending)} pending signal(s)...")
        resolved_count = 0

        for sig in pending:
            sig_id = sig["id"]
            coin = sig["coin"]
            direction = sig["direction"]
            entry = sig["entry_price"]
            target = sig["target_price"]
            stop = sig["stop_loss"]
            created_at_str = sig["created_at"]

            try:
                # Fetch recent 1h candles
                df = self.client.get_klines(coin, interval="1h", limit=120)
                # Filter candles after signal creation time
                created_dt = pd.to_datetime(created_at_str)
                df_after = df[df.index >= created_dt]

                if df_after.empty:
                    continue

                result = "PENDING"
                pnl = 0.0
                closed_at = datetime.now(timezone.utc)

                # Iterate chronologically to see which level was hit first
                for candle_time, row in df_after.iterrows():
                    high = row["high"]
                    low = row["low"]

                    if direction == "LONG":
                        # Check Target Hit first
                        if high >= target:
                            result = "TARGET_HIT"
                            pnl = round(((target - entry) / entry) * 100.0, 2)
                            closed_at = candle_time.to_pydatetime()
                            break
                        # Check Stop Hit
                        elif low <= stop:
                            result = "STOP_HIT"
                            pnl = round(((stop - entry) / entry) * 100.0, 2)
                            closed_at = candle_time.to_pydatetime()
                            break

                    elif direction == "SHORT":
                        # Check Target Hit first
                        if low <= target:
                            result = "TARGET_HIT"
                            pnl = round(((entry - target) / entry) * 100.0, 2)
                            closed_at = candle_time.to_pydatetime()
                            break
                        # Check Stop Hit
                        elif high >= stop:
                            result = "STOP_HIT"
                            pnl = round(((entry - stop) / entry) * 100.0, 2)
                            closed_at = candle_time.to_pydatetime()
                            break

                if result in ("TARGET_HIT", "STOP_HIT"):
                    logger.info(
                        f"Signal #{sig_id} for {coin} ({direction}) RESOLVED: {result} "
                        f"PnL: {pnl:+.2f}% at {closed_at}"
                    )
                    self.db.update_signal_result(sig_id, result, closed_at, pnl)
                    resolved_count += 1

            except Exception as exc:
                logger.warning(f"Error evaluating signal #{sig_id} for {coin}: {exc}")
                continue

        return resolved_count
