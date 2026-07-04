// Auth screen: login / signup / forgot-password / reset-password.
// Gates the whole app — nothing loads until you're signed in.
import { useState } from "react";
import { forgotPassword, login, resetPassword, signup } from "../api/client";
import { Logo } from "../components/Logo";
import { Button, Field } from "../components/ui";

const INPUT =
  "w-full rounded-lg border border-hairline bg-elevated/60 px-3 py-2 text-sm text-body outline-none transition-colors placeholder:text-muted focus:border-gold/50 focus:ring-2 focus:ring-gold/20";

function Shell({ children, sub }) {
  return (
    <div className="flex min-h-screen items-center justify-center px-6 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center rw-fade-up">
          <Logo markSize={46} wordSize={32} />
          <p className="mt-4 text-sm text-muted-strong">Know your risk. Own your edge.</p>
        </div>
        <div className="rw-fade-up rw-d1 rounded-2xl border border-hairline bg-card p-6 shadow-[var(--shadow-pop)]">
          {children}
        </div>
        {sub && <p className="mt-6 text-center text-xs text-muted">{sub}</p>}
      </div>
    </div>
  );
}

export default function Auth({ onAuthed, resetToken, onResetDone, flash }) {
  // reset mode is forced by a ?reset=token link; otherwise login/signup/forgot.
  const [mode, setMode] = useState(resetToken ? "reset" : "login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const isSignup = mode === "signup";

  async function submitAuth(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = isSignup
        ? await signup(email.trim(), username.trim(), password)
        : await login(email.trim(), password);
      onAuthed(res.user);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function submitForgot(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const res = await forgotPassword(email.trim());
      setNotice(
        res.dev_reset_link
          ? `Dev mode — open this reset link: ${res.dev_reset_link}`
          : "If that email is registered, we've sent a reset link. Check your inbox."
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function submitReset(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await resetPassword(resetToken, password);
      onResetDone("Password updated — please sign in with your new password.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  // ---- reset password (from email link) ----
  if (mode === "reset") {
    return (
      <Shell>
        <h1 className="text-lg font-semibold text-headline">Set a new password</h1>
        <p className="mt-1 mb-4 text-sm text-muted">Choose a new password for your account.</p>
        <form onSubmit={submitReset} className="space-y-4">
          <Field label="New password" hint="At least 8 characters">
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" placeholder="••••••••" className={INPUT} />
          </Field>
          {error && <p className="rounded-lg border border-down/25 bg-down/5 px-3 py-2 text-sm text-down">{error}</p>}
          <Button type="submit" disabled={busy || password.length < 8} className="w-full">
            {busy ? "Please wait…" : "Update password"}
          </Button>
        </form>
      </Shell>
    );
  }

  // ---- forgot password ----
  if (mode === "forgot") {
    return (
      <Shell>
        <h1 className="text-lg font-semibold text-headline">Reset your password</h1>
        <p className="mt-1 mb-4 text-sm text-muted">Enter your email and we'll send a reset link.</p>
        <form onSubmit={submitForgot} className="space-y-4">
          <Field label="Email">
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" placeholder="you@email.com" className={INPUT} />
          </Field>
          {error && <p className="rounded-lg border border-down/25 bg-down/5 px-3 py-2 text-sm text-down">{error}</p>}
          {notice && <p className="rounded-lg border border-up/25 bg-up/5 px-3 py-2 text-sm text-up break-words">{notice}</p>}
          <Button type="submit" disabled={busy || !email.includes("@")} className="w-full">
            {busy ? "Please wait…" : "Send reset link"}
          </Button>
        </form>
        <button onClick={() => { setMode("login"); setError(""); setNotice(""); }} className="mt-4 w-full text-center text-sm text-muted-strong transition-colors hover:text-gold">
          ← Back to sign in
        </button>
      </Shell>
    );
  }

  // ---- login / signup ----
  const canSubmit = email.includes("@") && password.length >= 8 && (!isSignup || username.trim().length >= 3);
  return (
    <Shell
      sub={
        isSignup
          ? "Your portfolio is private to your account. Read-only broker data — no orders are ever placed."
          : "You'll stay signed in on this device until you log out."
      }
    >
      {flash && (
        <p className={`mb-4 rounded-lg border px-3 py-2 text-sm ${flash.ok ? "border-up/25 bg-up/5 text-up" : "border-down/25 bg-down/5 text-down"}`}>
          {flash.text}
        </p>
      )}
      <div className="mb-5 flex rounded-xl border border-hairline bg-elevated/60 p-1">
        {[["login", "Sign in"], ["signup", "Create account"]].map(([m, label]) => (
          <button
            key={m}
            type="button"
            onClick={() => { setMode(m); setError(""); }}
            className={`flex-1 rounded-lg py-2 text-sm font-semibold transition-all ${mode === m ? "bg-gold/15 text-gold" : "text-muted-strong hover:text-body"}`}
          >
            {label}
          </button>
        ))}
      </div>

      <form onSubmit={submitAuth} className="space-y-4">
        <Field label="Email">
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" placeholder="you@email.com" className={INPUT} />
        </Field>
        {isSignup && (
          <Field label="Username" hint="3–20 letters, numbers or underscores">
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" placeholder="yourname" className={INPUT} />
          </Field>
        )}
        <Field label="Password" hint={isSignup ? "At least 8 characters" : undefined}>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={isSignup ? "new-password" : "current-password"} placeholder="••••••••" className={INPUT} />
        </Field>
        {error && <p className="rounded-lg border border-down/25 bg-down/5 px-3 py-2 text-sm text-down">{error}</p>}
        <Button type="submit" disabled={!canSubmit || busy} className="w-full">
          {busy ? "Please wait…" : isSignup ? "Create account" : "Sign in"}
        </Button>
      </form>

      {!isSignup && (
        <button onClick={() => { setMode("forgot"); setError(""); }} className="mt-4 w-full text-center text-sm text-muted-strong transition-colors hover:text-gold">
          Forgot your password?
        </button>
      )}
    </Shell>
  );
}
