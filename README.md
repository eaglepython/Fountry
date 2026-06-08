# Alpha Foundry

**Institutional-grade quantitative alpha research platform** — signal research, regime detection, macro analysis, paper trading, and AI-powered commentary in one full-stack application.

![Alpha Foundry](https://img.shields.io/badge/stack-React%20%2B%20FastAPI-blue) ![Python](https://img.shields.io/badge/Python-3.11%2B-green) ![License](https://img.shields.io/badge/license-MIT-orange)

---

## What It Does

| Tab | Description |
|-----|-------------|
| **Foundry** | Signal universe overview — 15 factor signals with IC, ICIR, Sharpe, capacity |
| **Signal Lab** | Deep dive: walk-forward results, IC decay, regime-conditional performance |
| **Stress Test** | Drawdown scenarios + live FRED macro signals (VIX, yield curve, credit spreads) |
| **Execution** | Trade blotter with market impact, VWAP slippage, and algo attribution |
| **Portfolio** | Equity curve, Fama-French factor attribution, risk metrics (VaR, CVaR) |
| **Agents** | Autonomous execution bot, AI commentary engine, background scheduler |

---

## Stack

**Frontend** — React 18 + Vite 5, single-file component, no external UI libraries  
**Backend** — FastAPI + uvicorn, async lifespan startup  
**Data** — yfinance (market), FRED CSV (macro, free/no key), SEC EDGAR XBRL (accounting, free/no key)  
**Signals** — 15 cross-sectional equity factors (momentum, value, quality, low-vol, ML)  
**Regimes** — Gaussian HMM (3-state) + rule-based fallback via hmmlearn  
**Agents** — APScheduler background jobs, Alpaca paper trading API, Ollama/Groq LLM commentary  

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+

### One-command start (Windows)
```bat
start.bat
```
This creates the Python venv, installs all deps, and opens the backend + frontend simultaneously.

### Manual start

**Backend**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
uvicorn main:app --port 8000 --reload
```

**Frontend**
```bash
npm install
npm run dev
# Open http://localhost:5173
```

---

## Free Data Sources

| Source | What | Key needed? |
|--------|------|-------------|
| **yfinance** | 5yr OHLCV + fundamentals, 60-ticker universe | No |
| **FRED** (Federal Reserve) | VIX, yield curve, CPI, Fed Funds, credit spreads | No |
| **SEC EDGAR XBRL** | Point-in-time 10-K/10-Q filings | No |

---

## Agents

### Execution Agent
Autonomous paper trading bot. Reads promoted signals → sizes positions → executes via Alpaca Paper API or in-memory paper portfolio.

To use Alpaca (free paper trading account at [alpaca.markets](https://alpaca.markets)):
```env
# backend/.env
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
```

### AI Commentary Agent
Generates institutional research notes from signal metrics. Model priority:
1. **Ollama** (local, free — install from [ollama.com](https://ollama.com), run `ollama pull llama3`)
2. **Groq** (free cloud tier — get key at [console.groq.com](https://console.groq.com))
3. **Template engine** (always available, no key needed)

```env
GROQ_API_KEY=your_key          # optional
OLLAMA_HOST=http://localhost:11434  # default
```

### Background Scheduler
APScheduler jobs — no external service needed:
- Price refresh: weekdays 16:30 ET
- FRED macro: every 6 hours
- Signal recompute: weekdays 17:00 ET
- Execution cycle: weekdays 17:30 ET
- AI commentary: weekdays 18:00 ET
- Deep refresh: Monday 09:00 ET

---

## Deployment

### Frontend → Vercel (free)
```bash
npm run build
# Connect repo to vercel.com — auto-detects Vite
```
Set environment variable: `VITE_API_URL=https://your-backend.onrender.com`

### Backend → Render (free tier)
`backend/render.yaml` is pre-configured. Connect repo at [render.com](https://render.com), point to `/backend`.

---

## Project Structure

```
├── quant-alpha-foundry.jsx   # Entire React frontend (single file)
├── src/main.jsx              # Vite entry point
├── index.html
├── vite.config.js
├── vercel.json               # Frontend deploy config
├── start.bat                 # One-click Windows launcher
└── backend/
    ├── main.py               # FastAPI app + all endpoints
    ├── signals.py            # 15-signal factor engine
    ├── data_loader.py        # yfinance async loader
    ├── regimes.py            # HMM regime detector
    ├── portfolio.py          # L/S portfolio + factor attribution
    ├── fred_signals.py       # FRED macro signal engine
    ├── edgar_signals.py      # SEC EDGAR accounting signals
    ├── cache.py              # TTL in-memory cache
    ├── requirements.txt
    ├── render.yaml           # Backend deploy config
    ├── Procfile
    └── agents/
        ├── execution_agent.py   # Paper trading bot
        ├── llm_agent.py         # AI commentary engine
        └── scheduler.py         # APScheduler background jobs
```

---

## Signals Researched

| Signal | Type | Status |
|--------|------|--------|
| 12-1 Momentum | Momentum | ✅ Promoted |
| Short-Term Reversal | Reversal | ✅ Promoted |
| 1-Month Momentum | Momentum | ✅ Promoted |
| Earnings Yield | Value | Under review |
| Book-to-Market | Value | Under review |
| Gross Profitability | Quality | ✅ Promoted |
| Return on Equity | Quality | Under review |
| Low Volatility | Low-risk | Under review |
| Low Beta | Low-risk | Under review |
| Idiosyncratic Vol | Low-risk | ✅ Promoted |
| Earnings Revision | Sentiment | ✅ Promoted |
| Short Interest | Sentiment | Under review |
| Accruals | Accounting | Under review |
| Investment Growth | Accounting | Under review |
| Quality-Value-Momentum | Composite | ✅ Promoted |

---

## License

MIT
