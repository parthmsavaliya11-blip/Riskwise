// App shell: collapsible left sidebar nav + glass top bar (portfolio value, P&L, badges).
import { inr, pctSigned } from "../api/client";
import { AlertBanner } from "./ui";
import { Logo, LogoMark } from "./Logo";
import Icon from "./icons";

// Grouped so the sidebar reads as a designed map of the product, not a flat list.
const NAV_GROUPS = [
  {
    label: "Overview",
    items: [
      { id: "dashboard", label: "Dashboard", icon: "dashboard" },
      { id: "holdings", label: "My Holdings", icon: "holdings" },
      { id: "portfolios", label: "Portfolios", icon: "portfolios" },
    ],
  },
  {
    label: "Manage risk",
    items: [
      { id: "allocation", label: "Allocation", icon: "allocation" },
      { id: "hedge", label: "Hedge", icon: "hedge" },
      { id: "options", label: "Options", icon: "options" },
      { id: "basket", label: "Basket Order", icon: "basket" },
    ],
  },
  {
    label: "Analyse",
    items: [
      { id: "risk", label: "Risk Analytics", icon: "risk" },
      { id: "journal", label: "Journal", icon: "journal" },
    ],
  },
];
const ALL_ITEMS = NAV_GROUPS.flatMap((g) => g.items);

function NavButton({ item, active, onNavigate }) {
  return (
    <button
      data-tour={`nav-${item.id}`}
      onClick={() => onNavigate(item.id)}
      aria-current={active ? "page" : undefined}
      className={`group relative flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
        active
          ? "bg-gold/10 font-semibold text-gold"
          : "text-muted-strong hover:bg-elevated/60 hover:text-body"
      }`}
    >
      {active && (
        <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-gold" />
      )}
      <Icon name={item.icon} size={18} className={active ? "" : "text-muted group-hover:text-body"} />
      <span className="flex-1 whitespace-nowrap text-left">{item.label}</span>
    </button>
  );
}

function Sidebar({ view, onNavigate, onReplayTour, open }) {
  return (
    <aside
      style={{ width: open ? 256 : 0, flexBasis: open ? 256 : 0 }}
      className={`hidden min-w-0 shrink-0 flex-col overflow-hidden border-hairline bg-card/50 transition-[width,flex-basis] duration-300 ease-out lg:flex ${
        open ? "border-r" : "border-r-0"
      }`}
    >
      <div className="w-64 px-5 py-6">
        <button onClick={() => onNavigate("dashboard")} aria-label="RiskWise home" className="transition-opacity hover:opacity-90">
          <Logo markSize={32} wordSize={21} />
        </button>
      </div>
      <nav className="w-64 flex-1 space-y-6 overflow-y-auto px-3 pb-4">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted">
              {group.label}
            </p>
            <div className="space-y-0.5">
              {group.items.map((item) => (
                <NavButton key={item.id} item={item} active={view === item.id} onNavigate={onNavigate} />
              ))}
            </div>
          </div>
        ))}
      </nav>
      <div className="w-64 border-t border-hairline px-4 py-4">
        {onReplayTour && (
          <button
            onClick={onReplayTour}
            className="mb-3 inline-flex items-center gap-2 rounded-lg px-2 py-1 text-xs font-medium text-muted-strong transition-colors hover:text-gold"
          >
            <Icon name="help" size={15} />
            Take the tour
          </button>
        )}
        <p className="text-[11px] leading-relaxed text-muted">
          Read-only. Educational analytics, not investment advice.
        </p>
      </div>
    </aside>
  );
}

function MobileTabs({ view, onNavigate, open }) {
  if (!open) return null;
  return (
    <nav className="flex gap-1 overflow-x-auto border-b border-hairline bg-card/60 px-2 py-2 lg:hidden">
      {ALL_ITEMS.map((item) => {
        const active = view === item.id;
        return (
          <button
            key={item.id}
            data-tour={`nav-${item.id}`}
            onClick={() => onNavigate(item.id)}
            className={`flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              active ? "bg-gold/10 text-gold" : "text-muted-strong"
            }`}
          >
            <Icon name={item.icon} size={15} />
            {item.label}
          </button>
        );
      })}
    </nav>
  );
}

function DataBadge({ dataMode }) {
  if (!dataMode) return null;
  const live = dataMode.mode === "live";
  return (
    <span
      className={`hidden items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium sm:inline-flex ${
        live ? "border-up/30 bg-up/10 text-up" : "border-hairline bg-elevated text-muted-strong"
      }`}
      title={dataMode.detail}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${live ? "bg-up" : "bg-muted"}`} />
      {dataMode.name} · {dataMode.mode}
    </span>
  );
}

function IconButton({ name, label, onClick }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-hairline text-muted-strong transition-colors hover:border-hairline-strong hover:text-gold"
    >
      <Icon name={name} size={17} />
    </button>
  );
}

function UserMenu({ user, onLogout }) {
  if (!user) return null;
  return (
    <div className="flex items-center gap-2 border-l border-hairline pl-3">
      <span className="hidden items-center gap-1.5 text-sm font-medium text-body md:inline-flex" title={user.email}>
        <Icon name="user" size={15} className="text-muted" />
        {user.username}
        {user.is_admin && (
          <span className="rounded bg-gold/15 px-1 py-0.5 text-[9px] font-bold uppercase tracking-wide text-gold">owner</span>
        )}
      </span>
      <IconButton name="logout" label="Log out" onClick={onLogout} />
    </div>
  );
}

function TopBar({ totals, dataMode, onReplayTour, theme, onToggleTheme, navOpen, onToggleNav, user, onLogout }) {
  const pnl = totals?.pnl ?? 0;
  const up = pnl >= 0;
  const dark = theme !== "light";
  return (
    <header className="rw-glass sticky top-0 z-20 flex flex-wrap items-center justify-between gap-4 border-b border-hairline px-4 py-3 lg:px-6">
      <div className="flex items-center gap-4 lg:gap-6">
        <button
          onClick={onToggleNav}
          aria-label={navOpen ? "Hide menu" : "Show menu"}
          aria-expanded={navOpen}
          title={navOpen ? "Hide menu" : "Show menu"}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-muted-strong transition-colors hover:bg-elevated/60 hover:text-gold"
        >
          <Icon name="menu" size={20} />
        </button>
        <span className={`transition-opacity ${navOpen ? "lg:hidden" : ""}`}>
          <LogoMark size={26} />
        </span>
        <div>
          <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted">Portfolio value</p>
          <p className="text-lg font-bold text-headline tnum">{inr(totals?.current_value)}</p>
        </div>
        <div className="hidden h-8 w-px bg-hairline sm:block" />
        <div className="hidden sm:block">
          <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted">Total P&amp;L</p>
          <p className={`text-lg font-bold tnum ${up ? "text-up" : "text-down"}`}>
            {up ? "▲" : "▼"} {inr(pnl)}
            <span className="ml-1 text-xs font-semibold">{pctSigned(totals?.pnl_pct ?? 0)}</span>
          </p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <DataBadge dataMode={dataMode} />
        <IconButton
          name={dark ? "sun" : "moon"}
          label={dark ? "Switch to light mode" : "Switch to dark mode"}
          onClick={onToggleTheme}
        />
        {onReplayTour && <IconButton name="help" label="Take the tour" onClick={onReplayTour} />}
        <UserMenu user={user} onLogout={onLogout} />
      </div>
    </header>
  );
}

// F&O expiry notices: what was just auto-settled into the journal + what expires within a day.
function ExpiryBanner({ expiry, onNavigate }) {
  const settled = expiry?.settled || [];
  const expiring = expiry?.expiring || [];
  if (!settled.length && !expiring.length) return null;
  const plural = (n) => (n > 1 ? "s" : "");
  return (
    <div className="mx-auto w-full max-w-[1320px] space-y-2 px-5 pt-4 lg:px-8">
      {expiring.length > 0 && (
        <AlertBanner tone="warn" title={`${expiring.length} F&O position${plural(expiring.length)} expiring within a day`}>
          {expiring.map((e) => e.tradingsymbol).join(", ")} — square this off at your broker before it expires; RiskWise will auto-settle it into your Journal once it does.
        </AlertBanner>
      )}
      {settled.length > 0 && (
        <AlertBanner tone="info" title={`${settled.length} expired F&O position${plural(settled.length)} auto-settled into your Journal`}>
          {settled.map((s) => `${s.tradingsymbol} @ ${inr(s.exit_price)}`).join(", ")}
          {settled.some((s) => s.price_source === "cost") && " (settled at cost — no live price for an expired contract)"}.{" "}
          <button onClick={() => onNavigate("journal")} className="font-semibold text-info underline-offset-2 hover:underline">
            View in Journal →
          </button>
        </AlertBanner>
      )}
    </div>
  );
}

export default function Shell({
  view,
  onNavigate,
  totals,
  dataMode,
  children,
  onReplayTour,
  theme,
  onToggleTheme,
  navOpen = true,
  onToggleNav,
  expiry,
  user,
  onLogout,
}) {
  return (
    <div className="flex min-h-screen">
      <a href="#main" className="skip-link">Skip to content</a>
      <Sidebar view={view} onNavigate={onNavigate} onReplayTour={onReplayTour} open={navOpen} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          totals={totals}
          dataMode={dataMode}
          onReplayTour={onReplayTour}
          theme={theme}
          onToggleTheme={onToggleTheme}
          navOpen={navOpen}
          onToggleNav={onToggleNav}
          user={user}
          onLogout={onLogout}
        />
        <MobileTabs view={view} onNavigate={onNavigate} open={navOpen} />
        <ExpiryBanner expiry={expiry} onNavigate={onNavigate} />
        <main id="main" className="mx-auto w-full max-w-[1320px] flex-1 space-y-8 px-5 py-8 lg:px-8 lg:py-10">
          {children}
        </main>
      </div>
    </div>
  );
}
