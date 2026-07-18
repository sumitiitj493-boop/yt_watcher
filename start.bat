@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "BACKEND_DIR=%ROOT%backend"
set "FRONTEND_DIR=%ROOT%frontend"
set "CHECK_ONLY=0"

if /I "%~1"=="--check" set "CHECK_ONLY=1"

echo +------------------------------------------+
echo ^|   YT Private Suite - Local Launcher     ^|
echo +------------------------------------------+
echo.

echo [1/3] Checking Python backend ...

set "PYTHON="
if exist "%ROOT%.venv\Scripts\python.exe" set "PYTHON=%ROOT%.venv\Scripts\python.exe"
if not defined PYTHON if exist "%BACKEND_DIR%\venv\Scripts\python.exe" set "PYTHON=%BACKEND_DIR%\venv\Scripts\python.exe"

if not defined PYTHON (
    for %%P in (python py python3) do (
        where %%P >nul 2>nul
        if not errorlevel 1 if not defined PYTHON set "PYTHON=%%P"
    )
)

if not defined PYTHON (
    echo ERROR: Python was not found. Install Python or create a virtualenv, then try again.
    pause
    exit /b 1
)

echo       Python: %PYTHON%

if not exist "%BACKEND_DIR%\requirements.txt" (
    echo ERROR: Backend requirements file not found: "%BACKEND_DIR%\requirements.txt"
    pause
    exit /b 1
)

pushd "%BACKEND_DIR%" >nul
"%PYTHON%" -m pip install -q -r requirements.txt
if errorlevel 1 (
    popd >nul
    echo ERROR: Failed to install backend dependencies.
    pause
    exit /b 1
)
popd >nul

echo [2/3] Checking frontend ...

where node >nul 2>nul
if errorlevel 1 (
    echo ERROR: Node.js was not found. Install Node.js and try again.
    pause
    exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
    echo ERROR: npm was not found. Reinstall Node.js with npm enabled.
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\package.json" (
    echo ERROR: Frontend package file not found: "%FRONTEND_DIR%\package.json"
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\node_modules" (
    echo       Installing npm dependencies one time ...
    pushd "%FRONTEND_DIR%" >nul
    call npm install
    if errorlevel 1 (
        popd >nul
        echo ERROR: Failed to install frontend dependencies.
        pause
        exit /b 1
    )
    popd >nul
)

if "%CHECK_ONLY%"=="1" (
    echo.
    echo Launcher check passed.
    exit /b 0
)

echo [3/3] Starting services ...
echo       Backend:  http://localhost:8005
echo       Frontend: http://localhost:8080
echo.

start "YT Suite Backend" powershell.exe -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '%BACKEND_DIR%'; & '%PYTHON%' -m uvicorn main:app --host 127.0.0.1 --port 8005"
if errorlevel 1 (
    echo ERROR: Could not open the backend PowerShell window.
    pause
    exit /b 1
)

start "YT Suite Frontend" powershell.exe -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '%FRONTEND_DIR%'; npm.cmd run dev"
if errorlevel 1 (
    echo ERROR: Could not open the frontend PowerShell window.
    pause
    exit /b 1
)

echo +------------------------------------------+
echo ^|  Backend  - http://localhost:8005       ^|
echo ^|  Frontend - http://localhost:8080       ^|
echo ^|                                          ^|
echo ^|  Open http://localhost:8080 in browser  ^|
echo ^|  Close the PowerShell windows to stop   ^|
echo +------------------------------------------+
echo.

pause
