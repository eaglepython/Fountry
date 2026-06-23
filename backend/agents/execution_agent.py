"""
Execution Agent — Autonomous paper-trading bot.

Reads promoted signals → sizes positions → executes via Alpaca paper API
(free at alpaca.markets). Falls back to an in-memory paper portfolio when
no Alpaca keys are configured.

Position sizing: equal-weight Kelly-fractioned by signal confidence (ICIR).
Risk controls:
  - Max single position: 5% of NAV
  - Max gross exposure: 150%
  - Stop-loss: -2% per position
  - Daily drawdown circuit-breaker: -3% NAV
"""
import os, json, logging, time
from datetime import datetime, date
from typing import Dict, List, Optional
from pathlib import Path
import numpy as np

log = logging.getLogger(__name__)

ALPACA_LIVE_URL  = "https://api.alpaca.markets"
ALPACA_PAPER_URL = "https://paper-api.alpaca.markets"
ALPACA_BASE      = os.getenv("ALPACA_BASE_URL", ALPACA_LIVE_URL)

STATE_FILE    = Path("/tmp/alpha_foundry_cache/execution_state.json")
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

# ── In-memory paper portfolio ─────────────────────────────────────────────────

class PaperPortfolio:
    def __init__(self, initial_cash: float = 100_000.0):
        self.cash          = initial_cash
        self.initial_cash  = initial_cash
        self.positions: Dict[str, dict] = {}  # ticker → {qty, avg_cost, side}
        self.trades: List[dict] = []
        self.daily_pnl     = 0.0
        self._nav_open     = initial_cash

    @property
    def nav(self) -> float:
        pos_value = sum(p["qty"] * p["last_price"] for p in self.positions.values())
        return self.cash + pos_value

    @property
    def total_return_pct(self) -> float:
        return (self.nav / self.initial_cash - 1) * 100

    def fill(self, ticker: str, side: str, qty: int, price: float, signal_id: str):
        cost = qty * price
        if side == "BUY":
            if cost > self.cash:
                qty = int(self.cash / price)
                cost = qty * price
            if qty <= 0:
                return None
            self.cash -= cost
            if ticker in self.positions and self.positions[ticker]["side"] == "LONG":
                p = self.positions[ticker]
                total_qty = p["qty"] + qty
                p["avg_cost"] = (p["avg_cost"] * p["qty"] + price * qty) / total_qty
                p["qty"] = total_qty
            else:
                self.positions[ticker] = {"qty": qty, "avg_cost": price, "last_price": price, "side": "LONG", "signal": signal_id}
        else:  # SELL / SHORT
            if ticker in self.positions:
                p = self.positions[ticker]
                proceeds = qty * price
                pnl = (price - p["avg_cost"]) * qty
                self.cash += proceeds
                p["qty"] -= qty
                if p["qty"] <= 0:
                    del self.positions[ticker]
            else:
                return None

        trade = {
            "id":        f"TRD-{len(self.trades)+1:04d}",
            "ticker":    ticker,
            "side":      side,
            "qty":       qty,
            "price":     round(price, 2),
            "cost":      round(cost, 2),
            "signal":    signal_id,
            "timestamp": datetime.utcnow().isoformat(),
            "status":    "FILLED",
        }
        self.trades.append(trade)
        log.info(f"  PAPER FILL: {side} {qty}×{ticker} @ ${price:.2f} [{signal_id}]")
        return trade

    def update_prices(self, prices: Dict[str, float]):
        for ticker, price in prices.items():
            if ticker in self.positions:
                self.positions[ticker]["last_price"] = price

    def check_stops(self, stop_pct: float = 0.02) -> List[str]:
        """Return tickers that hit stop-loss."""
        triggered = []
        for ticker, p in self.positions.items():
            ret = (p["last_price"] - p["avg_cost"]) / p["avg_cost"]
            if ret < -stop_pct:
                triggered.append(ticker)
        return triggered

    def to_dict(self) -> dict:
        return {
            "cash":         round(self.cash, 2),
            "nav":          round(self.nav, 2),
            "initial_cash": self.initial_cash,
            "total_return": round(self.total_return_pct, 2),
            "n_positions":  len(self.positions),
            "positions": {t: {**p, "unrealized_pnl": round((p["last_price"] - p["avg_cost"]) * p["qty"], 2),
                              "return_pct": round((p["last_price"] / p["avg_cost"] - 1) * 100, 2)}
                          for t, p in self.positions.items()},
            "recent_trades": self.trades[-20:][::-1],
            "n_trades":     len(self.trades),
        }


# ── Alpaca client (optional, paper only) ─────────────────────────────────────

class AlpacaClient:
    def __init__(self, base_url: str = ALPACA_BASE):
        self.api_key    = os.getenv("ALPACA_API_KEY", "")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY", "")
        self.base_url   = base_url
        self.enabled    = bool(self.api_key and self.secret_key)
        self._headers   = {
            "APCA-API-KEY-ID":     self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type":        "application/json",
        }

    @property
    def mode(self) -> str:
        return "PAPER" if "paper-api" in self.base_url else "LIVE"

    def switch(self, mode: str):
        """Hot-switch between 'live' and 'paper' without restarting."""
        self.base_url = ALPACA_PAPER_URL if mode == "paper" else ALPACA_LIVE_URL
        log.info(f"Alpaca switched to {self.mode} → {self.base_url}")

    def _get(self, path: str) -> Optional[dict]:
        if not self.enabled:
            return None
        try:
            import requests
            r = requests.get(f"{self.base_url}{path}", headers=self._headers, timeout=5)
            return r.json() if r.ok else None
        except Exception as e:
            log.warning(f"Alpaca GET {path}: {e}")
            return None

    def _post(self, path: str, body: dict) -> Optional[dict]:
        if not self.enabled:
            return None
        try:
            import requests
            r = requests.post(f"{ALPACA_BASE}{path}", json=body, headers=self._headers, timeout=5)
            if r.ok:
                return r.json()
            else:
                log.warning(f"Alpaca POST {path} failed {r.status_code}: {r.text[:300]}")
                return None
        except Exception as e:
            log.warning(f"Alpaca POST {path}: {e}")
            return None

    def get_account(self) -> Optional[dict]:
        return self._get("/v2/account")

    def get_positions(self) -> Optional[list]:
        return self._get("/v2/positions")

    def submit_order(self, ticker: str, side: str, qty: int, order_type: str = "market") -> Optional[dict]:
        result = self._post("/v2/orders", {
            "symbol":        ticker,
            "qty":           str(qty),
            "side":          side.lower(),
            "type":          order_type,
            "time_in_force": "gtc",  # good-till-cancelled: works outside market hours
        })
        if result:
            log.info(f"Alpaca order submitted: {side} {qty}x{ticker} → id={result.get('id','?')} status={result.get('status','?')}")
        return result

    def close_position(self, ticker: str) -> Optional[dict]:
        try:
            import requests
            r = requests.delete(f"{self.base_url}/v2/positions/{ticker}", headers=self._headers, timeout=5)
            return r.json() if r.ok else None
        except Exception as e:
            log.warning(f"Alpaca close {ticker}: {e}")
            return None


# ── Execution Agent ───────────────────────────────────────────────────────────

class ExecutionAgent:
    """
    Autonomous trading agent.
    - Runs a rebalance cycle when `run_cycle()` is called by the scheduler.
    - Uses Alpaca paper API if keys are set, otherwise in-memory paper portfolio.
    - Emits structured logs + a state dict the frontend can poll.
    """

    MAX_POSITION_PCT  = 0.05   # 5% max per position
    MAX_GROSS_EXP     = 1.50   # 150% gross leverage
    STOP_LOSS_PCT     = 0.02   # 2% stop-loss
    DD_CIRCUIT_BREAK  = 0.03   # 3% daily NAV drawdown → halt trading

    def __init__(self):
        self.alpaca       = AlpacaClient()
        self.paper        = PaperPortfolio(initial_cash=100_000.0)
        self.is_running   = False
        self.last_cycle   = None
        self.cycle_log: List[dict] = []
        self.status       = "IDLE"
        self._load_state()
        log.info(f"ExecutionAgent init — alpaca_mode: {self.alpaca.mode}, enabled: {self.alpaca.enabled}")

    @property
    def mode(self) -> str:
        if not self.alpaca.enabled:
            return "IN_MEMORY_PAPER"
        return f"ALPACA_{self.alpaca.mode}"  # ALPACA_LIVE or ALPACA_PAPER

    def _load_state(self):
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE) as f:
                    state = json.load(f)
                self.paper.cash = state.get("cash", self.paper.cash)
                self.paper.trades = state.get("trades", [])
                # Sync _nav_open so circuit breaker doesn't trip immediately on restart
                self.paper._nav_open = self.paper.nav
                log.info(f"Loaded execution state: NAV=${self.paper.nav:,.0f}")
        except Exception:
            pass

    def _save_state(self):
        try:
            with open(STATE_FILE, "w") as f:
                json.dump({"cash": self.paper.cash, "trades": self.paper.trades[-200:]}, f)
        except Exception:
            pass

    def reset_circuit_breaker(self):
        """Reset the circuit breaker and re-anchor NAV open to current NAV."""
        self.status = "IDLE"
        self.paper._nav_open = self.paper.nav
        log.info(f"Circuit breaker reset — NAV anchor: ${self.paper.nav:,.0f}")
        return {"status": "ok", "nav": round(self.paper.nav, 2), "message": "Circuit breaker reset"}

    def _get_target_positions(self, signal_metrics: list) -> Dict[str, dict]:
        """
        Convert signal metrics → target position weights.
        Only use promoted signals. Size by normalized ICIR confidence.
        """
        promoted = [s for s in signal_metrics if s.get("promoted")]
        if not promoted:
            return {}

        # Map signal IDs to representative tickers
        SIGNAL_TICKERS = {
            "MOM12_1":   ["NVDA", "META", "AVGO"],
            "STREV":     ["JPM",  "GS"],
            "MOM_1M":    ["MSFT", "GOOGL"],
            "QUAL_ROE":  ["AAPL", "V"],
            "QUAL_GP":   ["COST", "MA"],
            "LOW_VOL":   ["JNJ",  "PG"],
            "LOW_BETA":  ["KO",   "ABT"],
            "COMBO_QVM": ["NVDA", "AAPL", "MSFT"],
        }

        targets = {}
        total_weight = 0.0
        for sig in promoted:
            sid   = sig.get("signal_id") or sig.get("id")
            icir  = float(sig.get("icir", 0.4))
            tickers = SIGNAL_TICKERS.get(sid, [])
            for ticker in tickers:
                w = min(icir / 2.0, self.MAX_POSITION_PCT)
                if ticker not in targets or targets[ticker]["weight"] < w:
                    targets[ticker] = {"weight": w, "signal": sid, "icir": icir}
                    total_weight += w

        # Normalize so gross exposure ≤ MAX_GROSS_EXP
        if total_weight > self.MAX_GROSS_EXP:
            scale = self.MAX_GROSS_EXP / total_weight
            for t in targets:
                targets[t]["weight"] *= scale

        return targets

    def _current_prices(self, tickers: List[str]) -> Dict[str, float]:
        """Get current prices via yfinance (or Alpaca if available)."""
        prices = {}
        try:
            import yfinance as yf
            if not tickers:
                return prices
            data = yf.download(tickers, period="2d", auto_adjust=True,
                                progress=False, threads=True)
            if hasattr(data.columns, "levels"):
                closes = data["Close"]
                for t in tickers:
                    if t in closes.columns:
                        val = closes[t].dropna()
                        if len(val) > 0:
                            prices[t] = float(val.iloc[-1])
            else:
                val = data["Close"].dropna()
                if len(val) > 0 and tickers:
                    prices[tickers[0]] = float(val.iloc[-1])
        except Exception as e:
            log.warning(f"Price fetch failed: {e}")
        return prices

    def run_cycle(self, signal_metrics: list) -> dict:
        """
        Main rebalance cycle.
        1. Get current prices
        2. Update P&L + check stops
        3. Compute target vs actual positions
        4. Execute diffs
        Returns a cycle summary dict.
        """
        if self.is_running:
            return {"status": "ALREADY_RUNNING"}

        self.is_running = True
        self.status     = "RUNNING"
        cycle_start     = time.time()
        actions         = []

        try:
            targets   = self._get_target_positions(signal_metrics)
            all_tickers = list(set(list(targets.keys()) + list(self.paper.positions.keys())))
            prices    = self._current_prices(all_tickers)
            if not prices:
                return {"status": "NO_PRICES", "message": "Could not fetch prices"}

            self.paper.update_prices(prices)
            nav = self.paper.nav

            # Circuit breaker
            daily_dd = (nav - self.paper._nav_open) / self.paper._nav_open
            if daily_dd < -self.DD_CIRCUIT_BREAK:
                self.status = "CIRCUIT_BREAKER"
                return {"status": "CIRCUIT_BREAKER", "daily_dd_pct": round(daily_dd * 100, 2)}

            # Stop-loss exits
            for ticker in self.paper.check_stops(self.STOP_LOSS_PCT):
                p = self.paper.positions.get(ticker)
                if p and ticker in prices:
                    trade = self.paper.fill(ticker, "SELL", p["qty"], prices[ticker], "STOP_LOSS")
                    if trade:
                        actions.append({**trade, "reason": "STOP_LOSS"})
                        if self.alpaca.enabled:
                            self.alpaca.close_position(ticker)

            # Rebalance: exit positions no longer in targets
            for ticker in list(self.paper.positions.keys()):
                if ticker not in targets and ticker in prices:
                    p = self.paper.positions[ticker]
                    trade = self.paper.fill(ticker, "SELL", p["qty"], prices[ticker], "REBALANCE_EXIT")
                    if trade:
                        actions.append({**trade, "reason": "EXIT"})
                        if self.alpaca.enabled:
                            self.alpaca.close_position(ticker)

            # Open / top-up target positions
            for ticker, target in targets.items():
                if ticker not in prices:
                    continue
                price        = prices[ticker]
                target_value = nav * target["weight"]
                target_qty   = int(target_value / price)
                current_qty  = self.paper.positions.get(ticker, {}).get("qty", 0)
                diff_qty     = target_qty - current_qty

                if diff_qty > 0:
                    trade = self.paper.fill(ticker, "BUY", diff_qty, price, target["signal"])
                    if trade:
                        actions.append({**trade, "reason": "ENTER/INCREASE"})
                        if self.alpaca.enabled:
                            self.alpaca.submit_order(ticker, "buy", diff_qty)
                elif diff_qty < 0:
                    trade = self.paper.fill(ticker, "SELL", abs(diff_qty), price, target["signal"])
                    if trade:
                        actions.append({**trade, "reason": "REDUCE"})
                        if self.alpaca.enabled:
                            self.alpaca.submit_order(ticker, "sell", abs(diff_qty))

            self.paper._nav_open = self.paper.nav
            self._save_state()
            self.last_cycle = datetime.utcnow().isoformat()
            self.status     = "IDLE"

            summary = {
                "status":     "OK",
                "timestamp":  self.last_cycle,
                "actions":    actions,
                "n_actions":  len(actions),
                "nav":        round(self.paper.nav, 2),
                "n_positions": len(self.paper.positions),
                "elapsed_s":  round(time.time() - cycle_start, 2),
                "mode":       self.mode,
            }
            self.cycle_log.append(summary)
            if len(self.cycle_log) > 50:
                self.cycle_log = self.cycle_log[-50:]
            return summary

        except Exception as e:
            log.error(f"Execution cycle error: {e}", exc_info=True)
            self.status = "ERROR"
            return {"status": "ERROR", "message": str(e)}
        finally:
            self.is_running = False

    def get_state(self) -> dict:
        state = self.paper.to_dict()
        state.update({
            "mode":         self.mode,
            "alpaca_mode":  self.alpaca.mode,   # "LIVE" or "PAPER"
            "alpaca_url":   self.alpaca.base_url,
            "status":       self.status,
            "last_cycle":   self.last_cycle,
            "alpaca_enabled": self.alpaca.enabled,
            "recent_cycles":  self.cycle_log[-5:][::-1],
        })
        # Augment with live Alpaca account if available
        if self.alpaca.enabled:
            acct = self.alpaca.get_account()
            if acct:
                state["alpaca_account"] = {
                    "equity":          acct.get("equity"),
                    "buying_power":    acct.get("buying_power"),
                    "portfolio_value": acct.get("portfolio_value"),
                    "cash":            acct.get("cash"),
                    "status":          acct.get("status"),
                }
        return state
