"""
Vision Agent — Chart pattern analysis via multimodal LLM.

Model: meta/llama-3.2-90b-vision-instruct
  - 90B multimodal model — reads price chart images directly
  - Returns: pattern label, trend, support/resistance, conviction score

Workflow:
  1. Generate a simple ASCII/text price chart from OHLCV data (no image file needed)
     OR encode a matplotlib chart as base64 PNG
  2. Send to llama-90b-vision with chart image
  3. Get structured pattern analysis back

Patterns detected:
  - Trend: uptrend, downtrend, sideways
  - Patterns: breakout, head-and-shoulders, double-top, cup-and-handle, etc.
  - Support/resistance levels
  - Volume confirmation
  - Overall conviction: 0–1
"""
import os, logging, time, json, base64, io
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path

log = logging.getLogger(__name__)

NVIDIA_API_KEY  = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
VISION_MODEL    = os.getenv("NVIDIA_MODEL_VISION", "meta/llama-3.2-90b-vision-instruct")
FAST_MODEL      = os.getenv("NVIDIA_MODEL_FAST",   "meta/llama-3.3-70b-instruct")

CACHE_FILE = Path("/tmp/alpha_foundry_cache/vision.json")
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


# ── Chart Generator ───────────────────────────────────────────────────────────

def _generate_chart_b64(ticker: str, prices: list, volumes: list = None) -> Optional[str]:
    """
    Generate a matplotlib price chart and encode as base64 PNG.
    Returns base64 string or None if matplotlib unavailable.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # non-interactive backend
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        import numpy as np

        fig, axes = plt.subplots(2, 1, figsize=(10, 6),
                                  gridspec_kw={"height_ratios": [3, 1]})
        ax1, ax2 = axes

        # Price chart
        x = list(range(len(prices)))
        ax1.plot(x, prices, color="#00d4ff", linewidth=1.5)
        ax1.fill_between(x, prices, min(prices), alpha=0.1, color="#00d4ff")

        # 20-day and 50-day MAs
        if len(prices) >= 20:
            ma20 = [sum(prices[max(0, i-19):i+1]) / min(i+1, 20) for i in range(len(prices))]
            ax1.plot(x, ma20, color="#ff9900", linewidth=1, linestyle="--", label="MA20")
        if len(prices) >= 50:
            ma50 = [sum(prices[max(0, i-49):i+1]) / min(i+1, 50) for i in range(len(prices))]
            ax1.plot(x, ma50, color="#ff4444", linewidth=1, linestyle="--", label="MA50")

        ax1.set_title(f"{ticker} — Price Chart (last {len(prices)} days)", color="white", fontsize=11)
        ax1.set_facecolor("#0a0a0a")
        ax1.tick_params(colors="gray")
        ax1.legend(loc="upper left", fontsize=8)

        # Volume
        if volumes and len(volumes) == len(prices):
            colors = ["#00d4ff" if i == 0 or prices[i] >= prices[i-1]
                      else "#ff4444" for i in range(len(prices))]
            ax2.bar(x, volumes, color=colors, alpha=0.7)
        ax2.set_facecolor("#0a0a0a")
        ax2.tick_params(colors="gray")
        ax2.set_ylabel("Volume", color="gray", fontsize=8)

        fig.patch.set_facecolor("#0a0a0a")
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=100, bbox_inches="tight",
                    facecolor="#0a0a0a")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")
    except Exception as e:
        log.warning(f"Chart generation failed: {e}")
        return None


def _text_chart(ticker: str, prices: list) -> str:
    """ASCII sparkline fallback when matplotlib unavailable."""
    if not prices:
        return f"{ticker}: no price data"
    mn, mx = min(prices), max(prices)
    height = 8
    width  = min(len(prices), 60)
    step   = max(1, len(prices) // width)
    sampled = prices[::step][-width:]

    rows = []
    for row in range(height, 0, -1):
        threshold = mn + (mx - mn) * row / height
        line = ""
        for p in sampled:
            line += "█" if p >= threshold else " "
        rows.append(f"{threshold:8.1f} │{line}")
    rows.append(f"{'':8} └{'─' * width}")

    trend = "↑ UP" if prices[-1] > prices[0] else "↓ DOWN"
    change = (prices[-1] / prices[0] - 1) * 100
    header = f"{ticker} — {trend} {change:+.1f}% over {len(prices)} days"
    return header + "\n" + "\n".join(rows)


# ── Vision API Call ───────────────────────────────────────────────────────────

def _call_vision_llm(ticker: str, chart_b64: Optional[str],
                      chart_text: str, prices: list) -> Optional[dict]:
    """Call llama-3.2-90b-vision with chart data. Returns structured analysis."""
    if not NVIDIA_API_KEY:
        return None

    prompt_text = (
        f"Analyze this price chart for {ticker}. Provide:\n"
        f"1. TREND: (uptrend/downtrend/sideways)\n"
        f"2. PATTERN: identify any chart pattern (breakout, consolidation, "
        f"head-and-shoulders, double top/bottom, cup-and-handle, etc.)\n"
        f"3. SUPPORT: key support level (price)\n"
        f"4. RESISTANCE: key resistance level (price)\n"
        f"5. SIGNAL: BUY / SELL / HOLD\n"
        f"6. CONVICTION: 0.0-1.0\n"
        f"7. REASONING: one sentence\n\n"
        f"Format as JSON with keys: trend, pattern, support, resistance, "
        f"signal, conviction, reasoning"
    )

    # Build message content — use image if available, otherwise text chart
    if chart_b64:
        content = [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{chart_b64}"}},
            {"type": "text", "text": prompt_text},
        ]
    else:
        content = [{"type": "text", "text": f"ASCII Chart:\n{chart_text}\n\n{prompt_text}"}]

    models_to_try = [VISION_MODEL] if chart_b64 else [FAST_MODEL]
    if FAST_MODEL not in models_to_try:
        models_to_try.append(FAST_MODEL)

    for model in models_to_try:
        try:
            import requests
            resp = requests.post(
                f"{NVIDIA_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {NVIDIA_API_KEY}",
                         "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": content}],
                    "max_tokens": 300,
                    "temperature": 0.2,
                    "stream": False,
                },
                timeout=45,
            )
            if resp.ok:
                text = resp.json()["choices"][0]["message"]["content"].strip()
                # Parse JSON from response
                import re
                json_match = re.search(r"\{.*\}", text, re.DOTALL)
                if json_match:
                    try:
                        return {**json.loads(json_match.group()), "model": model}
                    except json.JSONDecodeError:
                        pass
                # Fallback: return raw text
                return {"raw": text, "model": model}
        except Exception as e:
            log.warning(f"Vision LLM {model}: {e}")
    return None


# ── Vision Agent ──────────────────────────────────────────────────────────────

class VisionAgent:
    """
    Chart pattern analysis using multimodal LLM.
    Generates charts from price data → sends to llama-90b-vision → structured analysis.
    """

    def __init__(self):
        self.last_report: Optional[dict] = None
        self.analyses: Dict[str, dict] = {}
        self._load_cache()

    def _load_cache(self):
        try:
            if CACHE_FILE.exists():
                age = time.time() - CACHE_FILE.stat().st_mtime
                if age < 3600:
                    with open(CACHE_FILE) as f:
                        cached = json.load(f)
                    self.analyses = cached.get("analyses", {})
        except Exception:
            pass

    def _save_cache(self):
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump({"timestamp": datetime.utcnow().isoformat(),
                           "analyses": self.analyses}, f, default=str)
        except Exception:
            pass

    def analyze_ticker(self, ticker: str, prices: list,
                        volumes: list = None) -> dict:
        """Analyze a single ticker's chart. Returns structured pattern analysis."""
        t0 = time.time()

        chart_b64  = _generate_chart_b64(ticker, prices, volumes)
        chart_text = _text_chart(ticker, prices)
        vision     = _call_vision_llm(ticker, chart_b64, chart_text, prices)

        result = {
            "ticker":      ticker,
            "timestamp":   datetime.utcnow().isoformat(),
            "price_last":  prices[-1] if prices else None,
            "price_change_pct": round((prices[-1] / prices[0] - 1) * 100, 2) if len(prices) > 1 else 0,
            "chart_generated": chart_b64 is not None,
            "analysis":    vision or {"trend": "unknown", "signal": "HOLD", "conviction": 0.5},
            "elapsed_s":   round(time.time() - t0, 2),
        }
        self.analyses[ticker] = result
        self._save_cache()
        return result

    def analyze_portfolio(self, tickers: List[str],
                           price_data: Dict[str, list]) -> dict:
        """Analyze all tickers in portfolio. Returns batch report."""
        t0 = time.time()
        results = {}
        for ticker in tickers:
            if ticker in price_data:
                results[ticker] = self.analyze_ticker(ticker, price_data[ticker])

        # Aggregate signals
        buys   = [t for t, r in results.items() if r.get("analysis", {}).get("signal") == "BUY"]
        sells  = [t for t, r in results.items() if r.get("analysis", {}).get("signal") == "SELL"]
        holds  = [t for t, r in results.items() if r.get("analysis", {}).get("signal") == "HOLD"]

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "elapsed_s": round(time.time() - t0, 2),
            "n_analyzed": len(results),
            "buy_signals":  buys,
            "sell_signals": sells,
            "hold_signals": holds,
            "analyses":    results,
        }
        self.last_report = report
        return report

    def get_signal(self, ticker: str) -> Optional[str]:
        """Quick lookup: BUY/SELL/HOLD for a ticker from last analysis."""
        a = self.analyses.get(ticker, {})
        return a.get("analysis", {}).get("signal")

    def get_conviction(self, ticker: str) -> float:
        """Get conviction score 0–1 for ticker from last analysis."""
        a = self.analyses.get(ticker, {})
        return float(a.get("analysis", {}).get("conviction", 0.5))
