from dataclasses import dataclass

import pandas as pd

from momentum.signals import momentum, volatility

CASH = "cash"


@dataclass(frozen=True)
class Params:
    lookback_months: int = 12
    skip_months: int = 1
    vol_window: int = 252
    vol_min_periods: int = 126
    min_weight: float = 0.02
    max_weight: float = 0.30


def normalize(scores: pd.Series) -> pd.Series:
    s = scores.clip(lower=0.0).fillna(0.0)
    total = s.sum()
    return s / total if total > 0 else s * 0.0


def apply_floor(weights: pd.Series, min_weight: float) -> pd.Series:
    """Give every asset `min_weight` and share the rest in proportion to `weights`.

    All-zero weights become equal weight.
    """
    w = weights.clip(lower=0.0).fillna(0.0)
    n = len(w)
    if n == 0:
        return w
    if w.sum() <= 0 or n * min_weight >= 1.0:
        return pd.Series(1.0 / n, index=w.index)
    if min_weight <= 0:
        return w / w.sum()
    return min_weight + (1.0 - n * min_weight) * w / w.sum()


def apply_cap(weights: pd.Series, cap: float, tol=1e-12) -> pd.Series:
    """Cap each weight and hand the excess to the uncapped names pro rata.

    When the cap cannot hold everything (too few assets), each asset gets the
    cap and the rest is left for cash.
    """
    w = weights.clip(lower=0.0).astype(float)
    if w.sum() <= 0:
        return w
    w = w / w.sum()
    if (w > 0).sum() * cap < 1.0 - tol:
        return (w > 0).astype(float) * cap
    for _ in range(len(w)):
        over = w > cap + tol
        if not over.any():
            break
        excess = float((w[over] - cap).sum())
        w[over] = cap
        room = (w < cap - tol) & (w > 0)
        if not room.any():
            break
        w[room] += excess * w[room] / w[room].sum()
    return w


def tsmom(prices, returns, as_of, params: Params) -> pd.Series:
    """Positive 12-1 momentum divided by volatility, with a floor and a cap."""
    mom = momentum(prices, as_of, params.lookback_months, params.skip_months)
    vol = volatility(returns, as_of, params.vol_window, params.vol_min_periods)
    scores = (mom.clip(lower=0.0) / vol.where(vol > 0)).fillna(0.0)
    w = apply_floor(normalize(scores), params.min_weight)
    return apply_cap(w, params.max_weight)


def equal_weight(prices, returns, as_of, params: Params) -> pd.Series:
    return pd.Series(1.0 / prices.shape[1], index=prices.columns)


def inverse_vol(prices, returns, as_of, params: Params) -> pd.Series:
    vol = volatility(returns, as_of, params.vol_window, params.vol_min_periods)
    return apply_floor(normalize(1.0 / vol.where(vol > 0)), params.min_weight)


def momentum_only(prices, returns, as_of, params: Params) -> pd.Series:
    mom = momentum(prices, as_of, params.lookback_months, params.skip_months)
    return apply_floor(normalize(mom), params.min_weight)


STRATEGIES = {
    "tsmom": tsmom,
    "equal_weight": equal_weight,
    "inverse_vol": inverse_vol,
    "momentum_only": momentum_only,
}

LABELS = {
    "tsmom": "TSMOM",
    "equal_weight": "Equal weight",
    "inverse_vol": "Inverse volatility",
    "momentum_only": "Momentum only",
}
