import { useEffect, useState } from "react";
import { bucketColor, getJSON, inr, num, pct, pctSigned, sendJSON } from "../api/client";
import { AlertBanner, Badge, Button, Card, Field, NumberInput, StatCard } from "../components/ui";
import Explainer from "../components/Explainer";

// Local (not UTC) YYYY-MM-DD, so the default date matches the trader's calendar day.
const todayISO = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};
const blank = () => ({
  symbol: "", bucket: "Swing", side: "long",
  entry_price: "", stop_price: "", target_price: "", exit_price: "",
  quantity: "", fees: "", notes: "",
  entry_date: todayISO(), exit_date: "",
});
const BUCKETS = ["F&O", "Long-term", "Swing"];
const DATE_CLS =
  "w-full rounded-lg border border-hairline bg-elevated px-3 py-2 text-sm text-body outline-none focus:ring-2 focus:ring-info/50";

function fmtDate(iso) {
  if (!iso) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  const mon = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][+m[2] - 1];
  return `${m[3]} ${mon} ${m[1]}`;
}

export default function Journal() {
  const [data, setData] = useState(null);
  const [review, setReview] = useState(null);
  const [form, setForm] = useState(blank);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [closing, setClosing] = useState({}); // id -> { price, date }

  async function reload() {
    const [j, r] = await Promise.all([
      getJSON("/api/journal"),
      getJSON("/api/journal/review").catch(() => null),
    ]);
    setData(j);
    setReview(r);
  }
  useEffect(() => {
    reload().catch((e) => setError(e.message));
  }, []);

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function addTrade() {
    setBusy(true);
    setError(null);
    try {
      const body = {
        symbol: form.symbol,
        bucket: form.bucket,
        side: form.side,
        entry_price: Number(form.entry_price),
        stop_price: Number(form.stop_price || 0),
        target_price: Number(form.target_price || 0),
        exit_price: Number(form.exit_price || 0),
        quantity: Number(form.quantity),
        fees: Number(form.fees || 0),
        notes: form.notes,
        entry_date: form.entry_date,
        exit_date: form.exit_date || null,
      };
      await sendJSON("/api/journal", body, "POST");
      setForm(blank());
      await reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function startClose(id) {
    setClosing((c) => ({ ...c, [id]: { price: "", date: todayISO() } }));
  }
  function cancelClose(id) {
    setClosing((c) => ({ ...c, [id]: undefined }));
  }
  function setClose(id, field, value) {
    setClosing((c) => ({ ...c, [id]: { ...c[id], [field]: value } }));
  }
  async function closeTrade(id) {
    const c = closing[id] || {};
    if (!Number(c.price) || !c.date) return;
    setBusy(true);
    setError(null);
    try {
      await sendJSON(`/api/journal/${id}/close`, { exit_price: Number(c.price), exit_date: c.date }, "PUT");
      setClosing((s) => ({ ...s, [id]: undefined }));
      await reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function removeTrade(id) {
    setBusy(true);
    try {
      await sendJSON(`/api/journal/${id}`, {}, "DELETE");
      await reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const trades = data?.trades ?? [];
  const stats = data?.stats ?? { count: 0 };
  const openTrades = trades.filter((t) => t.status === "open");
  const closedTrades = trades.filter((t) => t.status === "closed");
  const exitGiven = Number(form.exit_price) > 0;
  const canAdd =
    form.symbol && form.entry_price && form.quantity && form.entry_date && (!exitGiven || form.exit_date);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-headline">Trade Journal</h1>
        <p className="mt-1 text-sm text-muted">
          Log every trade and learn whether your edge is real — R-multiples, win rate and
          expectancy, not just gut feel. Closed trades roll up into a financial-year review.
        </p>
      </div>

      {error && <AlertBanner tone="breach" title="Something went wrong">{error}</AlertBanner>}

      {/* Lifetime stats (all closed trades) */}
      {stats.count > 0 ? (
        <section className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard label="Win rate" value={pct(stats.win_rate_pct, 0)} sub={`${stats.wins}W / ${stats.losses}L`} />
          <StatCard label="Expectancy" value={inr(stats.expectancy_money)} sub="per trade" tone={stats.expectancy_money >= 0 ? "up" : "down"} />
          <StatCard label="Avg R" value={`${stats.avg_r}R`} tone={stats.avg_r >= 0 ? "up" : "down"} />
          <StatCard label="Total P&L" value={inr(stats.total_pnl)} tone={stats.total_pnl >= 0 ? "up" : "down"} />
          <StatCard label="Profit factor" value={stats.profit_factor ?? "—"} />
        </section>
      ) : (
        <AlertBanner tone="info" title="No closed trades yet">
          Add a few trades below (with an exit price + exit date) to see your win rate and expectancy.
        </AlertBanner>
      )}

      {/* Financial-year review */}
      <FYReview review={review} />

      {/* Add trade */}
      <Card title="Log a trade" subtitle="Entry date is required. Add an exit price + exit date to log it as already closed.">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          <Field label="Symbol">
            <input value={form.symbol} onChange={(e) => set("symbol", e.target.value)} placeholder="e.g. RELIANCE"
              className="w-full rounded-lg border border-hairline bg-elevated px-3 py-2 text-sm text-body outline-none focus:ring-2 focus:ring-info/50" />
          </Field>
          <Field label="Bucket / segment">
            <div className="flex rounded-lg border border-hairline bg-elevated p-1">
              {BUCKETS.map((b) => (
                <button key={b} onClick={() => set("bucket", b)}
                  className={`flex-1 rounded-md px-1 py-1.5 text-[11px] font-medium ${form.bucket === b ? "bg-card text-headline" : "text-muted-strong"}`}>
                  {b}
                </button>
              ))}
            </div>
          </Field>
          <Field label="Side">
            <div className="flex rounded-lg border border-hairline bg-elevated p-1">
              {["long", "short"].map((s) => (
                <button key={s} onClick={() => set("side", s)}
                  className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium capitalize ${form.side === s ? "bg-card text-headline" : "text-muted-strong"}`}>
                  {s}
                </button>
              ))}
            </div>
          </Field>
          <Field label="Quantity"><NumberInput value={form.quantity} onChange={(v) => set("quantity", v)} min="0" /></Field>
          <Field label="Entry date *">
            <input type="date" value={form.entry_date} max={todayISO()} onChange={(e) => set("entry_date", e.target.value)} className={DATE_CLS} />
          </Field>
          <Field label="Entry price"><NumberInput value={form.entry_price} onChange={(v) => set("entry_price", v)} suffix="₹" /></Field>
          <Field label="Stop"><NumberInput value={form.stop_price} onChange={(v) => set("stop_price", v)} suffix="₹" /></Field>
          <Field label="Target"><NumberInput value={form.target_price} onChange={(v) => set("target_price", v)} suffix="₹" /></Field>
          <Field label="Exit price (optional)"><NumberInput value={form.exit_price} onChange={(v) => set("exit_price", v)} suffix="₹" /></Field>
          <Field label={exitGiven ? "Exit date *" : "Exit date (if closed)"}>
            <input type="date" value={form.exit_date} min={form.entry_date} max={todayISO()}
              onChange={(e) => set("exit_date", e.target.value)} className={DATE_CLS} />
          </Field>
          <Field label="Fees"><NumberInput value={form.fees} onChange={(v) => set("fees", v)} suffix="₹" /></Field>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <Button onClick={addTrade} disabled={!canAdd || busy}>{busy ? "Saving…" : "Add trade"}</Button>
          <Button variant="secondary" onClick={() => { setForm(blank()); setError(null); }} disabled={busy}>Cancel</Button>
          <span className="text-xs text-muted">Cancel clears the form — nothing is saved. R-multiple and P&L compute once an exit is set.</span>
        </div>
      </Card>

      {/* Open positions */}
      <TradeTable
        title={`Open positions (${openTrades.length})`}
        trades={openTrades}
        emptyMsg="No open positions."
        closing={closing}
        onStartClose={startClose}
        onSetClose={setClose}
        onConfirmClose={closeTrade}
        onCancelClose={cancelClose}
        onRemove={removeTrade}
        showClose
      />

      {/* Closed trades (the "new part" closed entries move to) */}
      <TradeTable
        title={`Closed trades (${closedTrades.length})`}
        trades={closedTrades}
        emptyMsg="No closed trades yet — close an open position above and it moves here."
        onRemove={removeTrade}
      />

      {data?.disclaimer && <p className="text-xs text-muted">{data.disclaimer}</p>}
    </div>
  );
}

// One trades table. Open table gets the inline Close (exit price + exit date); closed table is read-only + delete.
function TradeTable({ title, trades, emptyMsg, closing = {}, onStartClose, onSetClose, onConfirmClose, onCancelClose, onRemove, showClose }) {
  return (
    <Card title={title} className="!p-0 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-muted">
              <th className="px-5 py-3 font-medium">Symbol</th>
              <th className="px-5 py-3 font-medium">Segment</th>
              <th className="px-5 py-3 font-medium">Side</th>
              <th className="px-5 py-3 text-right font-medium">Entry</th>
              <th className="px-5 py-3 text-right font-medium">Exit</th>
              <th className="px-5 py-3 font-medium">Entry date</th>
              <th className="px-5 py-3 font-medium">Exit date</th>
              <th className="px-5 py-3 text-right font-medium">Qty</th>
              <th className="px-5 py-3 text-right font-medium">R</th>
              <th className="px-5 py-3 text-right font-medium">P&L</th>
              <th className="px-5 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {trades.length === 0 && (
              <tr><td colSpan={11} className="px-5 py-8 text-center text-muted">{emptyMsg}</td></tr>
            )}
            {trades.map((t) => (
              <tr key={t.id} className="border-b border-hairline/60 last:border-0 hover:bg-elevated/40">
                <td className="px-5 py-3 font-medium text-body">{t.symbol}</td>
                <td className="px-5 py-3">
                  <span className="flex items-center gap-1.5 text-muted-strong">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: bucketColor(t.bucket) }} />
                    {t.bucket}
                  </span>
                </td>
                <td className="px-5 py-3 capitalize text-muted-strong">{t.side}</td>
                <td className="px-5 py-3 text-right tnum text-body">{t.entry_price}</td>
                <td className="px-5 py-3 text-right tnum text-body">{t.exit_price || "—"}</td>
                <td className="px-5 py-3 tnum text-muted-strong">{fmtDate(t.entry_date)}</td>
                <td className="px-5 py-3 tnum text-muted-strong">{fmtDate(t.exit_date)}</td>
                <td className="px-5 py-3 text-right tnum text-body">{num(t.quantity)}</td>
                <td className={`px-5 py-3 text-right tnum font-medium ${t.r_multiple == null ? "text-muted" : t.r_multiple >= 0 ? "text-up" : "text-down"}`}>
                  {t.r_multiple == null ? "—" : `${t.r_multiple}R`}
                </td>
                <td className={`px-5 py-3 text-right tnum font-medium ${t.pnl == null ? "text-muted" : t.pnl >= 0 ? "text-up" : "text-down"}`}>
                  {t.pnl == null ? "—" : inr(t.pnl)}
                </td>
                <td className="px-5 py-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    {showClose && (
                      closing[t.id] !== undefined ? (
                        <span className="flex items-center gap-1">
                          <input type="number" value={closing[t.id].price} onChange={(e) => onSetClose(t.id, "price", e.target.value)}
                            placeholder="exit ₹" className="w-20 rounded border border-hairline bg-elevated px-2 py-1 text-xs text-body outline-none" />
                          <input type="date" value={closing[t.id].date} onChange={(e) => onSetClose(t.id, "date", e.target.value)}
                            className="rounded border border-hairline bg-elevated px-2 py-1 text-xs text-body outline-none" />
                          <button onClick={() => onConfirmClose(t.id)} className="text-up hover:opacity-80" title="Confirm close">✓</button>
                          <button onClick={() => onCancelClose(t.id)} className="text-muted hover:text-body" title="Cancel">✕</button>
                        </span>
                      ) : (
                        <button onClick={() => onStartClose(t.id)} className="text-xs text-gold hover:underline">Close</button>
                      )
                    )}
                    <button onClick={() => onRemove(t.id)} className="text-muted hover:text-down" title="Delete">✕</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// Financial-year review: per-segment performance for each COMPLETED FY, plus cross-FY comparison.
function FYReview({ review }) {
  const years = review?.financial_years ?? [];
  const completed = years.filter((y) => y.complete);
  const inProgress = years.filter((y) => !y.complete);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (completed.length && !completed.some((y) => y.label === selected)) {
      setSelected(completed[0].label);
    }
  }, [review]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!review) return null;

  if (!completed.length) {
    const cur = inProgress[0];
    return (
      <Card title="Financial-year review" subtitle="Indian financial year runs 1 Apr → 31 Mar.">
        <AlertBanner tone="info" title={`Your ${review.current_fy} is still in progress`}>
          The review unlocks once a financial year completes (after 31 March). Keep logging
          trades with their entry &amp; exit dates — a full-year breakdown by segment, with
          capital-allocation pointers, appears here automatically.
          {cur && (
            <> So far this year: {cur.overall.count} closed trade(s)
            {cur.held_total?.count > 0 && <>, plus {cur.held_total.count} open holding(s) worth {inr(cur.held_total.invested)} still working</>}.</>
          )}
        </AlertBanner>
      </Card>
    );
  }

  const fy = completed.find((y) => y.label === selected) || completed[0];
  const o = fy.overall;
  const segs = Object.entries(fy.by_segment);

  return (
    <Card
      title="Financial-year review"
      subtitle="Performance by segment for each completed year (1 Apr → 31 Mar) — which bucket earned its capital."
    >
      {/* Year selector */}
      <div className="flex flex-wrap items-center gap-2">
        {completed.map((y) => (
          <button key={y.label} onClick={() => setSelected(y.label)}
            className={`rounded-full px-3 py-1 text-xs font-medium ${fy.label === y.label ? "bg-gold text-onprimary" : "bg-elevated text-muted-strong hover:text-body"}`}>
            {y.label}
          </button>
        ))}
        <span className="ml-1 text-xs text-muted">{review.current_fy} in progress (not yet reviewed)</span>
      </div>

      {/* Realised (closed trades) — headline + per-segment */}
      {o.count > 0 ? (
        <>
          <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted">Realised — closed trades this year</p>
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <StatCard label="Total P&L" value={inr(o.total_pnl)} tone={o.total_pnl >= 0 ? "up" : "down"} />
            <StatCard label="Win rate" value={pct(o.win_rate_pct, 0)} sub={`${o.wins}W / ${o.losses}L`} />
            <StatCard label="Trades" value={num(o.count)} />
            <StatCard label="Avg R" value={`${o.avg_r}R`} tone={o.avg_r >= 0 ? "up" : "down"} />
            <StatCard label="Profit factor" value={o.profit_factor ?? "—"} />
          </div>
          <div className="mt-4 overflow-x-auto rounded-lg border border-hairline">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-muted">
                  <th className="px-4 py-2 font-medium">Segment</th>
                  <th className="px-4 py-2 text-right font-medium">Trades</th>
                  <th className="px-4 py-2 text-right font-medium">Win %</th>
                  <th className="px-4 py-2 text-right font-medium">Total P&L</th>
                  <th className="px-4 py-2 text-right font-medium">Expectancy</th>
                  <th className="px-4 py-2 text-right font-medium">Avg R</th>
                </tr>
              </thead>
              <tbody>
                {segs.map(([b, s]) => (
                  <tr key={b} className="border-b border-hairline/50 last:border-0">
                    <td className="px-4 py-2">
                      <span className="flex items-center gap-1.5 text-body">
                        <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: bucketColor(b) }} />
                        {b}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right tnum text-muted-strong">{s.count}</td>
                    <td className="px-4 py-2 text-right tnum text-muted-strong">{pct(s.win_rate_pct, 0)}</td>
                    <td className={`px-4 py-2 text-right tnum font-medium ${s.total_pnl >= 0 ? "text-up" : "text-down"}`}>{inr(s.total_pnl)}</td>
                    <td className={`px-4 py-2 text-right tnum ${s.expectancy_money >= 0 ? "text-up" : "text-down"}`}>{inr(s.expectancy_money)}</td>
                    <td className="px-4 py-2 text-right tnum text-muted-strong">{s.avg_r}R</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p className="mt-4 rounded-lg border border-hairline bg-elevated/40 p-3 text-sm text-muted">
          No trades were <span className="text-body">closed</span> in {fy.label}. You were still holding
          the open positions below — capital is committed, profit isn't booked until you sell.
        </p>
      )}

      {/* Open positions held at this year-end (from My Holdings, not the journal) */}
      {fy.held_total?.count > 0 && (
        <div className="mt-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
            Held at {fy.label} year-end — open positions <span className="text-muted/70">(from My Holdings, never closed)</span>
          </p>
          <div className="overflow-x-auto rounded-lg border border-hairline">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-muted">
                  <th className="px-4 py-2 font-medium">Segment</th>
                  <th className="px-4 py-2 text-right font-medium">Open positions</th>
                  <th className="px-4 py-2 text-right font-medium">Capital deployed</th>
                  <th className="px-4 py-2 text-right font-medium">Unrealised (now)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(fy.held_by_segment).map(([b, h]) => (
                  <tr key={b} className="border-b border-hairline/50 last:border-0">
                    <td className="px-4 py-2">
                      <span className="flex items-center gap-1.5 text-body">
                        <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: bucketColor(b) }} />
                        {b}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right tnum text-muted-strong">{h.count}</td>
                    <td className="px-4 py-2 text-right tnum text-body">{inr(h.invested)}</td>
                    <td className={`px-4 py-2 text-right tnum font-medium ${h.unrealized_pnl >= 0 ? "text-up" : "text-down"}`}>{inr(h.unrealized_pnl)}</td>
                  </tr>
                ))}
                <tr className="bg-elevated/40 font-medium">
                  <td className="px-4 py-2 text-body">Total held</td>
                  <td className="px-4 py-2 text-right tnum text-muted-strong">{fy.held_total.count}</td>
                  <td className="px-4 py-2 text-right tnum text-body">{inr(fy.held_total.invested)}</td>
                  <td className={`px-4 py-2 text-right tnum ${fy.held_total.unrealized_pnl >= 0 ? "text-up" : "text-down"}`}>{inr(fy.held_total.unrealized_pnl)}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-1.5 text-xs text-muted">
            Counted from the year you bought each position (by buy date), so a long-term holding shows up every
            year it's held — even though it's never closed. Unrealised P&L is as of today.
          </p>
        </div>
      )}

      {/* Allocation pointers (rule-based) */}
      {fy.guidance?.observations?.length > 0 && (
        <div className="mt-4 rounded-lg border border-hairline bg-elevated/40 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Capital-allocation pointers</p>
          <ul className="mt-2 space-y-1.5 text-sm text-body">
            {fy.guidance.observations.map((ob, i) => (
              <li key={i} className="flex gap-2"><span className="text-gold">•</span><span>{ob}</span></li>
            ))}
          </ul>
        </div>
      )}

      {/* Cross-FY comparison */}
      {review.comparison.length > 1 && (
        <div className="mt-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Year-on-year</p>
          <div className="overflow-x-auto rounded-lg border border-hairline">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-muted">
                  <th className="px-4 py-2 font-medium">Financial year</th>
                  <th className="px-4 py-2 text-right font-medium">Trades</th>
                  <th className="px-4 py-2 text-right font-medium">Win %</th>
                  <th className="px-4 py-2 text-right font-medium">Total P&L</th>
                  <th className="px-4 py-2 text-right font-medium">vs prev</th>
                  <th className="px-4 py-2 font-medium">Top segment</th>
                </tr>
              </thead>
              <tbody>
                {review.comparison.map((c) => (
                  <tr key={c.label} className={`border-b border-hairline/50 last:border-0 ${c.label === fy.label ? "bg-gold/5" : ""}`}>
                    <td className="px-4 py-2 font-medium text-body">{c.label}</td>
                    <td className="px-4 py-2 text-right tnum text-muted-strong">{c.count}</td>
                    <td className="px-4 py-2 text-right tnum text-muted-strong">{pct(c.win_rate_pct, 0)}</td>
                    <td className={`px-4 py-2 text-right tnum font-medium ${c.total_pnl >= 0 ? "text-up" : "text-down"}`}>{inr(c.total_pnl)}</td>
                    <td className={`px-4 py-2 text-right tnum ${c.pnl_change_vs_prev == null ? "text-muted" : c.pnl_change_vs_prev >= 0 ? "text-up" : "text-down"}`}>
                      {c.pnl_change_vs_prev == null ? "—" : inr(c.pnl_change_vs_prev)}
                    </td>
                    <td className="px-4 py-2 text-muted-strong">{c.best_segment || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="mt-5">
        <Explainer
          module="journal_review"
          data={{ financial_year: fy.label, overall: o, by_segment: fy.by_segment,
                  held_by_segment: fy.held_by_segment, held_total: fy.held_total,
                  guidance: fy.guidance, comparison: review.comparison }}
          label="Review this year with AI"
        />
      </div>
    </Card>
  );
}
