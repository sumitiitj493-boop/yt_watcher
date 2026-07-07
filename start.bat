@echo off
:: ─────────────────────────────────────────────────────
:: YT Private Suite — Local Launcher (Windows)
:: Starts both backend + frontend from source.
:: ─────────────────────────────────────────────────────

echo ╔══════════════════════════════════════════╗
echo ║   YT Private Suite - Local Launcher     ║
echo ╚══════════════════════════════════════════╝
echo.

:: ── Backend ──────────────────────────────────────
echo [1/2] Starting backend on http://localhost:8005 ...
cd /d "%~dp0backend"

:: Try common Python paths
set PYTHON=
for %%p in (python python3 py) do (
    where %%p >nul 2>nul
    if not errorlevel 1 set PYTHON=%%p
)
if "%PYTHON%"=="" (
    echo ERROR: Python not found. Install Python and try again.
    pause
    exit /b 1
)

:: Install deps
%PYTHON% -m pip install -q -r requirements.txt

:: Start backend in new window
start "YT Suite Backend" %PYTHON% -m uvicorn main:app --host 127.0.0.1 --port 8005

cd /d "%~dp0"

:: ── Frontend ─────────────────────────────────────
echo [2/2] Starting frontend on http://localhost:8080 ...
cd /d "%~dp0frontend"

:: Check Node
where node >nul 2>nul
if errorlevel 1 (
    echo ERROR: Node.js not found. Install Node.js and try again.
    pause
    exit /b 1
)

:: Install deps if needed
if not exist node_modules (
    echo       Installing npm dependencies (one-time) ...
    call npm install
)

:: Start frontend dev server
start "YT Suite Frontend" npm run dev

cd /d "%~dp0"

echo.
echo ┌──────────────────────────────────────────┐
echo │  Backend  → http://localhost:8005        │
echo │  Frontend → http://localhost:8080        │
echo │                                          │
echo │  Open http://localhost:8080 in browser   │
echo │  Close the terminal windows to stop      │
echo └──────────────────────────────────────────┘
echo.

pause
