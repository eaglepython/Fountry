"""
RegimeDetector — Classifies market regimes using HMM.
Uses S&P 500 return distribution to identify bull/bear/crisis/range states.
"""
import logging
import warnings
import numpy as np
import pandas as pd
from typing import Dict, List, Optional

warnings.filterwarnings("ignore")
log = logging.getLogger(__name__)

try:
    from hmmlearn.hmm import GaussianHMM
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    log.warning("hmmlearn not available — using rule-based regime classification")

REGIME_LABELS = {
    0: {"id": "bull",         "name": "Bull Market",    "color": "#4ade80", "desc": "Trending up, low volatility"},
    1: {"id": "bear",         "name": "Bear Market",    "color": "#f87171", "desc": "Trending down, elevated vol"},
    2: {"id": "crisis",       "name": "Crisis",         "color": "#c084fc", "desc": "Extreme vol, correlation spike"},
    3: {"id": "range_bound",  "name": "Range-Bound",    "color": "#facc15", "desc": "Low vol, mean-reverting"},
    4: {"id": "inflationary", "name": "Inflationary",   "color": "#fb923c", "desc": "Rising rates, commodity-driven"},
}

N_STATES = 3  # HMM uses 3 states; we map to semantic labels


class RegimeDetector:
    def __init__(self, data_loader):
        self.dl = data_loader
        self._model = None
        self._regime_series: Optional[pd.Series] = None
        self._prob_series: Optional[pd.DataFrame] = None
        self._features: Optional[pd.DataFrame] = None
        self._fit()

    def _build_features(self) -> pd.DataFrame:
        """Build feature matrix for HMM: returns, vol, vol-of-vol."""
        if "SPY" not in self.dl.returns:
            return pd.DataFrame()

        spy_ret = self.dl.returns["SPY"].dropna()
        if len(spy_ret) < 60:
            return pd.DataFrame()

        df = pd.DataFrame({"ret": spy_ret})
        df["vol_21"] = spy_ret.rolling(21).std() * np.sqrt(252)
        df["vol_5"] = spy_ret.rolling(5).std() * np.sqrt(252)
        df["vol_ratio"] = df["vol_5"] / df["vol_21"].replace(0, np.nan)  # Vol spike indicator
        df["trend_50"] = spy_ret.rolling(50).mean() * 252  # Annualized trend
        df["trend_200"] = spy_ret.rolling(200).mean() * 252
        df["sma_ratio"] = df["trend_50"] / df["trend_200"].replace(0, np.nan)

        df = df.dropna()
        return df

    def _fit(self):
        """Fit HMM to SPY return features."""
        features = self._build_features()
        if features.empty:
            log.warning("No data for regime detection — using rule-based")
            self._fit_rule_based()
            return

        self._features = features
        feature_cols = ["ret", "vol_21", "vol_ratio", "trend_50"]
        X = features[feature_cols].values

        if HMM_AVAILABLE and len(X) >= 100:
            try:
                model = GaussianHMM(
                    n_components=N_STATES,
                    covariance_type="diag",
                    n_iter=200,
                    random_state=42,
                    tol=1e-4,
                )
                model.fit(X)
                hidden_states = model.predict(X)
                probs = model.predict_proba(X)
                self._model = model

                # Map HMM states to semantic labels by vol level
                state_vols = {}
                for s in range(N_STATES):
                    mask = hidden_states == s
                    if mask.sum() > 0:
                        state_vols[s] = features["vol_21"].values[mask].mean()
                    else:
                        state_vols[s] = 0

                # Sort: low vol = bull/range, high vol = bear/crisis
                sorted_states = sorted(state_vols.keys(), key=lambda s: state_vols[s])
                state_to_regime = {}
                state_to_regime[sorted_states[0]] = "range_bound"  # Lowest vol
                if N_STATES == 3:
                    state_to_regime[sorted_states[1]] = "bull"
                    state_to_regime[sorted_states[2]] = "crisis"
                elif N_STATES >= 4:
                    state_to_regime[sorted_states[1]] = "bull"
                    state_to_regime[sorted_states[2]] = "bear"
                    if N_STATES >= 5:
                        state_to_regime[sorted_states[3]] = "inflationary"
                    state_to_regime[sorted_states[-1]] = "crisis"

                # Enrich: check if trend is down (bull→bear)
                regime_labels = []
                for i, s in enumerate(hidden_states):
                    label = state_to_regime.get(s, "bull")
                    trend = features["trend_50"].iloc[i]
                    if label == "bull" and trend < -0.05:
                        label = "bear"
                    regime_labels.append(label)

                self._regime_series = pd.Series(regime_labels, index=features.index)
                self._prob_series = pd.DataFrame(probs, index=features.index,
                    columns=[f"prob_{s}" for s in range(N_STATES)])
                log.info(f"✅ HMM fitted: {N_STATES} states, {len(X)} observations")
                return

            except Exception as e:
                log.warning(f"HMM fitting failed: {e} — using rule-based")

        # Fallback
        self._fit_rule_based()

    def _fit_rule_based(self):
        """Rule-based regime classification without HMM."""
        features = self._features
        if features is None or features.empty:
            features = self._build_features()
        if features is None or features.empty:
            self._regime_series = pd.Series()
            return

        labels = []
        for i in range(len(features)):
            row = features.iloc[i]
            vol = row.get("vol_21", 0.15)
            trend = row.get("trend_50", 0)
            vol_ratio = row.get("vol_ratio", 1)

            if vol > 0.35 or vol_ratio > 2.5:
                label = "crisis"
            elif trend > 0.1 and vol < 0.18:
                label = "bull"
            elif trend < -0.05:
                label = "bear"
            elif vol < 0.12:
                label = "range_bound"
            else:
                label = "bull"
            labels.append(label)

        self._regime_series = pd.Series(labels, index=features.index)
        log.info(f"Rule-based regimes computed: {len(labels)} days")

    def current_regime(self) -> dict:
        """Current regime classification with probability breakdown."""
        if self._regime_series is None or len(self._regime_series) == 0:
            return {
                "regime": "bull",
                "name": "Bull Market",
                "color": "#4ade80",
                "confidence": 0.75,
                "probabilities": {"bull": 0.75, "bear": 0.15, "crisis": 0.05, "range_bound": 0.05},
                "description": "Data insufficient for regime classification",
            }

        current = self._regime_series.iloc[-1]
        regime_info = next((v for v in REGIME_LABELS.values() if v["id"] == current), REGIME_LABELS[0])

        # Build probability breakdown
        probs = {}
        if self._prob_series is not None and len(self._prob_series) > 0:
            raw_probs = self._prob_series.iloc[-1].values
            probs = {f"state_{i}": round(float(p), 3) for i, p in enumerate(raw_probs)}
        else:
            # Rule-based confidence
            for reg in REGIME_LABELS.values():
                probs[reg["id"]] = 0.1
            probs[current] = 0.75
            # Normalize
            total = sum(probs.values())
            probs = {k: round(v / total, 3) for k, v in probs.items()}

        # Regime duration
        duration = 1
        for label in reversed(list(self._regime_series)):
            if label == current:
                duration += 1
            else:
                break

        return {
            "regime": current,
            "name": regime_info["name"],
            "color": regime_info["color"],
            "description": regime_info["desc"],
            "confidence": probs.get(current, 0.7),
            "duration_days": duration,
            "probabilities": probs,
            "last_updated": str(self._regime_series.index[-1].date()) if len(self._regime_series) > 0 else None,
        }

    def full_history(self) -> dict:
        """Full regime history as list of {date, regime, prob}."""
        if self._regime_series is None or len(self._regime_series) == 0:
            return {"history": [], "regime_counts": {}}

        history = []
        for date, regime in self._regime_series.items():
            regime_info = next((v for v in REGIME_LABELS.values() if v["id"] == regime), REGIME_LABELS[0])
            entry = {
                "date": str(date.date()),
                "regime": regime,
                "name": regime_info["name"],
                "color": regime_info["color"],
            }
            if self._prob_series is not None and date in self._prob_series.index:
                ps = self._prob_series.loc[date].values
                entry["probs"] = [round(float(p), 3) for p in ps]
            history.append(entry)

        # Regime counts
        counts = self._regime_series.value_counts().to_dict()
        total = len(self._regime_series)
        regime_counts = {k: {"count": int(v), "pct": round(v / total * 100, 1)} for k, v in counts.items()}

        return {
            "history": history[-252:],  # Last year
            "all_history": history,
            "regime_counts": regime_counts,
            "n_days": total,
            "current": self.current_regime(),
        }

    def get_regime_at_date(self, date) -> str:
        """Get regime label for a specific date."""
        if self._regime_series is None or len(self._regime_series) == 0:
            return "bull"
        try:
            date_idx = pd.Timestamp(date)
            if date_idx in self._regime_series.index:
                return self._regime_series[date_idx]
            # Find nearest
            nearest = self._regime_series.index[
                self._regime_series.index.get_indexer([date_idx], method="nearest")[0]
            ]
            return self._regime_series[nearest]
        except Exception:
            return "bull"
