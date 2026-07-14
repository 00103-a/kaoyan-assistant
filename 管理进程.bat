@echo off
cd /d "%~dp0"
set "PORT=8505"

:menu
cls
set "PID="
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%PORT%" ^| findstr "LISTENING" 2^>nul') do set "PID=%%a"

echo.
echo   ============================================
echo      Kaoyan Study Assistant - Process Manager
echo   ============================================
echo.
if defined PID (
    echo   [ON]   Running  PID:%PID%  Port:%PORT%
    echo          http://localhost:%PORT%
) else (
    echo   [OFF]  Stopped
)
echo.
echo   [1] Start    [2] Stop    [3] Browser
echo   [0] Exit
echo.

set "choice="
set /p "choice=   Select: "

if "%choice%"=="1" goto start
if "%choice%"=="2" goto stop
if "%choice%"=="3" goto browser
if "%choice%"=="0" exit /b
goto menu

:start
if defined PID (
    echo   Already running (PID:%PID%)
    pause >nul
    goto menu
)
if not exist "app.py" (
    echo   app.py not found
    pause >nul
    goto menu
)
where python >nul 2>&1
if errorlevel 1 (
    echo   Python not found. Install Python 3.10 or later and add it to PATH.
    pause >nul
    goto menu
)
echo   Starting...
start "" /MIN /D "%~dp0" python -m streamlit run app.py --server.port %PORT% --server.headless true --server.fileWatcherType none

set /a N=0
:wait
timeout /t 2 /nobreak >nul
set /a N+=2
netstat -ano 2>nul | findstr ":%PORT%" | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo   Ready, opening browser...
    start http://localhost:%PORT%
    pause >nul
    goto menu
)
if %N% lss 60 goto wait
echo   Timeout, check streamlit.log
pause >nul
goto menu

:stop
if not defined PID (
    echo   Not running
    pause >nul
    goto menu
)
echo   Stopping PID %PID% ...
taskkill /PID %PID% /F >nul 2>&1
if errorlevel 1 taskkill /F /IM python.exe >nul 2>&1
echo   Stopped
pause >nul
goto menu

:browser
start http://localhost:%PORT%
goto menu
