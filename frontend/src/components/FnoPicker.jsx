// Guided F&O contract picker: a flat search box can't pick among thousands of
// option strikes, so we narrow step by step — type (Futures / Call / Put) ->
// underlying -> expiry -> (strike for options). Calls onResolve(contract|null)
// whenever the selection becomes complete or incomplete; the contract carries
// {symbol, tradingsymbol, token, exchange, lot_size, kind} for the position.
import { useEffect, useRef, useState } from "react";
import { getJSON } from "../api/client";
import { Field } from "./ui";

const TYPES = [
  { id: "fut", label: "Futures" },
  { id: "CE", label: "Call (CE)" },
  { id: "PE", label: "Put (PE)" },
];

const SELECT_CLS =
  "w-full rounded-lg border border-hairline bg-elevated px-3 py-2 text-sm text-body outline-none focus:ring-2 focus:ring-info/50 disabled:opacity-50";

// Pretty "30JUN2026" -> "30 Jun 2026"
function fmtExpiry(e) {
  const m = /^(\d{2})([A-Z]{3})(\d{4})$/.exec(e || "");
  if (!m) return e;
  return `${m[1]} ${m[2][0]}${m[2].slice(1).toLowerCase()} ${m[3]}`;
}

export default function FnoPicker({ onResolve }) {
  const [type, setType] = useState("fut"); // fut | CE | PE
  const kind = type === "fut" ? "fut" : "opt";

  // Step 1: underlying (search + dropdown)
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState([]);
  const [open, setOpen] = useState(false);
  const [underlying, setUnderlying] = useState(null); // {name, lot_size, exchange}

  // Step 2 & 3: expiry + strike
  const [expiries, setExpiries] = useState([]);
  const [expiry, setExpiry] = useState("");
  const [strikes, setStrikes] = useState([]); // [{strike, token, symbol, lot_size,...}]
  const [token, setToken] = useState("");
  const [refPrice, setRefPrice] = useState(0); // live forward (nearest future) for ATM
  const [atmToken, setAtmToken] = useState(""); // strike nearest the reference

  const boxRef = useRef(null);
  const timer = useRef(null);

  // Reset everything below a step when an upstream choice changes.
  function resetFrom(step) {
    if (step <= 1) { setUnderlying(null); setExpiries([]); }
    if (step <= 2) { setExpiry(""); setStrikes([]); setRefPrice(0); setAtmToken(""); }
    if (step <= 3) { setToken(""); }
    onResolve(null);
  }

  // Changing the contract type restarts the whole flow.
  useEffect(() => {
    setQuery(""); setMatches([]); resetFrom(1);
  }, [type]); // eslint-disable-line react-hooks/exhaustive-deps

  // Debounced underlying search.
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    const q = query.trim();
    if (q.length < 1 || (underlying && underlying.name === q)) { setMatches([]); return; }
    timer.current = setTimeout(() => {
      getJSON(`/api/fno/underlyings?kind=${kind}&q=${encodeURIComponent(q)}&limit=12`)
        .then((d) => setMatches(d.underlyings || []))
        .catch(() => setMatches([]));
    }, 220);
    return () => timer.current && clearTimeout(timer.current);
  }, [query, kind]); // eslint-disable-line react-hooks/exhaustive-deps

  // Close the dropdown on outside click.
  useEffect(() => {
    function onDoc(e) { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  function pickUnderlying(u) {
    resetFrom(1);
    setUnderlying(u);
    setQuery(u.name);
    setOpen(false);
    getJSON(`/api/fno/expiries?name=${encodeURIComponent(u.name)}&kind=${kind}`)
      .then((d) => setExpiries(d.expiries || []))
      .catch(() => setExpiries([]));
  }

  function pickExpiry(exp) {
    resetFrom(2);
    setExpiry(exp);
    if (!exp || !underlying) return;
    const right = type === "fut" ? "" : `&right=${type}`;
    getJSON(`/api/fno/contracts?name=${encodeURIComponent(underlying.name)}&kind=${kind}&expiry=${exp}${right}`)
      .then((d) => {
        const list = d.contracts || [];
        if (type === "fut") {
          // One future per expiry — resolve it straight away.
          if (list[0]) { setToken(list[0].token); onResolve(list[0]); }
        } else {
          setStrikes(list);
          const ref = Number(d.ref_price) || 0;
          setRefPrice(ref);
          // Default to the at-the-money strike (nearest the live forward).
          const atm = ref
            ? list.reduce((b, c) => (Math.abs(c.strike - ref) < Math.abs(b.strike - ref) ? c : b), list[0])
            : null;
          if (atm) { setAtmToken(String(atm.token)); setToken(String(atm.token)); onResolve(atm); }
        }
      })
      .catch(() => setStrikes([]));
  }

  function pickStrike(tok) {
    setToken(tok);
    const c = strikes.find((s) => String(s.token) === String(tok));
    onResolve(c || null);
  }

  return (
    <>
      <Field label="Type">
        <div className="flex rounded-lg border border-hairline bg-elevated p-1">
          {TYPES.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setType(t.id)}
              className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                type === t.id ? "bg-card text-headline" : "text-muted-strong"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </Field>

      <Field
        label="Underlying"
        hint={underlying ? `${underlying.exchange} · 1 lot = ${underlying.lot_size}` : "e.g. NIFTY, BANKNIFTY, RELIANCE"}
      >
        <div className="relative" ref={boxRef}>
          <input
            value={query}
            onChange={(e) => { setQuery(e.target.value.toUpperCase()); setOpen(true); if (underlying) resetFrom(1); }}
            onFocus={() => setOpen(true)}
            placeholder="Search underlying"
            autoComplete="off"
            className="w-full rounded-lg border border-hairline bg-elevated px-3 py-2 text-sm text-body outline-none focus:ring-2 focus:ring-info/50"
          />
          {open && matches.length > 0 && (
            <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-hairline bg-card shadow-lg">
              {matches.map((u) => (
                <li key={u.name}>
                  <button
                    type="button"
                    onClick={() => pickUnderlying(u)}
                    className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-elevated"
                  >
                    <span className="font-medium text-body">{u.name}</span>
                    <span className="shrink-0 text-xs text-muted">1 lot = {u.lot_size}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Field>

      <Field label="Expiry">
        <select
          className={SELECT_CLS}
          value={expiry}
          disabled={!underlying || expiries.length === 0}
          onChange={(e) => pickExpiry(e.target.value)}
        >
          <option value="">{underlying ? "Select expiry" : "Pick an underlying first"}</option>
          {expiries.map((e) => (
            <option key={e} value={e}>{fmtExpiry(e)}</option>
          ))}
        </select>
      </Field>

      {type !== "fut" && (
        <Field
          label="Strike"
          hint={refPrice ? `ATM ≈ ${Number(refPrice).toLocaleString("en-IN")} (live) — defaulted to nearest strike` : undefined}
        >
          <select
            className={SELECT_CLS}
            value={token}
            disabled={!expiry || strikes.length === 0}
            onChange={(e) => pickStrike(e.target.value)}
          >
            <option value="">{expiry ? "Select strike" : "Pick an expiry first"}</option>
            {strikes.map((s) => (
              <option key={s.token} value={s.token}>
                {Number(s.strike).toLocaleString("en-IN")} {type}
                {String(s.token) === atmToken ? "  • ATM" : ""}
              </option>
            ))}
          </select>
        </Field>
      )}
    </>
  );
}
