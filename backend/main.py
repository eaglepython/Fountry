"""
Quant Alpha Foundry — FastAPI Backend v2.2
Serves real signal metrics, walk-forward results, regime labels,
FRED macro signals, SEC EDGAR accounting signals, and autonomous agents.
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio, time, logging, math, json
from contextlib import asynccontextmanager

from signals     import SignalEngine
from regimes     import RegimeDetector
from portfolio   import PortfolioEngine
from data_loader import DataLoader
from cache       import Cache
from fred_signals   import FREDLoader, MacroSignalEngine
from edgar_signals  import SECEdgarLoader, AccountingSignalEngine
from agents import ExecutionAgent, LLMCommentaryAgent, AgentScheduler

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)


def _sanitize(obj):
    """Recursively replace NaN/Inf floats with None for JSON safety."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj

cache             = Cache()
data_loader       = DataLoader()
fred_loader       = FREDLoader()
edgar_loader      = SECEdgarLoader()
signal_engine     = None
regime_detector   = None
portfolio_engine  = None
macro_engine      = None
accounting_engine = None
execution_agent   = None
commentary_agent  = None
scheduler         = AgentScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global signal_engine, regime_detector, portfolio_engine
    global macro_engine, accounting_engine
    global execution_agent, commentary_agent

    log.info("🚀 Alpha Foundry v2.1 starting…")
    loop = asyncio.get_event_loop()

    # ── 1. Market prices (yfinance) ─────────────────────────────────────────
    try:
        log.info("Loading market data (yfinance)…")
        await data_loader.load_all()
        signal_engine    = SignalEngine(data_loader)
        regime_detector  = RegimeDetector(data_loader)
        portfolio_engine = PortfolioEngine(data_loader, signal_engine)
        log.info(f"✅ Market data: {len(data_loader.prices)} tickers")
    except Exception as e:
        log.error(f"Market data failed: {e}")

    # ── 2. FRED macro signals ───────────────────────────────────────────────
    try:
        log.info("Loading FRED macro data…")
        fred_data = await asyncio.wait_for(
            loop.run_in_executor(None, fred_loader.load_all),
            timeout=12.0)
        macro_engine = MacroSignalEngine(fred_loader)
        log.info(f"✅ FRED: {len(fred_data)} series loaded")
    except (Exception, asyncio.TimeoutError) as e:
        log.warning(f"FRED load skipped ({type(e).__name__}) — using synthetic fallback")
        macro_engine = MacroSignalEngine(fred_loader)

    # ── 3. SEC EDGAR accounting signals ────────────────────────────────────
    try:
        log.info("Loading SEC EDGAR accounting data…")
        accounting_engine = AccountingSignalEngine(edgar_loader)
        tickers = data_loader.equity_universe[:25] if data_loader.is_loaded else []
        if tickers:
            await asyncio.wait_for(
                loop.run_in_executor(None,
                    lambda: accounting_engine.load_universe(tickers)),
                timeout=15.0)
            log.info(f"✅ EDGAR: {len(accounting_engine._universe_data)} tickers")
        else:
            log.warning("No universe tickers — EDGAR signals will use fallback")
    except (Exception, asyncio.TimeoutError) as e:
        log.warning(f"EDGAR load skipped ({type(e).__name__}) — using synthetic fallback")
        accounting_engine = AccountingSignalEngine(edgar_loader)

    # ── 4. Agents ───────────────────────────────────────────────────────────
    try:
        execution_agent  = ExecutionAgent()
        commentary_agent = LLMCommentaryAgent()

        # Wire references into scheduler so jobs can call engines
        scheduler.data_loader      = data_loader
        scheduler.signal_engine    = signal_engine
        scheduler.fred_loader      = fred_loader
        scheduler.execution_agent  = execution_agent
        scheduler.commentary_agent = commentary_agent
        scheduler.cache            = cache
        scheduler.regime_detector  = regime_detector
        scheduler.portfolio_engine = portfolio_engine
        scheduler.macro_engine     = macro_engine

        scheduler.start()
        log.info("✅ Agents initialized and scheduler started")
    except Exception as e:
        log.error(f"Agent initialization failed: {e}")

    log.info("✅ All engines initialized")
    yield
    log.info("Shutting down…")
    scheduler.stop()

app = FastAPI(title="Alpha Foundry API", version="2.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ── Health ───────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status":          "ok",
        "data_loaded":     data_loader.is_loaded,
        "fred_loaded":     fred_loader._loaded,
        "edgar_tickers":   len(accounting_engine._universe_data) if accounting_engine else 0,
        "universe_size":   len(data_loader.universe),
        "timestamp":       time.time(),
    }

# ── Market data ──────────────────────────────────────────────────────────────
@app.get("/api/universe")
async def get_universe():
    return data_loader.get_universe_info()

@app.get("/api/market/prices/{ticker}")
async def get_prices(ticker: str, period: str = "1y"):
    return data_loader.get_prices(ticker.upper(), period)

@app.get("/api/market/live")
async def get_live():
    return data_loader.get_live_snapshot()

# ── Signals ──────────────────────────────────────────────────────────────────
@app.get("/api/signals")
async def get_all_signals():
    if not signal_engine:
        raise HTTPException(503, "Signal engine not ready")
    return cache.get_or_compute("all_signals",
                                signal_engine.compute_all_signals, ttl=3600)

@app.get("/api/signals/{signal_id}")
async def get_signal_detail(signal_id: str):
    if not signal_engine:
        raise HTTPException(503, "Signal engine not ready")
    return cache.get_or_compute(
        f"signal_{signal_id}",
        lambda: signal_engine.compute_signal_detail(signal_id), ttl=3600)

@app.get("/api/signals/{signal_id}/walkforward")
async def get_walkforward(signal_id: str, years: int = 5):
    if not signal_engine:
        raise HTTPException(503, "Signal engine not ready")
    return signal_engine.walk_forward(signal_id, years=years)

@app.get("/api/signals/{signal_id}/decay")
async def get_decay(signal_id: str):
    if not signal_engine:
        raise HTTPException(503, "Signal engine not ready")
    return signal_engine.compute_decay(signal_id)

# ── Regimes ──────────────────────────────────────────────────────────────────
@app.get("/api/regimes/current")
async def get_current_regime():
    if not regime_detector:
        raise HTTPException(503, "Regime detector not ready")
    return regime_detector.current_regime()

@app.get("/api/regimes/history")
async def get_regime_history():
    if not regime_detector:
        raise HTTPException(503, "Regime detector not ready")
    return cache.get_or_compute("regime_history",
                                regime_detector.full_history, ttl=86400)

@app.get("/api/regimes/signal_performance")
async def get_regime_signal_perf():
    if not signal_engine or not regime_detector:
        raise HTTPException(503, "Engines not ready")
    return cache.get_or_compute(
        "regime_signal_perf",
        lambda: signal_engine.compute_regime_conditional_ic(regime_detector),
        ttl=3600)

# ── Portfolio ────────────────────────────────────────────────────────────────
@app.get("/api/portfolio/performance")
async def get_portfolio_perf():
    if not portfolio_engine:
        raise HTTPException(503, "Portfolio engine not ready")
    return cache.get_or_compute("portfolio_perf",
                                portfolio_engine.performance, ttl=300)

@app.get("/api/portfolio/attribution")
async def get_attribution():
    if not portfolio_engine:
        raise HTTPException(503, "Portfolio engine not ready")
    return cache.get_or_compute("attribution",
                                portfolio_engine.factor_attribution, ttl=3600)

@app.get("/api/portfolio/holdings")
async def get_holdings():
    if not portfolio_engine:
        raise HTTPException(503, "Portfolio engine not ready")
    return portfolio_engine.current_holdings()

@app.get("/api/portfolio/risk")
async def get_risk():
    if not portfolio_engine:
        raise HTTPException(503, "Portfolio engine not ready")
    return cache.get_or_compute("risk",
                                portfolio_engine.risk_metrics, ttl=300)

# ── FRED Macro Signals ───────────────────────────────────────────────────────
@app.get("/api/macro/all")
async def get_all_macro():
    """All FRED macro signals + composite regime score."""
    if not macro_engine:
        raise HTTPException(503, "Macro engine not ready")
    data = cache.get_or_compute("macro_all", macro_engine.all_signals, ttl=3600)
    return JSONResponse(content=_sanitize(data))

@app.get("/api/macro/composite")
async def get_macro_composite():
    """Composite macro regime score from all FRED signals."""
    if not macro_engine:
        raise HTTPException(503, "Macro engine not ready")
    data = cache.get_or_compute("macro_composite", macro_engine.composite_regime_score, ttl=3600)
    return JSONResponse(content=_sanitize(data))

@app.get("/api/macro/{signal_name}")
async def get_macro_signal(signal_name: str):
    """Individual macro signal (yield_curve, credit_spreads, volatility, etc.)."""
    if not macro_engine:
        raise HTTPException(503, "Macro engine not ready")
    fn_map = {
        "yield_curve":          macro_engine.yield_curve_signal,
        "credit_spreads":       macro_engine.credit_spread_signal,
        "volatility":           macro_engine.volatility_signal,
        "monetary_policy":      macro_engine.monetary_policy_signal,
        "economic_cycle":       macro_engine.economic_cycle_signal,
        "inflation":            macro_engine.inflation_signal,
        "financial_conditions": macro_engine.financial_conditions_signal,
    }
    fn = fn_map.get(signal_name)
    if not fn:
        raise HTTPException(404, f"Unknown macro signal: {signal_name}")
    data = cache.get_or_compute(f"macro_{signal_name}", fn, ttl=3600)
    return JSONResponse(content=_sanitize(data))

# ── SEC EDGAR Accounting Signals ─────────────────────────────────────────────
@app.get("/api/accounting/universe")
async def get_accounting_universe():
    """Accounting metrics for all tickers in the universe."""
    if not accounting_engine:
        raise HTTPException(503, "Accounting engine not ready")
    return cache.get_or_compute(
        "accounting_universe",
        accounting_engine.get_universe_accounting_summary, ttl=86400)

@app.get("/api/accounting/signals")
async def get_accounting_signals():
    """Metadata for all accounting signals."""
    if not accounting_engine:
        raise HTTPException(503, "Accounting engine not ready")
    return accounting_engine.get_signal_catalog()

@app.get("/api/accounting/signal/{signal_name}")
async def get_accounting_cross_section(signal_name: str):
    """Cross-sectional scores for a specific accounting signal."""
    if not accounting_engine:
        raise HTTPException(503, "Accounting engine not ready")
    valid = ["accruals","asset_growth","gross_profit","roe",
             "debt_equity","net_margin","capex_intensity","rd_intensity","cash_ratio"]
    if signal_name not in valid:
        raise HTTPException(404, f"Unknown accounting signal: {signal_name}")
    scores = accounting_engine.compute_cross_sectional_signal(signal_name)
    return scores.sort_values(ascending=False).to_dict()

@app.get("/api/accounting/ticker/{ticker}")
async def get_ticker_accounting(ticker: str):
    """All accounting metrics for a single ticker."""
    if not accounting_engine:
        raise HTTPException(503, "Accounting engine not ready")
    t = ticker.upper()
    data = accounting_engine._universe_data.get(t, {})
    if not data:
        raise HTTPException(404, f"{t} not in accounting universe")
    result = {}
    for field, series in data.items():
        if len(series) > 0:
            result[field] = {
                "latest":  round(float(series.dropna().iloc[-1]), 4),
                "history": {str(d.date()): round(float(v), 4)
                            for d, v in series.dropna().items()},
            }
    return result


# ── Agents ────────────────────────────────────────────────────────────────────

@app.get("/api/agents/status")
async def get_agents_status():
    """Top-level health of all three agents."""
    return {
        "execution": {
            "mode":       execution_agent.mode         if execution_agent else "not_initialized",
            "status":     execution_agent.status       if execution_agent else "unavailable",
            "last_cycle": execution_agent.last_cycle   if execution_agent else None,
            "alpaca_enabled": execution_agent.alpaca.enabled if execution_agent else False,
        },
        "commentary": {
            "has_report": bool(commentary_agent and commentary_agent.last_report),
            "last_timestamp": (commentary_agent.last_report or {}).get("timestamp"),
            "llm_source":     (commentary_agent.last_report or {}).get("source"),
        },
        "scheduler": scheduler.get_status(),
    }


# ── Execution agent ───────────────────────────────────────────────────────────

@app.get("/api/agents/execution/state")
async def get_execution_state():
    """Paper portfolio positions, trade history, and P&L."""
    if not execution_agent:
        raise HTTPException(503, "Execution agent not ready")
    return execution_agent.get_state()


@app.post("/api/agents/execution/run")
async def run_execution_cycle(background_tasks: BackgroundTasks):
    """Trigger an immediate rebalance cycle (runs in background)."""
    if not execution_agent:
        raise HTTPException(503, "Execution agent not ready")
    if not signal_engine:
        raise HTTPException(503, "Signal engine not ready")

    if execution_agent.is_running:
        return {"status": "already_running"}

    def _run():
        signals = cache.get("all_signals") or signal_engine.compute_all_signals()
        return execution_agent.run_cycle(signals)

    background_tasks.add_task(_run)
    return {"status": "started", "message": "Rebalance cycle triggered"}


@app.post("/api/agents/execution/mode/{mode}")
async def switch_alpaca_mode(mode: str):
    """Switch Alpaca between 'live' and 'paper' trading without restart."""
    if not execution_agent:
        raise HTTPException(503, "Execution agent not ready")
    if mode not in ("live", "paper"):
        raise HTTPException(400, "mode must be 'live' or 'paper'")
    if execution_agent.is_running:
        raise HTTPException(409, "Cannot switch mode while a cycle is running")
    execution_agent.alpaca.switch(mode)
    log.info(f"Trading mode switched to {mode.upper()} → {execution_agent.alpaca.base_url}")
    return {
        "status":       "ok",
        "alpaca_mode":  execution_agent.alpaca.mode,
        "alpaca_url":   execution_agent.alpaca.base_url,
        "message":      f"Switched to {mode.upper()} trading",
    }


@app.post("/api/agents/execution/reset")
async def reset_circuit_breaker():
    """Reset circuit breaker and re-anchor NAV baseline to current value."""
    if not execution_agent:
        raise HTTPException(503, "Execution agent not ready")
    result = execution_agent.reset_circuit_breaker()
    return result


@app.get("/api/agents/execution/positions")
async def get_positions():
    """Current open positions in the paper portfolio."""
    if not execution_agent:
        raise HTTPException(503, "Execution agent not ready")
    state = execution_agent.paper.to_dict()
    return {"positions": state["positions"], "nav": state["nav"],
            "cash": state["cash"], "n_positions": state["n_positions"]}


@app.get("/api/agents/execution/trades")
async def get_trade_history(limit: int = 50):
    """Recent trade history."""
    if not execution_agent:
        raise HTTPException(503, "Execution agent not ready")
    trades = execution_agent.paper.trades[-limit:][::-1]
    return {"trades": trades, "total": len(execution_agent.paper.trades)}


# ── LLM Commentary agent ──────────────────────────────────────────────────────

@app.get("/api/agents/commentary/latest")
async def get_latest_commentary():
    """Most recent AI-generated signal intelligence report."""
    if not commentary_agent:
        raise HTTPException(503, "Commentary agent not ready")
    return commentary_agent.get_last()


@app.post("/api/agents/commentary/generate")
async def generate_commentary(background_tasks: BackgroundTasks):
    """Trigger a new commentary report (runs in background)."""
    if not commentary_agent:
        raise HTTPException(503, "Commentary agent not ready")
    if not signal_engine or not portfolio_engine or not regime_detector:
        raise HTTPException(503, "Required engines not ready")

    if commentary_agent.is_generating:
        return {"status": "already_generating"}

    def _generate():
        signals   = cache.get("all_signals") or signal_engine.compute_all_signals()
        port_perf = portfolio_engine.performance()
        regime    = regime_detector.current_regime().get("regime", "bull")
        macro_data = {}
        if macro_engine:
            try:
                macro_data = {
                    "volatility":     macro_engine.volatility_signal(),
                    "yield_curve":    macro_engine.yield_curve_signal(),
                    "credit_spreads": macro_engine.credit_spread_signal(),
                }
            except Exception:
                pass
        commentary_agent.generate(signals, port_perf, regime, macro_data)

    background_tasks.add_task(_generate)
    return {"status": "started", "message": "Commentary generation triggered"}


# ── Scheduler ─────────────────────────────────────────────────────────────────

@app.get("/api/agents/scheduler/status")
async def get_scheduler_status():
    """Scheduler job list, next run times, and recent job history."""
    return scheduler.get_status()


@app.post("/api/agents/scheduler/trigger/{job_id}")
async def trigger_job(job_id: str, background_tasks: BackgroundTasks):
    """Manually trigger a scheduler job by ID."""
    job_map = {
        "refresh_prices":      scheduler._job_refresh_prices,
        "refresh_fred":        scheduler._job_refresh_fred,
        "recompute_signals":   scheduler._job_recompute_signals,
        "execution_cycle":     scheduler._job_execution_cycle,
        "commentary":          scheduler._job_commentary,
        "weekly_deep_refresh": scheduler._job_weekly_deep_refresh,
    }
    fn = job_map.get(job_id)
    if not fn:
        raise HTTPException(404, f"Unknown job: {job_id}. Valid: {list(job_map)}")
    background_tasks.add_task(fn)
    return {"status": "triggered", "job": job_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
