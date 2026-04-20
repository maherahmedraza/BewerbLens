import { subMonths } from "date-fns";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { encryptJson } from "@/lib/encryption";
import {
  createGoogleOAuthClient,
  GMAIL_SCOPES,
  getMissingGoogleOAuthEnvVars,
  isValidOAuthStateCookie,
  parseOAuthState,
} from "@/lib/server/google-oauth";
import { createClient } from "@/lib/supabase/server";

export const runtime = "nodejs";

function buildRedirect(origin: string, nextPath: string) {
  try {
    return new URL(nextPath, origin);
  } catch {
    return new URL("/profile", origin);
  }
}

export async function GET(request: Request) {
  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.redirect(new URL("/login", request.url));
    }

    const missingVars = getMissingGoogleOAuthEnvVars();
    const { searchParams, origin } = new URL(request.url);
    const state = parseOAuthState(searchParams.get("state"));
    const redirectUrl = buildRedirect(origin, state.next);
    const responseWithError = (message: string) => {
      redirectUrl.searchParams.set("gmail", "error");
      redirectUrl.searchParams.set("message", message);
      const response = NextResponse.redirect(redirectUrl);
      response.cookies.delete("google_oauth_state");
      return response;
    };

    if (missingVars.length > 0) {
      return responseWithError(
        `Google OAuth is not configured. Missing: ${missingVars.join(", ")}`
      );
    }

    const code = searchParams.get("code");
    if (!code) {
      return responseWithError("Missing Google authorization code.");
    }

    const stateCookie = (await cookies()).get("google_oauth_state")?.value;
    if (!isValidOAuthStateCookie(stateCookie, state.nonce)) {
      return responseWithError("Google OAuth session expired. Please try connecting Gmail again.");
    }

    const oauthClient = createGoogleOAuthClient();
    const { tokens } = await oauthClient.getToken(code);

    if (!tokens.refresh_token) {
      return responseWithError(
        "Google did not return a refresh token. Reconnect and grant consent again."
      );
    }

    const { data: profile } = await supabase
      .from("user_profiles")
      .select("backfill_start_date")
      .eq("id", user.id)
      .single();

    const backfillStartDate =
      profile?.backfill_start_date || subMonths(new Date(), 6).toISOString().slice(0, 10);

    const credentials = encryptJson({
      type: "authorized_user",
      client_id: process.env.GOOGLE_CLIENT_ID,
      client_secret: process.env.GOOGLE_CLIENT_SECRET,
      refresh_token: tokens.refresh_token,
      token: tokens.access_token,
      token_uri: "https://oauth2.googleapis.com/token",
      scopes: tokens.scope ? tokens.scope.split(" ") : GMAIL_SCOPES,
      expiry: tokens.expiry_date ? new Date(tokens.expiry_date).toISOString() : null,
    });

    const { error: updateError } = await supabase
      .from("user_profiles")
      .update({
        gmail_credentials: credentials,
        gmail_connected_via: "oauth",
        gmail_connected_at: new Date().toISOString(),
        backfill_start_date: backfillStartDate,
        sync_mode: "backfill",
        sync_status: "pending",
        sync_error: null,
      })
      .eq("id", user.id);

    if (updateError) {
      throw new Error(updateError.message);
    }

    redirectUrl.searchParams.set("gmail", "connected");
    const response = NextResponse.redirect(redirectUrl);
    response.cookies.delete("google_oauth_state");
    return response;
  } catch (error) {
    const { origin, searchParams } = new URL(request.url);
    const state = parseOAuthState(searchParams.get("state"));
    const redirectUrl = buildRedirect(origin, state.next);
    redirectUrl.searchParams.set("gmail", "error");
    redirectUrl.searchParams.set(
      "message",
      error instanceof Error ? error.message : "Failed to connect Gmail."
    );
    const response = NextResponse.redirect(redirectUrl);
    response.cookies.delete("google_oauth_state");
    return response;
  }
}
