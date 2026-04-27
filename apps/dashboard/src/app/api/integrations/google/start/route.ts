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

function buildFailureRedirect(request: Request, message: string) {
  const { searchParams, origin } = new URL(request.url);
  const nextPath = searchParams.get("next") || "/settings";
  const redirectUrl = new URL(nextPath, origin);
  redirectUrl.searchParams.set("gmail", "error");
  redirectUrl.searchParams.set("message", message);
  return NextResponse.redirect(redirectUrl);
}

export async function GET(request: Request) {
  try {
    const missingVars = getMissingGoogleOAuthEnvVars(request.url);
    if (missingVars.length > 0) {
      return buildFailureRedirect(
        request,
        `Google OAuth is not configured. Missing: ${missingVars.join(", ")}`
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

    const oauthClient = createGoogleOAuthClient(request.url);
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
    return buildFailureRedirect(
      request,
      error instanceof Error ? error.message : "Failed to start Google OAuth."
    );
  }
}
