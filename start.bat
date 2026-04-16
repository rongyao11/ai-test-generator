@echo off
chcp 65001 >nul
echo ========================================
echo   AI Test Case Generator
echo ========================================
echo.

cd /d "%~dp0"

echo [1/2] Starting FastAPI backend on http://127.0.0.1:8000 ...
start "AI-Test-Backend" python main.py

echo [2/2] Starting Streamlit UI on http://localhost:8501 ...
start "AI-Test-UI" streamlit run ui\app.py

echo.
echo ========================================
echo   Backend:   http://127.0.0.1:8000
echo   API Docs:  http://127.0.0.1:8000/docs
echo   UI:        http://localhost:8501
echo ========================================
echo.
echo Press Ctrl+C to stop both services, or close this window.
pause
