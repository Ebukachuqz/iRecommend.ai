import { createBrowserClient as createSupabaseBrowserClient } from "@supabase/ssr";

function getSupabaseConfig() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !anonKey) {
    throw new Error("NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY must be configured.");
  }

  return { url, anonKey };
}

export function createBrowserClient() {
  const { url, anonKey } = getSupabaseConfig();
  return createSupabaseBrowserClient(url, anonKey);
}
