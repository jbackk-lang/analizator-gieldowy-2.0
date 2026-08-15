@echo off
setlocal
cd /d "%~dp0"

echo === TIMDR 2.0 - analizator-gieldowy-2.0 ===
echo Instaluje zaleznosci (FastAPI, uvicorn, pandas, numpy)...
python -m pip install --quiet fastapi uvicorn pydantic numpy pandas httpx
if errorlevel 1 (
    echo BLAD: nie udalo sie zainstalowac zaleznosci. Sprawdz czy Python i pip sa zainstalowane.
    pause
    exit /b 1
)

REM WAZNE: yfinance zawsze dociagany do NAJNOWSZEJ wersji (--upgrade), tak
REM jak w run.bat wersji 1 - Yahoo Finance ma ochrone antybotowa i stare
REM wersje yfinance (bez curl_cffi) dostaja puste dane zamiast prawdziwych.
echo Aktualizuje yfinance do najnowszej wersji...
python -m pip install --quiet --upgrade yfinance
if errorlevel 1 (
    echo BLAD: nie udalo sie zainstalowac/zaktualizowac yfinance.
    pause
    exit /b 1
)

echo.
echo Uruchamiam serwer pod http://127.0.0.1:8000 ...
echo   - Dashboard (przycisk "Dane demo") dziala zawsze, dane syntetyczne.
echo   - Przycisk "Analizuj (zywe dane)" pobierze prawdziwe dane z Yahoo
echo     Finance, o ile ten komputer ma dostep do internetu.
echo   - Dokumentacja API (Swagger): http://127.0.0.1:8000/docs
echo.

start "" http://127.0.0.1:8000
python -m uvicorn api:app --host 127.0.0.1 --port 8000

pause
