import { createBrowserClient } from "@supabase/ssr";
import { dashboardEnv } from "@/lib/env";

export function createClient() {
  return createBrowserClient(
    dashboardEnv.supabaseUrl,
    dashboardEnv.supabaseAnonKey
  );
}
