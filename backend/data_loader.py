"""
DataLoader — Fetches real market data.
Primary: yfinance (free, no API key needed)
Optional upgrade: Polygon.io (set POLYGON_API_KEY in .env for real-time)
"""
import os
import asyncio
import logging
import time
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

# ── Research Universe ─────────────────────────────────────────────────────────
UNIVERSE = [
    # Large-cap US equities — liquid, good for factor research
    "AAPL","MSFT","GOOGL","AMZN","NVDA","META","BRK-B","JPM","XOM","JNJ",
    "V","PG","MA","HD","CVX","MRK","ABBV","PEP","KO","AVGO",
    "TSLA","LLY","UNH","TMO","COST","WMT","MCD","ABT","ACN","NFLX",
    "ADBE","CRM","QCOM","TXN","NEE","HON","IBM","CAT","GE","BA",
    "GS","MS","BAC","C","WFC","BLK","SPGI","MCO","ICE","CME",
    # ETFs for benchmarking
    "SPY","QQQ","IWM","VTV","VUG","VBR","VBK","AGG","TLT","GLD",
]

BENCHMARK = "SPY"

class DataLoader:
    def __init__(self):
        self.universe: List[str] = UNIVERSE
        self.prices: Dict[str, pd.DataFrame] = {}
        self.returns: Dict[str, pd.Series] = {}
        self.fundamentals: Dict[str, dict] = {}
        self.market_caps: Dict[str, float] = {}
        self.is_loaded: bool = False
        self._load_time: float = 0
        self.polygon_key = os.getenv("POLYGON_API_KEY", "")
        # Cache path
        self._cache_dir = "/tmp/alpha_foundry_cache"
        os.makedirs(self._cache_dir, exist_ok=True)

    async def load_all(self):
        """Fetch all data asynchronously."""
        log.info(f"Loading data for {len(self.universe)} tickers...")
        start = time.time()

        # Run yfinance download in thread pool (it's synchronous)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._download_prices)
        await loop.run_in_executor(None, self._download_fundamentals)

        self.is_loaded = True
        self._load_time = time.time() - start
        log.info(f"✅ Data loaded in {self._load_time:.1f}s — {len(self.prices)} tickers")

    def _download_prices(self):
        """Download 5 years of daily OHLCV — fetches individually for reliability."""
        cache_file = f"{self._cache_dir}/prices.pkl"

        if os.path.exists(cache_file):
            age = time.time() - os.path.getmtime(cache_file)
            if age < 3600:
                log.info("Using cached price data")
                df = pd.read_pickle(cache_file)
                self._process_prices(df)
                return

        all_closes = {}
        for ticker in self.universe:
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="5y", auto_adjust=True)
                if hist is not None and len(hist) > 60 and "Close" in hist.columns:
                    all_closes[ticker] = hist["Close"]
            except Exception:
                pass

        if all_closes:
            closes = pd.DataFrame(all_closes)
            try:
                closes.to_pickle(cache_file)
            except Exception:
                pass
            self._process_prices(closes)
            log.info(f"Downloaded prices: {closes.shape}")
        else:
            log.warning("No prices downloaded — using fallback")
            self._use_fallback_prices()

    def _process_prices(self, closes: pd.DataFrame):
        """Compute returns and store per-ticker series."""
        for ticker in closes.columns:
            try:
                px = closes[ticker].dropna()
                if len(px) < 60:
                    continue
                self.prices[ticker] = px
                self.returns[ticker] = px.pct_change().dropna()
            except Exception:
                pass

    def _download_fundamentals(self):
        """Fetch fundamental data for factor construction."""
        cache_file = f"{self._cache_dir}/fundamentals.pkl"
        if os.path.exists(cache_file):
            age = time.time() - os.path.getmtime(cache_file)
            if age < 86400:  # Cache fundamentals for 1 day
                log.info("Using cached fundamental data")
                df = pd.read_pickle(cache_file)
                self.fundamentals_df = df
                return

        rows = []
        equity_tickers = [t for t in self.universe if not t.startswith("SPY") and t not in ["QQQ","IWM","AGG","TLT","GLD","VTV","VUG","VBR","VBK"]]

        for ticker in equity_tickers[:40]:  # Limit to avoid rate limits
            try:
                info = yf.Ticker(ticker).info
                rows.append({
                    "ticker": ticker,
                    "market_cap": info.get("marketCap", np.nan),
                    "book_value": info.get("bookValue", np.nan),
                    "eps_ttm": info.get("trailingEps", np.nan),
                    "pe_ratio": info.get("trailingPE", np.nan),
                    "price_to_book": info.get("priceToBook", np.nan),
                    "roe": info.get("returnOnEquity", np.nan),
                    "gross_margin": info.get("grossMargins", np.nan),
                    "beta": info.get("beta", np.nan),
                    "short_ratio": info.get("shortRatio", np.nan),
                    "forward_pe": info.get("forwardPE", np.nan),
                    "peg_ratio": info.get("pegRatio", np.nan),
                    "total_assets": info.get("totalAssets", np.nan),
                    "total_debt": info.get("totalDebt", np.nan),
                    "free_cashflow": info.get("freeCashflow", np.nan),
                    "ebitda": info.get("ebitda", np.nan),
                    "revenue": info.get("totalRevenue", np.nan),
                    "gross_profit": info.get("grossProfits", np.nan),
                })
                self.market_caps[ticker] = info.get("marketCap", np.nan)
            except Exception:
                pass

        if rows:
            df = pd.DataFrame(rows).set_index("ticker")
            df.to_pickle(cache_file)
            self.fundamentals_df = df
            log.info(f"Downloaded fundamentals: {len(rows)} tickers")
        else:
            self.fundamentals_df = pd.DataFrame()

    def _use_fallback_prices(self):
        """Generate realistic synthetic prices if download fails."""
        log.warning("Using fallback synthetic price data")
        np.random.seed(42)
        dates = pd.bdate_range(end=datetime.today(), periods=252*3)
        for i, ticker in enumerate(self.universe[:30]):
            prices = 100 * np.exp(np.cumsum(
                np.random.normal(0.0003 + i*0.00001, 0.015, len(dates))
            ))
            self.prices[ticker] = pd.Series(prices, index=dates, name=ticker)
            self.returns[ticker] = self.prices[ticker].pct_change().dropna()

    def get_prices(self, ticker: str, period: str = "1y") -> dict:
        """Return OHLCV-style price data for frontend chart."""
        if ticker not in self.prices:
            raise HTTPException(404, f"Ticker {ticker} not in universe")
        px = self.prices[ticker]
        # Slice by period
        cutoff_days = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "2y": 504, "5y": 1260}
        days = cutoff_days.get(period, 252)
        px = px.iloc[-days:]
        return {
            "ticker": ticker,
            "dates": [d.strftime("%Y-%m-%d") for d in px.index],
            "prices": [round(float(v), 2) for v in px.values],
            "returns": [round(float(v), 6) for v in px.pct_change().dropna().values],
        }

    def get_live_snapshot(self) -> dict:
        """Latest closing prices for universe."""
        snapshot = {}
        for ticker, px in self.prices.items():
            if len(px) > 1:
                latest = float(px.iloc[-1])
                prev = float(px.iloc[-2])
                chg = (latest - prev) / prev
                snapshot[ticker] = {
                    "price": round(latest, 2),
                    "change": round(chg * 100, 2),
                    "volume": None,
                }
        return snapshot

    def get_universe_info(self) -> list:
        """Basic info for all tickers."""
        result = []
        for ticker in self.universe:
            if ticker in self.prices:
                px = self.prices[ticker]
                ret_1y = float((px.iloc[-1] / px.iloc[-252] - 1) * 100) if len(px) >= 252 else None
                vol = float(self.returns.get(ticker, pd.Series()).std() * np.sqrt(252) * 100) if ticker in self.returns else None
                result.append({
                    "ticker": ticker,
                    "price": round(float(px.iloc[-1]), 2),
                    "return_1y": round(ret_1y, 1) if ret_1y else None,
                    "volatility": round(vol, 1) if vol else None,
                    "market_cap": self.market_caps.get(ticker),
                })
        return result

    @property
    def equity_universe(self) -> List[str]:
        """Non-ETF tickers with price data."""
        etfs = {"SPY","QQQ","IWM","AGG","TLT","GLD","VTV","VUG","VBR","VBK"}
        return [t for t in self.universe if t not in etfs and t in self.prices]

    def get_returns_matrix(self, tickers: Optional[List[str]] = None, lookback: int = 252) -> pd.DataFrame:
        """Wide returns matrix: dates × tickers."""
        tickers = tickers or self.equity_universe
        series = {}
        for t in tickers:
            if t in self.returns:
                series[t] = self.returns[t].iloc[-lookback:]
        if not series:
            return pd.DataFrame()
        return pd.DataFrame(series).dropna(how="all")
