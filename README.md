<div align="center">

<br>

```
  ██████╗  ██╗   ██╗  █████╗  ███╗  ██╗ ████████╗      
 ██╔═══██╗ ██║   ██║ ██╔══██╗ ████╗ ██║    ██╔══╝      
 ██║   ██║ ██║   ██║ ███████║ ██╔██╗██║    ██║         
 ██║▄▄ ██║ ██║   ██║ ██╔══██║ ██║╚████║    ██║         
 ╚██████╔╝ ╚██████╔╝ ██║  ██║ ██║ ╚███║    ██║         
  ╚══▀▀═╝   ╚═════╝  ╚═╝  ╚═╝ ╚═╝  ╚══╝   ╚═╝         
                                                         
  █████╗  ██╗     ██████╗ ██╗  ██╗ █████╗               
 ██╔══██╗ ██║     ██╔══██╗██║  ██║██╔══██╗              
 ███████║ ██║     ██████╔╝███████║███████║              
 ██╔══██║ ██║     ██╔═══╝ ██╔══██║██╔══██║              
 ██║  ██║ ███████╗██║     ██║  ██║██║  ██║              
 ╚═╝  ╚═╝ ╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝             
                                                         
 ███████╗ ██████╗ ██╗   ██╗ ███╗  ██╗ ██████╗ ██████╗ ██╗   ██╗
 ██╔════╝██╔═══██╗██║   ██║ ████╗ ██║██╔══██╗██╔══██╗╚██╗ ██╔╝
 █████╗  ██║   ██║██║   ██║ ██╔██╗██║██║  ██║██████╔╝ ╚████╔╝ 
 ██╔══╝  ██║   ██║██║   ██║ ██║╚████║██║  ██║██╔══██╗  ╚██╔╝  
 ██║     ╚██████╔╝╚██████╔╝ ██║ ╚███║██████╔╝██║  ██║   ██║   
 ╚═╝      ╚═════╝  ╚═════╝  ╚═╝  ╚══╝╚═════╝ ╚═╝  ╚═╝   ╚═╝   
```

<br>

**⟡ Institutional-Grade Quantitative Alpha Research & Execution Platform ⟡**

<br>

[![Live Demo](https://img.shields.io/badge/🌐%20LIVE%20DEMO-fountry.netlify.app-c9a96e?style=for-the-badge)](https://fountry.netlify.app)

<br>

[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Vite](https://img.shields.io/badge/Vite-5-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev)

<br>

[![Signals](https://img.shields.io/badge/Alpha%20Signals-15%20Factors-c9a96e?style=flat-square&logo=chartdotjs)](https://fountry.netlify.app)
[![Data](https://img.shields.io/badge/Market%20Data-Free%20·%20No%20API%20Key-4ade80?style=flat-square&logo=yahoo)](https://fountry.netlify.app)
[![Agents](https://img.shields.io/badge/Autonomous%20Agents-7%20Active-c084fc?style=flat-square&logo=probot)](https://fountry.netlify.app)
[![Deploy](https://img.shields.io/badge/Hosted%20on-Netlify-00C7B7?style=flat-square&logo=netlify)](https://fountry.netlify.app)
[![License](https://img.shields.io/badge/License-MIT-facc15?style=flat-square)](LICENSE)

<br>

> *Research signals. Test regimes. Execute autonomously.*

</div>

---

<br>

## ◈ Overview

**Fountry** is a full-stack quantitative research platform that mirrors the internal tooling used at institutional asset managers. It covers the complete alpha lifecycle — from raw signal research and walk-forward validation, through regime stress-testing and execution analytics, to live paper trading with autonomous agents.

Everything runs **free with no API keys required** for core functionality. Market data comes from `yfinance`, macro signals from the Federal Reserve's public FRED API, and accounting signals from SEC EDGAR filings.

<br>

---

## ◈ Platform Views

<br>

<div align="center">

| View | What You Get |
|:----:|:------------|
| **⚗ FOUNTRY** | Signal universe command centre — 15 factor signals ranked by IC, ICIR, net Sharpe and capacity. Promoted vs. under-review pipeline. |
| **🔬 SIGNAL LAB** | Full deep-dive on any signal: 10-year walk-forward OOS results, IC decay curve, regime-conditional performance matrix. |
| **⚡ STRESS TEST** | Cross-signal performance heatmap across 5 market regimes (Bull, Bear, Crisis, Range-bound, Inflationary). Live FRED macro overlay. |
| **📋 EXECUTION** | Real-time trade blotter with VWAP slippage, market impact decomposition (VWAP / TWAP / IS), and algo attribution. |
| **📊 PORTFOLIO** | Equity curve vs benchmark, Fama-French factor attribution, full risk decomposition (VaR, CVaR, Sharpe, Sortino, Calmar). |
| **🤖 AGENTS** | Live autonomous agents dashboard — execution bot, AI commentary engine, background scheduler, circuit breaker controls. |

</div>

<br>

---

## ◈ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          FOUNTRY                                │
├─────────────────────────┬───────────────────────────────────────┤
│      FRONTEND           │           BACKEND                      │
│  React 18 + Vite 5      │       FastAPI + uvicorn               │
│  Single JSX component   │       Async lifespan startup          │
│  Bebas Neue / Mono UI   │       Port 8000                       │
├─────────────────────────┴───────────────────────────────────────┤
│                        DATA LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   yfinance   │  │  FRED (Fed)  │  │  SEC EDGAR XBRL      │  │
│  │  60 tickers  │  │  Macro data  │  │  10-K / 10-Q filings │  │
│  │  No API key  │  │  No API key  │  │  No API key          │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                       SIGNAL ENGINE                              │
│  15 cross-sectional equity factors  ·  Walk-forward 10yr OOS   │
│  HMM 3-state regime detector (hmmlearn)  ·  IC decay curves    │
├─────────────────────────────────────────────────────────────────┤
│                      AGENT LAYER (7 agents)                      │
│  ⚡ Execution  🧠 LLM Commentary  🛡 Risk  ⭐ Scorer           │
│  💬 Sentiment  👁 Vision  🕐 Scheduler                          │
└─────────────────────────────────────────────────────────────────┘
```

<br>

---

## ◈ Quick Start

### Prerequisites
- **Python** 3.11+
- **Node.js** 18+

<br>

### ▶ One Command (Windows)

```bat
start.bat
```
Bootstraps the Python venv, installs all dependencies, and launches both servers simultaneously.

<br>

### ▶ Manual Setup

**1 — Backend**
```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn main:app --port 8000 --reload
```

**2 — Frontend** *(new terminal)*
```bash
npm install
npm run dev
# → http://localhost:5173
```

**3 — Open the app**

Navigate to `http://localhost:5173`. The header badge switches from `SIMULATED` → **`LIVE`** once the backend finishes loading (~30s on first run while it fetches 60 tickers).

<br>

---

## ◈ Free Data Sources

<div align="center">

| Source | Data | Requires |
|:------:|:-----|:--------:|
| **yfinance** | 5yr OHLCV prices + fundamentals — 60-ticker equity universe | Nothing |
| **FRED** (Federal Reserve) | VIX · Yield curve · CPI · Fed Funds rate · Credit spreads | Nothing |
| **SEC EDGAR XBRL** | Point-in-time 10-K/10-Q: accruals, asset growth, ROE, GP | Nothing |
| **Alpaca Paper** | Paper trading execution *(optional)* | Free account |
| **Ollama / Groq** | Local or cloud LLM for AI commentary *(optional)* | Free |

</div>

<br>

---

## ◈ Alpha Signal Universe

<div align="center">

| # | Signal | Category | Typical IC | Status |
|:-:|:-------|:--------:|:----------:|:------:|
| 1 | **12-1 Momentum** | Momentum | 0.042 | ✅ Promoted |
| 2 | **Short-Term Reversal** | Reversal | 0.038 | ✅ Promoted |
| 3 | **Book-to-Market** | Value | 0.028 | ✅ Promoted |
| 4 | **Earnings Yield** | Value | 0.031 | ✅ Promoted |
| 5 | **Return on Equity** | Quality | 0.035 | ✅ Promoted |
| 6 | **Gross Profitability** | Quality | 0.033 | ✅ Promoted |
| 7 | **Low Volatility** | Risk | 0.029 | 🔬 Review |
| 8 | **Low Beta** | Risk | 0.027 | 🔬 Review |
| 9 | **Earnings Revision** | Sentiment | 0.051 | ✅ Promoted |
| 10 | **Short Interest** | Sentiment | 0.044 | ✅ Promoted |
| 11 | **Accruals** | Accounting | 0.026 | 🔬 Review |
| 12 | **Investment Growth** | Accounting | 0.024 | 🔬 Review |
| 13 | **Quality-Value-Momentum** | Composite | 0.048 | ✅ Promoted |
| 14 | **ML Gradient Boost** | ML | 0.062 | ✅ Promoted |
| 15 | **Earnings NLP** | ML | 0.055 | ✅ Promoted |

</div>

*Promotion gates: IC > 0.025 · ICIR > 0.40 · Net Sharpe > 0.50 · Walk-forward win rate > 60%*

<br>

---

## ◈ Autonomous Agents

<br>

### ⚡ Execution Agent
Autonomous paper trading bot. Reads promoted signals → sizes positions (max 5% per ticker, 150% gross) → executes via Alpaca Paper API or in-memory fallback. Includes daily circuit-breaker at −3% NAV.

```env
# backend/.env  (optional — falls back to in-memory paper portfolio)
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
```

<br>

### 🧠 AI Commentary Agent
Generates institutional-grade research notes from live signal metrics, regime state, and macro data. Model cascade:

```
1. NVIDIA NIM  (nemotron-70b)   ← best quality, needs NVIDIA_API_KEY
2. Ollama      (llama3, local)  ← free, runs on your machine
3. Groq        (llama3, cloud)  ← free tier, needs GROQ_API_KEY
4. Template engine              ← always available, zero config
```

```env
NVIDIA_API_KEY=your_key   # optional
GROQ_API_KEY=your_key     # optional
OLLAMA_HOST=http://localhost:11434  # default if Ollama installed
```

<br>

### 🛡 Risk Agent
Pre-trade risk gatekeeper. Validates every order against 7 rules before execution: concentration, leverage, drawdown, sector exposure, liquidity, macro conflict, and LLM-reasoned judgment. Returns `APPROVE / REJECT / REDUCE_SIZE`.

<br>

### ⭐ Scorer Agent
Ranks signals 0–1 across 5 dimensions — IC/ICIR/Sharpe, regime fit, macro alignment, liquidity, and LLM reward score — to drive dynamic allocation sizing.

<br>

### 💬 Sentiment Agent
Fetches headlines via yfinance → scores with FinBERT (local, CPU, free) → summarises with a 675B vision-language model for narrative context.

<br>

### 👁 Vision Agent
Generates OHLCV charts with matplotlib → submits to a 90B vision model → detects chart patterns (breakout, H&S, support/resistance) with conviction scores.

<br>

### 🕐 Background Scheduler
APScheduler jobs — no external service required:

| Job | Schedule |
|:----|:--------:|
| Price refresh | Weekdays 16:30 ET |
| FRED macro data | Every 6 hours |
| Signal recompute | Weekdays 17:00 ET |
| Execution cycle | Weekdays 17:30 ET |
| AI commentary | Weekdays 18:00 ET |
| Deep weekly refresh | Monday 09:00 ET |

<br>

---

## ◈ Deployment

### Frontend → Netlify *(live at [fountry.netlify.app](https://fountry.netlify.app))*
```bash
npm run build
# Drag & drop the dist/ folder to netlify.com, or connect the repo for CI/CD
```
Set environment variable:
```
VITE_API_URL=https://your-backend.onrender.com
```

### Backend → Render (free tier)
`backend/render.yaml` is pre-configured. Connect the repo at [render.com](https://render.com) and point the root to `/backend`. Cold starts take ~30s on the free tier.

<br>

---

## ◈ Project Structure

```
quant-alpha-foundry/
│
├── 📄 quant-alpha-foundry.jsx  ← Entire React frontend (single file, ~1700 lines)
├── 📄 src/main.jsx             ← Vite entry point
├── 📄 index.html
├── 📄 vite.config.js
├── 📄 vercel.json              ← Frontend deploy config
├── 📄 render.yaml              ← Root-level deploy config
├── 📄 start.bat                ← One-click Windows launcher
│
└── 📁 backend/
    ├── 📄 main.py              ← FastAPI app + all API endpoints
    ├── 📄 signals.py           ← 15-factor signal engine
    ├── 📄 data_loader.py       ← yfinance async loader (60 tickers)
    ├── 📄 regimes.py           ← Gaussian HMM regime detector
    ├── 📄 portfolio.py         ← L/S portfolio + factor attribution
    ├── 📄 fred_signals.py      ← FRED macro signal engine
    ├── 📄 edgar_signals.py     ← SEC EDGAR accounting signals
    ├── 📄 cache.py             ← TTL in-memory cache
    ├── 📄 requirements.txt
    ├── 📄 render.yaml          ← Backend deploy config
    ├── 📄 Procfile
    │
    └── 📁 agents/
        ├── 📄 execution_agent.py   ← Paper trading bot + Alpaca integration
        ├── 📄 llm_agent.py         ← AI commentary (NVIDIA / Ollama / Groq)
        ├── 📄 risk_agent.py        ← Pre-trade risk gatekeeper
        ├── 📄 scorer_agent.py      ← Signal confidence scorer
        ├── 📄 sentiment_agent.py   ← FinBERT sentiment pipeline
        ├── 📄 vision_agent.py      ← Chart pattern recognition
        └── 📄 scheduler.py         ← APScheduler background jobs
```

<br>

---

## ◈ Tech Stack

<div align="center">

| Layer | Technology |
|:-----:|:-----------|
| **UI** | React 18 · Vite 5 · Bebas Neue · JetBrains Mono · Cormorant Garamond |
| **API** | FastAPI · uvicorn · Python 3.11+ · async lifespan |
| **Market Data** | yfinance · pandas · numpy |
| **Signals** | scikit-learn · scipy · statsmodels |
| **Regimes** | hmmlearn (Gaussian HMM) |
| **Macro** | FRED public API (free) |
| **Accounting** | SEC EDGAR XBRL (free) |
| **Agents** | APScheduler · Alpaca SDK · transformers (FinBERT) |
| **LLM** | NVIDIA NIM · Ollama · Groq |
| **Deploy** | Netlify (frontend) · Render (backend) |

</div>

<br>

---

<div align="center">

**[🌐 Live Demo](https://fountry.netlify.app)** · **[⚗ Signal Lab](#-alpha-signal-universe)** · **[🤖 Agents](#-autonomous-agents)** · **[🚀 Deploy](#-deployment)**

<br>

*Built for quants, by quants. Zero hedge fund required.*

<br>

[![MIT License](https://img.shields.io/badge/License-MIT-facc15?style=flat-square)](LICENSE)

</div>

