import { NextResponse } from "next/server";

import {
  createGoogleOAuthClient,
  GMAIL_SCOPES,
  serializeOAuthState,
} from "@/lib/server/google-oauth";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  const { searchParams } = new URL(request.url);
  const nextPath = searchParams.get("next") || "/profile";

  const oauthClient = createGoogleOAuthClient();
  const url = oauthClient.generateAuthUrl({
    access_type: "offline",
    prompt: "consent",
    scope: GMAIL_SCOPES,
    state: serializeOAuthState(nextPath),
  });

  return NextResponse.redirect(url);
}
