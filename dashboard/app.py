import math
import os
from datetime import date
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dashboard import data
from momentum import metrics
from momentum.backtest import cash_returns_from_rate, run
from momentum.strategies import CASH, LABELS, STRATEGIES, Params

FRONTEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
MAX_ASSETS = 25

app = FastAPI(title="Momentum Allocation Dashboard", version="1.0.0",
              description="Run the monthly momentum strategies on any basket from any start date.")


class ModelSettings(BaseModel):
    lookback_months: int = Field(12, ge=2, le=24)
    skip_months: int = Field(1, ge=0, le=3)
    vol_window: int = Field(252, ge=21, le=756, description="Trading days used for volatility")
    min_weight: float = Field(0.02, ge=0, le=0.2)
    max_weight: float = Field(0.30, gt=0, le=1)


class BacktestRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=1, max_length=MAX_ASSETS)
    start: date = Field(..., description="First rebalance, or the next trading day after it")
    end: date | None = None
    rebalance: Literal["start_day", "month_end"] = "start_day"
    base_currency: str = Field("USD", pattern=r"^[A-Z]{3}$")
    cash_rate: float = Field(0.04, ge=0, le=0.2, description="Annual return on uninvested cash")
    settings: ModelSettings = ModelSettings()
    strategies: list[str] = list(STRATEGIES)


def _clean(x):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), 6)


def _dates(index) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in index]


@app.get("/api/health")
def health():
    return {"status": "ok", "price_source": "csv" if data.PRICES_CSV else "yahoo"}


@app.get("/api/strategies")
def strategies():
    return {"strategies": [{"id": k, "name": LABELS[k]} for k in STRATEGIES], "defaults": ModelSettings().model_dump()}


@app.get("/api/search")
def search(q: str = Query(..., min_length=1, max_length=40)):
    return {"results": data.search(q)}


@app.get("/api/lookup/{ticker}")
def lookup(ticker: str):
    try:
        ticker = data.normalize_ticker(ticker)
    except data.DataError as e:
        raise HTTPException(400, str(e))
    try:
        prices = data.raw_prices([ticker])[ticker].dropna()
    except data.DataError as e:
        raise HTTPException(404, str(e))
    info = data.ticker_info(ticker)
    currency, scale = data.currency_unit(info["currency"])
    return {"ticker": ticker, "name": info["name"], "currency": currency,
            "last_price": float(prices.iloc[-1] * scale), "first_date": prices.index[0].strftime("%Y-%m-%d")}


@app.post("/api/backtest")
def backtest(req: BacktestRequest):
    unknown = [s for s in req.strategies if s not in STRATEGIES]
    if unknown or not req.strategies:
        raise HTTPException(400, f"Unknown strategies: {', '.join(unknown)}" if unknown else "Pick at least one strategy")
    if req.settings.skip_months >= req.settings.lookback_months:
        raise HTTPException(400, "Skip months must be shorter than the lookback")
    if req.end and req.end <= req.start:
        raise HTTPException(400, "End date must be after the start date")
    try:
        tickers = list(dict.fromkeys(data.normalize_ticker(t) for t in req.tickers))
        prices = data.load_prices(tickers, req.base_currency)
    except data.DataError as e:
        raise HTTPException(400, str(e))

    start, end = pd.Timestamp(req.start), pd.Timestamp(req.end or prices.index.max())
    if start > prices.index.max():
        raise HTTPException(400, f"Start date is after the latest price ({prices.index.max():%Y-%m-%d})")
    params = Params(lookback_months=req.settings.lookback_months, skip_months=req.settings.skip_months,
                    vol_window=req.settings.vol_window, vol_min_periods=max(2, req.settings.vol_window // 2),
                    min_weight=req.settings.min_weight, max_weight=req.settings.max_weight)
    day = start.day if req.rebalance == "start_day" else None
    cash = cash_returns_from_rate(prices.index, req.cash_rate)
    history = req.settings.lookback_months + 1

    results = {}
    for name in req.strategies:
        try:
            res = run(name, prices.loc[:end], start, end, day, params, cash, min_history_months=history)
        except ValueError as e:
            raise HTTPException(400, str(e))
        summary = {k: _clean(v) for k, v in metrics.summarize(res, req.cash_rate).items()}
        current = res.weights.iloc[-1]
        results[name] = {
            "name": LABELS[name],
            "metrics": summary,
            "value": {"dates": _dates(res.value.index), "values": [_clean(v) for v in res.value]},
            "drawdown": [_clean(v) for v in metrics.drawdown(res.value)],
            "weights": {"dates": _dates(res.weights.index), "assets": tickers + [CASH],
                        "rows": [[_clean(v) for v in row] for row in res.weights[tickers + [CASH]].values]},
            "current": {"date": res.weights.index[-1].strftime("%Y-%m-%d"),
                        "weights": {a: _clean(current[a]) for a in tickers + [CASH]}},
            "turnover": {"dates": _dates(res.turnover.index), "values": [_clean(v) for v in res.turnover]},
        }

    first = next(iter(results.values()))
    late = [t for t in tickers if prices[t].first_valid_index() > start - pd.DateOffset(months=history)]
    return {
        "window": {"start": first["weights"]["dates"][0], "end": first["value"]["dates"][-1],
                   "rebalances": len(first["weights"]["dates"]),
                   "schedule": f"day {day} of each month" if day else "last trading day of each month"},
        "base_currency": req.base_currency,
        "assets": [{"ticker": t, "name": data.ticker_info(t)["name"],
                    "first_date": prices[t].first_valid_index().strftime("%Y-%m-%d")} for t in tickers],
        "notes": [f"{t} has less than {history} months of history at the start, so it joins once it has enough."
                  for t in late],
        "strategies": results,
    }


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(FRONTEND, "index.html"))


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
