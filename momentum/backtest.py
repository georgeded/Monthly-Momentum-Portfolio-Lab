from dataclasses import dataclass

import pandas as pd

from momentum.signals import TRADING_DAYS, price_asof
from momentum.strategies import CASH, Params, allocate


@dataclass
class Result:
    weights: pd.DataFrame    # target weights on each rebalance date, including cash
    period_returns: pd.Series  # return of each holding period, indexed by its end date
    value: pd.Series         # daily value of 1 invested on the first rebalance date
    turnover: pd.Series      # one-way turnover at each rebalance after the first


def rebalance_dates(index, start, end=None, day=None) -> pd.DatetimeIndex:
    """Trading days to rebalance on, from the first trading day on or after `start`.

    With `day` set, each month rebalances on the last trading day on or before
    that day of the month. Without it, on the last trading day of the month.
    """
    idx = pd.DatetimeIndex(index).sort_values()
    idx = idx[(idx >= pd.Timestamp(start)) & (idx <= pd.Timestamp(end or idx.max()))]
    if idx.empty:
        return idx
    dates = []
    for _, month in pd.Series(idx, index=idx).groupby([idx.year, idx.month]):
        if day is None:
            dates.append(month.iloc[-1])
            continue
        last_day = (month.iloc[0] + pd.offsets.MonthEnd(0)).day
        target = month.iloc[0].replace(day=min(int(day), last_day))
        eligible = month[month <= target]
        if not eligible.empty:
            dates.append(eligible.iloc[-1])
        elif not dates:
            dates.append(month.iloc[0])
    return pd.DatetimeIndex(dates)


def active_assets(prices: pd.DataFrame, as_of, min_history_months=13, min_days=126) -> list:
    """Assets with enough history on `as_of` to compute their signals."""
    cutoff = pd.Timestamp(as_of) - pd.DateOffset(months=min_history_months)
    active = []
    for col in prices.columns:
        s = prices[col].loc[:pd.Timestamp(as_of)].dropna()
        if not s.empty and s.index[0] <= cutoff and len(s) >= min_days:
            active.append(col)
    return active


def target_weights(strategy, prices, as_of, params=Params(), min_history_months=13) -> pd.Series:
    """Weights a strategy would set on `as_of`, using only prices up to that day."""
    past = prices.loc[:pd.Timestamp(as_of)]
    returns = past.pct_change()
    active = active_assets(past, as_of, min_history_months, params.vol_min_periods)
    return allocate(strategy, past, returns, as_of, active, params)
