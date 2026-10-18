"""Binance Public Market Data Client with retry and exponential backoff."""
import time
import logging
from typing import List, Dict, Any, Optional
import requests
import pandas as pd

logger = logging.getLogger(__name__)

# Primary and alternative public endpoints for redundancy
BINANCE_PUBLIC_BASE_URLS = [
    "https://api.binance.com",
    "https://data-api.binance.vision",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
]


class BinanceClient:
    def __init__(
        self,
        base_urls: Optional[List[str]] = None,
        max_retries: int = 3,
        retry_delay_base: float = 2.0,
        timeout: float = 10.0,
    ):
        self.base_urls = base_urls or BINANCE_PUBLIC_BASE_URLS
        self.max_retries = max_retries
        self.retry_delay_base = retry_delay_base
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "BinanceSquarePostingBot/1.0",
                "Accept": "application/json",
            }
        )

    def _request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None
    ) -> Any:
        """Executes a GET request across available endpoints with exponential backoff."""
        last_error = None
        req_timeout = timeout or self.timeout

        for attempt in range(self.max_retries):
            # Rotate endpoint on each attempt if needed
            base_url = self.base_urls[attempt % len(self.base_urls)]
            url = f"{base_url}{endpoint}"

            try:
                logger.debug(f"Requesting Binance API: {url} (Attempt {attempt + 1}/{self.max_retries})")
                response = self.session.get(url, params=params, timeout=req_timeout)
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                delay = self.retry_delay_base * (2 ** attempt)
                logger.warning(
                    f"Binance API request to {url} failed: {exc}. Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)

        logger.error(f"Binance API request {endpoint} failed after {self.max_retries} attempts.")
        raise RuntimeError(f"Binance API failure on {endpoint}: {last_error}") from last_error

    def get_24h_tickers(self) -> List[Dict[str, Any]]:
        """Fetch 24-hour ticker statistics for all symbols."""
        data = self._request("/api/v3/ticker/24hr", timeout=25.0)
        if not isinstance(data, list):
            raise ValueError("Expected a list of tickers from Binance 24hr API")
        return data

    def get_usdt_pairs_24h(self, min_quote_volume: float = 10_000_000.0) -> List[Dict[str, Any]]:
        """
        Fetch 24h tickers filtered for active USDT pairs meeting minimum quote volume.
        Excludes leveraged tokens (UP, DOWN, BULL, BEAR) and stablecoin pairs (USDC, FDUSD, etc.).
        """
        tickers = self.get_24h_tickers()
        filtered = []

        # Pairs to exclude (stablecoin-to-stablecoin, pegged assets, or leveraged tokens)
        excluded_bases = {
            "USDC", "FDUSD", "TUSD", "BUSD", "EUR", "DAI", "USDP", "AEUR",
            "U", "USDS", "USDE", "USTC", "EURI", "WBETH", "WBTC", "BNSOL",
        }

        for t in tickers:
            symbol = t.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue

            base = symbol[:-4]
            # Exclude non-ASCII/non-alphanumeric, leveraged tokens and stables
            if not base.isalnum() or not base.isascii():
                continue
            if any(base.endswith(suf) for suf in ("UP", "DOWN", "BULL", "BEAR")):
                continue
            if base in excluded_bases:
                continue

            try:
                quote_volume = float(t.get("quoteVolume", 0))
                price_change_pct = float(t.get("priceChangePercent", 0))
                last_price = float(t.get("lastPrice", 0))
                high_price = float(t.get("highPrice", 0))
                low_price = float(t.get("lowPrice", 0))
                volume = float(t.get("volume", 0))
            except (ValueError, TypeError):
                continue

            # Filter out stablecoins pegged to ~$1 with minimal volatility
            if 0.98 <= last_price <= 1.02 and last_price > 0:
                price_range = (high_price - low_price) / last_price
                if price_range < 0.02:  # Less than 2% daily volatility is a stablecoin
                    continue

            if quote_volume >= min_quote_volume and last_price > 0:
                filtered.append(
                    {
                        "symbol": symbol,
                        "base_asset": base,
                        "last_price": last_price,
                        "price_change_percent": price_change_pct,
                        "high_price": high_price,
                        "low_price": low_price,
                        "volume": volume,
                        "quote_volume": quote_volume,
                    }
                )

        logger.info(
            f"Filtered {len(filtered)} USDT pairs with >= {min_quote_volume:,.0f} USDT volume."
        )
        return filtered

    def get_klines(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candlestick data for a symbol and interval.
        Intervals: '1h', '4h', '1d', etc.
        Returns a clean pandas DataFrame indexed by UTC datetime.
        """
        params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
        raw_candles = self._request("/api/v3/klines", params=params)

        if not raw_candles:
            raise ValueError(f"No kline data returned for {symbol} on {interval}")

        # Binance Kline Format:
        # [0: Open time, 1: Open, 2: High, 3: Low, 4: Close, 5: Volume, 6: Close time, ...]
        rows = []
        for c in raw_candles:
            rows.append(
                {
                    "timestamp": pd.to_datetime(c[0], unit="ms", utc=True),
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4]),
                    "volume": float(c[5]),
                }
            )

        df = pd.DataFrame(rows)
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
        return df
