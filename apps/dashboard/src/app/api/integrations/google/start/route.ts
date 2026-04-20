import { NextResponse } from "next/server";

import {
  createOAuthNonce,
  createOAuthStateCookieValue,
  createGoogleOAuthClient,
  GMAIL_SCOPES,
  getMissingGoogleOAuthEnvVars,
  serializeOAuthState,
} from "@/lib/server/google-oauth";
import { createClient } from "@/lib/supabase/server";

export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    const missingVars = getMissingGoogleOAuthEnvVars();
    if (missingVars.length > 0) {
      return NextResponse.json(
        {
          error: `Google OAuth is not configured. Missing: ${missingVars.join(", ")}`,
        },
        { status: 503 }
      );
    }

    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.redirect(new URL("/login", request.url));
    }

    const { searchParams } = new URL(request.url);
    const nextPath = searchParams.get("next") || "/profile";
    const nonce = createOAuthNonce();

    const oauthClient = createGoogleOAuthClient();
    const url = oauthClient.generateAuthUrl({
      access_type: "offline",
      prompt: "consent",
      scope: GMAIL_SCOPES,
      state: serializeOAuthState(nextPath, nonce),
    });

    const response = NextResponse.redirect(url);
    response.cookies.set("google_oauth_state", createOAuthStateCookieValue(nonce), {
      httpOnly: true,
      sameSite: "lax",
      secure: new URL(request.url).protocol === "https:",
      maxAge: 60 * 10,
      path: "/",
    });
    return response;
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Failed to start Google OAuth.",
      },
      { status: 500 }
    );
  }
}
