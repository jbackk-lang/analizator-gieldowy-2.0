"""
TIMDR API – Rzeczywiste dane z Yahoo Finance
Endpoints:
- /         – komunikat powitalny
- /health   – status API
- /predict  – pełna prognoza (metryki + tezy + sygnał)
- /signal   – uproszczony sygnał: KUP / SPRZEDAJ / TRZYMAJ
- /ohlcv    – surowe dane OHLCV (dla wykresów)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import yfinance as yf
import pandas as pd
from datetime import datetime
import uvicorn
import numpy as np

# ------------------ INICJALIZACJA ------------------
app = FastAPI(
    title="TIMDR API – Boundary-Matter",
    description="API do analizy skrętu informacji na danych giełdowych",
    version="1.0"
)

# Dodajemy CORS, żeby Streamlit mógł komunikować się z API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------ MODELE DANYCH ------------------
class PredictRequest(BaseModel):
    symbol: str = "AAPL"
    period: str = "6mo"
    k: float = -0.75

class SignalRequest(BaseModel):
    symbol: str = "AAPL"
    period: str = "1mo"
    k: float = -0.75

# ------------------ FUNKCJE POMOCNICZE ------------------
def fetch_yfinance(symbol: str, period: str) -> dict:
    """Pobiera dane z Yahoo Finance."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"Brak danych dla {symbol}")
        
        return {
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd Yahoo Finance: {str(e)}")

def generate_signal(close_prices: List[float], k: float) -> dict:
    """Generuje sygnał KUP / SPRZEDAJ / TRZYMAJ."""
    if len(close_prices) < 30:
        return {"action": "TRZYMAJ", "price": close_prices[-1] if close_prices else 0, "probability": 50, "reason": "Za mało danych"}
    
    last = close_prices[-1]
    sma10 = sum(close_prices[-10:]) / 10
    sma30 = sum(close_prices[-30:]) / 30
    
    if sma10 > sma30 and last > sma10:
        base_signal = "KUP"
        base_prob = 65
    elif sma10 < sma30 and last < sma10:
        base_signal = "SPRZEDAJ"
        base_prob = 65
    else:
        base_signal = "TRZYMAJ"
        base_prob = 50
    
    # Korekta o k
    if k < 0:
        if base_signal == "KUP":
            base_prob = base_prob - int(abs(k) * 15)
            if base_prob < 35:
                base_signal = "TRZYMAJ"
        elif base_signal == "SPRZEDAJ":
            base_prob = base_prob + int(abs(k) * 15)
            if base_prob > 85:
                base_prob = 85
    else:
        if base_signal == "KUP":
            base_prob = base_prob + int(k * 15)
            if base_prob > 85:
                base_prob = 85
        elif base_signal == "SPRZEDAJ":
            base_prob = base_prob - int(k * 15)
            if base_prob < 35:
                base_signal = "TRZYMAJ"
    
    return {
        "action": base_signal,
        "price": round(last, 2),
        "probability": min(100, max(0, base_prob)),
        "reason": f"SMA10={sma10:.2f}, SMA30={sma30:.2f}, k={k:.2f}"
    }

def generate_theses(data: dict, k: float) -> list:
    """Generuje 3 sprzeczne tezy."""
    close = data["close"]
    symbol = data["symbol"]
    last = close[-1]
    sma10 = sum(close[-10:]) / 10
    sma30 = sum(close[-30:]) / 30 if len(close) >= 30 else sma10
    
    change = (last / close[0] - 1) * 100 if close[0] > 0 else 0
    volatility = (max(close[-20:]) - min(close[-20:])) / min(close[-20:]) * 100 if min(close[-20:]) > 0 else 0
    
    theses = [
        {
            "id": 1,
            "type": "kontratrendowa",
            "statement": f"Pomimo że rynek {symbol} wzrósł o {change:.1f}% w ostatnim okresie, struktura skrętu (k={k:.2f}) sugeruje możliwość korekty. SMA10={sma10:.2f} vs SMA30={sma30:.2f}.",
            "probability": 60 + int(abs(k) * 10),
            "confidence": 75,
            "action": "SPRZEDAJ" if k < 0 else "KUP",
            "entry": round(last * 1.02, 2),
            "stop_loss": round(last * 1.05, 2),
            "take_profit": round(last * 0.97, 2)
        },
        {
            "id": 2,
            "type": "ambiwalentna",
            "statement": f"Rynek {symbol} znajduje się w fazie konsolidacji. Zmienność {volatility:.1f}% sugeruje, że ruch w którąkolwiek stronę jest możliwy. Wskaźnik skrętu k={k:.2f} wskazuje na umiarkowane opóźnienie.",
            "probability": 55 + int(abs(k) * 5),
            "confidence": 70,
            "action": "TRZYMAJ",
            "entry": None,
            "stop_loss": None,
            "take_profit": None
        },
        {
            "id": 3,
            "type": "samospełniająca",
            "statement": f"Optymizm na rynku {symbol} jest podtrzymywany przez rosnące wolumeny, ale historia pokazuje, że przy k={k:.2f} takie układy często kończą się nagłymi ruchami. Rekomendujemy ostrożność.",
            "probability": 50 + int(abs(k) * 8),
            "confidence": 65,
            "action": "TRZYMAJ" if k < 0 else "KUP",
            "entry": None,
            "stop_loss": None,
            "take_profit": None
        }
    ]
    return theses

# ------------------ ENDPOINTY ------------------
@app.get("/")
def root():
    return {"message": "TIMDR API – Boundary-Matter", "version": "1.0"}

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.post("/predict")
def predict(request: PredictRequest):
    """Pełna prognoza – metryki + 3 tezy + sygnał."""
    data = fetch_yfinance(request.symbol, request.period)
    close = data["close"]
    
    last = close[-1]
    sma10 = sum(close[-10:]) / 10
    sma30 = sum(close[-30:]) / 30 if len(close) >= 30 else sma10
    change = (last / close[0] - 1) * 100 if close[0] > 0 else 0
    
    metrics = {
        "last_price": round(last, 2),
        "sma10": round(sma10, 2),
        "sma30": round(sma30, 2),
        "change_pct": round(change, 2),
        "k_used": request.k,
        "days": len(close)
    }
    
    theses = generate_theses(data, request.k)
    signal = generate_signal(close, request.k)
    
    return {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "symbol": request.symbol,
        "period": request.period,
        "k": request.k,
        "metrics": metrics,
        "theses": theses,
        "signal": signal
    }

@app.post("/signal")
def signal(request: SignalRequest):
    """Uproszczony endpoint – tylko KUP / SPRZEDAJ / TRZYMAJ."""
    data = fetch_yfinance(request.symbol, request.period)
    close = data["close"]
    result = generate_signal(close, request.k)
    return {
        "action": result["action"],
        "price": result["price"],
        "probability": result["probability"],
        "timestamp": datetime.now().isoformat(),
        "symbol": request.symbol,
        "k": request.k
    }

@app.post("/ohlcv")
def get_ohlcv(request: PredictRequest):
    """Pobiera surowe dane OHLCV z Yahoo Finance."""
    data = fetch_yfinance(request.symbol, request.period)
    return {
        "symbol": data["symbol"],
        "period": data["period"],
        "dates": data["date"],
        "open": data["open"],
        "high": data["high"],
        "low": data["low"],
        "close": data["close"],
        "volume": data["volume"],
        "last_update": data["last_update"]
    }

# ------------------ URUCHOMIENIE ------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)