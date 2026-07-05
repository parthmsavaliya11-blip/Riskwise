# Deploying RiskWise to Render + your domain

Everything is prepared: one Docker service builds the React app and serves it together
with the FastAPI backend, on **Neon Postgres**. Your portfolio is already migrated to
Neon. Follow these steps.

---

## 0. Rotate the secrets you pasted in chat (do this first)

Because your Resend key and Neon password were shared in chat, treat them as exposed:

- **Neon** → your project → *Roles* / *Connection Details* → **reset the password**. Copy the
  new connection string. (Your data stays — only the password changes.)
- **Resend** → *API Keys* → delete the old key, **create a new one**.

You'll paste the **new** values into Render (step 2), never into chat.

---

## 1. Deploy on Render (Blueprint)

1. Go to **render.com** → sign up (use "Continue with GitHub").
2. **New +** → **Blueprint** → connect your GitHub and pick **`parthmsavaliya11-blip/Riskwise`**.
3. Render reads `render.yaml` and shows one service, **riskwise**. Click **Apply**.
4. It will ask you to fill the **secret** environment variables (the ones marked "sync:false").
   `SECRET_KEY` is generated automatically — leave it.

## 2. The environment variables to set

| Key | Value |
|---|---|
| `DATABASE_URL` | your **new** Neon connection string (`postgresql://…?sslmode=require`) |
| `RESEND_API_KEY` | your **new** Resend key |
| `EMAIL_FROM` | `RiskWise <onboarding@resend.dev>` for now (change after step 5) |
| `APP_BASE_URL` | leave as the Render URL for now (e.g. `https://riskwise.onrender.com`) |
| `FRONTEND_ORIGIN` | same as `APP_BASE_URL` |
| `GEMINI_API_KEY` | your Gemini key (from your local `.env`) |
| `ANGEL_API_KEY`, `ANGEL_CLIENT_CODE`, `ANGEL_PIN`, `ANGEL_TOTP_SECRET` | your Angel creds (from `.env`) — the data-only live feed |

> Don't want live prices on the server for now? Set `MARKET_DATA=none` and skip the Angel vars —
> everyone (including you) enters holdings manually. You can flip it on later.

## 3. First deploy

Render builds the Docker image (5–10 min the first time) and gives you a URL like
`https://riskwise.onrender.com`. Open it — you should see the RiskWise login.
**Log in with your existing account** (`Apex_11` + your password) — your 10 holdings are
already there (migrated to Neon).

> Free plan note: the service **sleeps after ~15 min idle**, so the first hit after a nap
> takes ~30–60s to wake. Fine to start; upgrade to a paid instance for always-on.

## 4. Point your domain (Hostinger → Render)

1. In Render → your service → **Settings → Custom Domains → Add** `riskwise.yourdomain.com`
   (or the apex `yourdomain.com`).
2. Render shows the exact DNS record (a **CNAME** for a subdomain, or **A records** for the apex).
3. In **Hostinger → your domain → DNS**, add that record. Wait for it to verify (minutes to a few hours).
4. Back in Render env vars, set **`APP_BASE_URL`** and **`FRONTEND_ORIGIN`** to
   `https://riskwise.yourdomain.com` and **redeploy** (so verification/reset links point at your domain).

## 5. Turn on emails to real users (Resend domain)

Until now, Resend only emails **you**. To send verification / reset emails to anyone:

1. **Resend → Domains → Add domain** (`yourdomain.com`) → add the DNS records it gives you in Hostinger.
2. Once verified, set **`EMAIL_FROM`** in Render to `RiskWise <noreply@yourdomain.com>` and redeploy.

---

## You're live

- Sign up **first** on the live site becomes owner — that's already you (`Apex_11`), so you're set.
- Share the link only after step 3 works; each new signup gets their **own** private portfolio.

## Re-running the data migration (only if needed)
If you add more holdings locally before going live and want to re-copy:
```
cd backend ; .venv\Scripts\Activate.ps1
$env:TARGET_DATABASE_URL="<your Neon url>"
python migrate_to_postgres.py   # wipes + recopies — don't run after real users have data
```
