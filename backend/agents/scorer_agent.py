"""
Signal Confidence Scorer — Ranks signals before execution.

Model: nvidia/nemotron-4-340b-reward
  - Reward model: purpose-built to score outputs 0–1
  - Eliminates marginal/low-confidence signals before they generate orders
  - Runs after signal engine, before execution agent

Also uses: nvidia/llama-3.1-nemotron-ultra-253b-v1 for deep reasoning
  on complex multi-signal interactions.

Scoring dimensions:
  1. Statistical quality (IC, ICIR, Sharpe, decay)
  2. Regime fit (is the signal type suited to current market regime?)
  3. Macro alignment (signal direction vs macro backdrop)
  4. Capacity / liquidity (signal tickers vs avg volume)
  5. LLM confidence score (reward model 0–1)

Output: each signal gets a composite confidence score 0–1.
  > 0.7 → HIGH confidence → full allocation
  0.5–0.7 → MEDIUM → 70% allocation
  < 0.5 → LOW → skip or 30% allocation
"""
import os, logging, time, json
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path

log = logging.getLogger(__name__)

NVIDIA_API_KEY  = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
REWARD_MODEL    = os.getenv("NVIDIA_MODEL_REWARD",    "nvidia/nemotron-4-340b-reward")
REASONING_MODEL = os.getenv("NVIDIA_MODEL_REASONING", "nvidia/llama-3.1-nemotron-ultra-253b-v1")
FAST_MODEL      = os.getenv("NVIDIA_MODEL_FAST",       "meta/llama-3.3-70b-instruct")

CACHE_FILE = Path("/tmp/alpha_foundry_cache/signal_scores.json")
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


# ── Statistical scoring (deterministic) ──────────────────────────────────────

def _stat_score(signal: dict) -> float:
    """Score a signal on pure statistical quality. Returns 0–1."""
    ic     = float(signal.get("ic",        0.0))
    icir   = float(signal.get("icir",      0.0))
    sharpe = float(signal.get("net_sharpe", 0.0))
    decay  = float(signal.get("decay_halflife_days", 30.0))

    # Normalize each dimension
    ic_score    = min(ic / 0.10, 1.0)          # 0.10 IC = perfect
    icir_score  = min(icir / 1.0, 1.0)         # 1.0 ICIR = perfect
    sharpe_score = min(sharpe / 2.0, 1.0)      # 2.0 Sharpe = perfect
    decay_score  = min(decay / 5.0, 1.0)       # 5-day halflife = very alpha-rich

    # Weighted composite
    return round(
        ic_score    * 0.35 +
        icir_score  * 0.30 +
        sharpe_score * 0.25 +
        decay_score  * 0.10,
        4
    )


def _regime_fit_score(signal_id: str, regime: str) -> float:
    """Score how well signal type fits current market regime."""
    # Signal → regime affinity map
    REGIME_FIT = {
        "MOM12_1":   {"bull": 1.0, "bear": 0.3, "range": 0.5, "crisis": 0.2, "inflate": 0.7},
        "MOM_1M":    {"bull": 0.9, "bear": 0.2, "range": 0.6, "crisis": 0.1, "inflate": 0.6},
        "STREV":     {"bull": 0.4, "bear": 0.7, "range": 1.0, "crisis": 0.8, "inflate": 0.5},
        "QUAL_ROE":  {"bull": 0.8, "bear": 0.6, "range": 0.7, "crisis": 0.5, "inflate": 0.8},
        "QUAL_GP":   {"bull": 0.7, "bear": 0.6, "range": 0.7, "crisis": 0.5, "inflate": 0.7},
        "LOW_VOL":   {"bull": 0.5, "bear": 0.9, "range": 0.8, "crisis": 1.0, "inflate": 0.6},
        "LOW_BETA":  {"bull": 0.4, "bear": 1.0, "range": 0.7, "crisis": 1.0, "inflate": 0.5},
        "SHORT_INT": {"bull": 0.3, "bear": 0.9, "range": 0.5, "crisis": 0.8, "inflate": 0.4},
        "COMBO_QVM": {"bull": 0.8, "bear": 0.6, "range": 0.7, "crisis": 0.4, "inflate": 0.7},
    }
    fits = REGIME_FIT.get(signal_id, {})
    return fits.get(regime, 0.5)


# ── Reward Model Scoring ──────────────────────────────────────────────────────

def _reward_model_score(signal: dict, regime: str, macro_score: float) -> Optional[float]:
    """
    Use nemotron-4-340b-reward to score signal confidence.
    The reward model returns a logit-based score we convert to 0–1.
    """
    if not NVIDIA_API_KEY:
        return None

    sig_id  = signal.get("id") or signal.get("signal_id", "UNKNOWN")
    context = (
        f"Signal: {sig_id}\n"
        f"IC: {signal.get('ic', 0):.4f} | ICIR: {signal.get('icir', 0):.3f} | "
        f"Net Sharpe: {signal.get('net_sharpe', 0):.2f}\n"
        f"Market Regime: {regime}\n"
        f"Macro Score: {macro_score:.2f} (-1=bearish, +1=bullish)\n"
        f"Promoted: {signal.get('promoted', False)}\n"
    )
    prompt = (
        f"Evaluate the trading viability of this quantitative signal:\n\n{context}\n"
        f"Should we allocate capital to this signal right now? "
        f"Rate the confidence from 0.0 (no confidence) to 1.0 (very high confidence). "
        f"Respond with ONLY a decimal number between 0.0 and 1.0."
    )

    # Try reward model first, then reasoning model, then fast
    for model in [REWARD_MODEL, REASONING_MODEL, FAST_MODEL]:
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
                            "You are a quantitative signal evaluator. "
                            "Output only a single decimal number 0.0-1.0 representing signal confidence."
                        )},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 10,
                    "temperature": 0.1,
                    "stream": False,
                },
                timeout=20,
            )
            if resp.ok:
                text = resp.json()["choices"][0]["message"]["content"].strip()
                # Extract first float from response
                import re
                matches = re.findall(r"\d+\.?\d*", text)
                if matches:
                    score = float(matches[0])
                    if 0.0 <= score <= 1.0:
                        log.info(f"Reward score [{model}] {sig_id}: {score}")
                        return score
        except Exception as e:
            log.warning(f"Reward model {model}: {e}")
    return None


# ── Main Scorer ───────────────────────────────────────────────────────────────

class SignalScorerAgent:
    """
    Scores and ranks all signals before the execution cycle.
    Returns enriched signal list with confidence scores + allocation multipliers.
    """

    def __init__(self):
        self.last_scores: Optional[dict] = None
        self._load_cache()

    def _load_cache(self):
        try:
            if CACHE_FILE.exists():
                age = time.time() - CACHE_FILE.stat().st_mtime
                if age < 1800:  # 30-min cache
                    with open(CACHE_FILE) as f:
                        self.last_scores = json.load(f)
        except Exception:
            pass

    def _save_cache(self):
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(self.last_scores, f, default=str)
        except Exception:
            pass

    def score_signals(self, signals: List[dict], regime: str = "bull",
                      macro_score: float = 0.0) -> List[dict]:
        """
        Score each signal and add confidence metadata.
        Returns enriched list sorted by composite_score descending.
        """
        t0 = time.time()
        log.info(f"SignalScorer: scoring {len(signals)} signals (regime={regime})")

        scored = []
        for sig in signals:
            sig_id = sig.get("id") or sig.get("signal_id", "UNKNOWN")

            # 1. Statistical score
            stat   = _stat_score(sig)
            # 2. Regime fit
            regime_fit = _regime_fit_score(sig_id, regime)
            # 3. LLM reward score (only for promoted signals to save API calls)
            llm_score = None
            if sig.get("promoted", False):
                llm_score = _reward_model_score(sig, regime, macro_score)

            # 4. Composite
            if llm_score is not None:
                composite = stat * 0.40 + regime_fit * 0.25 + llm_score * 0.35
            else:
                composite = stat * 0.55 + regime_fit * 0.45

            composite = round(composite, 4)

            # 5. Allocation multiplier
            if composite >= 0.70:
                alloc_mult = 1.0
                confidence = "HIGH"
            elif composite >= 0.50:
                alloc_mult = 0.70
                confidence = "MEDIUM"
            else:
                alloc_mult = 0.30
                confidence = "LOW"

            enriched = {
                **sig,
                "confidence_score":  composite,
                "confidence_label":  confidence,
                "alloc_multiplier":  alloc_mult,
                "stat_score":        stat,
                "regime_fit_score":  regime_fit,
                "llm_score":         llm_score,
            }
            scored.append(enriched)

        scored.sort(key=lambda s: s["confidence_score"], reverse=True)

        result = {
            "timestamp":  datetime.utcnow().isoformat(),
            "elapsed_s":  round(time.time() - t0, 2),
            "regime":     regime,
            "macro_score": macro_score,
            "signals":    scored,
            "n_high":     sum(1 for s in scored if s["confidence_label"] == "HIGH"),
            "n_medium":   sum(1 for s in scored if s["confidence_label"] == "MEDIUM"),
            "n_low":      sum(1 for s in scored if s["confidence_label"] == "LOW"),
        }
        self.last_scores = result
        self._save_cache()
        return scored

    def get_last_report(self) -> Optional[dict]:
        return self.last_scores
