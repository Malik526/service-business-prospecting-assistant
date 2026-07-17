/** Supabase browser client and profile helpers for Phase 4 auth.
 *  The app shows setup guidance instead of crashing when env vars are missing.
 */

import { createClient, type User } from "@supabase/supabase-js";

import type { UserProfile } from "../types/prospect";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

export const isSupabaseConfigured = Boolean(
  supabaseUrl &&
    supabaseAnonKey &&
    !supabaseUrl.includes("your-project") &&
    !supabaseAnonKey.includes("your_anon_key"),
);

export const supabase = createClient(
  isSupabaseConfigured ? supabaseUrl : "https://placeholder.supabase.co",
  isSupabaseConfigured ? supabaseAnonKey : "placeholder-anon-key",
  {
    auth: {
      autoRefreshToken: true,
      detectSessionInUrl: true,
      persistSession: true,
    },
  },
);

/** Returns the currently authenticated Supabase user. */
export async function getUser(): Promise<User | null> {
  if (!isSupabaseConfigured) {
    return null;
  }

  const {
    data: { user },
  } = await supabase.auth.getUser();
  return user;
}

/** Fetches the monetization profile row for a Supabase auth user. */
export async function getUserProfile(userId: string): Promise<UserProfile> {
  const { data, error } = await supabase.from("users").select("*").eq("id", userId).single();
  if (error) {
    throw error;
  }
  return data as UserProfile;
}

/** Signs the active Supabase user out. */
export async function signOut(): Promise<void> {
  await supabase.auth.signOut();
}
