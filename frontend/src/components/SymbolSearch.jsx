// Instrument autocomplete. Queries the server (full NSE+BSE universe, or F&O contracts)
// as you type. onSelect returns the full instrument {symbol, exchange, token, lot_size,...}.
import { useEffect, useRef, useState } from "react";
import { getJSON } from "../api/client";

export default function SymbolSearch({ value, kind = "equity", onChange, onSelect, placeholder }) {
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const timer = useRef(null);

  // Debounced server search on the typed value.
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    const q = (value || "").trim();
    if (q.length < 1) {
      setResults([]);
      return;
    }
    timer.current = setTimeout(() => {
      getJSON(`/api/instruments?kind=${kind}&q=${encodeURIComponent(q)}&limit=12`)
        .then((d) => setResults(d.instruments || []))
        .catch(() => setResults([]));
    }, 220);
    return () => timer.current && clearTimeout(timer.current);
  }, [value, kind]);

  useEffect(() => {
    function onDoc(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <input
        value={value}
        onChange={(e) => {
          onChange(e.target.value.toUpperCase());
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder || (kind === "fno" ? "Search a contract — e.g. NIFTY" : "Search a stock — e.g. TATASTEEL")}
        autoComplete="off"
        className="w-full rounded-lg border border-hairline bg-elevated px-3 py-2 text-sm text-body outline-none focus:ring-2 focus:ring-info/50"
      />
      {open && results.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-hairline bg-card shadow-lg">
          {results.map((r) => (
            <li key={`${r.exchange}-${r.token}-${r.symbol}`}>
              <button
                type="button"
                onClick={() => {
                  onSelect(r);
                  setOpen(false);
                }}
                className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-elevated"
              >
                <span className="font-medium text-body">{r.symbol}</span>
                <span className="shrink-0 truncate text-xs text-muted">
                  {kind === "fno"
                    ? `${r.exchange} · 1 lot = ${r.lot_size}`
                    : r.name && r.name !== r.symbol
                      ? `${r.exchange} · ${r.name}`
                      : r.exchange}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
