import { Fragment, useEffect, useState } from "react";
import { bucketColor, getJSON, groupHoldings, inr, num, pctSigned, sendJSON } from "../api/client";
import { AlertBanner, Badge, Button, Card, Field, NumberInput } from "../components/ui";
import SymbolSearch from "../components/SymbolSearch";
import FnoPicker from "../components/FnoPicker";

const DEFAULT_BUCKETS = ["Long-term", "Swing", "F&O"];
const SOURCE_LABEL = { live: "live", manual: "your price", cost: "at cost" };

// Local (not UTC) YYYY-MM-DD — the close date defaults to today.
const todayISO = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

const blank = (bucket) => ({
  id: null, symbol: "", tradingsymbol: null, bucket,
  quantity: "", lots: "", avg_price: "", buy_date: todayISO(),
  token: null, exchange: null, lot_size: 1, kind: "EQ", side: "buy",
});

export default function Holdings({ buckets, onReload }) {
  const bucketNames = buckets && buckets.length ? buckets.map((b) => b.name) : DEFAULT_BUCKETS;
  const [data, setData] = useState(null);
  const [form, setForm] = useState(blank(bucketNames[0] || "Long-term"));
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [openBaskets, setOpenBaskets] = useState({}); // basket_id -> expanded?
  const [closing, setClosing] = useState({});         // position id -> { price, date, entry }
  const [closedMsg, setClosedMsg] = useState(null);   // success note after closing to journal

  const isFnO = form.bucket === "F&O";

  async function reload() {
    setData(await getJSON("/api/positions"));
  }
  useEffect(() => {
    reload().catch((e) => setError(e.message));
  }, []);

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }
  function resetForm() {
    setForm(blank(form.bucket));
  }

  // Switch segment: F&O searches contracts, others search stocks. Clear the selection.
  function pickBucket(b) {
    setForm({ ...blank(b) });
  }

  // Typing in the stock search box (before choosing) — clears any picked token.
  function onSymbolText(v) {
    setForm((f) => ({ ...f, symbol: v, tradingsymbol: null, token: null,
      exchange: null, lot_size: 1, kind: "EQ" }));
  }

  // Chose an instrument from the dropdown — capture its details for live price + lots.
  function pickInstrument(r) {
    setForm((f) => ({
      ...f, symbol: r.symbol, tradingsymbol: r.tradingsymbol || r.symbol,
      token: r.token, exchange: r.exchange, lot_size: r.lot_size || 1, kind: r.kind || "EQ",
    }));
  }

  // The F&O picker resolved (or cleared) a contract. symbol = underlying (NIFTY),
  // tradingsymbol = the full contract (NIFTY30JUN2620100CE).
  function onFnoResolve(c) {
    if (!c) {
      setForm((f) => ({ ...f, symbol: "", tradingsymbol: null, token: null,
        exchange: null, lot_size: 1, kind: "FUT" }));
      return;
    }
    setForm((f) => ({
      ...f, symbol: c.name || c.symbol, tradingsymbol: c.tradingsymbol || c.symbol,
      token: c.token, exchange: c.exchange, lot_size: c.lot_size || 1, kind: c.kind || "FUT",
    }));
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const qty = isFnO ? Number(form.lots) * Number(form.lot_size) : Number(form.quantity);
      const body = {
        symbol: form.symbol.trim(),
        bucket: form.bucket,
        quantity: qty,
        avg_price: Number(form.avg_price),
        buy_date: form.buy_date || null,
        tradingsymbol: form.tradingsymbol || null,
        exchange: form.exchange || null,
        token: form.token || null,
        lot_size: isFnO ? Number(form.lot_size) || 1 : 1,
        kind: isFnO ? form.kind || "FUT" : "EQ",
        side: isFnO ? form.side || "buy" : "buy",
      };
      if (form.id) await sendJSON(`/api/positions/${form.id}`, body, "PUT");
      else await sendJSON("/api/positions", body, "POST");
      resetForm();
      await reload();
      await onReload?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function edit(p) {
    const fno = p.kind && p.kind !== "EQ";
    setForm({
      id: p.id, symbol: p.symbol, tradingsymbol: p.tradingsymbol,
      bucket: p.bucket, quantity: fno ? "" : String(p.quantity),
      lots: fno ? String(p.lots ?? "") : "", avg_price: String(p.avg_price),
      buy_date: p.buy_date || "", token: p.token, exchange: p.exchange,
      lot_size: p.lot_size || 1, kind: p.kind || "EQ", side: p.side || "buy",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function remove(id) {
    setBusy(true);
    try {
      await sendJSON(`/api/positions/${id}`, {}, "DELETE");
      await reload();
      await onReload?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  // Close a holding straight into the Journal — exit date defaults to today.
  function startClose(p) {
    setClosedMsg(null);
    setError(null);
    setClosing((s) => ({ ...s, [p.id]: { price: "", date: todayISO(), entry: p.buy_date || "", qty: String(p.quantity) } }));
  }
  function setClose(id, field, value) {
    setClosing((s) => ({ ...s, [id]: { ...s[id], [field]: value } }));
  }
  function cancelClose(id) {
    setClosing((s) => ({ ...s, [id]: undefined }));
  }
  async function confirmClose(p) {
    const c = closing[p.id] || {};
    if (!Number(c.price)) return;
    // Partial sell is equity-only (not F&O / basket legs).
    const eqPartialOk = (p.kind || "EQ") === "EQ" && !p.basket_id;
    const sold = eqPartialOk ? Number(c.qty) : p.quantity;
    if (eqPartialOk && (!(sold > 0) || sold > p.quantity)) {
      setError(`Sell quantity must be between 1 and ${num(p.quantity)}.`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body = { exit_price: Number(c.price), exit_date: c.date || null };
      if (!p.buy_date) body.entry_date = c.entry || null;
      if (eqPartialOk) body.quantity = sold;
      await sendJSON(`/api/positions/${p.id}/close`, body, "POST");
      setClosing((s) => ({ ...s, [p.id]: undefined }));
      const left = p.quantity - sold;
      setClosedMsg(left > 0
        ? `Sold ${num(sold)} of ${p.symbol} and logged it to your Journal — ${num(left)} still held.`
        : `${p.tradingsymbol || p.symbol} closed and logged to your Journal as a closed trade.`);
      await reload();
      await onReload?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function toggleBasket(id) {
    setOpenBaskets((s) => ({ ...s, [id]: !s[id] }));
  }

  // Delete every leg of a saved basket in one action.
  async function removeBasket(item) {
    setBusy(true);
    setError(null);
    try {
      for (const leg of item.legs) {
        await sendJSON(`/api/positions/${leg.id}`, {}, "DELETE");
      }
      await reload();
      await onReload?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const positions = data?.positions ?? [];
  const usingSample = data?.using_sample;
  const canSave =
    form.symbol.trim() && form.avg_price && form.buy_date &&
    (isFnO ? form.lots && form.token && form.lot_size : form.quantity);
  const totalValue = positions.reduce((s, p) => s + p.current_value, 0);
  const totalPnl = positions.reduce((s, p) => s + p.pnl, 0);
  const items = groupHoldings(positions); // saved baskets shown as one expandable group

  // One holding row. `indented` styles it as a leg sitting inside an expanded basket.
  function legRow(p, indented = false) {
    return (
      <tr
        key={p.id}
        className={`border-b border-hairline/60 last:border-0 hover:bg-elevated/40 ${indented ? "bg-elevated/10" : ""}`}
      >
        <td className={`${indented ? "pl-12 pr-5" : "px-5"} py-3 font-medium text-body`}>
          <div>
            {indented && <span className="mr-1 text-muted">↳</span>}
            {p.kind && p.kind !== "EQ" ? p.tradingsymbol : p.symbol}
            {p.kind && p.kind !== "EQ" && p.side && (
              <span className={`ml-1.5 rounded px-1 py-0.5 text-[10px] font-semibold ${p.side === "sell" ? "bg-down/15 text-down" : "bg-up/15 text-up"}`}>
                {p.side === "sell" ? "SELL" : "BUY"}
              </span>
            )}
            {p.exchange && <span className="ml-1.5 text-[10px] text-muted">{p.exchange}</span>}
          </div>
          {/* F&O is leveraged: the value shown is Angel's margin (+ MTM), not the full
              contract value — spell out the leverage and what it actually controls. */}
          {p.kind && p.kind !== "EQ" && p.leverage != null && (
            <div className="mt-0.5 text-[10px] text-muted">
              {p.leverage}× leverage · controls {inr(p.notional)}
            </div>
          )}
        </td>
        <td className="px-5 py-3">
          <span className="flex items-center gap-1.5 text-muted-strong">
            <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: bucketColor(p.bucket) }} />
            {p.bucket}
          </span>
        </td>
        <td className="px-5 py-3 text-right tnum text-body">
          {p.kind && p.kind !== "EQ"
            ? `${num(p.lots)} lot${p.lots === 1 ? "" : "s"}`
            : num(p.quantity)}
        </td>
        <td className="px-5 py-3 text-right tnum text-muted-strong">{p.avg_price}</td>
        <td className="px-5 py-3 text-right">
          <span className="tnum text-body">{p.ltp}</span>
          <span className="ml-1 text-[10px] text-muted">{SOURCE_LABEL[p.price_source]}</span>
        </td>
        <td className="px-5 py-3 text-right tnum text-body">{inr(p.current_value)}</td>
        <td className={`px-5 py-3 text-right tnum font-medium ${p.pnl >= 0 ? "text-up" : "text-down"}`}>
          {inr(p.pnl)} <span className="text-xs">({pctSigned(p.pnl_pct)})</span>
        </td>
        <td className="px-5 py-3 text-right">
          <div className="flex items-center justify-end gap-2">
            {closing[p.id] !== undefined ? (
              <span className="flex items-center gap-1">
                {!p.buy_date && (
                  <input type="date" value={closing[p.id].entry} max={todayISO()}
                    onChange={(e) => setClose(p.id, "entry", e.target.value)} title="Buy date (none on file)"
                    className="rounded border border-hairline bg-elevated px-2 py-1 text-xs text-body outline-none" />
                )}
                {(p.kind || "EQ") === "EQ" && !p.basket_id && (
                  <input type="number" value={closing[p.id].qty} max={p.quantity} min="0"
                    onChange={(e) => setClose(p.id, "qty", e.target.value)} title={`Quantity to sell (you hold ${num(p.quantity)})`}
                    className="w-16 rounded border border-hairline bg-elevated px-2 py-1 text-xs text-body outline-none" />
                )}
                <input type="number" value={closing[p.id].price} onChange={(e) => setClose(p.id, "price", e.target.value)}
                  placeholder="sell ₹" className="w-20 rounded border border-hairline bg-elevated px-2 py-1 text-xs text-body outline-none" />
                <input type="date" value={closing[p.id].date} max={todayISO()}
                  onChange={(e) => setClose(p.id, "date", e.target.value)} title="Close date (today)"
                  className="rounded border border-hairline bg-elevated px-2 py-1 text-xs text-body outline-none" />
                <button onClick={() => confirmClose(p)} disabled={busy} className="text-up hover:opacity-80" title="Confirm — log to journal">✓</button>
                <button onClick={() => cancelClose(p.id)} className="text-muted hover:text-body" title="Cancel">✕</button>
              </span>
            ) : (
              <>
                <button onClick={() => edit(p)} className="text-xs text-gold hover:underline">Edit</button>
                <button onClick={() => startClose(p)} className="text-xs text-up hover:underline" title="Sell & log to journal">Close</button>
                <button onClick={() => remove(p.id)} className="text-muted hover:text-down" title="Delete">✕</button>
              </>
            )}
          </div>
        </td>
      </tr>
    );
  }

  // A saved basket: one summary row (totals across legs) that expands to its legs.
  function basketRow(item) {
    const open = !!openBaskets[item.basket_id];
    return (
      <Fragment key={`b-${item.basket_id}`}>
        <tr className="border-b border-hairline/60 bg-elevated/30 hover:bg-elevated/50">
          <td className="px-5 py-3 font-medium text-body">
            <button onClick={() => toggleBasket(item.basket_id)} className="flex items-center gap-2 text-left">
              <span className="text-muted">{open ? "▾" : "▸"}</span>
              <span>{item.label}</span>
              <span className="rounded bg-gold/15 px-1.5 py-0.5 text-[10px] font-semibold text-gold">
                BASKET · {item.legs.length} legs
              </span>
            </button>
          </td>
          <td className="px-5 py-3">
            <span className="flex items-center gap-1.5 text-muted-strong">
              <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: bucketColor(item.bucket) }} />
              {item.bucket}
            </span>
          </td>
          <td className="px-5 py-3 text-right tnum text-muted">{item.legs.length} legs</td>
          <td className="px-5 py-3 text-right tnum text-muted">—</td>
          <td className="px-5 py-3 text-right tnum text-muted">—</td>
          <td className="px-5 py-3 text-right tnum text-body">{inr(item.current_value)}</td>
          <td className={`px-5 py-3 text-right tnum font-medium ${item.pnl >= 0 ? "text-up" : "text-down"}`}>
            {inr(item.pnl)} <span className="text-xs">({pctSigned(item.pnl_pct)})</span>
          </td>
          <td className="px-5 py-3 text-right">
            <button onClick={() => removeBasket(item)} className="text-muted hover:text-down" title="Remove whole basket">✕</button>
          </td>
        </tr>
        {open && item.legs.map((p) => legRow(p, true))}
      </Fragment>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-headline">My Holdings</h1>
        <p className="mt-1 text-sm text-muted">
          Build your real portfolio. Search any NSE/BSE stock (or an F&O contract),
          enter what you paid — the current price is fetched live.
        </p>
      </div>

      {error && <AlertBanner tone="breach" title="Couldn't save">{error}</AlertBanner>}
      {closedMsg && <AlertBanner tone="ok" title="Closed & journaled">{closedMsg}</AlertBanner>}
      {usingSample && (
        <AlertBanner tone="info" title="You're viewing sample data">
          Add your holdings below and they'll replace the demo portfolio everywhere.
        </AlertBanner>
      )}

      {/* Add / edit */}
      <Card
        title={form.id ? "Edit holding" : "Add a holding"}
        subtitle={isFnO
          ? "F&O: search a futures/option contract, enter lots and the price you paid. Live price is automatic."
          : "Search any NSE/BSE stock, enter quantity and your buy price. Live price is automatic."}
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {/* Segment first, so the search knows stocks vs contracts */}
          <Field label="Segment">
            <div className="flex rounded-lg border border-hairline bg-elevated p-1">
              {bucketNames.map((b) => (
                <button
                  key={b}
                  onClick={() => pickBucket(b)}
                  className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                    form.bucket === b ? "bg-card text-headline" : "text-muted-strong"
                  }`}
                >
                  {b}
                </button>
              ))}
            </div>
          </Field>
          {isFnO ? (
            form.id ? (
              // Editing: the contract is fixed; only lots / price / date change.
              <Field label="Contract" hint={`${form.exchange || "NFO"} · 1 lot = ${form.lot_size}`}>
                <div className="rounded-lg border border-hairline bg-elevated px-3 py-2 text-sm text-body">
                  {form.tradingsymbol || form.symbol}
                </div>
              </Field>
            ) : (
              <FnoPicker onResolve={onFnoResolve} />
            )
          ) : (
            <Field label="Stock" hint={form.exchange || undefined}>
              <SymbolSearch
                value={form.symbol}
                kind="equity"
                onChange={onSymbolText}
                onSelect={pickInstrument}
              />
            </Field>
          )}
          {isFnO ? (
            <Field label="Lots" hint={form.token ? `${form.lots || 0} lot(s) = ${(Number(form.lots) || 0) * form.lot_size} units` : "Pick a contract first"}>
              <NumberInput value={form.lots} onChange={(v) => set("lots", v)} min="0" />
            </Field>
          ) : (
            <Field label="Quantity">
              <NumberInput value={form.quantity} onChange={(v) => set("quantity", v)} min="0" />
            </Field>
          )}
          {isFnO && (
            <Field label="Bought or sold?">
              <div className="flex rounded-lg border border-hairline bg-elevated p-1">
                {[["buy", "Bought (long)"], ["sell", "Sold (short)"]].map(([s, label]) => (
                  <button
                    key={s}
                    onClick={() => set("side", s)}
                    className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                      form.side === s
                        ? s === "buy" ? "bg-up/15 text-up" : "bg-down/15 text-down"
                        : "text-muted-strong"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </Field>
          )}
          <Field label={isFnO ? "Avg price paid (per unit)" : "Avg buy price"}>
            <NumberInput value={form.avg_price} onChange={(v) => set("avg_price", v)} suffix="₹" min="0" />
          </Field>
          <Field label="Buy date *">
            <input
              type="date"
              value={form.buy_date}
              max={todayISO()}
              onChange={(e) => set("buy_date", e.target.value)}
              className="w-full rounded-lg border border-hairline bg-elevated px-3 py-2 text-sm text-body outline-none focus:ring-2 focus:ring-info/50"
            />
          </Field>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <Button onClick={save} disabled={!canSave || busy}>
            {busy ? "Saving…" : form.id ? "Update holding" : "Add holding"}
          </Button>
          {form.id && <Button variant="ghost" onClick={resetForm}>Cancel</Button>}
          <span className="text-xs text-muted">Current price is fetched live from the market feed.</span>
        </div>
      </Card>

      {/* Holdings table */}
      <Card
        title={`Your holdings (${positions.length})`}
        subtitle={positions.length ? `Total value ${inr(totalValue)} · P&L ${inr(totalPnl)}` : undefined}
        className="!p-0 overflow-hidden"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-5 py-3 font-medium">Instrument</th>
                <th className="px-5 py-3 font-medium">Segment</th>
                <th className="px-5 py-3 text-right font-medium">Qty / Lots</th>
                <th className="px-5 py-3 text-right font-medium">Avg</th>
                <th className="px-5 py-3 text-right font-medium">Live price</th>
                <th className="px-5 py-3 text-right font-medium">Value</th>
                <th className="px-5 py-3 text-right font-medium">P&L</th>
                <th className="px-5 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {positions.length === 0 && (
                <tr><td colSpan={8} className="px-5 py-10 text-center text-muted">No holdings yet — add your first one above.</td></tr>
              )}
              {items.map((it) => (it.isBasket ? basketRow(it) : legRow(it.row)))}
            </tbody>
          </table>
        </div>
      </Card>

      {data?.disclaimer && <p className="text-xs text-muted">{data.disclaimer}</p>}
    </div>
  );
}
