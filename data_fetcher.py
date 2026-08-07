"""
Moduł do pobierania rzeczywistych danych giełdowych.
Obsługuje yfinance (domyślnie) oraz Alpha Vantage (opcjonalnie).
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# ------------------- KONFIGURACJA -------------------
DEFAULT_SYMBOL = "AAPL"
DEFAULT_PERIOD = "6mo"  # 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max

# ------------------- FUNKCJE GŁÓWNE -------------------

def fetch_yfinance(symbol: str = DEFAULT_SYMBOL, period: str = DEFAULT_PERIOD) -> dict:
    """
    Pobiera dane OHLCV z Yahoo Finance.
    Zwraca słownik z listami: open, high, low, close, volume.
    """
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        
        if hist.empty:
            raise ValueError(f"Brak danych dla {symbol} (okres: {period})")
        
        # Konwersja na listy (format zgodny z oczekiwaniami API)
        result = {
            "open": hist["Open"].tolist(),
            "high": hist["High"].tolist(),
            "low": hist["Low"].tolist(),
            "close": hist["Close"].tolist(),
            "volume": hist["Volume"].tolist(),
            "date": hist.index.strftime("%Y-%m-%d").tolist(),
            "symbol": symbol,
            "period": period,
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return result
    except Exception as e:
        raise RuntimeError(f"Błąd pobierania danych z Yahoo: {e}")

def fetch_alpha_vantage(symbol: str = DEFAULT_SYMBOL, api_key: str = None) -> dict:
    """
    Opcjonalny alternatywny źródło danych – Alpha Vantage.
    Wymaga darmowego klucza API z alphavantage.co
    """
    if not api_key:
        raise ValueError("Brak klucza API dla Alpha Vantage")
    
    import requests
    BASE_URL = "https://www.alphavantage.co/query"
    
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": "compact",
        "apikey": api_key
    }
    
    response = requests.get(BASE_URL, params=params)
    data = response.json()
    
    if "Time Series (Daily)" not in data:
        raise ValueError(f"Błąd Alpha Vantage: {data.get('Error Message', 'Nieznany błąd')}")
    
    ts = data["Time Series (Daily)"]
    dates = sorted(ts.keys())  # posortowane chronologicznie
    
    result = {
        "open": [float(ts[d]["1. open"]) for d in dates],
        "high": [float(ts[d]["2. high"]) for d in dates],
        "low": [float(ts[d]["3. low"]) for d in dates],
        "close": [float(ts[d]["4. close"]) for d in dates],
        "volume": [int(ts[d]["5. volume"]) for d in dates],
        "date": dates,
        "symbol": symbol,
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return result

# ------------------- PRZYKŁAD UŻYCIA -------------------
if __name__ == "__main__":
    # Test z yfinance
    print("Pobieranie danych z yfinance...")
    data = fetch_yfinance("AAPL", "1mo")
    print(f"Pobrano {len(data['close'])} dni dla {data['symbol']}")
    print("Ostatnie 5 zamknięć:", data['close'][-5:])