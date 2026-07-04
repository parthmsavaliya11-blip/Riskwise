// Login / signup screen. Gates the whole app — nothing loads until you're signed in.
// Your portfolio is private to your account.
import { useState } from "react";
import { login, signup } from "../api/client";
import { Logo } from "../components/Logo";
import { Button, Field } from "../components/ui";

const INPUT =
  "w-full rounded-lg border border-hairline bg-elevated/60 px-3 py-2 text-sm text-body outline-none transition-colors placeholder:text-muted focus:border-gold/50 focus:ring-2 focus:ring-gold/20";

export default function Auth({ onAuthed }) {
  const [mode, setMode] = useState("login"); // login | signup
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const isSignup = mode === "signup";

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = isSignup
        ? await signup(email.trim(), username.trim(), password)
        : await login(email.trim(), password);
      onAuthed(res.user);
    } catch (err) {
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const canSubmit =
    email.includes("@") && password.length >= 8 && (!isSignup || username.trim().length >= 3);

  return (
    <div className="flex min-h-screen items-center justify-center px-6 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center rw-fade-up">
          <Logo markSize={46} wordSize={32} />
          <p className="mt-4 text-sm text-muted-strong">Know your risk. Own your edge.</p>
        </div>

        <div className="rw-fade-up rw-d1 rounded-2xl border border-hairline bg-card p-6 shadow-[var(--shadow-pop)]">
          <div className="mb-5 flex rounded-xl border border-hairline bg-elevated/60 p-1">
            {[
              ["login", "Sign in"],
              ["signup", "Create account"],
            ].map(([m, label]) => (
              <button
                key={m}
                type="button"
                onClick={() => {
                  setMode(m);
                  setError("");
                }}
                className={`flex-1 rounded-lg py-2 text-sm font-semibold transition-all ${
                  mode === m ? "bg-gold/15 text-gold" : "text-muted-strong hover:text-body"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-4">
            <Field label="Email">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                placeholder="you@email.com"
                className={INPUT}
              />
            </Field>
            {isSignup && (
              <Field label="Username" hint="3–20 letters, numbers or underscores">
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  placeholder="yourname"
                  className={INPUT}
                />
              </Field>
            )}
            <Field label="Password" hint={isSignup ? "At least 8 characters" : undefined}>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={isSignup ? "new-password" : "current-password"}
                placeholder="••••••••"
                className={INPUT}
              />
            </Field>

            {error && (
              <p className="rounded-lg border border-down/25 bg-down/5 px-3 py-2 text-sm text-down">
                {error}
              </p>
            )}

            <Button type="submit" disabled={!canSubmit || busy} className="w-full">
              {busy ? "Please wait…" : isSignup ? "Create account" : "Sign in"}
            </Button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs text-muted">
          {isSignup
            ? "Your portfolio is private to your account. Read-only broker data — no orders are ever placed."
            : "You'll stay signed in on this device until you log out."}
        </p>
      </div>
    </div>
  );
}
