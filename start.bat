@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo   AI Test Case Generator
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] Cleaning up old processes ...
for /f "tokens=5" %%a in ('netstat -ano ^| find ":8000" ^| find "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| find ":8501" ^| find "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo [2/4] Starting FastAPI backend on http://127.0.0.1:8000 ...
start "AI-Test-Backend" cmd /k "python -m uvicorn main:app --host 127.0.0.1 --port 8000"

echo [3/4] Waiting for backend to start ...
timeout /t 5 /nobreak >nul

echo [4/4] Starting Streamlit UI on http://localhost:8501 ...
start "AI-Test-UI" cmd /k "streamlit run ui\app.py --server.headless true"

echo.
echo ========================================
echo   Backend:   http://127.0.0.1:8000
echo   API Docs:  http://127.0.0.1:8000/docs
echo   UI:        http://localhost:8501
echo ========================================
echo.
pause
