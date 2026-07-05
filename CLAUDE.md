# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Risk Cockpit** — a single web platform for Indian retail investors to manage trading
risk (allocation, hedging, options strategy, portfolio analytics, trade journal). The
broker connection is **read-only**: the app reads holdings/prices/history; the user
places all orders at their broker. The full design and phase plan live in the approved
plan file referenced from the README; this file is the working architecture summary.

## Commands

Backend (from `backend/`):
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1            # PowerShell (Windows)
pip install -r requirements.txt
uvicorn app.main:app --reload         # serves http://127.0.0.1:8000, docs at /docs
```
The backend imports the `app` package, so run uvicorn **from `backend/`** (or pass
`--app-dir backend`). Tables auto-create on startup via the FastAPI `lifespan` hook.

Frontend (from `frontend/`):
```bash
npm install
npm run dev      # http://localhost:5173 (proxies /api -> backend)
npm run build    # production build (also the quickest way to catch JSX/build errors)
```

You can avoid `cd` on Windows with `npm --prefix frontend run dev` and
`uvicorn app.main:app --app-dir backend`.

There is **no automated test suite yet**. To smoke-test the backend without HTTP, run a
script from `backend/` (with `backend/` on `PYTHONPATH`) that imports
`app.api.portfolio.get_portfolio` and calls it — the API route handlers are plain
functions and can be called directly.

Standalone credential checks live in `backend/test_angel.py` (Angel One, read-only),
`backend/test_gemini.py` (Gemini), and `backend/test_ai.py` (Claude). Each loads
`backend/.env` via `load_dotenv(Path(__file__)...)` so it runs from anywhere, is
independent of the app, and prints a clear message if its key isn't set.

## Architecture (the parts that span multiple files)

**Market-data provider abstraction is the central seam.** All business logic reads data
through `MarketDataProvider` (`backend/app/data/provider.py`). `get_provider()` in
`backend/app/data/__init__.py` is an `lru_cache`'d factory that returns `CsvProvider`
(offline, default) or `AngelOneProvider` (live, read-only) based on
`settings.data_provider`. Consequences:
- New modules must go through `get_provider()`, never import a concrete provider.
- The Angel One SDK (`smartapi-python`, `pyotp`) is imported **lazily** inside
  `angelone.py`, so CSV mode never needs it installed.
- Because the factory is cached, changing `DATA_PROVIDER` requires a backend restart.

**Holdings have one source of truth: `app/holdings.py:load_holdings()`.** Every module that
needs the portfolio (portfolio, allocation, hedge, risk) calls `load_holdings()`, **not**
`provider.get_holdings()` directly. It returns the user's manually-entered `Position` rows
(their real portfolio) when any exist, otherwise falls back to the provider's holdings
(sample CSV offline / live broker). The manual portfolio is full CRUD at
`GET/POST /api/positions` + `PUT/DELETE /api/positions/{id}` (frontend **My Holdings** page,
`pages/Holdings.jsx`); each `Position` carries `tradingsymbol/exchange/token/lot_size/kind`
so live price resolves and F&O lots are known (`db._migrate_positions()` ALTER-adds these to
existing SQLite rows). Adding the first position silently replaces the sample everywhere.
**Holdings are manual-first by the owner's choice** (he uses different brokers per segment, so
no broker *holdings* import). **But market data is live via a DATA-ONLY Angel feed**
(`app/market.py`, `get_market()`, on when `MARKET_DATA=angel` + Angel creds): it reads the
instrument master (full NSE+BSE stock universe + every F&O contract & lot size) and live LTP
— **never holdings/account**. Equity instrument search is `GET /api/instruments?q=&kind=equity`
(falls back to `data/symbols.py` curated list when the feed is off).

**F&O contracts are picked, not free-searched.** A flat box can't choose among thousands of
strikes — and worse, a substring like `NIFTY` matches every NIFTY-family *future* and fills the
result limit before any option shows (the "no option data in F&O" bug). So the F&O segment uses
a guided picker (`components/FnoPicker.jsx`): **type (Futures/Call/Put) → underlying → expiry →
strike**, backed by `GET /api/fno/underlyings|expiries|contracts` (`api/fno.py` → `market.py`
`fno_underlyings/fno_expiries/fno_contracts`; expiries sorted via `_exp_key`). The picker
resolves a single contract (token + lot size) into the form; quantity = **lots × lot_size**.
On *edit* the contract is shown read-only (you change lots/price, not the instrument). The strike
dropdown marks/auto-selects **ATM** using `ref_price` (the nearest-expiry future's live LTP, from
`market.fno_ref_price`) returned alongside the option chain.

**Basket Order builder (`pages/Basket.jsx`) is analysis-only — it never places an order**
(read-only design: the user takes the basket to their broker). Flow: pick underlying + expiry →
**+ Add future** (live entry price from `GET /api/fno/future` → `market.future_quote`) and/or
**Open option chain** (`GET /api/fno/chain?name=&expiry=&width=` → `market.option_chain`, a live
CE/PE grid around ATM). The chain shows **premium + OI + IV + Greeks per strike**: premium and OI are
raw market data (`market.quote_full` — ONE `getMarketData("FULL",…)` per 50 tokens, since FULL mode
returns `ltp` *and* `opnInterest` together), while IV + delta/gamma/theta/vega are **derived by the
math engine** (`services/options.py:enrich_chain_greeks`, called from `api/fno.py` — back out each
option's implied vol from its live premium via `implied_vol`, then `bs_greeks` off that vol, with spot
= chain `ref_price` and T from `days_to_expiry`). This keeps the math-vs-data line: OI is observed like
LTP, Greeks are computed. The frontend `ChainModal` lays it out as a mirrored grid
(OI·IV·Δ·θ·**LTP** | Strike | **LTP**·θ·Δ·IV·OI); only the clickable **LTP** adds a leg. A strike whose
premium is below intrinsic has no solvable IV → null Greeks → "—". Click a premium to add that leg to the cart (side
toggle Buy/Sell, lots, editable price), then **Analyse basket** → `POST /api/basket/analyse`
(`api/basket.py`). The math reuses the Phase-3 payoff engine: `services/options.py:analyze_basket`
maps a **future leg to an `"underlying"` leg priced at entry** (no upfront premium, so it's excluded
from the net option debit/credit) and options to call/put legs with their **live premium**, then
returns exact payoff curve / max P&L / breakevens, **net Greeks using each option's own implied vol**
(`implied_vol` bisection on `bs_price`), an inferred `view`, and rule-based `observations`. The page
renders `PayoffChart` + metrics + observations + the `Explainer` panel (`module="basket"`, AI narrates
the computed numbers only). A basket is **one underlying, one expiry** (single spot axis); legs live in
React state (no DB persistence) — except **Add to portfolio** (`POST /api/positions/bulk`), which saves
the legs as F&O `Position` rows in My Holdings. A multi-leg save tags every leg with one shared
**`basket_id`** (+ a human `basket_label` like `NIFTY · 31 Jul`) so the UI shows the basket as **one
grouped holding** instead of N separate legs. This is **display-only** — each leg stays its own
`Position` row so the math layer (hedge/risk/allocation) still sees the individual legs; `basket_id`/
`basket_label` are nullable `Position` columns (`db._migrate_positions` ALTER-adds them), echoed by both
`/api/positions` (`_row`) and `/api/portfolio` (via `Holding.basket_id/basket_label`). The frontend
`groupHoldings()` (`api/client.js`) collapses rows sharing a `basket_id` into one summary item (summed
value/P&L); **My Holdings** renders it as an expandable group (toggle to see/Edit/Delete each leg, or
**✕ remove the whole basket**), while the **Dashboard** and **Portfolios** tables show a single
read-only summary row. A single-leg save is left ungrouped (a normal holding).

**Basket extras (margin, hover, portfolio save).** (1) **Margin** is real SPAN+exposure from Angel's
batch calculator (`market.basket_margin` → `getMarginApi`, needs `orderType`+`productType` per leg); the
analyse response carries `margin_required`, `margin_unhedged` (risk legs only — futures + short options,
dropping long-option hedges) and `margin_saved`, so the page shows how much the hedge cuts the margin
(a naked future needs far more). Basket legs therefore carry `token`+`exchange` through to the request.
F&O underlyings can list on **both NFO and BFO** — `market._primary_exchange(name)` locks every `fno_*`
query to the dominant exchange so legs/tokens/margin stay consistent (SENSEX→BFO, most stocks→NFO).
(2) **`PayoffChart.jsx` is interactive**: hover shows a crosshair + tooltip with the price under the
cursor and the P&L there (green profit / red loss / "Breakeven" near 0), interpolated from the curve;
guarded against a zero-width rect. Shared, so the Options page gets it too. (3) Positions now have a
**`side`** (buy/sell) column (`db._migrate_positions` adds it) so short legs are P&L sign-correct
(`Holding.pnl` flips for `side=="sell"`); My Holdings shows a BUY/SELL tag and a Bought/Sold toggle for
F&O. Live option premiums for the chain use `market.ltp_many` (one batched `getMarketData("LTP",…)`,
chunked at 50 tokens/call).

**Live prices are batched + warmed, not one-call-per-stock.** Resolving each holding with its
own `ltpData` call made `/api/portfolio` ~15s and, on a cold feed, fall back to **cost** (the
top bar showed cost totals that never refreshed). Fix: `market.ltp_many({exch:[tokens]})` does
ONE `getMarketData("LTP", …)` call, and `warm_positions(positions)` prefetches the whole
portfolio in one shot — called at the top of `load_holdings()` and `positions._list()`. The
`lifespan` hook also runs `_warm_market()` in a daemon thread (build master + login + prefetch
LTPs) so the first page load is warm/live-correct, and `_LTP_TTL` is 30s. `_resolve_ltp` order
stays: live feed (cache) → CSV provider → manual price → cost. `AngelOneProvider` (the holdings
provider, `DATA_PROVIDER=angelone`) is separate and still stubbed — the market feed is
independent of it. `data/symbols.py` also holds `SECTOR_MAP` (used by `/api/risk`
concentration). History-dependent metrics (correlation, VaR, drawdown, precise beta) still
need `data/history/*.csv` and degrade gracefully for symbols without it.

**Math engine vs. AI is a hard separation.** Every number comes from deterministic code
in `backend/app/services/` (e.g. beta, payoff, Greeks, XIRR, VaR). The AI explainer
(`backend/app/ai/`) only *explains* already-computed numbers in plain language — it must
never produce figures. Keep this boundary when adding features. Services are **pure
functions** (plain data in, plain dicts out — no I/O), so each has a worked example that
matches a hand/spreadsheet calc; `backend/verify_phase{1,2,3,4}.py` are the runnable
checks for the Phase 1 services (`allocation.py`, `sizing.py`, `xirr.py`), Phase 2
(`hedge.py`), Phase 3 (`options.py`) and Phase 4 (`risk.py`, `journal.py`). `xirr.py` is
self-contained (Newton-Raphson + bisection fallback), so no `pyxirr` dependency is needed. **`hedge.py` computes beta as
`Cov(stock, index) / Var(index)` with numpy directly — not `scipy.stats.linregress`** —
to avoid a scipy dependency (cp314 wheels) while getting the same slope/R². Likewise
`options.py` (Phase 3, `verify_phase3.py`) does **Black-Scholes pricing + Greeks with
`math.erf` for the normal CDF**, again to skip scipy. Its payoff analysis scans a grid
that *includes every strike*, so max-profit / max-loss / breakeven come out exact
(piecewise-linear kinks land on grid points). Unbounded profit/loss is decided by the
**upside slope** = net call qty + net underlying qty (puts go to zero as spot→∞, and the
downside is always bounded since spot can't go below 0): slope >0 ⇒ unlimited profit,
slope <0 ⇒ **unlimited loss** (short straddle/strangle, ratio spreads — flagged
`max_loss_unbounded`, demoted in ranking, shown as "Unlimited"). The 17-strategy library
includes an `"underlying"` leg type (worth spot at expiry, delta 1) so covered call /
protective put / collar are modelled exactly.

**AI provider is pluggable, like the data layer.** `settings.ai_provider` selects
`"none"` | `"gemini"` (free tier, `google-genai`) | `"claude"` (paid, `anthropic`), and
`settings.ai_configured` reports whether the selected provider has a key. Provider SDKs
are imported lazily so an unused one never needs installing, and the app runs fully with
`ai_provider="none"` (numbers always come from the formulas). Adding a provider (e.g.
Groq) is a new branch here — never call a provider SDK outside `backend/app/ai/`.
`get_explainer()` (`backend/app/ai/__init__.py`, `lru_cache`'d) returns the
`Gemini`/`Claude`/`None` explainer; each `.explain(module, data)` narrates the
already-computed numbers via the shared `SYSTEM_PROMPT` in `explainer.py` (which forbids
inventing figures) after `_compact()` strips big arrays (payoff curves, series, matrices)
from the payload. Endpoints: `POST /api/ai/explain` (`{module, data}` → plain text, fails
soft so a bad AI call never breaks the page) and `GET /api/ai/status`. The frontend
`components/Explainer.jsx` panel (gold "AI" tag) is dropped into the Allocation, Hedge,
Options and Risk pages; it hides itself when `ai_configured` is false.

**SEBI framing is enforced in code.** Outputs are educational/analytical, not advice.
Wrap analytical API responses with `with_disclaimer(...)` from
`backend/app/core/disclaimers.py` so the disclaimer rides along; the frontend renders it.

**Multi-user auth (Stage 1 shipped).** The app is now **multi-user with per-account data
isolation**. A `User` table (`models/__init__.py`: id=uuid, email, username, bcrypt
`password_hash`, `email_verified`, `username_changes`, `is_admin`) backs email+password
signup/login. **Sessions are a JWT in an httpOnly cookie** (`rw_session`) — a login persists
per browser until logout and the token is unreadable by page scripts. Auth lives in
`backend/app/auth/`: `security.py` (bcrypt hash/verify + PyJWT), `context.py` (a `ContextVar`
+ `current_user_id()`), `deps.py` (`require_user` / `require_admin`). Endpoints:
`api/auth.py` → `POST /api/auth/signup|login|logout`, `GET /api/auth/me` (public);
**every data router is mounted with `dependencies=[Depends(require_user)]`** in `main.py`, so
each data route requires login and 401s otherwise. **Isolation mechanism (important):**
`require_user` is **async** so it sets the request-scoped current user in the request's own
context; the sync endpoints (run in the threadpool) and everything they call read it via
`current_user_id()` — which is what the model `user_id` defaults to and what every query/insert
filters on (was `settings.default_user_id`). Each request has its own context, so users can
never see each other's rows (verified). **First signup = owner**: `is_admin=True` **and** all
pre-existing rows (`user_id == settings.default_user_id`, i.e. `"local-user"`) are re-assigned to
that account — so the original single-user portfolio migrates to the owner, not a stranger.
`load_holdings()` now returns `[]` for a signed-in user with no positions (only the offline/
no-auth context still falls back to the sample). Frontend: `pages/Auth.jsx` (login/signup) gates
the whole app in `App.jsx` (checks `GET /api/auth/me` on mount; `credentials:"include"` on all
fetches; `AuthError` on 401); the Shell top bar shows the username + an "owner" tag + logout.
New settings in `config.py`: `secret_key` (JWT signing — MUST be a long random value in prod),
`jwt_expire_days`, `cookie_secure` (True in prod). Deps added: `bcrypt`, `PyJWT`, `email-validator`.
**Profile shipped** (`pages/Profile.jsx`, opened from the top-bar user chip): `PUT /api/auth/username`
(capped at 3 changes via `User.username_changes`, uniqueness-checked) and `PUT /api/auth/password`
(verifies current password). **Email verification + forgot-password shipped** (`auth/email.py` +
`auth/security.py` purpose tokens): signup emails a 24h `verify` link; `POST /api/auth/verify`,
`verify/resend`, `forgot-password` (never leaks whether an email exists), `reset-password` (30m `reset`
token). Purpose tokens are single-use-by-purpose (a verify token 400s if used to reset). Sender is
pluggable — **Resend** via plain `urllib` (MUST send a real `User-Agent`, else Cloudflare 403s with
"error 1010"); with no key it falls back to dev mode (link logged + returned in `dev_*_link` when
`environment=="development"`). New `config.py`: `resend_api_key`, `email_from`, `app_base_url` (where
verify/reset links point). Frontend: `Auth.jsx` has login/signup/forgot/reset modes (reset via
`?reset=token`, verify via `?verify=token` handled in `App.jsx`); a non-blocking "verify your email"
nudge banner in the Shell. **GOTCHA — Resend test mode:** until a domain is verified at
resend.com/domains (and `EMAIL_FROM` points to it), Resend only delivers to the account owner's own
email; sending elsewhere 403s. Preserve `user_id` + `current_user_id()` scoping on any new table.

**Production deploy (config shipped; deploy is owner-side dashboard work).** One **Docker single
service** (`Dockerfile`, multi-stage: `node` builds `frontend/dist`, then `python:3.12-slim` runs
uvicorn): `main.py` mounts `StaticFiles(frontend/dist, html=True)` at `/` **after** the routers, so
`/api/*`+`/health`+`/docs` win and everything else is the SPA — one origin, so httpOnly cookies work
with no CORS. Mount only happens if `frontend/dist` exists (dev = Vite on 5173, no mount). **Postgres**:
`db.py:_normalize_url` rewrites `postgres://`/`postgresql://` → `postgresql+psycopg://` (driver =
`psycopg[binary]`), adds `pool_pre_ping`+`pool_recycle` (Neon drops idle conns), and the SQLite-only
`_migrate_positions` ALTERs are skipped on Postgres (`create_all` makes complete tables). Switching DB is
purely `DATABASE_URL`. **`render.yaml`** is a Blueprint (Docker web service, `SECRET_KEY` generateValue,
all secrets `sync:false` → set in the Render dashboard). **`backend/migrate_to_postgres.py`** copies local
SQLite → Neon (User uuids preserved so `user_id` links survive; other tables' int ids reassigned).
Owner's data already migrated to Neon. Full runbook in `DEPLOY.md` (rotate secrets, Render Blueprint, env
vars, Hostinger DNS, Resend domain verify). Prod env: `cookie_secure=True`, `environment=production`,
`app_base_url`/`frontend_origin` → the real domain.

**Production deploy (config shipped; deploy is owner-side dashboard work).** One **Docker single
service** (`Dockerfile`, multi-stage: `node` builds `frontend/dist`, then `python:3.12-slim` runs
uvicorn): `main.py` mounts `StaticFiles(frontend/dist, html=True)` at `/` **after** the routers, so
`/api/*`+`/health`+`/docs` win and everything else is the SPA — one origin, so httpOnly cookies work
with no CORS. Mount only happens if `frontend/dist` exists (dev = Vite on 5173, no mount). **Postgres**:
`db.py:_normalize_url` rewrites `postgres://`/`postgresql://` → `postgresql+psycopg://` (driver =
`psycopg[binary]`), adds `pool_pre_ping`+`pool_recycle` (Neon drops idle conns), and the SQLite-only
`_migrate_positions` ALTERs are skipped on Postgres (`create_all` makes complete tables). Switching DB is
purely `DATABASE_URL`. **`render.yaml`** is a Blueprint (Docker web service, `SECRET_KEY` generateValue,
all secrets `sync:false` → set in the Render dashboard). **`backend/migrate_to_postgres.py`** copies local
SQLite → Neon (User uuids preserved so `user_id` links survive; other tables' int ids reassigned).
Owner's data already migrated to Neon. Full runbook in `DEPLOY.md` (rotate secrets, Render Blueprint, env
vars, Hostinger DNS, Resend domain verify). Prod env: `cookie_secure=True`, `environment=production`,
`app_base_url`/`frontend_origin` → the real domain.

**Config & secrets.** `backend/app/core/config.py` (`pydantic-settings`) reads
`backend/.env`. `PROJECT_ROOT` is derived as `config.py`'s `parents[3]`; `DATA_DIR` is
`<root>/data` and holds the SQLite file and CSVs. `.env` is git-ignored and never leaves
the machine.

**Request flow.** `frontend (React/Vite)` → dev-server proxy → `FastAPI` routers in
`backend/app/api/` → provider/services → response. Routers are mounted in
`backend/app/main.py`. Module 1 (Phase 1) endpoints: `GET /api/allocation` (drift +
rebalance report, holdings × bucket targets), `GET/PUT /api/buckets` +
`POST /api/buckets/reset-defaults` (the target plan — PUT replaces the whole set, the
"save my plan" action), `POST /api/sizing` (position size — backend service + endpoint retained,
but the **Position Sizing page was removed from the UI** at the owner's request, so this route is
currently unused; `services/sizing.py` + `verify_phase1.py` still cover it). The default F&O 20 /
Long-term 30 / Swing 50 plan is **seeded on startup** by `seed_default_buckets()` (called
from the `lifespan` hook) if the user has no buckets, so a fresh install isn't an empty
screen. Module 2 (Phase 2): `GET /api/hedge?index=&index_price=&lot_size=&put_premium=&iv=&days_to_expiry=&bucket=`
returns per-stock beta + value-weighted portfolio beta + futures/puts hedge sizing, plus a
full **comparable hedging-strategy library** (`hedge_strategies`: short futures, protective
put ATM/OTM, collar, zero-cost collar, bear put spread, covered call) — each sized to the
beta-adjusted exposure with its cost priced by Black-Scholes (`hedge.py` imports `bs_price`
from `options.py`), floor/cap, what it protects and the trade-off.
**Beta uses REAL daily history, live-first.** When the market feed is on
(`MARKET_DATA=angel`) the hedge endpoint pulls **live daily candles** for every holding
and the index from Angel `getCandleData` (read-only market data) — `market.candle_closes(exchange,
token, days)` (cached per token, `_CANDLE_TTL=1h`) and `market.index_ref(name)` (spot-index
tokens in `_INDEX_TOKENS`: NIFTY/BANKNIFTY/FINNIFTY/MIDCPNIFTY→NSE, SENSEX/BANKEX→BSE). Holdings
carry their `token`/`exchange`/`kind` from the `Position` row (the `Holding` dataclass now has
these), and equity rows without a token resolve via `market.resolve_equity`. This was a real bug
fix: previously beta only came from the sample `data/history/*.csv` (6 stocks + 3 indices), so the
user's real holdings all fell back to **assumed beta 1.0** and **every index reported the same
~1.00 portfolio beta**. Two rules make it correct now: (1) **in live mode there is NO sample-CSV
fallback** — those CSVs are synthetic and uncorrelated with the live index, so regressing them
against live index returns yields a meaningless ~0 beta; a holding with no live candles is flagged
*assumed* instead. **Options (CE/PE) get no regression beta** (premium is driven by theta/vega, not
linearly by spot) — flagged assumed; **equity + futures** get real candle betas. (2) Each holding is
regressed against the index **PAIRWISE** (`_holding_series`/`_index_series` + an inner-join in
`api/hedge.py`, not the old global `aligned_returns` intersection) so one short-history contract
(a freshly listed future) doesn't truncate the beta window for everything else. The regression runs
**per holding** (not via a symbol-keyed map) so an option leg can't inherit the beta of an equity
holding that shares its underlying's symbol; a beta from fewer than `MIN_CONFIDENT_DAYS` (30) overlapping
days is still shown but flagged `low_sample` ("low data" badge), and `candle_closes` caches a
failed/empty fetch only briefly (`_CANDLE_EMPTY_TTL=90s`, vs 1h for a good series) so a transient Angel
hiccup self-heals on the next load instead of pinning a holding to assumed-beta for an hour. Result: portfolio
beta now genuinely **differs by index** (e.g. NIFTY 1.07 / BANKNIFTY 0.79 / SENSEX 1.03) and updates
as holdings change (the endpoint reads `load_holdings()` fresh each call; the Hedge page remounts on
nav and refetches, with a `reqId` guard so fast index switches can't show a stale response).
`data_quality.history_source` is `"live"` vs `"csv"`; the page shows a "Betas from live daily
history" note. **Offline (CSV) mode is unchanged**: `data/history/<SYMBOL>.csv` (`date,close`) for
every holding + index, assumed 1.0 when missing; run `backend/generate_sample_history.py` to
(re)create reproducible sample history with known target betas. `verify_phase2.py` is feed-aware
(asserts sample betas offline, the index-differentiation invariant live). Module 3 (Phase 3):
`GET /api/options?index=&view=&conviction=&days_to_expiry=&budget=&spot=&iv=` ranks the
strategy library for the user's view and returns each candidate's payoff curve, max P/L,
breakevens and net Greeks. In CSV mode the option **chain is built theoretically** from
spot + IV (so it's testable offline); live mode swaps in real chain premiums with no
change to the payoff/Greeks math. Modules 4 & 5 (Phase 4): `GET /api/risk` (concentration
+ sector exposure + Herfindahl, correlation matrix, 1-day historical/parametric VaR +
CVaR, drawdown from a portfolio equity curve built as Σ qty×close, and a daily-loss
guardrail — pass `confidence`/`daily_loss_limit`/`day_pnl`), and the trade journal
`GET/POST /api/journal` + `PUT /api/journal/{id}/close` + `DELETE /api/journal/{id}` over
the `Trade` table (computes per-trade R-multiple/P&L and aggregate win-rate/expectancy/
profit-factor). Risk metrics need the same `data/history/<SYMBOL>.csv` as the hedge module.
**Journal trade dates are mandatory and user-supplied:** `entry_date` is required on every
trade and `exit_date` is required to close one (both ISO `YYYY-MM-DD`, validated — exit can't
precede entry); they map to the `Trade.opened_at`/`closed_at` columns (no new columns). The
journal page splits **Open positions** vs **Closed trades** (a closed entry moves to the
closed table). **Financial-year review** (`GET /api/journal/review` →
`services/journal.py:review_financial_years`) groups *closed* trades into Indian financial
years (1 Apr → 31 Mar) **by exit date**, and for each FY returns overall + **per-segment**
(bucket) stats via `summarize`, plus rule-based **capital-allocation pointers**
(`_allocation_guidance`: top/worst segment, best expectancy, a tilt suggestion) and a
cross-FY `comparison` with YoY P&L change. **Only completed FYs carry guidance** —
`fy_is_complete` gates on 31 Mar having passed, so the current FY is returned flagged
`complete:false` ("in progress, not yet reviewed"). The frontend `FYReview` (in
`pages/Journal.jsx`) renders a year selector + per-segment table + pointers + YoY table +
`Explainer module="journal_review"` (AI narrates the computed numbers only). The add-trade form
and the inline close editor each have a **Cancel** button (reset/dismiss without saving — for
test entries). **The review also folds in still-open holdings.** `review_financial_years` takes a
second arg, `holdings` (open `Position` rows from `_open_holdings()` in `api/journal.py` — bucket,
invested, unrealized P&L, buy_date), and for each FY adds a `held_by_segment`/`held_total` block of
positions **held at that year-end** — a holding counts for every FY from the one it was *bought* in
(by `buy_date`; null → current FY) through the latest, so a long-term position bought once and held
for years shows in each year's review **even though it was never closed** ("automatically in the
calculation"). Held positions are display-only capital context — they are **not** journal trades
(only closed trades appear in the journal list); realised stats still come from closed trades alone,
so there's no double count. `summarize([])` now returns a full zero dict (not just `{count:0}`) so
held-only years don't `KeyError`. NOTE: `/api/journal/review` resolves live prices for every holding,
so it's a ~3-5s call on a cold feed (front-end loads the rest of the page first, review fills in).
**My Holdings and the journal are linked: `POST /api/positions/{id}/close`** (`api/positions.py`,
`CloseHoldingIn`) sells a holding into the journal in one click — it creates a closed `Trade`
(entry = the holding's `buy_date`, or an `entry_date` override if none on file; exit = `exit_date` or
**today**; `entry_price = avg_price`, `stop = avg_price` so R is undefined; `side` buy→long / sell→short)
and **deletes the position**, so it stops counting as open capital and starts counting as a realised
trade in the FY review. The **Close** button + inline editor (sell price + close-date-defaulting-to-today,
plus a buy-date field only when the holding has none) lives in `Holdings.jsx`'s `legRow` next to Edit/Delete.
**Partial close is equity-only:** `CloseHoldingIn.quantity` (optional) sells part of a Swing/Long-term
**EQ** holding — the journal `Trade` logs the sold quantity and the position is *reduced* (same avg_price
/ buy_date) instead of deleted; selling the full quantity (or omitting it) deletes it. Partial is rejected
(400) for F&O (`kind != EQ`) and basket legs (`basket_id` set) — they close in full — and the frontend
only shows the **quantity** input for EQ non-basket rows, so F&O/basket close as before.
**Buy date is now mandatory on every new holding** (My Holdings "Add a holding": `Buy date *`, defaulted to
today, `canSave` blocks without it) so the entry date is captured up front and is already present when the
holding is closed (the close editor's buy-date field only appears for the rare dateless legacy row). The
backend defends this too — `_make` / `update_position` default `buy_date` to **today** when none is sent
(covers the basket-save path), so no new `Position` is ever dateless. Legacy holdings that predated this
were one-time **backfilled to today** at the owner's request (he can Edit any to the real date for accurate
FY attribution).

**F&O expiry: day-before alert + fully-automatic settlement into the journal.** On every app load
`App.jsx` calls `POST /api/positions/settle-expired` (auto-close), then reloads the portfolio, then
`GET /api/positions/expiries` (upcoming). **Expiry is parsed from the tradingsymbol**, not the master
(`api/positions.py:_fno_meta` regex `DDMONYY` + trailing `<strike>CE|PE`) — crucial because expired
contracts are **dropped from the live instrument master**, so a token lookup returns None (the master
lookup `market.expiry_date(token)` is only a fallback). `expiries` buckets F&O holdings into
`expiring_soon` (0–1 day → the "a day before" warn banner) and `expired`. `settle-expired` closes every
holding past expiry into a closed `Trade` and deletes the position (same lifecycle as a manual close).
**Settlement price = INTRINSIC** (owner's choice): options at `max(0, spot−strike)` (calls) /
`max(0, strike−spot)` (puts), futures at spot, where spot = `market.fno_ref_price(underlying)` (nearest-
future LTP). **GOTCHA (learned the hard way):** do NOT price an expired option via `_resolve_ltp` — a dead
option token resolves to the *underlying's* price, recording a massive fake P&L. Falls back to a manual
`ltp` then cost when spot is 0 (offline/cold feed) so P&L is neutral, never fake. Intrinsic uses the
*current* spot as a proxy for the expiry-day spot, so near-the-money past expiries can be slightly off
(the user can edit the journal exit price). The Shell shows an `ExpiryBanner` (warn = expiring within a
day, info = just auto-settled) fed by `App`'s `expiry` state.

**Per-bucket scoping.** Both `/api/hedge` and `/api/risk` take an optional `bucket=` param
(e.g. `Swing`, `Long-term`, `F&O`) so the user can hedge / risk-analyse one capital bucket
at a time instead of the whole portfolio — they hold long-term stock through everything but
trade swing/F&O aggressively, so each sub-portfolio is analysed on its own. Filtering goes
through `scope_holdings()` in `backend/app/api/scope.py`, which returns
`(filtered_holdings, available_buckets, selected_bucket)`; both responses echo `bucket` +
`available_buckets`, and the shared `BucketScope` control (`components/ui.jsx`) drives the
selector on the Hedge and Risk pages.

**Frontend is the "RiskWise" SPA — deep-navy + gold + cream, no router.** `App.jsx` holds a
`view` string and swaps pages (`src/pages/*`) inside `components/Shell.jsx` (grouped sidebar
nav + glass top bar). There is **no react-router** — navigation is plain state, so don't add
routing deps for new pages; just extend the `view` switch (App.jsx) and the `NAV_GROUPS`
array in `Shell.jsx`. Navigation goes through `navigate(view, bucket?)` in `App.jsx`, which
also sets `navScope` — the **Portfolios** page (`pages/Portfolios.jsx`, one card per capital
bucket) uses it to drill into Hedge/Risk pre-scoped to a bucket via
`<Hedge initialBucket={navScope}/>` / `<Risk initialBucket=.../>`.

**Design system (RiskWise brand, supersedes the old Binance-inspired `design-brief.md`).**
Built from the logo — a shield of protection over a managed-risk trendline. Tokens live in
`src/index.css` as a Tailwind v4 `@theme` block; **the semantic names are kept stable**
(`--color-canvas`, `--color-card`, `--color-elevated`, `--color-gold`, `--color-up/down/warn`,
`--color-body/headline/muted`, `--color-hairline`, `--color-onprimary`) so every page re-skins
for free. Added tokens: `--color-canvas-deep`, `--color-gold-bright/pressed/deep`,
`--color-hairline-strong`, and `--shadow-card/pop/gold`. Type pairs **Sora**
(`--font-display`, auto-applied to `h1–h6`) with **Inter** body and **JetBrains Mono** tabular
numbers (`.tnum`).

**Two themes off one gold accent (dark = default).** The `@theme` block holds the **DARK**
palette — a **near-black neutral canvas** (`--color-canvas: #0a0a0b`, no blue), charcoal cards,
cream text, gold `#e6c86e`. **LIGHT** mode overrides the same variables under
`:root[data-theme="light"]` (white canvas `#f6f6f4`, near-black text, a **deeper** gold
`#a9791d` that stays legible on white, `--color-onprimary: #fff` for gold buttons). Utilities
compile to `var(--color-…)`, so flipping the `data-theme` attribute on `<html>` re-skins the
whole app — **so keep using the token utilities, never raw hex** (SVG charts too: `PayoffChart`
and the Risk drawdown/correlation charts reference `var(--color-…)` so they follow the theme).
The toggle lives in the top bar (`Shell.jsx` `ThemeToggle`, sun/moon); `App.jsx` owns the
`theme` state + `onToggleTheme`, persists to `localStorage["rw_theme"]`, and an inline script
in `index.html` applies the saved theme **before first paint** (no flash). `index.css` also owns
the ambient background (radial gold glow + faint grain via a `body::before` feTurbulence
data-URI, both mode-tuned), the motion
system (`rwFadeUp/FadeIn/ScaleIn/Draw/Float/Progress/Halo` keyframes + `.rw-*`/`.rw-d1..d8`
delay utility classes, all disabled under `prefers-reduced-motion`), focus rings, and the
`.skip-link` + `.rw-glass` helpers. Use the token utilities (`bg-canvas`/`text-gold`/
`border-hairline`), **never raw hex**.

**Logo, icons, primitives.** The logo is components in `src/components/Logo.jsx` —
`<LogoMark animated?/>` (shield SVG; `animated` draws the trendline on the splash),
`<Wordmark/>` (RISK cream + WISE gold, Sora), and `<Logo/>` lock-up; the favicon is
`public/riskwise-icon.svg`. `src/components/icons.jsx` exports one stroke-based `<Icon name/>`
set (dashboard/holdings/…/journal + arrow/check/close/help…), shared by the sidebar and the
tutorial — no emoji glyphs. Shared primitives (Card, StatCard, Badge, Button, AlertBanner,
AllocationBar, NumberInput, BucketScope, Field, **PageHeader**) are in `src/components/ui.jsx`;
`Card` takes an optional `accent` (gold top hairline). The options payoff diagram is a
dependency-free inline-SVG component (`src/components/PayoffChart.jsx`) — there is **no
charting library** (no recharts), so draw new charts as SVG rather than adding one. Formatting
+ bucket colors are in `src/api/client.js` (`inr`, `pct`, `pctSigned`, `bucketColor`,
`sendJSON`).

**First-run experience — entrance + live guided tour.** Two separate pieces, both
presentational (no data touched). (1) `components/Onboarding.jsx` is a full-screen overlay
that plays **once per browser session** before the cockpit: **splash** (animated logo + hero
line "Know your risk. Own your edge." + subline, auto-advances) → **intro** (why risk
management) → **gate** (a clickable slogan — "Trade with a plan, not a hope."). Enter advances;
`onDone(withTour)` fires — **Skip / Esc / "Skip to app"** call `onDone(false)` (straight to the
app), the **gate** calls `onDone(true)` (enter **and** start the tour). `App.jsx` gates it on
`sessionStorage["rw_onboarded"]`. (2) `components/GuidedTour.jsx` is the **teacher-style tour
that runs OVER the live cockpit**: one step per tab (welcome + the 9 nav items), each step calls
`onNavigate(view)` to actually open that page, then **spotlights the real nav button** (dimmed
backdrop with a box-shadow cutout + gold ring around the `[data-tour="nav-<view>"]` element,
which both the sidebar and mobile tabs carry). The student can click the highlighted tab (a
click listener advances the tour) or press Next/Back; Enter/→ next, ← back, Esc skips. It
re-measures the target on step change / resize / scroll. `App.jsx` owns `tour` state; the Shell's
**"Take the tour"** (sidebar) and top-bar help button call `replayTour` (= `startTour`, which
also forces the sidebar open). GOTCHA: the spotlight/coach-card use CSS transitions/animations,
which **freeze in a hidden/background browser tab** (so automated previews read frozen positions
and blank splashes) — they animate normally in a real foreground tab.

**Collapsible sidebar (hamburger).** `App.jsx` owns `navOpen`; the top-bar hamburger toggles it.
Collapsing slides the sidebar to zero width (the active tab gets the full width) and reveals the
LogoMark in the top bar. GOTCHA: the sidebar is a **flex item**, so `w-0` alone won't shrink it
(flex items have `min-width:auto` and `flex-basis:auto`); it needs `min-w-0` **and** an explicit
`width`+`flex-basis` (driven by inline style in `Shell.jsx`) to actually collapse.

## Conventions & gotchas

- **Restarting the backend on Windows: avoid `--reload`, or kill the worker child, not
  the listener.** `uvicorn --reload` runs a WatchFiles *reloader* parent plus a
  *multiprocessing-fork* worker child; the child is what binds port 8000. Force-killing
  the PID that `Get-NetTCPConnection -LocalPort 8000` reports can orphan the worker, which
  keeps serving **stale code** (e.g. a newly added router 404s even though the source is
  correct). Find the real culprit with
  `Get-CimInstance Win32_Process -Filter "Name='python.exe'"` and kill the
  `--multiprocessing-fork` child. Simplest: run uvicorn **without** `--reload` and restart
  it deliberately after adding routers.

- **Python deps are intentionally unpinned** in `requirements.txt`. The dev machine runs
  Python 3.14, so pip must resolve the latest wheels (currently pandas 3.x / numpy 2.x).
  Don't pin to older versions that lack `cp314` wheels.
- **Vite proxy targets `http://127.0.0.1:8000`, not `localhost`.** On Windows `localhost`
  resolves to IPv6 `::1` first and uvicorn binds IPv4, causing 502s. Keep the explicit
  IPv4 host in `frontend/vite.config.js`.
- CSV provider columns: `holdings.csv` = `symbol,quantity,avg_price,bucket`;
  `prices.csv` = `symbol,ltp`; optional `data/history/<SYMBOL>.csv` = `date,close`.
  Missing files degrade gracefully (empty result) rather than crashing.
- Currency is INR; the frontend formats with `Intl.NumberFormat("en-IN", …)` (lakh/crore
  grouping) via the `inr()` helper in `frontend/src/api/client.js`.
- **Keep script `print()` output ASCII-only.** The Windows console is cp1252 — emoji or
  en/em-dashes raise `UnicodeEncodeError` and crash the script (learned the hard way in
  the `test_*.py` scripts).
- **Gemini `gemini-2.5-flash` is a "thinking" model** — it spends part of its output-token
  budget on internal reasoning, so a low `max_output_tokens` truncates the visible reply
  (a 200-token cap returned a half sentence; even at 800 tokens a *larger* explainer prompt
  came back cut off at ~80 chars). The fix in `GeminiExplainer` is to **disable thinking**
  via `types.ThinkingConfig(thinking_budget=0)` (wrapped in try/except so older SDKs without
  it still work) so the whole budget goes to the visible answer — a `*-flash-lite` model
  would also avoid it.
- AI provider SDKs (`google-genai` for Gemini, `anthropic` for Claude) are in
  `requirements.txt` but imported lazily in `backend/app/ai/`; the unused one need not be
  installed. The free path is `AI_PROVIDER=gemini` (key from aistudio.google.com, created
  in a **non-billing** project — a billing-enabled project returns 429 "prepayment credits
  depleted").
