import { bucketColor, groupHoldings, inr, pct, pctSigned } from "../api/client";
import { Badge, Button, Card } from "../components/ui";

// Each capital bucket shown as its own self-contained portfolio, with a one-click
// drill-in to hedge or risk-analyse just that sub-portfolio.
export default function Portfolios({ portfolio, allocation, onNavigate }) {
  const { holdings, buckets, totals } = portfolio;
  const allocByBucket = Object.fromEntries((allocation?.rows ?? []).map((r) => [r.bucket, r]));

  // Sort portfolios by current value (biggest first).
  const ordered = [...buckets].sort((a, b) => b.current_value - a.current_value);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-headline">Portfolios</h1>
        <p className="mt-1 text-sm text-muted">
          Your capital split into separate portfolios. Hedge or risk-check each one on its
          own — your long-term book and your aggressive swing/F&O books are different beasts.
        </p>
      </div>

      {/* whole-portfolio summary strip */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted">All portfolios</p>
            <p className="mt-1 text-2xl font-bold text-headline tnum">{inr(totals.current_value)}</p>
          </div>
          <div className="text-right">
            <p className="text-xs uppercase tracking-wide text-muted">Total P&amp;L</p>
            <p className={`mt-1 text-2xl font-bold tnum ${totals.pnl >= 0 ? "text-up" : "text-down"}`}>
              {inr(totals.pnl)} <span className="text-sm">{pctSigned(totals.pnl_pct)}</span>
            </p>
          </div>
        </div>
      </Card>

      {/* one card per portfolio */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        {ordered.map((b) => {
          const name = b.bucket;
          const rows = holdings.filter((h) => h.bucket === name);
          const items = groupHoldings(rows); // saved baskets shown as one summary row
          const alloc = allocByBucket[name];
          const color = bucketColor(name);
          const shareOfTotal = totals.current_value
            ? (b.current_value / totals.current_value) * 100
            : 0;
          return (
            <Card key={name} className="flex flex-col">
              {/* header */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: color }} />
                  <div>
                    <h2 className="text-lg font-bold text-headline">{name}</h2>
                    <p className="text-xs text-muted">
                      {rows.length} holding{rows.length === 1 ? "" : "s"} · {pct(shareOfTotal, 1)} of total
                    </p>
                  </div>
                </div>
                {alloc?.tracked && (
                  <Badge kind={alloc.status}>
                    {alloc.status === "in-band"
                      ? "on plan"
                      : `${alloc.status} ${pctSigned(alloc.drift_pct, 1)}`}
                  </Badge>
                )}
              </div>

              {/* stats */}
              <div className="mt-4 grid grid-cols-3 gap-3">
                <div className="rounded-lg border border-hairline bg-elevated/30 p-3">
                  <p className="text-[11px] uppercase tracking-wide text-muted">Value</p>
                  <p className="mt-0.5 font-semibold text-body tnum">{inr(b.current_value)}</p>
                </div>
                <div className="rounded-lg border border-hairline bg-elevated/30 p-3">
                  <p className="text-[11px] uppercase tracking-wide text-muted">Invested</p>
                  <p className="mt-0.5 font-semibold text-body tnum">{inr(b.invested)}</p>
                </div>
                <div className="rounded-lg border border-hairline bg-elevated/30 p-3">
                  <p className="text-[11px] uppercase tracking-wide text-muted">P&amp;L</p>
                  <p className={`mt-0.5 font-semibold tnum ${b.current_value - b.invested >= 0 ? "text-up" : "text-down"}`}>
                    {pctSigned((b.current_value - b.invested) / (b.invested || 1) * 100)}
                  </p>
                </div>
              </div>

              {alloc?.tracked && (
                <p className="mt-3 text-xs text-muted">
                  Allocation {pct(alloc.current_pct)} vs target {pct(alloc.target_pct)}
                  {Math.abs(alloc.rebalance_value) >= 1 && (
                    <>
                      {" · "}
                      <span className={alloc.rebalance_value > 0 ? "text-up" : "text-down"}>
                        {alloc.rebalance_value > 0
                          ? `add ${inr(alloc.rebalance_value)}`
                          : `trim ${inr(Math.abs(alloc.rebalance_value))}`}
                      </span>
                    </>
                  )}
                </p>
              )}

              {/* holdings */}
              <div className="mt-4 flex-1 overflow-hidden rounded-lg border border-hairline">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-muted">
                      <th className="px-3 py-2 font-medium">Symbol</th>
                      <th className="px-3 py-2 text-right font-medium">Qty</th>
                      <th className="px-3 py-2 text-right font-medium">Value</th>
                      <th className="px-3 py-2 text-right font-medium">P&amp;L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((it, i) =>
                      it.isBasket ? (
                        <tr key={`b-${it.basket_id}`} className="border-b border-hairline/50 last:border-0">
                          <td className="px-3 py-2 font-medium text-body">
                            {it.label}
                            <span className="ml-1.5 rounded bg-gold/15 px-1 py-0.5 text-[10px] font-semibold text-gold">
                              BASKET · {it.legs.length}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right tnum text-muted">—</td>
                          <td className="px-3 py-2 text-right tnum text-body">{inr(it.current_value)}</td>
                          <td className={`px-3 py-2 text-right tnum ${it.pnl >= 0 ? "text-up" : "text-down"}`}>
                            {pctSigned(it.pnl_pct)}
                          </td>
                        </tr>
                      ) : (
                        <tr key={it.row.id ?? `${it.row.symbol}-${it.row.bucket}-${i}`} className="border-b border-hairline/50 last:border-0">
                          <td className="px-3 py-2 font-medium text-body">{it.row.symbol}</td>
                          <td className="px-3 py-2 text-right tnum text-muted-strong">{it.row.quantity}</td>
                          <td className="px-3 py-2 text-right tnum text-body">{inr(it.row.current_value)}</td>
                          <td className={`px-3 py-2 text-right tnum ${it.row.pnl >= 0 ? "text-up" : "text-down"}`}>
                            {pctSigned(it.row.pnl_pct)}
                          </td>
                        </tr>
                      )
                    )}
                  </tbody>
                </table>
              </div>

              {/* actions: drill into Hedge / Risk pre-scoped to this portfolio */}
              <div className="mt-4 flex gap-2">
                <Button variant="secondary" onClick={() => onNavigate("hedge", name)}>
                  Hedge this
                </Button>
                <Button variant="secondary" onClick={() => onNavigate("risk", name)}>
                  Risk analysis
                </Button>
              </div>
            </Card>
          );
        })}
      </div>

      <p className="text-xs text-muted">{portfolio.disclaimer}</p>
    </div>
  );
}
