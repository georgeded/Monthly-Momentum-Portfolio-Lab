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
