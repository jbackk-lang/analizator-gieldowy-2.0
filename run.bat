@echo off
title TIMDR - Boundary-Matter Launcher
echo ========================================
echo   TIMDR - Boundary-Matter Launcher
echo   (c) 2026
echo ========================================
echo.
echo [1/3] Sprawdzanie zaleznosci...
python -m pip install -r requirements.txt
echo [OK] Zaleznosci zainstalowane.
echo.
echo [2/3] Uruchamianie API (port 8000)...
start "TIMDR API" cmd /k "python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload"
echo [OK] API uruchomione w nowym oknie.
echo.
echo [3/3] Uruchamianie Streamlit Dashboard (port 8501)...
timeout /t 3 /nobreak > nul
start "TIMDR Dashboard" cmd /k "python -m streamlit run app.py"
echo [OK] Dashboard uruchomiony w nowym oknie.
echo.
echo ========================================
echo   Wszystko uruchomione!
echo   API:        http://localhost:8000
echo   Dashboard:  http://localhost:8501
echo ========================================
echo.
echo Aby zatrzymac, zamknij okna terminala.
pause