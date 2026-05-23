import numpy as np
import pandas as pd

TRADING_DAYS = 252


def price_asof(prices: pd.DataFrame, date) -> pd.Series:
    """Last known price of each column on or before `date`."""
    past = prices.loc[:pd.Timestamp(date)]
    if past.empty:
        return pd.Series(np.nan, index=prices.columns, dtype=float)
    return past.ffill().iloc[-1]


def momentum(prices: pd.DataFrame, as_of, lookback_months=12, skip_months=1) -> pd.Series:
    """Return from `lookback_months` ago to `skip_months` ago, skipping the latest month."""
    as_of = pd.Timestamp(as_of)
    recent = price_asof(prices, as_of - pd.DateOffset(months=skip_months))
    old = price_asof(prices, as_of - pd.DateOffset(months=lookback_months))
    mom = recent / old - 1.0
    mom[(old <= 0) | old.isna() | recent.isna()] = np.nan
    return mom


def volatility(returns: pd.DataFrame, as_of, window=TRADING_DAYS, min_periods=126) -> pd.Series:
    """Annualized volatility of daily returns over the trailing window."""
    recent = returns.loc[:pd.Timestamp(as_of)].tail(window)
    vol = recent.std(ddof=1) * np.sqrt(TRADING_DAYS)
    vol[recent.count() < min_periods] = np.nan
    return vol
