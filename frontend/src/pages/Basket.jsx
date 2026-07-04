import { useEffect, useRef, useState } from "react";
import { getJSON, inr, num, pctSigned, sendJSON } from "../api/client";
import { AlertBanner, Badge, Button, Card, Field, NumberInput } from "../components/ui";
import PayoffChart from "../components/PayoffChart";
import Explainer from "../components/Explainer";

const SELECT_CLS =
  "w-full rounded-lg border border-hairline bg-elevated px-3 py-2 text-sm text-body outline-none focus:ring-2 focus:ring-info/50 disabled:opacity-50";

function fmtExpiry(e) {
  const m = /^(\d{2})([A-Z]{3})(\d{4})$/.exec(e || "");
  return m ? `${m[1]} ${m[2][0]}${m[2].slice(1).toLowerCase()} ${m[3]}` : e;
}

let _uid = 0;
const nextUid = () => ++_uid;

// --- underlying search (optionable names: every one has futures too) ---------
function UnderlyingSearch({ onPick }) {
  const [q, setQ] = useState("");
  const [matches, setMatches] = useState([]);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const timer = useRef(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    const s = q.trim();
    if (s.length < 1) { setMatches([]); return; }
    timer.current = setTimeout(() => {
      getJSON(`/api/fno/underlyings?kind=opt&q=${encodeURIComponent(s)}&limit=12`)
        .then((d) => setMatches(d.underlyings || []))
        .catch(() => setMatches([]));
    }, 220);
    return () => timer.current && clearTimeout(timer.current);
  }, [q]);

  useEffect(() => {
    function onDoc(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <input
        value={q}
        onChange={(e) => { setQ(e.target.value.toUpperCase()); setOpen(true); }}
        onFocus={() => setOpen(true)}
        placeholder="Search an index or stock — e.g. RELIANCE, NIFTY"
        autoComplete="off"
        className="w-full rounded-lg border border-hairline bg-elevated px-3 py-2 text-sm text-body outline-none focus:ring-2 focus:ring-info/50"
      />
      {open && matches.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-hairline bg-card shadow-lg">
          {matches.map((u) => (
            <li key={u.name}>
              <button
                type="button"
                onClick={() => { onPick(u); setQ(u.name); setOpen(false); }}
                className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-elevated"
              >
                <span className="font-medium text-body">{u.name}</span>
                <span className="shrink-0 text-xs text-muted">1 lot = {u.lot_size}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// --- option chain overlay ----------------------------------------------------
// Open interest in compact Indian short form (K / L / Cr) — chain OI runs to millions.
function fmtOI(v) {
  if (v === null || v === undefined || Number.isNaN(v) || v === 0) return "—";
  if (v >= 1e7) return (v / 1e7).toFixed(2) + "Cr";
  if (v >= 1e5) return (v / 1e5).toFixed(2) + "L";
  if (v >= 1e3) return (v / 1e3).toFixed(1) + "K";
  return num(v);
}
const g1 = (v) => (v === null || v === undefined ? "—" : num(v, { decimals: 1 }));
const g2 = (v) => (v === null || v === undefined ? "—" : num(v, { decimals: 2 }));
const ivp = (v) => (v === null || v === undefined ? "—" : num(v, { decimals: 1 }) + "%");

function ChainModal({ chain, onAdd, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onMouseDown={onClose}>
      <div
        className="max-h-[86vh] w-full max-w-5xl overflow-hidden rounded-xl border border-hairline bg-card shadow-2xl"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-hairline px-5 py-3">
          <div>
            <h3 className="font-semibold text-headline">
              {chain.name} option chain · {fmtExpiry(chain.expiry)}
            </h3>
            <p className="text-xs text-muted">
              Spot ≈ {num(chain.ref_price, { decimals: 1 })} · 1 lot = {chain.lot_size}
              {chain.days_to_expiry != null && <> · {chain.days_to_expiry}d to expiry</>} ·
              click a premium (LTP) to add it · OI live, Greeks from premium
            </p>
          </div>
          <button onClick={onClose} className="text-muted hover:text-body" title="Close">✕</button>
        </div>
        <div className="overflow-auto" style={{ maxHeight: "74vh" }}>
          <table className="w-full text-xs">
            <thead className="sticky top-0 z-10 bg-card">
              <tr className="border-b border-hairline/60 text-[10px] uppercase tracking-wide text-muted">
                <th colSpan={5} className="px-2 py-1.5 text-center font-semibold text-up">Calls (CE)</th>
                <th className="px-2 py-1.5"></th>
                <th colSpan={5} className="px-2 py-1.5 text-center font-semibold text-down">Puts (PE)</th>
              </tr>
              <tr className="border-b border-hairline text-[10px] uppercase tracking-wide text-muted">
                <th className="px-2 py-1.5 text-right font-medium">OI</th>
                <th className="px-2 py-1.5 text-right font-medium">IV</th>
                <th className="px-2 py-1.5 text-right font-medium">Delta</th>
                <th className="px-2 py-1.5 text-right font-medium">Theta</th>
                <th className="px-2 py-1.5 text-right font-medium text-up">LTP</th>
                <th className="px-2 py-1.5 text-center font-medium">Strike</th>
                <th className="px-2 py-1.5 text-left font-medium text-down">LTP</th>
                <th className="px-2 py-1.5 text-left font-medium">Theta</th>
                <th className="px-2 py-1.5 text-left font-medium">Delta</th>
                <th className="px-2 py-1.5 text-left font-medium">IV</th>
                <th className="px-2 py-1.5 text-left font-medium">OI</th>
              </tr>
            </thead>
            <tbody>
              {chain.rows.map((r) => {
                const atm = r.strike === chain.atm_strike;
                const ce = r.ce, pe = r.pe;
                return (
                  <tr key={r.strike} className={`border-b border-hairline/40 tnum ${atm ? "bg-gold/5" : "hover:bg-elevated/40"}`}>
                    {/* Call side */}
                    <td className="px-2 py-1 text-right text-muted">{fmtOI(ce?.oi)}</td>
                    <td className="px-2 py-1 text-right text-muted">{ivp(ce?.iv)}</td>
                    <td className="px-2 py-1 text-right text-muted">{g2(ce?.delta)}</td>
                    <td className="px-2 py-1 text-right text-muted">{g1(ce?.theta)}</td>
                    <td className="px-2 py-1 text-right">
                      {ce && (
                        <button
                          onClick={() => onAdd({ type: "call", strike: r.strike, price: ce.ltp, token: ce.token, symbol: ce.symbol })}
                          className="rounded px-2 py-0.5 font-medium text-up hover:bg-up/15"
                          title="Add this call"
                        >
                          {num(ce.ltp, { decimals: 2 })}
                        </button>
                      )}
                    </td>
                    {/* Strike */}
                    <td className={`px-2 py-1 text-center font-semibold ${atm ? "text-gold" : "text-body"}`}>
                      {num(r.strike)}{atm && <span className="ml-1 text-[9px]">ATM</span>}
                    </td>
                    {/* Put side */}
                    <td className="px-2 py-1 text-left">
                      {pe && (
                        <button
                          onClick={() => onAdd({ type: "put", strike: r.strike, price: pe.ltp, token: pe.token, symbol: pe.symbol })}
                          className="rounded px-2 py-0.5 font-medium text-down hover:bg-down/15"
                          title="Add this put"
                        >
                          {num(pe.ltp, { decimals: 2 })}
                        </button>
                      )}
                    </td>
                    <td className="px-2 py-1 text-left text-muted">{g1(pe?.theta)}</td>
                    <td className="px-2 py-1 text-left text-muted">{g2(pe?.delta)}</td>
                    <td className="px-2 py-1 text-left text-muted">{ivp(pe?.iv)}</td>
                    <td className="px-2 py-1 text-left text-muted">{fmtOI(pe?.oi)}</td>
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

const LEG_LABEL = (l) =>
  l.type === "future" ? "Futures" : `${num(l.strike)} ${l.type === "call" ? "CE" : "PE"}`;

export default function Basket() {
  const [name, setName] = useState("");
  const [lotSize, setLotSize] = useState(1);
  const [expiries, setExpiries] = useState([]);
  const [expiry, setExpiry] = useState("");
  const [legs, setLegs] = useState([]);
  const [chain, setChain] = useState(null);
  const [busy, setBusy] = useState(""); // "future" | "chain" | "analyse" | "save"
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [saved, setSaved] = useState(false);

  function pickUnderlying(u) {
    setName(u.name);
    setLotSize(u.lot_size || 1);
    setLegs([]);
    setResult(null);
    setExpiry("");
    setError(null);
    getJSON(`/api/fno/expiries?name=${encodeURIComponent(u.name)}&kind=opt`)
      .then((d) => { setExpiries(d.expiries || []); setExpiry((d.expiries || [])[0] || ""); })
      .catch(() => setExpiries([]));
  }

  async function addFuture() {
    setBusy("future"); setError(null);
    try {
      const d = await getJSON(`/api/fno/future?name=${encodeURIComponent(name)}&expiry=${expiry}`);
      const f = d.future;
      if (!f) throw new Error("No futures contract found for this underlying.");
      if (f.lot_size) setLotSize(f.lot_size);
      setLegs((ls) => [...ls, { uid: nextUid(), type: "future", side: "buy", strike: null,
        price: f.ltp || 0, lots: 1, token: f.token, exchange: f.exchange, tsym: f.symbol }]);
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  async function openChain() {
    setBusy("chain"); setError(null);
    try {
      const d = await getJSON(`/api/fno/chain?name=${encodeURIComponent(name)}&expiry=${expiry}&width=12`);
      if (d.lot_size) setLotSize(d.lot_size);
      setChain(d);
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  function addOptionLeg({ type, strike, price, token, symbol }) {
    setLegs((ls) => [...ls, { uid: nextUid(), type, side: "buy", strike, price: price || 0,
      lots: 1, token, exchange: chain?.exchange, tsym: symbol }]);
  }

  function updateLeg(uid, patch) {
    setLegs((ls) => ls.map((l) => (l.uid === uid ? { ...l, ...patch } : l)));
  }
  function removeLeg(uid) {
    setLegs((ls) => ls.filter((l) => l.uid !== uid));
  }

  const KIND = { future: "FUT", call: "CE", put: "PE" };
  async function addToPortfolio() {
    setBusy("save"); setError(null); setSaved(false);
    try {
      // A multi-leg basket is tagged so My Holdings / Dashboard / Portfolios show it as
      // ONE grouped holding. A single leg is just a normal holding (no basket wrapper).
      const isBasket = legs.length > 1;
      const basketId = isBasket
        ? (crypto?.randomUUID?.() || `b-${Date.now()}-${Math.random().toString(36).slice(2)}`)
        : null;
      const basketLabel = isBasket ? `${name} · ${fmtExpiry(expiry)}` : null;
      const positions = legs.map((l) => ({
        symbol: name,
        bucket: "F&O",
        quantity: (Number(l.lots) || 1) * (Number(lotSize) || 1),
        avg_price: Math.max(Number(l.price) || 0, 0.05), // backend requires > 0
        tradingsymbol: l.tsym || (l.type === "future" ? `${name} FUT`
          : `${name} ${l.strike} ${l.type === "call" ? "CE" : "PE"}`),
        exchange: l.exchange,
        token: l.token,
        lot_size: Number(lotSize) || 1,
        kind: KIND[l.type] || "FUT",
        side: l.side,
        basket_id: basketId,
        basket_label: basketLabel,
      }));
      await sendJSON("/api/positions/bulk", { positions });
      setSaved(true);
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  async function analyse() {
    setBusy("analyse"); setError(null); setResult(null); setSaved(false);
    try {
      const body = {
        name, expiry, lot_size: Number(lotSize) || 1,
        legs: legs.map((l) => ({
          type: l.type, side: l.side, lots: Number(l.lots) || 1,
          strike: l.strike, price: Number(l.price) || 0,
          token: l.token, exchange: l.exchange,
        })),
      };
      const res = await sendJSON("/api/basket/analyse", body);
      if (res.error) throw new Error(res.error);
      setResult(res);
    } catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  const ready = name && expiry;
  const canAnalyse = ready && legs.length > 0 && legs.every((l) => l.lots > 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-headline">Basket Order</h1>
        <p className="mt-1 text-sm text-muted">
          Build a multi-leg basket (futures + options) from the live option chain, then see its
          combined payoff and an AI read. <span className="text-muted-strong">Analysis only — place the
          actual order at your broker.</span>
        </p>
      </div>

      {error && <AlertBanner tone="breach" title="Something went wrong">{error}</AlertBanner>}

      {/* Builder */}
      <Card title="1 · Pick the underlying & expiry" subtitle="Search an index or stock that has F&O, then choose the expiry for this basket.">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Underlying" hint={name ? `1 lot = ${lotSize}` : undefined}>
            <UnderlyingSearch onPick={pickUnderlying} />
          </Field>
          <Field label="Expiry">
            <select
              className={SELECT_CLS}
              value={expiry}
              disabled={!name || expiries.length === 0}
              onChange={(e) => { setExpiry(e.target.value); setResult(null); }}
            >
              <option value="">{name ? "Select expiry" : "Pick an underlying first"}</option>
              {expiries.map((e) => <option key={e} value={e}>{fmtExpiry(e)}</option>)}
            </select>
          </Field>
          <Field label="Add legs">
            <div className="flex gap-2">
              <Button variant="secondary" onClick={addFuture} disabled={!ready || busy === "future"}>
                {busy === "future" ? "…" : "+ Add future"}
              </Button>
              <Button variant="secondary" onClick={openChain} disabled={!ready || busy === "chain"}>
                {busy === "chain" ? "…" : "Open option chain"}
              </Button>
            </div>
          </Field>
        </div>
      </Card>

      {/* Basket cart */}
      <Card
        title={`2 · Your basket (${legs.length} leg${legs.length === 1 ? "" : "s"})`}
        subtitle={name ? `${name} · ${expiry ? fmtExpiry(expiry) : ""} · 1 lot = ${lotSize}` : "Add futures or options above."}
      >
        {legs.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted">
            No legs yet. Use <span className="text-body">+ Add future</span> or{" "}
            <span className="text-body">Open option chain</span> to build your basket.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-muted">
                  <th className="px-3 py-2 font-medium">Leg</th>
                  <th className="px-3 py-2 font-medium">Side</th>
                  <th className="px-3 py-2 text-right font-medium">Lots</th>
                  <th className="px-3 py-2 text-right font-medium">Price (₹)</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {legs.map((l) => (
                  <tr key={l.uid} className="border-b border-hairline/50 last:border-0">
                    <td className="px-3 py-2 font-medium text-body">{LEG_LABEL(l)}</td>
                    <td className="px-3 py-2">
                      <div className="flex rounded-md border border-hairline bg-elevated p-0.5">
                        {["buy", "sell"].map((s) => (
                          <button
                            key={s}
                            onClick={() => updateLeg(l.uid, { side: s })}
                            className={`rounded px-2.5 py-1 text-xs font-medium capitalize ${
                              l.side === s
                                ? s === "buy" ? "bg-up/15 text-up" : "bg-down/15 text-down"
                                : "text-muted-strong"
                            }`}
                          >
                            {s}
                          </button>
                        ))}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-right">
                      <div className="ml-auto w-20">
                        <NumberInput value={l.lots} onChange={(v) => updateLeg(l.uid, { lots: v })} min="1" />
                      </div>
                    </td>
                    <td className="px-3 py-2 text-right">
                      <div className="ml-auto w-28">
                        <NumberInput value={l.price} onChange={(v) => updateLeg(l.uid, { price: v })} min="0" />
                      </div>
                    </td>
                    <td className="px-3 py-2 text-right">
                      <button onClick={() => removeLeg(l.uid)} className="text-muted hover:text-down" title="Remove">✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button onClick={analyse} disabled={!canAnalyse || busy === "analyse"}>
            {busy === "analyse" ? "Analysing…" : "Analyse basket"}
          </Button>
          <Button variant="secondary" onClick={addToPortfolio} disabled={!canAnalyse || busy === "save"}>
            {busy === "save" ? "Adding…" : "Add to portfolio"}
          </Button>
          <span className="text-xs text-muted">Payoff at expiry · max P/L · breakevens · Greeks</span>
        </div>
        {saved && (
          <div className="mt-3">
            <AlertBanner tone="info" title="Added to your portfolio">
              These {legs.length} leg{legs.length === 1 ? "" : "s"} are now in <span className="text-body">My Holdings</span> under the F&amp;O bucket (live prices). You still place the order at your broker.
            </AlertBanner>
          </div>
        )}
      </Card>

      {/* Results */}
      {result && (
        <>
          <Card title="3 · Payoff & risk" subtitle={`${result.name} · ${fmtExpiry(result.expiry)} · ${result.days_to_expiry} days to expiry`}>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Metric label="Net premium" value={`${inr(Math.abs(result.net_premium))}`} sub={result.net_type} tone={result.net_type === "credit" ? "up" : "default"} />
              <Metric
                label="Max profit"
                value={result.max_profit_unbounded ? "Unlimited" : inr(result.max_profit)}
                tone="up"
              />
              <Metric
                label="Max loss"
                value={result.max_loss_unbounded ? "Unlimited" : inr(Math.abs(result.max_loss))}
                tone={result.max_loss_unbounded ? "down" : "down"}
              />
              <Metric label="Breakeven(s)" value={result.breakevens.length ? result.breakevens.map((b) => num(b)).join(", ") : "—"} />
            </div>

            {result.margin_required != null && (
              <div className="mt-4 rounded-lg border border-hairline bg-elevated/30 p-4">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <p className="text-[11px] uppercase tracking-wide text-muted">Margin required (SPAN + exposure)</p>
                    <p className="mt-0.5 text-2xl font-bold text-headline tnum">{inr(result.margin_required)}</p>
                  </div>
                  {result.margin_saved != null && result.margin_saved > 0 && (
                    <div className="text-right">
                      <p className="text-[11px] uppercase tracking-wide text-muted">The hedge saves you</p>
                      <p className="mt-0.5 text-xl font-bold text-up tnum">{inr(result.margin_saved)}</p>
                      <p className="text-[11px] text-muted">naked would need {inr(result.margin_unhedged)}</p>
                    </div>
                  )}
                </div>
                <p className="mt-2 text-[11px] text-muted">
                  Live estimate from your broker's margin calculator — the exchange nets the hedge benefit. Actual may vary slightly at order time.
                </p>
              </div>
            )}

            <div className="mt-5">
              <PayoffChart curve={result.payoff_curve} breakevens={result.breakevens} spot={result.spot} />
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {["delta", "gamma", "theta", "vega"].map((k) => (
                <div key={k} className="rounded-lg border border-hairline bg-elevated/30 p-3">
                  <p className="text-[11px] uppercase tracking-wide text-muted">{k}</p>
                  <p className="mt-0.5 font-semibold text-body tnum">{num(result.greeks[k], { decimals: 2 })}</p>
                </div>
              ))}
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Badge kind="neutral">View: {result.view}</Badge>
              {result.max_loss_unbounded && <Badge kind="breach">Unlimited loss</Badge>}
            </div>

            <ul className="mt-4 space-y-1.5">
              {result.observations.map((o, i) => (
                <li key={i} className="flex gap-2 text-sm text-body">
                  <span className="text-gold">•</span>{o}
                </li>
              ))}
            </ul>

            {result.disclaimer && <p className="mt-4 text-xs text-muted">{result.disclaimer}</p>}
          </Card>

          <Explainer module="basket" data={result} label="Analyse with AI (incl. suggestions)" />
        </>
      )}

      {chain && (
        <ChainModal
          chain={chain}
          onAdd={addOptionLeg}
          onClose={() => setChain(null)}
        />
      )}
    </div>
  );
}

function Metric({ label, value, sub, tone = "default" }) {
  const toneText = { default: "text-headline", up: "text-up", down: "text-down" }[tone];
  return (
    <div className="rounded-lg border border-hairline bg-elevated/30 p-3">
      <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-0.5 font-semibold tnum ${toneText}`}>{value}</p>
      {sub && <p className="text-[11px] capitalize text-muted">{sub}</p>}
    </div>
  );
}
