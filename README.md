# TIMDR 2.0 — analizator-gieldowy-2.0 — API + Dashboard (jeden proces)

Naprawiona wersja [jbackk-lang/analizator-gieldowy-2.0](https://github.com/jbackk-lang/analizator-gieldowy-2.0):
parametryczny **skręt informacji (k)**, SMA10/SMA30, generator trzech
sprzecznych tez rynkowych (kontratrendowa / ambiwalentna /
samospełniająca) i sygnał KUP/SPRZEDAJ/TRZYMAJ na danych Yahoo Finance.

**Status: 13/13 testów przechodzi, 2 błędy znalezione i naprawione.**

## Uruchomienie

```
run.bat
```

Zainstaluje zależności i uruchomi `http://127.0.0.1:8000` w przeglądarce.
Dashboard startuje domyślnie na **danych demo** (przycisk "🎲 Dane demo").
Żeby pobrać prawdziwe dane, wybierz ticker i kliknij "▶ Analizuj (żywe
dane)" — wymaga to internetu na Twoim komputerze. Dokumentacja API
(Swagger, generowana automatycznie przez FastAPI) jest pod
`http://127.0.0.1:8000/docs`.

## Co zmieniono względem oryginału — "API podobne do wersji poprzedniej"

Oryginalny projekt uruchamiał **dwa osobne procesy na dwóch portach**:
`api.py` (FastAPI, port 8000) + `app.py` (Streamlit, port 8501),
połączone przez HTTP — trzeba było otwierać dwa okna terminala i dwie
karty przeglądarki. Poprosiłeś o API "podobne do wersji poprzedniej"
(czyli do `analizator-gieldowy` v1) — tam jest jeden proces, jeden
port, jeden `run.bat`.

Zrobiłem dokładnie to: **cała logika API pozostała bez zmian**
(te same endpointy, ten sam parametr `k`, te same 3 tezy), ale
`api.py` teraz **dodatkowo serwuje dashboard** (`static/dashboard.html`)
z tego samego portu — `GET /` zwraca dashboard zamiast starego komunikatu
JSON (który przeniesiono pod `GET /api`). Streamlit (`app.py`) nie
został usunięty — możesz go nadal uruchomić ręcznie, jeśli wolisz — ale
nie jest już wymagany do normalnego użytkowania.

## Znalezione błędy

### Bug 1 — sztywny dzielnik `10` w SMA10 dla krótkich serii

Oryginalny kod (w dwóch miejscach: `generate_theses()` i wewnątrz
`predict()`) liczył:
```python
sma10 = sum(close[-10:]) / 10
```
Jeśli seria danych ma **mniej niż 10** wartości (np. `period="5d"`,
albo świeżo notowana spółka z krótką historią), `close[-10:]` w
Pythonie po cichu zwraca WSZYSTKIE dostępne wartości (nie rzuca
błędu przy zbyt krótkim wycinku) — ale suma i tak jest dzielona przez
**sztywne 10**, a nie przez faktyczną liczbę uwzględnionych elementów.

Zweryfikowano bezpośrednio na 5-elementowej serii `[100, 102.5, 105,
107.5, 110]`:
```
poprawna średnia (suma / 5)         = 105.0
wynik oryginalnego kodu (suma / 10) = 52.5   <- dokładnie o połowę za mało
```
Błąd **nie crashuje** — więc łatwo go przeoczyć — po prostu cicho psuje
liczby pokazywane użytkownikowi, w tym treść wygenerowanych tez
(np. "SMA10=52." zamiast prawdziwych ~105).

**Naprawa:** dodano wspólną funkcję `_sma(values, window)`, która
zawsze dzieli przez `len(values[-window:])`, czyli faktyczną liczbę
uwzględnionych próbek, a nie przez nominalny rozmiar okna. Zastąpiono
nią obie zduplikowane, zepsute linijki.

### Bug 2 — niespójne `probability` po degradacji sygnału do TRZYMAJ

Gdy bardzo duże `|k|` obniżało `base_prob` poniżej progu 35 i
degradowało sygnał z KUP/SPRZEDAJ do TRZYMAJ, oryginalny kod **nie
resetował** `probability` z powrotem do neutralnej wartości — zostawał
wynik z (już nieaktualnej) matematyki KUP/SPRZEDAJ. Zweryfikowano: dla
serii rosnącej i `k=-4.0`, oryginalna logika zwracała `TRZYMAJ` z
`probability=5` — mylące, bo TRZYMAJ nie ma naturalnego kierunku
pewności, a 5% sugeruje coś zupełnie innego niż "trzymaj się z boku".

W domyślnym zakresie suwaka `k` w dashboardzie (-1.5..1.5) próg `|k|>2.0`
wymagany do zaobserwowania tego buga nie jest osiągalny — ale endpoint
jest wywoływalny bezpośrednio (np. przez `/docs` albo `curl`), więc
naprawiono defensywnie.

**Naprawa:** przy degradacji do TRZYMAJ, `probability` jest teraz
resetowane do neutralnych 50%.

### Obserwacja (nie błąd) — `data_fetcher.py` jest martwym kodem

`data_fetcher.py` definiuje własną, prawie identyczną kopię
`fetch_yfinance()`, ale `api.py` **nigdy jej nie importuje** — ma
swoją, osobną kopię tej samej logiki. Plik jest więc nieużywany
(martwy kod), strukturalnie podobny do osieroconego `timdr.py` w
katalogu głównym v1. Nie usunąłem go (może być używany gdzie indziej
albo planowany do dalszej integracji), ale warto o tym wiedzieć — jeśli
naprawisz coś w jednym pliku, pamiętaj że drugi kopiuje tę samą logikę
osobno.

## Co jest lepsze w wersji 2 (vs `analizator-gieldowy` v1)

Poprosiłeś, żebym zaznaczył, co v2 robi lepiej niż v1 — oto szczera
ocena, z plusami i minusami:

**Wielowariantowe tezy zamiast jednego wyniku.** v1 kończy analizę
jednym zagregowanym wynikiem TIMDR (`R_total` → klasa `obiekt`/
`pół-obiekt`/`szum`) — jedna liczba, jedna decyzja. v2 celowo generuje
**trzy sprzeczne tezy** (kontratrendowa, ambiwalentna, samospełniająca)
z osobnymi prawdopodobieństwami i poziomami wejścia/SL/TP. To lepiej
oddaje rzeczywistą niepewność rynku — zamiast udawać jedną pewną
odpowiedź, dashboard pokazuje wprost, że różne interpretacje tych
samych danych są możliwe, i zostawia wybór użytkownikowi.

**Parametr `k` jako jawny, przestrajalny bias.** W v1 wagi oceny
(sharpe 0.5 / winrate 0.3 / drawdown 0.2) są zaszyte na sztywno w
kodzie — zmiana wymaga edycji `core/timdr.py`. W v2 `k` (skręt
informacji) jest jawnym parametrem widocznym w dashboardzie (suwak),
który użytkownik przestawia w locie, żeby wyrazić własne nastawienie
(ostrożne / neutralne / kontynuacyjne) bez dotykania kodu.

**Walidacja requestów "za darmo".** FastAPI + Pydantic automatycznie
waliduje typy pól requestu (np. że `k` jest liczbą, `symbol` stringiem)
i zwraca czytelny błąd 422 przy złych danych, zanim kod w ogóle
zacznie działać. Flask (v1) sam z siebie tego nie robi — trzeba by to
pisać ręcznie.

**Automatyczna dokumentacja Swagger.** `/docs` w v2 daje interaktywną,
zawsze aktualną dokumentację API (można testować endpointy wprost z
przeglądarki) — w v1 trzeba czytać README, żeby wiedzieć jaki JSON
wysłać.

**Gdzie v1 wciąż wygrywa (dla równowagi):** v1 ma wektorowy backtester
z realnymi metrykami (Sharpe, winrate, max drawdown, equity curve z
symulowanego handlu) — v2 nie robi backtestu wcale, sygnał opiera się
wyłącznie na aktualnym SMA10/SMA30, bez sprawdzenia jak taka strategia
zachowałaby się historycznie. v1 też ma jeden, prosty, dobrze
przetestowany wynik liczbowy (R_total) łatwy do porównywania między
tickerami — trzy tezy v2 są bogatsze, ale trudniej je zredukować do
jednej decyzji "kup / nie kup" przy automatyzacji.

## Struktura repo

```
analizator-gieldowy-2.0/
├── api.py                # FastAPI - logika + serwowanie dashboardu (naprawiony, Bug 1-2)
├── api_original.py       # kopia oryginalnego api.py, do porównania (nieużywana)
├── demo_data.py           # syntetyczne dane demo (GBM, jawnie oznaczone)
├── app.py                 # oryginalny dashboard Streamlit (opcjonalny, nie wymagany)
├── data_fetcher.py         # oryginalny moduł danych (nieużywany przez api.py - patrz uwaga wyżej)
├── static/dashboard.html   # NOWY dashboard (Canvas 2D, bez CDN), serwowany z tego samego portu
├── test_api.py             # 13 testów, w tym regresje dla Bug 1-2
├── requirements.txt
└── run.bat                 # jeden proces, jeden port, wymusza upgrade yfinance
```

## API

| Endpoint | Metoda | Opis |
|---|---|---|
| `/` | GET | dashboard |
| `/api` | GET | komunikat powitalny (zgodność z oryginałem) |
| `/health` | GET | healthcheck |
| `/predict` | POST | `{"symbol":"AAPL","period":"6mo","k":-0.75,"use_demo":false}` — metryki + 3 tezy + sygnał |
| `/signal` | POST | uproszczony sygnał KUP/SPRZEDAJ/TRZYMAJ |
| `/ohlcv` | POST | surowe dane OHLCV (do wykresów) |
| `/docs` | GET | Swagger (automatyczny) |

## Testy

```
pip install -r requirements.txt
pytest -q
```
Wynik: **13/13 passed**.
