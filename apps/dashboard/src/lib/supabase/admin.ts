import "server-only";

import { createClient } from "@supabase/supabase-js";

import { dashboardEnv } from "@/lib/env";

export function createAdminClient() {
  const serviceRoleKey = process.env.SUPABASE_KEY;
  if (!serviceRoleKey) {
    throw new Error("Missing required environment variable: SUPABASE_KEY");
  }

  return createClient(dashboardEnv.supabaseUrl, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });
}
