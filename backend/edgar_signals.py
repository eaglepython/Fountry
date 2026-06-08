"""
SEC EDGAR Accounting Signal Module
====================================
Fetches real financial statement data from the SEC's official XBRL API.
No API key, no cost — this is public government data.

Endpoint: https://data.sec.gov/api/xbrl/companyfacts/{CIK}.json

Signals produced:
  - Accruals (Sloan 1996): low accruals predict higher returns
  - Asset growth: low investment growth outperforms
  - Gross profitability (Novy-Marx 2013): gross profit / total assets
  - Net profit margin: earnings quality
  - Debt-to-equity: leverage signal
  - Cash conversion cycle: working capital efficiency
  - R&D intensity: innovation investment

All signals are point-in-time (use filing date, not period end date)
to avoid look-ahead bias.
"""

import os
import json
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

CACHE_DIR = Path("/tmp/alpha_foundry_cache/edgar")
CACHE_TTL = 86400 * 7  # 7 days — filings don't change often

# SEC rate limit: 10 requests/second
SEC_DELAY = 0.12

# ── XBRL Concept Mapping ─────────────────────────────────────────────────────
XBRL_CONCEPTS = {
    # Income statement
    "revenue":          ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                         "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "gross_profit":     ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income":       ["NetIncomeLoss", "ProfitLoss"],
    "rd_expense":       ["ResearchAndDevelopmentExpense"],
    "cogs":             ["CostOfRevenue", "CostOfGoodsSold", "CostOfGoodsSoldAndOperatingExpenses"],

    # Balance sheet
    "total_assets":     ["Assets"],
    "current_assets":   ["AssetsCurrent"],
    "current_liab":     ["LiabilitiesCurrent"],
    "total_liab":       ["Liabilities"],
    "total_equity":     ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "cash":             ["CashAndCashEquivalentsAtCarryingValue",
                         "CashCashEquivalentsAndShortTermInvestments"],
    "inventory":        ["InventoryNet"],
    "receivables":      ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"],
    "ppe_net":          ["PropertyPlantAndEquipmentNet"],
    "intangibles":      ["IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsNet"],
    "goodwill":         ["Goodwill"],
    "long_term_debt":   ["LongTermDebt", "LongTermDebtNoncurrent"],

    # Cash flow
    "cfo":              ["NetCashProvidedByUsedInOperatingActivities"],
    "capex":            ["PaymentsToAcquirePropertyPlantAndEquipment",
                         "PaymentsForProceedsFromBusinessesAndInterestInAffiliates"],
    "free_cashflow":    ["FreeCashFlow"],

    # Shares
    "shares":           ["CommonStockSharesOutstanding", "CommonStockSharesIssued"],
}

# SEC company CIK mapping for major tickers
# Full mapping: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=10-K
TICKER_TO_CIK = {
    "AAPL": "0000320193", "MSFT": "0000789019", "GOOGL": "0001652044",
    "AMZN": "0001018724", "NVDA": "0001045810", "META":  "0001326801",
    "JPM":  "0000019617", "JNJ":  "0000200406", "V":     "0001403161",
    "PG":   "0000080424", "MA":   "0001141391", "HD":    "0000354950",
    "CVX":  "0000093410", "MRK":  "0000310158", "ABBV":  "0001551152",
    "PEP":  "0000077476", "KO":   "0000021344", "AVGO":  "0001730168",
    "TSLA": "0001318605", "LLY":  "0000059478", "UNH":   "0000731766",
    "TMO":  "0000097476", "COST": "0000909832", "WMT":   "0000104169",
    "MCD":  "0000063908", "ABT":  "0000001800", "ACN":   "0001467373",
    "NFLX": "0001065280", "ADBE": "0000796343", "CRM":   "0001108524",
    "QCOM": "0000804328", "TXN":  "0000097476", "NEE":   "0000753308",
    "HON":  "0000773840", "IBM":  "0000051143", "CAT":   "0000018230",
    "GE":   "0000040534", "BA":   "0000012927", "GS":    "0000886982",
    "MS":   "0000895421", "BAC":  "0000070858", "C":     "0000831001",
    "WFC":  "0000072971", "BLK":  "0001364742", "SPGI":  "0000064040",
    "XOM":  "0000034088", "CVX":  "0000093410",
}


class SECEdgarLoader:
    """
    Fetches financial statement data from SEC EDGAR XBRL API.
    Completely free, official government data, no API key needed.
    """

    COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/{cik}.json"
    SUBMISSIONS_URL   = "https://data.sec.gov/submissions/{cik}.json"
    HEADERS = {
        "User-Agent": "AlphaFoundry research@example.com",  # SEC requires this
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",
    }

    def __init__(self):
        self._cache: Dict[str, dict] = {}
        self._facts: Dict[str, dict] = {}
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, cik: str) -> Path:
        return CACHE_DIR / f"{cik}.pkl"

    def _is_cache_fresh(self, cik: str) -> bool:
        p = self._cache_path(cik)
        if not p.exists():
            return False
        return (time.time() - p.stat().st_mtime) < CACHE_TTL

    def fetch_company_facts(self, cik: str) -> Optional[dict]:
        """Fetch all XBRL facts for a company. Returns raw JSON dict."""
        cik_padded = cik.lstrip("0").zfill(10)
        cik_padded = f"CIK{cik_padded}"

        # Check cache
        if self._is_cache_fresh(cik_padded):
            cached = self._load_cache(cik_padded)
            if cached:
                return cached

        try:
            url = self.COMPANY_FACTS_URL.format(cik=cik_padded)
            resp = requests.get(url, headers=self.HEADERS, timeout=15)
            time.sleep(SEC_DELAY)

            if resp.status_code == 200:
                data = resp.json()
                self._save_cache(cik_padded, data)
                return data
            else:
                log.debug(f"SEC EDGAR {cik}: HTTP {resp.status_code}")
                return None
        except Exception as e:
            log.debug(f"SEC EDGAR fetch failed for {cik}: {e}")
            return None

    def _load_cache(self, key: str) -> Optional[dict]:
        try:
            with open(CACHE_DIR / f"{key}.pkl", "rb") as f:
                return pickle.load(f)
        except Exception:
            return None

    def _save_cache(self, key: str, data: dict):
        try:
            with open(CACHE_DIR / f"{key}.pkl", "wb") as f:
                pickle.dump(data, f)
        except Exception:
            pass

    def extract_concept(self, facts: dict, concept_names: List[str],
                        unit: str = "USD", form: str = "10-K") -> pd.DataFrame:
        """
        Extract a specific concept from the XBRL facts dict.
        Returns DataFrame with columns: end, val, filed, accn, form
        """
        us_gaap = facts.get("facts", {}).get("us-gaap", {})

        for concept in concept_names:
            if concept not in us_gaap:
                continue
            units = us_gaap[concept].get("units", {})
            data = units.get(unit, units.get("USD", []))
            if not data:
                continue

            rows = [
                {
                    "end":   pd.Timestamp(r["end"]),
                    "val":   float(r["val"]),
                    "filed": pd.Timestamp(r.get("filed", r["end"])),
                    "accn":  r.get("accn", ""),
                    "form":  r.get("form", ""),
                    "fp":    r.get("fp", ""),
                }
                for r in data
                if r.get("form", "") in ("10-K", "10-Q", form, "")
                   and "val" in r
            ]
            if rows:
                df = pd.DataFrame(rows).sort_values("end")
                # Keep annual 10-K filings primarily
                annual = df[df["form"] == "10-K"]
                if len(annual) >= 2:
                    return annual
                return df

        return pd.DataFrame()

    def get_financial_history(self, ticker: str) -> dict:
        """
        Get multi-year financial history for a ticker.
        Returns dict of DataFrames: revenue, gross_profit, total_assets, etc.
        """
        cik = TICKER_TO_CIK.get(ticker.upper())
        if not cik:
            return {}

        facts = self.fetch_company_facts(cik)
        if not facts:
            return {}

        result = {}
        for field, concepts in XBRL_CONCEPTS.items():
            df = self.extract_concept(facts, concepts)
            if not df.empty:
                # Create point-in-time series using filing date (not period end)
                series = df.set_index("filed")["val"].sort_index()
                series = series[~series.index.duplicated(keep="last")]
                result[field] = series

        return result

    def load_universe(self, tickers: List[str]) -> Dict[str, dict]:
        """Load financial data for multiple tickers."""
        results = {}
        available = [t for t in tickers if t.upper() in TICKER_TO_CIK]
        log.info(f"SEC EDGAR: fetching {len(available)} tickers...")

        for ticker in available[:30]:  # Limit initial load
            data = self.get_financial_history(ticker)
            if data:
                results[ticker] = data
                log.debug(f"  {ticker}: {list(data.keys())}")
            time.sleep(SEC_DELAY)

        log.info(f"SEC EDGAR: loaded {len(results)} tickers")
        return results


# ── ACCOUNTING SIGNAL ENGINE ─────────────────────────────────────────────────

class AccountingSignalEngine:
    """
    Computes accounting-based alpha signals from SEC EDGAR data.
    All signals use point-in-time (filing date) data to avoid look-ahead bias.
    """

    def __init__(self, edgar_loader: SECEdgarLoader):
        self.edgar = edgar_loader
        self._universe_data: Dict[str, dict] = {}

    def load_universe(self, tickers: List[str]):
        """Load accounting data for the full universe."""
        self._universe_data = self.edgar.load_universe(tickers)
        log.info(f"Accounting data loaded for {len(self._universe_data)} tickers")

    def _get_latest(self, ticker: str, field: str) -> Optional[float]:
        """Get the most recent value of a financial field for a ticker."""
        data = self._universe_data.get(ticker, {})
        series = data.get(field)
        if series is None or len(series) == 0:
            return None
        return float(series.dropna().iloc[-1])

    def _get_prev(self, ticker: str, field: str, n: int = 1) -> Optional[float]:
        """Get the n-th most recent value of a field."""
        data = self._universe_data.get(ticker, {})
        series = data.get(field)
        if series is None or len(series) <= n:
            return None
        return float(series.dropna().iloc[-(n+1)])

    # ── Signal Computations ──────────────────────────────────────────────────

    def compute_accruals(self, ticker: str) -> Optional[float]:
        """
        Sloan (1996) accruals signal.
        Accruals = (Net Income - Cash from Operations) / Total Assets
        Low accruals = high earnings quality = outperformance.
        """
        ni  = self._get_latest(ticker, "net_income")
        cfo = self._get_latest(ticker, "cfo")
        ta  = self._get_latest(ticker, "total_assets")

        if any(v is None or v == 0 for v in [ni, ta]) or ta == 0:
            return None

        if cfo is None:
            # Approximate CFO from net income and working capital changes
            curr_a = self._get_latest(ticker, "current_assets")
            curr_l = self._get_latest(ticker, "current_liab")
            prev_a = self._get_prev(ticker, "current_assets")
            prev_l = self._get_prev(ticker, "current_liab")
            if all(v is not None for v in [curr_a, curr_l, prev_a, prev_l]):
                delta_wc = (curr_a - curr_l) - (prev_a - prev_l)
                cfo = ni - delta_wc
            else:
                return None

        accruals = (ni - cfo) / abs(ta)
        return float(accruals)

    def compute_asset_growth(self, ticker: str) -> Optional[float]:
        """
        Cooper, Gulen, Schill (2008) asset growth signal.
        Asset Growth = (Total Assets_t / Total Assets_{t-1}) - 1
        Low growth = better forward returns.
        """
        ta_curr = self._get_latest(ticker, "total_assets")
        ta_prev = self._get_prev(ticker, "total_assets")

        if ta_curr is None or ta_prev is None or ta_prev == 0:
            return None

        growth = ta_curr / ta_prev - 1
        return float(growth)

    def compute_gross_profitability(self, ticker: str) -> Optional[float]:
        """
        Novy-Marx (2013) gross profitability signal.
        GP/A = Gross Profit / Total Assets
        Higher is better (quality metric orthogonal to value).
        """
        gp = self._get_latest(ticker, "gross_profit")
        ta = self._get_latest(ticker, "total_assets")

        if gp is None and (self._get_latest(ticker, "revenue") is not None
                           and self._get_latest(ticker, "cogs") is not None):
            rev  = self._get_latest(ticker, "revenue")
            cogs = self._get_latest(ticker, "cogs")
            gp   = rev - abs(cogs)

        if gp is None or ta is None or ta == 0:
            return None

        return float(gp / abs(ta))

    def compute_roe(self, ticker: str) -> Optional[float]:
        """
        Return on Equity = Net Income / Shareholders' Equity.
        Higher ROE = higher quality earnings.
        """
        ni  = self._get_latest(ticker, "net_income")
        eq  = self._get_latest(ticker, "total_equity")

        if ni is None or eq is None or eq == 0:
            return None

        return float(ni / abs(eq))

    def compute_debt_to_equity(self, ticker: str) -> Optional[float]:
        """
        Financial leverage signal. High D/E = higher risk.
        Low D/E predicts better risk-adjusted returns.
        """
        debt = self._get_latest(ticker, "long_term_debt")
        eq   = self._get_latest(ticker, "total_equity")

        if debt is None or eq is None or eq == 0:
            return None

        return float(debt / abs(eq))

    def compute_net_profit_margin(self, ticker: str) -> Optional[float]:
        """Net income margin = Net Income / Revenue."""
        ni  = self._get_latest(ticker, "net_income")
        rev = self._get_latest(ticker, "revenue")

        if ni is None or rev is None or rev == 0:
            return None

        return float(ni / abs(rev))

    def compute_capex_intensity(self, ticker: str) -> Optional[float]:
        """
        Capital expenditure intensity = CapEx / Total Assets.
        High CapEx relative to assets may signal over-investment.
        """
        capex = self._get_latest(ticker, "capex")
        ta    = self._get_latest(ticker, "total_assets")

        if capex is None or ta is None or ta == 0:
            return None

        return float(abs(capex) / ta)

    def compute_rd_intensity(self, ticker: str) -> Optional[float]:
        """R&D / Revenue. Innovation investment as quality signal."""
        rd  = self._get_latest(ticker, "rd_expense")
        rev = self._get_latest(ticker, "revenue")

        if rd is None or rev is None or rev == 0:
            return None

        return float(abs(rd) / abs(rev))

    def compute_cash_ratio(self, ticker: str) -> Optional[float]:
        """Cash / Current Liabilities. Liquidity quality signal."""
        cash = self._get_latest(ticker, "cash")
        cl   = self._get_latest(ticker, "current_liab")

        if cash is None or cl is None or cl == 0:
            return None

        return float(cash / abs(cl))

    # ── Cross-Sectional Signal ───────────────────────────────────────────────

    def compute_cross_sectional_signal(self, signal_fn_name: str,
                                        higher_is_better: bool = True) -> pd.Series:
        """
        Compute a cross-sectional signal score for all tickers.
        Returns z-scored signal (positive = long, negative = short).
        """
        fn_map = {
            "accruals":          (self.compute_accruals,          False),  # Low accruals = good
            "asset_growth":      (self.compute_asset_growth,       False),  # Low growth = good
            "gross_profit":      (self.compute_gross_profitability, True),
            "roe":               (self.compute_roe,                 True),
            "debt_equity":       (self.compute_debt_to_equity,      False),  # Low leverage = good
            "net_margin":        (self.compute_net_profit_margin,   True),
            "capex_intensity":   (self.compute_capex_intensity,     False),  # Low capex = good (contrarian)
            "rd_intensity":      (self.compute_rd_intensity,        True),
            "cash_ratio":        (self.compute_cash_ratio,          True),
        }

        if signal_fn_name not in fn_map:
            return pd.Series()

        fn, default_direction = fn_map[signal_fn_name]
        use_higher = higher_is_better if higher_is_better is not None else default_direction

        scores = {}
        for ticker in self._universe_data:
            val = fn(ticker)
            if val is not None and not np.isnan(val) and not np.isinf(val):
                scores[ticker] = val

        if not scores:
            return pd.Series()

        s = pd.Series(scores)
        # Winsorize at 5th/95th percentile
        lo, hi = s.quantile(0.05), s.quantile(0.95)
        s = s.clip(lower=lo, upper=hi)
        # Z-score
        std = s.std()
        if std == 0 or np.isnan(std):
            return pd.Series()
        z = (s - s.mean()) / std
        return z if use_higher else -z

    # ── Summary Table ─────────────────────────────────────────────────────────

    def get_universe_accounting_summary(self) -> List[dict]:
        """
        Summary table: all tickers × all accounting metrics.
        Used by the frontend accounting panel.
        """
        rows = []
        for ticker in self._universe_data:
            row = {"ticker": ticker}
            for sig, (fn, _) in [
                ("accruals",     (self.compute_accruals,          False)),
                ("asset_growth", (self.compute_asset_growth,      False)),
                ("gross_profit_ratio", (self.compute_gross_profitability, True)),
                ("roe",          (self.compute_roe,                True)),
                ("net_margin",   (self.compute_net_profit_margin,  True)),
                ("debt_equity",  (self.compute_debt_to_equity,     False)),
                ("cash_ratio",   (self.compute_cash_ratio,         True)),
            ]:
                val = fn(ticker)
                row[sig] = round(float(val), 4) if val is not None else None
            rows.append(row)

        # Sort by gross profitability descending
        rows.sort(key=lambda r: r.get("gross_profit_ratio") or -99, reverse=True)
        return rows

    def get_signal_catalog(self) -> List[dict]:
        """Return accounting signal metadata for the frontend."""
        return [
            {
                "id": "ACCRUAL",
                "name": "Accruals (Sloan)",
                "description": "Net Income - CFO / Total Assets. Low accruals = high earnings quality.",
                "reference": "Sloan (1996) The Accounting Review",
                "direction": "lower_is_better",
            },
            {
                "id": "INV_GROW",
                "name": "Asset Growth",
                "description": "YoY change in total assets. Low growth predicts outperformance.",
                "reference": "Cooper, Gulen, Schill (2008) JF",
                "direction": "lower_is_better",
            },
            {
                "id": "QUAL_GP",
                "name": "Gross Profitability",
                "description": "Gross Profit / Total Assets. Orthogonal to value, high predictive power.",
                "reference": "Novy-Marx (2013) JFE",
                "direction": "higher_is_better",
            },
            {
                "id": "QUAL_ROE",
                "name": "Return on Equity",
                "description": "Net Income / Equity. Quality of earnings metric.",
                "reference": "Fama-French (2006)",
                "direction": "higher_is_better",
            },
            {
                "id": "LEV",
                "name": "Financial Leverage",
                "description": "Long-Term Debt / Equity. Lower leverage = better risk-adjusted returns.",
                "reference": "George, Hwang (2010)",
                "direction": "lower_is_better",
            },
        ]
