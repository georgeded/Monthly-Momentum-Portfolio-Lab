"""Live prices from Yahoo Finance for the dashboard, converted to one currency and cached on disk."""
import json
import os
import re
import time

import pandas as pd

CACHE_DIR = os.environ.get("CACHE_DIR", os.path.join(os.path.dirname(__file__), "..", "cache"))
CACHE_TTL_HOURS = float(os.environ.get("CACHE_TTL_HOURS", "12"))
PRICES_CSV = os.environ.get("PRICES_CSV")
MAX_GAP_DAYS = 5

TICKER_PATTERN = re.compile(r"^[A-Z0-9^][A-Z0-9.\-=^]{0,19}$")
MINOR_UNITS = {"GBp": ("GBP", 0.01), "GBX": ("GBP", 0.01), "ZAc": ("ZAR", 0.01), "ILA": ("ILS", 0.01)}
NO_SECTOR_TYPES = {"ETF", "INDEX", "MUTUALFUND", "CURRENCY", "CRYPTOCURRENCY"}
SEARCH_TYPES = {"EQUITY", "ETF", "INDEX", "MUTUALFUND"}


class DataError(Exception):
    pass


def normalize_ticker(ticker: str) -> str:
    t = str(ticker).strip().upper()
    if not TICKER_PATTERN.match(t):
        raise DataError(f"Not a valid ticker: {ticker!r}")
    return t


def currency_unit(code) -> tuple[str, float]:
    """ISO currency and the factor that turns a quoted price into it."""
    if not code:
        return "USD", 1.0
    return MINOR_UNITS.get(code, (str(code).upper(), 1.0))


def _cache_path(name: str) -> str:
    root = os.path.realpath(CACHE_DIR)
    os.makedirs(root, exist_ok=True)
    path = os.path.realpath(os.path.join(root, name))
    if os.path.dirname(path) != root:
        raise DataError(f"Invalid cache name: {name!r}")
    return path


def _fresh(path: str) -> bool:
    return os.path.exists(path) and (time.time() - os.path.getmtime(path)) / 3600 < CACHE_TTL_HOURS


def _download(tickers: list[str]) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(tickers, period="max", auto_adjust=True, progress=False, threads=True, group_by="column")
    if raw is None or raw.empty:
        return pd.DataFrame()
    close = raw["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close


def _yahoo_prices(tickers: list[str]) -> pd.DataFrame:
    frames, missing = [], []
    for t in tickers:
        path = _cache_path(f"{t}.csv")
        if _fresh(path):
            frames.append(pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0].rename(t))
        else:
            missing.append(t)
    if missing:
        close = _download(missing)
        for t in missing:
            if t not in close.columns or close[t].dropna().empty:
                raise DataError(f"No price history for {t}")
            s = close[t].dropna()
            s.to_csv(_cache_path(f"{t}.csv"), header=[t])
            frames.append(s.rename(t))
    return pd.concat(frames, axis=1).sort_index()


def _csv_prices(tickers: list[str]) -> pd.DataFrame:
    df = pd.read_csv(PRICES_CSV, index_col=0, parse_dates=True).sort_index()
    df.columns = [c.upper() for c in df.columns]
    absent = [t for t in tickers if t not in df.columns]
    if absent:
        raise DataError(f"Not in {PRICES_CSV}: {', '.join(absent)}")
    return df[tickers]


def raw_prices(tickers: list[str]) -> pd.DataFrame:
    return _csv_prices(tickers) if PRICES_CSV else _yahoo_prices(tickers)


def check_stale(prices: pd.DataFrame) -> None:
    """Fail on tickers that stopped trading, instead of cutting every series short."""
    stale = []
    for t in prices.columns:
        last = prices[t].last_valid_index()
        if last is None:
            raise DataError(f"No price history for {t}")
        if (prices.index > last).sum() > MAX_GAP_DAYS:
            stale.append(f"{t} (last price {last:%Y-%m-%d})")
    if stale:
        raise DataError(f"No recent prices for {', '.join(stale)}. Remove them or check the symbols.")
