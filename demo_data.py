"""
demo_data.py — syntetyczne dane OHLCV dla trybu demo analizator-gieldowy-2.0.

Używane, gdy symbol == "DEMO" (albo Yahoo Finance jest niedostępne) - żeby
dashboard i testy działały bez połączenia z internetem. Dane generowane
metodą geometrycznego ruchu Browna (GBM), TAK SAMO jak w analizator-gieldowy
(v1) - jawnie oznaczone jako syntetyczne, nigdy nie przedstawiane jako
prawdziwe dane rynkowe.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

_PERIOD_DAYS = {
    "5d": 5,
    "1mo": 22,
    "3mo": 63,
    "6mo": 126,
    "1y": 252,
    "2y": 504,
    "5y": 1260,
}


def generate_demo_ohlc(symbol: str = "DEMO", period: str = "6mo", seed: int = 7) -> dict:
    """Zwraca słownik w DOKŁADNIE takim samym formacie jak fetch_yfinance()."""
    n = _PERIOD_DAYS.get(period, 126)
    rng = np.random.default_rng(seed)

    mu, sigma = 0.0003, 0.016
    log_returns = rng.normal(mu, sigma, n)
    # lekki wstrzyknięty trend spadkowy w środkowej jednej trzeciej okresu,
    # żeby tezy "kontratrendowa" miały sens na danych demo
    dip_start, dip_end = n // 3, 2 * n // 3
    log_returns[dip_start:dip_end] -= 0.0015

    price = 100.0 * np.exp(np.cumsum(log_returns))
    close = price
    open_ = np.concatenate([[100.0], close[:-1]])
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.006, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.006, n))
    volume = rng.integers(1_000_000, 5_000_000, n)

    end = datetime.now()
    dates = pd.bdate_range(end=end, periods=n)

    return {
        "open": [round(float(x), 4) for x in open_],
        "high": [round(float(x), 4) for x in high],
        "low": [round(float(x), 4) for x in low],
        "close": [round(float(x), 4) for x in close],
        "volume": [int(v) for v in volume],
        "date": [d.strftime("%Y-%m-%d") for d in dates],
        "symbol": symbol,
        "period": period,
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
