import { useState, useEffect, useCallback } from "react";

const API_BASE = import.meta.env?.VITE_API_URL || "http://localhost:8000";

// ═══════════════════════════════════════════════════════════════════════════
// QUANT ALPHA FOUNDRY — Institutional-Grade Alpha Research & Execution Platform
// ═══════════════════════════════════════════════════════════════════════════

// ── SEEDED PRNG for deterministic "live" data ──────────────────────────────
function mulberry32(seed) {
  return function() {
    seed |= 0; seed = seed + 0x6D2B79F5 | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
const rng = mulberry32(0xdeadbeef);
const rn = () => rng();
const rnRange = (a, b) => a + (b - a) * rn();
const rnNorm = () => { let u = 0, v = 0; while (!u) u = rn(); while (!v) v = rn(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };

// ── SIGNAL UNIVERSE ─────────────────────────────────────────────────────────
const SIGNALS = [
  { id: "MOM12_1",   name: "12-1 Momentum",        category: "Momentum",   description: "12-month return skipping last month. Classic Jegadeesh-Titman (1993)." },
  { id: "STREV",     name: "Short-Term Reversal",   category: "Reversal",   description: "1-week return reversal. Microstructure-driven mean reversion." },
  { id: "VAL_BM",    name: "Book-to-Market",         category: "Value",      description: "Fama-French value factor. High BtM stocks historically outperform." },
  { id: "VAL_EP",    name: "Earnings Yield",         category: "Value",      description: "E/P ratio. Earnings yield as cheapness metric." },
  { id: "QUAL_ROE",  name: "Return on Equity",       category: "Quality",    description: "High ROE firms. Quality factor with risk-based and behavioral explanations." },
  { id: "QUAL_GP",   name: "Gross Profitability",    category: "Quality",    description: "Novy-Marx (2013) gross profit factor. Orthogonal to value." },
  { id: "LOW_VOL",   name: "Low Volatility",         category: "Risk",       description: "Low realized vol stocks outperform on risk-adjusted basis. Volatility anomaly." },
  { id: "LOW_BETA",  name: "Low Beta",               category: "Risk",       description: "Security market line flatter than CAPM predicts. Betting against beta." },
  { id: "EARN_REV",  name: "Earnings Revision",      category: "Sentiment",  description: "Analyst estimate revisions. Forecast drift captures delayed reaction." },
  { id: "SHORT_INT", name: "Short Interest",         category: "Sentiment",  description: "High short interest predicts negative returns. Informed short sellers." },
  { id: "ACCRUAL",   name: "Accruals",               category: "Accounting", description: "Low accruals predict higher returns. Sloan (1996) accrual anomaly." },
  { id: "INV_GROW",  name: "Investment Growth",      category: "Accounting", description: "Low asset growth predicts outperformance. Over-investment destruction." },
  { id: "COMBO_QVM", name: "Quality-Value-Momentum", category: "Composite",  description: "Equal-weighted composite of QVM signals. Diversification across factors." },
  { id: "ML_GBDT",   name: "ML Gradient Boost",      category: "ML",         description: "XGBoost trained on 40+ features with walk-forward retrain every quarter." },
  { id: "NLP_EARN",  name: "Earnings NLP",           category: "ML",         description: "FinBERT sentiment on earnings calls. Q&A tone vs prepared remarks delta." },
];

// ── REGIME DEFINITIONS ───────────────────────────────────────────────────────
const REGIMES = [
  { id: "bull",    name: "Bull Market",    color: "#4ade80", desc: "Trending up, low vol" },
  { id: "bear",    name: "Bear Market",    color: "#f87171", desc: "Trending down, high vol" },
  { id: "crisis",  name: "Crisis",         color: "#c084fc", desc: "Extreme vol, correlation spike" },
  { id: "range",   name: "Range-Bound",    color: "#facc15", desc: "Low vol, mean-reverting" },
  { id: "inflate", name: "Inflationary",   color: "#fb923c", desc: "Rising rates, commodity-driven" },
];

// ── GENERATE REALISTIC SIGNAL METRICS ────────────────────────────────────────
function generateSignalMetrics(signalId) {
  const seed = signalId.split("").reduce((a, c) => a + c.charCodeAt(0), 0);
  const r = mulberry32(seed);
  const nn = () => { let u=0,v=0; while(!u) u=r(); while(!v) v=r(); return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v); };

  const baseIC = { MOM12_1: 0.042, STREV: 0.038, VAL_BM: 0.028, VAL_EP: 0.031,
    QUAL_ROE: 0.035, QUAL_GP: 0.033, LOW_VOL: 0.029, LOW_BETA: 0.027,
    EARN_REV: 0.051, SHORT_INT: 0.044, ACCRUAL: 0.026, INV_GROW: 0.024,
    COMBO_QVM: 0.048, ML_GBDT: 0.062, NLP_EARN: 0.055 }[signalId] || 0.03;

  const ic = baseIC + nn() * 0.008;
  const icir = ic / (0.08 + r() * 0.04);
  const annualIR = icir * Math.sqrt(252);
  const turnover = 0.2 + r() * 0.6;
  const grossSharpe = 0.6 + r() * 0.8;
  const tcCost = turnover * 0.001;
  const netSharpe = grossSharpe - tcCost * 4;
  const maxDD = -(0.08 + r() * 0.15);
  const calmar = netSharpe > 0 ? netSharpe / Math.abs(maxDD) : 0;
  const winRate = 0.50 + ic * 3 + nn() * 0.02;
  const hitRate = 0.48 + ic * 2;
  const capacity = Math.floor(rnRange(50, 2000));

  // Regime performance
  const regimeIC = {};
  REGIMES.forEach(reg => {
    const base = { bull: 1.1, bear: 0.7, crisis: 0.4, range: 1.2, inflate: 0.9 }[reg.id] || 1;
    regimeIC[reg.id] = (ic * base + nn() * 0.01).toFixed(4);
  });

  // Walk-forward years
  const wfYears = [];
  const baseYear = 2014;
  let cumPnL = 0;
  for (let y = 0; y < 10; y++) {
    const yr = baseYear + y;
    const regime = REGIMES[Math.floor(r() * REGIMES.length)].id;
    const ann = ic * 30 + nn() * 8 + (regime === "crisis" ? -5 : regime === "bull" ? 3 : 0);
    cumPnL += ann;
    wfYears.push({ year: yr, ic: (ic + nn() * 0.01).toFixed(3), annReturn: ann.toFixed(1), cumPnL: cumPnL.toFixed(1), regime });
  }

  // Decay curve
  const decay = [];
  for (let lag = 1; lag <= 21; lag++) {
    decay.push({ lag, ic: Math.max(0, ic * Math.exp(-lag / 8) + nn() * 0.003) });
  }

  // Distribution
  const returns = Array.from({ length: 60 }, (_, i) => ({
    month: i + 1, ret: ic * 2 + nn() * 3,
    long: ic * 3 + nn() * 2,
    short: -ic * 1.5 + nn() * 2.5,
  }));

  // Promotions
  const promoted = netSharpe > 0.5 && Math.abs(ic) > 0.025 && icir > 0.4;

  return {
    ic: ic.toFixed(4),
    icir: icir.toFixed(3),
    annualIR: annualIR.toFixed(2),
    grossSharpe: grossSharpe.toFixed(2),
    netSharpe: netSharpe.toFixed(2),
    maxDD: (maxDD * 100).toFixed(1),
    calmar: calmar.toFixed(2),
    turnover: (turnover * 100).toFixed(0),
    winRate: (winRate * 100).toFixed(1),
    hitRate: (hitRate * 100).toFixed(1),
    capacity: `$${capacity}M`,
    tcCost: (tcCost * 100).toFixed(2),
    regimeIC,
    wfYears,
    decay,
    returns,
    promoted,
  };
}

// Pre-compute all signal metrics
const SIGNAL_METRICS_SIM = {};
SIGNALS.forEach(s => { SIGNAL_METRICS_SIM[s.id] = generateSignalMetrics(s.id); });

// ── GENERATE PRICE DATA ───────────────────────────────────────────────────────
function generatePriceSeries(n = 252) {
  const series = [100];
  const vol = 0.015;
  let trend = 0.0003;
  for (let i = 1; i < n; i++) {
    if (i % 60 === 0) trend = (rn() - 0.5) * 0.001;
    const ret = trend + rnNorm() * vol;
    series.push(series[i-1] * (1 + ret));
  }
  return series;
}

// ── EXECUTION SIMULATION ─────────────────────────────────────────────────────
function generateExecutionData() {
  const trades = [];
  const statuses = ["FILLED", "FILLED", "FILLED", "PARTIAL", "CANCELLED"];
  const tickers = ["AAPL","MSFT","GOOGL","AMZN","NVDA","META","BRK","JPM","XOM","JNJ","V","PG","MA","HD","CVX"];
  const sides = ["BUY","BUY","BUY","SELL","SELL"];
  for (let i = 0; i < 40; i++) {
    const side = sides[Math.floor(rn() * sides.length)];
    const qty = Math.floor(rnRange(100, 5000));
    const price = rnRange(50, 800);
    const impact = rnRange(0.01, 0.08);
    const spread = rnRange(0.01, 0.05);
    trades.push({
      id: `TRD-${String(1000 + i).padStart(4, "0")}`,
      ticker: tickers[Math.floor(rn() * tickers.length)],
      side,
      qty,
      price: price.toFixed(2),
      impact: impact.toFixed(3),
      spread: spread.toFixed(3),
      totalTc: ((impact + spread) * qty * price / 10000).toFixed(0),
      status: statuses[Math.floor(rn() * statuses.length)],
      vwapSlippage: (rnNorm() * 0.02).toFixed(4),
      time: `${String(9 + Math.floor(rn() * 6)).padStart(2,"0")}:${String(Math.floor(rn() * 60)).padStart(2,"0")}:${String(Math.floor(rn() * 60)).padStart(2,"0")}`,
    });
  }
  return trades;
}

const PORTFOLIO_PNL_SIM = generatePriceSeries(252);
const EXECUTION_TRADES   = generateExecutionData();
const SPY_BENCHMARK_SIM  = generatePriceSeries(252);

// ═══════════════════════════════════════════════════════════════════════════
// COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════

const VIEWS = ["FOUNDRY", "SIGNAL LAB", "STRESS TEST", "EXECUTION", "PORTFOLIO", "AGENTS"];

function sparkColor(val) {
  if (val === undefined || val === null) return "#888";
  const n = parseFloat(val);
  if (isNaN(n)) return "#888";
  return n >= 0 ? "#4ade80" : "#f87171";
}

function Badge({ text, color }) {
  return (
    <span style={{
      display: "inline-block", padding: "2px 10px", borderRadius: 2,
      background: color + "20", color, border: `1px solid ${color}44`,
      fontFamily: "JetBrains Mono, monospace", fontSize: 10, letterSpacing: "0.1em",
    }}>{text}</span>
  );
}

function StatCard({ label, value, sub, color = "#c9a96e", size = "normal" }) {
  const big = size === "big";
  return (
    <div style={{
      background: "linear-gradient(135deg, rgba(16,22,32,0.95), rgba(10,14,22,0.98))",
      border: `1px solid ${color}25`, borderRadius: 4, padding: big ? "20px 24px" : "14px 18px",
      position: "relative", overflow: "hidden",
    }}>
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: 2,
        background: `linear-gradient(90deg, transparent, ${color}, transparent)`, opacity: 0.5,
      }}/>
      <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.45)", letterSpacing: "0.15em", marginBottom: 6 }}>{label.toUpperCase()}</div>
      <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: big ? 36 : 24, color, lineHeight: 1, marginBottom: sub ? 4 : 0 }}>{value}</div>
      {sub && <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.4)" }}>{sub}</div>}
    </div>
  );
}

function MiniSparkline({ data, color = "#c9a96e", height = 32 }) {
  if (!data || data.length < 2) return null;
  const w = 120, h = height;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * h}`).join(" ");
  const last = data[data.length - 1];
  const lx = w, ly = h - ((last - min) / range) * h;
  return (
    <svg width={w} height={h} style={{ overflow: "visible" }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" opacity="0.8"/>
      <circle cx={lx} cy={ly} r="3" fill={color}/>
    </svg>
  );
}

function ICBar({ value, max = 0.07 }) {
  const pct = Math.min(Math.abs(parseFloat(value)) / max * 100, 100);
  const col = parseFloat(value) > 0.035 ? "#4ade80" : parseFloat(value) > 0.025 ? "#facc15" : "#f87171";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 6, background: "rgba(255,255,255,0.06)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: col, borderRadius: 3, transition: "width 0.6s ease" }}/>
      </div>
      <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: col, minWidth: 50, textAlign: "right" }}>{value}</span>
    </div>
  );
}

function GaugeArc({ value, max, color, label }) {
  const pct = Math.min(value / max, 1);
  const angle = Math.max(pct * 180, 0.001);
  const r = 40, cx = 50, cy = 50;
  const startAngle = 180;
  const endAngle = 180 + angle;
  const toRad = (d) => (d * Math.PI) / 180;
  const sx = cx + r * Math.cos(toRad(startAngle));
  const sy = cy + r * Math.sin(toRad(startAngle));
  const ex = cx + r * Math.cos(toRad(endAngle));
  const ey = cy + r * Math.sin(toRad(endAngle));
  const largeArc = angle > 180 ? 1 : 0;
  return (
    <div style={{ textAlign: "center" }}>
      <svg width={100} height={60} viewBox="0 0 100 55" style={{ overflow: "visible" }}>
        <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="8" strokeLinecap="round"/>
        <path d={`M ${sx} ${sy} A ${r} ${r} 0 ${largeArc} 1 ${ex} ${ey}`} fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"/>
        <text x={cx} y={cy - 2} textAnchor="middle" fill={color} fontFamily="Bebas Neue, sans-serif" fontSize="16">{value.toFixed(2)}</text>
      </svg>
      <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 9, color: "rgba(232,224,208,0.45)", marginTop: -8 }}>{label}</div>
    </div>
  );
}

function ReturnChart({ data, height = 160 }) {
  const w = 100, h = height;
  const rets = data.map(d => parseFloat(d.ret));
  const min = Math.min(...rets) - 0.5;
  const max = Math.max(...rets) + 0.5;
  const range = max - min;
  const toY = v => h - ((v - min) / range) * h;
  const barW = w / rets.length;
  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <line x1="0" y1={toY(0)} x2={w} y2={toY(0)} stroke="rgba(255,255,255,0.15)" strokeWidth="0.5"/>
      {rets.map((v, i) => (
        <rect key={i} x={i * barW} y={v >= 0 ? toY(v) : toY(0)} width={barW * 0.7}
          height={Math.abs(toY(0) - toY(v))} fill={v >= 0 ? "#4ade8088" : "#f8717188"}/>
      ))}
    </svg>
  );
}

function DecayCurve({ decay }) {
  const w = 200, h = 80;
  const max = decay[0].ic || 1;
  const pts = decay.map((d, i) => `${(i / (decay.length - 1)) * w},${h - (d.ic / max) * h}`).join(" ");
  const halfLife = decay.find(d => d.ic < max * 0.5)?.lag || "∞";
  return (
    <div>
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ overflow: "visible", width: "100%" }}>
        <defs><linearGradient id="dcg" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor="#c9a96e"/><stop offset="100%" stopColor="#4ade80" stopOpacity="0.3"/></linearGradient></defs>
        <line x1="0" y1={h/2} x2={w} y2={h/2} stroke="rgba(255,255,255,0.06)" strokeWidth="1" strokeDasharray="4,4"/>
        <polyline points={pts} fill="none" stroke="url(#dcg)" strokeWidth="2"/>
        {decay.filter((_, i) => i % 5 === 0).map((d, i) => (
          <circle key={i} cx={(d.lag - 1) / (decay.length - 1) * w} cy={h - (d.ic / max) * h} r="2.5" fill="#c9a96e"/>
        ))}
      </svg>
      <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(201,169,110,0.6)", marginTop: 4 }}>
        Half-life: <span style={{ color: "#c9a96e" }}>~{halfLife} days</span>
      </div>
    </div>
  );
}

function EquityCurve({ pnl, benchmark, height = 200 }) {
  const w = 400, h = height;
  const allVals = [...pnl, ...benchmark];
  const min = Math.min(...allVals), max = Math.max(...allVals);
  const range = max - min;
  const toY = v => h - ((v - min) / range) * (h * 0.9) - h * 0.05;
  const toX = i => (i / (pnl.length - 1)) * w;
  const pnlPts = pnl.map((v, i) => `${toX(i)},${toY(v)}`).join(" ");
  const bPts = benchmark.map((v, i) => `${toX(i)},${toY(v)}`).join(" ");
  const pnlArea = `${toX(0)},${h} ${pnlPts} ${toX(pnl.length - 1)},${h}`;
  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ overflow: "visible" }}>
      <defs>
        <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#c9a96e" stopOpacity="0.3"/>
          <stop offset="100%" stopColor="#c9a96e" stopOpacity="0"/>
        </linearGradient>
      </defs>
      {[0.25, 0.5, 0.75].map(pct => (
        <line key={pct} x1="0" y1={h * pct} x2={w} y2={h * pct} stroke="rgba(255,255,255,0.04)" strokeWidth="1"/>
      ))}
      <polygon points={pnlArea} fill="url(#pnlGrad)"/>
      <polyline points={bPts} fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5" strokeDasharray="6,3"/>
      <polyline points={pnlPts} fill="none" stroke="#c9a96e" strokeWidth="2"/>
    </svg>
  );
}

function RegimeMatrix({ regimeIC }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
      {REGIMES.map(reg => {
        const ic = parseFloat(regimeIC[reg.id]);
        const pct = Math.min(Math.abs(ic) / 0.07 * 100, 100);
        return (
          <div key={reg.id} style={{
            background: "rgba(255,255,255,0.03)", borderRadius: 3, padding: "8px 10px",
            border: `1px solid ${reg.color}22`,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
              <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: reg.color }}>{reg.name}</span>
              <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: ic > 0.02 ? "#4ade80" : "#f87171" }}>{ic.toFixed(3)}</span>
            </div>
            <div style={{ height: 4, background: "rgba(255,255,255,0.06)", borderRadius: 2 }}>
              <div style={{ width: `${pct}%`, height: "100%", background: ic > 0.02 ? reg.color : "#f87171", borderRadius: 2 }}/>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// VIEWS
// ═══════════════════════════════════════════════════════════════════════════

function FoundryOverview({ onSelectSignal, metrics }) {
  const promoted = SIGNALS.filter(s => metrics[s.id].promoted);
  const review = SIGNALS.filter(s => !metrics[s.id].promoted);
  const totalIC = (SIGNALS.reduce((a, s) => a + parseFloat(metrics[s.id].ic), 0) / SIGNALS.length).toFixed(4);
  const avgNetSharpe = (promoted.reduce((a, s) => a + parseFloat(metrics[s.id].netSharpe), 0) / promoted.length).toFixed(2);

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1400, margin: "0 auto" }}>
      {/* KPI Strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 12, marginBottom: 32 }}>
        <StatCard label="Signals Researched" value={SIGNALS.length} sub="Active universe" size="normal"/>
        <StatCard label="Promoted" value={promoted.length} sub="Pass all gates" color="#4ade80" size="normal"/>
        <StatCard label="In Review" value={review.length} sub="Needs work" color="#facc15" size="normal"/>
        <StatCard label="Avg IC" value={totalIC} sub="Universe mean" color="#c9a96e" size="normal"/>
        <StatCard label="Portfolio IR" value={avgNetSharpe} sub="Net of TC" color="#4ade80" size="normal"/>
        <StatCard label="Capacity" value="$2.4B" sub="Aggregate AUM" color="#c084fc" size="normal"/>
      </div>

      {/* Signal Pipeline */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 28 }}>
        {/* Promoted Signals */}
        <div style={{ background: "rgba(12,18,28,0.95)", border: "1px solid rgba(74,222,128,0.2)", borderRadius: 6, padding: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 18, color: "#4ade80", letterSpacing: "0.08em" }}>PROMOTED SIGNALS</div>
            <Badge text="LIVE" color="#4ade80"/>
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {promoted.map(s => {
              const m = metrics[s.id];
              return (
                <div key={s.id} onClick={() => onSelectSignal(s)}
                  style={{
                    display: "grid", gridTemplateColumns: "1fr auto auto auto", gap: 12, alignItems: "center",
                    padding: "10px 14px", background: "rgba(74,222,128,0.04)", borderRadius: 3,
                    border: "1px solid rgba(74,222,128,0.12)", cursor: "pointer", transition: "all 0.2s",
                  }}
                  onMouseEnter={e => e.currentTarget.style.borderColor = "rgba(74,222,128,0.35)"}
                  onMouseLeave={e => e.currentTarget.style.borderColor = "rgba(74,222,128,0.12)"}
                >
                  <div>
                    <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 12, color: "#e8e0d0" }}>{s.name}</div>
                    <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.4)" }}>{s.category}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "#c9a96e" }}>IC {m.ic}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "#4ade80" }}>SR {m.netSharpe}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "#c084fc" }}>{m.capacity}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Under Review */}
        <div style={{ background: "rgba(12,18,28,0.95)", border: "1px solid rgba(250,204,21,0.2)", borderRadius: 6, padding: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 18, color: "#facc15", letterSpacing: "0.08em" }}>UNDER REVIEW</div>
            <Badge text="RESEARCH" color="#facc15"/>
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {review.map(s => {
              const m = metrics[s.id];
              const issues = [];
              if (parseFloat(m.ic) < 0.025) issues.push("LOW IC");
              if (parseFloat(m.netSharpe) < 0.5) issues.push("TC DRAG");
              if (parseFloat(m.icir) < 0.4) issues.push("UNSTABLE");
              return (
                <div key={s.id} onClick={() => onSelectSignal(s)}
                  style={{
                    display: "grid", gridTemplateColumns: "1fr auto auto", gap: 12, alignItems: "center",
                    padding: "10px 14px", background: "rgba(250,204,21,0.03)", borderRadius: 3,
                    border: "1px solid rgba(250,204,21,0.1)", cursor: "pointer", transition: "all 0.2s",
                  }}
                  onMouseEnter={e => e.currentTarget.style.borderColor = "rgba(250,204,21,0.3)"}
                  onMouseLeave={e => e.currentTarget.style.borderColor = "rgba(250,204,21,0.1)"}
                >
                  <div>
                    <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 12, color: "#e8e0d0" }}>{s.name}</div>
                    <div style={{ display: "flex", gap: 4, marginTop: 3, flexWrap: "wrap" }}>
                      {issues.map(iss => <Badge key={iss} text={iss} color="#f87171"/>)}
                      {issues.length === 0 && <Badge text="BORDERLINE" color="#facc15"/>}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "#c9a96e" }}>IC {m.ic}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: parseFloat(m.netSharpe) > 0 ? "#facc15" : "#f87171" }}>SR {m.netSharpe}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* IC Universe Heatmap */}
      <div style={{ background: "rgba(12,18,28,0.95)", border: "1px solid rgba(201,169,110,0.15)", borderRadius: 6, padding: 20, marginBottom: 20 }}>
        <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 18, color: "#c9a96e", letterSpacing: "0.08em", marginBottom: 16 }}>SIGNAL UNIVERSE — IC RANKING</div>
        <div style={{ display: "grid", gap: 8 }}>
          {[...SIGNALS].sort((a, b) => parseFloat(metrics[b.id].ic) - parseFloat(metrics[a.id].ic)).map((s, rank) => {
            const m = metrics[s.id];
            return (
              <div key={s.id} style={{ display: "grid", gridTemplateColumns: "24px 180px 1fr 80px 80px 80px 80px", gap: 12, alignItems: "center", padding: "8px 0" }}>
                <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.3)", textAlign: "right" }}>#{rank+1}</div>
                <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: m.promoted ? "#e8e0d0" : "rgba(232,224,208,0.5)", cursor: "pointer" }} onClick={() => onSelectSignal(s)}>{s.name}</div>
                <ICBar value={m.ic}/>
                <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.5)", textAlign: "right" }}>ICIR {m.icir}</div>
                <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: parseFloat(m.netSharpe) > 0.5 ? "#4ade80" : "#f87171", textAlign: "right" }}>SR {m.netSharpe}</div>
                <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.4)", textAlign: "right" }}>TO {m.turnover}%</div>
                <div style={{ textAlign: "right" }}><Badge text={m.promoted ? "LIVE" : "REVIEW"} color={m.promoted ? "#4ade80" : "#facc15"}/></div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function SignalLab({ signal, metrics }) {
  const m = metrics[signal.id];
  const pnlData = m.returns.map(d => parseFloat(d.ret));

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1400, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28 }}>
        <div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 6 }}>
            <h2 style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 32, color: "#c9a96e", letterSpacing: "0.05em", margin: 0 }}>{signal.name}</h2>
            <Badge text={signal.category} color="#c9a96e"/>
            <Badge text={m.promoted ? "PROMOTED" : "UNDER REVIEW"} color={m.promoted ? "#4ade80" : "#facc15"}/>
          </div>
          <p style={{ fontFamily: "Cormorant Garamond, serif", fontSize: 15, color: "rgba(232,224,208,0.6)", margin: 0, maxWidth: 600, lineHeight: 1.7 }}>{signal.description}</p>
        </div>
        <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(201,169,110,0.5)", textAlign: "right" }}>
          <div>ID: {signal.id}</div>
          <div>LAST UPDATED: {new Date().toLocaleDateString()}</div>
        </div>
      </div>

      {/* Core Metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 24 }}>
        <StatCard label="Information Coefficient" value={m.ic} sub="Mean IC (annualized)" color="#c9a96e" size="normal"/>
        <StatCard label="IC Information Ratio" value={m.icir} sub="IC / σ(IC)" color="#c9a96e" size="normal"/>
        <StatCard label="Gross Sharpe" value={m.grossSharpe} sub="Before TC" color="#4ade80" size="normal"/>
        <StatCard label="Net Sharpe" value={m.netSharpe} sub={`After ${m.tcCost}% TC`} color={parseFloat(m.netSharpe) > 0.5 ? "#4ade80" : "#f87171"} size="normal"/>
        <StatCard label="Max Drawdown" value={`${m.maxDD}%`} sub="Worst period" color="#f87171" size="normal"/>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 28 }}>
        <StatCard label="Annual Turnover" value={`${m.turnover}%`} sub="One-way" color="#c9a96e"/>
        <StatCard label="Win Rate" value={`${m.winRate}%`} sub="Long-side" color="#4ade80"/>
        <StatCard label="Hit Rate" value={`${m.hitRate}%`} sub="Long-short" color="#c9a96e"/>
        <StatCard label="Capacity" value={m.capacity} sub="Estimated AUM cap" color="#c084fc"/>
        <StatCard label="Calmar Ratio" value={m.calmar} sub="SR / |MaxDD|" color={parseFloat(m.calmar) > 1 ? "#4ade80" : "#facc15"}/>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
        {/* Walk-Forward Performance */}
        <div style={{ background: "rgba(12,18,28,0.95)", border: "1px solid rgba(201,169,110,0.15)", borderRadius: 6, padding: 20 }}>
          <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 16, color: "#c9a96e", letterSpacing: "0.08em", marginBottom: 14 }}>WALK-FORWARD ANALYSIS (10Y OOS)</div>
          <div style={{ display: "grid", gap: 6 }}>
            <div style={{ display: "grid", gridTemplateColumns: "60px 70px 80px 80px 80px", gap: 8, marginBottom: 4 }}>
              {["YEAR","IC","ANN RET %","CUM RET %","REGIME"].map(h => (
                <div key={h} style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 9, color: "rgba(232,224,208,0.35)", letterSpacing: "0.1em" }}>{h}</div>
              ))}
            </div>
            {m.wfYears.map(y => {
              const reg = REGIMES.find(r => r.id === y.regime);
              return (
                <div key={y.year} style={{ display: "grid", gridTemplateColumns: "60px 70px 80px 80px 80px", gap: 8, alignItems: "center", padding: "4px 0", borderTop: "1px solid rgba(255,255,255,0.04)" }}>
                  <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "#e8e0d0" }}>{y.year}</div>
                  <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "#c9a96e" }}>{y.ic}</div>
                  <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: parseFloat(y.annReturn) > 0 ? "#4ade80" : "#f87171" }}>{parseFloat(y.annReturn) > 0 ? "+" : ""}{y.annReturn}%</div>
                  <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: parseFloat(y.cumPnL) > 0 ? "#4ade80" : "#f87171" }}>{y.cumPnL}%</div>
                  <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 9, color: reg?.color }}>{reg?.name}</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Signal Decay + Regime Matrix */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ background: "rgba(12,18,28,0.95)", border: "1px solid rgba(201,169,110,0.15)", borderRadius: 6, padding: 20 }}>
            <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 16, color: "#c9a96e", letterSpacing: "0.08em", marginBottom: 12 }}>SIGNAL DECAY CURVE</div>
            <DecayCurve decay={m.decay}/>
          </div>
          <div style={{ background: "rgba(12,18,28,0.95)", border: "1px solid rgba(201,169,110,0.15)", borderRadius: 6, padding: 20 }}>
            <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 16, color: "#c9a96e", letterSpacing: "0.08em", marginBottom: 12 }}>REGIME PERFORMANCE</div>
            <RegimeMatrix regimeIC={m.regimeIC}/>
          </div>
        </div>
      </div>

      {/* Monthly Returns Bar Chart */}
      <div style={{ background: "rgba(12,18,28,0.95)", border: "1px solid rgba(201,169,110,0.15)", borderRadius: 6, padding: 20 }}>
        <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 16, color: "#c9a96e", letterSpacing: "0.08em", marginBottom: 12 }}>MONTHLY RETURNS DISTRIBUTION</div>
        <ReturnChart data={m.returns} height={120}/>
        <div style={{ display: "flex", gap: 24, marginTop: 8 }}>
          <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.4)" }}>
            Positive months: <span style={{ color: "#4ade80" }}>{m.returns.filter(d => parseFloat(d.ret) > 0).length}/60</span>
          </div>
          <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.4)" }}>
            Best month: <span style={{ color: "#4ade80" }}>+{Math.max(...m.returns.map(d => parseFloat(d.ret))).toFixed(2)}%</span>
          </div>
          <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.4)" }}>
            Worst month: <span style={{ color: "#f87171" }}>{Math.min(...m.returns.map(d => parseFloat(d.ret))).toFixed(2)}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function StressTest({ metrics, macroSignals }) {
  const [activeRegime, setActiveRegime] = useState("crisis");
  const reg = REGIMES.find(r => r.id === activeRegime);
  return (
    <div style={{ padding: "32px 40px", maxWidth: 1400, margin: "0 auto" }}>
      <div style={{ marginBottom: 28 }}>
        <h2 style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 28, color: "#c9a96e", letterSpacing: "0.05em", marginBottom: 6 }}>REGIME STRESS TEST ENGINE</h2>
        <p style={{ fontFamily: "Cormorant Garamond, serif", fontSize: 15, color: "rgba(232,224,208,0.5)", margin: 0 }}>
          Evaluate every signal across 5 market regimes. Identify regime-conditional failure modes before deployment.
        </p>
      </div>

      {/* Regime Selector */}
      <div style={{ display: "flex", gap: 10, marginBottom: 28, flexWrap: "wrap" }}>
        {REGIMES.map(r => (
          <button key={r.id} onClick={() => setActiveRegime(r.id)} style={{
            padding: "10px 20px", borderRadius: 3,
            background: activeRegime === r.id ? r.color + "22" : "rgba(255,255,255,0.03)",
            border: `1px solid ${activeRegime === r.id ? r.color : "rgba(255,255,255,0.1)"}`,
            color: activeRegime === r.id ? r.color : "rgba(232,224,208,0.5)",
            fontFamily: "JetBrains Mono, monospace", fontSize: 11, letterSpacing: "0.1em",
            cursor: "pointer", transition: "all 0.2s",
          }}>
            <div>{r.name.toUpperCase()}</div>
            <div style={{ fontSize: 9, opacity: 0.6, marginTop: 2 }}>{r.desc}</div>
          </button>
        ))}
      </div>

      {/* Heatmap Grid */}
      <div style={{ background: "rgba(12,18,28,0.95)", border: `1px solid ${reg.color}25`, borderRadius: 6, padding: 20, marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 18, color: reg.color, letterSpacing: "0.08em" }}>
            SIGNAL PERFORMANCE · {reg.name.toUpperCase()}
          </div>
          <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.4)" }}>{reg.desc}</div>
        </div>
        <div style={{ display: "grid", gap: 0 }}>
          <div style={{ display: "grid", gridTemplateColumns: "200px repeat(5, 1fr) 80px 80px", gap: 12, padding: "0 0 8px 0", borderBottom: "1px solid rgba(255,255,255,0.06)", marginBottom: 8 }}>
            {["SIGNAL", ...REGIMES.map(r => r.name), "WORST", "BEST"].map(h => (
              <div key={h} style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 9, color: "rgba(232,224,208,0.35)", letterSpacing: "0.08em" }}>{h.toUpperCase()}</div>
            ))}
          </div>
          {SIGNALS.map(s => {
            const m = metrics[s.id];
            const regVals = REGIMES.map(r => parseFloat(m.regimeIC[r.id]));
            const worst = Math.min(...regVals).toFixed(3);
            const best = Math.max(...regVals).toFixed(3);
            return (
              <div key={s.id} style={{
                display: "grid", gridTemplateColumns: "200px repeat(5, 1fr) 80px 80px",
                gap: 12, alignItems: "center", padding: "8px 0",
                borderBottom: "1px solid rgba(255,255,255,0.03)",
                background: s.id === activeRegime ? "rgba(255,255,255,0.02)" : "transparent",
              }}>
                <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "#e8e0d0" }}>{s.name}</div>
                {REGIMES.map(r => {
                  const ic = parseFloat(m.regimeIC[r.id]);
                  const isActive = r.id === activeRegime;
                  const bg = ic > 0.04 ? "#4ade8033" : ic > 0.025 ? "#facc1522" : ic > 0 ? "#f8717122" : "#c084fc22";
                  const col = ic > 0.04 ? "#4ade80" : ic > 0.025 ? "#facc15" : ic > 0 ? "#f87171" : "#c084fc";
                  return (
                    <div key={r.id} style={{
                      background: bg,
                      border: `1px solid ${isActive ? r.color + "66" : "transparent"}`,
                      borderRadius: 2, padding: "3px 6px", textAlign: "center",
                      fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: col,
                    }}>{ic.toFixed(3)}</div>
                  );
                })}
                <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "#f87171", textAlign: "right" }}>{worst}</div>
                <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "#4ade80", textAlign: "right" }}>{best}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Correlation matrix placeholder */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <div style={{ background: "rgba(12,18,28,0.95)", border: "1px solid rgba(201,169,110,0.15)", borderRadius: 6, padding: 20 }}>
          <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 16, color: "#c9a96e", letterSpacing: "0.08em", marginBottom: 14 }}>REGIME CLASSIFICATION MODEL</div>
          <div style={{ display: "grid", gap: 10 }}>
            {[
              { name: "HMM (3-State)", acc: "78.3%", status: "PRIMARY" },
              { name: "Volatility Regime", acc: "71.2%", status: "SECONDARY" },
              { name: "Trend Filter (200MA)", acc: "65.8%", status: "TERTIARY" },
              { name: "Macro Composite", acc: "73.1%", status: "OVERLAY" },
            ].map(m => (
              <div key={m.name} style={{ display: "flex", justifyContent: "space-between", padding: "8px 10px", background: "rgba(255,255,255,0.03)", borderRadius: 3, border: "1px solid rgba(255,255,255,0.05)" }}>
                <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 12, color: "#e8e0d0" }}>{m.name}</span>
                <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                  <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "#4ade80" }}>{m.acc}</span>
                  <Badge text={m.status} color="#c9a96e"/>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div style={{ background: "rgba(12,18,28,0.95)", border: "1px solid rgba(201,169,110,0.15)", borderRadius: 6, padding: 20 }}>
          <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 16, color: "#c9a96e", letterSpacing: "0.08em", marginBottom: 14 }}>PROMOTION GATES</div>
          <div style={{ display: "grid", gap: 8 }}>
            {[
              { gate: "Min IC > 0.025", threshold: "0.025", weight: "Hard" },
              { gate: "ICIR > 0.40", threshold: "0.40", weight: "Hard" },
              { gate: "Net Sharpe > 0.50", threshold: "0.50", weight: "Hard" },
              { gate: "No regime IC < -0.01", threshold: "-0.01", weight: "Soft" },
              { gate: "TC-adjusted capacity > $50M", threshold: "$50M", weight: "Soft" },
              { gate: "Walk-forward win rate > 60%", threshold: "60%", weight: "Hard" },
            ].map(g => (
              <div key={g.gate} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 0", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "rgba(232,224,208,0.7)" }}>{g.gate}</span>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "#c9a96e" }}>{g.threshold}</span>
                  <Badge text={g.weight} color={g.weight === "Hard" ? "#f87171" : "#facc15"}/>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Live FRED Macro Signals — shown only when backend is running */}
      {macroSignals && (() => {
        const macroItems = [
          macroSignals.yield_curve,
          macroSignals.credit_spreads,
          macroSignals.volatility,
          macroSignals.monetary_policy,
          macroSignals.inflation,
          macroSignals.financial_conditions,
        ].filter(Boolean);
        if (!macroItems.length) return null;
        return (
          <div style={{ background: "rgba(12,18,28,0.95)", border: "1px solid rgba(201,169,110,0.15)", borderRadius: 6, padding: 20, marginTop: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 18, color: "#c9a96e", letterSpacing: "0.08em" }}>LIVE MACRO SIGNALS — FRED</div>
              <Badge text="LIVE · NO API KEY" color="#4ade80"/>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
              {macroItems.map((m, i) => (
                <div key={i} style={{ background: "rgba(255,255,255,0.03)", border: `1px solid ${m.color || "#c9a96e"}22`, borderRadius: 4, padding: "12px 14px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                    <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.5)" }}>{m.name || m.series_id}</span>
                    <Badge text={m.signal || "—"} color={m.color || "#c9a96e"}/>
                  </div>
                  <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 22, color: m.color || "#c9a96e" }}>{m.value ?? "—"}</div>
                  <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.4)", marginTop: 4, lineHeight: 1.5 }}>{m.description?.slice(0, 90)}</div>
                </div>
              ))}
            </div>
          </div>
        );
      })()}
    </div>
  );
}

function ExecutionDashboard() {
  const [filter, setFilter] = useState("ALL");
  const trades = filter === "ALL" ? EXECUTION_TRADES : EXECUTION_TRADES.filter(t => t.status === filter);
  const totalTC = EXECUTION_TRADES.reduce((a, t) => a + parseFloat(t.totalTc), 0);
  const avgSlippage = (EXECUTION_TRADES.reduce((a, t) => a + Math.abs(parseFloat(t.vwapSlippage)), 0) / EXECUTION_TRADES.length * 100).toFixed(4);
  const fillRate = (EXECUTION_TRADES.filter(t => t.status === "FILLED").length / EXECUTION_TRADES.length * 100).toFixed(1);
  return (
    <div style={{ padding: "32px 40px", maxWidth: 1400, margin: "0 auto" }}>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 28, color: "#c9a96e", letterSpacing: "0.05em", marginBottom: 4 }}>EXECUTION ANALYTICS</h2>
        <p style={{ fontFamily: "Cormorant Garamond, serif", fontSize: 15, color: "rgba(232,224,208,0.5)", margin: 0 }}>
          Real-time trade blotter, market impact attribution, and cost decomposition.
        </p>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 24 }}>
        <StatCard label="Total Trades" value={EXECUTION_TRADES.length} sub="Today's blotter" color="#c9a96e"/>
        <StatCard label="Fill Rate" value={`${fillRate}%`} sub="Fully filled" color="#4ade80"/>
        <StatCard label="Total TC" value={`$${Math.floor(totalTC).toLocaleString()}`} sub="Bps drag" color="#f87171"/>
        <StatCard label="Avg Slippage" value={`${avgSlippage}%`} sub="vs VWAP" color="#facc15"/>
        <StatCard label="Notional" value="$84.2M" sub="Today's volume" color="#c084fc"/>
      </div>

      {/* Algo split */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 24 }}>
        {[
          { algo: "VWAP", pct: 42, fills: 17, tc: "4.2 bps", color: "#4ade80" },
          { algo: "TWAP", pct: 28, fills: 11, tc: "5.1 bps", color: "#c9a96e" },
          { algo: "IS (Implementation Shortfall)", pct: 30, fills: 12, tc: "3.8 bps", color: "#c084fc" },
        ].map(a => (
          <div key={a.algo} style={{ background: "rgba(12,18,28,0.95)", border: `1px solid ${a.color}22`, borderRadius: 6, padding: 16 }}>
            <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 16, color: a.color, letterSpacing: "0.08em", marginBottom: 10 }}>{a.algo}</div>
            <div style={{ height: 6, background: "rgba(255,255,255,0.06)", borderRadius: 3, marginBottom: 10 }}>
              <div style={{ width: `${a.pct}%`, height: "100%", background: a.color, borderRadius: 3 }}/>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "rgba(232,224,208,0.5)" }}>{a.pct}% of flow · {a.fills} trades</div>
              <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "#c9a96e" }}>{a.tc}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Trade Blotter */}
      <div style={{ background: "rgba(12,18,28,0.95)", border: "1px solid rgba(201,169,110,0.15)", borderRadius: 6, padding: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 18, color: "#c9a96e", letterSpacing: "0.08em" }}>TRADE BLOTTER</div>
          <div style={{ display: "flex", gap: 8 }}>
            {["ALL", "FILLED", "PARTIAL", "CANCELLED"].map(f => (
              <button key={f} onClick={() => setFilter(f)} style={{
                padding: "4px 12px", borderRadius: 2, border: `1px solid ${filter === f ? "#c9a96e" : "rgba(255,255,255,0.1)"}`,
                background: filter === f ? "rgba(201,169,110,0.12)" : "transparent",
                color: filter === f ? "#c9a96e" : "rgba(232,224,208,0.4)",
                fontFamily: "JetBrains Mono, monospace", fontSize: 10, cursor: "pointer",
              }}>{f}</button>
            ))}
          </div>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
                {["TIME","ID","TICKER","SIDE","QTY","PRICE","IMPACT","SPREAD","TC ($)","VWAP SLIP","STATUS"].map(h => (
                  <th key={h} style={{ padding: "6px 12px", textAlign: "left", color: "rgba(232,224,208,0.35)", fontSize: 9, letterSpacing: "0.1em", fontWeight: "normal" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trades.slice(0, 20).map(t => {
                const statusCol = { FILLED: "#4ade80", PARTIAL: "#facc15", CANCELLED: "#f87171" }[t.status];
                const sideCol = t.side === "BUY" ? "#4ade80" : "#f87171";
                return (
                  <tr key={t.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}
                    onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.02)"}
                    onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                    <td style={{ padding: "8px 12px", color: "rgba(232,224,208,0.4)" }}>{t.time}</td>
                    <td style={{ padding: "8px 12px", color: "rgba(232,224,208,0.5)" }}>{t.id}</td>
                    <td style={{ padding: "8px 12px", color: "#e8e0d0" }}>{t.ticker}</td>
                    <td style={{ padding: "8px 12px", color: sideCol }}>{t.side}</td>
                    <td style={{ padding: "8px 12px", color: "rgba(232,224,208,0.7)" }}>{t.qty.toLocaleString()}</td>
                    <td style={{ padding: "8px 12px", color: "rgba(232,224,208,0.7)" }}>${t.price}</td>
                    <td style={{ padding: "8px 12px", color: "#facc15" }}>{t.impact}%</td>
                    <td style={{ padding: "8px 12px", color: "rgba(232,224,208,0.5)" }}>{t.spread}%</td>
                    <td style={{ padding: "8px 12px", color: "#f87171" }}>${parseInt(t.totalTc).toLocaleString()}</td>
                    <td style={{ padding: "8px 12px", color: parseFloat(t.vwapSlippage) < 0 ? "#f87171" : "#4ade80" }}>{(parseFloat(t.vwapSlippage) * 100).toFixed(3)}%</td>
                    <td style={{ padding: "8px 12px" }}><Badge text={t.status} color={statusCol}/></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function PortfolioDashboard({ pnl, benchmark }) {
  const pnlChange = ((pnl[pnl.length - 1] - pnl[0]) / pnl[0] * 100).toFixed(2);
  const benchChange = ((benchmark[benchmark.length - 1] - benchmark[0]) / benchmark[0] * 100).toFixed(2);
  return (
    <div style={{ padding: "32px 40px", maxWidth: 1400, margin: "0 auto" }}>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 28, color: "#c9a96e", letterSpacing: "0.05em", marginBottom: 4 }}>PORTFOLIO ANALYTICS</h2>
        <p style={{ fontFamily: "Cormorant Garamond, serif", fontSize: 15, color: "rgba(232,224,208,0.5)", margin: 0 }}>
          Live portfolio performance, factor exposure attribution, and risk decomposition.
        </p>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 12, marginBottom: 24 }}>
        <StatCard label="Portfolio Return" value={`+${pnlChange}%`} sub="YTD" color="#4ade80"/>
        <StatCard label="Benchmark (SPY)" value={`+${benchChange}%`} sub="YTD" color="rgba(232,224,208,0.4)"/>
        <StatCard label="Alpha" value={`+${(parseFloat(pnlChange) - parseFloat(benchChange)).toFixed(2)}%`} sub="Excess return" color="#c9a96e"/>
        <StatCard label="Portfolio Sharpe" value="1.42" sub="Annualized" color="#4ade80"/>
        <StatCard label="Net Exposure" value="18%" sub="Long-short net" color="#c9a96e"/>
        <StatCard label="Gross Exposure" value="142%" sub="Long + Short" color="#facc15"/>
      </div>

      {/* Equity Curve */}
      <div style={{ background: "rgba(12,18,28,0.95)", border: "1px solid rgba(201,169,110,0.15)", borderRadius: 6, padding: 20, marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 18, color: "#c9a96e", letterSpacing: "0.08em" }}>EQUITY CURVE (1Y)</div>
          <div style={{ display: "flex", gap: 20, fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}>
            <span style={{ color: "#c9a96e" }}>— Portfolio (+{pnlChange}%)</span>
            <span style={{ color: "rgba(255,255,255,0.3)" }}>- - SPY (+{benchChange}%)</span>
          </div>
        </div>
        <EquityCurve pnl={pnl} benchmark={benchmark} height={200}/>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
        {/* Factor Attribution */}
        <div style={{ background: "rgba(12,18,28,0.95)", border: "1px solid rgba(201,169,110,0.15)", borderRadius: 6, padding: 20 }}>
          <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 16, color: "#c9a96e", letterSpacing: "0.08em", marginBottom: 14 }}>FACTOR ATTRIBUTION</div>
          <div style={{ display: "grid", gap: 8 }}>
            {[
              { factor: "Market (Beta)", contrib: "+4.2%", exposure: "0.12", color: "#4ade80" },
              { factor: "Momentum", contrib: "+3.8%", exposure: "0.31", color: "#4ade80" },
              { factor: "Value", contrib: "+2.1%", exposure: "0.22", color: "#4ade80" },
              { factor: "Quality", contrib: "+1.9%", exposure: "0.28", color: "#4ade80" },
              { factor: "Low Vol", contrib: "+0.8%", exposure: "0.15", color: "#facc15" },
              { factor: "Idiosyncratic", contrib: "+3.6%", exposure: "—", color: "#c084fc" },
              { factor: "Transaction Costs", contrib: "-2.4%", exposure: "—", color: "#f87171" },
            ].map(f => (
              <div key={f.factor} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "rgba(232,224,208,0.7)" }}>{f.factor}</span>
                <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                  <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.4)" }}>β={f.exposure}</span>
                  <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: f.color, minWidth: 50, textAlign: "right" }}>{f.contrib}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Risk Decomposition */}
        <div style={{ background: "rgba(12,18,28,0.95)", border: "1px solid rgba(201,169,110,0.15)", borderRadius: 6, padding: 20 }}>
          <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 16, color: "#c9a96e", letterSpacing: "0.08em", marginBottom: 14 }}>RISK DECOMPOSITION</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 16 }}>
            <GaugeArc value={1.42} max={3} color="#4ade80" label="Sharpe"/>
            <GaugeArc value={0.87} max={3} color="#c9a96e" label="Sortino"/>
            <GaugeArc value={2.31} max={4} color="#c084fc" label="Calmar"/>
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {[
              { label: "1D 99% VaR", value: "-$142K", color: "#f87171" },
              { label: "10D 99% CVaR", value: "-$891K", color: "#f87171" },
              { label: "Max Drawdown (YTD)", value: "-3.2%", color: "#facc15" },
              { label: "Volatility (Ann.)", value: "8.4%", color: "#c9a96e" },
              { label: "Tracking Error", value: "6.1%", color: "#c9a96e" },
              { label: "Beta to SPY", value: "0.12", color: "#4ade80" },
            ].map(r => (
              <div key={r.label} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0" }}>
                <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.5)" }}>{r.label}</span>
                <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: r.color }}>{r.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Top Holdings */}
      <div style={{ background: "rgba(12,18,28,0.95)", border: "1px solid rgba(201,169,110,0.15)", borderRadius: 6, padding: 20 }}>
        <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 16, color: "#c9a96e", letterSpacing: "0.08em", marginBottom: 14 }}>TOP POSITIONS</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8 }}>
          {[
            { ticker: "NVDA", side: "L", weight: "+3.8%", pnl: "+$124K", signal: "MOM+QUAL" },
            { ticker: "META", side: "L", weight: "+3.2%", pnl: "+$98K", signal: "MOM+NLP" },
            { ticker: "GOOGL", side: "L", weight: "+2.9%", pnl: "+$76K", signal: "VAL+QUAL" },
            { ticker: "XOM", side: "S", weight: "-2.1%", pnl: "+$54K", signal: "INV+ST" },
            { ticker: "INTC", side: "S", weight: "-1.8%", pnl: "+$41K", signal: "MOM+ACCRUAL" },
          ].map(p => (
            <div key={p.ticker} style={{
              background: p.side === "L" ? "rgba(74,222,128,0.05)" : "rgba(248,113,113,0.05)",
              border: `1px solid ${p.side === "L" ? "rgba(74,222,128,0.2)" : "rgba(248,113,113,0.2)"}`,
              borderRadius: 4, padding: 14,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 18, color: "#e8e0d0" }}>{p.ticker}</span>
                <Badge text={p.side === "L" ? "LONG" : "SHORT"} color={p.side === "L" ? "#4ade80" : "#f87171"}/>
              </div>
              <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 13, color: "#c9a96e", marginBottom: 2 }}>{p.weight}</div>
              <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 12, color: "#4ade80", marginBottom: 6 }}>{p.pnl}</div>
              <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 9, color: "rgba(232,224,208,0.35)" }}>{p.signal}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════════════════════════

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=JetBrains+Mono:wght@300;400;500&family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,400&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #070b12; color: #e8e0d0; font-family: 'Cormorant Garamond', serif; overflow-x: hidden; }
  ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-track { background: #0a0f18; } ::-webkit-scrollbar-thumb { background: #c9a96e55; border-radius: 2px; }
  button { cursor: pointer; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
  .fade-in { animation: fadeIn 0.4s ease forwards; }
  .live-dot { width: 6px; height: 6px; border-radius: 50%; background: #4ade80; animation: pulse 2s ease-in-out infinite; display: inline-block; margin-right: 6px; }
`;

// ─────────────────────────────────────────────────────────────────────────────
// AGENTS DASHBOARD
// ─────────────────────────────────────────────────────────────────────────────
function AgentsDashboard({ agentData, apiBase }) {
  const [runningJob, setRunningJob] = useState(null);
  const [localAgent, setLocalAgent] = useState(agentData);
  const [switchingMode, setSwitchingMode] = useState(false);
  const [modeSwitchMsg, setModeSwitchMsg] = useState(null);

  // Sync prop changes
  useEffect(() => { setLocalAgent(agentData); }, [agentData]);

  const exec      = localAgent?.execution;
  const sched     = localAgent?.scheduler;
  const commentary = localAgent?.commentary;

  // Current mode derived from backend state
  const currentMode = exec?.alpaca_mode === "PAPER" ? "paper" : "live";

  const switchMode = async (newMode) => {
    if (switchingMode) return;
    setSwitchingMode(true);
    setModeSwitchMsg(null);
    try {
      const r = await fetch(`${apiBase}/api/agents/execution/mode/${newMode}`, { method: "POST" });
      const data = await r.json();
      if (r.ok) {
        setModeSwitchMsg({ ok: true, text: `Switched to ${newMode.toUpperCase()} trading` });
        // Refresh agent state
        const s = await fetch(`${apiBase}/api/agents/execution/state`);
        if (s.ok) {
          const state = await s.json();
          setLocalAgent(prev => ({ ...prev, execution: state }));
        }
      } else {
        setModeSwitchMsg({ ok: false, text: data.detail || "Switch failed" });
      }
    } catch (e) {
      setModeSwitchMsg({ ok: false, text: "Backend unreachable" });
    }
    setSwitchingMode(false);
    setTimeout(() => setModeSwitchMsg(null), 4000);
  };

  const triggerJob = async (jobId) => {
    setRunningJob(jobId);
    try {
      await fetch(`${apiBase}/api/agents/scheduler/trigger/${jobId}`, { method: "POST" });
    } catch {}
    setTimeout(() => setRunningJob(null), 3000);
  };

  const triggerExecution = async () => {
    setRunningJob("execution");
    try { await fetch(`${apiBase}/api/agents/execution/run`, { method: "POST" }); } catch {}
    setTimeout(() => setRunningJob(null), 5000);
  };

  const triggerCommentary = async () => {
    setRunningJob("commentary");
    try { await fetch(`${apiBase}/api/agents/commentary/generate`, { method: "POST" }); } catch {}
    setTimeout(() => setRunningJob(null), 15000);
  };

  const mono = { fontFamily: "JetBrains Mono, monospace" };
  const card = { background: "rgba(12,18,28,0.95)", border: "1px solid rgba(201,169,110,0.15)", borderRadius: 6, padding: 20 };
  const sectionTitle = { fontFamily: "Bebas Neue, sans-serif", fontSize: 20, color: "#c9a96e", letterSpacing: "0.08em", marginBottom: 16 };

  const agentStatus = (status) => {
    const colors = { IDLE: "#4ade80", RUNNING: "#facc15", ERROR: "#f87171", CIRCUIT_BREAKER: "#f87171" };
    return <span style={{ ...mono, fontSize: 11, color: colors[status] || "rgba(232,224,208,0.5)", padding: "2px 8px", border: `1px solid ${colors[status] || "rgba(255,255,255,0.1)"}22`, borderRadius: 2 }}>{status || "UNKNOWN"}</span>;
  };

  const BtnRun = ({ label, onClick, active }) => (
    <button onClick={onClick} disabled={active} style={{
      padding: "6px 16px", borderRadius: 2,
      border: `1px solid ${active ? "rgba(201,169,110,0.3)" : "#c9a96e"}`,
      background: active ? "rgba(201,169,110,0.05)" : "rgba(201,169,110,0.12)",
      color: active ? "rgba(201,169,110,0.4)" : "#c9a96e",
      ...mono, fontSize: 11, cursor: active ? "wait" : "pointer", letterSpacing: "0.08em",
    }}>{active ? "RUNNING…" : label}</button>
  );

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1400, margin: "0 auto" }}>
      <div style={{ marginBottom: 28 }}>
        <h2 style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 28, color: "#c9a96e", letterSpacing: "0.05em", marginBottom: 4 }}>AUTONOMOUS AGENTS</h2>
        <p style={{ fontFamily: "Cormorant Garamond, serif", fontSize: 15, color: "rgba(232,224,208,0.5)", margin: 0 }}>
          Execution bot · AI commentary engine · Background data scheduler
        </p>
        {!localAgent && (
          <div style={{ marginTop: 12, padding: "10px 16px", background: "rgba(248,113,113,0.08)", border: "1px solid rgba(248,113,113,0.2)", borderRadius: 4, ...mono, fontSize: 11, color: "rgba(248,113,113,0.8)" }}>
            ⚠ Backend not connected — start the backend to activate agents
          </div>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>

        {/* ── Execution Agent ── */}
        <div style={card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div style={sectionTitle}>⚡ EXECUTION AGENT</div>
            {exec && agentStatus(exec.status)}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 16 }}>
            {[
              { label: "Mode",       value: exec?.mode || "—" },
              { label: "NAV",        value: exec ? `$${(exec.nav || 0).toLocaleString(undefined, {maximumFractionDigits:0})}` : "—" },
              { label: "Return",     value: exec ? `${exec.total_return >= 0 ? "+" : ""}${(exec.total_return || 0).toFixed(2)}%` : "—",
                                     color: exec?.total_return >= 0 ? "#4ade80" : "#f87171" },
              { label: "Positions",  value: exec?.n_positions ?? "—" },
              { label: "Trades",     value: exec?.n_trades ?? "—" },
              { label: "Alpaca",     value: exec?.alpaca_enabled ? "CONNECTED" : "DISABLED",
                                     color: exec?.alpaca_enabled ? "#4ade80" : "rgba(232,224,208,0.35)" },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ background: "rgba(255,255,255,0.03)", borderRadius: 4, padding: "10px 14px" }}>
                <div style={{ ...mono, fontSize: 9, color: "rgba(232,224,208,0.35)", letterSpacing: "0.1em", marginBottom: 4 }}>{label}</div>
                <div style={{ ...mono, fontSize: 14, color: color || "rgba(232,224,208,0.85)" }}>{String(value)}</div>
              </div>
            ))}
          </div>
          {/* Positions mini-table */}
          {exec?.positions && Object.keys(exec.positions).length > 0 && (
            <div style={{ marginBottom: 14, overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", ...mono, fontSize: 10 }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                    {["TICKER","QTY","COST","LAST","P&L","RET%","SIGNAL"].map(h => (
                      <th key={h} style={{ padding: "4px 8px", textAlign: "left", color: "rgba(232,224,208,0.3)", fontSize: 9, fontWeight: "normal" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(exec.positions).slice(0, 8).map(([ticker, pos]) => (
                    <tr key={ticker} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                      <td style={{ padding: "5px 8px", color: "#c9a96e" }}>{ticker}</td>
                      <td style={{ padding: "5px 8px", color: "rgba(232,224,208,0.7)" }}>{pos.qty}</td>
                      <td style={{ padding: "5px 8px", color: "rgba(232,224,208,0.5)" }}>${pos.avg_cost?.toFixed(2)}</td>
                      <td style={{ padding: "5px 8px", color: "rgba(232,224,208,0.7)" }}>${pos.last_price?.toFixed(2)}</td>
                      <td style={{ padding: "5px 8px", color: pos.unrealized_pnl >= 0 ? "#4ade80" : "#f87171" }}>${pos.unrealized_pnl?.toFixed(0)}</td>
                      <td style={{ padding: "5px 8px", color: pos.return_pct >= 0 ? "#4ade80" : "#f87171" }}>{pos.return_pct?.toFixed(2)}%</td>
                      <td style={{ padding: "5px 8px", color: "rgba(201,169,110,0.6)", fontSize: 9 }}>{pos.signal}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div style={{ display: "flex", gap: 8 }}>
            <BtnRun label="RUN CYCLE" onClick={triggerExecution} active={runningJob === "execution"} />
          </div>

          {/* ── Trading Mode Toggle ── */}
          {exec?.alpaca_enabled && (
            <div style={{ marginTop: 16, padding: "14px 16px", background: "rgba(255,255,255,0.02)", border: "1px solid rgba(201,169,110,0.12)", borderRadius: 4 }}>
              <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 9, color: "rgba(232,224,208,0.4)", letterSpacing: "0.12em", marginBottom: 10 }}>TRADING MODE</div>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                {/* PAPER label */}
                <span style={{
                  fontFamily: "JetBrains Mono, monospace", fontSize: 11,
                  color: currentMode === "paper" ? "#4ade80" : "rgba(232,224,208,0.3)",
                  fontWeight: currentMode === "paper" ? "bold" : "normal",
                  transition: "color 0.3s",
                }}>PAPER</span>

                {/* Toggle pill */}
                <div
                  onClick={() => !switchingMode && switchMode(currentMode === "live" ? "paper" : "live")}
                  style={{
                    position: "relative", width: 44, height: 22, borderRadius: 11,
                    background: currentMode === "live"
                      ? "rgba(248,113,113,0.25)"
                      : "rgba(74,222,128,0.2)",
                    border: `1px solid ${currentMode === "live" ? "rgba(248,113,113,0.5)" : "rgba(74,222,128,0.4)"}`,
                    cursor: switchingMode ? "wait" : "pointer",
                    transition: "background 0.3s, border-color 0.3s",
                  }}
                >
                  <div style={{
                    position: "absolute", top: 2,
                    left: currentMode === "live" ? 22 : 2,
                    width: 16, height: 16, borderRadius: "50%",
                    background: currentMode === "live" ? "#f87171" : "#4ade80",
                    transition: "left 0.25s ease, background 0.3s",
                    boxShadow: `0 0 6px ${currentMode === "live" ? "rgba(248,113,113,0.6)" : "rgba(74,222,128,0.6)"}`,
                  }} />
                </div>

                {/* LIVE label */}
                <span style={{
                  fontFamily: "JetBrains Mono, monospace", fontSize: 11,
                  color: currentMode === "live" ? "#f87171" : "rgba(232,224,208,0.3)",
                  fontWeight: currentMode === "live" ? "bold" : "normal",
                  transition: "color 0.3s",
                }}>LIVE</span>

                {/* Status badge */}
                <span style={{
                  fontFamily: "JetBrains Mono, monospace", fontSize: 9,
                  padding: "3px 8px", borderRadius: 2,
                  background: currentMode === "live" ? "rgba(248,113,113,0.1)" : "rgba(74,222,128,0.1)",
                  border: `1px solid ${currentMode === "live" ? "rgba(248,113,113,0.3)" : "rgba(74,222,128,0.3)"}`,
                  color: currentMode === "live" ? "#f87171" : "#4ade80",
                  letterSpacing: "0.1em",
                }}>
                  {switchingMode ? "SWITCHING…" : currentMode === "live" ? "⚠ REAL MONEY" : "✓ SIMULATED"}
                </span>
              </div>

              {/* Feedback message */}
              {modeSwitchMsg && (
                <div style={{
                  marginTop: 8, fontFamily: "JetBrains Mono, monospace", fontSize: 10,
                  color: modeSwitchMsg.ok ? "#4ade80" : "#f87171",
                  padding: "6px 10px",
                  background: modeSwitchMsg.ok ? "rgba(74,222,128,0.07)" : "rgba(248,113,113,0.07)",
                  border: `1px solid ${modeSwitchMsg.ok ? "rgba(74,222,128,0.2)" : "rgba(248,113,113,0.2)"}`,
                  borderRadius: 3,
                }}>
                  {modeSwitchMsg.ok ? "✓" : "✗"} {modeSwitchMsg.text}
                </div>
              )}

              {/* Alpaca account info */}
              {exec?.alpaca_account && (
                <div style={{ marginTop: 10, display: "flex", gap: 16 }}>
                  {[
                    { label: "EQUITY",        value: `$${parseFloat(exec.alpaca_account.equity || 0).toLocaleString(undefined, {maximumFractionDigits:0})}` },
                    { label: "CASH",          value: `$${parseFloat(exec.alpaca_account.cash || 0).toLocaleString(undefined, {maximumFractionDigits:0})}` },
                    { label: "BUYING POWER",  value: `$${parseFloat(exec.alpaca_account.buying_power || 0).toLocaleString(undefined, {maximumFractionDigits:0})}` },
                  ].map(({ label, value }) => (
                    <div key={label}>
                      <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 8, color: "rgba(232,224,208,0.3)", letterSpacing: "0.1em", marginBottom: 2 }}>{label}</div>
                      <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 12, color: "rgba(232,224,208,0.75)" }}>{value}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {exec?.last_cycle && (
            <div style={{ ...mono, fontSize: 9, color: "rgba(232,224,208,0.25)", marginTop: 8 }}>Last cycle: {exec.last_cycle}</div>
          )}
        </div>

        {/* ── Commentary Agent ── */}
        <div style={card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div style={sectionTitle}>🧠 AI COMMENTARY AGENT</div>
            {commentary && (
              <span style={{ ...mono, fontSize: 10, padding: "2px 8px", border: "1px solid rgba(192,132,252,0.3)", borderRadius: 2, color: "#c084fc" }}>
                {commentary.source === "llm" ? "LLM" : "TEMPLATE"}
              </span>
            )}
          </div>
          {commentary?.stats && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 8, marginBottom: 14 }}>
              {[
                { label: "Promoted",  value: commentary.stats.n_promoted },
                { label: "Top Signal", value: commentary.stats.top_signal },
                { label: "Portfolio SR", value: commentary.stats.portfolio_sharpe?.toFixed(2) || "—" },
              ].map(({ label, value }) => (
                <div key={label} style={{ background: "rgba(255,255,255,0.03)", borderRadius: 4, padding: "8px 12px" }}>
                  <div style={{ ...mono, fontSize: 9, color: "rgba(232,224,208,0.35)", letterSpacing: "0.1em", marginBottom: 3 }}>{label}</div>
                  <div style={{ ...mono, fontSize: 12, color: "rgba(232,224,208,0.85)" }}>{value}</div>
                </div>
              ))}
            </div>
          )}
          <div style={{
            flex: 1,
            background: "rgba(0,0,0,0.3)",
            borderRadius: 4, padding: "14px 16px",
            fontFamily: "Cormorant Garamond, serif", fontSize: 13,
            color: "rgba(232,224,208,0.75)", lineHeight: 1.7,
            maxHeight: 280, overflowY: "auto",
            whiteSpace: "pre-wrap",
            marginBottom: 14,
          }}>
            {commentary?.commentary
              ? commentary.commentary
              : <span style={{ color: "rgba(232,224,208,0.25)", fontStyle: "italic" }}>No report generated yet. Click Generate Report to run the agent.</span>
            }
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <BtnRun label="GENERATE REPORT" onClick={triggerCommentary} active={runningJob === "commentary"} />
            {commentary?.timestamp && (
              <span style={{ ...mono, fontSize: 9, color: "rgba(232,224,208,0.25)" }}>{commentary.timestamp}</span>
            )}
          </div>
        </div>
      </div>

      {/* ── Scheduler ── */}
      <div style={card}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div style={sectionTitle}>🕐 BACKGROUND SCHEDULER</div>
          <span style={{ ...mono, fontSize: 11, color: sched?.running ? "#4ade80" : "rgba(248,113,113,0.7)",
            padding: "2px 8px", border: `1px solid ${sched?.running ? "#4ade8022" : "rgba(248,113,113,0.2)"}`, borderRadius: 2 }}>
            {sched?.running ? "RUNNING" : sched ? "STOPPED" : "OFFLINE"}
          </span>
        </div>
        {!sched?.apscheduler && (
          <div style={{ padding: "8px 12px", background: "rgba(250,204,21,0.06)", border: "1px solid rgba(250,204,21,0.2)", borderRadius: 4, ...mono, fontSize: 11, color: "rgba(250,204,21,0.7)", marginBottom: 14 }}>
            APScheduler not installed. Run: <code>pip install apscheduler</code> then restart.
          </div>
        )}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 16 }}>
          {[
            { id: "refresh_prices",    label: "Price Refresh",     icon: "📈", desc: "Weekdays 16:30 ET" },
            { id: "refresh_fred",      label: "FRED Macro",        icon: "🏦", desc: "Every 6 hours" },
            { id: "recompute_signals", label: "Signal Recompute",  icon: "⚙",  desc: "Weekdays 17:00 ET" },
            { id: "execution_cycle",   label: "Execution Cycle",   icon: "⚡", desc: "Weekdays 17:30 ET" },
            { id: "commentary",        label: "AI Commentary",     icon: "🧠", desc: "Weekdays 18:00 ET" },
            { id: "weekly_deep_refresh",label:"Deep Refresh",      icon: "🔄", desc: "Monday 09:00 ET" },
          ].map(job => {
            const scheduled = sched?.jobs?.find(j => j.id === job.id);
            const recentRun = sched?.recent_history?.find(h => h.job === job.id);
            return (
              <div key={job.id} style={{ background: "rgba(255,255,255,0.03)", borderRadius: 4, padding: "12px 14px", display: "flex", flexDirection: "column", gap: 6 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <span style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 13, color: "#c9a96e", letterSpacing: "0.05em" }}>{job.icon} {job.label}</span>
                  {recentRun && (
                    <span style={{ ...mono, fontSize: 8, padding: "1px 6px", borderRadius: 2,
                      color:       recentRun.status === "OK" ? "#4ade80" : "#f87171",
                      border: `1px solid ${recentRun.status === "OK" ? "#4ade8022" : "rgba(248,113,113,0.2)"}`
                    }}>{recentRun.status}</span>
                  )}
                </div>
                <div style={{ ...mono, fontSize: 9, color: "rgba(232,224,208,0.3)" }}>{job.desc}</div>
                {scheduled?.next_run && (
                  <div style={{ ...mono, fontSize: 9, color: "rgba(232,224,208,0.4)" }}>Next: {new Date(scheduled.next_run).toLocaleTimeString()}</div>
                )}
                {recentRun?.detail && (
                  <div style={{ ...mono, fontSize: 9, color: "rgba(232,224,208,0.4)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{recentRun.detail}</div>
                )}
                <BtnRun label="RUN NOW" onClick={() => triggerJob(job.id)} active={runningJob === job.id} />
              </div>
            );
          })}
        </div>
        {/* Recent job history */}
        {sched?.recent_history?.length > 0 && (
          <div>
            <div style={{ ...mono, fontSize: 9, color: "rgba(232,224,208,0.3)", letterSpacing: "0.1em", marginBottom: 8 }}>RECENT JOB HISTORY</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 160, overflowY: "auto" }}>
              {sched.recent_history.slice(0, 15).map((h, i) => (
                <div key={i} style={{ display: "flex", gap: 12, alignItems: "center", ...mono, fontSize: 10 }}>
                  <span style={{ color: "rgba(232,224,208,0.25)", fontSize: 9, minWidth: 140 }}>{h.timestamp?.slice(0, 19).replace("T", " ")}</span>
                  <span style={{ color: "rgba(201,169,110,0.6)", minWidth: 140 }}>{h.job}</span>
                  <span style={{ color: h.status === "OK" ? "#4ade80" : "#f87171", minWidth: 40 }}>{h.status}</span>
                  <span style={{ color: "rgba(232,224,208,0.35)" }}>{h.detail}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function QuantAlphaFoundry() {
  const [activeView, setActiveView] = useState("FOUNDRY");
  const [selectedSignal, setSelectedSignal] = useState(SIGNALS[0]);
  const [tick, setTick] = useState(0);

  // ── Live data state ──────────────────────────────────────────────────────
  const [liveMetrics, setLiveMetrics]     = useState(null);
  const [livePnl, setLivePnl]             = useState(null);
  const [liveBenchmark, setLiveBenchmark] = useState(null);
  const [macroSignals, setMacroSignals]   = useState(null);
  const [agentData, setAgentData]         = useState(null);
  const [dataSource, setDataSource]       = useState("SIMULATED");
  const [isComputing, setIsComputing]     = useState(false);

  // Active data: live if available, otherwise simulated fallback
  const activeMetrics   = liveMetrics   || SIGNAL_METRICS_SIM;
  const activePnl       = livePnl       || PORTFOLIO_PNL_SIM;
  const activeBenchmark = liveBenchmark || SPY_BENCHMARK_SIM;

  // ── Transform fountryhh API responses → frontend metrics shape ─────────────
  function transformSignalList(signals, details) {
    const CAPACITY = {
      MOM12_1: "$800M", STREV: "$80M", MOM_1M: "$200M", VAL_BM: "$1.2B",
      VAL_EP: "$900M", QUAL_ROE: "$1.0B", QUAL_GP: "$1.5B", LOW_VOL: "$2.0B",
      LOW_BETA: "$1.8B", IDIOVOL: "$600M", EARN_REV: "$400M", SHORT_INT: "$300M",
      ACCRUAL: "$600M", INV_GROW: "$700M", COMBO_QVM: "$2.0B",
      ML_GBDT: "$500M", NLP_EARN: "$350M",
    };
    const metrics = {};
    for (const s of signals) {
      const id = s.signal_id || s.id;
      const detail = details[id] || {};
      const decay = detail.decay || [];
      const wf = detail.walkforward || [];
      const monthlyRets = detail.monthly_returns || [];
      const regimeRaw = detail.regime_ic || {};

      // Walk-forward → add cumPnL + map regime keys
      let cum = 0;
      const wfYears = wf.map(y => {
        cum += parseFloat(y.ann_return || 0);
        return {
          year: y.year,
          ic: (y.ic || 0).toFixed(4),
          annReturn: String(y.ann_return || 0),
          cumPnL: cum.toFixed(1),
          regime: y.regime || "bull",
        };
      });

      // Map fountryhh regime keys → frontend keys (range_bound→range, inflationary→inflate)
      const regimeIC = {
        bull:    (regimeRaw.bull    ?? 0).toFixed(4),
        bear:    (regimeRaw.bear    ?? 0).toFixed(4),
        crisis:  (regimeRaw.crisis  ?? 0).toFixed(4),
        range:   (regimeRaw.range_bound   ?? regimeRaw.range   ?? 0).toFixed(4),
        inflate: (regimeRaw.inflationary  ?? regimeRaw.inflate ?? 0).toFixed(4),
      };

      const returns = monthlyRets.map((r, i) => ({
        month: i + 1,
        ret: r.return ?? r.ret ?? 0,
        long: (r.return ?? r.ret ?? 0) * 1.5,
        short: (r.return ?? r.ret ?? 0) * -0.7,
      }));

      const md = s.max_drawdown || 0;
      const ns = parseFloat(s.net_sharpe || 0);
      const calmar = md !== 0 ? Math.abs(ns / (md / 100)).toFixed(2) : "0.00";

      metrics[id] = {
        ic:          (s.ic || 0).toFixed(4),
        icir:        (s.icir || 0).toFixed(3),
        annualIR:    (s.annual_ir || 0).toFixed(2),
        grossSharpe: (s.gross_sharpe || 0).toFixed(2),
        netSharpe:   (s.net_sharpe || 0).toFixed(2),
        maxDD:       String(md),
        calmar,
        turnover:    String(Math.round(s.turnover || 0)),
        winRate:     (s.win_rate || 50).toFixed(1),
        hitRate:     (s.win_rate || 50).toFixed(1),
        capacity:    CAPACITY[id] || "$500M",
        tcCost:      (s.tc_cost || 0).toFixed(3),
        regimeIC,
        wfYears,
        decay:       decay.map(d => ({ lag: d.lag, ic: d.ic })),
        returns,
        promoted:    Boolean(s.promoted),
      };
    }
    return metrics;
  }

  useEffect(() => {
    async function fetchLive() {
      try {
        const healthRes = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
        if (!healthRes.ok) return;
        const health = await healthRes.json();
        if (!health.data_loaded) { setIsComputing(true); return; }

        // Fetch signal list + detail for all signals in parallel
        const sigRes = await fetch(`${API_BASE}/api/signals`);
        if (!sigRes.ok) return;
        const signalList = await sigRes.json();
        if (!Array.isArray(signalList) || signalList.length === 0) return;

        const detailResults = await Promise.allSettled(
          signalList.map(s =>
            fetch(`${API_BASE}/api/signals/${s.signal_id || s.id}`)
              .then(r => r.ok ? r.json() : null)
          )
        );
        const details = {};
        signalList.forEach((s, i) => {
          const id = s.signal_id || s.id;
          const v = detailResults[i];
          if (v.status === "fulfilled" && v.value) details[id] = v.value;
        });

        // Merge simulated fallback for signals not in backend (ML_GBDT, NLP_EARN)
        const liveIds = new Set(signalList.map(s => s.signal_id || s.id));
        const transformed = transformSignalList(signalList, details);
        const merged = { ...SIGNAL_METRICS_SIM };
        Object.assign(merged, transformed);
        // Keep sim data for signals not returned by backend
        for (const id of liveIds) merged[id] = transformed[id];

        setLiveMetrics(merged);
        setDataSource("LIVE");
        setIsComputing(false);

        // FRED macro signals (free, no key)
        const macroRes = await fetch(`${API_BASE}/api/macro/all`);
        if (macroRes.ok) {
          const macroData = await macroRes.json();
          if (macroData && typeof macroData === "object") setMacroSignals(macroData);
        }

        // Portfolio
        const portRes = await fetch(`${API_BASE}/api/portfolio/performance`);
        if (portRes.ok) {
          const port = await portRes.json();
          const curve = port.equity_curve;
          if (curve?.portfolio?.length > 10) {
            setLivePnl(curve.portfolio.map(v => v * 100));
            setLiveBenchmark(curve.benchmark.map(v => v * 100));
          }
        }

        // Agents
        try {
          const [agentStatus, execState, commentary, schedStatus] = await Promise.allSettled([
            fetch(`${API_BASE}/api/agents/status`).then(r => r.ok ? r.json() : null),
            fetch(`${API_BASE}/api/agents/execution/state`).then(r => r.ok ? r.json() : null),
            fetch(`${API_BASE}/api/agents/commentary/latest`).then(r => r.ok ? r.json() : null),
            fetch(`${API_BASE}/api/agents/scheduler/status`).then(r => r.ok ? r.json() : null),
          ]);
          setAgentData({
            status:      agentStatus.status === "fulfilled" ? agentStatus.value : null,
            execution:   execState.status === "fulfilled"   ? execState.value   : null,
            commentary:  commentary.status === "fulfilled"  ? commentary.value  : null,
            scheduler:   schedStatus.status === "fulfilled" ? schedStatus.value : null,
          });
        } catch { /* agents not ready */ }
      } catch {
        // Backend not running — silently stay on simulated data
      }
    }

    fetchLive();
    const poll = setInterval(fetchLive, 60_000);
    return () => clearInterval(poll);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => setTick(t => t + 1), 3000);
    return () => clearInterval(interval);
  }, []);

  const handleSelectSignal = useCallback((signal) => {
    setSelectedSignal(signal);
    setActiveView("SIGNAL LAB");
  }, []);

  const livePrice = (100 + Math.sin(tick * 0.3) * 2 + tick * 0.05).toFixed(2);
  const tickerPnl = (12.4 + Math.sin(tick * 0.2) * 0.3).toFixed(2);

  return (
    <div style={{ minHeight: "100vh", background: "#070b12" }}>
      <style>{CSS}</style>

      {/* Background scanline effect */}
      <div style={{
        position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0,
        background: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(201,169,110,0.008) 2px, rgba(201,169,110,0.008) 4px)",
      }}/>
      <div style={{
        position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0,
        background: "radial-gradient(ellipse at 20% 50%, rgba(201,169,110,0.04) 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, rgba(192,132,252,0.03) 0%, transparent 50%)",
      }}/>

      {/* TOP NAV */}
      <nav style={{
        position: "sticky", top: 0, zIndex: 100,
        background: "rgba(7,11,18,0.97)", backdropFilter: "blur(24px)",
        borderBottom: "1px solid rgba(201,169,110,0.12)",
        padding: "0 40px",
      }}>
        <div style={{ maxWidth: 1400, margin: "0 auto", display: "flex", alignItems: "center", height: 56, gap: 0 }}>
          {/* Brand */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginRight: 40, flexShrink: 0 }}>
            <div style={{ position: "relative" }}>
              <div style={{ width: 28, height: 28, border: "1px solid #c9a96e", transform: "rotate(45deg)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 14, color: "#c9a96e", transform: "rotate(-45deg)" }}>α</div>
              </div>
            </div>
            <div>
              <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 16, color: "#c9a96e", letterSpacing: "0.2em" }}>ALPHA FOUNDRY</div>
              <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 8, color: "rgba(201,169,110,0.45)", letterSpacing: "0.2em" }}>INSTITUTIONAL RESEARCH PLATFORM</div>
            </div>
          </div>

          {/* Nav Tabs */}
          <div style={{ display: "flex", flex: 1, gap: 2 }}>
            {VIEWS.map(v => (
              <button key={v} onClick={() => setActiveView(v)} style={{
                padding: "8px 18px", border: "none",
                background: activeView === v ? "rgba(201,169,110,0.12)" : "transparent",
                color: activeView === v ? "#c9a96e" : "rgba(232,224,208,0.35)",
                fontFamily: "JetBrains Mono, monospace", fontSize: 11, letterSpacing: "0.12em",
                borderBottom: activeView === v ? "2px solid #c9a96e" : "2px solid transparent",
                transition: "all 0.15s",
              }}
              onMouseEnter={e => { if (activeView !== v) e.currentTarget.style.color = "rgba(232,224,208,0.7)"; }}
              onMouseLeave={e => { if (activeView !== v) e.currentTarget.style.color = "rgba(232,224,208,0.35)"; }}
              >{v}</button>
            ))}
          </div>

          {/* Live Ticker + Data Source */}
          <div style={{ display: "flex", gap: 20, alignItems: "center", fontFamily: "JetBrains Mono, monospace", fontSize: 11, flexShrink: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 14px", background: "rgba(74,222,128,0.06)", border: "1px solid rgba(74,222,128,0.15)", borderRadius: 2 }}>
              <span className="live-dot"/>
              <span style={{ color: "rgba(232,224,208,0.5)" }}>PNL</span>
              <span style={{ color: "#4ade80" }}>+{tickerPnl}%</span>
            </div>
            <div style={{ color: "rgba(232,224,208,0.3)" }}>SPX <span style={{ color: "#c9a96e" }}>{livePrice}</span></div>
            <Badge
              text={dataSource}
              color={dataSource === "LIVE" ? "#4ade80" : "#facc15"}
            />
          </div>
        </div>
      </nav>

      {/* Computing banner */}
      {isComputing && (
        <div style={{
          background: "rgba(201,169,110,0.08)", borderBottom: "1px solid rgba(201,169,110,0.15)",
          padding: "7px 40px", fontFamily: "JetBrains Mono, monospace", fontSize: 10,
          color: "rgba(201,169,110,0.7)", letterSpacing: "0.12em",
          display: "flex", alignItems: "center", gap: 8,
        }}>
          <span className="live-dot" style={{ background: "#c9a96e" }}/>
          COMPUTING LIVE SIGNAL METRICS — SHOWING SIMULATED DATA UNTIL READY
        </div>
      )}

      {/* Signal Sub-Nav (Signal Lab) */}
      {activeView === "SIGNAL LAB" && (
        <div style={{
          background: "rgba(7,11,18,0.95)", borderBottom: "1px solid rgba(255,255,255,0.06)",
          padding: "10px 40px", display: "flex", gap: 6, flexWrap: "wrap",
        }}>
          {SIGNALS.map(s => {
            const m = activeMetrics[s.id];
            return (
              <button key={s.id} onClick={() => setSelectedSignal(s)} style={{
                padding: "5px 14px", borderRadius: 2,
                background: selectedSignal.id === s.id ? "rgba(201,169,110,0.12)" : "transparent",
                border: `1px solid ${selectedSignal.id === s.id ? "rgba(201,169,110,0.4)" : "rgba(255,255,255,0.07)"}`,
                color: selectedSignal.id === s.id ? "#c9a96e" : "rgba(232,224,208,0.4)",
                fontFamily: "JetBrains Mono, monospace", fontSize: 10, letterSpacing: "0.08em",
                transition: "all 0.15s",
              }}>
                <span style={{ marginRight: 6 }}>{s.name}</span>
                <span style={{ color: m.promoted ? "#4ade80" : "#facc15", fontSize: 8 }}>●</span>
              </button>
            );
          })}
        </div>
      )}

      {/* Main Content */}
      <main style={{ position: "relative", zIndex: 1 }} className="fade-in" key={activeView + selectedSignal.id}>
        {activeView === "FOUNDRY"      && <FoundryOverview onSelectSignal={handleSelectSignal} metrics={activeMetrics}/>}
        {activeView === "SIGNAL LAB"   && <SignalLab signal={selectedSignal} metrics={activeMetrics}/>}
        {activeView === "STRESS TEST"  && <StressTest metrics={activeMetrics} macroSignals={macroSignals}/>}
        {activeView === "EXECUTION"    && <ExecutionDashboard/>}
        {activeView === "PORTFOLIO"    && <PortfolioDashboard pnl={activePnl} benchmark={activeBenchmark}/>}
        {activeView === "AGENTS"        && <AgentsDashboard agentData={agentData} apiBase={API_BASE}/>}
      </main>

      {/* Footer */}
      <footer style={{ borderTop: "1px solid rgba(201,169,110,0.08)", padding: "16px 40px", marginTop: 60 }}>
        <div style={{ maxWidth: 1400, margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(201,169,110,0.4)" }}>
            ALPHA FOUNDRY v2.0 · {SIGNALS.length} signals researched · {SIGNALS.filter(s => activeMetrics[s.id].promoted).length} promoted · {dataSource === "LIVE" ? "Live data via yfinance" : "Simulated data — start backend for live"}
          </div>
          <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.2)" }}>
            IR = IC · √N · Vₜ + rSVₛ + ½σ²S²Vₛₛ = rV
          </div>
        </div>
      </footer>
    </div>
  );
}
