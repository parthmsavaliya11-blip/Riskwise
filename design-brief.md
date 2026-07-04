# Risk Cockpit — Design System (Binance-inspired, eye-friendly dark)

Design spec for **Risk Cockpit**, a risk-management web app for Indian retail investors.
Adapted from the Binance design language — dark canvas, a single scarce gold accent, and
green/red trading semantics — but **tuned to be smooth, attractive, and easy on the eyes**
(soft off-white text, restrained accent, gentle contrast, a little more breathing room).

## Vibe

Authoritative but calm trading-dashboard. Near-black canvas, white-ish type, one gold
accent that does all the brand work. Numbers are the heroes (P&L, allocation %, beta,
payoff) so they read at a glance and feel trustworthy. **Single dark theme** to start —
all our surfaces are dashboards, and we're read-only (no buy/deposit flows), so we don't
need a light transactional mode yet (optional later).

**Eye-comfort rules (our adaptation):**
- Body text is soft `#EAECEF`, never pure white. Muted labels `#707A8A`.
- Gold accent is used *scarcely* — primary CTAs, the wordmark, one key headline per view.
  Big emphasis otherwise uses white text, not yellow.
- Green/red are **text colors / thin accents only**, never large saturated card fills.
- Slightly more whitespace than Binance (we teach beginners; give content room).

## Colors

### Canvas & surfaces (dark)
| Role | Hex |
|------|-----|
| Canvas (page floor) | `#0B0E11` |
| Card surface | `#1E2329` |
| Elevated surface (nested cards, hover, chart panels) | `#2B3139` |
| Input background | `#2B3139` |

### Accent (single brand color — use scarcely)
| Role | Hex |
|------|-----|
| **Primary / gold** | `#FCD535` |
| Primary pressed | `#F0B90B` |
| Primary disabled (on dark) | `#3A3A1F` |
| On-primary text (black on gold) | `#181A20` |

### Trading semantics (text/accents only — never card fills)
| Role | Hex |
|------|-----|
| Up / profit (green) | `#0ECB81` |
| Down / loss (red) | `#F6465D` |
| Warning / drift / guardrail (amber) | `#F59E0B` |
| Info / focus ring | `#3B82F6` |

### Text & lines
| Role | Hex |
|------|-----|
| Body text (soft, default) | `#EAECEF` |
| High-contrast headline | `#FFFFFF` |
| Muted (labels, captions, table headers) | `#707A8A` |
| Muted strong | `#929AA5` |
| Hairline / divider on dark | `#2B3139` |

**Bucket accent colors:** F&O = `#F6465D`, Long-term = `#0ECB81`, Swing = `#F59E0B`,
Unassigned = `#707A8A`.

## Typography

Binance's BinanceNova/BinancePlex are proprietary, so we substitute open-source:
- **UI / copy:** **Inter** (display + body).
- **Numbers (prices, %, stats, payoff, beta):** Inter with `font-variant-numeric:
  tabular-nums`, or **JetBrains Mono / IBM Plex Mono** for big stat displays — so figures
  align in tables and feel "tabular and reliable."

| Role | Size / Weight | Use |
|------|---------------|-----|
| Hero / page H1 | 32px / 700 | Dashboard title, big claim |
| Section head | 24px / 600 | Module section titles |
| Card title | 16px / 600 | Card / panel headers |
| Big stat number | 28–40px / 700, tabular | Portfolio value, P&L, prize numbers |
| Table number | 14–16px / 500, tabular | Prices, %, cells |
| Body | 14px / 400 | Running text |
| Label / caption | 12px / 500, muted | Field labels, table headers, captions |
| Button | 14px / 600 | CTA labels |

Display weights stay **bold (700)** — a trading dashboard wants numbers and headings to
read at a glance. Don't soften to 400.

## Layout

- **App shell:** left **sidebar** (collapsible) nav — Dashboard, Allocation, Position
  Sizing, Hedge, Options, Risk Analytics, Journal, Settings — + a **top bar** with
  portfolio value, day P&L, and the data-mode badge (CSV / Live).
- **Content:** flat card grid on `#0B0E11`, cards `#1E2329`, max width ~1280px.
- **Spacing scale (4px base):** 4 · 8 · 12 · 16 · 24 · 32 · 48 · 80. Card padding 24px;
  section rhythm ~64–80px; grid gutters 24px.
- **Density:** denser than airy marketing sites, but uniform — let color contrast
  (gold vs dark, green vs red) do the separation, with consistent spacing.

## Elevation & shape

- **Flat surfaces, color-block separation** — depth comes from the lightness step between
  `#0B0E11` → `#1E2329` → `#2B3139`. No heavy drop shadows, **no gradients/glow** on
  canvas (one exception allowed: a subtle gold→dark hero gradient on a special landing/
  empty-state, used once).
- **Hairlines:** 1px `#2B3139` for dividers, table rows, input borders.
- **Focus ring:** `0 0 0 2px` of `#3B82F6` at ~50% alpha on inputs/buttons.
- **Radius:** buttons 6px · inputs/cards 8px · elevated card containers 12px · pill
  (9999px) for the top "primary action"; circles for coin icons/avatars.

## Components (mapped to our product)

- **button-primary:** gold `#FCD535` bg, black `#181A20` text, 6px radius, 40px tall —
  the one primary CTA everywhere. Pressed → `#F0B90B`. (Pill variant for the top action.)
- **button-secondary:** `#1E2329` bg, soft text, 6px radius, for less-emphasized actions.
- **stat-card:** `#1E2329`, 12px radius, 24px padding — label (muted) + big tabular
  number; P&L colored green/red as **text**.
- **allocation-bar / donut:** bucket-colored, target marker, amber drift badge when out of
  band.
- **price / pnl cell:** transparent, green/red text + ▲/▼ arrow (never color alone).
- **alert-banner:** thin left-accent + tint — amber (warning) / red (breach) / green (ok).
- **beta-gauge:** radial gauge 0–2, gold needle, muted track.
- **payoff-chart:** line/area; profit zone subtle green, loss zone subtle red; breakeven +
  max-profit/max-loss markers; dark `#2B3139` plot panel.
- **correlation-heatmap:** muted→info blue scale, values labeled; avoid harsh reds.
- **data-table:** hairline row dividers, hover `#2B3139`, right-aligned tabular numbers.
- **explainer-panel:** `#1E2329` card with a small "AI" gold tag, plain-language text +
  the disclaimer — soft, low contrast.
- **badges/pills:** rounded-full for status (Live/CSV, In-band/Drifted, Open/Closed).

## Do / Don't

**Do**
- Reserve gold `#FCD535` for primary CTAs, the wordmark, and one key headline per view —
  its scarcity is the brand.
- Keep black-on-gold as the primary button (don't invert to white-on-gold).
- Use green/red only for price-direction / profit-loss meaning, as text or thin accents.
- Use tabular numerals for every figure.
- Anchor bands on the spacing scale; keep contrast comfortable, not glaring.

**Don't**
- No second brand color; no yellow body text or yellow fills.
- No green/red **card-background** fills (they're price signals, not surfaces).
- No atmospheric gradients/glow on the canvas.
- Don't push contrast to pure-black/pure-white extremes — keep body at `#EAECEF`.

## Responsive

- **< 768px:** sidebar → bottom tab bar / hamburger sheet; cards stack 1-up; tables become
  horizontally scrollable per-row cards; big stat numbers shrink, don't wrap.
- **768–1024px:** sidebar tightens; grids 2-up.
- **≥ 1024px:** full sidebar; multi-column dashboards; analytics in main + side-rail split.
- Touch targets ≥ 40px; coin/asset icons fixed 24/32px.
