"""Binance Public Market Data Client with retry and exponential backoff."""
import time
import logging
from typing import List, Dict, Any, Optional
import requests
import pandas as pd

logger = logging.getLogger(__name__)

# Primary and alternative public endpoints for redundancy (data-api.binance.vision has no USA 451 geoblock)
BINANCE_PUBLIC_BASE_URLS = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
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
            except requests.HTTPError as exc:
                last_error = exc
                status = exc.response.status_code if exc.response is not None else 0
                if status in (400, 451):
                    # 400 = invalid symbol, 451 = geoblock. Retrying the same endpoint with delay is useless.
                    logger.debug(f"Binance API {url} returned HTTP {status}: skipping retry delay.")
                    continue
                delay = self.retry_delay_base * (2 ** attempt)
                logger.warning(
                    f"Binance API request to {url} failed: {exc}. Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
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

    def get_futures_pairs_24h(self, min_quote_volume: float = 10_000_000.0) -> List[Dict[str, Any]]:
        """
        Fetch 24h tickers filtered for active Binance Futures (USDT-M) pairs meeting minimum volume.
        Tries:
        1. Direct Binance Futures API (fapi.binance.com)
        2. CoinGecko Binance Futures derivatives tickers (bypasses cloud runner 451 geoblocks)
        3. Gate.io Futures public tickers (backup)
        4. Spot fallback if all futures endpoints fail
        """
        # 1. Try Binance Futures API directly
        try:
            res = self.session.get("https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=12)
            if res.ok and isinstance(res.json(), list) and len(res.json()) > 0:
                tickers = res.json()
                filtered = []
                for t in tickers:
                    symbol = t.get("symbol", "")
                    if not symbol.endswith("USDT"):
                        continue
                    base = symbol[:-4]
                    if not base.isalnum() or not base.isascii():
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
                    if quote_volume >= min_quote_volume and last_price > 0:
                        filtered.append({
                            "symbol": symbol,
                            "base_asset": base,
                            "last_price": last_price,
                            "price_change_percent": price_change_pct,
                            "high_price": high_price,
                            "low_price": low_price,
                            "volume": volume,
                            "quote_volume": quote_volume,
                        })
                if filtered:
                    logger.info(f"Loaded {len(filtered)} Binance Futures pairs directly from fapi.binance.com")
                    return filtered
        except Exception as exc:
            logger.debug(f"Direct Binance Futures ticker fetch failed ({exc}). Trying CoinGecko/Gate...")

        # 2. CoinGecko Binance Futures API (worldwide public API, no USA 451 geoblock)
        try:
            url = "https://api.coingecko.com/api/v3/derivatives/exchanges/binance_futures?include_tickers=all"
            res = self.session.get(url, timeout=12)
            if res.ok:
                cg_tickers = res.json().get("tickers", [])
                filtered = []
                for t in cg_tickers:
                    sym = t.get("symbol", "")
                    target = t.get("target", "")
                    if target != "USDT" or not sym.endswith("USDT"):
                        continue
                    base = sym[:-4]
                    try:
                        price = float(t.get("last", 0) or 0)
                        pct = float(t.get("price_change_percentage_24h", 0) or 0)
                        usd_vol = float(t.get("converted_volume", {}).get("usd", 0) or 0)
                    except (ValueError, TypeError):
                        continue
                    if usd_vol >= min_quote_volume and price > 0:
                        filtered.append({
                            "symbol": sym,
                            "base_asset": base,
                            "last_price": price,
                            "price_change_percent": pct,
                            "high_price": price * 1.03,
                            "low_price": price * 0.97,
                            "volume": usd_vol / price if price > 0 else 0,
                            "quote_volume": usd_vol,
                        })
                if filtered:
                    logger.info(f"Loaded {len(filtered)} Binance Futures pairs via CoinGecko derivatives API")
                    return filtered
        except Exception as exc:
            logger.debug(f"CoinGecko Binance Futures fetch failed: {exc}")

        # 3. Gate.io Futures API backup
        try:
            url = "https://fx-api.gateio.ws/api/v4/futures/usdt/tickers"
            res = self.session.get(url, timeout=10)
            if res.ok and isinstance(res.json(), list):
                filtered = []
                for t in res.json():
                    contract = t.get("contract", "")
                    if not contract.endswith("_USDT"):
                        continue
                    sym = contract.replace("_", "")
                    base = sym[:-4]
                    try:
                        qv = float(t.get("volume_24h_quote", 0))
                        pct = float(t.get("change_percentage", 0))
                        price = float(t.get("last", 0))
                        h = float(t.get("high_24h", 0))
                        l = float(t.get("low_24h", 0))
                        v = float(t.get("volume_24h_base", 0))
                    except (ValueError, TypeError):
                        continue
                    if qv >= min_quote_volume and price > 0:
                        filtered.append({
                            "symbol": sym,
                            "base_asset": base,
                            "last_price": price,
                            "price_change_percent": pct,
                            "high_price": h,
                            "low_price": l,
                            "volume": v,
                            "quote_volume": qv,
                        })
                if filtered:
                    logger.info(f"Loaded {len(filtered)} Futures pairs via Gate.io API")
                    return filtered
        except Exception as exc:
            logger.debug(f"Gate.io Futures fetch failed: {exc}")

        # 4. Fallback to Spot pairs if all Futures endpoints failed
        logger.warning("All Futures ticker sources failed. Falling back to Spot market pairs.")
        return self.get_usdt_pairs_24h(min_quote_volume=min_quote_volume)

    def _get_klines_gateio(self, symbol: str, interval: str, limit: int) -> Optional[pd.DataFrame]:
        """Fallback to Gate.io public candles if Binance is geoblocked (HTTP 451) on cloud runners."""
        base = symbol.replace("USDT", "")
        pairs = [f"{base}_USDT", f"1000{base}_USDT"]
        endpoints = [
            "spot/candlesticks?currency_pair=",
            "futures/usdt/candlesticks?contract=",
        ]
        for pair in pairs:
            for ep in endpoints:
                try:
                    url = f"https://api.gateio.ws/api/v4/{ep}{pair}&interval={interval}&limit={limit}"
                    res = self.session.get(url, timeout=8)
                    if res.ok:
                        data = res.json()
                        if isinstance(data, list) and len(data) > 0 and len(data[0]) >= 7:
                            rows = []
                            for c in data:
                                rows.append({
                                    "timestamp": pd.to_datetime(int(c[0]), unit="s", utc=True),
                                    "open": float(c[5]),
                                    "high": float(c[3]),
                                    "low": float(c[4]),
                                    "close": float(c[2]),
                                    "volume": float(c[6]),
                                })
                            df = pd.DataFrame(rows).set_index("timestamp").sort_index()
                            logger.info(f"Successfully fetched {len(df)} candles for {symbol} from Gate.io ({ep.split('/')[0]})")
                            return df
                except Exception as e:
                    logger.debug(f"Gate.io {ep}{pair} failed: {e}")
        return None

    def _get_klines_mexc(self, symbol: str, interval: str, limit: int) -> Optional[pd.DataFrame]:
        """Fallback to MEXC public candles if Binance and Gate.io fail."""
        mexc_interval = "60m" if interval == "1h" else ("4h" if interval == "4h" else interval)
        base = symbol.replace("USDT", "")
        for s in [f"{base}USDT", f"1000{base}USDT", symbol]:
            try:
                url = f"https://api.mexc.com/api/v3/klines?symbol={s}&interval={mexc_interval}&limit={limit}"
                res = self.session.get(url, timeout=8)
                if res.ok:
                    data = res.json()
                    if isinstance(data, list) and len(data) > 0 and len(data[0]) >= 6:
                        rows = []
                        for c in data:
                            rows.append({
                                "timestamp": pd.to_datetime(c[0], unit="ms", utc=True),
                                "open": float(c[1]),
                                "high": float(c[2]),
                                "low": float(c[3]),
                                "close": float(c[4]),
                                "volume": float(c[5]),
                            })
                        df = pd.DataFrame(rows).set_index("timestamp").sort_index()
                        logger.info(f"Successfully fetched {len(df)} candles for {symbol} from MEXC")
                        return df
            except Exception as e:
                logger.debug(f"MEXC {s} failed: {e}")
        return None

    def get_klines(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candlestick data for a symbol and interval.
        Order of resolution:
        1. Binance Spot API (via data-api.binance.vision / api.binance.com)
        2. Binance Futures API (via fapi.binance.com)
        3. Gate.io Public API (worldwide fallback, bypasses USA 451 geoblocks)
        4. MEXC Public API (secondary worldwide fallback)
        Returns a clean pandas DataFrame indexed by UTC datetime.
        """
        clean_symbol = symbol.replace("$", "").replace("/", "").replace("-", "").strip().upper()
        if not clean_symbol.endswith("USDT"):
            clean_symbol = clean_symbol + "USDT"
        symbol = clean_symbol

        params = {"symbol": symbol, "interval": interval, "limit": limit}

        # 1. Try Binance Spot
        raw_candles = None
        last_error = None

        try:
            raw_candles = self._request("/api/v3/klines", params=params)
        except Exception as exc:
            last_error = exc
            logger.debug(f"Spot klines failed for {symbol}: {exc}")

        # 2. Try Binance Futures (for coins listed on Futures / Perpetual)
        if not raw_candles:
            orig_urls = self.base_urls
            try:
                self.base_urls = ["https://fapi.binance.com"]
                raw_candles = self._request("/fapi/v1/klines", params=params)
                logger.info(f"Using Binance Futures klines for {symbol}")
            except Exception as exc:
                last_error = exc
                logger.debug(f"Binance Futures klines failed for {symbol}: {exc}")
            finally:
                self.base_urls = orig_urls

        # If Binance returned candles, parse them
        if raw_candles:
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

        # 3. Fallback to Gate.io (works globally on GitHub Actions runners without HTTP 451 geoblocks)
        logger.info(f"Binance klines failed for {symbol} ({last_error}). Trying Gate.io fallback...")
        df_gate = self._get_klines_gateio(symbol, interval, limit)
        if df_gate is not None and not df_gate.empty:
            return df_gate

        # 4. Fallback to MEXC
        logger.info(f"Gate.io klines failed for {symbol}. Trying MEXC fallback...")
        df_mexc = self._get_klines_mexc(symbol, interval, limit)
        if df_mexc is not None and not df_mexc.empty:
            return df_mexc

        raise ValueError(f"No kline data available for {symbol} across Binance, Gate.io, and MEXC: {last_error}")
