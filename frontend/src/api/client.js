// Tiny fetch helper. The Vite dev server proxies "/api" to the backend.

// A 401 from any call means "not signed in" — the app catches this to show login.
export class AuthError extends Error {}

export async function getJSON(path) {
  const res = await fetch(path, { credentials: "include" });
  if (!res.ok) {
    if (res.status === 401) throw new AuthError("Not signed in");
    throw new Error(`Request to ${path} failed (${res.status})`);
  }
  return res.json();
}

export async function sendJSON(path, body, method = "POST") {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    if (res.status === 401) throw new AuthError("Not signed in");
    let detail = "";
    try {
      detail = JSON.stringify(await res.json());
    } catch {
      detail = res.statusText;
    }
    throw new Error(`${method} ${path} failed (${res.status}): ${detail}`);
  }
  return res.json();
}

// --- Auth ---------------------------------------------------------------
// Auth calls surface the backend's clean `detail` message (e.g. "That username is taken.").
async function authPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  let data = {};
  try {
    data = await res.json();
  } catch {
    /* no body */
  }
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

async function authSend(path, body, method = "POST") {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  let data = {};
  try {
    data = await res.json();
  } catch {
    /* no body */
  }
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

export const getMe = () => getJSON("/api/auth/me"); // throws AuthError if not signed in
export const login = (email, password) => authPost("/api/auth/login", { email, password });
export const signup = (email, username, password) =>
  authPost("/api/auth/signup", { email, username, password });
export const logout = () => authPost("/api/auth/logout", {});
export const changeUsername = (username) => authSend("/api/auth/username", { username }, "PUT");
export const changePassword = (current_password, new_password) =>
  authSend("/api/auth/password", { current_password, new_password }, "PUT");
export const verifyEmail = (token) => authPost("/api/auth/verify", { token });
export const resendVerification = () => authPost("/api/auth/verify/resend", {});
export const forgotPassword = (email) => authPost("/api/auth/forgot-password", { email });
export const resetPassword = (token, password) =>
  authPost("/api/auth/reset-password", { token, password });

// AI explainer availability — fetched once and memoized for all explainer panels.
let _aiStatusPromise;
export function getAIStatus() {
  if (!_aiStatusPromise) {
    _aiStatusPromise = getJSON("/api/ai/status").catch(() => ({
      provider: "none",
      configured: false,
    }));
  }
  return _aiStatusPromise;
}

// Format a number as Indian Rupees (₹1,23,456 style — lakh/crore grouping).
export function inr(value, { decimals = 0 } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: decimals,
  }).format(value);
}

// Plain Indian-grouped number (no currency symbol).
export function num(value, { decimals = 0 } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  }).format(value);
}

// Percent with a sign for drift-style values (+10.2% / -3.4%).
export function pctSigned(value, decimals = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}

export function pct(value, decimals = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(decimals)}%`;
}

// Bucket accent colors from the design brief (hex so they work in inline styles too).
export const BUCKET_COLOR = {
  "F&O": "#F6465D",
  "Long-term": "#0ECB81",
  Swing: "#F59E0B",
  unassigned: "#707A8A",
};

export function bucketColor(name) {
  return BUCKET_COLOR[name] || "#3B82F6";
}

// Collapse holdings that were saved together as one basket (they share a basket_id)
// into a single grouped item, leaving every other holding as-is. Display only — the
// underlying rows are untouched. Returns items in first-seen order, each either
//   { isBasket: false, row }                                   (a normal holding)
//   { isBasket: true, basket_id, label, bucket, legs,          (a saved basket)
//     invested, current_value, pnl, pnl_pct }
export function groupHoldings(rows = []) {
  const byId = new Map();
  const out = [];
  for (const r of rows) {
    if (!r.basket_id) {
      out.push({ isBasket: false, row: r });
      continue;
    }
    let g = byId.get(r.basket_id);
    if (!g) {
      g = {
        isBasket: true,
        basket_id: r.basket_id,
        label: r.basket_label || `${r.symbol} basket`,
        bucket: r.bucket,
        legs: [],
        invested: 0,
        current_value: 0,
        pnl: 0,
      };
      byId.set(r.basket_id, g);
      out.push(g);
    }
    g.legs.push(r);
    g.invested += r.invested || 0;
    g.current_value += r.current_value || 0;
    g.pnl += r.pnl || 0;
  }
  for (const g of out) {
    if (g.isBasket) g.pnl_pct = g.invested ? (g.pnl / g.invested) * 100 : 0;
  }
  return out;
}
