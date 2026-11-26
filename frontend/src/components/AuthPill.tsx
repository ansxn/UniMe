"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { displayNameFor, useAuth } from "./AuthProvider";

/** Top-right "Log in" / account-name pill shown on every page when accounts are enabled. */
export default function AuthPill() {
  const { enabled, loading, user, profile } = useAuth();
  const pathname = usePathname();

  if (!enabled || loading) return null;
  if (pathname === "/login" || pathname === "/reset-password") return null;

  if (!user) {
    const next = pathname && pathname !== "/" ? `?next=${encodeURIComponent(pathname)}` : "";
    return (
      <Link href={`/login${next}`} className="auth-pill">
        Log in
      </Link>
    );
  }

  return (
    <Link
      href="/account"
      className={`auth-pill ${pathname === "/account" ? "auth-pill-active" : ""}`}
      title={user.email ?? undefined}
    >
      <span className="auth-pill-dot" aria-hidden="true" />
      <span className="auth-pill-name">{displayNameFor(user, profile)}</span>
    </Link>
  );
}
