@echo off
chcp 65001 >nul 2>&1
echo Stopping AI Test Case Generator services...

REM Kill by port (more precise)
for /f "tokens=5" %%a in ('netstat -ano ^| find ":8000" ^| find "LISTENING"') do (
    echo Killing process on port 8000: %%a
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| find ":8501" ^| find "LISTENING"') do (
    echo Killing process on port 8501: %%a
    taskkill /F /PID %%a >nul 2>&1
)

REM Also kill by window title as fallback
taskkill /F /FI "WINDOWTITLE eq AI-Test-Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq AI-Test-UI*" >nul 2>&1

echo Done. Services stopped.
pause
