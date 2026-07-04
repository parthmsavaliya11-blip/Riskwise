import { useEffect, useState } from "react";
import { bucketColor, getJSON, inr, num, pct } from "../api/client";
import { AlertBanner, Badge, BucketScope, Card, Field, NumberInput, StatCard } from "../components/ui";
import Explainer from "../components/Explainer";

const SECTOR_COLOR = {
  Financials: "#3B82F6",
  IT: "#0ECB81",
  Energy: "#F59E0B",
  Auto: "#F6465D",
  Pharma: "#14B8A6",
  "FMCG/Consumer": "#A855F7",
  Metals: "#94A3B8",
  "Infra/Cement": "#F97316",
  Telecom: "#EC4899",
  Index: "#FCD535",
  Other: "#707A8A",
};

// Compact equity-curve line chart with the max-drawdown trough marked.
function EquityChart({ series, troughDate, height = 180 }) {
  if (!series || series.length < 2) return null;
  const W = 640;
  const H = height;
  const padL = 56;
  const padR = 12;
  const padT = 12;
  const padB = 22;
  const vals = series.map((p) => p.value);
  const vMin = Math.min(...vals);
  const vMax = Math.max(...vals);
  const pad = (vMax - vMin) * 0.08 || 1;
  const sx = (i) => padL + (i / (series.length - 1)) * (W - padL - padR);
  const sy = (v) => padT + ((vMax + pad - v) / (vMax - vMin + 2 * pad)) * (H - padT - padB);
  const line = series.map((p, i) => `${sx(i)},${sy(p.value)}`).join(" ");
  const area = `M ${sx(0)},${H - padB} L ${line.replace(/ /g, " L ")} L ${sx(series.length - 1)},${H - padB} Z`;
  const troughIdx = series.findIndex((p) => p.date === troughDate);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Equity curve">
      <path d={area} fill="var(--color-up)" opacity="0.10" />
      <polyline points={line} fill="none" stroke="var(--color-up)" strokeWidth="2" />
      {troughIdx >= 0 && (
        <>
          <circle cx={sx(troughIdx)} cy={sy(series[troughIdx].value)} r="4" fill="var(--color-down)" />
          <text x={sx(troughIdx)} y={sy(series[troughIdx].value) - 8} fill="var(--color-down)" fontSize="10" textAnchor="middle">
            max DD
          </text>
        </>
      )}
      <text x={padL - 6} y={sy(vMax) + 4} fill="var(--color-muted)" fontSize="10" textAnchor="end">{inr(vMax)}</text>
      <text x={padL - 6} y={sy(vMin) + 4} fill="var(--color-muted)" fontSize="10" textAnchor="end">{inr(vMin)}</text>
      <text x={padL} y={H - 6} fill="var(--color-muted)" fontSize="10">{series[0].date}</text>
      <text x={W - padR} y={H - 6} fill="var(--color-muted)" fontSize="10" textAnchor="end">{series[series.length - 1].date}</text>
    </svg>
  );
}

function CorrHeatmap({ symbols, matrix }) {
  if (!symbols?.length || !matrix?.length) {
    return <p className="text-sm text-muted">Not enough price history for a correlation matrix.</p>;
  }
  const cellColor = (v) =>
    v >= 0
      ? `rgba(59,130,246,${(v * 0.85).toFixed(2)})`   // info-blue scale for positive
      : `rgba(112,122,138,0.15)`;                      // muted for negative (avoid harsh red)
  return (
    <div className="overflow-x-auto">
      <table className="border-separate" style={{ borderSpacing: 2 }}>
        <thead>
          <tr>
            <th></th>
            {symbols.map((s) => (
              <th key={s} className="px-1 pb-1 text-[10px] font-medium text-muted">
                {s.slice(0, 5)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}>
              <td className="pr-2 text-right text-[10px] font-medium text-muted">{symbols[i].slice(0, 8)}</td>
              {row.map((v, j) => (
                <td
                  key={j}
                  title={`${symbols[i]} vs ${symbols[j]}: ${v}`}
                  className="h-9 w-12 rounded text-center text-[11px] tnum text-body"
                  style={{ backgroundColor: i === j ? "var(--color-elevated)" : cellColor(v) }}
                >
                  {v.toFixed(2)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Bars({ items, colorFor, labelKey }) {
  const max = Math.max(...items.map((i) => i.weight_pct), 1);
  return (
    <div className="space-y-2.5">
      {items.map((it) => (
        <div key={it[labelKey]}>
          <div className="mb-1 flex justify-between text-sm">
            <span className="flex items-center gap-2 text-body">
              <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: colorFor(it) }} />
              {it[labelKey]}
            </span>
            <span className="tnum text-muted-strong">{inr(it.value)} · {pct(it.weight_pct)}</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-elevated">
            <div className="h-full rounded-full" style={{ width: `${(it.weight_pct / max) * 100}%`, backgroundColor: colorFor(it) }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function Risk({ initialBucket = "" }) {
  const [form, setForm] = useState({ confidence: "95", limit: "20000", bucket: initialBucket });
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  async function load(f) {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams({ confidence: f.confidence });
      if (f.limit) qs.set("daily_loss_limit", f.limit);
      if (f.bucket) qs.set("bucket", f.bucket);
      setData(await getJSON(`/api/risk?${qs.toString()}`));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(form);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.confidence, form.limit, form.bucket]);

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  const conc = data?.concentration;
  const v = data?.var;
  const dd = data?.drawdown;
  const corr = data?.correlation;
  const guard = data?.guardrail;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold text-headline">Risk Analytics</h1>
          <p className="mt-1 text-sm text-muted">
            {form.bucket
              ? `Risk for your ${form.bucket} sub-portfolio only — concentration, VaR and drawdown for those holdings.`
              : "Hidden concentration, correlation clusters, potential daily loss, and drawdown across your whole portfolio."}
          </p>
        </div>
        <BucketScope buckets={data?.available_buckets} value={form.bucket} onChange={(b) => set("bucket", b)} />
      </div>

      {error && <AlertBanner tone="breach" title="Couldn't load risk analytics">{error}</AlertBanner>}
      {loading && <p className="text-sm text-muted">Crunching risk metrics…</p>}

      {data && !loading && (
        <>
          {/* Concentration */}
          {conc?.flags?.length > 0 && (
            <AlertBanner tone="warn" title="Concentration warnings">
              <ul className="list-disc space-y-0.5 pl-4">
                {conc.flags.map((f, i) => <li key={i}>{f}</li>)}
              </ul>
            </AlertBanner>
          )}

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card title="Concentration by holding" subtitle={`Top holding ${pct(conc.top1_pct)} · top 3 ${pct(conc.top3_pct)} · HHI ${conc.hhi}`}>
              <Bars items={conc.holdings} labelKey="symbol" colorFor={(it) => bucketColor(it.symbol)} />
            </Card>
            <Card title="Sector exposure">
              <Bars items={conc.sectors} labelKey="sector" colorFor={(it) => SECTOR_COLOR[it.sector] || "#707A8A"} />
            </Card>
          </div>

          {/* Value at Risk */}
          <Card
            title="Value at Risk (1 day)"
            subtitle="The loss you might exceed on a bad day, at the chosen confidence."
            right={
              <div className="flex rounded-lg border border-hairline bg-elevated p-1">
                {["90", "95", "99"].map((c) => (
                  <button key={c} onClick={() => set("confidence", c)}
                    className={`rounded-md px-3 py-1 text-xs font-medium ${form.confidence === c ? "bg-card text-headline" : "text-muted-strong"}`}>
                    {c}%
                  </button>
                ))}
              </div>
            }
          >
            {v?.available ? (
              <>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <StatCard label={`Historical VaR ${v.confidence}%`} value={inr(v.historical_var)} sub={`${v.historical_var_pct}% of portfolio`} tone="down" />
                  <StatCard label="Parametric VaR" value={inr(v.parametric_var)} sub={`${v.parametric_var_pct}%`} tone="down" />
                  <StatCard label="CVaR (tail avg)" value={inr(v.cvar)} sub={`${v.cvar_pct}%`} tone="down" />
                  <StatCard label="Daily volatility" value={pct(v.daily_vol_pct)} />
                </div>
                <p className="mt-3 text-sm text-muted">
                  On a bad day ({v.confidence}% confidence) you could lose more than{" "}
                  <span className="font-semibold text-body">{inr(v.historical_var)}</span>, based on{" "}
                  {v.n_days} days of history.
                </p>
              </>
            ) : (
              <p className="text-sm text-muted">Need more price history to estimate VaR.</p>
            )}
          </Card>

          {/* Drawdown */}
          <Card title="Drawdown" subtitle="How far the portfolio has fallen from its peak.">
            {dd?.available ? (
              <>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <StatCard label="Current drawdown" value={pct(dd.current_drawdown_pct)} tone={dd.current_drawdown_pct < 0 ? "down" : "up"} />
                  <StatCard label="Max drawdown" value={pct(dd.max_drawdown_pct)} tone="down" />
                  <StatCard label="Peak value" value={inr(dd.peak_value)} />
                  <StatCard label="Current value" value={inr(dd.current_value)} />
                </div>
                <div className="mt-4 rounded-xl border border-hairline bg-elevated/30 p-3">
                  <EquityChart series={dd.series} troughDate={dd.trough_date} />
                </div>
              </>
            ) : (
              <p className="text-sm text-muted">Need more price history to compute drawdown.</p>
            )}
          </Card>

          {/* Correlation */}
          <Card title="Correlation" subtitle="Holdings that move together hide diversification you think you have.">
            <CorrHeatmap symbols={corr?.symbols} matrix={corr?.matrix} />
            {corr?.high_pairs?.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {corr.high_pairs.map((p, i) => (
                  <Badge key={i} kind="over">{p.a} ↔ {p.b}: {p.corr}</Badge>
                ))}
              </div>
            )}
          </Card>

          {/* Daily-loss guardrail */}
          <Card title="Daily-loss guardrail" subtitle="A circuit-breaker: set the most you'll allow yourself to lose in a day.">
            <div className="flex flex-wrap items-end gap-4">
              <Field label="Daily loss cap">
                <NumberInput value={form.limit} onChange={(v) => set("limit", v)} suffix="₹" min="0" />
              </Field>
              <p className="text-xs text-muted">
                Today's P&L (last session):{" "}
                <span className={`tnum ${(data.day_pnl ?? 0) >= 0 ? "text-up" : "text-down"}`}>{inr(data.day_pnl)}</span>
              </p>
            </div>
            {guard?.configured && (
              <div className="mt-4">
                <AlertBanner
                  tone={guard.status === "breached" ? "breach" : guard.status === "approaching" ? "warn" : "ok"}
                  title={
                    guard.status === "breached" ? "Daily loss cap breached — stop trading"
                      : guard.status === "approaching" ? "Approaching your daily loss cap"
                      : "Within your daily loss cap"
                  }
                >
                  Used {pct(guard.used_pct, 0)} of the {inr(guard.limit_amount)} cap · {inr(guard.remaining)} of buffer left.
                </AlertBanner>
              </div>
            )}
          </Card>

          <Explainer module="risk analytics" data={data} />

          <p className="text-xs text-muted">{data.disclaimer}</p>
        </>
      )}
    </div>
  );
}
