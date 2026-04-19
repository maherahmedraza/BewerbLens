import type { SupabaseClient } from "@supabase/supabase-js";

import type { SyncMode, SyncStatus } from "@/lib/types";

type Region = "en" | "de" | "fr" | "es";

interface LegacyProfileRow {
  id: string;
  email: string;
  full_name: string | null;
  region: Region | null;
  gmail_credentials?: unknown;
  telegram_enabled?: boolean | null;
  telegram_chat_id?: string | null;
}

interface EnhancedProfileRow extends LegacyProfileRow {
  role?: "user" | "admin" | null;
  gmail_connected_at?: string | null;
  telegram_connected_at?: string | null;
  sync_mode?: SyncMode | null;
  sync_status?: SyncStatus | null;
  backfill_start_date?: string | null;
  last_synced_at?: string | null;
  sync_error?: string | null;
}

export interface CompatibleUserProfile {
  id: string;
  email: string;
  full_name: string | null;
  region: Region;
  role: "user" | "admin";
  telegram_enabled: boolean;
  gmail_connected: boolean;
  gmail_connected_at: string | null;
  telegram_connected: boolean;
  telegram_connected_at: string | null;
  sync_mode: SyncMode;
  sync_status: SyncStatus;
  backfill_start_date: string | null;
  last_synced_at: string | null;
  sync_error: string | null;
  supportsSyncSchema: boolean;
}

const LEGACY_PROFILE_SELECT =
  "id, email, full_name, region, gmail_credentials, telegram_enabled, telegram_chat_id";

const ENHANCED_PROFILE_SELECT =
  `${LEGACY_PROFILE_SELECT}, role, gmail_connected_at, telegram_connected_at, sync_mode, sync_status, backfill_start_date, last_synced_at, sync_error`;

function isMissingColumnError(error: { message?: string } | null) {
  const message = String(error?.message || "").toLowerCase();
  return (
    message.includes("column") ||
    message.includes("schema cache") ||
    message.includes("could not find")
  );
}

function normalizeRegion(region: string | null | undefined): Region {
  if (region === "de" || region === "fr" || region === "es") {
    return region;
  }
  return "en";
}

function normalizeProfile(
  row: LegacyProfileRow | EnhancedProfileRow,
  supportsSyncSchema: boolean
): CompatibleUserProfile {
  const gmailConnected = Boolean(
    ("gmail_connected_at" in row ? row.gmail_connected_at : null) || row.gmail_credentials
  );
  const telegramConnected = Boolean(
    ("telegram_connected_at" in row ? row.telegram_connected_at : null) || row.telegram_chat_id
  );

  return {
    id: row.id,
    email: row.email,
    full_name: row.full_name ?? null,
    region: normalizeRegion(row.region),
    role: "role" in row && row.role === "admin" ? "admin" : "user",
    telegram_enabled: Boolean(row.telegram_enabled),
    gmail_connected: gmailConnected,
    gmail_connected_at:
      supportsSyncSchema && "gmail_connected_at" in row ? row.gmail_connected_at ?? null : null,
    telegram_connected: telegramConnected,
    telegram_connected_at:
      supportsSyncSchema && "telegram_connected_at" in row
        ? row.telegram_connected_at ?? null
        : null,
    sync_mode:
      supportsSyncSchema && "sync_mode" in row && row.sync_mode ? row.sync_mode : "backfill",
    sync_status:
      supportsSyncSchema && "sync_status" in row && row.sync_status ? row.sync_status : "pending",
    backfill_start_date:
      supportsSyncSchema && "backfill_start_date" in row ? row.backfill_start_date ?? null : null,
    last_synced_at:
      supportsSyncSchema && "last_synced_at" in row ? row.last_synced_at ?? null : null,
    sync_error: supportsSyncSchema && "sync_error" in row ? row.sync_error ?? null : null,
    supportsSyncSchema,
  };
}

async function fetchProfileRow(
  supabase: SupabaseClient,
  userId: string
): Promise<{ row: LegacyProfileRow | EnhancedProfileRow | null; supportsSyncSchema: boolean }> {
  const enhanced = await supabase
    .from("user_profiles")
    .select(ENHANCED_PROFILE_SELECT)
    .eq("id", userId)
    .maybeSingle();

  if (!enhanced.error) {
    return {
      row: (enhanced.data as EnhancedProfileRow | null) ?? null,
      supportsSyncSchema: true,
    };
  }

  if (!isMissingColumnError(enhanced.error)) {
    throw enhanced.error;
  }

  const legacy = await supabase
    .from("user_profiles")
    .select(LEGACY_PROFILE_SELECT)
    .eq("id", userId)
    .maybeSingle();

  if (legacy.error) {
    throw legacy.error;
  }

  return {
    row: (legacy.data as LegacyProfileRow | null) ?? null,
    supportsSyncSchema: false,
  };
}

export async function getOrCreateCompatibleUserProfile(
  supabase: SupabaseClient,
  userId: string,
  userEmail: string
) {
  let profileResult = await fetchProfileRow(supabase, userId);

  if (!profileResult.row) {
    const { error: upsertError } = await supabase
      .from("user_profiles")
      .upsert({ id: userId, email: userEmail });

    if (upsertError) {
      throw upsertError;
    }

    const { error: initializeError } = await supabase.rpc("initialize_user", {
      p_user_id: userId,
      p_region: "en",
    });

    if (initializeError) {
      throw initializeError;
    }

    profileResult = await fetchProfileRow(supabase, userId);
  }

  if (!profileResult.row) {
    throw new Error("User profile could not be loaded.");
  }

  return normalizeProfile(profileResult.row, profileResult.supportsSyncSchema);
}
