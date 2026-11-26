"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { User } from "@supabase/supabase-js";
import { authEnabled, supabase } from "@/lib/supabase";
import { flushPendingSaves } from "@/lib/saved";

export interface Profile {
  id: string;
  display_name: string | null;
  grad_year: number | null;
  created_at: string;
}

interface AuthState {
  /** False when Supabase env vars are missing: hide all account UI. */
  enabled: boolean;
  /** True until the stored session has been checked. */
  loading: boolean;
  user: User | null;
  profile: Profile | null;
  refreshProfile: () => Promise<void>;
  /** Bumped whenever pending guest results were saved after login. */
  savedVersion: number;
}

const AuthContext = createContext<AuthState>({
  enabled: false,
  loading: false,
  user: null,
  profile: null,
  refreshProfile: async () => {},
  savedVersion: 0,
});

export const useAuth = () => useContext(AuthContext);

/** Name to show for the signed-in user. */
export function displayNameFor(user: User | null, profile: Profile | null): string {
  return (
    profile?.display_name?.trim() ||
    (user?.user_metadata?.display_name as string | undefined)?.trim() ||
    user?.email?.split("@")[0] ||
    "Account"
  );
}

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(authEnabled);
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [savedVersion, setSavedVersion] = useState(0);

  const loadProfile = useCallback(async (u: User | null) => {
    if (!supabase || !u) {
      setProfile(null);
      return;
    }
    const { data } = await supabase
      .from("profiles")
      .select("id, display_name, grad_year, created_at")
      .eq("id", u.id)
      .maybeSingle();
    setProfile((data as Profile | null) ?? null);
  }, []);

  useEffect(() => {
    if (!supabase) return;
    const client = supabase;

    const { data: sub } = client.auth.onAuthStateChange((event, session) => {
      const u = session?.user ?? null;
      setUser(u);
      setLoading(false);
      // Supabase advises not awaiting other client calls inside this callback.
      setTimeout(() => {
        if (event === "SIGNED_OUT") {
          setProfile(null);
          return;
        }
        if (event === "INITIAL_SESSION" || event === "SIGNED_IN" || event === "USER_UPDATED") {
          loadProfile(u);
        }
        if (u && (event === "INITIAL_SESSION" || event === "SIGNED_IN")) {
          flushPendingSaves().then((saved) => {
            if (saved) setSavedVersion((v) => v + 1);
          });
        }
      }, 0);
    });
    return () => sub.subscription.unsubscribe();
  }, [loadProfile]);

  const refreshProfile = useCallback(() => loadProfile(user), [loadProfile, user]);

  return (
    <AuthContext.Provider
      value={{ enabled: authEnabled, loading, user, profile, refreshProfile, savedVersion }}
    >
      {children}
    </AuthContext.Provider>
  );
}
