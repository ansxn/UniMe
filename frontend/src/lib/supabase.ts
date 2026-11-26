import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// NEXT_PUBLIC_* values are inlined at build time, so they must be referenced literally.
const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key =
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ||
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

/** True when accounts are available (env vars set). Safe to read during render. */
export const authEnabled = Boolean(url && key);

/**
 * The one Supabase browser client for the app, or `null` when Supabase isn't
 * configured (or during server prerender). With no client, accounts are off:
 * auth UI is hidden and the quiz / ChanceMe work exactly as they do for guests.
 */
export const supabase: SupabaseClient | null =
  authEnabled && typeof window !== "undefined"
    ? createClient(url!, key!, {
        auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
      })
    : null;
