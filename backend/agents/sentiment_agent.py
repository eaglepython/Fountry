"""
Sentiment Agent — Real-time news & social sentiment analysis.

Models:
  PRIMARY  : mistralai/mistral-large-3-675b-instruct-2512 (675B, unstructured text)
  LOCAL    : FinBERT (HuggingFace transformers, runs in venv, zero API cost)
  FALLBACK : meta/llama-3.3-70b-instruct

Workflow:
  1. Fetch headlines from Yahoo Finance RSS / yfinance news
  2. Score with FinBERT locally (0.2–0.3s per batch)
  3. Summarize top movers with mistral-675b for deeper narrative
  4. Return aggregate sentiment score per ticker + market-level score
"""
import os, logging, time, json
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path

log = logging.getLogger(__name__)

NVIDIA_API_KEY  = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")

SENTIMENT_MODEL    = os.getenv("NVIDIA_MODEL_SENTIMENT", "mistralai/mistral-large-3-675b-instruct-2512")
SENTIMENT_FAST     = os.getenv("NVIDIA_MODEL_FAST",      "meta/llama-3.3-70b-instruct")

CACHE_FILE = Path("/tmp/alpha_foundry_cache/sentiment.json")
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


# ── FinBERT (local, free) ─────────────────────────────────────────────────────

_finbert_pipeline = None

def _load_finbert():
    """Lazy-load FinBERT only when first called. Requires transformers package."""
    global _finbert_pipeline
    if _finbert_pipeline is not None:
        return _finbert_pipeline
    try:
        from transformers import pipeline
        _finbert_pipeline = pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            truncation=True,
            max_length=512,
            device=-1,  # CPU
        )
        log.info("FinBERT loaded (local, CPU)")
    except Exception as e:
        log.warning(f"FinBERT unavailable (pip install transformers): {e}")
        _finbert_pipeline = None
    return _finbert_pipeline


def _finbert_score(texts: List[str]) -> List[dict]:
    """Score a list of headlines with FinBERT. Returns list of {label, score}."""
    pipe = _load_finbert()
    if pipe is None:
        return []
    try:
        results = pipe(texts, batch_size=16, truncation=True)
        # Normalize: positive=1, neutral=0, negative=-1
        label_map = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}
        scored = []
        for text, r in zip(texts, results):
            polarity = label_map.get(r["label"].lower(), 0.0) * r["score"]
            scored.append({"text": text[:120], "label": r["label"], "score": polarity, "confidence": r["score"]})
        return scored
    except Exception as e:
        log.warning(f"FinBERT scoring error: {e}")
        return []


# ── NVIDIA NIM Narrative ──────────────────────────────────────────────────────

def _nvidia_sentiment_narrative(headlines: List[str], tickers: List[str]) -> Optional[str]:
    """Use mistral-675b to generate a narrative sentiment summary."""
    if not NVIDIA_API_KEY or not headlines:
        return None
    prompt = (
        f"Analyze the market sentiment from these recent financial headlines. "
        f"Focus on implications for: {', '.join(tickers[:10])}.\n\n"
        f"Headlines:\n" + "\n".join(f"- {h}" for h in headlines[:30]) +
        "\n\nProvide: (1) Overall market sentiment (bullish/bearish/mixed), "
        "(2) Key risks, (3) Key tailwinds, (4) Top 3 tickers most affected and why. "
        "Be concise — 3 paragraphs max."
    )
    try:
        import requests
        resp = requests.post(
            f"{NVIDIA_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": SENTIMENT_MODEL,
                "messages": [
                    {"role": "system", "content": (
                        "You are a senior market analyst specializing in sentiment analysis. "
                        "Be precise, data-driven, and focus on actionable insights."
                    )},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 512,
                "temperature": 0.3,
                "stream": False,
            },
            timeout=45,
        )
        if resp.ok:
            return resp.json()["choices"][0]["message"]["content"].strip()
        # Fallback to fast model
        resp2 = requests.post(
            f"{NVIDIA_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": SENTIMENT_FAST,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 400, "temperature": 0.3, "stream": False,
            },
            timeout=30,
        )
        if resp2.ok:
            return resp2.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.warning(f"NVIDIA sentiment narrative failed: {e}")
    return None


# ── News Fetcher ──────────────────────────────────────────────────────────────

def _fetch_yfinance_news(tickers: List[str]) -> List[dict]:
    """Fetch recent news headlines via yfinance."""
    headlines = []
    try:
        import yfinance as yf
        for ticker in tickers[:15]:
            try:
                t = yf.Ticker(ticker)
                news = t.news or []
                for item in news[:5]:
                    title = item.get("content", {}).get("title") or item.get("title", "")
                    if title:
                        headlines.append({"ticker": ticker, "text": title,
                                          "ts": item.get("content", {}).get("pubDate", "")})
            except Exception:
                pass
    except Exception as e:
        log.warning(f"yfinance news fetch failed: {e}")
    return headlines


# ── Main Sentiment Agent ──────────────────────────────────────────────────────

class SentimentAgent:
    """
    Aggregates real-time news sentiment per ticker and at market level.
    Uses FinBERT locally for speed + mistral-675b for narrative depth.
    """

    def __init__(self):
        self.last_report: Optional[dict] = None
        self._load_cache()

    def _load_cache(self):
        try:
            if CACHE_FILE.exists():
                age = time.time() - CACHE_FILE.stat().st_mtime
                if age < 3600:  # 1-hour cache
                    with open(CACHE_FILE) as f:
                        self.last_report = json.load(f)
                    log.info("Sentiment: loaded from cache")
        except Exception:
            pass

    def _save_cache(self):
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(self.last_report, f, default=str)
        except Exception:
            pass

    def generate(self, tickers: List[str]) -> dict:
        """Run full sentiment pipeline. Returns structured sentiment report."""
        t0 = time.time()
        log.info(f"SentimentAgent: analyzing {len(tickers)} tickers…")

        # 1. Fetch headlines
        raw_news = _fetch_yfinance_news(tickers)
        texts = [n["text"] for n in raw_news]

        # 2. FinBERT local scoring
        finbert_scores = _finbert_score(texts)
        finbert_available = len(finbert_scores) > 0

        # 3. Aggregate per ticker
        ticker_sentiment: Dict[str, dict] = {}
        if finbert_scores:
            from collections import defaultdict
            ticker_scores = defaultdict(list)
            for news_item, fb in zip(raw_news, finbert_scores):
                ticker_scores[news_item["ticker"]].append(fb["score"])
            for ticker, scores in ticker_scores.items():
                avg = sum(scores) / len(scores)
                ticker_sentiment[ticker] = {
                    "score":     round(avg, 4),
                    "label":     "bullish" if avg > 0.1 else ("bearish" if avg < -0.1 else "neutral"),
                    "n_articles": len(scores),
                }

        # 4. Market-level aggregate
        all_scores = [fb["score"] for fb in finbert_scores]
        market_score = round(sum(all_scores) / len(all_scores), 4) if all_scores else 0.0
        market_label = "bullish" if market_score > 0.05 else ("bearish" if market_score < -0.05 else "neutral")

        # 5. NVIDIA narrative (async-style: call after local scoring)
        narrative = _nvidia_sentiment_narrative(texts, tickers)

        report = {
            "timestamp":        datetime.utcnow().isoformat(),
            "elapsed_s":        round(time.time() - t0, 2),
            "market_sentiment": {"score": market_score, "label": market_label},
            "ticker_sentiment": ticker_sentiment,
            "n_headlines":      len(texts),
            "finbert_available": finbert_available,
            "narrative":        narrative or "NVIDIA narrative unavailable.",
            "model":            SENTIMENT_MODEL,
            "top_headlines":    [fb["text"] for fb in finbert_scores[:10]],
        }
        self.last_report = report
        self._save_cache()
        return report

    def get_signal_weights(self, tickers: List[str]) -> Dict[str, float]:
        """
        Returns a sentiment adjustment multiplier per ticker.
        bullish → 1.2, neutral → 1.0, bearish → 0.7
        Used by ExecutionAgent to scale position sizes.
        """
        if not self.last_report:
            return {t: 1.0 for t in tickers}
        sent = self.last_report.get("ticker_sentiment", {})
        weight_map = {"bullish": 1.2, "neutral": 1.0, "bearish": 0.7}
        return {
            t: weight_map.get(sent.get(t, {}).get("label", "neutral"), 1.0)
            for t in tickers
        }
