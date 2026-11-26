"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AccountShell, { AccountsUnavailable } from "@/components/AccountShell";
import { displayNameFor, useAuth } from "@/components/AuthProvider";
import { supabase } from "@/lib/supabase";
import {
  deleteChanceCheck,
  deleteQuizResult,
  deleteSavedProgram,
  listChanceChecks,
  listQuizResults,
  listSavedPrograms,
  reopenQuizResult,
  type ChanceCheckRow,
  type ProgramMatch,
  type QuizResultRow,
  type SavedProgramRow,
} from "@/lib/saved";

const pct = (v: unknown) => (typeof v === "number" ? `${Math.round(v * 100)}%` : "—");

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });

/** /api/match returns either an array or {matches: [...]}. */
function matchesOf(row: QuizResultRow): ProgramMatch[] {
  const m = row.matches as { matches?: unknown } | unknown[];
  const arr = Array.isArray(m) ? m : (m as { matches?: unknown })?.matches;
  return Array.isArray(arr) ? (arr as ProgramMatch[]) : [];
}

const THIS_YEAR = new Date().getFullYear();

export default function AccountPage() {
  const router = useRouter();
  const { enabled, loading, user, profile, refreshProfile, savedVersion } = useAuth();

  const [quizResults, setQuizResults] = useState<QuizResultRow[] | null>(null);
  const [chanceChecks, setChanceChecks] = useState<ChanceCheckRow[] | null>(null);
  const [programs, setPrograms] = useState<SavedProgramRow[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [gradYear, setGradYear] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileMsg, setProfileMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const [q, c, p] = await Promise.all([listQuizResults(), listChanceChecks(), listSavedPrograms()]);
      setQuizResults(q);
      setChanceChecks(c);
      setPrograms(p);
    } catch (err) {
      console.error("Couldn't load saved data:", err);
      setLoadError("We couldn't load your saved results. Please refresh to try again.");
    }
  }, []);

  useEffect(() => {
    if (user) load();
  }, [user, load, savedVersion]);

  useEffect(() => {
    setName(profile?.display_name ?? "");
    setGradYear(profile?.grad_year ? String(profile.grad_year) : "");
  }, [profile]);

  if (!enabled) return <AccountsUnavailable />;

  if (loading) {
    return (
      <AccountShell narrow>
        <p className="acct-subtitle">Loading your account…</p>
      </AccountShell>
    );
  }

  if (!user) {
    return (
      <AccountShell narrow>
        <p className="acct-eyebrow">UniMe account</p>
        <h1 className="acct-title">Your account</h1>
        <p className="acct-subtitle">
          Log in to see your saved quiz results, ChanceMe checks, and starred programs.
        </p>
        <div className="acct-actions" style={{ justifyContent: "center" }}>
          <Link href="/login?next=%2Faccount" className="acct-btn">Log in</Link>
          <Link href="/login?next=%2Faccount&mode=signup" className="acct-btn-ghost">Create an account</Link>
        </div>
      </AccountShell>
    );
  }

  const remove = async (kind: "quiz" | "chance" | "program", id: string) => {
    if (!window.confirm("Delete this from your account?")) return;
    setDeleting(id);
    try {
      if (kind === "quiz") {
        await deleteQuizResult(id);
        setQuizResults((rows) => rows?.filter((r) => r.id !== id) ?? null);
      } else if (kind === "chance") {
        await deleteChanceCheck(id);
        setChanceChecks((rows) => rows?.filter((r) => r.id !== id) ?? null);
      } else {
        await deleteSavedProgram(id);
        setPrograms((rows) => rows?.filter((r) => r.id !== id) ?? null);
      }
    } catch (err) {
      console.error("Delete failed:", err);
      setLoadError("Couldn't delete that. Please try again.");
    } finally {
      setDeleting(null);
    }
  };

  const openQuiz = (row: QuizResultRow) => {
    reopenQuizResult(row);
    router.push("/matches");
  };

  const saveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supabase) return;
    const year = gradYear.trim() ? Number(gradYear) : null;
    if (year !== null && (!Number.isInteger(year) || year < 2000 || year > 2100)) {
      setProfileMsg({ ok: false, text: "Enter a graduation year like 2027." });
      return;
    }
    setProfileBusy(true);
    setProfileMsg(null);
    const { error } = await supabase
      .from("profiles")
      .upsert({ id: user.id, display_name: name.trim() || null, grad_year: year });
    setProfileBusy(false);
    if (error) {
      setProfileMsg({ ok: false, text: "Couldn't save your profile. Please try again." });
      return;
    }
    setProfileMsg({ ok: true, text: "Profile saved." });
    refreshProfile();
  };

  const logOut = async () => {
    await supabase?.auth.signOut();
    router.push("/");
  };

  const DeleteButton = ({ kind, id, label }: { kind: "quiz" | "chance" | "program"; id: string; label: string }) => (
    <button
      type="button"
      className="acct-icon-btn"
      aria-label={label}
      title="Delete"
      disabled={deleting === id}
      onClick={(e) => {
        e.stopPropagation();
        remove(kind, id);
      }}
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <polyline points="3 6 5 6 21 6" />
        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
        <path d="M10 11v6M14 11v6M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
      </svg>
    </button>
  );

  return (
    <AccountShell>
      <p className="acct-eyebrow">Your account</p>
      <h1 className="acct-title">Hi, {displayNameFor(user, profile)}</h1>
      <p className="acct-subtitle">Everything you&apos;ve saved from MatchMe and ChanceMe.</p>

      {loadError && <p className="acct-error" role="alert">{loadError}</p>}

      {/* Quiz results */}
      <section className="acct-panel" aria-labelledby="quiz-heading">
        <div className="acct-panel-head">
          <h2 id="quiz-heading">MatchMe results</h2>
          {quizResults && <span className="acct-count">{quizResults.length} saved</span>}
        </div>
        {quizResults === null ? (
          <p className="acct-empty">Loading…</p>
        ) : quizResults.length === 0 ? (
          <p className="acct-empty">
            No saved quiz results yet. <Link href="/quiz">Take the MatchMe quiz →</Link>
          </p>
        ) : (
          <ul className="acct-list">
            {quizResults.map((row) => {
              const top = matchesOf(row);
              return (
                <li
                  key={row.id}
                  className="acct-item acct-item-clickable"
                  role="link"
                  tabIndex={0}
                  onClick={() => openQuiz(row)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      openQuiz(row);
                    }
                  }}
                >
                  <div className="acct-item-main">
                    <div className="acct-item-title">
                      {top[0] ? `${top[0].program} — ${top[0].school}` : "Quiz result"}
                    </div>
                    <div className="acct-item-sub">
                      {formatDate(row.created_at)}
                      {top.length > 1 && ` · also ${top.slice(1, 3).map((m) => m.school).join(", ")}`}
                      {" · "}Open matches →
                    </div>
                  </div>
                  {top[0] && <span className="acct-item-badge">{pct(top[0].overall)}</span>}
                  <DeleteButton kind="quiz" id={row.id} label="Delete this quiz result" />
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* Saved programs */}
      <section className="acct-panel" aria-labelledby="programs-heading">
        <div className="acct-panel-head">
          <h2 id="programs-heading">Saved programs</h2>
          {programs && <span className="acct-count">{programs.length} saved</span>}
        </div>
        {programs === null ? (
          <p className="acct-empty">Loading…</p>
        ) : programs.length === 0 ? (
          <p className="acct-empty">Star programs on your matches page to keep them here.</p>
        ) : (
          <ul className="acct-list">
            {programs.map((row) => (
              <li key={row.id} className="acct-item">
                <div className="acct-item-main">
                  <div className="acct-item-title">{row.program}</div>
                  <div className="acct-item-sub">
                    {row.school}
                    {row.match &&
                      ` · Academics ${pct(row.match.academic)} · Social ${pct(row.match.social)} · Campus ${pct(row.match.campus)}`}
                  </div>
                </div>
                {row.match && <span className="acct-item-badge">{pct(row.match.overall)}</span>}
                <DeleteButton kind="program" id={row.id} label={`Remove ${row.program} at ${row.school}`} />
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ChanceMe checks */}
      <section className="acct-panel" aria-labelledby="chance-heading">
        <div className="acct-panel-head">
          <h2 id="chance-heading">ChanceMe checks</h2>
          {chanceChecks && <span className="acct-count">{chanceChecks.length} saved</span>}
        </div>
        {chanceChecks === null ? (
          <p className="acct-empty">Loading…</p>
        ) : chanceChecks.length === 0 ? (
          <p className="acct-empty">
            No saved checks yet. <Link href="/chance">Check your chances →</Link>
          </p>
        ) : (
          <ul className="acct-list">
            {chanceChecks.map((row) => {
              const p = row.prediction as Record<string, unknown>;
              const found = p.found === true;
              return (
                <li key={row.id} className="acct-item">
                  <div className="acct-item-main">
                    <div className="acct-item-title">
                      {String((found && p.program) || row.inputs.program)} — {String((found && p.school) || row.inputs.school)}
                    </div>
                    <div className="acct-item-sub">
                      Top 6: {row.inputs.top6}%
                      {row.inputs.ecs && ` · ECs: ${row.inputs.ecs}`}
                      {found && typeof p.verdict === "string" && ` · ${p.verdict}`}
                      {" · "}
                      {formatDate(row.created_at)}
                    </div>
                  </div>
                  <span className="acct-item-badge">{found ? `${p.chance}%` : "n/a"}</span>
                  <DeleteButton kind="chance" id={row.id} label="Delete this ChanceMe check" />
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* Profile */}
      <section className="acct-panel" aria-labelledby="profile-heading">
        <div className="acct-panel-head">
          <h2 id="profile-heading">Profile</h2>
          <span className="acct-count">{user.email}</span>
        </div>
        {profileMsg && (
          <p className={profileMsg.ok ? "acct-notice" : "acct-error"} role="status">
            {profileMsg.text}
          </p>
        )}
        <form onSubmit={saveProfile}>
          <div className="acct-form-row">
            <label className="acct-field">
              <span>Display name</span>
              <input
                className="acct-input"
                type="text"
                maxLength={80}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
              />
            </label>
            <label className="acct-field">
              <span>High school grad year</span>
              <input
                className="acct-input"
                type="number"
                inputMode="numeric"
                min={2000}
                max={2100}
                placeholder={String(THIS_YEAR + 1)}
                value={gradYear}
                onChange={(e) => setGradYear(e.target.value)}
              />
              <small>Optional</small>
            </label>
          </div>
          <div className="acct-actions" style={{ justifyContent: "space-between" }}>
            <button type="submit" className="acct-btn" disabled={profileBusy}>
              {profileBusy ? "Saving…" : "Save profile"}
            </button>
            <button type="button" className="acct-btn-ghost" onClick={logOut}>
              Log out
            </button>
          </div>
        </form>
      </section>
    </AccountShell>
  );
}
