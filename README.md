# 🛡️ Risk Cockpit — Risk management for the Indian retail investor

One place to manage **all** your trading risk. You connect your broker once (read-only)
and do everything risk-related here; you place actual orders at your broker. Built for
the Indian market (NSE/BSE, Nifty/Bank Nifty F&O).

> ⚠️ **For education and analysis only — not investment advice.** This tool never places
> orders. You always trade through your own broker.

## What it does (planned modules)

1. **Allocation + position sizing** — split capital into buckets (e.g. F&O 20% /
   Long-term 30% / Swing 50%), track drift, see which bucket really earns best (XIRR),
   and size positions by the 1–2% risk rule.
2. **Beta hedge** — portfolio beta → how many index futures/puts to hedge.
3. **Options strategy recommender** — your view on an index → best strategy with payoff
   chart, P/L, breakevens, Greeks.
4. **Portfolio risk analytics** — concentration, correlation, VaR, drawdown, daily-loss
   guardrail.
5. **Trade journal** — R-multiples, win rate, expectancy.

A Claude-powered explainer teaches and explains every result in plain language. All
numbers come from transparent formulas; the AI only explains them.

---

## Project layout

```
backend/    Python + FastAPI (the maths + APIs + broker connection)
frontend/   React + Vite + Tailwind (the dashboard you see)
data/        your CSV files + the local database
```

## Requirements (one-time install)

- **Python 3.11+** (you have 3.14) — https://www.python.org/downloads/
- **Node.js 18+** (you have 22) — https://nodejs.org/

## Setup (one-time)

### 1. Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell:  .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env           # then open .env and fill in your keys (optional for now)
```

### 2. Frontend
```bash
cd frontend
npm install
```

## Running the app (every time)

Open **two** terminals.

**Terminal 1 — backend:**
```bash
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```
Backend runs at http://127.0.0.1:8000 (API docs at http://127.0.0.1:8000/docs).

**Terminal 2 — frontend:**
```bash
cd frontend
npm run dev
```
Open the link it prints (http://localhost:5173). 🎉

The app works **immediately in CSV mode** — no broker or API keys needed. It reads the
sample portfolio in `data/holdings.csv` and `data/prices.csv`.

---

## Connecting your data

### Option A — CSV / manual (default, no setup)
Edit these files in the `data/` folder:
- `holdings.csv` → `symbol, quantity, avg_price, bucket`
- `prices.csv` → `symbol, ltp` (last traded price)

### Option B — Angel One SmartAPI (live, read-only)
1. Open an **Angel One** account and go to https://smartapi.angelone.in
2. Create an app (Market / Trading & Historical) → get your **API Key**.
3. Enable **TOTP** and save the **TOTP secret**.
4. In `backend/.env` set `DATA_PROVIDER=angelone` and fill in `ANGEL_API_KEY`,
   `ANGEL_CLIENT_CODE`, `ANGEL_PIN`, `ANGEL_TOTP_SECRET`.

> 🔒 **Security:** your `.env` file stays on your computer, is never committed to git,
> and is never sent anywhere. Never paste API keys, PINs or TOTP secrets into a chat.

### AI explainer (optional)
Add `ANTHROPIC_API_KEY` (from https://console.anthropic.com) to `backend/.env` to turn
on plain-language explanations.

---

## Status

- ✅ **Phase 0 — Foundation:** backend + frontend + swappable data layer (CSV live now,
  Angel One ready to wire), database, dashboard. **Working.**
- ⏳ Phase 1 — Allocation + position sizing
- ⏳ Phase 2 — Beta hedge
- ⏳ Phase 3 — Options recommender
- ⏳ Phase 4 — Risk analytics + trade journal
- ⏳ Phase 5 — AI explainer + polish
