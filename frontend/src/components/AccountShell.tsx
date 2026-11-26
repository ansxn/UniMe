import Link from "next/link";

/** Page frame shared by /login, /reset-password and /account. */
export default function AccountShell({
  children,
  narrow = false,
  quizBackground = false,
}: {
  children: React.ReactNode;
  narrow?: boolean;
  quizBackground?: boolean;
}) {
  return (
    <div className={`acct-page ${quizBackground ? "acct-page-quiz-bg" : ""}`}>
      <Link href="/" className="back-button">
        ← Back to Home
      </Link>
      <main className={`acct-inner ${narrow ? "acct-narrow" : ""}`}>{children}</main>
    </div>
  );
}

/** Shown on account pages when Supabase isn't configured. */
export function AccountsUnavailable() {
  return (
    <AccountShell narrow>
      <h1 className="acct-title">Accounts are coming soon</h1>
      <p className="acct-subtitle">
        You can still take the MatchMe quiz and use ChanceMe without an account.
      </p>
      <div className="acct-actions" style={{ justifyContent: "center" }}>
        <Link href="/quiz" className="acct-btn">MatchMe</Link>
        <Link href="/chance" className="acct-btn-ghost">ChanceMe</Link>
      </div>
    </AccountShell>
  );
}
