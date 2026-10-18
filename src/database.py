"""SQLite state management for posts history, cooldown deduplication, and signal tracking."""
import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Generator

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Creates tables and indexes if they do not exist."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    coin TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    target_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    risk_reward REAL,
                    post_text TEXT NOT NULL,
                    post_id TEXT,
                    share_link TEXT,
                    chart_path TEXT,
                    status TEXT NOT NULL,  -- PUBLISHED, DRY_RUN, FAILED
                    result TEXT DEFAULT 'PENDING',  -- PENDING, TARGET_HIT, STOP_HIT, EXPIRED
                    closed_at TEXT,
                    pnl_percent REAL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_posts_coin_created 
                ON posts(coin, created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_posts_created 
                ON posts(created_at)
            """)
            conn.commit()

    def is_coin_on_cooldown(self, coin: str, cooldown_hours: float = 6.0) -> bool:
        """Check if this coin was already posted within the last N hours."""
        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)
        cutoff_str = cutoff_dt.isoformat()

        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, coin, created_at FROM posts 
                WHERE coin = ? 
                  AND created_at >= ?
                  AND status IN ('PUBLISHED', 'DRY_RUN')
                ORDER BY created_at DESC 
                LIMIT 1
                """,
                (coin.upper(), cutoff_str),
            )
            row = cursor.fetchone()
            if row:
                logger.info(
                    f"Coin {coin} is on cooldown. Last posted at {row['created_at']} (Cooldown: {cooldown_hours}h)"
                )
                return True
            return False

    def get_daily_post_count(self, target_date: Optional[datetime] = None) -> int:
        """Get the number of successful posts published on the given UTC date."""
        if target_date is None:
            target_date = datetime.now(timezone.utc)
        day_prefix = target_date.strftime("%Y-%m-%d")

        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) as cnt FROM posts 
                WHERE created_at LIKE ?
                  AND status = 'PUBLISHED'
                """,
                (f"{day_prefix}%",),
            )
            row = cursor.fetchone()
            return row["cnt"] if row else 0

    def record_post(
        self,
        coin: str,
        direction: str,
        entry_price: float,
        target_price: float,
        stop_loss: float,
        post_text: str,
        post_id: Optional[str],
        share_link: Optional[str],
        chart_path: Optional[str],
        status: str = "PUBLISHED",
        risk_reward: Optional[float] = None,
        created_at: Optional[datetime] = None,
    ) -> int:
        """Save a new post entry in the database."""
        if created_at is None:
            created_at = datetime.now(timezone.utc)
        created_str = created_at.isoformat()

        if risk_reward is None and entry_price and stop_loss:
            risk = abs(entry_price - stop_loss)
            reward = abs(target_price - entry_price)
            risk_reward = round(reward / risk, 2) if risk > 0 else 0.0

        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO posts (
                    coin, direction, entry_price, target_price, stop_loss,
                    risk_reward, post_text, post_id, share_link, chart_path,
                    status, result, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
                """,
                (
                    coin.upper(),
                    direction.upper(),
                    entry_price,
                    target_price,
                    stop_loss,
                    risk_reward,
                    post_text,
                    post_id,
                    share_link,
                    str(chart_path) if chart_path else None,
                    status,
                    created_str,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_recent_posts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch the most recent posts."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM posts 
                ORDER BY created_at DESC 
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_daily_summary(self, target_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Aggregate performance and counts for a specific day."""
        if target_date is None:
            target_date = datetime.now(timezone.utc)
        day_prefix = target_date.strftime("%Y-%m-%d")

        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    COUNT(*) as total_attempts,
                    SUM(CASE WHEN status = 'PUBLISHED' THEN 1 ELSE 0 END) as published_count,
                    SUM(CASE WHEN status = 'DRY_RUN' THEN 1 ELSE 0 END) as dry_run_count,
                    SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_count,
                    SUM(CASE WHEN direction = 'LONG' AND status = 'PUBLISHED' THEN 1 ELSE 0 END) as long_count,
                    SUM(CASE WHEN direction = 'SHORT' AND status = 'PUBLISHED' THEN 1 ELSE 0 END) as short_count
                FROM posts 
                WHERE created_at LIKE ?
                """,
                (f"{day_prefix}%",),
            )
            row = cursor.fetchone()
            summary = dict(row) if row else {}
            summary["date"] = day_prefix

            cursor.execute(
                """
                SELECT DISTINCT coin, direction, status, created_at 
                FROM posts 
                WHERE created_at LIKE ?
                ORDER BY created_at ASC
                """,
                (f"{day_prefix}%",),
            )
            summary["posts"] = [dict(r) for r in cursor.fetchall()]
            return summary

    def get_pending_signals(self, max_age_days: int = 7) -> List[Dict[str, Any]]:
        """Fetch open signals to check whether Target or Stop Loss has been triggered."""
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM posts 
                WHERE result = 'PENDING' 
                  AND status IN ('PUBLISHED', 'DRY_RUN')
                  AND created_at >= ?
                ORDER BY created_at ASC
                """,
                (cutoff_dt.isoformat(),),
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_signal_result(
        self, post_id: int, result: str, closed_at: datetime, pnl_percent: float
    ) -> None:
        """Update the evaluated result of a signal."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE posts 
                SET result = ?, closed_at = ?, pnl_percent = ?
                WHERE id = ?
                """,
                (result, closed_at.isoformat(), pnl_percent, post_id),
            )
            conn.commit()

    def get_accuracy_stats(self) -> Dict[str, Any]:
        """Calculates historical hit-rate and performance metrics."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_signals,
                    SUM(CASE WHEN result = 'TARGET_HIT' THEN 1 ELSE 0 END) as target_hits,
                    SUM(CASE WHEN result = 'STOP_HIT' THEN 1 ELSE 0 END) as stop_hits,
                    SUM(CASE WHEN result = 'PENDING' THEN 1 ELSE 0 END) as pending_count,
                    SUM(CASE WHEN result = 'EXPIRED' THEN 1 ELSE 0 END) as expired_count,
                    AVG(CASE WHEN result IN ('TARGET_HIT', 'STOP_HIT') THEN pnl_percent ELSE NULL END) as avg_pnl,
                    SUM(CASE WHEN result IN ('TARGET_HIT', 'STOP_HIT') THEN pnl_percent ELSE 0.0 END) as total_pnl
                FROM posts
                WHERE status IN ('PUBLISHED', 'DRY_RUN')
            """)
            row = cursor.fetchone()
            stats = dict(row) if row else {}

            total_hits = (stats.get("target_hits") or 0)
            total_stops = (stats.get("stop_hits") or 0)
            resolved = total_hits + total_stops

            win_rate = round((total_hits / resolved) * 100.0, 1) if resolved > 0 else 0.0
            stats["win_rate_percent"] = win_rate
            stats["resolved_signals"] = resolved
            stats["avg_pnl"] = round(stats.get("avg_pnl") or 0.0, 2)
            stats["total_pnl"] = round(stats.get("total_pnl") or 0.0, 2)
            return stats


