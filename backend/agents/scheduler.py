"""
Scheduler — Background worker that keeps all data and agents fresh.

Jobs (APScheduler, no external service needed):
  Every day  16:30 ET  → refresh market prices (post-close)
  Every 6h             → refresh FRED macro data
  Every day  17:00 ET  → recompute signal metrics
  Every day  17:30 ET  → run execution agent rebalance
  Every day  18:00 ET  → generate LLM commentary report
  Every Mon  09:00 ET  → full cache clear + deep recompute
"""
import logging
from datetime import datetime
from typing import Callable, Optional

log = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    APScheduler_AVAILABLE = True
except ImportError:
    APScheduler_AVAILABLE = False
    log.warning("APScheduler not installed — scheduler disabled. Install with: pip install apscheduler")


class AgentScheduler:
    """
    Wraps APScheduler. Holds references to all engine/agent objects
    so jobs can call them without circular imports.
    """

    def __init__(self):
        self._scheduler: Optional[object]    = None
        self.job_history: list               = []
        self.is_running  = False

        # Injected by main.py after all engines are ready
        self.data_loader      = None
        self.signal_engine    = None
        self.fred_loader      = None
        self.execution_agent  = None
        self.commentary_agent = None
        self.cache            = None
        self.regime_detector  = None
        self.portfolio_engine = None
        self.macro_engine     = None

    def _record(self, job_name: str, status: str, detail: str = ""):
        self.job_history.append({
            "job":       job_name,
            "status":    status,
            "detail":    detail,
            "timestamp": datetime.utcnow().isoformat(),
        })
        if len(self.job_history) > 200:
            self.job_history = self.job_history[-200:]

    # ── Job definitions ───────────────────────────────────────────────────────

    async def _job_refresh_prices(self):
        log.info("⏰ Scheduler: refreshing market prices…")
        try:
            if self.data_loader:
                await self.data_loader.load_all()
                self._record("refresh_prices", "OK",
                             f"{len(self.data_loader.prices)} tickers")
        except Exception as e:
            self._record("refresh_prices", "ERROR", str(e))
            log.error(f"Price refresh failed: {e}")

    async def _job_refresh_fred(self):
        log.info("⏰ Scheduler: refreshing FRED macro data…")
        try:
            if self.fred_loader:
                import asyncio
                loop = asyncio.get_event_loop()
                fred_data = await loop.run_in_executor(None, self.fred_loader.load_all)
                self._record("refresh_fred", "OK", f"{len(fred_data)} series")
        except Exception as e:
            self._record("refresh_fred", "ERROR", str(e))
            log.error(f"FRED refresh failed: {e}")

    async def _job_recompute_signals(self):
        log.info("⏰ Scheduler: recomputing signal metrics…")
        try:
            if self.signal_engine and self.cache:
                self.cache.invalidate("all_signals")
                signals = self.signal_engine.compute_all_signals()
                self.cache.set("all_signals", signals, ttl=3600)
                self._record("recompute_signals", "OK", f"{len(signals)} signals")
        except Exception as e:
            self._record("recompute_signals", "ERROR", str(e))
            log.error(f"Signal recompute failed: {e}")

    async def _job_execution_cycle(self):
        log.info("⏰ Scheduler: running execution agent cycle…")
        try:
            if self.execution_agent and self.signal_engine and self.cache:
                signals = self.cache.get("all_signals") or self.signal_engine.compute_all_signals()
                result  = self.execution_agent.run_cycle(signals)
                self._record("execution_cycle", result.get("status", "?"),
                             f"{result.get('n_actions', 0)} actions, NAV=${result.get('nav', 0):,.0f}")
        except Exception as e:
            self._record("execution_cycle", "ERROR", str(e))
            log.error(f"Execution cycle failed: {e}")

    async def _job_commentary(self):
        log.info("⏰ Scheduler: generating LLM commentary…")
        try:
            if (self.commentary_agent and self.signal_engine
                    and self.portfolio_engine and self.regime_detector):
                signals    = self.cache.get("all_signals") or self.signal_engine.compute_all_signals()
                port_perf  = self.portfolio_engine.performance()
                regime     = self.regime_detector.current_regime().get("regime", "bull")
                macro_data = {}
                if self.macro_engine:
                    try:
                        macro_data = {
                            "volatility":   self.macro_engine.volatility_signal(),
                            "yield_curve":  self.macro_engine.yield_curve_signal(),
                            "credit_spreads": self.macro_engine.credit_spread_signal(),
                        }
                    except Exception:
                        pass
                result = self.commentary_agent.generate(signals, port_perf, regime, macro_data)
                self._record("commentary", result.get("status", "?"),
                             f"source={result.get('source','?')}")
        except Exception as e:
            self._record("commentary", "ERROR", str(e))
            log.error(f"Commentary generation failed: {e}")

    async def _job_weekly_deep_refresh(self):
        log.info("⏰ Scheduler: weekly deep refresh…")
        try:
            if self.cache:
                self.cache.clear_all()
            await self._job_refresh_prices()
            await self._job_refresh_fred()
            await self._job_recompute_signals()
            await self._job_commentary()
            self._record("weekly_deep_refresh", "OK")
        except Exception as e:
            self._record("weekly_deep_refresh", "ERROR", str(e))
            log.error(f"Weekly deep refresh failed: {e}")

    # ── Start / Stop ──────────────────────────────────────────────────────────

    def start(self):
        if not APScheduler_AVAILABLE:
            log.warning("APScheduler not available — jobs will not run automatically")
            return

        self._scheduler = AsyncIOScheduler(timezone="America/New_York")

        # Daily price refresh — 16:30 ET (30 min after market close)
        self._scheduler.add_job(self._job_refresh_prices, CronTrigger(
            hour=16, minute=30, day_of_week="mon-fri"), id="refresh_prices")

        # FRED refresh — every 6 hours
        self._scheduler.add_job(self._job_refresh_fred,
            IntervalTrigger(hours=6), id="refresh_fred")

        # Signal recompute — 17:00 ET weekdays
        self._scheduler.add_job(self._job_recompute_signals, CronTrigger(
            hour=17, minute=0, day_of_week="mon-fri"), id="recompute_signals")

        # Execution cycle — 17:30 ET weekdays
        self._scheduler.add_job(self._job_execution_cycle, CronTrigger(
            hour=17, minute=30, day_of_week="mon-fri"), id="execution_cycle")

        # Commentary — 18:00 ET weekdays
        self._scheduler.add_job(self._job_commentary, CronTrigger(
            hour=18, minute=0, day_of_week="mon-fri"), id="commentary")

        # Weekly deep refresh — Monday 09:00 ET
        self._scheduler.add_job(self._job_weekly_deep_refresh, CronTrigger(
            hour=9, minute=0, day_of_week="mon"), id="weekly_deep_refresh")

        self._scheduler.start()
        self.is_running = True
        log.info("✅ Scheduler started — 6 jobs registered")

    def stop(self):
        if self._scheduler and self.is_running:
            self._scheduler.shutdown(wait=False)
            self.is_running = False
            log.info("Scheduler stopped")

    def get_status(self) -> dict:
        jobs = []
        if self._scheduler and self.is_running:
            for job in self._scheduler.get_jobs():
                next_run = job.next_run_time
                jobs.append({
                    "id":       job.id,
                    "next_run": next_run.isoformat() if next_run else None,
                })

        return {
            "running":       self.is_running,
            "apscheduler":   APScheduler_AVAILABLE,
            "n_jobs":        len(jobs),
            "jobs":          jobs,
            "recent_history": self.job_history[-20:][::-1],
        }
