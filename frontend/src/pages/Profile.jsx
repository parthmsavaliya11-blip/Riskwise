// Profile: account info, username change (max 3×, unique), and change password.
import { useState } from "react";
import { changePassword, changeUsername } from "../api/client";
import { Badge, Button, Card, Field, PageHeader } from "../components/ui";

const INPUT =
  "w-full rounded-lg border border-hairline bg-elevated/60 px-3 py-2 text-sm text-body outline-none transition-colors placeholder:text-muted focus:border-gold/50 focus:ring-2 focus:ring-gold/20 disabled:opacity-50";

function Note({ msg }) {
  if (!msg) return null;
  return <p className={`text-sm ${msg.ok ? "text-up" : "text-down"}`}>{msg.text}</p>;
}

export default function Profile({ user, onUserUpdate }) {
  const changesLeft = user.username_changes_left ?? 0;

  const [username, setUsername] = useState(user.username);
  const [uBusy, setUBusy] = useState(false);
  const [uMsg, setUMsg] = useState(null);

  const [cur, setCur] = useState("");
  const [nw, setNw] = useState("");
  const [pBusy, setPBusy] = useState(false);
  const [pMsg, setPMsg] = useState(null);

  async function saveUsername(e) {
    e.preventDefault();
    setUBusy(true);
    setUMsg(null);
    try {
      const res = await changeUsername(username.trim());
      onUserUpdate(res.user);
      const left = res.user.username_changes_left;
      setUMsg({ ok: true, text: `Username updated — ${left} change${left === 1 ? "" : "s"} left.` });
    } catch (err) {
      setUMsg({ ok: false, text: err.message });
    } finally {
      setUBusy(false);
    }
  }

  async function savePassword(e) {
    e.preventDefault();
    setPBusy(true);
    setPMsg(null);
    try {
      await changePassword(cur, nw);
      setCur("");
      setNw("");
      setPMsg({ ok: true, text: "Password changed." });
    } catch (err) {
      setPMsg({ ok: false, text: err.message });
    } finally {
      setPBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader title="Profile" lead="Your account — your portfolio is private to it." />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Account">
          <dl className="space-y-3 text-sm">
            <div className="flex items-center justify-between gap-4">
              <dt className="text-muted">Email</dt>
              <dd className="truncate text-body">{user.email}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-muted">Role</dt>
              <dd>{user.is_admin ? <Badge kind="gold">Owner</Badge> : <Badge kind="neutral">Member</Badge>}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-muted">Email verified</dt>
              <dd>{user.email_verified ? <Badge kind="ok">Verified</Badge> : <Badge kind="under">Not yet</Badge>}</dd>
            </div>
          </dl>
        </Card>

        <Card
          accent
          title="Username"
          subtitle={
            changesLeft > 0
              ? `You can change your username ${changesLeft} more time${changesLeft === 1 ? "" : "s"}. This can't be undone.`
              : "You've used all 3 username changes."
          }
        >
          <form onSubmit={saveUsername} className="space-y-3">
            <Field label="Username" hint="3–20 letters, numbers or underscores">
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className={INPUT}
                disabled={changesLeft <= 0}
                autoComplete="off"
              />
            </Field>
            <Note msg={uMsg} />
            <Button
              type="submit"
              disabled={uBusy || changesLeft <= 0 || username.trim() === user.username || username.trim().length < 3}
            >
              {uBusy ? "Saving…" : "Save username"}
            </Button>
          </form>
        </Card>

        <Card title="Change password" className="lg:col-span-2">
          <form onSubmit={savePassword} className="grid max-w-xl gap-3 sm:grid-cols-2">
            <Field label="Current password">
              <input type="password" value={cur} onChange={(e) => setCur(e.target.value)} className={INPUT} autoComplete="current-password" />
            </Field>
            <Field label="New password" hint="At least 8 characters">
              <input type="password" value={nw} onChange={(e) => setNw(e.target.value)} className={INPUT} autoComplete="new-password" />
            </Field>
            <div className="sm:col-span-2">
              <Note msg={pMsg} />
            </div>
            <div className="sm:col-span-2">
              <Button type="submit" disabled={pBusy || !cur || nw.length < 8}>
                {pBusy ? "Saving…" : "Change password"}
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}
