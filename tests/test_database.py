"""Unit tests for SQLite database operations and cooldown deduplication."""
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from src.database import Database


def test_database_init_and_cooldown():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        db = Database(db_path)

        # Initially no cooldown
        assert db.is_coin_on_cooldown("SOLUSDT", cooldown_hours=6.0) is False

        # Record a post
        db.record_post(
            coin="SOLUSDT",
            direction="LONG",
            entry_price=150.0,
            target_price=165.0,
            stop_loss=142.0,
            post_text="Test post",
            post_id="test_123",
            share_link="https://binance.com/square/post/123",
            chart_path=None,
            status="PUBLISHED",
        )

        # Now SOLUSDT should be on cooldown
        assert db.is_coin_on_cooldown("SOLUSDT", cooldown_hours=6.0) is True
        # Other coin should NOT be on cooldown
        assert db.is_coin_on_cooldown("BTCUSDT", cooldown_hours=6.0) is False

        # Old post beyond cooldown
        old_time = datetime.now(timezone.utc) - timedelta(hours=7)
        db.record_post(
            coin="ETHUSDT",
            direction="SHORT",
            entry_price=2600.0,
            target_price=2400.0,
            stop_loss=2700.0,
            post_text="Old post",
            post_id="old_123",
            share_link=None,
            chart_path=None,
            status="PUBLISHED",
            created_at=old_time,
        )
        assert db.is_coin_on_cooldown("ETHUSDT", cooldown_hours=6.0) is False


def test_daily_counts_and_summary():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        db = Database(db_path)

        # Record 2 published posts, 1 dry run
        db.record_post("BTCUSDT", "LONG", 60000, 63000, 58500, "Text 1", "p1", None, None, "PUBLISHED")
        db.record_post("BNBUSDT", "SHORT", 580, 550, 595, "Text 2", "p2", None, None, "PUBLISHED")
        db.record_post("AVAXUSDT", "LONG", 30, 33, 28, "Text 3", "p3", None, None, "DRY_RUN")

        count = db.get_daily_post_count()
        assert count == 2

        summary = db.get_daily_summary()
        assert summary["total_attempts"] == 3
        assert summary["published_count"] == 2
        assert summary["dry_run_count"] == 1
        assert summary["long_count"] == 1
        assert summary["short_count"] == 1


def test_signal_tracking():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        db = Database(db_path)

        post_id = db.record_post(
            "ADAUSDT", "LONG", 0.35, 0.40, 0.32, "Text ADA", "p_ada", None, None, "PUBLISHED"
        )
        pending = db.get_pending_signals()
        assert len(pending) == 1
        assert pending[0]["id"] == post_id
        assert pending[0]["result"] == "PENDING"

        # Update resolution
        now = datetime.now(timezone.utc)
        db.update_signal_result(post_id, "TARGET_HIT", now, 14.28)

        pending_after = db.get_pending_signals()
        assert len(pending_after) == 0

        recent = db.get_recent_posts(limit=1)
        assert recent[0]["result"] == "TARGET_HIT"
        assert recent[0]["pnl_percent"] == 14.28
