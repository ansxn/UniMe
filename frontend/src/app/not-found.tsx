import Link from "next/link";
import AccountShell from "@/components/AccountShell";

export const metadata = { title: "Page not found — UniMe" };

/** Shown for any URL that doesn't match a page. */
export default function NotFound() {
  return (
    <AccountShell narrow>
      <p className="nf-code" aria-hidden="true">404</p>
      <h1 className="acct-title">Lost in space</h1>
      <p className="acct-subtitle">
        We couldn&apos;t find what you were looking for. It may have moved, or the link might be
        mistyped.
      </p>
      <div className="acct-panel">
        <Link href="/" className="acct-btn acct-btn-block">Back to home</Link>
        <div className="acct-actions" style={{ justifyContent: "center", marginTop: 14 }}>
          <Link href="/quiz" className="acct-btn-ghost">Take MatchMe</Link>
          <Link href="/chance" className="acct-btn-ghost">Try ChanceMe</Link>
        </div>
      </div>
    </AccountShell>
  );
}
