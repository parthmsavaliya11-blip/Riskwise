// Shared UI primitives for RiskWise. Navy surfaces, a single gold accent, tinted
// elevation, and consistent motion on everything interactive.
import { bucketColor, pctSigned } from "../api/client";

export function Card({ title, subtitle, right, children, className = "", accent = false }) {
  return (
    <section
      className={`relative rounded-2xl border border-hairline bg-card p-6 shadow-[var(--shadow-card)] ${className}`}
    >
      {accent && (
        <span className="pointer-events-none absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-gold/60 to-transparent" />
      )}
      {(title || right) && (
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            {title && <h2 className="text-base font-semibold text-headline">{title}</h2>}
            {subtitle && <p className="mt-1 text-xs leading-relaxed text-muted">{subtitle}</p>}
          </div>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatCard({ label, value, sub, tone = "default", mono = true }) {
  const toneText = {
    default: "text-headline",
    up: "text-up",
    down: "text-down",
    gold: "text-gold",
  }[tone];
  return (
    <div className="group relative overflow-hidden rounded-2xl border border-hairline bg-card p-5 shadow-[var(--shadow-card)] transition-colors hover:border-hairline-strong">
      <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted">{label}</p>
      <p className={`mt-2 text-[28px] font-bold leading-tight ${toneText} ${mono ? "tnum" : ""}`}>
        {value}
      </p>
      {sub && <p className="mt-1 text-xs font-medium text-muted-strong tnum">{sub}</p>}
    </div>
  );
}

const BADGE_STYLES = {
  "in-band": "bg-up/10 text-up ring-1 ring-up/20",
  ok: "bg-up/10 text-up ring-1 ring-up/20",
  over: "bg-warn/10 text-warn ring-1 ring-warn/20",
  under: "bg-warn/10 text-warn ring-1 ring-warn/20",
  untracked: "bg-muted/10 text-muted-strong ring-1 ring-hairline",
  breach: "bg-down/10 text-down ring-1 ring-down/20",
  gold: "bg-gold/10 text-gold ring-1 ring-gold/25",
  neutral: "bg-elevated text-muted-strong ring-1 ring-hairline",
};

export function Badge({ kind = "neutral", children }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
        BADGE_STYLES[kind] || BADGE_STYLES.neutral
      }`}
    >
      {children}
    </span>
  );
}

export function Button({ children, variant = "primary", type = "button", className = "", ...props }) {
  const styles = {
    primary:
      "bg-gold text-onprimary shadow-[var(--shadow-gold)] hover:bg-gold-bright active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none",
    secondary:
      "bg-elevated text-body border border-hairline hover:border-hairline-strong hover:bg-elevated/70 active:scale-[0.98]",
    ghost: "text-muted-strong hover:bg-elevated/60 hover:text-body",
    danger: "bg-down/10 text-down border border-down/25 hover:bg-down/15 active:scale-[0.98]",
  }[variant];
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold transition-all ${styles} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

// Portfolio-scope selector: analyse the whole portfolio or one capital bucket.
export function BucketScope({ buckets, value, onChange }) {
  const opts = ["All", ...(buckets || [])];
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted">Portfolio</span>
      <div className="flex flex-wrap gap-1 rounded-xl border border-hairline bg-elevated/60 p-1">
        {opts.map((b) => {
          const val = b === "All" ? "" : b;
          const active = (value || "") === val;
          return (
            <button
              key={b}
              onClick={() => onChange(val)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                active ? "bg-gold/15 text-gold" : "text-muted-strong hover:text-body"
              }`}
            >
              {b}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-muted-strong">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
    </label>
  );
}

export function NumberInput({ value, onChange, suffix, ...props }) {
  return (
    <div className="flex items-center rounded-lg border border-hairline bg-elevated/60 transition-colors focus-within:border-gold/50 focus-within:ring-2 focus-within:ring-gold/20">
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-transparent px-3 py-2 text-sm text-body tnum outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
        {...props}
      />
      {suffix && <span className="px-3 text-xs text-muted">{suffix}</span>}
    </div>
  );
}

// Thin left-accent alert banner: amber (warn) / red (breach) / green (ok) / info.
export function AlertBanner({ tone = "info", title, children }) {
  const accent = {
    ok: { border: "border-up", text: "text-up", bg: "bg-up/5" },
    warn: { border: "border-warn", text: "text-warn", bg: "bg-warn/5" },
    breach: { border: "border-down", text: "text-down", bg: "bg-down/5" },
    info: { border: "border-info", text: "text-info", bg: "bg-info/5" },
  }[tone];
  return (
    <div className={`rounded-xl border border-hairline border-l-[3px] ${accent.border} ${accent.bg} px-4 py-3`}>
      {title && <p className={`text-sm font-semibold ${accent.text}`}>{title}</p>}
      {children && <div className="mt-0.5 text-sm text-body">{children}</div>}
    </div>
  );
}

// Allocation bar: current fill in the bucket color, a gold target marker, and a
// drift badge when out of band.
export function AllocationBar({ name, currentPct, targetPct, status }) {
  const color = bucketColor(name);
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-sm">
        <span className="flex items-center gap-2 font-medium text-body">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
          {name}
        </span>
        <span className="flex items-center gap-2 tnum text-muted-strong">
          {currentPct.toFixed(1)}%
          {status && status !== "in-band" && (
            <Badge kind={status}>
              {status === "untracked" ? "untracked" : `${status} ${pctSigned(currentPct - targetPct, 1)}`}
            </Badge>
          )}
        </span>
      </div>
      <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-elevated">
        <div
          className="h-full rounded-full transition-[width] duration-500"
          style={{ width: `${Math.min(currentPct, 100)}%`, backgroundColor: color }}
        />
        {targetPct > 0 && (
          <div
            className="absolute top-[-2px] h-[calc(100%+4px)] w-0.5 bg-gold"
            style={{ left: `${Math.min(targetPct, 100)}%` }}
            title={`Target ${targetPct}%`}
          />
        )}
      </div>
    </div>
  );
}

// Shared page header — display title + optional lead + right-side actions.
export function PageHeader({ title, lead, children }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-3xl font-bold text-headline sm:text-[34px]">{title}</h1>
        {lead && <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted-strong">{lead}</p>}
      </div>
      {children && <div className="flex items-center gap-3">{children}</div>}
    </div>
  );
}
