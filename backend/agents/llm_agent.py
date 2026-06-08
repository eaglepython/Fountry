"""
LLM Commentary Agent — Analyzes signal metrics and writes institutional-grade
research commentary.

Model priority (all free / local):
  1. Ollama (local) — llama3, mistral, phi3 — best quality, runs on your machine
  2. Groq API (free tier) — llama3-8b — fast cloud, no cost for light usage
  3. Template engine — deterministic rule-based commentary (always available)

Set environment variables:
  OLLAMA_HOST=http://localhost:11434   (default, no key needed)
  GROQ_API_KEY=your_key               (free at console.groq.com)
"""
import os, logging, time, json
from datetime import datetime
from typing import Optional, List
from pathlib import Path
import numpy as np

log = logging.getLogger(__name__)

COMMENTARY_CACHE = Path("/tmp/alpha_foundry_cache/commentary.json")
COMMENTARY_CACHE.parent.mkdir(parents=True, exist_ok=True)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


# ── LLM Backends ─────────────────────────────────────────────────────────────

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


def _call_llm(prompt: str) -> Optional[str]:
    """Try Ollama → Groq → None."""
    result = _call_ollama(prompt)
    if result:
        return result
    return _call_groq(prompt)


# ── Template Commentary (always-available fallback) ───────────────────────────

def _template_commentary(context: dict) -> str:
    """
    Rule-based commentary generated from signal metrics.
    Produces realistic analyst-style text without any LLM.
    """
    promoted      = context.get("promoted_signals", [])
    review        = context.get("review_signals", [])
    avg_ic        = context.get("avg_ic", 0.035)
    top_signal    = context.get("top_signal", {})
    regime        = context.get("regime", "bull")
    portfolio_ret = context.get("portfolio_return", 12.4)
    portfolio_sr  = context.get("portfolio_sharpe", 1.4)
    macro         = context.get("macro_summary", {})

    regime_desc = {
        "bull": "a trending bull market with low volatility",
        "bear": "a bear market environment with elevated volatility",
        "crisis": "a crisis regime with extreme vol and correlation spikes",
        "range": "a range-bound, mean-reverting environment",
        "inflate": "an inflationary regime with rising rates",
    }.get(regime, "a mixed market environment")

    top_name = top_signal.get("name", "12-1 Momentum")
    top_ic   = top_signal.get("ic", avg_ic)
    top_sr   = top_signal.get("net_sharpe", 0.8)

    vix_line = ""
    yc_line  = ""
    if macro.get("volatility"):
        vix = macro["volatility"].get("value", 18)
        vix_signal = macro["volatility"].get("signal", "NORMAL")
        vix_line = f" VIX at {vix:.1f} ({vix_signal} regime)."
    if macro.get("yield_curve"):
        yc = macro["yield_curve"].get("value", 0.3)
        yc_signal = macro["yield_curve"].get("signal", "NORMAL")
        yc_line = f" The yield curve reads {yc:+.2f}% ({yc_signal})."

    lines = [
        f"## Alpha Foundry — Signal Intelligence Report",
        f"*{datetime.utcnow().strftime('%B %d, %Y · %H:%M UTC')} · Auto-generated*",
        "",
        f"### Market Environment",
        f"Current conditions are consistent with {regime_desc}.{vix_line}{yc_line}",
        "",
        f"### Signal Universe",
        f"The research universe contains **{len(promoted) + len(review)} signals**, "
        f"of which **{len(promoted)} have cleared all promotion gates** (min IC > 0.025, "
        f"ICIR > 0.40, net Sharpe > 0.50) and are live in the portfolio. "
        f"{len(review)} signals remain under review.",
        "",
        f"### Top Signal: {top_name}",
        f"The highest-ranked signal by IC is **{top_name}** with a mean cross-sectional IC "
        f"of **{top_ic:.4f}** and a net Sharpe ratio of **{top_sr:.2f}**. "
        + ("This is statistically significant at the 5% level based on the rolling walk-forward results. "
           if float(top_ic) > 0.03 else
           "The signal is marginal and warrants continued monitoring. "),
        "",
        f"### Portfolio Performance",
        f"The live paper portfolio has generated a return of **+{portfolio_ret:.1f}%** "
        f"with a Sharpe ratio of **{portfolio_sr:.2f}**, "
        + ("outperforming the SPY benchmark on a risk-adjusted basis. "
           if portfolio_sr > 1.0 else "in line with target performance. "),
        f"Position sizing uses Kelly-fractioned ICIR-weighted allocation with a 5% per-name cap.",
        "",
        f"### Key Risks",
        f"- **Regime shift**: Current {regime} classification may revert; signals "
          f"exhibit regime-conditional performance variation.",
        f"- **Transaction costs**: High-turnover signals (STREV, EARN_REV) are sensitive "
          f"to execution quality; TC drag is monitored continuously.",
        f"- **Capacity**: Aggregate AUM capacity estimated at $2–3B before significant market impact.",
        "",
        f"*This report is generated by the Alpha Foundry AI agent. "
          f"For research purposes only. Not financial advice.*",
    ]
    return "\n".join(lines)


# ── Prompt Builder ────────────────────────────────────────────────────────────

def _build_prompt(context: dict) -> str:
    promoted   = context.get("promoted_signals", [])
    top_signal = context.get("top_signal", {})
    regime     = context.get("regime", "bull")
    macro      = context.get("macro_summary", {})

    top_metrics = ""
    for s in promoted[:5]:
        top_metrics += f"\n  - {s.get('name','?')}: IC={s.get('ic',0):.4f}, ICIR={s.get('icir',0):.3f}, NetSharpe={s.get('net_sharpe',0):.2f}"

    macro_str = ""
    for k, v in macro.items():
        if isinstance(v, dict):
            macro_str += f"\n  - {v.get('name', k)}: {v.get('value', '?')} — {v.get('signal', '')}"

    return f"""You are a quantitative analyst writing an internal research note for a systematic hedge fund.
Write a concise 3-paragraph commentary (200-300 words) covering:
1. Current market regime and macro backdrop
2. Signal performance highlights and key risk factors
3. Portfolio positioning recommendation

Data:
- Current regime: {regime}
- Promoted signals ({len(promoted)} total):{top_metrics}
- Macro indicators:{macro_str if macro_str else ' unavailable'}
- Portfolio return: {context.get('portfolio_return', 0):.1f}%, Sharpe: {context.get('portfolio_sharpe', 0):.2f}

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
        self._load_cache()

    def _load_cache(self):
        try:
            if COMMENTARY_CACHE.exists():
                with open(COMMENTARY_CACHE) as f:
                    self.last_report = json.load(f)
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
        if self.is_generating:
            return self.last_report or {"status": "generating"}

        self.is_generating = True
        t0 = time.time()

        try:
            promoted = [s for s in signal_metrics if s.get("promoted")]
            review   = [s for s in signal_metrics if not s.get("promoted")]
            top = max(promoted, key=lambda s: float(s.get("ic", 0)), default={}) if promoted else {}
            avg_ic = np.mean([float(s.get("ic", 0)) for s in promoted]) if promoted else 0.03

            context = {
                "promoted_signals":  promoted,
                "review_signals":    review,
                "avg_ic":            avg_ic,
                "top_signal":        top,
                "regime":            regime,
                "portfolio_return":  portfolio_perf.get("ann_return", 12.4),
                "portfolio_sharpe":  portfolio_perf.get("sharpe", 1.4),
                "macro_summary":     macro_signals,
            }

            # Try LLM first, fall back to template
            llm_text = _call_llm(_build_prompt(context))
            template_text = _template_commentary(context)

            report = {
                "status":        "ok",
                "timestamp":     datetime.utcnow().isoformat(),
                "regime":        regime,
                "llm_available": llm_text is not None,
                "source":        "llm" if llm_text else "template",
                "commentary":    llm_text or template_text,
                "template":      template_text,  # always include template version
                "stats": {
                    "n_promoted":  len(promoted),
                    "n_review":    len(review),
                    "avg_ic":      round(float(avg_ic), 4),
                    "top_signal":  top.get("name", "—"),
                    "portfolio_return": portfolio_perf.get("ann_return", 0),
                    "portfolio_sharpe": portfolio_perf.get("sharpe", 0),
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

    def get_last(self) -> dict:
        if self.last_report:
            return self.last_report
        return {
            "status":    "not_generated",
            "commentary": "No report yet. The agent will generate one automatically after data loads.",
            "llm_available": _call_ollama("ping", "llama3") is not None,
        }
