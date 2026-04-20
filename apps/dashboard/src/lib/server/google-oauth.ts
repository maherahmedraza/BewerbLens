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

export function createGoogleOAuthClient() {
  return new OAuth2Client({
    clientId: getRequiredEnv("GOOGLE_CLIENT_ID"),
    clientSecret: getRequiredEnv("GOOGLE_CLIENT_SECRET"),
    redirectUri: getRequiredEnv("GOOGLE_OAUTH_REDIRECT_URI"),
  });
}

export function getMissingGoogleOAuthEnvVars() {
  return ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_OAUTH_REDIRECT_URI"].filter(
    (name) => !process.env[name]
  );
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
