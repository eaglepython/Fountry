"""
SignalEngine — Computes real alpha signals from market data.
Each signal produces a cross-sectional score (rank or z-score)
for every stock. IC is computed against actual forward returns.
"""
import logging
import warnings
from datetime import datetime
from typing import Dict, List, Optional, Callable
import pandas as pd
import numpy as np
from scipy import stats
# RankWarning not needed

warnings.filterwarnings("ignore")
log = logging.getLogger(__name__)

SIGNAL_CATALOG = [
    {"id": "MOM12_1",   "name": "12-1 Momentum",        "category": "Momentum",   "description": "12-month return skipping last month. Jegadeesh-Titman (1993)."},
    {"id": "STREV",     "name": "Short-Term Reversal",   "category": "Reversal",   "description": "1-week return reversal. Microstructure mean reversion."},
    {"id": "MOM_1M",    "name": "1-Month Momentum",      "category": "Momentum",   "description": "Trailing 21-day return. Captures intermediate trend."},
    {"id": "VAL_BM",    "name": "Book-to-Market",         "category": "Value",      "description": "Fama-French value factor. High BtM stocks outperform."},
    {"id": "VAL_EP",    "name": "Earnings Yield",         "category": "Value",      "description": "Trailing E/P ratio. Cheapness measured by earnings."},
    {"id": "QUAL_ROE",  "name": "Return on Equity",       "category": "Quality",    "description": "High ROE firms outperform. Profitability factor."},
    {"id": "QUAL_GP",   "name": "Gross Profitability",    "category": "Quality",    "description": "Novy-Marx (2013) gross profit. Orthogonal to value."},
    {"id": "LOW_VOL",   "name": "Low Volatility",         "category": "Risk",       "description": "Low realized vol anomaly. Risk-adjusted outperformance."},
    {"id": "LOW_BETA",  "name": "Low Beta",               "category": "Risk",       "description": "Flat SML. Betting against beta (BAB)."},
    {"id": "IDIOVOL",   "name": "Idiosyncratic Vol",      "category": "Risk",       "description": "Low idiosyncratic vol predicts higher returns."},
    {"id": "EARN_REV",  "name": "Earnings Revision",      "category": "Sentiment",  "description": "Analyst estimate revisions capture delayed reaction."},
    {"id": "SHORT_INT", "name": "Short Interest",         "category": "Sentiment",  "description": "High short interest predicts negative returns."},
    {"id": "ACCRUAL",   "name": "Accruals",               "category": "Accounting", "description": "Low accruals predict higher returns (Sloan 1996)."},
    {"id": "INV_GROW",  "name": "Investment Growth",      "category": "Accounting", "description": "Low asset growth predicts outperformance."},
    {"id": "COMBO_QVM", "name": "Quality-Value-Momentum", "category": "Composite",  "description": "Equal-weighted composite of QVM signals."},
]


def winsorize(s: pd.Series, limits=(0.05, 0.05)) -> pd.Series:
    """Winsorize at given percentiles to reduce outlier influence."""
    low = s.quantile(limits[0])
    high = s.quantile(1 - limits[1])
    return s.clip(lower=low, upper=high)


def cross_sectional_zscore(s: pd.Series) -> pd.Series:
    """Standardize cross-sectionally, remove outliers."""
    s = winsorize(s)
    std = s.std()
    if std == 0 or np.isnan(std):
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - s.mean()) / std


def ic_from_series(signal: pd.Series, forward_ret: pd.Series) -> float:
    """Pearson IC between signal and forward return."""
    common = signal.dropna().index.intersection(forward_ret.dropna().index)
    if len(common) < 10:
        return np.nan
    x = signal[common].values
    y = forward_ret[common].values
    mask = ~(np.isnan(x) | np.isnan(y) | np.isinf(x) | np.isinf(y))
    if mask.sum() < 10:
        return np.nan
    r, _ = stats.pearsonr(x[mask], y[mask])
    return float(r)


def rank_ic(signal: pd.Series, forward_ret: pd.Series) -> float:
    """Spearman Rank IC — more robust to outliers."""
    common = signal.dropna().index.intersection(forward_ret.dropna().index)
    if len(common) < 10:
        return np.nan
    x = signal[common].values
    y = forward_ret[common].values
    mask = ~(np.isnan(x) | np.isnan(y) | np.isinf(x) | np.isinf(y))
    if mask.sum() < 10:
        return np.nan
    r, _ = stats.spearmanr(x[mask], y[mask])
    return float(r)


class SignalEngine:
    def __init__(self, data_loader):
        self.dl = data_loader
        self._signal_cache: Dict[str, pd.DataFrame] = {}
        self._ic_cache: Dict[str, dict] = {}

    # ── Signal Constructors ───────────────────────────────────────────────────

    def _compute_momentum(self, lookback: int = 252, skip: int = 21) -> pd.Series:
        """Cross-sectional momentum signal."""
        rm = self.dl.get_returns_matrix(lookback=lookback + skip + 20)
        if rm.empty:
            return pd.Series()
        cum_ret = {}
        for t in rm.columns:
            px_ret = rm[t].dropna()
            if len(px_ret) < lookback:
                continue
            end_idx = -skip if skip > 0 else len(px_ret)
            start_idx = end_idx - lookback
            if start_idx < 0:
                continue
            slice_ret = px_ret.iloc[start_idx:end_idx]
            cum_ret[t] = (1 + slice_ret).prod() - 1
        return cross_sectional_zscore(pd.Series(cum_ret))

    def _compute_short_term_reversal(self, days: int = 5) -> pd.Series:
        """Short-term reversal: negative of last n-day return."""
        rm = self.dl.get_returns_matrix(lookback=days + 5)
        if rm.empty:
            return pd.Series()
        recent = {}
        for t in rm.columns:
            px_ret = rm[t].dropna()
            if len(px_ret) < days:
                continue
            recent[t] = (1 + px_ret.iloc[-days:]).prod() - 1
        s = pd.Series(recent)
        return cross_sectional_zscore(-s)  # Reversal = negative momentum

    def _compute_realized_vol(self, window: int = 21) -> pd.Series:
        """Realized volatility signal (low vol anomaly → negate)."""
        rm = self.dl.get_returns_matrix(lookback=window + 5)
        if rm.empty:
            return pd.Series()
        vols = rm.tail(window).std() * np.sqrt(252)
        return cross_sectional_zscore(-vols)  # Low vol = positive score

    def _compute_beta(self) -> pd.Series:
        """Market beta from 1-year regression."""
        rm = self.dl.get_returns_matrix(lookback=252)
        if rm.empty or BENCHMARK not in self.dl.returns:
            return pd.Series()
        mkt = self.dl.returns[BENCHMARK].reindex(rm.index).dropna()
        betas = {}
        for t in rm.columns:
            stock_ret = rm[t].dropna()
            common_dates = stock_ret.index.intersection(mkt.index)
            if len(common_dates) < 60:
                continue
            x = mkt[common_dates].values
            y = stock_ret[common_dates].values
            cov = np.cov(x, y)[0, 1]
            var = np.var(x)
            betas[t] = cov / var if var > 0 else np.nan
        return cross_sectional_zscore(-pd.Series(betas))  # Low beta = positive

    def _compute_idiovol(self, window: int = 60) -> pd.Series:
        """Idiosyncratic volatility from market model residuals."""
        rm = self.dl.get_returns_matrix(lookback=window + 5)
        if rm.empty or BENCHMARK not in self.dl.returns:
            return pd.Series()
        mkt = self.dl.returns[BENCHMARK].reindex(rm.index).dropna()
        idio_vols = {}
        for t in rm.columns:
            stock_ret = rm[t].dropna()
            common_dates = stock_ret.index.intersection(mkt.index)
            if len(common_dates) < 30:
                continue
            x = mkt[common_dates].values.reshape(-1, 1)
            y = stock_ret[common_dates].values
            try:
                slope, intercept, _, _, _ = stats.linregress(x.flatten(), y)
                residuals = y - (slope * x.flatten() + intercept)
                idio_vols[t] = float(np.std(residuals) * np.sqrt(252))
            except Exception:
                pass
        return cross_sectional_zscore(-pd.Series(idio_vols))

    def _compute_fundamental_signal(self, field: str, higher_is_better: bool = True) -> pd.Series:
        """Generic fundamental signal from fundamentals_df."""
        if not hasattr(self.dl, "fundamentals_df") or self.dl.fundamentals_df.empty:
            return self._synthetic_fundamental_signal(field)
        df = self.dl.fundamentals_df
        if field not in df.columns:
            return self._synthetic_fundamental_signal(field)
        s = df[field].dropna()
        s = s[s.index.isin(self.dl.equity_universe)]
        if s.empty:
            return self._synthetic_fundamental_signal(field)
        if not higher_is_better:
            s = -s
        return cross_sectional_zscore(s)

    def _synthetic_fundamental_signal(self, field: str) -> pd.Series:
        """Do not invent accounting or analyst data when it is unavailable."""
        log.warning("Signal %s unavailable: no point-in-time source", field)
        return pd.Series(dtype=float)

    def _get_signal(self, signal_id: str) -> pd.Series:
        """Dispatch to signal constructor."""
        dispatch = {
            "MOM12_1":   lambda: self._compute_momentum(252, 21),
            "STREV":     lambda: self._compute_short_term_reversal(5),
            "MOM_1M":    lambda: self._compute_momentum(21, 0),
            "VAL_BM":    lambda: self._compute_fundamental_signal("price_to_book", False),
            "VAL_EP":    lambda: self._compute_fundamental_signal("pe_ratio", False),
            "QUAL_ROE":  lambda: self._compute_fundamental_signal("roe", True),
            "QUAL_GP":   lambda: self._compute_fundamental_signal("gross_margin", True),
            "LOW_VOL":   lambda: self._compute_realized_vol(21),
            "LOW_BETA":  lambda: self._compute_beta(),
            "IDIOVOL":   lambda: self._compute_idiovol(60),
            "EARN_REV":  lambda: self._synthetic_fundamental_signal("earn_rev"),  # Needs analyst data
            "SHORT_INT": lambda: self._compute_fundamental_signal("short_ratio", False),
            "ACCRUAL":   lambda: self._synthetic_fundamental_signal("accrual"),
            "INV_GROW":  lambda: self._synthetic_fundamental_signal("inv_grow"),
            "COMBO_QVM": lambda: self._compute_composite(),
        }
        fn = dispatch.get(signal_id)
        if fn is None:
            return pd.Series()
        try:
            return fn()
        except Exception as e:
            log.warning(f"Signal {signal_id} failed: {e}")
            return pd.Series()

    def _compute_composite(self) -> pd.Series:
        """Equal-weight composite of quality, value, momentum."""
        signals = []
        for sid in ["MOM12_1", "VAL_BM", "QUAL_ROE"]:
            s = self._get_signal(sid)
            if not s.empty:
                signals.append(cross_sectional_zscore(s))
        if not signals:
            return pd.Series()
        combined = pd.concat(signals, axis=1).mean(axis=1)
        return cross_sectional_zscore(combined)

    # ── IC Computation ────────────────────────────────────────────────────────

    def compute_rolling_ic(self, signal_id: str, horizon: int = 21, window: int = 252) -> dict:
        """Compute rolling IC over the past `window` days."""
        rm = self.dl.get_returns_matrix(lookback=window + horizon + 30)
        if rm.empty:
            return {"ic_series": [], "dates": [], "mean_ic": None, "icir": None}

        # Compute signal at each rebalance date (monthly)
        rebal_dates = rm.index[::21]  # Monthly
        ic_values = []
        dates_used = []

        for i, date in enumerate(rebal_dates[:-1]):
            # Signal at date t
            signal = self._get_signal_at(signal_id, date, rm)
            if signal.empty:
                continue

            # Forward return: date t to t+horizon
            future_idx = rm.index.get_loc(date)
            future_start_idx = future_idx + 1
            future_end_idx = min(future_idx + horizon + 1, len(rm))
            if future_end_idx <= future_start_idx:
                continue

            future_ret = (1 + rm.iloc[future_start_idx:future_end_idx]).prod() - 1
            fwd = future_ret

            ic = rank_ic(signal, fwd)
            if not np.isnan(ic):
                ic_values.append(ic)
                dates_used.append(str(date.date()))

        if not ic_values:
            return {"ic_series": [], "dates": [], "mean_ic": None, "icir": None}

        mean_ic = float(np.mean(ic_values))
        icir = float(mean_ic / np.std(ic_values)) if np.std(ic_values) > 0 else 0

        return {
            "dates": dates_used,
            "ic_series": [round(v, 4) for v in ic_values],
            "mean_ic": round(mean_ic, 4),
            "icir": round(icir, 3),
            "t_stat": round(mean_ic / (np.std(ic_values) / np.sqrt(len(ic_values))), 2) if len(ic_values) > 1 else 0,
            "pct_positive": round(sum(1 for v in ic_values if v > 0) / len(ic_values) * 100, 1),
        }

    def _get_signal_at(self, signal_id: str, date, returns: pd.DataFrame) -> pd.Series:
        """Build technical signals from observations available by `date` only."""
        history = returns.loc[:date]
        if signal_id == "MOM12_1":
            values = (1 + history.iloc[-252-21:-21]).prod() - 1 if len(history) >= 273 else pd.Series(dtype=float)
        elif signal_id == "MOM_1M":
            values = (1 + history.tail(21)).prod() - 1 if len(history) >= 21 else pd.Series(dtype=float)
        elif signal_id == "STREV":
            values = -((1 + history.tail(5)).prod() - 1) if len(history) >= 5 else pd.Series(dtype=float)
        elif signal_id == "LOW_VOL":
            values = -history.tail(21).std() * np.sqrt(252) if len(history) >= 21 else pd.Series(dtype=float)
        elif signal_id in {"LOW_BETA", "IDIOVOL"} and BENCHMARK in history.columns:
            market = history[BENCHMARK]
            window = history.tail(252 if signal_id == "LOW_BETA" else 60)
            values = {}
            for ticker in window.columns:
                if ticker == BENCHMARK:
                    continue
                pair = pd.concat([window[ticker], market.reindex(window.index)], axis=1).dropna()
                if len(pair) < (60 if signal_id == "LOW_BETA" else 30):
                    continue
                cov = np.cov(pair.iloc[:, 0], pair.iloc[:, 1])[0, 1]
                var = np.var(pair.iloc[:, 1])
                if var <= 0:
                    continue
                beta = cov / var
                values[ticker] = -beta if signal_id == "LOW_BETA" else -float(np.std(pair.iloc[:, 0] - beta * pair.iloc[:, 1]) * np.sqrt(252))
            values = pd.Series(values)
        else:
            # Current Yahoo fundamentals and analyst snapshots are not historical data.
            return pd.Series(dtype=float)
        return cross_sectional_zscore(values.dropna()) if len(values) else pd.Series(dtype=float)

    def compute_signal_stats(self, signal_id: str, horizon: int = 21) -> dict:
        """Core performance stats for one signal."""
        ic_data = self.compute_rolling_ic(signal_id, horizon=horizon)
        if not ic_data["ic_series"]:
            return {"signal_id": signal_id, "ic": None, "icir": None, "t_stat": None,
                    "pct_positive_ic": None, "gross_sharpe": None, "net_sharpe": None,
                    "annual_ir": None, "max_drawdown": None, "turnover": None,
                    "tc_cost": None, "win_rate": None, "n_periods": 0,
                    "promoted": False, "status": "INSUFFICIENT_POINT_IN_TIME_DATA"}

        ic_vals = ic_data["ic_series"]
        mean_ic = ic_data["mean_ic"]
        icir = ic_data["icir"]
        t_stat = ic_data["t_stat"]

        return {
            "signal_id": signal_id,
            "ic": round(mean_ic, 4) if mean_ic else 0,
            "icir": round(icir, 3) if icir else 0,
            "t_stat": round(t_stat, 2) if t_stat else 0,
            "pct_positive_ic": ic_data.get("pct_positive", 50),
            "gross_sharpe": None,
            "net_sharpe": None,
            "annual_ir": None,
            "max_drawdown": None,
            "turnover": None,
            "tc_cost": None,
            "win_rate": None,
            "n_periods": len(ic_vals),
            # IC alone is not a net portfolio backtest; never auto-promote on it.
            "promoted": False,
            "status": "IC_RESEARCH_ONLY",
        }

    # ── Bulk Computations ─────────────────────────────────────────────────────

    def compute_all_signals(self) -> list:
        """Compute stats for all signals in catalog."""
        results = []
        for sig in SIGNAL_CATALOG:
            log.info(f"Computing {sig['id']}...")
            stats_data = self.compute_signal_stats(sig["id"])
            results.append({**sig, **stats_data})
        return results

    def compute_signal_detail(self, signal_id: str) -> dict:
        """Full detail for one signal including decay and distributions."""
        base = self.compute_signal_stats(signal_id)
        ic_roll = self.compute_rolling_ic(signal_id)
        wf = self.walk_forward(signal_id, years=5)

        return {
            **base,
            "rolling_ic": ic_roll,
            "decay": [],
            "walkforward": wf,
            "monthly_returns": [],
        }

    def compute_decay(self, signal_id: str) -> list:
        """IC decay as function of lag days 1–21."""
        return []

    def walk_forward(self, signal_id: str, years: int = 5) -> list:
        """Year-by-year walk-forward OOS metrics."""
        ic_roll = self.compute_rolling_ic(signal_id)
        ic_series = ic_roll.get("ic_series", [])
        dates = ic_roll.get("dates", [])

        results = []
        for y in range(years):
            year = datetime.now().year - years + y
            year_ics = [ic_series[i] for i, d in enumerate(dates) if d.startswith(str(year))]
            if year_ics:
                yr_ic = float(np.mean(year_ics))
            else:
                continue

            results.append({
                "year": year,
                "ic": round(yr_ic, 4),
                "ann_return": None,
                "n_months": len(year_ics),
            })

        return results

    def compute_regime_conditional_ic(self, regime_detector) -> dict:
        """IC of each signal conditioned on each regime."""
        return {sig["id"]: {reg: None for reg in ["bull", "bear", "crisis", "range_bound", "inflationary"]}
                for sig in SIGNAL_CATALOG}


BENCHMARK = "SPY"
