"""
LLM Commentary Agent — Analyzes signal metrics and writes institutional-grade
research commentary.

Model assignments (NVIDIA NIM — purpose-built per task):
  COMMENTARY  : writer/palmyra-fin-70b-32k        — finance-specialist 70B, 32k context
  REGIME      : stockmark/stockmark-2-100b-instruct — stock market domain expert 100B
  REASONING   : nvidia/llama-3.1-nemotron-ultra-253b-v1 — deep reasoning 253B
  FALLBACK    : deepseek-ai/deepseek-v4-pro        — best general reasoning
  FAST        : meta/llama-3.3-70b-instruct        — fast responses

Priority chain: NVIDIA NIM → Ollama (local) → Groq → Template engine

Set environment variables in .env:
  NVIDIA_API_KEY=nvapi-...
  NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
"""
import os, logging, time, json, threading
from datetime import datetime
from typing import Optional, List
from pathlib import Path
import numpy as np

log = logging.getLogger(__name__)

COMMENTARY_CACHE = Path("/tmp/alpha_foundry_cache/commentary.json")
COMMENTARY_CACHE.parent.mkdir(parents=True, exist_ok=True)

NVIDIA_API_KEY  = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
OLLAMA_HOST     = os.getenv("OLLAMA_HOST",     "http://localhost:11434")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY",    "")

# ── NVIDIA Model Registry — purpose-built per agent task ─────────────────────
NVIDIA_MODELS = {
    # Primary commentary model — finance specialist, 32k context window
    "commentary":  os.getenv("NVIDIA_MODEL_COMMENTARY", "writer/palmyra-fin-70b-32k"),
    # Regime + macro analysis — stock market domain expert
    "regime":      os.getenv("NVIDIA_MODEL_REGIME",     "stockmark/stockmark-2-100b-instruct"),
    # Deep signal reasoning — ultra-large reasoning model
    "reasoning":   os.getenv("NVIDIA_MODEL_REASONING",  "nvidia/llama-3.1-nemotron-ultra-253b-v1"),
    # Macro dissent — second opinion, large general model
    "dissent":     os.getenv("NVIDIA_MODEL_DISSENT",    "qwen/qwen3.5-397b-a17b"),
    # Earnings / catalyst watch — finance specialist
    "earnings":    os.getenv("NVIDIA_MODEL_EARNINGS",   "writer/palmyra-fin-70b-32k"),
    # Portfolio optimizer — deep reasoning
    "optimizer":   os.getenv("NVIDIA_MODEL_OPTIMIZER",  "nvidia/llama-3.1-nemotron-ultra-253b-v1"),
    # Fallback / fast inference
    "fast":        os.getenv("NVIDIA_MODEL_FAST",       "meta/llama-3.3-70b-instruct"),
    # General fallback
    "default":     os.getenv("NVIDIA_MODEL",            "deepseek-ai/deepseek-v4-pro"),
}

# Keep backward compat
NVIDIA_MODEL = NVIDIA_MODELS["commentary"]


# ── LLM Backends ─────────────────────────────────────────────────────────────

def _call_nvidia(prompt: str, task: str = "commentary") -> Optional[str]:
    """Call NVIDIA NIM API with the right model for each task.

    Tasks:
      commentary  → writer/palmyra-fin-70b-32k   (finance specialist)
      regime      → stockmark/stockmark-2-100b   (market domain expert)
      reasoning   → nvidia/nemotron-ultra-253b   (deep reasoning)
      fast        → meta/llama-3.3-70b           (quick responses)
      default     → deepseek-v4-pro              (general fallback)
    """
    if not NVIDIA_API_KEY:
        return None

    model = NVIDIA_MODELS.get(task, NVIDIA_MODELS["default"])

    # System prompts tailored per task
    system_prompts = {
        "commentary": (
            "You are a senior quantitative analyst at a world-class systematic hedge fund. "
            "Your research notes are precise, data-driven, and institutional in tone. "
            "Combine rigorous statistical reasoning with deep market intuition to produce "
            "actionable alpha insights. Write in flowing prose — no bullet lists."
        ),
        "regime": (
            "You are a macro strategist and market regime expert. You analyze economic cycles, "
            "volatility regimes, yield curves, and cross-asset signals to classify market states "
            "and predict regime transitions. Be precise and data-driven."
        ),
        "reasoning": (
            "You are an expert quantitative researcher. Think step-by-step through complex "
            "financial data, signal interactions, and statistical relationships. "
            "Provide deep analytical reasoning with specific data references."
        ),
        "dissent": (
            "You are a contrarian macro strategist. Your role is to challenge the consensus view "
            "and identify risks that other analysts miss. Provide a rigorous second opinion on "
            "the current market regime and signal allocations. Be direct and specific."
        ),
        "earnings": (
            "You are a fundamental analyst specializing in earnings catalysts and corporate events. "
            "Analyze upcoming earnings, guidance, and corporate actions that could affect "
            "quantitative signal performance. Focus on timing and magnitude of potential impact."
        ),
        "optimizer": (
            "You are a portfolio optimization expert. Analyze the current portfolio composition, "
            "signal weights, risk metrics, and macro regime to recommend specific allocation "
            "adjustments that improve risk-adjusted returns. Be quantitative and specific."
        ),
        "fast": (
            "You are a concise quantitative analyst. Provide brief, accurate financial analysis."
        ),
        "default": (
            "You are a senior quantitative analyst. Be precise, data-driven, and institutional."
        ),
    }
    system = system_prompts.get(task, system_prompts["default"])

    try:
        import requests
        resp = requests.post(
            f"{NVIDIA_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {NVIDIA_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "model":       model,
                "messages":    [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt},
                ],
                "max_tokens":  1024,
                "temperature": 0.35,
                "top_p":       0.9,
                "stream":      False,
            },
            timeout=60,
        )
        if resp.ok:
            content = resp.json()["choices"][0]["message"]["content"].strip()
            log.info(f"NVIDIA NIM [{task}] ({model}): {len(content)} chars")
            return content
        else:
            log.warning(f"NVIDIA [{task}] {resp.status_code}: {resp.text[:200]}")
            # Try fast fallback model if primary failed
            if task != "fast" and task != "default":
                log.info(f"Retrying with fast fallback model…")
                return _call_nvidia(prompt, task="fast")
    except Exception as e:
        log.warning(f"NVIDIA NIM [{task}] unavailable: {e}")
    return None


def _call_ollama(prompt: str, model: str = "llama3") -> Optional[str]:
    """Call local Ollama instance. Free, runs on your machine."""
    try:
        import requests
        resp = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        if resp.ok:
            return resp.json().get("response", "").strip()
    except Exception as e:
        log.debug(f"Ollama unavailable: {e}")
    return None


def _call_groq(prompt: str, model: str = "llama3-8b-8192") -> Optional[str]:
    """Call Groq API (free tier: 30 req/min, 6000 RPD)."""
    if not GROQ_API_KEY:
        return None
    try:
        import requests
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a quantitative research analyst at a systematic hedge fund. Be precise, concise, and institutional in tone."},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 600,
                "temperature": 0.4,
            },
            timeout=20,
        )
        if resp.ok:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.debug(f"Groq unavailable: {e}")
    return None


def _call_llm(prompt: str, task: str = "commentary") -> Optional[str]:
    """Try NVIDIA NIM (task-specific model) → Ollama → Groq → None."""
    result = _call_nvidia(prompt, task=task)
    if result:
        return result
    result = _call_ollama(prompt)
    if result:
        return result
    return _call_groq(prompt)


# ── Template Commentary (always-available fallback) ───────────────────────────

def _template_commentary(context: dict) -> str:
    """Report only measured inputs; never fill missing performance with guesses."""
    promoted      = context.get("promoted_signals", [])
    review        = context.get("review_signals", [])
    top_signal    = context.get("top_signal", {})
    regime        = context.get("regime", "bull")
    portfolio_ret = context.get("portfolio_return")
    portfolio_sr  = context.get("portfolio_sharpe")
    macro         = context.get("macro_summary", {})

    regime_desc = {
        "bull": "a trending bull market with low volatility",
        "bear": "a bear market environment with elevated volatility",
        "crisis": "a crisis regime with extreme vol and correlation spikes",
        "range": "a range-bound, mean-reverting environment",
        "inflate": "an inflationary regime with rising rates",
    }.get(regime, "unclassified (no validated historical classification available)")

    top_name = top_signal.get("name")

    vix_line = ""
    yc_line  = ""
    if macro.get("volatility") and macro["volatility"].get("value") is not None:
        vix_line = f" Volatility indicator: {macro['volatility']['value']} ({macro['volatility'].get('signal', 'unclassified')})."
    if macro.get("yield_curve") and macro["yield_curve"].get("value") is not None:
        yc_line = f" Yield curve indicator: {macro['yield_curve']['value']} ({macro['yield_curve'].get('signal', 'unclassified')})."

    lines = [
        f"## Fountry — Signal Intelligence Report",
        f"*{datetime.utcnow().strftime('%B %d, %Y · %H:%M UTC')} · Auto-generated*",
        "",
        f"### Market Environment",
        f"Current data indicate {regime_desc}.{vix_line}{yc_line}",
        "",
        f"### Signal Universe",
        f"The research universe contains **{len(promoted) + len(review)} signals**, "
        f"{len(promoted)} signals are approved for execution and {len(review)} are not. "
        "IC observations alone are exploratory and do not establish profitability.",
        "",
        f"### Signal observations",
        (f"The leading candidate by observed IC is **{top_name}**. Its observed mean IC is "
         f"{top_signal.get('ic')} across {top_signal.get('n_periods', 0)} periods. This is not an estimate of returns."
         if top_name else "No signal is approved for execution. Point-in-time histories and after-cost results are unavailable."),
        "",
        f"### Portfolio Performance",
        (f"Portfolio annual return: {portfolio_ret}%; Sharpe: {portfolio_sr}."
         if portfolio_ret is not None and portfolio_sr is not None
         else "Portfolio performance is unavailable; no validated after-cost backtest is connected."),
        "",
        f"### Data limitations",
        "The available IC observations use a present-day ticker universe and are not a point-in-time, after-cost investment backtest.",
        "",
        f"*This report is generated by the Fountry AI agent. "
          f"For research purposes only. Not financial advice.*",
    ]
    return "\n".join(lines)


# ── Prompt Builder ────────────────────────────────────────────────────────────

def _build_prompt(context: dict) -> str:
    promoted   = context.get("promoted_signals", [])
    top_signal = context.get("top_signal", {})
    regime     = context.get("regime", "bull")
    macro      = context.get("macro_summary", {})

    top_metrics = "\n".join(
        f"  - {s.get('name', '?')}: observed IC={s.get('ic')}, periods={s.get('n_periods', 0)}"
        for s in promoted[:5]
    ) or "  - none"

    macro_str = ""
    for k, v in macro.items():
        if isinstance(v, dict):
            macro_str += f"\n  - {v.get('name', k)}: {v.get('value', '?')} — {v.get('signal', '')}"

    return f"""Write a concise research status note using only the supplied values.
Do not invent, estimate, extrapolate, or imply returns, Sharpe, capacity, statistical significance,
portfolio positions, or profitability. If a value is unavailable, state that it is unavailable.
Do not recommend or authorize trades. An IC is not a portfolio return.

Data:
- Current regime: {regime}
- Promoted signals ({len(promoted)} total):{top_metrics}
- Macro indicators:{macro_str if macro_str else ' unavailable'}
- Portfolio return: {context.get('portfolio_return')}, Sharpe: {context.get('portfolio_sharpe')}

Tone: institutional, data-driven, concise. No bullet lists in the output — prose only."""


# ── LLM Commentary Agent ──────────────────────────────────────────────────────

class LLMCommentaryAgent:
    """
    Generates signal intelligence reports.
    Caches the last report; regenerates when called with fresh data.
    """

    def __init__(self):
        self.last_report:  Optional[dict] = None
        self.is_generating = False
        self._generation_lock = threading.Lock()
        self._load_cache()

    def _load_cache(self):
        try:
            if COMMENTARY_CACHE.exists():
                with open(COMMENTARY_CACHE) as f:
                    cached = json.load(f)
                self.last_report = cached if cached.get("schema_version") == 2 else None
        except Exception:
            pass

    def _save_cache(self, report: dict):
        try:
            with open(COMMENTARY_CACHE, "w") as f:
                json.dump(report, f, indent=2)
        except Exception:
            pass

    def generate(self, signal_metrics: list, portfolio_perf: dict,
                 regime: str, macro_signals: dict) -> dict:
        if not self._generation_lock.acquire(blocking=False):
            return self.last_report or {"status": "generating"}
        if self.is_generating:
            self._generation_lock.release()
            return self.last_report or {"status": "generating"}
        self.is_generating = True
        t0 = time.time()

        try:
            promoted = [s for s in signal_metrics if s.get("promoted")]
            review   = [s for s in signal_metrics if not s.get("promoted")]
            top = max(promoted, key=lambda s: float(s.get("ic", 0)), default={}) if promoted else {}
            avg_ic = float(np.mean([float(s["ic"]) for s in promoted if s.get("ic") is not None])) if any(s.get("ic") is not None for s in promoted) else None

            context = {
                "promoted_signals":  promoted,
                "review_signals":    review,
                "avg_ic":            avg_ic,
                "top_signal":        top,
                "regime":            regime,
                "portfolio_return":  portfolio_perf.get("ann_return"),
                "portfolio_sharpe":  portfolio_perf.get("sharpe"),
                "macro_summary":     macro_signals,
            }

            # Try LLM first (NVIDIA finance model → Ollama → Groq), fall back to template
            llm_text = _call_llm(_build_prompt(context), task="commentary")
            template_text = _template_commentary(context)

            # Determine which backend was used
            if llm_text and NVIDIA_API_KEY:
                llm_source = "nvidia"
                model_used = NVIDIA_MODELS["commentary"]
            elif llm_text and GROQ_API_KEY:
                llm_source = "groq"
                model_used = "llama3-8b-8192"
            elif llm_text:
                llm_source = "ollama"
                model_used = "llama3"
            else:
                llm_source = "template"
                model_used = "template"

            report = {
                "schema_version": 2,
                "status":        "ok",
                "timestamp":     datetime.utcnow().isoformat(),
                "regime":        regime,
                "llm_available": llm_text is not None,
                "source":        llm_source,
                "model":         model_used,
                "backend":       "nvidia_nim" if llm_source == "nvidia" else llm_source,
                "commentary":    llm_text or template_text,
                "template":      template_text,  # always include template version
                "stats": {
                    "n_promoted":  len(promoted),
                    "n_review":    len(review),
                    "avg_ic":      round(float(avg_ic), 4) if avg_ic is not None else None,
                    "top_signal":  top.get("name", "—"),
                    "portfolio_return": portfolio_perf.get("ann_return"),
                    "portfolio_sharpe": portfolio_perf.get("sharpe"),
                },
                "elapsed_s": round(time.time() - t0, 2),
            }
            self.last_report = report
            self._save_cache(report)
            return report

        except Exception as e:
            log.error(f"Commentary generation failed: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
        finally:
            self.is_generating = False
            self._generation_lock.release()

    def get_last(self) -> dict:
        if self.last_report:
            return self.last_report
        return {
            "status":    "not_generated",
            "commentary": "No report yet. The agent will generate one automatically after data loads.",
            "llm_available": _call_ollama("ping", "llama3") is not None,
        }

    def generate_earnings_alert(self, signal_metrics: list, tickers: List[str],
                                  regime: str) -> dict:
        """
        Scan for upcoming earnings catalysts that could impact signal positions.
        Uses writer/palmyra-fin-70b-32k (earnings task).
        """
        t0 = time.time()
        promoted = [s for s in signal_metrics if s.get("promoted")]
        prompt = (
            f"You are a fundamental analyst. Given these quantitative signal positions:\n"
            f"Tickers: {', '.join(tickers[:20])}\n"
            f"Market regime: {regime}\n"
            f"Promoted signals: {len(promoted)}\n\n"
            f"Identify: (1) Which of these tickers likely have earnings in the next 2-4 weeks? "
            f"(2) What is the historical earnings surprise pattern for momentum stocks in a {regime} regime? "
            f"(3) Which positions should be reduced pre-earnings and which held through? "
            f"(4) Top 3 risk events to watch this week. "
            f"Be specific and actionable. 3 paragraphs."
        )
        text = _call_llm(prompt, task="earnings")
        report = {
            "status":    "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "type":      "earnings_alert",
            "tickers":   tickers[:20],
            "regime":    regime,
            "analysis":  text or "Earnings analysis unavailable — NVIDIA API not configured.",
            "model":     NVIDIA_MODELS["earnings"],
            "elapsed_s": round(time.time() - t0, 2),
        }
        return report

    def generate_macro_dissent(self, regime: str, macro_signals: dict,
                                signal_metrics: list) -> dict:
        """
        Second-opinion contrarian view using qwen3.5-397b-a17b (dissent task).
        Challenges the current regime classification and signal allocations.
        """
        t0 = time.time()
        macro_str = ""
        for k, v in macro_signals.items():
            if isinstance(v, dict):
                macro_str += f"  {v.get('name', k)}: {v.get('value', '?')} [{v.get('signal', '')}]\n"

        promoted = [s.get("id") or s.get("signal_id", "?") for s in signal_metrics if s.get("promoted")]
        prompt = (
            f"You are a contrarian macro strategist. Provide a rigorous second opinion challenging "
            f"the current market assessment:\n\n"
            f"Consensus regime: {regime}\n"
            f"Current long signals: {', '.join(promoted)}\n"
            f"Macro data:\n{macro_str}\n"
            f"Challenge: (1) What could make the regime call wrong? "
            f"(2) What tail risks are being ignored? "
            f"(3) Which signal allocations are most dangerous if the consensus is wrong? "
            f"(4) What would you do differently? "
            f"Be direct and provocative. 3 paragraphs."
        )
        text = _call_llm(prompt, task="dissent")
        report = {
            "status":    "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "type":      "macro_dissent",
            "regime":    regime,
            "analysis":  text or "Dissent analysis unavailable — NVIDIA API not configured.",
            "model":     NVIDIA_MODELS["dissent"],
            "elapsed_s": round(time.time() - t0, 2),
        }
        return report

    def generate_optimizer_recommendation(self, portfolio_state: dict,
                                           signal_metrics: list,
                                           macro_signals: dict,
                                           regime: str) -> dict:
        """
        Portfolio optimization recommendations using nvidia/nemotron-ultra-253b-v1.
        Analyzes current allocations and suggests specific weight adjustments.
        """
        t0 = time.time()
        promoted = [s for s in signal_metrics if s.get("promoted")]
        positions = portfolio_state.get("positions", {})
        nav       = portfolio_state.get("nav", 0)

        pos_str = ""
        for ticker, p in list(positions.items())[:10]:
            pct = p.get("qty", 0) * p.get("last_price", 0) / nav * 100 if nav else 0
            pos_str += f"  {ticker}: {pct:.1f}% NAV, PnL={p.get('unrealized_pnl', 0):+.0f}\n"

        sig_str = ""
        for s in promoted[:5]:
            sig_str += f"  {s.get('id','?')}: IC={s.get('ic',0):.4f}, Sharpe={s.get('net_sharpe',0):.2f}\n"

        prompt = (
            f"You are a portfolio optimization expert. Analyze and recommend adjustments:\n\n"
            f"Regime: {regime}\n"
            f"NAV: ${nav:,.0f}\n"
            f"Current positions:\n{pos_str or '  None'}\n"
            f"Live signals:\n{sig_str or '  None'}\n\n"
            f"Recommend: (1) Specific allocation % changes for each position. "
            f"(2) Which signals to increase/decrease weight. "
            f"(3) Target portfolio metrics (Sharpe, max drawdown, gross exposure). "
            f"(4) Estimated improvement in risk-adjusted return. "
            f"Be quantitative — use specific percentages. 4 paragraphs."
        )
        text = _call_llm(prompt, task="optimizer")
        report = {
            "status":    "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "type":      "optimizer",
            "regime":    regime,
            "nav":       nav,
            "analysis":  text or "Optimizer unavailable — NVIDIA API not configured.",
            "model":     NVIDIA_MODELS["optimizer"],
            "elapsed_s": round(time.time() - t0, 2),
        }
        return report
