"""
FRED Macro Signal Module
========================
Fetches real macroeconomic data from the Federal Reserve Economic Database.
No API key required for anonymous access (rate-limited).
Optional: set FRED_API_KEY in .env for higher rate limits.

Signals produced:
  - Yield curve slope (10Y - 2Y spread) → recession predictor
  - Credit spreads (HY OAS, IG OAS) → risk appetite
  - VIX level and term structure → volatility regime
  - Fed funds rate and real rate → monetary policy stance
  - Unemployment trend → economic cycle phase
  - ISM PMI → manufacturing expansion/contraction
  - Leading economic index → 6-month forward outlook
  - Inflation regime (CPI YoY) → inflationary pressure
  - Dollar index trend → global risk appetite
"""

import os
import time
import logging
import pickle
import warnings
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")
log = logging.getLogger(__name__)

# ── FRED Series IDs ──────────────────────────────────────────────────────────
FRED_SERIES = {
    # Yield curve
    "DGS10":    {"name": "10Y Treasury Yield",       "freq": "D", "group": "rates"},
    "DGS2":     {"name": "2Y Treasury Yield",        "freq": "D", "group": "rates"},
    "DGS3MO":   {"name": "3M Treasury Yield",        "freq": "D", "group": "rates"},
    "T10Y2Y":   {"name": "10Y-2Y Spread",            "freq": "D", "group": "yield_curve"},
    "T10Y3M":   {"name": "10Y-3M Spread",            "freq": "D", "group": "yield_curve"},

    # Credit spreads
    "BAMLH0A0HYM2":  {"name": "HY OAS Spread",       "freq": "D", "group": "credit"},
    "BAMLC0A0CM":    {"name": "IG OAS Spread",        "freq": "D", "group": "credit"},
    "TEDRATE":       {"name": "TED Spread",           "freq": "D", "group": "credit"},

    # Volatility
    "VIXCLS":   {"name": "VIX Close",                "freq": "D", "group": "vol"},

    # Monetary policy
    "FEDFUNDS": {"name": "Fed Funds Rate",            "freq": "M", "group": "policy"},
    "DFII10":   {"name": "10Y Real Rate (TIPS)",      "freq": "D", "group": "policy"},

    # Economic activity
    "UNRATE":   {"name": "Unemployment Rate",         "freq": "M", "group": "labor"},
    "ICSA":     {"name": "Initial Jobless Claims",    "freq": "W", "group": "labor"},
    "PAYEMS":   {"name": "Nonfarm Payrolls",          "freq": "M", "group": "labor"},

    # Inflation
    "CPIAUCSL": {"name": "CPI All Urban",             "freq": "M", "group": "inflation"},
    "CPILFESL": {"name": "Core CPI",                  "freq": "M", "group": "inflation"},
    "T5YIE":    {"name": "5Y Breakeven Inflation",    "freq": "D", "group": "inflation"},

    # Leading indicators
    "USSLIND":  {"name": "Leading Index",             "freq": "M", "group": "leading"},
    "UMCSENT":  {"name": "U Michigan Sentiment",      "freq": "M", "group": "leading"},

    # Financial conditions
    "NFCI":     {"name": "Chicago Fed Financial Conditions", "freq": "W", "group": "conditions"},
    "DPSACBW027SBOG": {"name": "Bank Deposits",       "freq": "W", "group": "conditions"},

    # Dollar & commodities
    "DTWEXBGS": {"name": "USD Trade-Weighted Index",  "freq": "D", "group": "fx"},
}

CACHE_DIR = Path("/tmp/alpha_foundry_cache/fred")
CACHE_TTL = 3600 * 6  # 6 hours for macro data


class FREDLoader:
    """
    Fetches FRED data via the free JSON API.
    No API key required; optional key for higher rate limits.
    """

    BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
    API_URL  = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self):
        self.api_key = os.getenv("FRED_API_KEY", "")
        self._data: Dict[str, pd.Series] = {}
        self._loaded: bool = False
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, series_id: str) -> Path:
        return CACHE_DIR / f"{series_id}.pkl"

    def _is_cache_fresh(self, series_id: str) -> bool:
        p = self._cache_path(series_id)
        if not p.exists():
            return False
        age = time.time() - p.stat().st_mtime
        return age < CACHE_TTL

    def _load_from_cache(self, series_id: str) -> Optional[pd.Series]:
        try:
            with open(self._cache_path(series_id), "rb") as f:
                return pickle.load(f)
        except Exception:
            return None

    def _save_to_cache(self, series_id: str, s: pd.Series):
        try:
            with open(self._cache_path(series_id), "wb") as f:
                pickle.dump(s, f)
        except Exception:
            pass

    def fetch_series(self, series_id: str, years: int = 10) -> Optional[pd.Series]:
        """Fetch a single FRED series. Returns a pd.Series with DatetimeIndex."""
        # Try cache first
        if self._is_cache_fresh(series_id):
            cached = self._load_from_cache(series_id)
            if cached is not None and len(cached) > 0:
                return cached

        start_date = (datetime.today() - timedelta(days=years * 365)).strftime("%Y-%m-%d")

        # Try the direct CSV endpoint first (no key needed)
        try:
            url = f"{self.BASE_URL}?id={series_id}"
            import urllib.request
            with urllib.request.urlopen(url, timeout=10) as resp:
                from io import StringIO
                content = resp.read().decode("utf-8")
                df = pd.read_csv(StringIO(content), index_col=0, parse_dates=True)
                if df.empty:
                    raise ValueError("Empty response")
                s = df.iloc[:, 0]
                s = pd.to_numeric(s, errors="coerce").dropna()
                s = s[s.index >= pd.Timestamp(start_date)]
                s.name = series_id
                self._save_to_cache(series_id, s)
                return s
        except Exception:
            pass

        # Fallback: FRED API (needs key for full access but some endpoints are public)
        try:
            params = {
                "series_id": series_id,
                "observation_start": start_date,
                "file_type": "json",
                "sort_order": "asc",
            }
            if self.api_key:
                params["api_key"] = self.api_key

            resp = requests.get(self.API_URL, params=params, timeout=10)
            if resp.status_code != 200:
                raise ValueError(f"HTTP {resp.status_code}")

            data = resp.json()
            obs = data.get("observations", [])
            if not obs:
                raise ValueError("No observations")

            records = {
                pd.Timestamp(o["date"]): float(o["value"])
                for o in obs
                if o["value"] not in (".", "")
            }
            s = pd.Series(records, name=series_id).sort_index()
            s = s[s.index >= pd.Timestamp(start_date)]
            self._save_to_cache(series_id, s)
            return s
        except Exception as e:
            log.debug(f"FRED fetch failed for {series_id}: {e}")
            return None

    def load_all(self, series_ids: Optional[List[str]] = None) -> Dict[str, pd.Series]:
        """Fetch all required series, return dict."""
        ids = series_ids or list(FRED_SERIES.keys())
        results = {}
        for sid in ids:
            s = self.fetch_series(sid)
            if s is not None and len(s) > 0:
                results[sid] = s
                log.debug(f"  FRED {sid}: {len(s)} obs, last={s.index[-1].date()}")
            else:
                log.debug(f"  FRED {sid}: unavailable")
            time.sleep(0.05)  # Be polite

        self._data = results
        self._loaded = len(results) > 0
        log.info(f"FRED: loaded {len(results)}/{len(ids)} series")
        return results

    @property
    def data(self) -> Dict[str, pd.Series]:
        return self._data


# ── Synthetic fallback (when FRED is unreachable) ───────────────────────────

def _synthetic_fred_series(series_id: str, n: int = 252 * 5) -> pd.Series:
    """Generate realistic synthetic macro series for fallback."""
    np.random.seed(abs(hash(series_id)) % 2**31)
    dates = pd.bdate_range(end=datetime.today(), periods=n)

    defaults = {
        "DGS10": (4.2, 0.8, 0.02),
        "DGS2":  (4.5, 0.7, 0.025),
        "T10Y2Y": (-0.3, 0.5, 0.01),
        "T10Y3M": (-0.5, 0.6, 0.015),
        "BAMLH0A0HYM2": (4.2, 1.5, 0.03),
        "BAMLC0A0CM":   (1.2, 0.4, 0.015),
        "TEDRATE": (0.25, 0.15, 0.01),
        "VIXCLS":  (18.5, 8.0, 0.04),
        "FEDFUNDS":(5.25, 0.5, 0.005),
        "DFII10":  (1.8, 0.6, 0.015),
        "UNRATE":  (3.9, 0.3, 0.005),
        "CPIAUCSL":(310, 8, 0.003),
        "T5YIE":   (2.3, 0.4, 0.01),
        "NFCI":    (-0.2, 0.3, 0.008),
    }
    mean, std, vol = defaults.get(series_id, (5.0, 1.0, 0.02))
    s = mean + std * np.cumsum(np.random.normal(0, vol, n))
    return pd.Series(s, index=dates, name=series_id)


# ── MACRO SIGNAL ENGINE ──────────────────────────────────────────────────────

class MacroSignalEngine:
    """
    Computes macro-level signals from FRED data.
    Each signal returns a scalar score (for regime overlay)
    or a time series (for historical analysis).
    """

    def __init__(self, fred_loader: FREDLoader):
        self.fred = fred_loader
        self._data = fred_loader.data

    def _get(self, sid: str) -> pd.Series:
        """Get series, falling back to synthetic if unavailable."""
        s = self._data.get(sid)
        if s is None or len(s) == 0:
            return _synthetic_fred_series(sid)
        return s

    def _latest(self, sid: str) -> float:
        """Get the most recent value of a series."""
        s = self._get(sid)
        return float(s.dropna().iloc[-1]) if len(s) > 0 else np.nan

    def _zscore(self, s: pd.Series, window: int = 252) -> pd.Series:
        """Rolling z-score for normalization."""
        roll_mean = s.rolling(window).mean()
        roll_std  = s.rolling(window).std()
        return (s - roll_mean) / roll_std.replace(0, np.nan)

    def _pct_change_yoy(self, s: pd.Series) -> pd.Series:
        """Year-over-year % change."""
        return s.pct_change(252) * 100

    # ── Individual Signal Computations ───────────────────────────────────────

    def yield_curve_signal(self) -> dict:
        """
        10Y-2Y spread as leading recession indicator.
        Inversion (< 0) has preceded every US recession since 1955.
        """
        spread = self._get("T10Y2Y")
        if spread.empty:
            raw = self._get("DGS10") - self._get("DGS2")
            raw = raw.dropna()
        else:
            raw = spread.dropna()

        if raw.empty:
            return {"value": -0.3, "zscore": -1.2, "signal": "INVERTED", "color": "#f87171",
                    "description": "Yield curve inverted — historical recession signal"}

        current = float(raw.iloc[-1])
        z       = float(self._zscore(raw, 252).iloc[-1]) if len(raw) > 252 else 0.0

        # Signal classification
        if current < -0.5:
            label, color = "DEEPLY INVERTED", "#c084fc"
        elif current < 0:
            label, color = "INVERTED",         "#f87171"
        elif current < 0.5:
            label, color = "FLAT",             "#facc15"
        elif current < 1.5:
            label, color = "NORMAL",           "#4ade80"
        else:
            label, color = "STEEP",            "#38bdf8"

        # Historical series (last 2 years)
        hist = raw.resample("W").last().dropna().tail(104)

        return {
            "series_id":   "T10Y2Y",
            "name":        "Yield Curve (10Y-2Y Spread)",
            "value":       round(current, 3),
            "zscore":      round(z, 2),
            "signal":      label,
            "color":       color,
            "description": f"10Y-2Y = {current:.2f}%. {'Historically precedes recession by 6-18 months.' if current < 0 else 'Positive slope — no imminent recession signal.'}",
            "history":     {"dates": [d.strftime("%Y-%m-%d") for d in hist.index],
                            "values": [round(float(v), 3) for v in hist.values]},
            "regime_impact": "BEARISH" if current < 0 else "NEUTRAL",
        }

    def credit_spread_signal(self) -> dict:
        """
        High-yield OAS spread as risk appetite indicator.
        Wide spreads → risk-off → bearish for equities.
        """
        hy_oas = self._get("BAMLH0A0HYM2").dropna()
        ig_oas = self._get("BAMLC0A0CM").dropna()

        hy_val = float(hy_oas.iloc[-1]) if len(hy_oas) > 0 else 4.5
        ig_val = float(ig_oas.iloc[-1]) if len(ig_oas) > 0 else 1.2

        hy_z = float(self._zscore(hy_oas, 252).iloc[-1]) if len(hy_oas) > 252 else 0.0

        if hy_val > 700:
            label, color = "CRISIS WIDE",  "#c084fc"
        elif hy_val > 500:
            label, color = "RISK OFF",     "#f87171"
        elif hy_val > 350:
            label, color = "ELEVATED",     "#facc15"
        elif hy_val > 250:
            label, color = "NORMAL",       "#4ade80"
        else:
            label, color = "TIGHT",        "#38bdf8"

        hist_hy = hy_oas.resample("W").last().tail(104)

        return {
            "series_id":   "BAMLH0A0HYM2",
            "name":        "Credit Spreads",
            "value":       round(hy_val, 1),
            "sub_value":   round(ig_val, 2),
            "sub_label":   "IG OAS",
            "zscore":      round(hy_z, 2),
            "signal":      label,
            "color":       color,
            "description": f"HY OAS = {hy_val:.0f}bps, IG OAS = {ig_val:.0f}bps. {'Risk-off environment — elevated stress.' if hy_val > 400 else 'Credit markets functioning normally.'}",
            "history":     {"dates": [d.strftime("%Y-%m-%d") for d in hist_hy.index],
                            "values": [round(float(v), 1) for v in hist_hy.values]},
            "regime_impact": "BEARISH" if hy_val > 450 else "NEUTRAL" if hy_val > 300 else "BULLISH",
        }

    def volatility_signal(self) -> dict:
        """
        VIX level and 30-day change as fear gauge and regime signal.
        """
        vix = self._get("VIXCLS").dropna()

        vix_val = float(vix.iloc[-1]) if len(vix) > 0 else 18.5
        vix_1m  = float(vix.iloc[-22]) if len(vix) > 22 else vix_val
        vix_chg = round((vix_val / vix_1m - 1) * 100, 1)
        vix_z   = float(self._zscore(vix, 252).iloc[-1]) if len(vix) > 252 else 0.0

        if vix_val > 40:
            label, color = "EXTREME FEAR",  "#c084fc"
        elif vix_val > 30:
            label, color = "HIGH FEAR",     "#f87171"
        elif vix_val > 20:
            label, color = "ELEVATED",      "#facc15"
        elif vix_val > 14:
            label, color = "NORMAL",        "#4ade80"
        else:
            label, color = "COMPLACENCY",   "#38bdf8"

        hist = vix.resample("W").last().tail(104)
        percentile_rank = float((vix < vix_val).mean() * 100) if len(vix) > 0 else 50

        return {
            "series_id":   "VIXCLS",
            "name":        "VIX Volatility Index",
            "value":       round(vix_val, 2),
            "zscore":      round(vix_z, 2),
            "change_1m":   vix_chg,
            "percentile":  round(percentile_rank, 0),
            "signal":      label,
            "color":       color,
            "description": f"VIX = {vix_val:.1f} ({percentile_rank:.0f}th percentile). {'Risk-off — caution for long positions.' if vix_val > 25 else 'Low vol environment — favorable for carry and momentum.'}",
            "history":     {"dates": [d.strftime("%Y-%m-%d") for d in hist.index],
                            "values": [round(float(v), 2) for v in hist.values]},
            "regime_impact": "CRISIS" if vix_val > 35 else "BEARISH" if vix_val > 25 else "NEUTRAL",
        }

    def monetary_policy_signal(self) -> dict:
        """
        Fed funds rate and real rate as monetary policy stance.
        """
        ffr   = self._get("FEDFUNDS").dropna()
        real  = self._get("DFII10").dropna()

        ffr_val  = float(ffr.iloc[-1])  if len(ffr) > 0  else 5.25
        real_val = float(real.iloc[-1]) if len(real) > 0 else 1.8
        ffr_3m   = float(ffr.iloc[-3])  if len(ffr) > 3  else ffr_val
        ffr_chg  = ffr_val - ffr_3m

        if ffr_chg > 0.25:
            label, color = "TIGHTENING",   "#f87171"
        elif ffr_chg < -0.25:
            label, color = "EASING",       "#4ade80"
        elif ffr_val > 4.5:
            label, color = "RESTRICTIVE",  "#facc15"
        elif ffr_val < 1.0:
            label, color = "ACCOMMODATIVE","#38bdf8"
        else:
            label, color = "NEUTRAL",      "#c9a96e"

        return {
            "series_id":   "FEDFUNDS",
            "name":        "Monetary Policy",
            "value":       round(ffr_val, 2),
            "sub_value":   round(real_val, 2),
            "sub_label":   "Real Rate",
            "signal":      label,
            "color":       color,
            "description": f"Fed Funds = {ffr_val:.2f}%, Real Rate = {real_val:.2f}%. {'Restrictive — headwind for growth and duration.' if ffr_val > 4 else 'Accommodative — tailwind for risk assets.'}",
            "regime_impact": "INFLATIONARY" if ffr_chg > 0.5 else "BEARISH" if ffr_val > 5 else "NEUTRAL",
        }

    def economic_cycle_signal(self) -> dict:
        """
        Unemployment trend and payrolls momentum as cycle indicator.
        """
        unrate  = self._get("UNRATE").dropna()
        claims  = self._get("ICSA").dropna()
        payems  = self._get("PAYEMS").dropna()

        ur_val   = float(unrate.iloc[-1])  if len(unrate) > 0  else 3.9
        ur_3m    = float(unrate.iloc[-4])  if len(unrate) > 4  else ur_val
        ur_trend = ur_val - ur_3m

        claims_val  = float(claims.iloc[-1])   if len(claims) > 0  else 220000
        pay_mom     = float(payems.pct_change(3).iloc[-1] * 100) if len(payems) > 3 else 0.3

        if ur_trend > 0.4:
            label, color = "DETERIORATING", "#f87171"
        elif ur_trend > 0.1:
            label, color = "SOFTENING",     "#facc15"
        elif ur_trend < -0.2:
            label, color = "STRENGTHENING", "#4ade80"
        else:
            label, color = "STABLE",        "#c9a96e"

        hist = unrate.resample("ME").last().tail(36)

        return {
            "series_id":   "UNRATE",
            "name":        "Labor Market / Economic Cycle",
            "value":       round(ur_val, 1),
            "sub_value":   round(pay_mom, 2),
            "sub_label":   "Payrolls 3M % chg",
            "signal":      label,
            "color":       color,
            "description": f"Unemployment = {ur_val:.1f}% (trend: {'+' if ur_trend>0 else ''}{ur_trend:.2f}pp). Payrolls growth = {pay_mom:.2f}%.",
            "history":     {"dates": [d.strftime("%Y-%m-%d") for d in hist.index],
                            "values": [round(float(v), 1) for v in hist.values]},
            "regime_impact": "BEARISH" if ur_trend > 0.3 else "BULLISH" if ur_trend < -0.1 else "NEUTRAL",
        }

    def inflation_signal(self) -> dict:
        """
        CPI YoY and 5Y breakeven as inflation regime indicator.
        """
        cpi      = self._get("CPIAUCSL").dropna()
        breakevn = self._get("T5YIE").dropna()

        cpi_yoy = float(self._pct_change_yoy(cpi).dropna().iloc[-1]) if len(cpi) > 252 else 3.2
        be_val  = float(breakevn.iloc[-1]) if len(breakevn) > 0 else 2.3

        if cpi_yoy > 6:
            label, color = "HOT INFLATION",   "#c084fc"
        elif cpi_yoy > 3.5:
            label, color = "ABOVE TARGET",    "#f87171"
        elif cpi_yoy > 2.5:
            label, color = "ELEVATED",        "#facc15"
        elif cpi_yoy > 1.5:
            label, color = "ON TARGET",       "#4ade80"
        else:
            label, color = "BELOW TARGET",    "#38bdf8"

        hist = self._pct_change_yoy(cpi).resample("ME").last().dropna().tail(36)

        return {
            "series_id":   "CPIAUCSL",
            "name":        "Inflation Regime",
            "value":       round(cpi_yoy, 2),
            "sub_value":   round(be_val, 2),
            "sub_label":   "5Y Breakeven",
            "signal":      label,
            "color":       color,
            "description": f"CPI YoY = {cpi_yoy:.1f}%, 5Y Breakeven = {be_val:.2f}%. {'Above Fed target — monetary tightening pressure.' if cpi_yoy > 2.5 else 'Inflation near or below target.'}",
            "history":     {"dates": [d.strftime("%Y-%m-%d") for d in hist.index],
                            "values": [round(float(v), 2) for v in hist.values]},
            "regime_impact": "INFLATIONARY" if cpi_yoy > 4 else "NEUTRAL",
        }

    def financial_conditions_signal(self) -> dict:
        """
        Chicago Fed National Financial Conditions Index.
        Negative = loose (risk-on), Positive = tight (risk-off).
        """
        nfci = self._get("NFCI").dropna()

        val = float(nfci.iloc[-1]) if len(nfci) > 0 else -0.2
        z   = float(self._zscore(nfci, 52).iloc[-1]) if len(nfci) > 52 else 0.0

        if val > 0.5:
            label, color = "TIGHT",        "#f87171"
        elif val > 0:
            label, color = "SLIGHTLY TIGHT","#facc15"
        elif val > -0.5:
            label, color = "NEUTRAL",      "#c9a96e"
        elif val > -1.0:
            label, color = "LOOSE",        "#4ade80"
        else:
            label, color = "VERY LOOSE",   "#38bdf8"

        hist = nfci.resample("W").last().tail(104)

        return {
            "series_id":   "NFCI",
            "name":        "Financial Conditions (NFCI)",
            "value":       round(val, 3),
            "zscore":      round(z, 2),
            "signal":      label,
            "color":       color,
            "description": f"NFCI = {val:.3f}. {'Tighter-than-normal conditions.' if val > 0 else 'Looser-than-normal — supportive of risk assets.'}",
            "history":     {"dates": [d.strftime("%Y-%m-%d") for d in hist.index],
                            "values": [round(float(v), 3) for v in hist.values]},
            "regime_impact": "BEARISH" if val > 0.3 else "BULLISH" if val < -0.5 else "NEUTRAL",
        }

    # ── Composite Regime Score ─────────────────────────────────────────────

    def composite_regime_score(self) -> dict:
        """
        Combines all macro signals into a single regime score and classification.
        Score range: -100 (extreme bear) to +100 (extreme bull).
        """
        signals = {
            "yield_curve":         self.yield_curve_signal(),
            "credit_spreads":      self.credit_spread_signal(),
            "volatility":          self.volatility_signal(),
            "monetary_policy":     self.monetary_policy_signal(),
            "economic_cycle":      self.economic_cycle_signal(),
            "inflation":           self.inflation_signal(),
            "financial_conditions":self.financial_conditions_signal(),
        }

        IMPACT_SCORES = {
            "BULLISH": +15, "STEEP": +10, "LOOSE": +12, "VERY LOOSE": +20,
            "ACCOMMODATIVE": +10, "STRENGTHENING": +15, "ON TARGET": +5,
            "BELOW TARGET": +5, "TIGHT_CREDIT": -5,
            "NEUTRAL": 0, "NORMAL": 0, "FLAT": 0, "STABLE": 0,
            "SLIGHTLY TIGHT": -5,
            "BEARISH": -15, "INVERTED": -15, "ELEVATED": -10,
            "RISK OFF": -15, "RESTRICTIVE": -10, "SOFTENING": -8,
            "ABOVE TARGET": -8, "TIGHT": -12,
            "DEEPLY INVERTED": -25, "CRISIS WIDE": -30, "HIGH FEAR": -20,
            "EXTREME FEAR": -35, "TIGHTENING": -12, "DETERIORATING": -20,
            "HOT INFLATION": -15, "COMPLACENCY": -5,
            "INFLATIONARY": -10,
        }

        score = 0
        details = []
        for sig_name, sig_data in signals.items():
            signal_label = sig_data.get("signal", "NEUTRAL")
            sig_score = IMPACT_SCORES.get(signal_label, 0)
            score += sig_score
            details.append({
                "signal":      sig_name.replace("_", " ").title(),
                "label":       signal_label,
                "score":       sig_score,
                "color":       sig_data.get("color", "#c9a96e"),
                "value":       sig_data.get("value"),
                "description": sig_data.get("description", ""),
            })

        score = max(-100, min(100, score))

        if score > 40:
            regime, color = "BULL MARKET",    "#4ade80"
        elif score > 15:
            regime, color = "RISK ON",        "#a3e635"
        elif score > -15:
            regime, color = "NEUTRAL",        "#c9a96e"
        elif score > -40:
            regime, color = "RISK OFF",       "#facc15"
        elif score > -65:
            regime, color = "BEAR MARKET",    "#f87171"
        else:
            regime, color = "CRISIS",         "#c084fc"

        return {
            "composite_score": score,
            "regime":          regime,
            "color":           color,
            "signals":         details,
            "individual":      signals,
            "timestamp":       datetime.now().isoformat(),
            "data_live":       self.fred._loaded,
        }

    def all_signals(self) -> dict:
        """Return all macro signals as a flat dict."""
        return {
            "yield_curve":          self.yield_curve_signal(),
            "credit_spreads":       self.credit_spread_signal(),
            "volatility":           self.volatility_signal(),
            "monetary_policy":      self.monetary_policy_signal(),
            "economic_cycle":       self.economic_cycle_signal(),
            "inflation":            self.inflation_signal(),
            "financial_conditions": self.financial_conditions_signal(),
            "composite":            self.composite_regime_score(),
        }

    def get_regime_features(self) -> pd.DataFrame:
        """
        Build a daily feature matrix for HMM regime detection.
        Returns normalized macro features aligned to trading calendar.
        """
        series_needed = ["T10Y2Y", "BAMLH0A0HYM2", "VIXCLS", "DFII10", "T5YIE"]
        frames = {}
        for sid in series_needed:
            s = self._get(sid).dropna()
            if len(s) > 0:
                s_filled = s.resample("D").ffill()
                frames[sid] = s_filled

        if not frames:
            return pd.DataFrame()

        df = pd.DataFrame(frames).dropna(how="all")
        df = df.ffill().bfill()

        # Normalize each column
        for col in df.columns:
            roll_mean = df[col].rolling(252, min_periods=20).mean()
            roll_std  = df[col].rolling(252, min_periods=20).std().replace(0, np.nan)
            df[f"{col}_z"] = (df[col] - roll_mean) / roll_std

        z_cols = [c for c in df.columns if c.endswith("_z")]
        result = df[z_cols].dropna(how="all")
        result.columns = [c.replace("_z", "") for c in z_cols]
        return result
