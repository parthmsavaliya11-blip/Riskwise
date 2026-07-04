import { useEffect, useMemo, useState } from "react";
import { getJSON, inr, num } from "../api/client";
import { AlertBanner, Badge, Card, Field, NumberInput } from "../components/ui";
import PayoffChart from "../components/PayoffChart";
import Explainer from "../components/Explainer";

const INDICES = ["NIFTY", "BANKNIFTY", "SENSEX"];
const VIEWS = [
  { id: "bullish", label: "Bullish" },
  { id: "bearish", label: "Bearish" },
  { id: "neutral", label: "Neutral" },
  { id: "volatile", label: "Big move" },
];
const CONVICTIONS = ["low", "medium", "high"];

function Segmented({ options, value, onChange }) {
  return (
    <div className="flex rounded-lg border border-hairline bg-elevated p-1">
      {options.map((o) => {
        const id = typeof o === "string" ? o : o.id;
        const label = typeof o === "string" ? o : o.label;
        return (
          <button
            key={id}
            onClick={() => onChange(id)}
            className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium capitalize transition-colors ${
              value === id ? "bg-card text-headline" : "text-muted-strong"
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

function Metric({ label, value, tone = "default", hint }) {
  const color = { default: "text-body", up: "text-up", down: "text-down", gold: "text-gold" }[tone];
  return (
    <div className="rounded-lg border border-hairline bg-elevated/40 p-3">
      <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-0.5 text-lg font-semibold tnum ${color}`}>{value}</p>
      {hint && <p className="text-[11px] text-muted">{hint}</p>}
    </div>
  );
}

export default function Options() {
  const [form, setForm] = useState({
    index: "NIFTY",
    view: "bullish",
    conviction: "high",
    days: "30",
    budget: "50000",
  });
  const [data, setData] = useState(null);
  const [selectedKey, setSelectedKey] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  async function load(f) {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams({
        index: f.index,
        view: f.view,
        conviction: f.conviction,
        days_to_expiry: f.days || "30",
      });
      if (f.budget) qs.set("budget", f.budget);
      const res = await getJSON(`/api/options?${qs.toString()}`);
      setData(res);
      const rec = res.candidates.find((c) => c.recommended) || res.candidates[0];
      setSelectedKey(rec?.key ?? null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // Reload whenever the inputs change.
  useEffect(() => {
    load(form);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.index, form.view, form.conviction, form.days, form.budget]);

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  const selected = useMemo(
    () => data?.candidates.find((c) => c.key === selectedKey) ?? null,
    [data, selectedKey],
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-headline">Options Strategy</h1>
        <p className="mt-1 text-sm text-muted">
          Tell it your view; it ranks the strategies that fit and shows the payoff,
          breakevens and Greeks for each.
        </p>
      </div>

      {error && <AlertBanner tone="breach" title="Couldn't load strategies">{error}</AlertBanner>}

      {/* Controls */}
      <Card title="Your view">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          <Field label="Index"><Segmented options={INDICES} value={form.index} onChange={(v) => set("index", v)} /></Field>
          <Field label="Market view"><Segmented options={VIEWS} value={form.view} onChange={(v) => set("view", v)} /></Field>
          <Field label="Conviction"><Segmented options={CONVICTIONS} value={form.conviction} onChange={(v) => set("conviction", v)} /></Field>
          <Field label="Days to expiry"><NumberInput value={form.days} onChange={(v) => set("days", v)} min="1" max="365" /></Field>
          <Field label="Budget / capital" hint="Used to flag affordable strategies."><NumberInput value={form.budget} onChange={(v) => set("budget", v)} suffix="₹" /></Field>
        </div>
        {data && (
          <p className="mt-4 text-xs text-muted">
            {data.index} spot <span className="text-body tnum">{num(data.spot)}</span> · IV{" "}
            <span className="text-body tnum">{data.iv_pct}%</span> · lot{" "}
            <span className="text-body tnum">{data.lot_size}</span> · {data.days_to_expiry} days to expiry
          </p>
        )}
      </Card>

      {loading && <p className="text-sm text-muted">Pricing strategies…</p>}

      {data && !loading && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[300px_1fr]">
          {/* Ranked list */}
          <div className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted">
              Ranked for your view
            </p>
            {data.candidates.map((c) => (
              <button
                key={c.key}
                onClick={() => setSelectedKey(c.key)}
                className={`w-full rounded-xl border p-4 text-left transition-colors ${
                  c.key === selectedKey
                    ? "border-gold bg-card"
                    : "border-hairline bg-card hover:border-muted/40"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-body">{c.name}</span>
                  {c.recommended && <Badge kind="ok">top pick</Badge>}
                </div>
                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                  {c.max_loss_unbounded ? (
                    <Badge kind="breach">⚠ unlimited risk</Badge>
                  ) : (
                    <span className="text-muted-strong">
                      Risk:Reward{" "}
                      <span className="tnum text-body">
                        {c.reward_risk ? `1:${c.reward_risk}` : "∞"}
                      </span>
                    </span>
                  )}
                  {!c.affordable && !c.max_loss_unbounded && <Badge kind="over">over budget</Badge>}
                  <Badge kind="neutral">{c.net_type}</Badge>
                </div>
              </button>
            ))}
          </div>

          {/* Selected detail */}
          {selected && (
            <Card>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-xl font-bold text-headline">{selected.name}</h2>
                  <p className="mt-1 max-w-xl text-sm text-muted">{selected.summary}</p>
                </div>
                {selected.recommended && <Badge kind="ok">recommended</Badge>}
              </div>

              <div className="mt-5 rounded-xl border border-hairline bg-elevated/30 p-3">
                <PayoffChart
                  curve={selected.payoff_curve}
                  breakevens={selected.breakevens}
                  spot={data.spot}
                />
              </div>

              <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Metric
                  label="Max profit"
                  value={selected.max_profit_unbounded ? "Unlimited" : inr(selected.max_profit)}
                  tone="up"
                />
                <Metric
                  label="Max loss"
                  value={selected.max_loss_unbounded ? "Unlimited" : inr(selected.max_loss)}
                  tone="down"
                />
                <Metric
                  label={selected.net_type === "debit" ? "Net cost (debit)" : "Net credit"}
                  value={inr(Math.abs(selected.net_premium))}
                  tone={selected.net_type === "credit" ? "up" : "default"}
                />
                <Metric
                  label="Breakeven"
                  value={selected.breakevens.map((b) => num(b)).join(" / ")}
                  tone="gold"
                />
              </div>

              {/* Greeks */}
              <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Metric label="Delta" value={num(selected.greeks.delta, { decimals: 1 })} hint="per ₹1 index move ×lot" />
                <Metric label="Theta / day" value={inr(selected.greeks.theta)} hint="time decay" />
                <Metric label="Vega / 1% IV" value={inr(selected.greeks.vega)} hint="vol sensitivity" />
                <Metric label="Capital req." value={selected.capital_required == null ? "Margin" : inr(selected.capital_required)} />
              </div>

              {/* Legs */}
              <div className="mt-5">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">Legs</p>
                <div className="overflow-hidden rounded-lg border border-hairline">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-muted">
                        <th className="px-4 py-2 font-medium">Action</th>
                        <th className="px-4 py-2 font-medium">Type</th>
                        <th className="px-4 py-2 text-right font-medium">Strike</th>
                        <th className="px-4 py-2 text-right font-medium">Lots</th>
                        <th className="px-4 py-2 text-right font-medium">Premium</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selected.legs.map((leg, i) => (
                        <tr key={i} className="border-b border-hairline/50 last:border-0">
                          <td className={`px-4 py-2 font-medium ${leg.action === "Buy" ? "text-up" : "text-down"}`}>
                            {leg.action}
                          </td>
                          <td className="px-4 py-2 capitalize text-body">{leg.kind}</td>
                          <td className="px-4 py-2 text-right tnum text-body">{num(leg.strike)}</td>
                          <td className="px-4 py-2 text-right tnum text-body">{leg.qty}</td>
                          <td className="px-4 py-2 text-right tnum text-muted-strong">{leg.premium}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="mt-5">
                <Explainer
                  module="options strategy"
                  data={{
                    index: data.index, spot: data.spot, iv_pct: data.iv_pct,
                    days_to_expiry: data.days_to_expiry, view: data.view, strategy: selected,
                  }}
                />
              </div>

              <p className="mt-5 text-xs text-muted">{data.disclaimer}</p>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
