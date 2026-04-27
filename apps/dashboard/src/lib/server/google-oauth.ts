import "server-only";

import crypto from "node:crypto";

import { OAuth2Client } from "google-auth-library";

export const GMAIL_SCOPES = [
  "https://www.googleapis.com/auth/gmail.readonly",
  "https://www.googleapis.com/auth/userinfo.email",
];

interface OAuthState {
  next: string;
  nonce: string;
}

function getRequiredEnv(name: string) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export function resolveGoogleOAuthRedirectUri(requestUrl?: string) {
  const configured = process.env.GOOGLE_OAUTH_REDIRECT_URI;
  if (configured) {
    return configured;
  }
  if (!requestUrl) {
    throw new Error("Missing required environment variable: GOOGLE_OAUTH_REDIRECT_URI");
  }
  return new URL("/api/integrations/google/callback", requestUrl).toString();
}

export function createGoogleOAuthClient(requestUrl?: string) {
  return new OAuth2Client({
    clientId: getRequiredEnv("GOOGLE_CLIENT_ID"),
    clientSecret: getRequiredEnv("GOOGLE_CLIENT_SECRET"),
    redirectUri: resolveGoogleOAuthRedirectUri(requestUrl),
  });
}

export function getMissingGoogleOAuthEnvVars(requestUrl?: string) {
  const missing = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"].filter((name) => !process.env[name]);
  if (!process.env.GOOGLE_OAUTH_REDIRECT_URI && !requestUrl) {
    missing.push("GOOGLE_OAUTH_REDIRECT_URI");
  }
  return missing;
}

function normalizeNextPath(nextPath: string | null | undefined) {
  if (!nextPath || !nextPath.startsWith("/") || nextPath.startsWith("//")) {
    return "/profile";
  }
  return nextPath;
}

export function createOAuthNonce() {
  return crypto.randomUUID();
}

function signNonce(nonce: string) {
  return crypto
    .createHmac("sha256", getRequiredEnv("GOOGLE_CLIENT_SECRET"))
    .update(nonce)
    .digest("base64url");
}

export function createOAuthStateCookieValue(nonce: string) {
  return `${nonce}.${signNonce(nonce)}`;
}

export function isValidOAuthStateCookie(cookieValue: string | undefined, nonce: string | null) {
  if (!cookieValue || !nonce) {
    return false;
  }

  const [cookieNonce, signature] = cookieValue.split(".", 2);
  if (!cookieNonce || !signature || cookieNonce !== nonce) {
    return false;
  }

  return signature === signNonce(nonce);
}

export function serializeOAuthState(nextPath: string, nonce: string) {
  const payload: OAuthState = {
    next: normalizeNextPath(nextPath),
    nonce,
  };
  return Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
}

export function parseOAuthState(state: string | null) {
  if (!state) {
    return { next: "/profile", nonce: null };
  }

  try {
    const parsed = JSON.parse(Buffer.from(state, "base64url").toString("utf8")) as Partial<OAuthState>;
    return {
      next: normalizeNextPath(parsed.next),
      nonce: typeof parsed.nonce === "string" ? parsed.nonce : null,
    };
  } catch {
    return { next: "/profile", nonce: null };
  }
}
