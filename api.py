"""
api.py — TIMDR 2.0 (analizator-gieldowy-2.0), API + dashboard w JEDNYM procesie
=================================================================================
Oryginalny projekt (jbackk-lang/analizator-gieldowy-2.0) uruchamiał dwa
osobne procesy na dwóch portach: FastAPI (api.py, port 8000) + Streamlit
(app.py, port 8501), połączone przez HTTP. Ten plik zachowuje CAŁĄ logikę
API (te same endpointy: /predict, /signal, /ohlcv + ten sam parametr
skrętu k), ale dodatkowo SERWUJE dashboard (static/dashboard.html) z tego
samego procesu i portu — dokładnie tak jak w analizator-gieldowy (v1):
jeden `run.bat`, jeden port, żadnego osobnego terminala dla Streamlit.

Endpointy:
  GET  /            -> dashboard (static/dashboard.html)
  GET  /api         -> komunikat powitalny (JSON, zgodność z oryginałem)
  GET  /health       -> status API
  POST /predict      -> pełna prognoza (metryki + 3 tezy + sygnał)
  POST /signal        -> uproszczony sygnał: KUP / SPRZEDAJ / TRZYMAJ
  POST /ohlcv         -> surowe dane OHLCV (dla wykresów)
  GET  /docs          -> automatyczna dokumentacja Swagger (FastAPI, "za darmo")

WAŻNE: pobieranie żywych danych przez yfinance wymaga internetu na
komputerze, na którym to uruchamiasz. Ustaw "use_demo": true w body
requestu (albo kliknij "Dane demo" w dashboardzie), żeby zobaczyć
działanie na syntetycznych, jawnie oznaczonych danych.
"""

import os
from datetime import datetime
from typing import List, Optional

import numpy as np
import yfinance as yf
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from demo_data import generate_demo_ohlc

# ------------------ INICJALIZACJA ------------------
app = FastAPI(
    title="TIMDR API – Boundary-Matter (analizator-gieldowy-2.0)",
    description="API do analizy skrętu informacji (k) na danych giełdowych",
    version="2.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


# ------------------ MODELE DANYCH ------------------
class PredictRequest(BaseModel):
    symbol: str = "AAPL"
    period: str = "6mo"
    k: float = -0.75
    use_demo: bool = False


class SignalRequest(BaseModel):
    symbol: str = "AAPL"
    period: str = "1mo"
    k: float = -0.75
    use_demo: bool = False


# ------------------ FUNKCJE POMOCNICZE ------------------
def fetch_yfinance(symbol: str, period: str, use_demo: bool = False) -> dict:
    """Pobiera dane z Yahoo Finance albo (use_demo=True / symbol=='DEMO') zwraca
    syntetyczne dane demo - patrz demo_data.py."""
    if use_demo or symbol.strip().upper() == "DEMO":
        return generate_demo_ohlc(symbol="DEMO", period=period)

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)

        if hist.empty:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Brak danych dla '{symbol}' (period='{period}'). "
                    "Jeśli masz przestarzałą wersję yfinance, Yahoo Finance "
                    "może zwracać puste dane z powodu ochrony antybotowej "
                    "- spróbuj: python -m pip install --upgrade yfinance. "
                    "Albo ustaw \"use_demo\": true, żeby zobaczyć działanie "
                    "na danych syntetycznych."
                ),
            )

        return {
            "open": hist["Open"].tolist(),
            "high": hist["High"].tolist(),
            "low": hist["Low"].tolist(),
            "close": hist["Close"].tolist(),
            "volume": hist["Volume"].tolist(),
            "date": hist.index.strftime("%Y-%m-%d").tolist(),
            "symbol": symbol,
            "period": period,
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd Yahoo Finance: {str(e)}")


def _sma(values: List[float], window: int) -> float:
    """
    Średnia krocząca z OSTATNICH `window` wartości.

    POPRAWKA (Bug #1, znaleziony przy testowaniu tego API): oryginalny kod
    liczył `sum(close[-10:]) / 10` — jeśli seria ma MNIEJ niż 10 wartości
    (np. bardzo krótki `period` w rodzaju "5d", albo świeżo notowana
    spółka z krótką historią), `close[-10:]` zwraca WSZYSTKIE dostępne
    wartości (Python nie rzuca błędu przy zbyt krótkim wycinku), ale suma
    i tak jest dzielona przez SZTYWNE 10 — dając cichy, błędny wynik (np.
    dla 5 wartości ~[100..110] zwracało sma10=52.5 zamiast poprawnych
    105.0 — dokładnie o połowę za mało, bo dzielone przez 10 zamiast
    przez 5). Błąd nie crashuje, więc łatwo przeoczyć - po prostu psuje
    liczby pokazywane użytkownikowi (w tym treść wygenerowanych "tez").
    Naprawiono: dzielimy zawsze przez FAKTYCZNĄ liczbę uwzględnionych
    wartości, nie przez nominalne rozmiar okna.
    """
    window_vals = values[-window:]
    if not window_vals:
        return 0.0
    return sum(window_vals) / len(window_vals)


def generate_signal(close_prices: List[float], k: float) -> dict:
    """Generuje sygnał KUP / SPRZEDAJ / TRZYMAJ."""
    if len(close_prices) < 30:
        return {
            "action": "TRZYMAJ",
            "price": close_prices[-1] if close_prices else 0,
            "probability": 50,
            "reason": "Za mało danych",
        }

    last = close_prices[-1]
    sma10 = _sma(close_prices, 10)
    sma30 = _sma(close_prices, 30)

    if sma10 > sma30 and last > sma10:
        base_signal = "KUP"
        base_prob = 65
    elif sma10 < sma30 and last < sma10:
        base_signal = "SPRZEDAJ"
        base_prob = 65
    else:
        base_signal = "TRZYMAJ"
        base_prob = 50

    # ── Korekta o k ───────────────────────────────────────────────────────
    # POPRAWKA (Bug #2): oryginalny kod, gdy ekstremalne |k| obniżało
    # base_prob poniżej progu 35 i degradowało sygnał do "TRZYMAJ", NIE
    # resetował base_prob z powrotem do sensownej wartości - zostawało to,
    # co wyszło z (już nieaktualnej) matematyki KUP/SPRZEDAJ, więc końcowy
    # wynik mógł wyglądać jak "TRZYMAJ - 5%" (mylące, bo TRZYMAJ nie ma
    # naturalnego kierunku ufności). Naprawiono: przy degradacji do
    # TRZYMAJ, prawdopodobieństwo wraca do neutralnej wartości 50.
    # (W domyślnym zakresie suwaka k z dashboardu, -1.5..1.5, i tak się to
    # nie zdarzało - próg wymagał |k|>2.0 - ale endpoint jest wywoływalny
    # też bezpośrednio przez /docs, więc naprawiono defensywnie.)
    if k < 0:
        if base_signal == "KUP":
            base_prob = base_prob - int(abs(k) * 15)
            if base_prob < 35:
                base_signal = "TRZYMAJ"
                base_prob = 50
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
                base_prob = 50

    return {
        "action": base_signal,
        "price": round(last, 2),
        "probability": min(100, max(0, base_prob)),
        "reason": f"SMA10={sma10:.2f}, SMA30={sma30:.2f}, k={k:.2f}",
    }


def generate_theses(data: dict, k: float) -> list:
    """Generuje 3 sprzeczne tezy."""
    close = data["close"]
    symbol = data["symbol"]
    last = close[-1]
    sma10 = _sma(close, 10)
    sma30 = _sma(close, 30)

    change = (last / close[0] - 1) * 100 if close[0] > 0 else 0
    window20 = close[-20:]
    volatility = (
        (max(window20) - min(window20)) / min(window20) * 100
        if window20 and min(window20) > 0
        else 0
    )

    theses = [
        {
            "id": 1,
            "type": "kontratrendowa",
            "statement": (
                f"Pomimo że rynek {symbol} wzrósł o {change:.1f}% w ostatnim okresie, "
                f"struktura skrętu (k={k:.2f}) sugeruje możliwość korekty. "
                f"SMA10={sma10:.2f} vs SMA30={sma30:.2f}."
            ),
            "probability": min(100, 60 + int(abs(k) * 10)),
            "confidence": 75,
            "action": "SPRZEDAJ" if k < 0 else "KUP",
            "entry": round(last * 1.02, 2),
            "stop_loss": round(last * 1.05, 2),
            "take_profit": round(last * 0.97, 2),
        },
        {
            "id": 2,
            "type": "ambiwalentna",
            "statement": (
                f"Rynek {symbol} znajduje się w fazie konsolidacji. Zmienność "
                f"{volatility:.1f}% sugeruje, że ruch w którąkolwiek stronę jest "
                f"możliwy. Wskaźnik skrętu k={k:.2f} wskazuje na umiarkowane "
                f"opóźnienie."
            ),
            "probability": min(100, 55 + int(abs(k) * 5)),
            "confidence": 70,
            "action": "TRZYMAJ",
            "entry": None,
            "stop_loss": None,
            "take_profit": None,
        },
        {
            "id": 3,
            "type": "samospełniająca",
            "statement": (
                f"Optymizm na rynku {symbol} jest podtrzymywany przez rosnące "
                f"wolumeny, ale historia pokazuje, że przy k={k:.2f} takie układy "
                f"często kończą się nagłymi ruchami. Rekomendujemy ostrożność."
            ),
            "probability": min(100, 50 + int(abs(k) * 8)),
            "confidence": 65,
            "action": "TRZYMAJ" if k < 0 else "KUP",
            "entry": None,
            "stop_loss": None,
            "take_profit": None,
        },
    ]
    return theses


# ------------------ ENDPOINTY ------------------
@app.get("/")
def dashboard():
    """Serwuje dashboard (patrz analizator-gieldowy v1 - ten sam wzorzec:
    jeden port, jeden proces, żadnego osobnego Streamlita)."""
    return FileResponse(os.path.join(STATIC_DIR, "dashboard.html"))


@app.get("/api")
def root():
    return {"message": "TIMDR API – Boundary-Matter", "version": "2.1"}


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/predict")
def predict(request: PredictRequest):
    """Pełna prognoza – metryki + 3 tezy + sygnał."""
    data = fetch_yfinance(request.symbol, request.period, request.use_demo)
    close = data["close"]

    if len(close) < 2:
        raise HTTPException(status_code=400, detail=f"Za mało danych ({len(close)} świec) dla '{request.symbol}'.")

    last = close[-1]
    sma10 = _sma(close, 10)
    sma30 = _sma(close, 30)
    change = (last / close[0] - 1) * 100 if close[0] > 0 else 0

    metrics = {
        "last_price": round(last, 2),
        "sma10": round(sma10, 2),
        "sma30": round(sma30, 2),
        "change_pct": round(change, 2),
        "k_used": request.k,
        "days": len(close),
    }

    theses = generate_theses(data, request.k)
    signal = generate_signal(close, request.k)

    return {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "symbol": data["symbol"],
        "period": request.period,
        "k": request.k,
        "is_demo": request.use_demo or data["symbol"] == "DEMO",
        "metrics": metrics,
        "theses": theses,
        "signal": signal,
    }


@app.post("/signal")
def signal(request: SignalRequest):
    """Uproszczony endpoint – tylko KUP / SPRZEDAJ / TRZYMAJ."""
    data = fetch_yfinance(request.symbol, request.period, request.use_demo)
    close = data["close"]
    result = generate_signal(close, request.k)
    return {
        "action": result["action"],
        "price": result["price"],
        "probability": result["probability"],
        "timestamp": datetime.now().isoformat(),
        "symbol": data["symbol"],
        "k": request.k,
    }


@app.post("/ohlcv")
def get_ohlcv(request: PredictRequest):
    """Pobiera surowe dane OHLCV z Yahoo Finance (albo demo)."""
    data = fetch_yfinance(request.symbol, request.period, request.use_demo)
    return {
        "symbol": data["symbol"],
        "period": data["period"],
        "dates": data["date"],
        "open": data["open"],
        "high": data["high"],
        "low": data["low"],
        "close": data["close"],
        "volume": data["volume"],
        "last_update": data["last_update"],
    }


# ------------------ URUCHOMIENIE ------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
