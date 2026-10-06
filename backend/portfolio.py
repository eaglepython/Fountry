"""
PortfolioEngine — Fails closed until a point-in-time, after-cost strategy
backtest is implemented. It does not report simulated fallback performance.
"""
import logging
import warnings
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from scipy import stats

warnings.filterwarnings("ignore")
log = logging.getLogger(__name__)

BENCHMARK = "SPY"

# ETF proxies are not used as Fama-French factors; attribution is unavailable.
FF_PROXIES = {
    "Market": ("SPY", True),
    "Value":  ("VTV", True),   # Value tilt
    "Growth": ("VUG", True),   # Growth
    "SmallCap": ("IWM", True), # Small cap
    "LongBond": ("TLT", True), # Interest rate duration
    "Gold":   ("GLD", True),   # Inflation hedge
}


class PortfolioEngine:
    def __init__(self, data_loader, signal_engine):
        self.dl = data_loader
        self.se = signal_engine
        self._portfolio_returns: Optional[pd.Series] = None
        self._benchmark_returns: Optional[pd.Series] = None
        self._build_portfolio()

    def _build_portfolio(self):
        """Fail closed until the strategy has a valid point-in-time backtest."""
        self._portfolio_returns = None
        self._benchmark_returns = None
        self.unavailable_reason = (
            "Portfolio results are disabled until historical, point-in-time signals, "
            "survivorship-aware constituents, and execution costs are available."
        )

    def performance(self) -> dict:
        """Portfolio performance statistics."""
        pr = self._portfolio_returns
        bm = self._benchmark_returns

        if pr is None or len(pr) == 0:
            return {"status": "unavailable", "reason": self.unavailable_reason}

        # Annualize (monthly)
        ann_ret = float(pr.mean() * 12)
        ann_vol = float(pr.std() * np.sqrt(12))
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0

        # Sortino
        downside = pr[pr < 0].std() * np.sqrt(12)
        sortino = ann_ret / downside if downside > 0 else 0

        # Max drawdown
        cum = (1 + pr).cumprod()
        running_max = cum.cummax()
        dd = (cum / running_max) - 1
        max_dd = float(dd.min())

        # Calmar
        calmar = ann_ret / abs(max_dd) if max_dd < 0 else 0

        # Beta to benchmark
        beta = 0.0
        alpha = ann_ret
        if bm is not None and len(bm) == len(pr):
            cov_matrix = np.cov(pr.values, bm.values)
            if cov_matrix[1, 1] > 0:
                beta = float(cov_matrix[0, 1] / cov_matrix[1, 1])
                bm_ann = float(bm.mean() * 12)
                alpha = ann_ret - beta * bm_ann

        # Equity curves
        pf_curve = (1 + pr).cumprod()
        bm_curve = (1 + bm).cumprod() if bm is not None and len(bm) > 0 else pf_curve

        return {
            "ann_return": round(ann_ret * 100, 2),
            "ann_volatility": round(ann_vol * 100, 2),
            "sharpe": round(sharpe, 2),
            "sortino": round(sortino, 2),
            "calmar": round(calmar, 2),
            "max_drawdown": round(max_dd * 100, 2),
            "beta": round(beta, 3),
            "alpha": round(alpha * 100, 2),
            "n_months": len(pr),
            "win_rate": round(float((pr > 0).mean() * 100), 1),
            "equity_curve": {
                "dates": [str(d.date()) for d in pf_curve.index],
                "portfolio": [round(float(v), 4) for v in pf_curve.values],
                "benchmark": [round(float(v), 4) for v in bm_curve.values],
            },
            "monthly_returns": [round(float(v * 100), 2) for v in pr.values],
        }

    def factor_attribution(self) -> dict:
        """Fama-French style factor return decomposition."""
        pr = self._portfolio_returns
        if pr is None or len(pr) == 0:
            return {"status": "unavailable", "attribution": [], "r_squared": None}

        # Build factor returns matrix
        factor_rets = {}
        for name, (ticker, _) in FF_PROXIES.items():
            if ticker in self.dl.returns:
                monthly = self.dl.returns[ticker].resample("ME").sum()
                factor_rets[name] = monthly.reindex(pr.index, method="nearest")

        if not factor_rets:
            return {"status": "unavailable", "attribution": [], "r_squared": None}

        X = pd.DataFrame(factor_rets).dropna()
        y = pr.reindex(X.index).dropna()
        common_idx = X.index.intersection(y.index)
        if len(common_idx) < 10:
            return {"status": "unavailable", "attribution": [], "r_squared": None}

        X_aligned = X.loc[common_idx]
        y_aligned = y.loc[common_idx]

        # OLS regression
        try:
            from sklearn.linear_model import LinearRegression
            model = LinearRegression()
            model.fit(X_aligned.values, y_aligned.values)
            residuals = y_aligned.values - model.predict(X_aligned.values)
            r2 = float(model.score(X_aligned.values, y_aligned.values))

            attribution = []
            for i, name in enumerate(X_aligned.columns):
                coeff = float(model.coef_[i])
                factor_ret = float(X_aligned[name].mean() * 12)
                contribution = coeff * factor_ret
                attribution.append({
                    "factor": name,
                    "beta": round(coeff, 3),
                    "factor_return": round(factor_ret * 100, 2),
                    "contribution": round(contribution * 100, 2),
                })

            # Add alpha
            ann_alpha = float(residuals.mean() * 12)
            attribution.append({
                "factor": "Alpha (Idiosyncratic)",
                "beta": None,
                "factor_return": None,
                "contribution": round(ann_alpha * 100, 2),
            })

            return {"attribution": attribution, "r_squared": round(r2, 3)}
        except Exception as e:
            log.warning(f"Attribution failed: {e}")
            return {"status": "unavailable", "attribution": [], "r_squared": None}

    def risk_metrics(self) -> dict:
        """VaR, CVaR, volatility, tracking error."""
        pr = self._portfolio_returns
        if pr is None or len(pr) == 0:
            return {"status": "unavailable", "reason": self.unavailable_reason}

        # Monthly to daily approximate
        daily_approx = pr / 21

        var_95 = float(np.percentile(pr.values, 5))
        var_99 = float(np.percentile(pr.values, 1))
        cvar_95 = float(pr[pr <= np.percentile(pr.values, 5)].mean())
        cvar_99 = float(pr[pr <= np.percentile(pr.values, 1)].mean())

        ann_vol = float(pr.std() * np.sqrt(12))

        tracking_error = 0.06
        if self._benchmark_returns is not None and len(self._benchmark_returns) == len(pr):
            active_ret = pr.values - self._benchmark_returns.values
            tracking_error = float(np.std(active_ret) * np.sqrt(12))

        return {
            "var_95_monthly": round(var_95 * 100, 2),
            "var_99_monthly": round(var_99 * 100, 2),
            "cvar_95_monthly": round(cvar_95 * 100, 2),
            "cvar_99_monthly": round(cvar_99 * 100, 2),
            "ann_volatility": round(ann_vol * 100, 2),
            "tracking_error": round(tracking_error * 100, 2),
            "skewness": round(float(stats.skew(pr.values)), 2),
            "kurtosis": round(float(stats.kurtosis(pr.values)), 2),
        }

    def current_holdings(self) -> dict:
        """No recommended holdings until a strategy passes a real validation gate."""
        return {"status": "unavailable", "longs": [], "shorts": []}

        return {"status": "unavailable", "longs": [], "shorts": []}
