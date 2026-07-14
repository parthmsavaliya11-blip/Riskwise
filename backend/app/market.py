"""Angel market-data feed — DATA ONLY (instrument list, lot sizes, live prices).

This never reads the user's holdings or account. It powers:
  * full NSE + BSE stock search (the instrument master),
  * F&O contract search + per-contract lot sizes,
  * live LTP for the user's manually-entered holdings.

Enabled only when ``settings.market_enabled`` (MARKET_DATA=angel + Angel creds).
The instrument master is a public file (no auth); LTP needs the SmartConnect session.
Everything degrades gracefully — any failure returns empty/0 so the app keeps working.
"""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timedelta
from functools import lru_cache

from .core.config import DATA_DIR, settings


def _exp_key(expiry: str):
    """Sort key for an Angel expiry string like '30JUN2026' (earliest first)."""
    try:
        return (0, datetime.strptime(expiry, "%d%b%Y"))
    except (ValueError, TypeError):
        return (1, datetime.max)  # unparseable expiries sink to the bottom

INSTRUMENT_URL = (
    "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
)
_MASTER_PATH = DATA_DIR / "angel_instruments.json"
_MASTER_TTL = 24 * 3600          # refresh the instrument dump daily
_LTP_TTL = 30                    # seconds to cache a live price (risk dashboard, not a scalping terminal)
_CANDLE_TTL = 3600               # daily candles barely move intraday; cache per token for the session
_CANDLE_EMPTY_TTL = 90           # but cache a FAILED/empty fetch only briefly, so a transient Angel
                                 # hiccup doesn't pin a holding to assumed-beta for a whole hour
_CANDLE_MIN_GAP = 0.34           # min seconds between historical calls (Angel caps ~3 req/s)
_MARGIN_TTL = 120                # SPAN+exposure margin barely moves intraday; cache per leg-set

# Spot-index tokens for historical candles (stable Angel tokens; exchange = segment).
# Used so beta is computed against the REAL index series, not a sample CSV. Each index
# regresses differently against a stock, which is the whole point of choosing one.
_INDEX_TOKENS = {
    "NIFTY": ("NSE", "99926000"),
    "BANKNIFTY": ("NSE", "99926009"),
    "FINNIFTY": ("NSE", "99926037"),
    "MIDCPNIFTY": ("NSE", "99926074"),
    "SENSEX": ("BSE", "99919000"),
    "BANKEX": ("BSE", "99919012"),
}

# Cash equity series we treat as "stocks" on NSE; BSE cash has no series suffix.
_NSE_EQ_SERIES = ("-EQ", "-BE")
_FUT_TYPES = ("FUTSTK", "FUTIDX")
_OPT_TYPES = ("OPTSTK", "OPTIDX")


class AngelMarket:
    def __init__(self):
        self._client = None
        self._equity: list[dict] | None = None
        self._fno: list[dict] | None = None
        self._by_token: dict[str, dict] = {}
        self._eq_by_symbol: dict[str, dict] = {}
        self._ltp_cache: dict[str, tuple[float, float]] = {}
        self._candle_cache: dict[str, tuple[float, object]] = {}
        self._last_candle_ts: float = 0.0
        self._primary_exch: dict[str, str | None] = {}
        self._margin_cache: dict[tuple, tuple[float, float | None]] = {}

    # --- session (only needed for live LTP) -------------------------------
    def _session(self):
        if self._client is not None:
            return self._client
        import pyotp
        from SmartApi import SmartConnect

        s = settings
        client = SmartConnect(api_key=s.angel_api_key)
        client.generateSession(s.angel_client_code, s.angel_pin, pyotp.TOTP(s.angel_totp_secret).now())
        self._client = client
        return client

    # --- instrument master ------------------------------------------------
    def _raw_master(self) -> list[dict]:
        try:
            if _MASTER_PATH.exists() and (time.time() - _MASTER_PATH.stat().st_mtime) < _MASTER_TTL:
                return json.loads(_MASTER_PATH.read_text())
        except Exception:
            pass
        data = json.loads(urllib.request.urlopen(INSTRUMENT_URL, timeout=90).read())
        try:
            _MASTER_PATH.write_text(json.dumps(data))
        except Exception:
            pass
        return data

    def _build(self) -> None:
        if self._equity is not None:
            return
        equity: list[dict] = []
        fno: list[dict] = []
        for d in self._raw_master():
            seg = d.get("exch_seg")
            itype = d.get("instrumenttype") or ""
            sym = d.get("symbol") or ""
            name = (d.get("name") or "").upper()
            token = d.get("token")
            try:
                lot = int(float(d.get("lotsize") or 1))
            except (TypeError, ValueError):
                lot = 1

            if itype == "" and seg == "NSE" and sym.endswith(_NSE_EQ_SERIES):
                rec = {"symbol": name, "tradingsymbol": sym, "exchange": "NSE",
                       "token": token, "lot_size": 1, "name": name, "kind": "EQ"}
                equity.append(rec)
                self._eq_by_symbol.setdefault(name, rec)
                self._by_token[token] = rec
            elif itype == "" and seg == "BSE" and name and not sym.startswith("NIFTY"):
                rec = {"symbol": name, "tradingsymbol": sym, "exchange": "BSE",
                       "token": token, "lot_size": 1, "name": name, "kind": "EQ"}
                equity.append(rec)
                self._eq_by_symbol.setdefault(name, rec)
                self._by_token[token] = rec
            elif itype in _FUT_TYPES or itype in _OPT_TYPES:
                strike = 0.0
                try:
                    strike = float(d.get("strike") or 0) / 100.0  # master stores paise
                except (TypeError, ValueError):
                    pass
                rec = {
                    "symbol": sym, "tradingsymbol": sym, "exchange": seg, "token": token,
                    "lot_size": lot, "name": name, "expiry": d.get("expiry") or "",
                    "strike": strike, "instrumenttype": itype,
                    "kind": "FUT" if itype in _FUT_TYPES else ("CE" if sym.endswith("CE") else "PE"),
                }
                fno.append(rec)
                self._by_token[token] = rec

        self._equity = equity
        self._fno = fno

    def expiry_date(self, token):
        """Expiry date (``datetime.date``) for an F&O instrument token, or None.

        Read-only lookup in the instrument master — used to detect holdings at/after
        expiry so they can be auto-settled into the journal. Returns None for equity,
        unknown tokens, or an unparseable expiry.
        """
        if not token:
            return None
        self._build()
        rec = self._by_token.get(str(token)) or self._by_token.get(token)
        exp = (rec or {}).get("expiry") or ""
        try:
            return datetime.strptime(exp, "%d%b%Y").date()
        except (ValueError, TypeError):
            return None

    # --- search -----------------------------------------------------------
    def search_equity(self, query: str | None, limit: int = 25) -> list[dict]:
        self._build()
        items = self._equity or []
        if not query:
            return [self._eq_out(r) for r in items[:limit]]
        q = query.strip().upper()
        scored = []
        for r in items:
            s = r["symbol"]
            if s == q:
                scored.append((0, r))
            elif s.startswith(q):
                scored.append((1, r))
            elif q in s:
                scored.append((2, r))
        scored.sort(key=lambda x: (x[0], x[1]["symbol"]))
        return [self._eq_out(r) for _, r in scored[:limit]]

    def search_fno(self, query: str | None, limit: int = 30) -> list[dict]:
        self._build()
        items = self._fno or []
        if not query:
            return []
        q = query.strip().upper().replace(" ", "")
        scored = []
        for r in items:
            sym = r["symbol"]
            if q in sym or q in r["name"]:
                # futures first, then by expiry then strike
                rank = 0 if r["kind"] == "FUT" else 1
                scored.append((rank, r["expiry"], r["strike"], r))
        scored.sort(key=lambda x: (x[0], x[1], x[2]))
        return [self._fno_out(r) for *_, r in scored[:limit]]

    # --- F&O picker: underlying -> expiry -> strike -----------------------
    # A flat search box can't pick among thousands of strikes, so the add-holding
    # form narrows step by step. kind="fut" -> futures; kind="opt" -> options.
    def fno_underlyings(self, query: str | None, kind: str = "fut", limit: int = 25) -> list[dict]:
        self._build()
        want_fut = kind != "opt"
        q = (query or "").strip().upper().replace(" ", "")
        seen: dict[str, dict] = {}
        for r in (self._fno or []):
            if (r["kind"] == "FUT") != want_fut:
                continue
            name = r["name"]
            if q and q not in name:
                continue
            cur = seen.get(name)
            if cur is None:
                seen[name] = {"name": name, "lot_size": r["lot_size"], "exchange": r["exchange"]}
        def rank(name: str) -> tuple:
            if not q:
                return (0, name)
            if name == q:
                return (0, name)
            if name.startswith(q):
                return (1, name)
            return (2, name)
        out = sorted(seen.values(), key=lambda r: rank(r["name"]))
        return out[:limit]

    def _primary_exchange(self, name: str) -> str | None:
        """The exchange carrying the most F&O contracts for an underlying.

        Some stocks list options on BOTH NFO and BFO; a basket must stay on one
        exchange (mixed-exchange legs break the margin call and live tokens), so every
        fno_* query below locks to this. SENSEX/BANKEX resolve to BFO, most stocks NFO.
        """
        name = (name or "").strip().upper()
        if self._primary_exch.get(name):
            return self._primary_exch[name]
        self._build()
        counts: dict[str, int] = {}
        for r in (self._fno or []):
            if r["name"] == name:
                counts[r["exchange"]] = counts.get(r["exchange"], 0) + 1
        exch = max(counts, key=counts.get) if counts else None
        if exch:  # don't cache a miss (e.g. called before the master was built)
            self._primary_exch[name] = exch
        return exch

    def fno_expiries(self, name: str, kind: str = "fut") -> list[str]:
        self._build()
        want_fut = kind != "opt"
        name = (name or "").strip().upper()
        exch = self._primary_exchange(name)
        exps = {
            r["expiry"]
            for r in (self._fno or [])
            if r["name"] == name and r["exchange"] == exch
            and (r["kind"] == "FUT") == want_fut and r["expiry"]
        }
        return sorted(exps, key=_exp_key)

    def fno_ref_price(self, name: str) -> float:
        """A live reference level for marking ATM — the nearest-expiry future's LTP.

        Options are centered on the forward, and every F&O underlying (index or
        stock) has a future, so this is a uniform ATM reference. 0 if unavailable.
        """
        for f in self.fno_contracts(name, "fut"):  # sorted nearest-expiry first
            ltp = self.ltp_by_token(f["exchange"], f["token"])
            if ltp > 0:
                return ltp
        return 0.0

    def future_quote(self, name: str, expiry: str | None = None) -> dict | None:
        """The futures contract for an underlying (+ live LTP) for the 'Add future' action.

        Prefers the requested expiry; falls back to the nearest future (e.g. weekly
        option expiries have no matching future) and flags whether it matched.
        """
        futs = self.fno_contracts(name, "fut")  # nearest-expiry first
        if not futs:
            return None
        chosen = next((f for f in futs if f["expiry"] == expiry), None) if expiry else None
        matched = chosen is not None
        chosen = chosen or futs[0]
        ltp = self.ltp_by_token(chosen["exchange"], chosen["token"])
        return {**chosen, "ltp": ltp, "matched_expiry": matched}

    def fno_contracts(self, name: str, kind: str = "fut", expiry: str | None = None,
                      right: str | None = None) -> list[dict]:
        self._build()
        want_fut = kind != "opt"
        name = (name or "").strip().upper()
        right = (right or "").strip().upper()
        exch = self._primary_exchange(name)
        out = []
        for r in (self._fno or []):
            if r["name"] != name or r["exchange"] != exch or (r["kind"] == "FUT") != want_fut:
                continue
            if expiry and r["expiry"] != expiry:
                continue
            if not want_fut and right and r["kind"] != right:
                continue
            out.append(self._fno_out(r))
        out.sort(key=lambda x: (_exp_key(x["expiry"]), x["strike"]))
        return out

    def _eq_out(self, r: dict) -> dict:
        return {"symbol": r["symbol"], "name": r["name"], "exchange": r["exchange"],
                "token": r["token"], "lot_size": 1, "kind": "EQ"}

    def _fno_out(self, r: dict) -> dict:
        return {"symbol": r["symbol"], "name": r["name"], "exchange": r["exchange"],
                "token": r["token"], "lot_size": r["lot_size"], "expiry": r["expiry"],
                "strike": r["strike"], "kind": r["kind"]}

    # --- live LTP ---------------------------------------------------------
    def lot_size_for(self, token: str) -> int:
        self._build()
        rec = self._by_token.get(str(token))
        return int(rec.get("lot_size", 1)) if rec else 1

    def resolve_equity(self, symbol: str) -> dict | None:
        self._build()
        return self._eq_by_symbol.get(symbol.strip().upper())

    def ltp_by_token(self, exchange: str, token: str) -> float:
        token = str(token)
        cached = self._ltp_cache.get(token)
        if cached and time.time() - cached[0] < _LTP_TTL:
            return cached[1]
        self._build()
        rec = self._by_token.get(token)
        tsym = rec["tradingsymbol"] if rec else ""
        exch = exchange or (rec["exchange"] if rec else "NSE")
        try:
            resp = self._session().ltpData(exch, tsym, token)
            ltp = float(((resp or {}).get("data") or {}).get("ltp", 0) or 0)
        except Exception:
            ltp = 0.0
        self._ltp_cache[token] = (time.time(), ltp)
        return ltp

    # --- historical candles (read-only, for beta / correlation / VaR) -----
    def index_ref(self, name: str) -> tuple[str, str] | None:
        """(exchange, token) for an index's spot series, or None if unknown."""
        return _INDEX_TOKENS.get((name or "").strip().upper())

    def candle_closes(self, exchange: str, token: str, days: int = 400):
        """Daily close series (pandas Series indexed by date) via Angel getCandleData.

        This is read-only historical market data (never holdings/account) used to
        compute a *real* beta for each holding against the chosen index — so different
        indices genuinely differ. Cached per token for the session; any failure returns
        an empty Series so the caller degrades to CSV history / an assumed beta.
        """
        import pandas as pd

        token = str(token)
        key = f"{exchange}:{token}"
        cached = self._candle_cache.get(key)
        if cached:
            ts, ser = cached
            # A good series is cached for the hour; an empty (failed) one only briefly so
            # a transient failure self-heals on the next page load instead of sticking.
            ttl = _CANDLE_TTL if (ser is not None and len(ser) > 0) else _CANDLE_EMPTY_TTL
            if time.time() - ts < ttl:
                return ser

        series = pd.Series(dtype=float)
        try:
            end = datetime.now()
            start = end - timedelta(days=max(days, 30))
            params = {
                "exchange": exchange or "NSE",
                "symboltoken": token,
                "interval": "ONE_DAY",
                "fromdate": start.strftime("%Y-%m-%d %H:%M"),
                "todate": end.strftime("%Y-%m-%d %H:%M"),
            }
            # Pace consecutive historical calls to stay under Angel's ~3 req/s cap, but
            # don't sleep when calls are already naturally spaced (cache hits in between).
            gap = _CANDLE_MIN_GAP - (time.time() - self._last_candle_ts)
            if gap > 0:
                time.sleep(gap)
            resp = self._session().getCandleData(params)
            self._last_candle_ts = time.time()
            rows = (resp or {}).get("data") or []
            if rows:
                # rows: [timestamp, open, high, low, close, volume]; use date + close.
                idx = pd.to_datetime([str(r[0])[:10] for r in rows])
                closes = [float(r[4]) for r in rows]
                series = pd.Series(closes, index=idx, name="close").sort_index()
                series = series[~series.index.duplicated(keep="last")]
        except Exception:
            series = pd.Series(dtype=float)
        self._candle_cache[key] = (time.time(), series)
        return series

    def basket_margin(self, positions: list[dict]) -> dict | None:
        """Net margin for a basket via Angel's batch margin calc (SPAN + exposure).

        ``positions`` items: {token, exchange, qty, price, tradeType}. The exchange
        computes hedge benefit across the legs, so a future + protective option needs
        far less than a naked future. Returns Angel's ``data`` block, or None on failure.
        """
        if not positions:
            return None
        payload = {"positions": [
            {
                "exchange": p["exchange"],
                "qty": int(p["qty"]),
                "price": float(p.get("price") or 0),
                "productType": "CARRYFORWARD",   # positional (NRML); INTRADAY would differ
                "orderType": "LIMIT",
                "token": str(p["token"]),
                "tradeType": p["tradeType"].upper(),
            }
            for p in positions if p.get("token")
        ]}
        try:
            resp = self._session().getMarginApi(payload)
            if resp and resp.get("status"):
                return resp.get("data") or None
        except Exception:
            pass
        return None

    def basket_margin_total(self, positions: list[dict]) -> float | None:
        """Total SPAN+exposure margin (a single number) for a leg-set, cached.

        Same call as ``basket_margin`` but returns just ``totalMarginRequired`` and
        caches it keyed by the legs (token/exchange/qty/side) so repeatedly loading the
        portfolio doesn't re-hit Angel every time. Price is excluded from the key on
        purpose — margin is stable intraday while LTP ticks. None on failure/feed-off.
        """
        legs = [p for p in positions if p.get("token")]
        if not legs:
            return None
        key = tuple(sorted(
            (str(p["token"]), p.get("exchange") or "NFO", int(p["qty"]),
             (p.get("tradeType") or "BUY").upper())
            for p in legs
        ))
        cached = self._margin_cache.get(key)
        if cached and time.time() - cached[0] < _MARGIN_TTL:
            return cached[1]
        data = self.basket_margin(legs)
        total = None
        if data is not None:
            try:
                total = float(data.get("totalMarginRequired"))
            except (TypeError, ValueError):
                total = None
        self._margin_cache[key] = (time.time(), total)
        return total

    def option_chain(self, name: str, expiry: str, width: int = 12) -> dict:
        """Live option chain around ATM: strikes with CE/PE token + premium.

        Limited to the ``2*width+1`` strikes nearest the forward so the batched price
        fetch stays small and the table is the part a trader actually uses.
        """
        self._build()
        ces = {c["strike"]: c for c in self.fno_contracts(name, "opt", expiry, "CE")}
        pes = {c["strike"]: c for c in self.fno_contracts(name, "opt", expiry, "PE")}
        all_strikes = sorted(set(ces) | set(pes))
        ref = self.fno_ref_price(name)
        atm = min(all_strikes, key=lambda k: abs(k - ref)) if (ref and all_strikes) else (all_strikes[len(all_strikes)//2] if all_strikes else 0.0)
        if ref and all_strikes:
            near = sorted(all_strikes, key=lambda k: abs(k - ref))[: 2 * width + 1]
            strikes = sorted(near)
        else:
            strikes = all_strikes[: 2 * width + 1]

        exch = ""
        tokens: list[str] = []
        for k in strikes:
            for side in (ces.get(k), pes.get(k)):
                if side:
                    exch = exch or side["exchange"]
                    tokens.append(str(side["token"]))
        # FULL mode gets premium AND open interest in one batched call.
        quotes = self.quote_full({exch: tokens}) if tokens else {}

        def _side(c):
            q = quotes.get(str(c["token"]), {})
            return {"token": c["token"], "symbol": c["symbol"], "lot_size": c["lot_size"],
                    "ltp": q.get("ltp", 0.0), "oi": q.get("oi", 0.0), "volume": q.get("volume", 0.0)}

        lot = 0
        rows = []
        for k in strikes:
            ce, pe = ces.get(k), pes.get(k)
            lot = lot or (ce or pe or {}).get("lot_size", 0)
            rows.append({
                "strike": k,
                "ce": _side(ce) if ce else None,
                "pe": _side(pe) if pe else None,
            })
        days = max((datetime.strptime(expiry, "%d%b%Y").date() - datetime.now().date()).days, 0) \
            if _exp_key(expiry)[0] == 0 else 0
        return {"name": name.strip().upper(), "expiry": expiry, "exchange": exch,
                "ref_price": ref, "atm_strike": atm, "lot_size": lot,
                "days_to_expiry": days, "rows": rows}

    def ltp_many(self, exchange_tokens: dict[str, list[str]]) -> dict[str, float]:
        """Live LTP for many tokens in ONE call (Angel getMarketData, LTP mode).

        Resolving each holding with a separate ``ltpData`` call is slow (a network
        round-trip per stock) and on a cold feed some calls return 0 -> the page
        falls back to cost. Batching keeps the portfolio fast and live-correct.
        Tokens already warm in the 10s cache are skipped; failures degrade to the
        per-token path. Returns {token: ltp} for everything it could fetch.
        """
        out: dict[str, float] = {}
        pending: dict[str, list[str]] = {}
        now = time.time()
        for exch, toks in exchange_tokens.items():
            fresh = []
            for t in toks:
                t = str(t)
                c = self._ltp_cache.get(t)
                if c and now - c[0] < _LTP_TTL:
                    out[t] = c[1]
                else:
                    fresh.append(t)
            if fresh:
                pending[exch] = fresh
        if pending:
            try:
                client = self._session()
                # Angel caps LTP mode at 50 tokens/exchange/call, so chunk (a full option
                # chain is ~50 tokens). Most calls (a portfolio) fit in one chunk.
                for exch, toks in pending.items():
                    for i in range(0, len(toks), 50):
                        resp = client.getMarketData("LTP", {exch: toks[i:i + 50]})
                        for row in (((resp or {}).get("data") or {}).get("fetched") or []):
                            tok = str(row.get("symbolToken"))
                            ltp = float(row.get("ltp") or 0)
                            if ltp > 0:
                                self._ltp_cache[tok] = (time.time(), ltp)
                                out[tok] = ltp
            except Exception:
                pass
        return out

    def quote_full(self, exchange_tokens: dict[str, list[str]]) -> dict[str, dict]:
        """FULL quote for many tokens in ONE call (Angel getMarketData, FULL mode).

        FULL mode returns premium *and* open interest (+ traded volume) together, so
        the option chain gets all three without a second round-trip. Chunked at 50
        tokens (Angel's per-call cap; a chain is ~50). LTPs also warm the shared
        cache. Returns {token: {"ltp":.., "oi":.., "volume":..}}; empty on failure.
        """
        out: dict[str, dict] = {}
        if not any(exchange_tokens.values()):
            return out
        try:
            client = self._session()
            for exch, toks in exchange_tokens.items():
                toks = [str(t) for t in toks]
                for i in range(0, len(toks), 50):
                    resp = client.getMarketData("FULL", {exch: toks[i:i + 50]})
                    for row in (((resp or {}).get("data") or {}).get("fetched") or []):
                        tok = str(row.get("symbolToken"))
                        ltp = float(row.get("ltp") or 0)
                        out[tok] = {
                            "ltp": ltp,
                            "oi": float(row.get("opnInterest") or 0),
                            "volume": float(row.get("tradeVolume") or 0),
                        }
                        if ltp > 0:
                            self._ltp_cache[tok] = (time.time(), ltp)
        except Exception:
            pass
        return out

    def warm_positions(self, positions) -> None:
        """Pre-fetch LTP for all tokened positions in one batched call."""
        ex_tokens: dict[str, list[str]] = {}
        for p in positions:
            tok = getattr(p, "token", None)
            if not tok:
                continue
            ex_tokens.setdefault(getattr(p, "exchange", None) or "NSE", []).append(str(tok))
        if ex_tokens:
            self.ltp_many(ex_tokens)


@lru_cache
def get_market() -> AngelMarket | None:
    """The market feed, or None when it's turned off."""
    return AngelMarket() if settings.market_enabled else None
