@echo off
title Alpha Foundry — Launcher
echo.
echo  ╔═══════════════════════════════════════╗
echo  ║      QUANT ALPHA FOUNDRY v2.1         ║
echo  ║  yfinance + FRED + SEC EDGAR (free)   ║
echo  ╚═══════════════════════════════════════╝
echo.

:: ── 1. Start Python backend ────────────────────────────────────────────────
echo [1/3] Starting FastAPI backend on port 8000...
cd /d "%~dp0backend"

:: Create venv if it doesn't exist
if not exist ".venv" (
    echo      Creating Python virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate.bat

:: Always sync deps in case requirements.txt changed
echo      Syncing Python dependencies...
pip install -r requirements.txt --quiet

:: Launch backend in a new window
start "Alpha Foundry — Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\activate.bat && uvicorn main:app --port 8000 --reload"

:: ── 2. Install frontend deps if needed ────────────────────────────────────
echo [2/3] Checking frontend dependencies...
cd /d "%~dp0"
if not exist "node_modules" (
    echo      Installing npm packages (first run only)...
    npm install
)

:: ── 3. Launch frontend ─────────────────────────────────────────────────────
echo [3/3] Starting frontend on http://localhost:5173 ...
echo.
echo  Open your browser at:  http://localhost:5173
echo  Backend API docs:       http://localhost:8000/docs
echo  Data sources:           yfinance (prices) + FRED (macro) + SEC EDGAR (accounting)
echo  No API keys required.
echo.
npm run dev
