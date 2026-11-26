"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AccountShell, { AccountsUnavailable } from "@/components/AccountShell";
import { useAuth } from "@/components/AuthProvider";
import { supabase } from "@/lib/supabase";

const MIN_PASSWORD = 8;

/**
 * Landing page for Supabase's password-reset email. The link signs the user in
 * with a short-lived recovery session (picked up by the Supabase client from
 * the URL); here they choose a new password.
 */
export default function ResetPasswordPage() {
  const router = useRouter();
  const { enabled, loading, user } = useAuth();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);

  // Expired / reused links come back with the error in the URL fragment or query.
  useEffect(() => {
    const params = new URLSearchParams(
      window.location.hash.replace(/^#/, "") || window.location.search.replace(/^\?/, ""),
    );
    const desc = params.get("error_description");
    if (desc) setLinkError(desc.replace(/\+/g, " "));
  }, []);

  if (!enabled) return <AccountsUnavailable />;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supabase) return;
    setError(null);
    if (password.length < MIN_PASSWORD) {
      setError(`Use at least ${MIN_PASSWORD} characters for your password.`);
      return;
    }
    if (password !== confirm) {
      setError("Those passwords don't match.");
      return;
    }
    setBusy(true);
    const { error } = await supabase.auth.updateUser({ password });
    setBusy(false);
    if (error) {
      setError(error.message || "Couldn't update your password. Please try again.");
      return;
    }
    setDone(true);
    setTimeout(() => router.replace("/account"), 1500);
  };

  return (
    <AccountShell narrow>
      <p className="acct-eyebrow">UniMe account</p>
      <h1 className="acct-title">Choose a new password</h1>

      <div className="acct-panel" style={{ marginTop: 28 }}>
        {loading ? (
          <p className="acct-muted">Checking your reset link…</p>
        ) : done ? (
          <p className="acct-notice" role="status">Password updated. Taking you to your account…</p>
        ) : !user ? (
          <>
            <p className="acct-error" role="alert">
              {linkError ?? "This reset link is invalid or has expired."}
            </p>
            <Link href="/login?mode=forgot" className="acct-btn acct-btn-block">
              Send a new link
            </Link>
          </>
        ) : (
          <form onSubmit={handleSubmit}>
            <p className="acct-muted" style={{ marginBottom: 18 }}>
              Signed in as {user.email}
            </p>
            {error && <p className="acct-error" role="alert">{error}</p>}
            <label className="acct-field">
              <span>New password</span>
              <input
                className="acct-input"
                type="password"
                required
                minLength={MIN_PASSWORD}
                autoComplete="new-password"
                placeholder={`At least ${MIN_PASSWORD} characters`}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <label className="acct-field">
              <span>Confirm new password</span>
              <input
                className="acct-input"
                type="password"
                required
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            </label>
            <button type="submit" className="acct-btn acct-btn-block" disabled={busy}>
              {busy ? "Saving…" : "Update password"}
            </button>
          </form>
        )}
      </div>
    </AccountShell>
  );
}
