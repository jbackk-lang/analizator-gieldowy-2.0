"""
test_api.py — testy dla api.py (analizator-gieldowy-2.0)

Dokumentuje 2 błędy znalezione w oryginalnym api.py (patrz README.md):

  Bug 1: `sma10 = sum(close[-10:]) / 10` — dla serii krótszej niż 10
         wartości (np. period="5d") dzieli sumę przez SZTYWNE 10 zamiast
         przez faktyczną liczbę elementów, dając cichy, błędny wynik
         (np. suma z 5 wartości ~525 / 10 = 52.5, zamiast poprawnych
         525 / 5 = 105.0 — dokładnie o połowę za mało).
  Bug 2: gdy ekstremalne |k| degraduje sygnał KUP/SPRZEDAJ do TRZYMAJ,
         oryginalny kod NIE resetował `probability` z powrotem do
         neutralnej wartości — zostawiał nieaktualną matematykę
         KUP/SPRZEDAJ (np. "TRZYMAJ - 5%"), co jest mylące.

Każdy test poniżej odtwarza oryginalną (zepsutą) logikę inline i pokazuje
błędny wynik, a następnie weryfikuje że naprawiona wersja w api.py
zwraca poprawny wynik.
"""

import pytest
from fastapi.testclient import TestClient

import api
from demo_data import generate_demo_ohlc


@pytest.fixture()
def client():
    return TestClient(api.app)


# ---------------------------------------------------------------------
# Bug 1: sztywny dzielnik 10 w SMA
# ---------------------------------------------------------------------

def test_bug1_sma_naprawiona_dzieli_przez_faktyczna_dlugosc():
    close = [100.0, 102.5, 105.0, 107.5, 110.0]  # tylko 5 wartości
    assert api._sma(close, 10) == pytest.approx(105.0)  # poprawna średnia z 5


def test_bug1_reprodukcja_oryginalnego_bledu_sztywnego_dzielnika():
    """Odtwarza dokładnie oryginalną (zepsutą) linijkę kodu i pokazuje,
    że dawała błędny wynik dla serii krótszej niż okno."""
    close = [100.0, 102.5, 105.0, 107.5, 110.0]

    def original_sma10(close_prices):
        return sum(close_prices[-10:]) / 10  # SZTYWNE 10, bez względu na len()

    buggy = original_sma10(close)
    correct = api._sma(close, 10)
    assert buggy == pytest.approx(52.5)      # błędny wynik oryginału
    assert correct == pytest.approx(105.0)   # poprawny wynik po naprawie
    assert buggy != correct


def test_bug1_predict_endpoint_krotki_okres_daje_poprawne_sma(client):
    """Regresja end-to-end: /predict z bardzo krótką serią (period='5d')
    demo musi zwrócić SMA10 policzone z faktycznej liczby świec, nie
    sztucznie zaniżone przez dzielenie przez 10."""
    r = client.post("/predict", json={"symbol": "DEMO", "period": "5d", "k": -0.75, "use_demo": True})
    assert r.status_code == 200
    data = r.json()
    close = generate_demo_ohlc("DEMO", "5d")["close"]
    expected_sma10 = sum(close) / len(close)  # bo len(close) < 10
    assert data["metrics"]["sma10"] == pytest.approx(expected_sma10, abs=0.01)


# ---------------------------------------------------------------------
# Bug 2: niespójne probability po degradacji do TRZYMAJ
# ---------------------------------------------------------------------

def test_bug2_degradacja_do_trzymaj_resetuje_probability():
    """Przy bardzo dużym |k| (poza zakresem suwaka w dashboardzie, ale
    osiągalnym przez bezpośrednie wywołanie API/Swagger) KUP powinno
    degradować do TRZYMAJ z NEUTRALNYM prawdopodobieństwem (50), a nie
    zostawiać starą, nieaktualną liczbę."""
    # Seria rosnąca -> KUP przed korektą o k
    close = [100 + i * 0.5 for i in range(40)]
    result = api.generate_signal(close, k=-4.0)  # |k|=4 -> baza spada poniżej 35
    assert result["action"] == "TRZYMAJ"
    assert result["probability"] == 50


def test_bug2_reprodukcja_oryginalnego_bledu_niespojnego_prawdopodobienstwa():
    """Odtwarza oryginalną logikę i pokazuje, że dawała TRZYMAJ z
    myląco niskim prawdopodobieństwem (pozostałość z matematyki KUP)."""
    close = [100 + i * 0.5 for i in range(40)]
    last = close[-1]
    sma10 = sum(close[-10:]) / 10
    sma30 = sum(close[-30:]) / 30

    def original_logic(k):
        if sma10 > sma30 and last > sma10:
            base_signal, base_prob = "KUP", 65
        elif sma10 < sma30 and last < sma10:
            base_signal, base_prob = "SPRZEDAJ", 65
        else:
            base_signal, base_prob = "TRZYMAJ", 50

        if k < 0:
            if base_signal == "KUP":
                base_prob = base_prob - int(abs(k) * 15)
                if base_prob < 35:
                    base_signal = "TRZYMAJ"  # bug: probability NIE resetowane
        return base_signal, min(100, max(0, base_prob))

    action, prob = original_logic(-4.0)
    assert action == "TRZYMAJ"
    assert prob == 5, "oryginalny bug: TRZYMAJ z myląco niskim prawdopodobieństwem (5%)"
    # naprawiona wersja daje spójne 50%:
    fixed = api.generate_signal(close, k=-4.0)
    assert fixed["probability"] == 50


# ---------------------------------------------------------------------
# Testy end-to-end / zdroworozsądkowe
# ---------------------------------------------------------------------

def test_dashboard_serwowany_na_glownej_sciezce(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "TIMDR" in r.text


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_predict_demo_ma_3_tezy_i_sygnal(client):
    r = client.post("/predict", json={"symbol": "DEMO", "period": "6mo", "k": -0.75, "use_demo": True})
    assert r.status_code == 200
    data = r.json()
    assert len(data["theses"]) == 3
    types = {t["type"] for t in data["theses"]}
    assert types == {"kontratrendowa", "ambiwalentna", "samospełniająca"}
    assert data["signal"]["action"] in ("KUP", "SPRZEDAJ", "TRZYMAJ")
    assert data["is_demo"] is True


def test_predict_symbol_demo_dziala_bez_flagi_use_demo(client):
    """symbol='DEMO' samo w sobie (bez use_demo=True) też powinno użyć
    danych syntetycznych, nie próbować pytać Yahoo Finance o spółkę 'DEMO'."""
    r = client.post("/predict", json={"symbol": "DEMO", "period": "6mo", "k": 0.0})
    assert r.status_code == 200
    assert r.json()["is_demo"] is True


def test_ohlcv_demo(client):
    r = client.post("/ohlcv", json={"symbol": "DEMO", "period": "1y", "k": 0.0, "use_demo": True})
    assert r.status_code == 200
    data = r.json()
    assert len(data["dates"]) == len(data["close"]) == 252


def test_signal_endpoint_demo(client):
    r = client.post("/signal", json={"symbol": "DEMO", "period": "6mo", "k": -0.75, "use_demo": True})
    assert r.status_code == 200
    data = r.json()
    assert "action" in data and "probability" in data


def test_predict_k_dodatnie_i_ujemne_daja_rozne_tezy(client):
    r_neg = client.post("/predict", json={"symbol": "DEMO", "period": "6mo", "k": -1.0, "use_demo": True}).json()
    r_pos = client.post("/predict", json={"symbol": "DEMO", "period": "6mo", "k": 1.0, "use_demo": True}).json()
    # k wpływa na kierunek pierwszej tezy (kontratrendowa)
    assert r_neg["theses"][0]["action"] == "SPRZEDAJ"
    assert r_pos["theses"][0]["action"] == "KUP"


def test_generate_signal_za_malo_danych_nie_crashuje():
    result = api.generate_signal([], k=-0.75)
    assert result["action"] == "TRZYMAJ"
    assert result["price"] == 0
