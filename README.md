
# 📊 TIMDR analizator-gieldowy-2.0

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-FF4B4B)
![License](https://img.shields.io/badge/license-MIT-green)

Aplikacja analityczno-symulacyjna wykorzystująca koncepcję **skrętu informacji ($k$)** do analizy szeregów czasowych oraz generowania wiel wariantowych tez rynkowych na podstawie rzeczywistych danych giełdowych (Yahoo Finance).

---

## 🚀 Główny opis projektu

**TIMDR (analizator-gieldowy-2.0)** to hybrydowy system złożony z backendu API oraz interaktywnego panelu kontrolnego (Dashboard). System pobiera aktualne oraz historyczne dane finansowe, wylicza wskaźniki dynamiki trendu (m.in. SMA10, SMA30) oraz stosuje parametryczny modyfikator skrętu ($k$) do generowania scenariuszy handlowych:
- **Kontratrendowych** (korekcyjnych),
- **Ambiwalentnych** (konsolidacyjnych),
- **Samospełniających się** (impulsowych).

---

## 🛠️ Architektura projektu

* **`api.py`** – Serwer FastAPI wystawiający punkty końcowe (`/predict`, `/signal`, `/ohlcv`) do obliczeń i pobierania danych.
* **`app.py`** – Interfejs graficzny zbudowany w bibliotece Streamlit z wizualizacjami Plotly.
* **`data_fetcher.py`** – Moduł pobierania i przetwarzania danych z Yahoo Finance / Alpha Vantage.
* **`run.bat`** – Skrypt uruchamiający cały stos technologiczny jednym kliknięciem (zgodny z Windows Device Guard).

---

## 💻 Wymagania systemowe

- Python **3.10** lub nowszy
- System operacyjny: **Windows / Linux / macOS**

---

## ⚡ Szybki start (Uruchomienie)

### Metoda 1: Automatyczna (Windows `.bat`)
Krok polega na uruchomieniu skryptu wsadowego w głównym katalogu projektu:
```cmd
run.bat

Uwaga: Skrypt run.bat jest dostosowany do wymogów Windows Device Guard / AppLocker – uruchamia moduły bezpośrednio przez proces Pythona (python -m ...).Metoda 2: Ręczna (Terminal / PowerShell)Zainstaluj zależności:Bashpython -m pip install -r requirements.txt
Uruchom serwer API (FastAPI):Bashpython -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
W nowym oknie terminala uruchom Dashboard (Streamlit):Bashpython -m streamlit run app.py
🌐 Punkty dostępowe (Endpoints)Po uruchomieniu aplikacja dostępna jest pod adresami:UsługaAdres URLOpisStreamlit Dashboardhttp://localhost:8501Panel użytkownika z wykresamiFastAPI Backendhttp://localhost:8000Interfejs programistyczny APIDokumentacja Swaggerhttp://localhost:8000/docsInteraktywna dokumentacja API⚙️ Parametryzacja modelu ($k$)$k < 0$ (Lewoskrętność): Model przyjmuje konserwatywne założenia z opóźnieniem cykli i wyższą wrażliwością na sygnały sprzedaży / korekty.$k > 0$ (Prawoskrętność): Model zwiększa wagę dla kontynuacji trendu i sygnałów zakupu.Wartość domyślna ($k = -0.75$): Zoptymalizowana pod kątem oporu w warunkach podwyższonej zmienności.📝 LicencjaProjekt udostępniany na licencji MIT. Szegóły w pliku LICENSE.
