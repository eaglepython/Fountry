import { useState, useEffect, useCallback } from "react";

const API_BASE = (import.meta.env?.VITE_API_URL || (import.meta.env?.PROD ? "" : "http://localhost:8000"))
  .trim()
  .replace(/\/+$/, "");

// ═══════════════════════════════════════════════════════════════════════════
// FOUNTRY — Experimental quantitative research workbench
// ═══════════════════════════════════════════════════════════════════════════

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
  { id: "ML_GBDT",   name: "ML Gradient Boost",      category: "ML",         description: "Candidate only; model and historical evaluation are not implemented." },
  { id: "NLP_EARN",  name: "Earnings NLP",           category: "ML",         description: "Candidate only; historical earnings text and validated model are unavailable." },
];

// ── REGIME DEFINITIONS ───────────────────────────────────────────────────────
const REGIMES = [
  { id: "bull",    name: "Bull Market",    color: "#4ade80", desc: "Trending up, low vol" },
  { id: "bear",    name: "Bear Market",    color: "#f87171", desc: "Trending down, high vol" },
  { id: "crisis",  name: "Crisis",         color: "#c084fc", desc: "Extreme vol, correlation spike" },
  { id: "range",   name: "Range-Bound",    color: "#facc15", desc: "Low vol, mean-reverting" },
  { id: "inflate", name: "Inflationary",   color: "#fb923c", desc: "Rising rates, commodity-driven" },
];

const VIEWS = ["FOUNTRY", "SIGNAL LAB", "STRESS TEST", "EXECUTION", "PORTFOLIO", "AGENTS"];

// Research views begin in an unavailable state until real backend data arrives.
const EMPTY_SIGNAL_METRIC = {
  ic: "—", icir: "—", annualIR: "—", grossSharpe: "—", netSharpe: "—",
  maxDD: "—", calmar: "—", turnover: "—", winRate: "—", hitRate: "—",
  capacity: "—", tcCost: "—", regimeIC: { bull: "—", bear: "—", crisis: "—", range: "—", inflate: "—" },
  wfYears: [], decay: [], returns: [], promoted: false, nPeriods: 0,
};
const EMPTY_SIGNAL_METRICS = Object.fromEntries(SIGNALS.map(signal => [signal.id, EMPTY_SIGNAL_METRIC]));
// ═══════════════════════════════════════════════════════════════════════════
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
  const numericValue = Number(value);
  const available = Number.isFinite(numericValue);
  const pct = available ? Math.min(Math.abs(numericValue) / max * 100, 100) : 0;
  const col = !available ? "rgba(232,224,208,0.25)" : numericValue > 0.035 ? "#4ade80" : numericValue > 0.025 ? "#facc15" : "#f87171";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 6, background: "rgba(255,255,255,0.06)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: col, borderRadius: 3, transition: "width 0.6s ease" }}/>
      </div>
      <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: col, minWidth: 50, textAlign: "right" }}>{available ? value : "—"}</span>
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
  if (!data?.length) return <p style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.4)" }}>No validated strategy return series available.</p>;
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
  if (!decay?.length) return <p style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.4)" }}>Decay requires dated, point-in-time observations.</p>;
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
        const rawIC = regimeIC[reg.id];
        const ic = rawIC == null || rawIC === "—" ? null : Number(rawIC);
        const pct = ic == null || !Number.isFinite(ic) ? 0 : Math.min(Math.abs(ic) / 0.07 * 100, 100);
        return (
          <div key={reg.id} style={{
            background: "rgba(255,255,255,0.03)", borderRadius: 3, padding: "8px 10px",
            border: `1px solid ${reg.color}22`,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
              <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: reg.color }}>{reg.name}</span>
              <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: ic != null && ic > 0.02 ? "#4ade80" : "rgba(232,224,208,0.4)" }}>{ic == null ? "—" : ic.toFixed(3)}</span>
            </div>
            <div style={{ height: 4, background: "rgba(255,255,255,0.06)", borderRadius: 2 }}>
              <div style={{ width: `${pct}%`, height: "100%", background: ic != null && ic > 0.02 ? reg.color : "#f87171", borderRadius: 2 }}/>
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
  const measuredICs = SIGNALS.map(s => Number(metrics[s.id].ic)).filter(Number.isFinite);
  const totalIC = measuredICs.length ? (measuredICs.reduce((a, v) => a + v, 0) / measuredICs.length).toFixed(4) : "—";
  const avgNetSharpe = promoted.length
    ? (promoted.reduce((a, s) => a + parseFloat(metrics[s.id].netSharpe), 0) / promoted.length).toFixed(2)
    : "—";

  return (
    <div className="page-pad" style={{ padding: "32px 40px", maxWidth: 1400, margin: "0 auto" }}>
      {/* KPI Strip */}
      <div className="stat-grid-6" style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 12, marginBottom: 32 }}>
        <StatCard label="Signals Researched" value={SIGNALS.length} sub="Active universe" size="normal"/>
        <StatCard label="Promoted" value={promoted.length} sub="Pass all gates" color="#4ade80" size="normal"/>
        <StatCard label="In Review" value={review.length} sub="Needs work" color="#facc15" size="normal"/>
        <StatCard label="Avg IC" value={totalIC} sub="Universe mean" color="#c9a96e" size="normal"/>
        <StatCard label="Portfolio IR" value={avgNetSharpe} sub="Requires after-cost portfolio results" color="#4ade80" size="normal"/>
        <StatCard label="Capacity" value="—" sub="Not measured" color="#c084fc" size="normal"/>
      </div>

      {/* Signal Pipeline */}
      <div className="grid-2col" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 28 }}>
        {/* Promoted Signals */}
        <div style={{ background: "rgba(12,18,28,0.95)", border: "1px solid rgba(74,222,128,0.2)", borderRadius: 6, padding: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 18, color: "#4ade80", letterSpacing: "0.08em" }}>PROMOTED SIGNALS</div>
            <Badge text="NONE VALIDATED" color="#facc15"/>
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
              if (m.nPeriods === 0) issues.push("NO DATA");
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
                      {issues.length === 0 && <Badge text="NOT VALIDATED" color="#facc15"/>}
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
      <div className="stat-grid-5" style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 24 }}>
        <StatCard label="Information Coefficient" value={m.ic} sub="Cross-sectional rank correlation" color="#c9a96e" size="normal"/>
        <StatCard label="IC Information Ratio" value={m.icir} sub="IC / σ(IC)" color="#c9a96e" size="normal"/>
        <StatCard label="Gross Sharpe" value={m.grossSharpe} sub="Before TC" color="#4ade80" size="normal"/>
        <StatCard label="Net Sharpe" value={m.netSharpe} sub="Requires fills and measured costs" color={parseFloat(m.netSharpe) > 0.5 ? "#4ade80" : "#f87171"} size="normal"/>
        <StatCard label="Max Drawdown" value={m.maxDD === "—" ? "—" : `${m.maxDD}%`} sub="Requires portfolio returns" color="#f87171" size="normal"/>
      </div>
      <div className="stat-grid-5" style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 28 }}>
        <StatCard label="Annual Turnover" value={m.turnover === "—" ? "—" : `${m.turnover}%`} sub="Requires dated holdings" color="#c9a96e"/>
        <StatCard label="Positive IC Periods" value={m.winRate === "—" ? "—" : `${m.winRate}%`} sub="Not a portfolio win rate" color="#4ade80"/>
        <StatCard label="Hit Rate" value={m.hitRate} sub="Requires portfolio returns" color="#c9a96e"/>
        <StatCard label="Capacity" value={m.capacity} sub="Estimated AUM cap" color="#c084fc"/>
        <StatCard label="Calmar Ratio" value={m.calmar} sub="SR / |MaxDD|" color={parseFloat(m.calmar) > 1 ? "#4ade80" : "#facc15"}/>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
        {/* Walk-Forward Performance */}
        <div style={{ background: "rgba(12,18,28,0.95)", border: "1px solid rgba(201,169,110,0.15)", borderRadius: 6, padding: 20 }}>
          <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 16, color: "#c9a96e", letterSpacing: "0.08em", marginBottom: 14 }}>OBSERVED IC BY YEAR (NO RETURN BACKTEST)</div>
          <div style={{ display: "grid", gap: 6 }}>
            <div style={{ display: "grid", gridTemplateColumns: "60px 70px 80px 80px 80px", gap: 8, marginBottom: 4 }}>
              {["YEAR","MEAN IC","SAMPLES","RETURN","REGIME"].map(h => (
                <div key={h} style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 9, color: "rgba(232,224,208,0.35)", letterSpacing: "0.1em" }}>{h}</div>
              ))}
            </div>
            {m.wfYears.length ? m.wfYears.map(y => {
              const reg = REGIMES.find(r => r.id === y.regime);
              return (
                <div key={y.year} style={{ display: "grid", gridTemplateColumns: "60px 70px 80px 80px 80px", gap: 8, alignItems: "center", padding: "4px 0", borderTop: "1px solid rgba(255,255,255,0.04)" }}>
                  <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "#e8e0d0" }}>{y.year}</div>
                  <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "#c9a96e" }}>{y.ic}</div>
                  <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "rgba(232,224,208,0.4)" }}>{y.nMonths}</div>
                  <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "rgba(232,224,208,0.4)" }}>—</div>
                  <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 9, color: reg?.color }}>{reg?.name}</div>
                </div>
              );
            }) : <p style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.4)" }}>No year has enough observed IC samples.</p>}
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
        <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 16, color: "#c9a96e", letterSpacing: "0.08em", marginBottom: 12 }}>MONTHLY RETURNS (UNAVAILABLE)</div>
        <ReturnChart data={m.returns} height={120}/>
        {m.returns.length > 0 && <div style={{ display: "flex", gap: 24, marginTop: 8 }}>
          <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.4)" }}>
            Positive months: <span style={{ color: "#4ade80" }}>{m.returns.filter(d => parseFloat(d.ret) > 0).length}/60</span>
          </div>
          <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.4)" }}>
            Best month: <span style={{ color: "#4ade80" }}>+{Math.max(...m.returns.map(d => parseFloat(d.ret))).toFixed(2)}%</span>
          </div>
          <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.4)" }}>
            Worst month: <span style={{ color: "#f87171" }}>{Math.min(...m.returns.map(d => parseFloat(d.ret))).toFixed(2)}%</span>
          </div>
        </div>}
      </div>
    </div>
  );
}

function StressTest() { return <UnavailablePanel title="Regime stress results unavailable" message="No date-aligned historical regime-conditioned returns are implemented."/>; }

function ExecutionDashboard() { return <UnavailablePanel title="Execution analytics unavailable" message="No verified broker fills or execution-cost feed is connected."/>; }

function PortfolioDashboard() { return <UnavailablePanel title="Portfolio performance unavailable" message="No validated point-in-time, after-cost portfolio backtest is available."/>; }

function UnavailablePanel({ title, message }) {
  return (
    <section style={{ maxWidth: 960, margin: "56px auto", padding: "24px 28px", border: "1px solid rgba(201,169,110,0.2)", borderRadius: 6, background: "rgba(12,18,28,0.95)" }}>
      <h2 style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 24, color: "#c9a96e", letterSpacing: "0.06em", marginBottom: 8 }}>{title}</h2>
      <p style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 12, lineHeight: 1.7, color: "rgba(232,224,208,0.62)" }}>{message}</p>
    </section>
  );
}
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

  /* ── Mobile nav drawer ── */
  .mobile-menu-btn { display: none; background: none; border: 1px solid rgba(201,169,110,0.3); padding: 6px 10px; border-radius: 3px; color: #c9a96e; font-size: 16px; }
  .nav-tabs-mobile { display: none; position: fixed; top: 56px; left: 0; right: 0; z-index: 99;
    background: rgba(7,11,18,0.98); border-bottom: 1px solid rgba(201,169,110,0.15);
    flex-direction: column; padding: 8px 0; }
  .nav-tabs-mobile.open { display: flex; }
  .nav-tabs-mobile button { padding: 12px 24px !important; font-size: 13px !important; border-bottom: none !important; border-left: 2px solid transparent; text-align: left; }
  .nav-tabs-mobile button.active-tab { border-left: 2px solid #c9a96e !important; }

  /* ── Responsive grid overrides ── */
  @media (max-width: 768px) {
    .mobile-menu-btn { display: block !important; }
    .nav-tabs-desktop { display: none !important; }
    .nav-ticker { display: none !important; }
    .nav-brand-sub { display: none !important; }

    .page-pad { padding: 16px !important; }
    .stat-grid-6 { grid-template-columns: repeat(2, 1fr) !important; }
    .stat-grid-5 { grid-template-columns: repeat(2, 1fr) !important; }
    .stat-grid-4 { grid-template-columns: repeat(2, 1fr) !important; }
    .stat-grid-3 { grid-template-columns: repeat(2, 1fr) !important; }
    .grid-2col  { grid-template-columns: 1fr !important; }
    .grid-2col-agents { grid-template-columns: 1fr !important; }
    .hide-mobile { display: none !important; }
    .signal-row-grid { grid-template-columns: 1fr auto auto !important; }
    .signal-rank-col { display: none !important; }
    .overflow-mobile { overflow-x: auto; -webkit-overflow-scrolling: touch; }
    .page-title { font-size: 22px !important; }
    .nav-inner { padding: 0 16px !important; }
  }

  @media (max-width: 480px) {
    .stat-grid-6 { grid-template-columns: repeat(2, 1fr) !important; }
    .stat-grid-5 { grid-template-columns: repeat(2, 1fr) !important; }
    .card-pad { padding: 14px !important; }
  }
`;

// ─────────────────────────────────────────────────────────────────────────────
// AGENTS DASHBOARD
// ─────────────────────────────────────────────────────────────────────────────
function AgentsDashboard({ agentData, apiBase }) {
  const [runningJob, setRunningJob] = useState(null);
  const [localAgent, setLocalAgent] = useState(agentData);
  const [switchingMode, setSwitchingMode] = useState(false);
  const [modeSwitchMsg, setModeSwitchMsg] = useState(null);
  const [controlToken, setControlToken] = useState("");

  // Sync prop changes
  useEffect(() => { setLocalAgent(agentData); }, [agentData]);

  const exec      = localAgent?.execution;
  const sched     = localAgent?.scheduler;
  const commentary = localAgent?.commentary;

  // Current mode derived from backend state
  const currentMode = !exec?.alpaca_enabled || exec?.alpaca_mode === "PAPER" ? "paper" : "live";
  const hasControlToken = Boolean(controlToken.trim());
  const runControl = async (path) => {
    const response = await fetch(`${apiBase}${path}`, {
      method: "POST",
      headers: { "X-Agent-Control-Token": controlToken.trim() },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    return data;
  };

  const switchMode = async (newMode) => {
    if (switchingMode) return;
    setSwitchingMode(true);
    setModeSwitchMsg(null);
    try {
      await runControl(`/api/agents/execution/mode/${newMode}`);
      setModeSwitchMsg({ ok: true, text: `Switched to ${newMode.toUpperCase()} trading` });
      const s = await fetch(`${apiBase}/api/agents/execution/state`);
      if (s.ok) {
        const state = await s.json();
        setLocalAgent(prev => ({ ...prev, execution: state }));
      }
    } catch (e) {
      setModeSwitchMsg({ ok: false, text: e.message || "Backend unreachable" });
    }
    setSwitchingMode(false);
    setTimeout(() => setModeSwitchMsg(null), 4000);
  };

  const triggerJob = async (jobId) => {
    setRunningJob(jobId);
    try {
      const result = await runControl(`/api/agents/scheduler/trigger/${jobId}`);
      setModeSwitchMsg({ ok: true, text: result.status === "triggered" ? `${jobId} started` : result.message || "Job started" });
    } catch (e) { setModeSwitchMsg({ ok: false, text: e.message || "Could not start job" }); }
    setTimeout(() => setRunningJob(null), 3000);
  };

  const triggerExecution = async () => {
    setRunningJob("execution");
    try {
      const result = await runControl("/api/agents/execution/run");
      setModeSwitchMsg({ ok: true, text: result.message || result.status });
    } catch (e) { setModeSwitchMsg({ ok: false, text: e.message || "Could not start execution" }); }
    setTimeout(() => setRunningJob(null), 5000);
  };

  const resetCircuitBreaker = async () => {
    try {
      const data = await runControl("/api/agents/execution/reset");
      setModeSwitchMsg({ ok: true, text: `Circuit breaker reset — NAV anchor: $${data.nav?.toLocaleString()}` });
      const s = await fetch(`${apiBase}/api/agents/execution/state`);
      if (s.ok) {
        const state = await s.json();
        setLocalAgent(prev => ({ ...prev, execution: state }));
      }
    } catch (e) { setModeSwitchMsg({ ok: false, text: e.message || "Reset failed" }); }
    setTimeout(() => setModeSwitchMsg(null), 5000);
  };

  const triggerCommentary = async () => {
    setRunningJob("commentary");
    try {
      const result = await runControl("/api/agents/commentary/generate");
      setModeSwitchMsg({ ok: true, text: result.message || result.status });
    } catch (e) { setModeSwitchMsg({ ok: false, text: e.message || "Could not generate commentary" }); }
    setTimeout(() => setRunningJob(null), 15000);
  };

  const mono = { fontFamily: "JetBrains Mono, monospace" };
  const card = { background: "rgba(12,18,28,0.95)", border: "1px solid rgba(201,169,110,0.15)", borderRadius: 6, padding: 20 };
  const sectionTitle = { fontFamily: "Bebas Neue, sans-serif", fontSize: 20, color: "#c9a96e", letterSpacing: "0.08em", marginBottom: 16 };

  const agentStatus = (status) => {
    const colors = { IDLE: "#4ade80", RUNNING: "#facc15", ERROR: "#f87171", CIRCUIT_BREAKER: "#f87171" };
    return <span style={{ ...mono, fontSize: 11, color: colors[status] || "rgba(232,224,208,0.5)", padding: "2px 8px", border: `1px solid ${colors[status] || "rgba(255,255,255,0.1)"}22`, borderRadius: 2 }}>{status || "UNKNOWN"}</span>;
  };

  const BtnRun = ({ label, onClick, active, disabled = false }) => (
    <button onClick={onClick} disabled={active || disabled} style={{
      padding: "6px 16px", borderRadius: 2,
      border: `1px solid ${active ? "rgba(201,169,110,0.3)" : "#c9a96e"}`,
      background: active ? "rgba(201,169,110,0.05)" : "rgba(201,169,110,0.12)",
      color: active || disabled ? "rgba(201,169,110,0.4)" : "#c9a96e",
      ...mono, fontSize: 11, cursor: active ? "wait" : disabled ? "not-allowed" : "pointer", letterSpacing: "0.08em",
    }}>{active ? "RUNNING…" : label}</button>
  );

  return (
    <div className="page-pad" style={{ padding: "32px 40px", maxWidth: 1400, margin: "0 auto" }}>
      <div style={{ marginBottom: 28 }}>
        <h2 className="page-title" style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 28, color: "#c9a96e", letterSpacing: "0.05em", marginBottom: 4 }}>AUTONOMOUS AGENTS</h2>
        <p style={{ fontFamily: "Cormorant Garamond, serif", fontSize: 15, color: "rgba(232,224,208,0.5)", margin: 0 }}>
          Execution bot · AI commentary engine · Background data scheduler
        </p>
        <div style={{ marginTop: 12, padding: "12px 14px", background: "rgba(255,255,255,0.02)", border: "1px solid rgba(201,169,110,0.12)", borderRadius: 4 }}>
          <label htmlFor="agent-control-token" style={{ display: "block", ...mono, fontSize: 9, color: "rgba(232,224,208,0.55)", letterSpacing: "0.1em", marginBottom: 7 }}>
            AGENT CONTROL TOKEN · REQUIRED FOR ACTIONS
          </label>
          <input
            id="agent-control-token"
            type="password"
            autoComplete="off"
            value={controlToken}
            onChange={event => setControlToken(event.target.value)}
            placeholder="Enter the backend AGENT_CONTROL_TOKEN"
            style={{ width: "min(100%, 420px)", padding: "8px 10px", color: "#e8e0d0", background: "#070b12", border: "1px solid rgba(201,169,110,0.25)", borderRadius: 3, ...mono, fontSize: 11 }}
          />
          <div style={{ marginTop: 6, ...mono, fontSize: 9, color: "rgba(232,224,208,0.35)" }}>
            The token stays in this page’s memory and is sent only with agent control requests.
          </div>
        </div>
        {modeSwitchMsg && (
          <div role="status" style={{ marginTop: 8, ...mono, fontSize: 10, color: modeSwitchMsg.ok ? "#4ade80" : "#f87171" }}>
            {modeSwitchMsg.text}
          </div>
        )}
        {!localAgent && (
          <div style={{ marginTop: 12, padding: "10px 16px", background: "rgba(248,113,113,0.08)", border: "1px solid rgba(248,113,113,0.2)", borderRadius: 4, ...mono, fontSize: 11, color: "rgba(248,113,113,0.8)" }}>
            {apiBase
              ? `⚠ Backend not connected at ${apiBase} — check that this API URL is deployed and reachable.`
              : "⚠ Production API URL is not configured. Set VITE_API_URL to your deployed backend URL and rebuild the frontend."}
          </div>
        )}
      </div>

      <div className="grid-2col-agents" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}
>
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
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <BtnRun label="RUN CYCLE" onClick={triggerExecution} active={runningJob === "execution"} disabled={!hasControlToken} />
            {exec?.status === "CIRCUIT_BREAKER" && (
              <button onClick={resetCircuitBreaker} disabled={!hasControlToken} style={{
                padding: "6px 16px", borderRadius: 2,
                border: "1px solid rgba(248,113,113,0.6)",
                background: "rgba(248,113,113,0.1)",
                color: "#f87171",
                fontFamily: "JetBrains Mono, monospace", fontSize: 11,
                cursor: hasControlToken ? "pointer" : "not-allowed", opacity: hasControlToken ? 1 : 0.5, letterSpacing: "0.08em",
              }}>⚠ RESET CIRCUIT BREAKER</button>
            )}
          </div>

          {/* ── Trading Mode Toggle — always visible when Alpaca is connected ── */}
          <div style={{ marginTop: 16, padding: "14px 16px", background: "rgba(255,255,255,0.02)", border: "1px solid rgba(201,169,110,0.12)", borderRadius: 4 }}>
            <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 9, color: "rgba(232,224,208,0.4)", letterSpacing: "0.12em", marginBottom: 10 }}>TRADING MODE</div>

            {!exec?.alpaca_enabled ? (
              <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "rgba(232,224,208,0.3)" }}>
                Alpaca not connected — add keys to .env
              </div>
            ) : (
              <>
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
                    onClick={() => hasControlToken && !switchingMode && switchMode(currentMode === "live" ? "paper" : "live")}
                    style={{
                      position: "relative", width: 44, height: 22, borderRadius: 11,
                      background: currentMode === "live" ? "rgba(248,113,113,0.25)" : "rgba(74,222,128,0.2)",
                      border: `1px solid ${currentMode === "live" ? "rgba(248,113,113,0.5)" : "rgba(74,222,128,0.4)"}`,
                      cursor: switchingMode ? "wait" : hasControlToken ? "pointer" : "not-allowed",
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
                      { label: "EQUITY",       value: `$${parseFloat(exec.alpaca_account.equity || 0).toLocaleString(undefined, {maximumFractionDigits:0})}` },
                      { label: "CASH",         value: `$${parseFloat(exec.alpaca_account.cash || 0).toLocaleString(undefined, {maximumFractionDigits:0})}` },
                      { label: "BUYING POWER", value: `$${parseFloat(exec.alpaca_account.buying_power || 0).toLocaleString(undefined, {maximumFractionDigits:0})}` },
                    ].map(({ label, value }) => (
                      <div key={label}>
                        <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 8, color: "rgba(232,224,208,0.3)", letterSpacing: "0.1em", marginBottom: 2 }}>{label}</div>
                        <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 12, color: "rgba(232,224,208,0.75)" }}>{value}</div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

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
            <BtnRun label="GENERATE REPORT" onClick={triggerCommentary} active={runningJob === "commentary"} disabled={!hasControlToken} />
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
        {sched && !sched.apscheduler && (
          <div style={{ padding: "8px 12px", background: "rgba(250,204,21,0.06)", border: "1px solid rgba(250,204,21,0.2)", borderRadius: 4, ...mono, fontSize: 11, color: "rgba(250,204,21,0.7)", marginBottom: 14 }}>
            APScheduler not installed. Run: <code>pip install apscheduler</code> then restart.
          </div>
        )}
        {!sched && (
          <div style={{ padding: "8px 12px", background: "rgba(248,113,113,0.06)", border: "1px solid rgba(248,113,113,0.2)", borderRadius: 4, ...mono, fontSize: 11, color: "rgba(248,113,113,0.7)", marginBottom: 14 }}>
            Scheduler status unavailable because the backend is not connected.
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
                <BtnRun label="RUN NOW" onClick={() => triggerJob(job.id)} active={runningJob === job.id} disabled={!hasControlToken} />
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
  const [activeView, setActiveView] = useState("FOUNTRY");
  const [selectedSignal, setSelectedSignal] = useState(SIGNALS[0]);

  // ── Live data state ──────────────────────────────────────────────────────
  const [liveMetrics, setLiveMetrics]     = useState(null);
  const [macroSignals, setMacroSignals]   = useState(null);
  const [agentData, setAgentData]         = useState(null);
  const [marketQuote, setMarketQuote]     = useState(null);
  const [dataSource, setDataSource]       = useState("OFFLINE");
  const [isComputing, setIsComputing]     = useState(false);

  // No research values are shown until the backend provides them.
  const activeMetrics   = liveMetrics   || EMPTY_SIGNAL_METRICS;

  // ── Transform fountryhh API responses → frontend metrics shape ─────────────
  function transformSignalList(signals, details) {
    const metrics = {};
    for (const s of signals) {
      const id = s.signal_id || s.id;
      const detail = details[id] || {};
      const decay = detail.decay || [];
      const wf = detail.walkforward || [];
      const monthlyRets = detail.monthly_returns || [];
      const regimeRaw = detail.regime_ic || {};

      // Summarize observed IC periods; this is not a return backtest.
      const wfYears = wf.map(y => {
        return {
          year: y.year,
          ic: y.ic == null ? "—" : Number(y.ic).toFixed(4),
          annReturn: y.ann_return == null ? "—" : String(y.ann_return),
          cumPnL: "—",
          regime: y.regime || null,
          nMonths: Number(y.n_months || 0),
        };
      });

      // Map fountryhh regime keys → frontend keys (range_bound→range, inflationary→inflate)
      const asIC = value => value == null ? "—" : Number(value).toFixed(4);
      const regimeIC = {
        bull:    asIC(regimeRaw.bull),
        bear:    asIC(regimeRaw.bear),
        crisis:  asIC(regimeRaw.crisis),
        range:   asIC(regimeRaw.range_bound ?? regimeRaw.range),
        inflate: asIC(regimeRaw.inflationary ?? regimeRaw.inflate),
      };

      const returns = monthlyRets.map((r, i) => ({
        month: i + 1,
        ret: r.return ?? r.ret ?? 0,
        long: (r.return ?? r.ret ?? 0) * 1.5,
        short: (r.return ?? r.ret ?? 0) * -0.7,
      }));

      const md = s.max_drawdown;
      metrics[id] = {
        ic:          s.ic == null ? "—" : Number(s.ic).toFixed(4),
        icir:        s.icir == null ? "—" : Number(s.icir).toFixed(3),
        annualIR:    s.annual_ir == null ? "—" : Number(s.annual_ir).toFixed(2),
        grossSharpe: s.gross_sharpe == null ? "—" : Number(s.gross_sharpe).toFixed(2),
        netSharpe:   s.net_sharpe == null ? "—" : Number(s.net_sharpe).toFixed(2),
        maxDD:       md == null ? "—" : String(md),
        calmar:      "—",
        turnover:    s.turnover == null ? "—" : String(Math.round(s.turnover)),
        winRate:     s.pct_positive_ic == null ? "—" : Number(s.pct_positive_ic).toFixed(1),
        hitRate:     "—",
        capacity:    "—",
        tcCost:      s.tc_cost == null ? "—" : Number(s.tc_cost).toFixed(3),
        regimeIC,
        wfYears,
        decay:       decay.map(d => ({ lag: d.lag, ic: d.ic })),
        returns,
        promoted:    Boolean(s.promoted),
        nPeriods:    Number(s.n_periods || 0),
      };
    }
    return metrics;
  }

  useEffect(() => {
    async function fetchLive() {
      try {
        if (!API_BASE) return;
        // Render free tier cold-starts take up to 50s — use generous timeout + retry
        let healthRes;
        for (let attempt = 0; attempt < 3; attempt++) {
          try {
            healthRes = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(25000) });
            if (healthRes.ok) break;
          } catch {
            if (attempt === 2) return; // all retries exhausted
            await new Promise(r => setTimeout(r, 5000));
          }
        }
        if (!healthRes || !healthRes.ok) return;
        const health = await healthRes.json();
        try {
          const marketRes = await fetch(`${API_BASE}/api/market/live`, { signal: AbortSignal.timeout(10000) });
          if (marketRes.ok) {
            const snapshot = await marketRes.json();
            const quote = snapshot["^GSPC"]
              ? { ...snapshot["^GSPC"], ticker: "SPX" }
              : snapshot.SPY ? { ...snapshot.SPY, ticker: "SPY" } : null;
            setMarketQuote(quote);
          }
        } catch { /* Keep the last observed quote, if any. */ }
        if (!health.data_loaded) { setIsComputing(false); setDataSource("DATA UNAVAILABLE"); return; }

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

        const transformed = transformSignalList(signalList, details);
        // Missing backend signals stay explicitly unavailable; never fill the gaps with demo metrics.
        for (const signal of SIGNALS) {
          if (!transformed[signal.id]) transformed[signal.id] = {
            ic: "—", icir: "—", annualIR: "—", grossSharpe: "—", netSharpe: "—",
            maxDD: "—", calmar: "—", turnover: "—", winRate: "—", hitRate: "—",
            capacity: "—", tcCost: "—", regimeIC: { bull: "—", bear: "—", crisis: "—", range: "—", inflate: "—" },
            wfYears: [], decay: [], returns: [], promoted: false, nPeriods: 0,
          };
        }

        setLiveMetrics(transformed);
        setDataSource("CONNECTED");
        setIsComputing(false);

        // FRED macro signals (free, no key)
        const macroRes = await fetch(`${API_BASE}/api/macro/all`);
        if (macroRes.ok) {
          const macroData = await macroRes.json();
          if (macroData && typeof macroData === "object") setMacroSignals(macroData);
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
        // Keep research unavailable when the backend cannot be reached.
      }
    }

    fetchLive();
    const poll = setInterval(fetchLive, 60_000);
    return () => clearInterval(poll);
  }, []);

  const handleSelectSignal = useCallback((signal) => {
    setSelectedSignal(signal);
    setActiveView("SIGNAL LAB");
  }, []);

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

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
      }}>
        <div className="nav-inner" style={{ maxWidth: 1400, margin: "0 auto", display: "flex", alignItems: "center", height: 56, gap: 0, padding: "0 40px" }}>
          {/* Brand */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginRight: 40, flexShrink: 0 }}>
            <div style={{ position: "relative" }}>
              <div style={{ width: 28, height: 28, border: "1px solid #c9a96e", transform: "rotate(45deg)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 14, color: "#c9a96e", transform: "rotate(-45deg)" }}>α</div>
              </div>
            </div>
            <div>
              <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 16, color: "#c9a96e", letterSpacing: "0.2em" }}>FOUNTRY</div>
              <div className="nav-brand-sub" style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 8, color: "rgba(201,169,110,0.45)", letterSpacing: "0.2em" }}>EXPERIMENTAL QUANT RESEARCH</div>
            </div>
          </div>

          {/* Desktop nav tabs */}
          <div className="nav-tabs-desktop" style={{ display: "flex", gap: 0 }}>
            {VIEWS.map(v => (
              <button key={v}
                className={activeView === v ? "active-tab" : ""}
                onClick={() => { setActiveView(v); setMobileMenuOpen(false); }}
                style={{
                  padding: "0 18px", height: 56, border: "none",
                  background: "transparent",
                  borderBottom: `2px solid ${activeView === v ? "#c9a96e" : "transparent"}`,
                  color: activeView === v ? "#c9a96e" : "rgba(232,224,208,0.4)",
                  fontFamily: "JetBrains Mono, monospace", fontSize: 11, letterSpacing: "0.12em",
                  cursor: "pointer", transition: "all 0.2s",
                }}
                onMouseEnter={e => { if (activeView !== v) e.currentTarget.style.color = "rgba(232,224,208,0.75)"; }}
                onMouseLeave={e => { if (activeView !== v) e.currentTarget.style.color = "rgba(232,224,208,0.4)"; }}
              >{v}</button>
            ))}
          </div>

          {/* Spacer */}
          <div style={{ flex: 1 }}/>

          {/* Right: data source + observed market close */}
          <div className="nav-ticker" style={{ display: "flex", alignItems: "center", gap: 20, flexShrink: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {dataSource === "CONNECTED" && <span className="live-dot"/>}
              <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 9, letterSpacing: "0.12em",
                color: dataSource === "CONNECTED" ? "#4ade80" : "rgba(201,169,110,0.45)" }}>
                {isComputing ? "COMPUTING..." : dataSource}
              </span>
            </div>
            <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "rgba(232,224,208,0.5)" }}>
              {marketQuote?.ticker || "SPX"} <span
                title={marketQuote?.as_of ? `Latest reported daily close · ${marketQuote.as_of} · ${marketQuote.source || "market data"}` : "Market data unavailable"}
                style={{ color: marketQuote ? "#c9a96e" : "rgba(232,224,208,0.35)" }}
              >{Number.isFinite(marketQuote?.price)
                ? `${marketQuote.ticker === "SPX" ? marketQuote.price.toLocaleString(undefined, { maximumFractionDigits: 2 }) : `$${marketQuote.price.toFixed(2)}`}${Number.isFinite(marketQuote.change) ? ` (${marketQuote.change > 0 ? "+" : ""}${marketQuote.change.toFixed(2)}%)` : ""}`
                : "—"}</span>
            </div>
            <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11 }}>
              P&amp;L <span style={{ color: "rgba(232,224,208,0.35)" }}>—</span>
            </div>
          </div>

          {/* Mobile hamburger */}
          <button className="mobile-menu-btn" onClick={() => setMobileMenuOpen(o => !o)}>{"☰"}</button>
        </div>

        {/* Mobile nav dropdown */}
        <div className={`nav-tabs-mobile${mobileMenuOpen ? " open" : ""}`}>
          {VIEWS.map(v => (
            <button key={v}
              className={activeView === v ? "active-tab" : ""}
              onClick={() => { setActiveView(v); setMobileMenuOpen(false); }}
              style={{
                border: "none", background: "transparent",
                color: activeView === v ? "#c9a96e" : "rgba(232,224,208,0.5)",
                fontFamily: "JetBrains Mono, monospace", fontSize: 12, letterSpacing: "0.1em",
                cursor: "pointer",
              }}
            >{v}</button>
          ))}
        </div>
      </nav>

      {/* MAIN CONTENT */}
      <main style={{ position: "relative", zIndex: 1 }}>
        <div className="fade-in" key={activeView}>
          {activeView === "FOUNTRY"     && (dataSource === "CONNECTED" ? <FoundryOverview onSelectSignal={handleSelectSignal} metrics={activeMetrics}/> : <UnavailablePanel title="Research results unavailable" message="Connect the backend to view measured signals. Synthetic demo performance has been removed."/>)}
          {activeView === "SIGNAL LAB"  && (dataSource === "CONNECTED" ? <SignalLab signal={selectedSignal} metrics={activeMetrics}/> : <UnavailablePanel title="Signal research unavailable" message="Connect the backend to view results computed from market data."/>)}
          {activeView === "STRESS TEST" && <UnavailablePanel title="Regime stress results unavailable" message="No date-aligned historical regime-conditioned returns are implemented yet."/>}
          {activeView === "EXECUTION"   && <UnavailablePanel title="Execution analytics unavailable" message="This view has no verified broker fill and transaction cost feed connected."/>}
          {activeView === "PORTFOLIO"   && <UnavailablePanel title="Portfolio performance unavailable" message="No validated point-in-time, after-cost portfolio backtest is available yet."/>}
          {activeView === "AGENTS"      && <AgentsDashboard agentData={agentData} apiBase={API_BASE}/>}
        </div>
      </main>

      <footer style={{ borderTop: "1px solid rgba(201,169,110,0.08)", padding: "16px 40px", marginTop: 60 }}>
        <div style={{ maxWidth: 1400, margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(201,169,110,0.4)" }}>
            FOUNTRY v2.0
          </div>
          <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "rgba(232,224,208,0.2)" }}>
            Experimental research · no validated live strategy
          </div>
        </div>
      </footer>
    </div>
  );
}
