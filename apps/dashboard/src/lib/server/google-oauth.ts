import "server-only";

import { OAuth2Client } from "google-auth-library";

export const GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"];

interface OAuthState {
  next: string;
}

function getRequiredEnv(name: string) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export function createGoogleOAuthClient() {
  return new OAuth2Client({
    clientId: getRequiredEnv("GOOGLE_CLIENT_ID"),
    clientSecret: getRequiredEnv("GOOGLE_CLIENT_SECRET"),
    redirectUri: getRequiredEnv("GOOGLE_OAUTH_REDIRECT_URI"),
  });
}

function normalizeNextPath(nextPath: string | null | undefined) {
  if (!nextPath || !nextPath.startsWith("/") || nextPath.startsWith("//")) {
    return "/profile";
  }
  return nextPath;
}

export function serializeOAuthState(nextPath: string) {
  const payload: OAuthState = {
    next: normalizeNextPath(nextPath),
  };
  return Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
}

export function parseOAuthState(state: string | null) {
  if (!state) {
    return { next: "/profile" };
  }

  try {
    const parsed = JSON.parse(Buffer.from(state, "base64url").toString("utf8")) as Partial<OAuthState>;
    return { next: normalizeNextPath(parsed.next) };
  } catch {
    return { next: "/profile" };
  }
}
