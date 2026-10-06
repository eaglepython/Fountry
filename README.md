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

**⟡ Quantitative Research Workbench — Experimental, Not Investment-Validated ⟡**

<br>

[![Live Demo](https://img.shields.io/badge/🌐%20LIVE%20DEMO-fountry.netlify.app-c9a96e?style=for-the-badge)](https://fountry.netlify.app)

<br>

[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Vite](https://img.shields.io/badge/Vite-5-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev)

<br>

[![Signals](https://img.shields.io/badge/Research%20Candidates-15-c9a96e?style=flat-square&logo=chartdotjs)](https://fountry.netlify.app)
[![Data](https://img.shields.io/badge/Market%20Data-Free%20·%20No%20API%20Key-4ade80?style=flat-square&logo=yahoo)](https://fountry.netlify.app)
[![Agents](https://img.shields.io/badge/Agent%20Modules-7-c084fc?style=flat-square&logo=probot)](https://fountry.netlify.app)
[![Deploy](https://img.shields.io/badge/Hosted%20on-Netlify-00C7B7?style=flat-square&logo=netlify)](https://fountry.netlify.app)
[![License](https://img.shields.io/badge/License-MIT-facc15?style=flat-square)](LICENSE)

<br>

> *Explore signals and market data. Trading results are not validated.*

</div>

---

<br>

## ◈ Overview

**Fountry** is an experimental quantitative research dashboard. It is not institutional-grade or investment validated. The current data vendor provides today’s surviving ticker universe and current snapshots for many fundamentals; it does not provide the historical constituents and publication timestamps required to substantiate a point-in-time long-horizon backtest. Historical return, Sharpe, capacity, regime and trade analytics must not be inferred from its research-candidate list.

Market prices use `yfinance`; the header shows the latest observed S&P 500 index close (or the SPY ETF close if the index quote is unavailable), its date, and the one-day move. This is daily market data, not a streaming or exchange-certified real-time feed. Portfolio P&L remains unavailable until actual portfolio performance data exists. When real data is unavailable the API reports a degraded/unavailable state instead of fabricating market prices. Model providers require their own configured runtime or API credentials; model weights are not bundled.

<br>

---

## ◈ Platform Views

<br>

<div align="center">

| View | What You Get |
|:----:|:------------|
| **⚗ FOUNTRY** | Signal research candidates with observed IC only. Net Sharpe, trading capacity and strategy promotion are unavailable. |
| **🔬 SIGNAL LAB** | Exploratory IC statistics where observations are available. IC is not a portfolio return or profitability estimate. |
| **⚡ STRESS TEST** | Regime and macro exploration; regime-conditioned strategy results are unavailable without validated historical labels. |
| **📋 EXECUTION** | Broker execution analytics are unavailable until a verified fill and transaction-cost feed is connected. |
| **📊 PORTFOLIO** | Portfolio return analytics are disabled until a valid point-in-time, after-cost backtest is implemented. |
| **🤖 AGENTS** | Agent status, commentary-provider configuration and scheduler controls. Trading agents do not have a validated profitable strategy. |

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
│  Exploratory price signals · point-in-time history pending     │
│  Regime research only · no validated return or decay claims     │
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

**Agent controls require a backend token.** Set `AGENT_CONTROL_TOKEN` in `backend/.env` to a random secret with at least 32 characters, then enter the same value in the Agents dashboard. The dashboard keeps it in page memory only. On Render, set the `AGENT_CONTROL_TOKEN` environment variable in the service settings. Mutating agent endpoints reject missing or invalid tokens. CORS is limited to the configured origins.

Set Netlify's `VITE_API_URL` build environment variable to the actual public URL of the Python API service, then trigger a frontend deploy. Production builds do not guess a backend hostname or fall back to `localhost`, which would point to each visitor's own computer. The commentary and risk agents call hosted model APIs; set `NVIDIA_API_KEY` or `GROQ_API_KEY` on the backend to enable those providers. No model weights are bundled in the frontend.

Alpaca always starts in paper mode by default. To permit switching to live trading, explicitly set `ALPACA_LIVE_TRADING_ENABLED=true` on the backend. Keep it `false` for paper trading.

**1 — Backend**
```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
# Add AGENT_CONTROL_TOKEN=<32+ character random secret> to backend/.env
python -m uvicorn main:app --port 8000 --reload
```

**2 — Frontend** *(new terminal)*
```bash
npm install
npm run dev
# → http://localhost:5173
```

**3 — Open the app**

Navigate to `http://localhost:5173`. Research views open when the backend has loaded real market prices. If the backend is offline or data loading fails, they show an unavailable state instead of demo performance.

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

| # | Signal | Category | Evidence status |
|:-:|:-------|:--------:|:----------------|
| 1 | **12-1 Momentum** | Momentum | Exploratory only |
| 2 | **Short-Term Reversal** | Reversal | Exploratory only |
| 3 | **Book-to-Market** | Value | No point-in-time fundamentals |
| 4 | **Earnings Yield** | Value | No point-in-time fundamentals |
| 5 | **Return on Equity** | Quality | No point-in-time fundamentals |
| 6 | **Gross Profitability** | Quality | No point-in-time fundamentals |
| 7 | **Low Volatility** | Risk | Exploratory only |
| 8 | **Low Beta** | Risk | Exploratory only |
| 9 | **Earnings Revision** | Sentiment | No historical analyst estimates |
| 10 | **Short Interest** | Sentiment | No point-in-time series |
| 11 | **Accruals** | Accounting | No point-in-time fundamentals |
| 12 | **Investment Growth** | Accounting | No point-in-time fundamentals |
| 13 | **Quality-Value-Momentum** | Composite | Not performance validated |
| 14 | **ML Gradient Boost** | ML | Model/backtest not implemented |
| 15 | **Earnings NLP** | ML | Historical text dataset/model not implemented |

</div>

No promotion or profitability gates are currently enabled. A valid evaluation needs dated point-in-time features and constituents, chronological out-of-sample periods, and measured execution costs.

<br>

---

## ◈ Autonomous Agents

<br>

### ⚡ Execution Agent
Experimental execution agent. It consumes only explicitly promoted signals; none are currently promoted because IC is not sufficient evidence of profitability. Do not enable live trading on this project until broker state reconciliation, fill accounting, tested hard risk limits and a valid after-cost strategy backtest are in place.

```env
# backend/.env  (optional — falls back to in-memory paper portfolio)
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
```

<br>

### 🧠 AI Commentary Agent
Generates research status notes from available signal and macro data. Models run through configured providers; weights are not bundled. Missing return metrics are reported as unavailable. Model cascade:

```
1. NVIDIA NIM  (configured model IDs) ← needs NVIDIA_API_KEY
2. Ollama      (llama3, local)       ← requires a reachable server and installed model
3. Groq        (llama3, cloud)       ← needs GROQ_API_KEY
4. Template engine              ← always available, zero config
```

```env
NVIDIA_API_KEY=your_key   # optional
GROQ_API_KEY=your_key     # optional
OLLAMA_HOST=http://localhost:11434  # default if Ollama installed
```

<br>

### 🛡 Risk Agent
Experimental pre-trade checks for concentration, leverage, drawdown, sector exposure, and macro conflict. LLM output is advisory; these checks do not replace broker-side controls. Liquidity checks are not implemented.

<br>

### ⭐ Scorer Agent
Prototype scoring module. It is not connected to execution and must not determine capital allocations from unvalidated IC values.

<br>

### 💬 Sentiment Agent
Optional headline sentiment module. FinBERT requires the optional `transformers` package and downloaded weights. Hosted model calls require configured credentials; model weights are not installed by this repo.

<br>

### 👁 Vision Agent
Optional chart commentary module. It needs a reachable multimodal model API; detected patterns are not validated trading signals.

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
VITE_API_URL=https://your-api-service.onrender.com
```

If hosting the frontend as a Render Node web service, use build command `npm ci && npm run build` and start command `npm start`. The start script serves the built `dist/` directory on Render's assigned `PORT`.

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

