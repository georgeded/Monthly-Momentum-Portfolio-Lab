import numpy as np
import pandas as pd

MONTHS_PER_YEAR = 12


def cumulative_return(returns: pd.Series) -> float:
    r = returns.dropna()
    return float((1.0 + r).prod() - 1.0) if len(r) else np.nan


def annualized_return(returns: pd.Series, periods_per_year=MONTHS_PER_YEAR) -> float:
    r = returns.dropna()
    growth = float((1.0 + r).prod())
    if r.empty or growth <= 0:
        return np.nan
    return growth ** (periods_per_year / len(r)) - 1.0


def annualized_volatility(returns: pd.Series, periods_per_year=MONTHS_PER_YEAR) -> float:
    r = returns.dropna()
    return float(r.std(ddof=1) * np.sqrt(periods_per_year)) if len(r) > 1 else np.nan


def sharpe_ratio(returns: pd.Series, rf_annual=0.0, periods_per_year=MONTHS_PER_YEAR) -> float:
    vol = annualized_volatility(returns, periods_per_year)
    if not vol or np.isnan(vol):
        return np.nan
    return (annualized_return(returns, periods_per_year) - rf_annual) / vol


def sortino_ratio(returns: pd.Series, rf_annual=0.0, periods_per_year=MONTHS_PER_YEAR) -> float:
    r = returns.dropna()
    if r.empty:
        return np.nan
    rf_period = (1.0 + rf_annual) ** (1.0 / periods_per_year) - 1.0
    downside = np.sqrt(((r - rf_period).clip(upper=0.0) ** 2).mean() * periods_per_year)
    if downside == 0:
        return np.nan
    return (annualized_return(r, periods_per_year) - rf_annual) / downside
