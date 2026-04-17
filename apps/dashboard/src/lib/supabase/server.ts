import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { dashboardEnv } from "@/lib/env";

export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    dashboardEnv.supabaseUrl,
    dashboardEnv.supabaseAnonKey,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            );
          } catch {
            // The `setAll` method was called from a Server Component.
            // This can result in a cookie not being set, which is fine
            // because Server Components don't have the ability to set cookies
            // that persist across requests.
          }
        },
      },
    }
  );
}
