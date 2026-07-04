import { useEffect, useState } from "react";
import { bucketColor, inr, pct, pctSigned, sendJSON } from "../api/client";
import {
  AlertBanner,
  Badge,
  Button,
  Card,
  NumberInput,
} from "../components/ui";
import Explainer from "../components/Explainer";

function planFromBuckets(buckets) {
  return buckets.map((b) => ({
    name: b.name,
    target_pct: b.target_pct,
    tolerance_pct: b.tolerance_pct,
  }));
}

export default function Allocation({ allocation, buckets, onReload }) {
  const [plan, setPlan] = useState(planFromBuckets(buckets));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Keep the editor in sync if the saved plan changes underneath us.
  useEffect(() => {
    setPlan(planFromBuckets(buckets));
  }, [buckets]);

  const targetSum = plan.reduce((s, b) => s + Number(b.target_pct || 0), 0);
  const sumValid = Math.abs(targetSum - 100) < 0.01;

  function update(i, field, value) {
    setPlan((p) =>
      p.map((row, idx) => (idx === i ? { ...row, [field]: value } : row)),
    );
  }
  function addRow() {
    setPlan((p) => [...p, { name: "", target_pct: 0, tolerance_pct: 5 }]);
  }
  function removeRow(i) {
    setPlan((p) => p.filter((_, idx) => idx !== i));
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const body = plan
        .filter((b) => b.name.trim())
        .map((b) => ({
          name: b.name.trim(),
          target_pct: Number(b.target_pct) || 0,
          tolerance_pct: Number(b.tolerance_pct) || 0,
        }));
      await sendJSON("/api/buckets", body, "PUT");
      await onReload();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function resetDefaults() {
    setSaving(true);
    setError(null);
    try {
      await sendJSON("/api/buckets/reset-defaults", {}, "POST");
      await onReload();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  const rows = allocation?.rows ?? [];
  const drifted = rows.filter((r) => r.tracked && r.status !== "in-band");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-headline">Allocation</h1>
        <p className="mt-1 text-sm text-muted">
          Split your capital into buckets, then track drift and rebalance back to
          plan.
        </p>
      </div>

      {!allocation?.targets_valid && (
        <AlertBanner tone="warn" title="Your target plan doesn't add up to 100%">
          Targets currently sum to {pct(allocation?.target_sum_pct ?? 0)}. Edit the
          plan below so the buckets total 100%.
        </AlertBanner>
      )}

      {drifted.length > 0 && allocation?.targets_valid && (
        <AlertBanner
          tone="warn"
          title={`${drifted.length} bucket${drifted.length > 1 ? "s" : ""} outside the tolerance band`}
        >
          Consider rebalancing the rows marked over/under below.
        </AlertBanner>
      )}

      {/* The plan editor */}
      <Card
        title="Your target plan"
        subtitle="Each bucket's target % of capital and how far it can drift before it's flagged."
        right={
          <span
            className={`text-sm font-semibold tnum ${
              sumValid ? "text-up" : "text-warn"
            }`}
          >
            Σ {pct(targetSum)}
          </span>
        }
      >
        <div className="space-y-3">
          <div className="hidden grid-cols-12 gap-3 px-1 text-xs font-medium uppercase tracking-wide text-muted sm:grid">
            <span className="col-span-5">Bucket</span>
            <span className="col-span-3">Target %</span>
            <span className="col-span-3">Tolerance ±%</span>
            <span className="col-span-1"></span>
          </div>
          {plan.map((row, i) => (
            <div key={i} className="grid grid-cols-12 items-center gap-3">
              <div className="col-span-12 sm:col-span-5">
                <div className="flex items-center gap-2 rounded-lg border border-hairline bg-elevated px-3 focus-within:ring-2 focus-within:ring-info/50">
                  <span
                    className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: bucketColor(row.name) }}
                  />
                  <input
                    value={row.name}
                    onChange={(e) => update(i, "name", e.target.value)}
                    placeholder="Bucket name"
                    className="w-full bg-transparent py-2 text-sm text-body outline-none"
                  />
                </div>
              </div>
              <div className="col-span-5 sm:col-span-3">
                <NumberInput
                  value={row.target_pct}
                  onChange={(v) => update(i, "target_pct", v)}
                  suffix="%"
                  min="0"
                  max="100"
                />
              </div>
              <div className="col-span-5 sm:col-span-3">
                <NumberInput
                  value={row.tolerance_pct}
                  onChange={(v) => update(i, "tolerance_pct", v)}
                  suffix="±%"
                  min="0"
                  max="100"
                />
              </div>
              <div className="col-span-2 flex justify-end sm:col-span-1">
                <button
                  onClick={() => removeRow(i)}
                  className="rounded-md px-2 py-2 text-muted hover:text-down"
                  title="Remove bucket"
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button variant="secondary" onClick={addRow}>
            + Add bucket
          </Button>
          <Button onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save plan"}
          </Button>
          <Button variant="ghost" onClick={resetDefaults} disabled={saving}>
            Reset to defaults
          </Button>
          {!sumValid && (
            <span className="text-xs text-warn">
              Targets sum to {pct(targetSum)} — should be 100%.
            </span>
          )}
        </div>
        {error && <p className="mt-3 text-sm text-down">{error}</p>}
      </Card>

      {/* The live report */}
      <Card title="Current vs target" className="!p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-6 py-3 font-medium">Bucket</th>
                <th className="px-6 py-3 text-right font-medium">Value</th>
                <th className="px-6 py-3 text-right font-medium">Current %</th>
                <th className="px-6 py-3 text-right font-medium">Target %</th>
                <th className="px-6 py-3 text-right font-medium">Drift</th>
                <th className="px-6 py-3 text-right font-medium">Rebalance</th>
                <th className="px-6 py-3 text-right font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.bucket}
                  className="border-b border-hairline/60 last:border-0 hover:bg-elevated/50"
                >
                  <td className="px-6 py-3 font-medium text-body">
                    <span className="flex items-center gap-2">
                      <span
                        className="inline-block h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: bucketColor(r.bucket) }}
                      />
                      {r.bucket}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-right tnum text-body">
                    {inr(r.current_value)}
                  </td>
                  <td className="px-6 py-3 text-right tnum text-body">
                    {pct(r.current_pct)}
                  </td>
                  <td className="px-6 py-3 text-right tnum text-muted-strong">
                    {r.tracked ? pct(r.target_pct) : "—"}
                  </td>
                  <td
                    className={`px-6 py-3 text-right tnum ${
                      !r.tracked
                        ? "text-muted"
                        : r.status === "in-band"
                          ? "text-up"
                          : "text-warn"
                    }`}
                  >
                    {r.tracked ? pctSigned(r.drift_pct) : "—"}
                  </td>
                  <td
                    className={`px-6 py-3 text-right tnum ${
                      Math.abs(r.rebalance_value) < 1
                        ? "text-muted"
                        : r.rebalance_value > 0
                          ? "text-up"
                          : "text-down"
                    }`}
                  >
                    {!r.tracked
                      ? "—"
                      : r.rebalance_value > 0
                        ? `Add ${inr(r.rebalance_value)}`
                        : r.rebalance_value < 0
                          ? `Trim ${inr(Math.abs(r.rebalance_value))}`
                          : "On target"}
                  </td>
                  <td className="px-6 py-3 text-right">
                    <Badge kind={r.status}>{r.status}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Explainer module="allocation" data={allocation} />

      <p className="text-xs text-muted">{allocation?.disclaimer}</p>
    </div>
  );
}
