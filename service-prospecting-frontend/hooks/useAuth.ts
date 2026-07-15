/** Hook for Supabase auth state and user profile loading.
 *  Returns auth loading state, user object, user profile, setup status, and refresh helpers.
 */

import type { User } from "@supabase/supabase-js";
import { useRouter } from "next/router";
import { useCallback, useEffect, useState } from "react";

import { getUser, getUserProfile, isSupabaseConfigured, signOut } from "../lib/supabase";
import type { UserProfile } from "../types/prospect";

interface AuthState {
  authLoading: boolean;
  user: User | null;
  profile: UserProfile | null;
  authError: string;
  configured: boolean;
  refreshProfile: () => Promise<void>;
  logout: () => Promise<void>;
}

/** Loads Supabase auth state and redirects anonymous users when requested. */
export function useAuth(requireAuth = true): AuthState {
  const router = useRouter();
  const [authLoading, setAuthLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [authError, setAuthError] = useState("");

  /** Refreshes the logged-in user's profile row from Supabase. */
  const refreshProfile = useCallback(async () => {
    if (!user) {
      return;
    }

    const nextProfile = await getUserProfile(user.id);
    setProfile(nextProfile);
  }, [user]);

  /** Signs out and returns the user to the auth page. */
  const logout = useCallback(async () => {
    await signOut();
    setUser(null);
    setProfile(null);
    await router.push("/auth");
  }, [router]);

  useEffect(() => {
    let mounted = true;

    /** Loads the active user and profile once on page entry. */
    async function loadAuth(): Promise<void> {
      if (!isSupabaseConfigured) {
        setAuthLoading(false);
        return;
      }

      try {
        const activeUser = await getUser();
        if (!mounted) {
          return;
        }

        if (!activeUser) {
          setAuthLoading(false);
          if (requireAuth) {
            await router.push("/auth");
          }
          return;
        }

        setUser(activeUser);
        setProfile(await getUserProfile(activeUser.id));
        setAuthLoading(false);
      } catch (error) {
        setAuthError(error instanceof Error ? error.message : "Could not load account");
        setAuthLoading(false);
      }
    }

    loadAuth();
    return () => {
      mounted = false;
    };
  }, [requireAuth, router]);

  return {
    authLoading,
    user,
    profile,
    authError,
    configured: isSupabaseConfigured,
    refreshProfile,
    logout,
  };
}

