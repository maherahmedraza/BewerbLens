const warnedEnvKeys = new Set<string>();

function warnMissingEnv(name: string): void {
  if (warnedEnvKeys.has(name)) {
    return;
  }

  warnedEnvKeys.add(name);
  console.warn(`Missing ${name}; using a safe fallback value for dashboard stability.`);
}

function readEnv(name: string, fallback: string): string {
  const value = process.env[name]?.trim();
  if (value) {
    return value;
  }

  warnMissingEnv(name);
  return fallback;
}

export const dashboardEnv = {
  orchestratorUrl: process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://localhost:8000",
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL || "https://example.supabase.co",
  supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "missing-supabase-anon-key",
};
