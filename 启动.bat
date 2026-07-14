@echo off
cd /d "%~dp0"

if not exist "app.py" (
    echo [ERROR] app.py not found in %cd%
    pause
    exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10 or later and add it to PATH.
    pause
    exit /b 1
)

echo.
echo   ============================================
echo      Kaoyan Study Assistant
echo      http://localhost:8505
echo   ============================================
echo.
echo   Starting server, please wait...
echo   Browser will open automatically once ready
echo   ============================================

start "" /MIN /D "%~dp0" python -m streamlit run app.py --server.port 8505 --server.headless true --server.fileWatcherType none

set /a T=0
:wait
timeout /t 2 /nobreak >nul
set /a T+=2
netstat -ano 2>nul | find ":8505" | find "LISTENING" >nul
if %errorlevel%==0 goto open
if %T% lss 60 goto wait

echo   [WARN] Timeout after 60s. Check: http://localhost:8505
pause
exit /b 1

:open
echo   Server ready, opening browser...
start http://localhost:8505
echo.
echo   Browser opened. Press any key to close this window.
echo   (Server will keep running in background)
pause >nul
