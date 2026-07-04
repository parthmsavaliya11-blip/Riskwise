import { useEffect, useRef, useState } from "react";
import { bucketColor, getJSON, inr, num, pct } from "../api/client";
import {
  AlertBanner,
  Badge,
  BucketScope,
  Button,
  Card,
  Field,
  NumberInput,
} from "../components/ui";
import Explainer from "../components/Explainer";

const INDICES = ["NIFTY", "BANKNIFTY", "SENSEX"];

// Horizontal 0–2 beta meter with a gold marker (design-brief beta-gauge).
function BetaGauge({ beta }) {
  const clamped = Math.max(0, Math.min(beta, 2));
  const left = (clamped / 2) * 100;
  return (
    <div className="mt-2">
      <div className="relative h-3 w-full rounded-full bg-elevated">
        {/* 1.0 reference tick (moves exactly with the market) */}
        <div className="absolute top-[-3px] h-[calc(100%+6px)] w-px bg-muted" style={{ left: "50%" }} />
        <div
          className="absolute top-[-3px] h-[calc(100%+6px)] w-1 rounded-full bg-gold"
          style={{ left: `calc(${left}% - 2px)` }}
          title={`Beta ${beta}`}
        />
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-muted">
        <span>0 · market-neutral</span>
        <span>1 · moves with market</span>
        <span>2 · amplified</span>
      </div>
    </div>
  );
}

// One card per hedging strategy: cost (debit red / credit green / margin muted),
// the protected floor and capped upside, what it protects, and what you give up.
function HedgeStrategyCard({ s }) {
  const costLabel =
    s.net_type === "margin"
      ? "Margin only"
      : s.net_type === "credit"
        ? `+${inr(Math.abs(s.net_cost))} credit`
        : inr(s.net_cost);
  const costTone =
    s.net_type === "margin" ? "text-muted-strong" : s.net_type === "credit" ? "text-up" : "text-down";
  return (
    <div className="rounded-xl border border-hairline bg-elevated/30 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-body">{s.name}</p>
          <p className="mt-0.5 text-xs text-muted">{s.instrument}</p>
        </div>
        <div className="text-right">
          <p className={`tnum font-semibold ${costTone}`}>{costLabel}</p>
          {s.net_type !== "margin" && (
            <p className="text-[11px] text-muted tnum">{pct(Math.abs(s.cost_pct))} of portfolio</p>
          )}
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {s.floor != null && <Badge kind="ok">Floor {num(s.floor)}</Badge>}
        {s.cap != null && <Badge kind="over">Cap {num(s.cap)}</Badge>}
      </div>
      <p className="mt-2 text-sm text-body">{s.protects}</p>
      <p className="mt-1 text-xs text-muted">Trade-off: {s.tradeoff}</p>
    </div>
  );
}

export default function Hedge({ initialBucket = "" }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  // Controls; empty string means "use the server default", filled from the first response.
  const [form, setForm] = useState({
    index: "NIFTY",
    index_price: "",
    lot_size: "",
    iv: "14",
    days: "30",
    bucket: initialBucket,
  });

  // Live-candle fetches take a moment, so a fast index/bucket switch can have several
  // requests in flight. Tag each and only let the most recent one update state, so an
  // earlier-but-slower response can't overwrite the index the user actually chose.
  const reqId = useRef(0);

  async function load(params, fillForm) {
    const myId = ++reqId.current;
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      qs.set("index", params.index);
      if (params.index_price) qs.set("index_price", params.index_price);
      if (params.lot_size) qs.set("lot_size", params.lot_size);
      if (params.iv) qs.set("iv", params.iv);
      if (params.days) qs.set("days_to_expiry", params.days);
      if (params.bucket) qs.set("bucket", params.bucket);
      const res = await getJSON(`/api/hedge?${qs.toString()}`);
      if (myId !== reqId.current) return; // superseded by a newer request
      setData(res);
      if (fillForm && !res.error) {
        setForm((f) => ({
          ...f,
          index_price: f.index_price || String(res.index_price),
          lot_size: f.lot_size || String(res.lot_size),
        }));
      }
    } catch (e) {
      if (myId === reqId.current) setError(e.message);
    } finally {
      if (myId === reqId.current) setLoading(false);
    }
  }

  // Initial load uses server defaults and fills the controls from the response.
  useEffect(() => {
    load({ index: "NIFTY", bucket: initialBucket }, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  // Switching index clears price/lot so the server defaults for that index apply.
  function onIndexChange(idx) {
    const next = { index: idx, index_price: "", lot_size: "", iv: form.iv, days: form.days, bucket: form.bucket };
    setForm(next);
    load(next, true);
  }

  function onBucketChange(b) {
    const next = { ...form, bucket: b };
    setForm(next);
    load(next, false);
  }

  const rows = data?.rows ?? [];
  const fut = data?.hedge_futures;
  const dq = data?.data_quality;
  const beta = data?.portfolio_beta ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold text-headline">Beta Hedge</h1>
          <p className="mt-1 text-sm text-muted">
            {form.bucket
              ? `Hedging just your ${form.bucket} sub-portfolio — beta and sizing for those holdings only.`
              : "How much your whole portfolio moves with the market, and what index position neutralises it."}
          </p>
        </div>
        <BucketScope buckets={data?.available_buckets} value={form.bucket} onChange={onBucketChange} />
      </div>

      {error && <AlertBanner tone="breach" title="Couldn't load hedge">{error}</AlertBanner>}
      {data?.error && <AlertBanner tone="warn" title="No data">{data.error}</AlertBanner>}

      {/* Controls */}
      <Card title="Index & contract">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <Field label="Index">
            <div className="flex rounded-lg border border-hairline bg-elevated p-1">
              {INDICES.map((idx) => (
                <button
                  key={idx}
                  onClick={() => onIndexChange(idx)}
                  className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                    form.index === idx ? "bg-card text-headline" : "text-muted-strong"
                  }`}
                >
                  {idx}
                </button>
              ))}
            </div>
          </Field>
          <Field label="Index price">
            <NumberInput value={form.index_price} onChange={(v) => set("index_price", v)} suffix="₹" />
          </Field>
          <Field label="Lot size">
            <NumberInput value={form.lot_size} onChange={(v) => set("lot_size", v)} min="1" />
          </Field>
          <Field label="Implied vol" hint="India VIX ≈ 13–15.">
            <NumberInput value={form.iv} onChange={(v) => set("iv", v)} suffix="%" min="1" />
          </Field>
          <Field label="Days to expiry">
            <NumberInput value={form.days} onChange={(v) => set("days", v)} min="1" max="365" />
          </Field>
        </div>
        <div className="mt-4">
          <Button onClick={() => load(form, false)} disabled={loading}>
            {loading ? "Calculating…" : "Recalculate"}
          </Button>
        </div>
      </Card>

      {data && !data.error && (
        <>
          {/* Portfolio beta + hedge headline */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card title="Portfolio beta" subtitle={`Value-weighted across ${rows.length} holdings vs ${data.index}.`}>
              <p className="text-4xl font-bold text-headline tnum">{beta.toFixed(2)}</p>
              <BetaGauge beta={beta} />
              <p className="mt-4 text-sm text-muted">
                A ₹{num(data.portfolio_value)} portfolio with beta {beta.toFixed(2)} behaves
                like {inr(data.portfolio_value * beta)} of {data.index}. A 1% {data.index}{" "}
                move is roughly a {pct(beta * 1, 2)} move in your portfolio.
              </p>
            </Card>

            <Card title="Hedge with index futures">
              <p className="text-sm text-muted">To neutralise market risk, short:</p>
              <p className="mt-1 text-4xl font-bold text-gold tnum">
                {num(fut.lots_to_short)}{" "}
                <span className="text-lg font-semibold text-body">
                  lot{fut.lots_to_short === 1 ? "" : "s"} of {data.index}
                </span>
              </p>
              <dl className="mt-4 space-y-2 text-sm">
                <Row label="Beta-adjusted exposure" value={inr(fut.beta_adjusted_exposure)} hint="value × beta" />
                <Row label="One contract" value={inr(fut.contract_value)} hint={`${num(data.lot_size)} × ₹${num(data.index_price)}`} />
                <Row label="Exact lots" value={num(fut.lots_exact, { decimals: 2 })} hint="rounded to nearest" />
                <Row
                  label="Residual after hedge"
                  value={`${inr(fut.residual_exposure)} (β ${fut.residual_beta.toFixed(2)})`}
                  hint="left unhedged by lot rounding"
                />
              </dl>
            </Card>
          </div>

          {/* Full hedging-strategy library */}
          <Card
            title="Hedging strategies compared"
            subtitle={`All sized to your beta-adjusted exposure. Option premiums priced from spot ${num(data.index_price)} · IV ${data.iv_pct}% · ${data.days_to_expiry} days. Educational, not advice.`}
          >
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {(data.hedge_strategies?.strategies ?? []).map((s) => (
                <HedgeStrategyCard key={s.key} s={s} />
              ))}
            </div>
          </Card>

          {/* Where the betas came from */}
          {dq?.history_source === "live" && (
            <p className="text-xs text-muted">
              Betas computed from <span className="text-up">live daily history</span> vs{" "}
              {data.index} (up to {dq.aligned_days} days per holding) — they update as your
              holdings change and differ by index.
            </p>
          )}

          {/* Data quality */}
          {dq?.missing_history?.length > 0 && (
            <AlertBanner tone="warn" title="A few holdings have no usable history">
              {dq.missing_history.join(", ")} — beta assumed to be{" "}
              {dq.assumed_beta_for_missing} (moves with the market).{" "}
              {dq.history_source === "live"
                ? "No live candles for these (e.g. options or a just-listed contract)."
                : "Add their history CSVs or turn on live data for a real beta."}
            </AlertBanner>
          )}

          {/* Per-stock beta table */}
          <Card title="Beta by holding" className="!p-0 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-muted">
                    <th className="px-6 py-3 font-medium">Symbol</th>
                    <th className="px-6 py-3 text-right font-medium">Value</th>
                    <th className="px-6 py-3 text-right font-medium">Weight</th>
                    <th className="px-6 py-3 text-right font-medium">Beta</th>
                    <th className="px-6 py-3 text-right font-medium">R²</th>
                    <th className="px-6 py-3 text-right font-medium">Fit</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={r.id ?? `${r.symbol}-${r.bucket}-${i}`} className="border-b border-hairline/60 last:border-0 hover:bg-elevated/50">
                      <td className="px-6 py-3 font-medium text-body">
                        <span className="flex items-center gap-2">
                          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: bucketColor(r.bucket) }} />
                          {r.symbol}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-right tnum text-body">{inr(r.value)}</td>
                      <td className="px-6 py-3 text-right tnum text-muted-strong">{pct(r.weight_pct)}</td>
                      <td className="px-6 py-3 text-right tnum font-medium text-body">
                        {r.beta === null ? `~${r.beta_used.toFixed(2)}` : r.beta.toFixed(2)}
                      </td>
                      <td className="px-6 py-3 text-right tnum text-muted-strong">
                        {r.r_squared === null ? "—" : r.r_squared.toFixed(2)}
                      </td>
                      <td className="px-6 py-3 text-right">
                        {!r.has_history ? (
                          <Badge kind="untracked">assumed</Badge>
                        ) : r.low_sample ? (
                          <span title={`Only ${r.n_days} days of history — beta is noisy`}>
                            <Badge kind="over">low data</Badge>
                          </span>
                        ) : r.r_squared >= 0.5 ? (
                          <Badge kind="ok">good</Badge>
                        ) : (
                          <Badge kind="over">weak</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Explainer module="hedge" data={data} />

          <p className="text-xs text-muted">{data.disclaimer}</p>
        </>
      )}
    </div>
  );
}

function Row({ label, value, hint }) {
  return (
    <div className="flex items-baseline justify-between border-b border-hairline/50 pb-2 last:border-0">
      <span className="text-muted-strong">
        {label}
        {hint && <span className="ml-2 text-xs text-muted">{hint}</span>}
      </span>
      <span className="tnum font-medium text-body">{value}</span>
    </div>
  );
}
