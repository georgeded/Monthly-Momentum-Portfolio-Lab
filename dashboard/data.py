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
