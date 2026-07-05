import { useCallback, useEffect, useState } from "react";
import {
  getJSON,
  sendJSON,
  getMe,
  logout as apiLogout,
  verifyEmail,
  resendVerification,
  AuthError,
} from "./api/client";
import Shell from "./components/Shell";
import Onboarding from "./components/Onboarding";
import GuidedTour from "./components/GuidedTour";
import { LogoMark } from "./components/Logo";
import Auth from "./pages/Auth";
import Profile from "./pages/Profile";
import Dashboard from "./pages/Dashboard";
import Holdings from "./pages/Holdings";
import Portfolios from "./pages/Portfolios";
import Allocation from "./pages/Allocation";
import Hedge from "./pages/Hedge";
import Options from "./pages/Options";
import Basket from "./pages/Basket";
import Risk from "./pages/Risk";
import Journal from "./pages/Journal";

function App() {
  const [view, setView] = useState("dashboard");
  // When you drill into Hedge/Risk from a specific portfolio, this pre-selects its bucket.
  const [navScope, setNavScope] = useState("");
  const [status, setStatus] = useState(null);
  const [portfolio, setPortfolio] = useState(null);
  const [allocation, setAllocation] = useState(null);
  const [buckets, setBuckets] = useState(null);
  const [error, setError] = useState(null);
  // F&O expiry: positions auto-settled into the journal + those expiring within a day.
  const [expiry, setExpiry] = useState({ settled: [], expiring: [] });

  // Auth: undefined = checking the session, null = signed out, object = signed in.
  const [user, setUser] = useState(undefined);
  useEffect(() => {
    getMe()
      .then((r) => setUser(r.user))
      .catch(() => setUser(null));
  }, []);
  const onLogout = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      /* ignore */
    }
    setUser(null);
    setPortfolio(null);
    setAllocation(null);
    setBuckets(null);
    setError(null);
    setView("dashboard");
    setExpiry({ settled: [], expiring: [] });
  }, []);

  // Email verification + password reset arrive as ?verify=… / ?reset=… links.
  const [flash, setFlash] = useState(null);
  const [resetToken, setResetToken] = useState(
    () => new URLSearchParams(window.location.search).get("reset")
  );
  const stripParam = (name) => {
    const params = new URLSearchParams(window.location.search);
    params.delete(name);
    const qs = params.toString();
    window.history.replaceState({}, "", window.location.pathname + (qs ? "?" + qs : ""));
  };
  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("verify");
    if (!token) return;
    verifyEmail(token)
      .then(() => {
        setFlash({ ok: true, text: "Email verified — thank you!" });
        setUser((u) => (u ? { ...u, email_verified: true } : u));
      })
      .catch(() => setFlash({ ok: false, text: "That verification link is invalid or has expired." }))
      .finally(() => stripParam("verify"));
  }, []);
  const clearReset = useCallback((msg) => {
    setResetToken(null);
    stripParam("reset");
    if (msg) setFlash({ ok: true, text: msg });
  }, []);
  const onResendVerify = useCallback(async () => {
    try {
      await resendVerification();
      setFlash({ ok: true, text: "Verification email sent — check your inbox." });
    } catch {
      setFlash({ ok: false, text: "Couldn't send the email. Please try again." });
    }
  }, []);

  // Collapsible left menu (hamburger) — collapsing gives the active tab the full width.
  const [navOpen, setNavOpen] = useState(true);
  const toggleNav = useCallback(() => setNavOpen((o) => !o), []);

  // Interactive guided tour that runs over the live cockpit.
  const [tour, setTour] = useState(false);
  const startTour = useCallback(() => {
    setNavOpen(true); // the tour spotlights the sidebar tabs, so make sure it's open
    setTour(true);
  }, []);

  // Entrance: FIRST-EVER visit gets the full experience (splash → intro → gate → tour,
  // gated by localStorage). Returning visits get just the logo entrance once per browser
  // session (sessionStorage); a same-session refresh shows nothing. The tour is always
  // re-openable from "Take the tour".
  const [onboarding, setOnboarding] = useState(() => {
    if (!localStorage.getItem("rw_onboarded")) return { mode: "full" };
    if (!sessionStorage.getItem("rw_splash_seen")) return { mode: "splash" };
    return null;
  });
  const finishOnboarding = useCallback(
    (withTour) => {
      localStorage.setItem("rw_onboarded", "1");
      sessionStorage.setItem("rw_splash_seen", "1");
      setOnboarding(null);
      if (withTour) startTour();
    },
    [startTour]
  );
  const replayTour = startTour;

  // Theme: black dark mode (default) or white light mode. The initial attribute is
  // set in index.html before paint; here we just track + toggle + persist it.
  const [theme, setTheme] = useState(
    () => document.documentElement.getAttribute("data-theme") || "dark"
  );
  const toggleTheme = useCallback(() => {
    setTheme((t) => {
      const next = t === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try {
        localStorage.setItem("rw_theme", next);
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  // Refetch everything that depends on holdings/plan (after a bucket edit, etc.).
  // A 401 here means this device's session was revoked (logged out elsewhere, or
  // evicted by a newer login past the device cap) — drop cleanly to the login screen.
  const reload = useCallback(async () => {
    try {
      const [p, a, b] = await Promise.all([
        getJSON("/api/portfolio"),
        getJSON("/api/allocation"),
        getJSON("/api/buckets"),
      ]);
      setPortfolio(p);
      setAllocation(a);
      setBuckets(b);
    } catch (e) {
      if (e instanceof AuthError) {
        setUser(null);
        return;
      }
      throw e;
    }
  }, []);

  // Navigate to a view, optionally scoped to a capital bucket (for Hedge/Risk drill-in).
  const navigate = useCallback((nextView, bucket = "") => {
    setNavScope(bucket);
    setView(nextView);
  }, []);

  useEffect(() => {
    if (!user) return; // nothing loads until signed in
    getJSON("/api/status").then(setStatus).catch((e) => setError(e.message));
    // Auto-settle any expired F&O into the journal first, then load the (now-current)
    // portfolio, then note anything expiring within a day for the alert. Best-effort —
    // a settlement/expiry hiccup never blocks the app.
    (async () => {
      let settled = [];
      try {
        const r = await sendJSON("/api/positions/settle-expired", {});
        settled = r.settled || [];
      } catch {
        /* ignore */
      }
      await reload().catch((e) => setError(e.message));
      try {
        const e = await getJSON("/api/positions/expiries");
        setExpiry({ settled, expiring: e.expiring_soon || [] });
      } catch {
        setExpiry({ settled, expiring: [] });
      }
    })();
  }, [reload, user]);

  // Auth gate — before anything else.
  // A password-reset link works even mid-session, so check it first.
  if (resetToken) {
    return <Auth resetToken={resetToken} onResetDone={clearReset} onAuthed={setUser} />;
  }
  if (user === undefined) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LogoMark size={52} animated className="rw-float" />
      </div>
    );
  }
  if (user === null) {
    return <Auth onAuthed={setUser} flash={flash} />;
  }

  // The onboarding overlay plays over whatever the app is doing (loading, ready, or
  // even an error) so the entrance is instant and data loads behind it.
  const overlay = onboarding && (
    <Onboarding mode={onboarding.mode} onDone={finishOnboarding} />
  );

  let content;
  if (error) {
    content = (
      <div className="flex min-h-screen items-center justify-center p-6">
        <div className="w-full max-w-md rounded-2xl border border-hairline bg-card p-8 text-center shadow-[var(--shadow-pop)]">
          <LogoMark size={44} className="mx-auto" />
          <h2 className="mt-5 text-xl font-semibold text-headline">Can't reach the backend</h2>
          <p className="mt-2 text-sm text-body">{error}</p>
          <p className="mt-4 text-sm text-muted-strong">
            Start the servers by double-clicking{" "}
            <code className="rounded bg-elevated px-1.5 py-0.5 text-gold">start.bat</code>, or run{" "}
            <code className="rounded bg-elevated px-1.5 py-0.5 text-body">uvicorn app.main:app</code>{" "}
            from <code className="rounded bg-elevated px-1.5 py-0.5 text-body">backend/</code>.
          </p>
        </div>
      </div>
    );
  } else if (!portfolio || !allocation || !buckets) {
    content = (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 text-muted-strong">
        <LogoMark size={52} animated className="rw-float" />
        <p className="text-sm tracking-wide">Loading your cockpit…</p>
      </div>
    );
  } else {
    content = (
      <Shell
        view={view}
        onNavigate={(v) => navigate(v)}
        totals={portfolio.totals}
        dataMode={status?.data_provider}
        onReplayTour={replayTour}
        theme={theme}
        onToggleTheme={toggleTheme}
        navOpen={navOpen}
        onToggleNav={toggleNav}
        expiry={expiry}
        user={user}
        onLogout={onLogout}
        onResendVerify={onResendVerify}
        flash={flash}
        onDismissFlash={() => setFlash(null)}
      >
        {view === "dashboard" && (
          <Dashboard portfolio={portfolio} allocation={allocation} onNavigate={navigate} />
        )}
        {view === "holdings" && <Holdings buckets={buckets.buckets} onReload={reload} />}
        {view === "portfolios" && (
          <Portfolios portfolio={portfolio} allocation={allocation} onNavigate={navigate} />
        )}
        {view === "allocation" && (
          <Allocation allocation={allocation} buckets={buckets.buckets} onReload={reload} />
        )}
        {view === "hedge" && <Hedge initialBucket={navScope} />}
        {view === "options" && <Options />}
        {view === "basket" && <Basket />}
        {view === "risk" && <Risk initialBucket={navScope} />}
        {view === "journal" && <Journal />}
        {view === "profile" && <Profile user={user} onUserUpdate={setUser} />}
      </Shell>
    );
  }

  const canTour = portfolio && allocation && buckets && !error;

  return (
    <>
      {content}
      {overlay}
      {tour && canTour && (
        <GuidedTour onNavigate={(v) => navigate(v)} onDone={() => setTour(false)} />
      )}
    </>
  );
}

export default App;
