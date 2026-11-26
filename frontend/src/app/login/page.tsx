"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AccountShell, { AccountsUnavailable } from "@/components/AccountShell";
import { useAuth } from "@/components/AuthProvider";
import { supabase } from "@/lib/supabase";
import { hasPendingSaves } from "@/lib/saved";
import { safeNext } from "@/lib/nav";

type Mode = "login" | "signup" | "forgot";

const MIN_PASSWORD = 8;

export default function LoginPage() {
  const router = useRouter();
  const { enabled, loading, user } = useAuth();

  const [mode, setMode] = useState<Mode>("login");
  const [next, setNext] = useState("/account");
  const [savingIntent, setSavingIntent] = useState(false);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Read ?next=&mode=&reason= on the client (pages here are client-only).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setNext(safeNext(params.get("next")));
    const m = params.get("mode");
    if (m === "signup" || m === "login" || m === "forgot") setMode(m);
    setSavingIntent(params.get("reason") === "save" || hasPendingSaves());
  }, []);

  // Already logged in (or just logged in): continue to where they were going.
  useEffect(() => {
    if (!loading && user) router.replace(next);
  }, [loading, user, next, router]);

  if (!enabled) return <AccountsUnavailable />;

  const switchMode = (m: Mode) => {
    setMode(m);
    setError(null);
    setNotice(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supabase) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const trimmedEmail = email.trim();
      if (mode === "login") {
        const { error } = await supabase.auth.signInWithPassword({ email: trimmedEmail, password });
        if (error) throw error;
        // AuthProvider sees SIGNED_IN, saves pending results; the effect above redirects.
      } else if (mode === "signup") {
        if (password.length < MIN_PASSWORD) {
          throw new Error(`Use at least ${MIN_PASSWORD} characters for your password.`);
        }
        const { data, error } = await supabase.auth.signUp({
          email: trimmedEmail,
          password,
          options: {
            data: { display_name: displayName.trim() || null },
            emailRedirectTo: `${window.location.origin}/auth/confirm?next=${encodeURIComponent(next)}`,
          },
        });
        if (error) throw error;
        if (!data.session) {
          // Email confirmation is on: Supabase sent a link. Pending saves stay in
          // localStorage and are saved when they come back via that link.
          setNotice(
            `We sent a confirmation link to ${trimmedEmail}. Open it on this device to finish creating your account` +
              (savingIntent ? " — your results will be saved automatically." : "."),
          );
          setPassword("");
        }
      } else {
        const { error } = await supabase.auth.resetPasswordForEmail(trimmedEmail, {
          redirectTo: `${window.location.origin}/reset-password`,
        });
        if (error) throw error;
        setNotice(`If an account exists for ${trimmedEmail}, a password reset link is on its way.`);
      }
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  };

  const title =
    mode === "forgot" ? "Reset your password" : mode === "signup" ? "Create your account" : "Welcome back";
  const subtitle =
    mode === "forgot"
      ? "Enter your email and we'll send you a link to choose a new password."
      : savingIntent
        ? "Log in or create a free account to save your results. You'll come right back to them."
        : "Save your quiz results, ChanceMe checks, and favourite programs in one place.";

  return (
    <AccountShell narrow>
      <p className="acct-eyebrow">UniMe account</p>
      <h1 className="acct-title">{title}</h1>
      <p className="acct-subtitle">{subtitle}</p>

      <div className="acct-panel">
        {mode !== "forgot" && (
          <div className="acct-tabs" role="tablist" aria-label="Log in or sign up">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "login"}
              className="acct-tab"
              onClick={() => switchMode("login")}
            >
              Log in
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "signup"}
              className="acct-tab"
              onClick={() => switchMode("signup")}
            >
              Sign up
            </button>
          </div>
        )}

        {error && <p className="acct-error" role="alert">{error}</p>}
        {notice && <p className="acct-notice" role="status">{notice}</p>}

        <form onSubmit={handleSubmit} noValidate={false}>
          {mode === "signup" && (
            <label className="acct-field">
              <span>Name</span>
              <input
                className="acct-input"
                type="text"
                autoComplete="given-name"
                maxLength={80}
                placeholder="What should we call you?"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </label>
          )}

          <label className="acct-field">
            <span>Email</span>
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

          {mode !== "forgot" && (
            <label className="acct-field">
              <span>Password</span>
              <input
                className="acct-input"
                type="password"
                required
                minLength={mode === "signup" ? MIN_PASSWORD : undefined}
                autoComplete={mode === "signup" ? "new-password" : "current-password"}
                placeholder={mode === "signup" ? `At least ${MIN_PASSWORD} characters` : "Your password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
          )}

          <button type="submit" className="acct-btn acct-btn-block" disabled={busy}>
            {busy
              ? "One moment…"
              : mode === "login"
                ? "Log in"
                : mode === "signup"
                  ? "Create account"
                  : "Send reset link"}
          </button>
        </form>

        <p className="acct-footer-links">
          {mode === "login" && (
            <button type="button" className="acct-link" onClick={() => switchMode("forgot")}>
              Forgot your password?
            </button>
          )}
          {mode === "forgot" && (
            <button type="button" className="acct-link" onClick={() => switchMode("login")}>
              ← Back to log in
            </button>
          )}
          {mode === "signup" && (
            <span>No account needed to use MatchMe or ChanceMe — accounts just let you save.</span>
          )}
        </p>
      </div>
    </AccountShell>
  );
}

function friendlyError(err: unknown): string {
  const message = err instanceof Error ? err.message : String(err);
  if (/invalid login credentials/i.test(message)) return "That email and password don't match.";
  if (/email not confirmed/i.test(message)) return "Please confirm your email first — check your inbox for the link.";
  if (/already registered/i.test(message)) return "There's already an account with that email. Try logging in.";
  if (/rate limit|too many/i.test(message)) return "Too many attempts. Please wait a few minutes and try again.";
  if (/failed to fetch|network/i.test(message)) return "We couldn't reach the server. Please try again in a moment.";
  return message || "Something went wrong. Please try again.";
}
