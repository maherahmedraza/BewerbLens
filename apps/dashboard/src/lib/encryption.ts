import "server-only";

import crypto from "node:crypto";

const AES_PREFIX = "aes256gcm";

function getEncryptionSecret() {
  const secret = process.env.ENCRYPTION_SECRET || process.env.ENCRYPTION_KEY;
  if (!secret) {
    throw new Error("Missing required environment variable: ENCRYPTION_SECRET or ENCRYPTION_KEY");
  }
  return secret;
}

function deriveKey() {
  return crypto.createHash("sha256").update(getEncryptionSecret()).digest();
}

export function encryptJson(payload: unknown) {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", deriveKey(), iv);
  const ciphertext = Buffer.concat([
    cipher.update(JSON.stringify(payload), "utf8"),
    cipher.final(),
  ]);
  const authTag = cipher.getAuthTag();

  return `${AES_PREFIX}:${iv.toString("base64url")}:${Buffer.concat([
    ciphertext,
    authTag,
  ]).toString("base64url")}`;
}
