"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { PlusIcon, TrashIcon } from "@heroicons/react/24/outline";

import { createClient } from "@/lib/supabase/client";
import type { SyncMode, SyncStatus } from "@/lib/types";

import styles from "./profile.module.css";

type Region = "en" | "de" | "fr" | "es";
type FilterType = "include" | "exclude";
type FilterField = "subject" | "sender" | "body";

interface EmailFilter {
  id: string;
  filter_type: FilterType;
  field: FilterField;
  pattern: string;
  is_regex: boolean;
  is_active: boolean;
  priority: number;
}

interface ProfileState {
  id: string;
  email: string;
  full_name: string | null;
  region: Region;
  role: "user" | "admin";
  gmail_connected_at: string | null;
  telegram_connected_at: string | null;
  telegram_enabled: boolean;
  sync_mode: SyncMode;
  sync_status: SyncStatus;
  backfill_start_date: string | null;
  last_synced_at: string | null;
}

interface TelegramLinkState {
  linkCode: string;
  expiresAt: string;
  botUsername: string | null;
  botUrl: string | null;
}

const PROFILE_SELECT =
  "id, email, full_name, region, role, gmail_connected_at, telegram_connected_at, telegram_enabled, sync_mode, sync_status, backfill_start_date, last_synced_at";

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function formatDate(value: string | null) {
  if (!value) {
    return "Not connected";
  }
  return new Date(value).toLocaleString();
}

export default function ProfileSettingsPage() {
  const supabase = useMemo(() => createClient(), []);
  const [profile, setProfile] = useState<ProfileState | null>(null);
  const [filters, setFilters] = useState<EmailFilter[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [integrationMessage, setIntegrationMessage] = useState("");
  const [telegramLink, setTelegramLink] = useState<TelegramLinkState | null>(null);
  const [linkingTelegram, setLinkingTelegram] = useState(false);

  const loadProfile = useCallback(async () => {
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) {
      setProfile(null);
      return;
    }

    const { data, error } = await supabase
      .from("user_profiles")
      .select(PROFILE_SELECT)
      .eq("id", user.id)
      .maybeSingle();

    if (!data) {
      const { error: upsertError } = await supabase
        .from("user_profiles")
        .upsert({ id: user.id, email: user.email || "" });

      if (upsertError) {
        throw upsertError;
      }

      const { error: initializeError } = await supabase.rpc("initialize_user", {
        p_user_id: user.id,
        p_region: "en",
      });
      if (initializeError) {
        throw initializeError;
      }

      const { data: reloadedProfile, error: reloadError } = await supabase
        .from("user_profiles")
        .select(PROFILE_SELECT)
        .eq("id", user.id)
        .single();

      if (reloadError) {
        throw reloadError;
      }
      setProfile(reloadedProfile as ProfileState);
      return;
    }

    if (error) {
      throw error;
    }

    setProfile(data as ProfileState);
  }, [supabase]);

  const loadFilters = useCallback(async () => {
    const { data, error } = await supabase
      .from("email_filters")
      .select("id, filter_type, field, pattern, is_regex, is_active, priority")
      .order("priority", { ascending: true });

    if (error) {
      throw error;
    }

    setFilters((data || []) as EmailFilter[]);
  }, [supabase]);

  useEffect(() => {
    async function loadPage() {
      try {
        await Promise.all([loadProfile(), loadFilters()]);
      } catch (error) {
        setMessage(getErrorMessage(error));
      } finally {
        setLoading(false);
      }
    }

    void loadPage();
  }, [loadFilters, loadProfile]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      const searchParams = new URLSearchParams(window.location.search);
      const gmailState = searchParams.get("gmail");
      const callbackMessage = searchParams.get("message");

      if (gmailState === "connected") {
        setIntegrationMessage("Gmail connected. You can start your backfill from Settings.");
      } else if (gmailState === "error") {
        setIntegrationMessage(callbackMessage || "Gmail connection failed.");
      }
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, []);

  async function saveProfile(updates: Partial<ProfileState>) {
    if (!profile) {
      return;
    }

    setSaving(true);
    setMessage("");

    try {
      const { error } = await supabase.from("user_profiles").update(updates).eq("id", profile.id);
      if (error) {
        throw error;
      }

      setProfile((current) => (current ? { ...current, ...updates } : current));
      setMessage("Profile updated.");
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function changeRegion(newRegion: Region) {
    if (!profile || !window.confirm("Changing region resets your default email filters. Continue?")) {
      return;
    }

    setSaving(true);
    setMessage("");

    try {
      const { error } = await supabase.rpc("initialize_user", {
        p_user_id: profile.id,
        p_region: newRegion,
      });

      if (error) {
        throw error;
      }

      setProfile((current) => (current ? { ...current, region: newRegion } : current));
      await loadFilters();
      setMessage(`Region updated to ${newRegion.toUpperCase()}.`);
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function addFilter() {
    if (!profile) {
      return;
    }

    try {
      const { data, error } = await supabase
        .from("email_filters")
        .insert({
          user_id: profile.id,
          filter_type: "include",
          field: "subject",
          pattern: "",
          is_regex: false,
          is_active: true,
          priority: filters.length,
        })
        .select("id, filter_type, field, pattern, is_regex, is_active, priority")
        .single();

      if (error) {
        throw error;
      }

      setFilters((current) => [...current, data as EmailFilter]);
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  async function updateFilter(filterId: string, updates: Partial<EmailFilter>) {
    try {
      const { error } = await supabase.from("email_filters").update(updates).eq("id", filterId);
      if (error) {
        throw error;
      }

      setFilters((current) =>
        current.map((filter) => (filter.id === filterId ? { ...filter, ...updates } : filter))
      );
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  async function deleteFilter(filterId: string) {
    try {
      const { error } = await supabase.from("email_filters").delete().eq("id", filterId);
      if (error) {
        throw error;
      }

      setFilters((current) => current.filter((filter) => filter.id !== filterId));
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  function connectGmail() {
    window.location.assign("/api/integrations/google/start?next=/profile");
  }

  async function startTelegramLink() {
    setLinkingTelegram(true);
    setMessage("");

    try {
      const response = await fetch("/api/integrations/telegram/link/start", {
        method: "POST",
      });
      const payload = (await response.json()) as
        | {
            error?: string;
            link_code: string;
            expires_at: string;
            bot_username: string | null;
            bot_url: string | null;
          }
        | { error: string };

      if (!response.ok || !("link_code" in payload)) {
        throw new Error(("error" in payload && payload.error) || "Failed to create Telegram link code.");
      }

      setTelegramLink({
        linkCode: payload.link_code,
        expiresAt: payload.expires_at,
        botUsername: payload.bot_username,
        botUrl: payload.bot_url,
      });
      setMessage("Telegram link code created. Send it to your bot to connect notifications.");
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setLinkingTelegram(false);
    }
  }

  async function copyTelegramCode() {
    if (!telegramLink) {
      return;
    }

    await navigator.clipboard.writeText(telegramLink.linkCode);
    setMessage("Telegram link code copied.");
  }

  if (loading) {
    return <div className={styles.loading}>Loading profile...</div>;
  }

  if (!profile) {
    return (
      <div className={styles.error}>
        <p>Could not load your profile. Please sign in again.</p>
        <Link href="/login" className={styles.helpLink}>
          Go to Login
        </Link>
      </div>
    );
  }

  const gmailConnected = Boolean(profile.gmail_connected_at);
  const telegramConnected = Boolean(profile.telegram_connected_at);

  return (
    <div className={styles.profileContainer}>
      <h1>Profile & Settings</h1>

      {message || integrationMessage ? (
        <div className={styles.message}>{message || integrationMessage}</div>
      ) : null}

      <section className={styles.section}>
        <h2>Basic Information</h2>

        <div className={styles.formGroup}>
          <label>Email</label>
          <input type="text" value={profile.email} disabled />
        </div>

        <div className={styles.formGroup}>
          <label>Full Name</label>
          <input
            type="text"
            value={profile.full_name || ""}
            onChange={(event) =>
              setProfile((current) => (current ? { ...current, full_name: event.target.value } : current))
            }
            onBlur={() => void saveProfile({ full_name: profile.full_name })}
          />
        </div>

        <div className={styles.formGroup}>
          <label>Region / Language</label>
          <select
            value={profile.region}
            disabled={saving}
            onChange={(event) => void changeRegion(event.target.value as Region)}
          >
            <option value="en">English (EN)</option>
            <option value="de">German (DE)</option>
            <option value="fr">French (FR)</option>
            <option value="es">Spanish (ES)</option>
          </select>
          <p className={styles.helpText}>This refreshes the default include and exclude filters.</p>
        </div>
      </section>

      <section className={styles.section}>
        <h2>Integrations</h2>

        <div className={styles.providerCard}>
          <div className={styles.providerHeader}>
            <h3>Gmail</h3>
            <span className={gmailConnected ? styles.statusConnected : styles.statusDisconnected}>
              {gmailConnected ? "Connected" : "Not connected"}
            </span>
          </div>
          <p>Authorize Gmail once. BewerbLens stores the refresh token server-side and keeps sync controls in Settings.</p>
          <p className={styles.helpText}>
            Connected: {formatDate(profile.gmail_connected_at)} · Sync mode: {profile.sync_mode} · Status: {profile.sync_status}
          </p>
          <div className={styles.inlineActions}>
            <button onClick={connectGmail} className={styles.btnPrimary}>
              {gmailConnected ? "Reconnect Gmail" : "Connect Gmail"}
            </button>
            <Link href="/settings" className={styles.btnSecondary}>
              Manage Sync
            </Link>
          </div>
        </div>

        <div className={styles.providerCard}>
          <div className={styles.providerHeader}>
            <h3>Telegram Notifications</h3>
            <span className={telegramConnected ? styles.statusConnected : styles.statusDisconnected}>
              {telegramConnected ? "Connected" : "Not connected"}
            </span>
          </div>
          <p>Link your Telegram chat with a one-time code instead of pasting bot tokens or chat IDs into the browser.</p>
          <p className={styles.helpText}>Connected: {formatDate(profile.telegram_connected_at)}</p>

          <label className={styles.checkboxLabel}>
            <input
              type="checkbox"
              checked={profile.telegram_enabled}
              disabled={!telegramConnected || saving}
              onChange={(event) => void saveProfile({ telegram_enabled: event.target.checked })}
            />
            Enable Telegram notifications
          </label>

          <div className={styles.inlineActions}>
            <button
              onClick={() => void startTelegramLink()}
              className={styles.btnPrimary}
              disabled={linkingTelegram}
            >
              {telegramConnected ? "Relink Telegram" : "Link Telegram"}
            </button>
          </div>

          {telegramLink ? (
            <div className={styles.noticeCard}>
              <p className={styles.helpText}>Link code (expires {formatDate(telegramLink.expiresAt)})</p>
              <div className={styles.codeRow}>
                <code className={styles.codeBlock}>{telegramLink.linkCode}</code>
                <button onClick={() => void copyTelegramCode()} className={styles.btnSecondary}>
                  Copy Code
                </button>
              </div>
              {telegramLink.botUrl ? (
                <a
                  href={telegramLink.botUrl}
                  target="_blank"
                  rel="noreferrer"
                  className={styles.helpLink}
                >
                  Open @{telegramLink.botUsername} →
                </a>
              ) : (
                <p className={styles.helpText}>
                  Send this code to your Telegram bot to complete the link.
                </p>
              )}
            </div>
          ) : null}
        </div>
      </section>

      <section className={styles.section}>
        <h2>Email Filters</h2>
        <p className={styles.helpText}>
          Include and exclude rules run before classification so you can keep noisy alerts out of the pipeline.
        </p>

        <button onClick={() => void addFilter()} className={styles.btnSecondary}>
          <PlusIcon className={styles.icon} /> Add Filter
        </button>

        <div className={styles.filtersList}>
          {filters.map((filter) => (
            <div key={filter.id} className={styles.filterCard}>
              <div className={styles.filterRow}>
                <select
                  value={filter.filter_type}
                  onChange={(event) =>
                    void updateFilter(filter.id, { filter_type: event.target.value as FilterType })
                  }
                  className={styles.filterType}
                >
                  <option value="include">Include</option>
                  <option value="exclude">Exclude</option>
                </select>

                <span className={styles.filterText}>emails where</span>

                <select
                  value={filter.field}
                  onChange={(event) =>
                    void updateFilter(filter.id, { field: event.target.value as FilterField })
                  }
                >
                  <option value="subject">Subject</option>
                  <option value="sender">Sender</option>
                  <option value="body">Body</option>
                </select>

                <span className={styles.filterText}>contains</span>

                <input
                  type="text"
                  value={filter.pattern}
                  onChange={(event) => void updateFilter(filter.id, { pattern: event.target.value })}
                  placeholder="e.g. application, bewerbung"
                  className={styles.filterPattern}
                />

                <label className={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={filter.is_regex}
                    onChange={(event) =>
                      void updateFilter(filter.id, { is_regex: event.target.checked })
                    }
                  />
                  Regex
                </label>

                <label className={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={filter.is_active}
                    onChange={(event) =>
                      void updateFilter(filter.id, { is_active: event.target.checked })
                    }
                  />
                  Active
                </label>

                <button
                  onClick={() => void deleteFilter(filter.id)}
                  className={styles.btnIconDanger}
                  title="Delete filter"
                >
                  <TrashIcon className={styles.icon} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
