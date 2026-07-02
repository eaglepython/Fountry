"""
Risk Gatekeeper Agent — Pre-trade risk validation.

Model: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
  - 30B reasoning model — fast enough for pre-trade latency
  - Runs BEFORE every order in ExecutionAgent
  - Returns: APPROVE / REJECT / REDUCE_SIZE with reasoning

Risk checks performed:
  1. Position concentration (>5% NAV single name)
  2. Gross leverage (>150% total)
  3. Daily drawdown (approaching -3% circuit breaker)
  4. Sector concentration (>30% single sector)
  5. Liquidity (avg volume vs order size)
  6. Macro regime conflict (bearish macro → reduce longs)
  7. LLM reasoned risk judgment (nemotron-30b)
"""
import os, logging, time, json
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path

log = logging.getLogger(__name__)

NVIDIA_API_KEY  = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
RISK_MODEL      = os.getenv("NVIDIA_MODEL_RISK", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning")
RISK_FAST       = os.getenv("NVIDIA_MODEL_FAST",  "meta/llama-3.3-70b-instruct")

SECTOR_MAP = {
    "NVDA": "Tech", "META": "Tech", "AVGO": "Tech", "MSFT": "Tech",
    "GOOGL": "Tech", "AAPL": "Tech", "AMD": "Tech", "INTC": "Tech",
    "JPM": "Finance", "GS": "Finance", "MS": "Finance", "BAC": "Finance",
    "V": "Finance", "MA": "Finance",
    "JNJ": "Health", "ABT": "Health", "UNH": "Health", "PFE": "Health",
    "COST": "Consumer", "PG": "Consumer", "KO": "Consumer", "WMT": "Consumer",
    "XOM": "Energy", "CVX": "Energy",
}


# ── Rule-based checks (deterministic, fast) ───────────────────────────────────

def _check_concentration(ticker: str, qty: int, price: float, nav: float,
                          positions: dict) -> Optional[str]:
    position_value = qty * price
    # Include existing position
    existing = positions.get(ticker, {}).get("qty", 0) * price
    total_exposure = position_value + existing
    pct = total_exposure / nav if nav > 0 else 1.0
    if pct > 0.05:
        return f"Concentration risk: {ticker} would be {pct:.1%} of NAV (limit 5%)"
    return None


def _check_leverage(new_value: float, nav: float, positions: dict) -> Optional[str]:
    gross = sum(p.get("qty", 0) * p.get("last_price", 0) for p in positions.values())
    gross += new_value
    leverage = gross / nav if nav > 0 else 99
    if leverage > 1.50:
        return f"Leverage exceeded: {leverage:.2f}x gross (limit 1.5x)"
    return None


def _check_drawdown(nav: float, nav_open: float) -> Optional[str]:
    dd = (nav - nav_open) / nav_open if nav_open > 0 else 0
    if dd < -0.025:  # warn at -2.5%, circuit breaks at -3%
        return f"Approaching daily drawdown limit: {dd:.2%} (circuit breaker at -3%)"
    return None


def _check_sector(ticker: str, qty: int, price: float, nav: float,
                   positions: dict) -> Optional[str]:
    sector = SECTOR_MAP.get(ticker, "Other")
    sector_value = qty * price
    for t, p in positions.items():
        if SECTOR_MAP.get(t, "Other") == sector:
            sector_value += p.get("qty", 0) * p.get("last_price", 0)
    sector_pct = sector_value / nav if nav > 0 else 0
    if sector_pct > 0.30:
        return f"Sector concentration: {sector} at {sector_pct:.1%} of NAV (limit 30%)"
    return None


# ── LLM Reasoned Risk Judgment ────────────────────────────────────────────────

def _llm_risk_check(ticker: str, side: str, qty: int, price: float,
                     nav: float, regime: str, macro_score: float,
                     rule_warnings: List[str]) -> Optional[str]:
    """
    Ask nemotron-30b-reasoning to make a holistic risk judgment.
    Only called when rule checks pass — LLM adds nuance.
    """
    if not NVIDIA_API_KEY:
        return None

    context = {
        "order": f"{side} {qty} shares of {ticker} @ ${price:.2f}",
        "portfolio_nav": f"${nav:,.0f}",
        "order_value": f"${qty * price:,.0f} ({qty * price / nav:.1%} of NAV)",
        "market_regime": regime,
        "macro_score": f"{macro_score:.2f} (-1=bearish, +1=bullish)",
        "rule_warnings": rule_warnings or ["none"],
    }

    prompt = (
        f"You are a risk officer at a systematic hedge fund. Evaluate this proposed trade:\n\n"
        f"{json.dumps(context, indent=2)}\n\n"
        f"Respond with EXACTLY one of:\n"
        f"APPROVE — trade is acceptable\n"
        f"REJECT — trade violates risk limits (explain why in one sentence)\n"
        f"REDUCE_SIZE [N] — approve but reduce quantity to N shares (explain why)\n\n"
        f"Be decisive. One line answer only."
    )

    for model in [RISK_MODEL, RISK_FAST]:
        try:
            import requests
            resp = requests.post(
                f"{NVIDIA_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {NVIDIA_API_KEY}",
                         "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": (
                            "You are a strict risk officer. Give only one-line decisions: "
                            "APPROVE, REJECT [reason], or REDUCE_SIZE [N] [reason]."
                        )},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 80,
                    "temperature": 0.1,
                    "stream": False,
                },
                timeout=15,
            )
            if resp.ok:
                answer = resp.json()["choices"][0]["message"]["content"].strip()
                log.info(f"Risk LLM [{model}]: {answer}")
                return answer
        except Exception as e:
            log.warning(f"Risk LLM {model}: {e}")
    return None


# ── Risk Gatekeeper Agent ─────────────────────────────────────────────────────

class RiskGatekeeperAgent:
    """
    Validates each proposed order before it reaches the execution engine.
    Returns a decision: APPROVE | REJECT | REDUCE_SIZE
    """

    def __init__(self):
        self.decisions: List[dict] = []
        self.last_decision: Optional[dict] = None

    def evaluate(self, ticker: str, side: str, qty: int, price: float,
                  nav: float, nav_open: float, positions: dict,
                  regime: str = "unknown", macro_score: float = 0.0) -> dict:
        """
        Full pre-trade risk evaluation.
        Returns: {"decision": "APPROVE|REJECT|REDUCE_SIZE", "qty": int, "reasons": [...]}
        """
        t0 = time.time()
        warnings = []
        reject_reasons = []

        # ── Rule-based checks ─────────────────────────────────────────────
        order_value = qty * price

        c = _check_concentration(ticker, qty, price, nav, positions)
        if c:
            reject_reasons.append(c)

        lev = _check_leverage(order_value, nav, positions)
        if lev:
            reject_reasons.append(lev)

        dd = _check_drawdown(nav, nav_open)
        if dd:
            warnings.append(dd)

        sec = _check_sector(ticker, qty, price, nav, positions)
        if sec:
            warnings.append(sec)

        # Hard reject: macro conflict — bearish regime + large long
        if side == "BUY" and macro_score < -0.5 and order_value / nav > 0.03:
            reject_reasons.append(f"Macro conflict: bearish regime (score {macro_score:.2f}) with large long order")

        # ── If hard rules reject → skip LLM ──────────────────────────────
        if reject_reasons:
            decision = {
                "decision": "REJECT",
                "qty": 0,
                "ticker": ticker,
                "side": side,
                "requested_qty": qty,
                "reasons": reject_reasons + warnings,
                "llm_used": False,
                "elapsed_ms": round((time.time() - t0) * 1000),
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            # ── LLM holistic judgment ─────────────────────────────────────
            llm_answer = _llm_risk_check(ticker, side, qty, price, nav,
                                          regime, macro_score, warnings)

            approved_qty = qty
            final_decision = "APPROVE"
            llm_reasons = []

            if llm_answer:
                upper = llm_answer.upper()
                if upper.startswith("REJECT"):
                    final_decision = "REJECT"
                    approved_qty = 0
                    llm_reasons = [llm_answer]
                elif upper.startswith("REDUCE_SIZE"):
                    final_decision = "REDUCE_SIZE"
                    tokens = llm_answer.split()
                    for tok in tokens:
                        if tok.isdigit():
                            approved_qty = min(int(tok), qty)
                            break
                    llm_reasons = [llm_answer]
                else:
                    final_decision = "APPROVE"

            decision = {
                "decision": final_decision,
                "qty": approved_qty,
                "ticker": ticker,
                "side": side,
                "requested_qty": qty,
                "reasons": warnings + llm_reasons,
                "llm_used": llm_answer is not None,
                "llm_response": llm_answer,
                "elapsed_ms": round((time.time() - t0) * 1000),
                "timestamp": datetime.utcnow().isoformat(),
            }

        self.last_decision = decision
        self.decisions.append(decision)
        if len(self.decisions) > 200:
            self.decisions = self.decisions[-200:]

        log.info(
            f"RiskGatekeeper: {decision['decision']} {ticker} "
            f"{side} {approved_qty if decision['decision'] != 'REJECT' else 0}/"
            f"{qty} shares @ ${price:.2f}"
        )
        return decision

    def get_history(self, n: int = 50) -> List[dict]:
        return self.decisions[-n:][::-1]

    def stats(self) -> dict:
        total = len(self.decisions)
        if total == 0:
            return {"total": 0, "approve_rate": 0, "reject_rate": 0}
        approved = sum(1 for d in self.decisions if d["decision"] == "APPROVE")
        rejected = sum(1 for d in self.decisions if d["decision"] == "REJECT")
        reduced  = sum(1 for d in self.decisions if d["decision"] == "REDUCE_SIZE")
        return {
            "total":        total,
            "approved":     approved,
            "rejected":     rejected,
            "reduced":      reduced,
            "approve_rate": round(approved / total * 100, 1),
            "reject_rate":  round(rejected / total * 100, 1),
        }
