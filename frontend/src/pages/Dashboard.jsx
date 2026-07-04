import { groupHoldings, inr, pctSigned } from "../api/client";
import { AlertBanner, AllocationBar, Card, PageHeader, StatCard } from "../components/ui";

export default function Dashboard({ portfolio, allocation, onNavigate }) {
  const { totals, holdings } = portfolio;
  const rows = allocation?.rows ?? [];
  const drifted = rows.filter((r) => r.tracked && r.status !== "in-band");
  // Saved baskets collapse into one summary row (overview table — not expandable here).
  const holdingItems = groupHoldings(holdings);

  return (
    <div className="space-y-8">
      <PageHeader title="Dashboard" lead="Your whole risk picture at a glance — value, P&L, allocation drift and holdings." />

      {/* Totals */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Invested" value={inr(totals.invested)} />
        <StatCard label="Current value" value={inr(totals.current_value)} />
        <StatCard
          label="Total P&L"
          value={inr(totals.pnl)}
          sub={pctSigned(totals.pnl_pct)}
          tone={totals.pnl >= 0 ? "up" : "down"}
        />
        <StatCard label="Holdings" value={totals.holdings_count} />
      </section>

      {/* Drift alert */}
      {drifted.length > 0 && (
        <AlertBanner
          tone="warn"
          title={`${drifted.length} bucket${drifted.length > 1 ? "s" : ""} off target`}
        >
          {drifted
            .map((d) => `${d.bucket} is ${d.status} by ${pctSigned(d.drift_pct, 1)}`)
            .join(" · ")}
          .{" "}
          <button
            onClick={() => onNavigate("allocation")}
            className="font-semibold text-warn underline-offset-2 hover:underline"
          >
            Review allocation →
          </button>
        </AlertBanner>
      )}

      {/* Allocation overview */}
      <Card
        accent
        title="Capital allocation"
        subtitle="Current split vs your target plan. The gold marker is each bucket's target."
        right={
          <button
            onClick={() => onNavigate("allocation")}
            className="text-xs font-semibold text-gold hover:underline"
          >
            Manage →
          </button>
        }
      >
        <div className="space-y-4">
          {rows.length === 0 && (
            <p className="text-sm text-muted">No holdings loaded yet.</p>
          )}
          {rows.map((r) => (
            <AllocationBar
              key={r.bucket}
              name={r.bucket}
              currentPct={r.current_pct}
              targetPct={r.target_pct}
              status={r.status}
            />
          ))}
        </div>
      </Card>

      {/* Holdings */}
      <Card title="Holdings" className="!p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-6 py-3 font-medium">Symbol</th>
                <th className="px-6 py-3 font-medium">Bucket</th>
                <th className="px-6 py-3 text-right font-medium">Qty</th>
                <th className="px-6 py-3 text-right font-medium">Avg</th>
                <th className="px-6 py-3 text-right font-medium">LTP</th>
                <th className="px-6 py-3 text-right font-medium">Value</th>
                <th className="px-6 py-3 text-right font-medium">P&L</th>
              </tr>
            </thead>
            <tbody>
              {holdingItems.map((it, i) =>
                it.isBasket ? (
                  <tr
                    key={`b-${it.basket_id}`}
                    className="border-b border-hairline/60 last:border-0 hover:bg-elevated/50"
                  >
                    <td className="px-6 py-3 font-medium text-body">
                      {it.label}
                      <span className="ml-1.5 rounded bg-gold/15 px-1 py-0.5 text-[10px] font-semibold text-gold">
                        BASKET · {it.legs.length} legs
                      </span>
                    </td>
                    <td className="px-6 py-3 text-muted-strong">{it.bucket}</td>
                    <td className="px-6 py-3 text-right tnum text-muted">—</td>
                    <td className="px-6 py-3 text-right tnum text-muted">—</td>
                    <td className="px-6 py-3 text-right tnum text-muted">—</td>
                    <td className="px-6 py-3 text-right tnum text-body">
                      {inr(it.current_value)}
                    </td>
                    <td
                      className={`px-6 py-3 text-right tnum font-medium ${
                        it.pnl >= 0 ? "text-up" : "text-down"
                      }`}
                    >
                      {it.pnl >= 0 ? "▲" : "▼"} {inr(it.pnl)}
                      <span className="ml-1 text-xs">({pctSigned(it.pnl_pct)})</span>
                    </td>
                  </tr>
                ) : (
                  <tr
                    key={it.row.id ?? `${it.row.symbol}-${it.row.bucket}-${i}`}
                    className="border-b border-hairline/60 last:border-0 hover:bg-elevated/50"
                  >
                    <td className="px-6 py-3 font-medium text-body">{it.row.symbol}</td>
                    <td className="px-6 py-3 text-muted-strong">{it.row.bucket}</td>
                    <td className="px-6 py-3 text-right tnum text-body">{it.row.quantity}</td>
                    <td className="px-6 py-3 text-right tnum text-muted-strong">
                      {it.row.avg_price}
                    </td>
                    <td className="px-6 py-3 text-right tnum text-body">{it.row.ltp}</td>
                    <td className="px-6 py-3 text-right tnum text-body">
                      {inr(it.row.current_value)}
                    </td>
                    <td
                      className={`px-6 py-3 text-right tnum font-medium ${
                        it.row.pnl >= 0 ? "text-up" : "text-down"
                      }`}
                    >
                      {it.row.pnl >= 0 ? "▲" : "▼"} {inr(it.row.pnl)}
                      <span className="ml-1 text-xs">({pctSigned(it.row.pnl_pct)})</span>
                    </td>
                  </tr>
                )
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
