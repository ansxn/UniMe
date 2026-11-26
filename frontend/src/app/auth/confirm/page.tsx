"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import type { EmailOtpType } from "@supabase/supabase-js";
import AccountShell, { AccountsUnavailable } from "@/components/AccountShell";
import { displayNameFor, useAuth } from "@/components/AuthProvider";
import { supabase } from "@/lib/supabase";
import { safeNext } from "@/lib/nav";

/**
 * Landing page for the "confirm your email" link. Supabase sends the user here
 * with the new session in the URL (#access_token=… or ?code=…), which the
 * Supabase client picks up on load; ?token_hash=&type= links are verified here.
 * Expired or reused links arrive with error_description in the URL instead.
 */
export default function ConfirmEmailPage() {
  const { enabled, loading, user, profile, savedVersion } = useAuth();
  const [next, setNext] = useState("/account");
  const [linkError, setLinkError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);

  const [email, setEmail] = useState("");
  const [resending, setResending] = useState(false);
  const [resendNote, setResendNote] = useState<string | null>(null);

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    setNext(safeNext(query.get("next")));

    const desc = hash.get("error_description") || query.get("error_description");
    if (desc) {
      setLinkError(desc.replace(/\+/g, " ").replace(/([^.!?])$/, "$1."));
      return;
    }

    const tokenHash = query.get("token_hash");
    const type = query.get("type") as EmailOtpType | null;
    if (tokenHash && type && supabase) {
      setVerifying(true);
      supabase.auth
        .verifyOtp({ token_hash: tokenHash, type })
        .then(({ error }) => {
          if (error) setLinkError(error.message);
        })
        .finally(() => setVerifying(false));
    }
  }, []);

  // Once signed in, drop the tokens from the address bar (keep ?next=).
  useEffect(() => {
    if (!user) return;
    const keep = new URLSearchParams();
    const n = new URLSearchParams(window.location.search).get("next");
    if (n) keep.set("next", n);
    const clean = window.location.pathname + (keep.size ? `?${keep}` : "");
    window.history.replaceState(null, "", clean);
  }, [user]);

  if (!enabled) return <AccountsUnavailable />;

  const resend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supabase) return;
    setResending(true);
    setResendNote(null);
    const { error } = await supabase.auth.resend({
      type: "signup",
      email: email.trim(),
      options: { emailRedirectTo: `${window.location.origin}/auth/confirm?next=${encodeURIComponent(next)}` },
    });
    setResending(false);
    setResendNote(
      error
        ? /rate limit|too many/i.test(error.message)
          ? "Too many emails sent. Please wait a few minutes and try again."
          : error.message
        : `If ${email.trim()} is waiting to be confirmed, a new link is on its way.`,
    );
  };

  const checking = loading || verifying;
  const confirmed = !checking && !!user;
  const nextLabel =
    next.startsWith("/matches") ? "Back to my matches" : next.startsWith("/chance") ? "Back to ChanceMe" : "Go to my account";

  return (
    <AccountShell narrow>
      <p className="acct-eyebrow">UniMe account</p>

      {checking ? (
        <>
          <h1 className="acct-title">Confirming your email…</h1>
          <p className="acct-subtitle">Hang tight, this only takes a second.</p>
        </>
      ) : confirmed ? (
        <>
          <div className="acct-confirm-badge" aria-hidden="true">✓</div>
          <h1 className="acct-title">You&apos;re all set, {displayNameFor(user, profile)}!</h1>
          <p className="acct-subtitle">
            Your email is confirmed and you&apos;re logged in. Quiz results, ChanceMe checks and
            starred programs will now be saved to your account.
          </p>
          <div className="acct-panel">
            {savedVersion > 0 && (
              <p className="acct-notice" role="status">
                The results you saved before signing up are now in your account.
              </p>
            )}
            <p className="acct-muted" style={{ marginBottom: 18 }}>Signed in as {user.email}</p>
            <Link href={next} className="acct-btn acct-btn-block">
              {nextLabel}
            </Link>
            <div className="acct-actions" style={{ justifyContent: "center", marginTop: 14 }}>
              <Link href="/quiz" className="acct-btn-ghost">Take MatchMe</Link>
              <Link href="/chance" className="acct-btn-ghost">Try ChanceMe</Link>
            </div>
          </div>
        </>
      ) : (
        <>
          <h1 className="acct-title">This link didn&apos;t work</h1>
          <p className="acct-subtitle">
            {linkError ?? "The confirmation link is invalid or has expired."} Links only work once and
            expire after a while. If you already confirmed, just log in.
          </p>
          <div className="acct-panel">
            <Link href={`/login?next=${encodeURIComponent(next)}`} className="acct-btn acct-btn-block">
              Log in
            </Link>
            <form onSubmit={resend} style={{ marginTop: 24 }}>
              <label className="acct-field">
                <span>Need a new link?</span>
                <input
                  className="acct-input"
                  type="email"
                  required
                  autoComplete="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </label>
              {resendNote && <p className="acct-notice" role="status">{resendNote}</p>}
              <button type="submit" className="acct-btn-ghost acct-btn-block" disabled={resending}>
                {resending ? "Sending…" : "Resend confirmation email"}
              </button>
            </form>
          </div>
        </>
      )}
    </AccountShell>
  );
}
