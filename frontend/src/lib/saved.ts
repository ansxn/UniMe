// Per-user saved data (quiz results, ChanceMe checks, starred programs).
// Every function is a no-op / empty result when Supabase isn't configured.
import { supabase } from "./supabase";

export interface ProgramMatch {
  school: string;
  program: string;
  overall: number;
  academic: number;
  campus: number;
  social: number;
}

export interface QuizResultRow {
  id: string;
  answers: unknown;
  matches: unknown;
  created_at: string;
}

export interface ChanceCheckRow {
  id: string;
  inputs: { school: string; program: string; top6: string; ecs: string };
  // Same shape as /api/chance-me's `prediction`
  prediction: Record<string, unknown> & { found: boolean };
  created_at: string;
}

export interface SavedProgramRow {
  id: string;
  school: string;
  program: string;
  match: ProgramMatch | null;
  created_at: string;
}

// --- localStorage keys -------------------------------------------------------
// "matches" and "answers" are written by the quiz page (pre-existing keys).
const QUIZ_RESULT_ID = "unime:quizResultId"; // saved row id for the results in "matches"
const PENDING = "unime:pending"; // what a guest asked to save before logging in

interface PendingSave {
  quiz?: boolean;
  chance?: { inputs: ChanceCheckRow["inputs"]; prediction: ChanceCheckRow["prediction"] };
  programs?: ProgramMatch[];
}

function readJSON<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function writePending(p: PendingSave) {
  try {
    if (!p.quiz && !p.chance && !(p.programs && p.programs.length)) localStorage.removeItem(PENDING);
    else localStorage.setItem(PENDING, JSON.stringify(p));
  } catch {
    /* storage unavailable */
  }
}

/** Remember something a guest wants saved; it's saved by flushPendingSaves() after login. */
export function queuePendingSave(add: PendingSave) {
  const p = readJSON<PendingSave>(PENDING) ?? {};
  if (add.quiz) p.quiz = true;
  if (add.chance) p.chance = add.chance;
  if (add.programs) {
    const list = p.programs ?? [];
    for (const m of add.programs) {
      if (!list.some((x) => x.school === m.school && x.program === m.program)) list.push(m);
    }
    p.programs = list;
  }
  writePending(p);
}

export function hasPendingSaves(): boolean {
  return readJSON<PendingSave>(PENDING) !== null;
}

async function currentUserId(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.user.id ?? null;
}

// --- Quiz results ------------------------------------------------------------

/** Called by the quiz page when new results arrive: they aren't saved yet. */
export function markQuizResultsUnsaved() {
  try {
    localStorage.removeItem(QUIZ_RESULT_ID);
  } catch {
    /* ignore */
  }
}

export function currentQuizResultId(): string | null {
  try {
    return localStorage.getItem(QUIZ_RESULT_ID);
  } catch {
    return null;
  }
}

let quizSaveInFlight: Promise<string | null> | null = null;

/** Save the quiz results currently in localStorage (once). Returns the row id. */
export function saveCurrentQuizResult(): Promise<string | null> {
  quizSaveInFlight ??= doSaveCurrentQuizResult().finally(() => {
    quizSaveInFlight = null;
  });
  return quizSaveInFlight;
}

/** The quiz save started by the quiz page, if it's still running (so /matches can show its status). */
export function quizSaveInProgress(): Promise<string | null> | null {
  return quizSaveInFlight;
}

async function doSaveCurrentQuizResult(): Promise<string | null> {
  if (!supabase || !(await currentUserId())) return null;
  const existing = currentQuizResultId();
  if (existing) return existing;
  const matches = readJSON<unknown>("matches");
  const answers = readJSON<unknown>("answers");
  if (!matches || !answers) return null;
  const { data, error } = await supabase
    .from("quiz_results")
    .insert({ answers, matches })
    .select("id")
    .single();
  if (error) throw error;
  localStorage.setItem(QUIZ_RESULT_ID, data.id);
  return data.id as string;
}

export async function listQuizResults(): Promise<QuizResultRow[]> {
  if (!supabase) return [];
  const { data, error } = await supabase
    .from("quiz_results")
    .select("id, answers, matches, created_at")
    .order("created_at", { ascending: false });
  if (error) throw error;
  return data as QuizResultRow[];
}

/** Put a saved result back into localStorage so /matches shows it. */
export function reopenQuizResult(row: QuizResultRow) {
  localStorage.setItem("matches", JSON.stringify(row.matches));
  localStorage.setItem("answers", JSON.stringify(row.answers));
  localStorage.setItem(QUIZ_RESULT_ID, row.id);
}

export async function deleteQuizResult(id: string) {
  if (!supabase) return;
  const { error } = await supabase.from("quiz_results").delete().eq("id", id);
  if (error) throw error;
  if (currentQuizResultId() === id) markQuizResultsUnsaved();
}

// --- ChanceMe checks ---------------------------------------------------------

export async function saveChanceCheck(
  inputs: ChanceCheckRow["inputs"],
  prediction: ChanceCheckRow["prediction"],
): Promise<string | null> {
  if (!supabase || !(await currentUserId())) return null;
  const { data, error } = await supabase
    .from("chance_checks")
    .insert({ inputs, prediction })
    .select("id")
    .single();
  if (error) throw error;
  return data.id as string;
}

export async function listChanceChecks(): Promise<ChanceCheckRow[]> {
  if (!supabase) return [];
  const { data, error } = await supabase
    .from("chance_checks")
    .select("id, inputs, prediction, created_at")
    .order("created_at", { ascending: false });
  if (error) throw error;
  return data as ChanceCheckRow[];
}

export async function deleteChanceCheck(id: string) {
  if (!supabase) return;
  const { error } = await supabase.from("chance_checks").delete().eq("id", id);
  if (error) throw error;
}

// --- Saved (starred) programs ------------------------------------------------

export const programKey = (school: string, program: string) => `${school}\u0000${program}`;

export async function saveProgram(match: ProgramMatch) {
  if (!supabase || !(await currentUserId())) return;
  const { error } = await supabase
    .from("saved_programs")
    .upsert(
      { school: match.school, program: match.program, match },
      { onConflict: "user_id,school,program", ignoreDuplicates: true },
    );
  if (error) throw error;
}

export async function unsaveProgram(school: string, program: string) {
  if (!supabase) return;
  const { error } = await supabase
    .from("saved_programs")
    .delete()
    .eq("school", school)
    .eq("program", program);
  if (error) throw error;
}

export async function listSavedPrograms(): Promise<SavedProgramRow[]> {
  if (!supabase) return [];
  const { data, error } = await supabase
    .from("saved_programs")
    .select("id, school, program, match, created_at")
    .order("created_at", { ascending: false });
  if (error) throw error;
  return data as SavedProgramRow[];
}

export async function deleteSavedProgram(id: string) {
  if (!supabase) return;
  const { error } = await supabase.from("saved_programs").delete().eq("id", id);
  if (error) throw error;
}

// --- After login -------------------------------------------------------------

/**
 * Save whatever a guest queued before logging in / signing up. Safe to call
 * repeatedly; only clears each item once it has been saved.
 */
let flushInFlight: Promise<boolean> | null = null;

export function flushPendingSaves(): Promise<boolean> {
  flushInFlight ??= doFlushPendingSaves().finally(() => {
    flushInFlight = null;
  });
  return flushInFlight;
}

async function doFlushPendingSaves(): Promise<boolean> {
  const p = readJSON<PendingSave>(PENDING);
  if (!p || !supabase || !(await currentUserId())) return false;
  let saved = false;
  try {
    if (p.quiz) {
      await saveCurrentQuizResult();
      p.quiz = false;
      saved = true;
    }
    if (p.chance) {
      await saveChanceCheck(p.chance.inputs, p.chance.prediction);
      p.chance = undefined;
      saved = true;
    }
    while (p.programs && p.programs.length) {
      await saveProgram(p.programs[0]);
      p.programs.shift();
      saved = true;
    }
  } catch (err) {
    console.error("Couldn't save pending results:", err);
  } finally {
    writePending(p);
  }
  return saved;
}
