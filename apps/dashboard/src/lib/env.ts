export const dashboardEnv = {
  orchestratorUrl: process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://localhost:8000",
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL || "https://example.supabase.co",
  supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "missing-supabase-anon-key",
};
