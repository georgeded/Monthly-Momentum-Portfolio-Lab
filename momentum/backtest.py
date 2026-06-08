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


def cash_returns_from_rate(index, annual_rate: float) -> pd.Series:
    daily = (1.0 + annual_rate) ** (1.0 / TRADING_DAYS) - 1.0
    return pd.Series(daily, index=index)


def run(strategy, prices: pd.DataFrame, start, end=None, rebalance_day=None,
        params=Params(), cash_returns: pd.Series | None = None, min_history_months=13) -> Result:
    """Rebalance monthly from `start` and hold the weights, letting them drift, until the next date.

    Signals on a rebalance date use prices up to and including that close.
    """
    prices = prices.sort_index()
    end = pd.Timestamp(end or prices.index.max())
    dates = rebalance_dates(prices.index, start, end, rebalance_day)
    if dates.empty:
        raise ValueError("No trading days between the start and end dates")
    if cash_returns is None:
        cash_returns = cash_returns_from_rate(prices.index, 0.0)
    cash_returns = cash_returns.reindex(prices.index).fillna(0.0)
    returns = prices.pct_change()
    cols = list(prices.columns)

    weights, periods, paths, turnover = {}, {}, [], {}
    value = 1.0
    drifted = None
    stops = list(dates[1:]) + ([end] if end > dates[-1] else [])
    for i, d in enumerate(dates):
        active = active_assets(prices.loc[:d], d, min_history_months, params.vol_min_periods)
        w = allocate(strategy, prices.loc[:d], returns.loc[:d], d, active, params)
        weights[d] = w
        if drifted is not None:
            turnover[d] = 0.5 * float((w - drifted).abs().sum())
        if i >= len(stops):
            break

        stop = stops[i]
        window = prices.loc[d:stop, cols].ffill()
        growth = window / price_asof(prices, d)[cols]
        cash_growth = (1.0 + cash_returns.loc[d:stop].iloc[1:]).cumprod().reindex(window.index).fillna(1.0)
        held = growth.fillna(1.0).mul(w[cols]).sum(axis=1) + w[CASH] * cash_growth
        paths.append(held.iloc[1:] * value if paths else held * value)
        periods[stop] = float(held.iloc[-1] - 1.0)
        value *= float(held.iloc[-1])

        end_weights = pd.concat([growth.iloc[-1].fillna(1.0) * w[cols], pd.Series({CASH: w[CASH] * cash_growth.iloc[-1]})])
        drifted = end_weights / end_weights.sum()

    frame = pd.DataFrame(weights).T
    frame.index.name = "rebalance_date"
    path = pd.concat(paths) if paths else pd.Series([1.0], index=[dates[0]])
    return Result(
        weights=frame,
        period_returns=pd.Series(periods, name="return"),
        value=path.rename("value"),
        turnover=pd.Series(turnover, name="turnover", dtype=float),
    )
