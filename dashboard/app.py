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
