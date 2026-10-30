"""Live prices from Yahoo Finance for the dashboard, converted to one currency and cached on disk."""
import json
import os
import re
import threading
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
_info_lock = threading.Lock()
# yfinance keeps download results in module globals, so overlapping downloads can mix them up.
_download_lock = threading.Lock()


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


def _write_atomic(path: str, write) -> None:
    # Write to a temporary file and swap it in, so readers never see half a file.
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    write(tmp)
    os.replace(tmp, path)


def _fresh(path: str) -> bool:
    return os.path.exists(path) and (time.time() - os.path.getmtime(path)) / 3600 < CACHE_TTL_HOURS


def _download(tickers: list[str]) -> pd.DataFrame:
    import yfinance as yf

    with _download_lock:
        raw = yf.download(tickers, period="max", auto_adjust=True, progress=False, threads=True, group_by="column")
    if raw is None or raw.empty:
        return pd.DataFrame()
    close = raw["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close


def _read_cached(path: str) -> pd.Series | None:
    if not _fresh(path):
        return None
    try:
        return pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0]
    except (OSError, ValueError, IndexError):
        return None


def _yahoo_prices(tickers: list[str]) -> pd.DataFrame:
    frames, missing = [], []
    for t in tickers:
        cached = _read_cached(_cache_path(f"{t}.csv"))
        if cached is None:
            missing.append(t)
        else:
            frames.append(cached.rename(t))
    if missing:
        close = _download(missing)
        for t in missing:
            if t not in close.columns or close[t].dropna().empty:
                raise DataError(f"No price history for {t}")
            s = close[t].dropna()
            _write_atomic(_cache_path(f"{t}.csv"), lambda tmp: s.to_csv(tmp, header=[t]))
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


def load_prices(tickers: list[str], base: str = "USD") -> pd.DataFrame:
    """Daily prices in the base currency, one column per ticker, on the union of trading days."""
    tickers = list(dict.fromkeys(normalize_ticker(t) for t in tickers))
    units = {t: currency_unit(ticker_info(t)["currency"]) for t in tickers}
    pairs = sorted({f"{c}{base}=X" for c, _ in units.values() if c != base})
    prices = raw_prices(tickers + pairs)
    check_stale(prices[tickers])
    prices = prices.ffill(limit=MAX_GAP_DAYS)
    out = {}
    for t, (currency, scale) in units.items():
        fx = 1.0 if currency == base else prices[f"{currency}{base}=X"]
        out[t] = prices[t] * scale * fx
    return pd.DataFrame(out).dropna(how="all")


def _read_store(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _dump_json(store: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(store, f, indent=1)


def ticker_info(ticker: str) -> dict:
    """Name and quote currency from Yahoo, cached. Incomplete answers are retried after an hour."""
    ticker = normalize_ticker(ticker)
    path = _cache_path("info.json")
    with _info_lock:
        cached = _read_store(path).get(ticker)
    if cached and (cached["complete"] or time.time() - cached["fetched"] < 3600):
        return {k: cached[k] for k in ("name", "sector", "currency")}

    entry = {"name": ticker, "sector": None, "currency": None}
    if PRICES_CSV:
        return entry
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info or {}
    except Exception:
        info = {}
    if not info.get("longName") and not info.get("shortName"):
        return {k: cached[k] for k in ("name", "sector", "currency")} if cached else entry
    entry = {"name": info.get("longName") or info.get("shortName"), "sector": info.get("sector"),
             "currency": info.get("currency")}
    with _info_lock:
        store = _read_store(path)
        store[ticker] = {**entry, "complete": bool(entry["sector"]) or info.get("quoteType") in NO_SECTOR_TYPES,
                         "fetched": time.time()}
        _write_atomic(path, lambda tmp: _dump_json(store, tmp))
    return entry


_search_cache: dict[str, list[dict]] = {}


def search(query: str, limit: int = 8) -> list[dict]:
    q = query.strip()
    if not q:
        return []
    if PRICES_CSV:
        columns = pd.read_csv(PRICES_CSV, nrows=0).columns[1:]
        return [{"ticker": c.upper(), "name": c.upper(), "exchange": None, "type": None}
                for c in columns if c.upper().startswith(q.upper())][:limit]
    key = q.lower()
    if key not in _search_cache:
        try:
            import yfinance as yf

            quotes = yf.Search(q, max_results=limit * 2, news_count=0).quotes
        except Exception:
            return []
        results = []
        for item in quotes:
            symbol = str(item.get("symbol") or "").upper()
            if item.get("quoteType") in SEARCH_TYPES and TICKER_PATTERN.match(symbol):
                results.append({"ticker": symbol, "name": item.get("longname") or item.get("shortname") or symbol,
                                "exchange": item.get("exchDisp"), "type": item.get("quoteType").lower()})
        if len(_search_cache) > 500:
            _search_cache.clear()
        _search_cache[key] = results
    return _search_cache[key][:limit]
