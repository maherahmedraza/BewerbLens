"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import WorkspaceSettings from "@/components/settings/WorkspaceSettings";
import Tooltip from "@/components/ui/Tooltip";
import api from "@/lib/api";
import type { PipelineConfig, SyncMode, SyncStatus } from "@/lib/types";
import { createClient } from "@/lib/supabase/client";
import { getOrCreateCompatibleUserProfile } from "@/lib/userProfiles";

import styles from "./page.module.css";

interface SyncSettings {
  id: string;
  supportsSyncSchema: boolean;
  gmail_connected: boolean;
  gmail_connected_at: string | null;
  gmail_connected_via: "oauth" | "env_fallback" | null;
  backfill_start_date: string | null;
  last_synced_at: string | null;
  sync_mode: SyncMode;
  sync_status: SyncStatus;
  sync_error: string | null;
}

function getErrorMessage(error: unknown) {
  if (error && typeof error === "object" && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) {
      return response.data.detail;
    }
  }

  return error instanceof Error ? error.message : "Something went wrong.";
}

function formatDate(value: string | null) {
  if (!value) {
    return "Not available";
  }
  return new Date(value).toLocaleString();
}

export default function SettingsPage() {
  const supabase = useMemo(() => createClient(), []);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [config, setConfig] = useState<PipelineConfig | null>(null);
  const [syncSettings, setSyncSettings] = useState<SyncSettings | null>(null);
  const [configLoading, setConfigLoading] = useState(true);
  const [syncLoading, setSyncLoading] = useState(true);
  const [backfillStartDate, setBackfillStartDate] = useState("");

  const loadConfig = useCallback(async () => {
    try {
      const response = await api.get("/config/");
      setConfig(response.data as PipelineConfig);
    } catch {
      setConfig(null);
    } finally {
      setConfigLoading(false);
    }
  }, []);

  const loadSyncSettings = useCallback(async () => {
    try {
      const {
        data: { user },
      } = await supabase.auth.getUser();

      if (!user) {
        setSyncSettings(null);
        return;
      }

      const profile = await getOrCreateCompatibleUserProfile(supabase, user.id, user.email || "");
      setSyncSettings(profile);
      setBackfillStartDate(profile.backfill_start_date || new Date().toISOString().slice(0, 10));
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setSyncLoading(false);
    }
  }, [supabase]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void Promise.all([loadConfig(), loadSyncSettings()]);
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [loadConfig, loadSyncSettings]);

  async function updateConfig(patch: Partial<PipelineConfig>) {
    setLoading(true);
    setMessage("");

    try {
      const response = await api.patch("/config/", patch);
      setConfig(response.data as PipelineConfig);
      setMessage("Pipeline configuration updated.");
    } catch (error) {
      setMessage(`Update failed: ${getErrorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  }

  async function triggerBackfill() {
    setLoading(true);
    setMessage("");

    try {
      const response = await fetch("/api/sync/backfill", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ startDate: backfillStartDate }),
      });
      const payload = (await response.json()) as { error?: string; message?: string };
      if (!response.ok) {
        throw new Error(payload.error || "Failed to queue backfill sync.");
      }

      await loadSyncSettings();
      setMessage(payload.message || "Backfill sync queued.");
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  async function triggerIncremental() {
    setLoading(true);
    setMessage("");

    try {
      const response = await fetch("/api/sync/incremental", {
        method: "POST",
      });
      const payload = (await response.json()) as { error?: string; message?: string };
      if (!response.ok) {
        throw new Error(payload.error || "Failed to queue incremental sync.");
      }

      await loadSyncSettings();
      setMessage(payload.message || "Incremental sync queued.");
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  async function handleExport() {
    setLoading(true);
    setMessage("");

    try {
      window.location.assign("/api/applications/export");
      setMessage("CSV export started. The file opens cleanly in Excel and Google Sheets.");
    } catch (error) {
      setMessage(`Export failed: ${getErrorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  }

  function connectGmail() {
    window.location.assign("/api/integrations/google/start?next=/settings");
  }

  async function handleDelete() {
    if (!window.confirm("Are you sure? This will delete all your data and cannot be undone.")) {
      return;
    }

    setLoading(true);
    setMessage("");

    try {
      const { error } = await supabase.rpc("delete_all_data");
      if (error) {
        throw error;
      }
      setMessage("All data deleted successfully.");
    } catch (error) {
      setMessage(`Delete failed: ${getErrorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  }

  const gmailConnected = Boolean(syncSettings?.gmail_connected);

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <span className={styles.eyebrow}>Workspace controls</span>
        <h1 className={styles.heading}>One place for account, sync, notifications, and data controls.</h1>
        <p className={styles.description}>
          Settings now groups personal account setup, integrations, pipeline controls, and privacy actions
          into a single workspace so configuration lives in one place.
        </p>
      </header>

      <div className={styles.stack}>
      <div className={styles.section} id="sync-controls">
        <h2 className={styles.sectionTitle}>Sync Controls</h2>
        <p className={styles.description}>
          Choose the backfill window for first-time syncs, check the latest status, and trigger on-demand runs.
        </p>

        {syncLoading ? (
          <p className={styles.description}>Loading sync settings...</p>
        ) : syncSettings ? (
          <div className={styles.syncGrid}>
            <div className={styles.noticeCard}>
              <h3 className={styles.noticeTitle}>How first-time sync works</h3>
              <p className={styles.description}>
                The backend Gemini key stays shared on DigitalOcean. Each user connects Gmail via
                OAuth, then queues a backfill here to process read and unread emails.
              </p>
              {!gmailConnected ? (
                <button className={styles.button} onClick={connectGmail} disabled={loading}>
                  Connect Gmail with OAuth
                </button>
              ) : null}
              <p className={styles.helperText}>
                Broad discovery mode is currently permissive and lets Gemini decide job relevance so
                you can measure maximum capture before tightening filters later.
              </p>
            </div>

            {!syncSettings.supportsSyncSchema ? (
              <p className={styles.errorText}>
                Migration <code>010_sync_integrations_analytics.sql</code> has not been applied yet.
                Basic profile data still works, but sync status and on-demand sync controls stay
                disabled until that migration is in the database.
              </p>
            ) : null}

            <div className={styles.statusCard}>
              <div>
                <span className={styles.label}>Current mode</span>
                <p className={styles.statusValue}>{syncSettings.sync_mode}</p>
              </div>
              <div>
                <span className={styles.label}>Status</span>
                <p className={styles.statusValue}>{syncSettings.sync_status}</p>
              </div>
              <div>
                <span className={styles.label}>Last synced</span>
                <p className={styles.statusValue}>{formatDate(syncSettings.last_synced_at)}</p>
              </div>
            </div>

            <div className={styles.fieldGrid}>
              <div className={styles.configRow}>
                <label className={styles.label} htmlFor="backfill-start">
                  Backfill start date
                  <Tooltip iconOnly content="Determines how far back the initial sync looks for job applications. Set this to the date you started applying." />
                </label>
                <input
                  id="backfill-start"
                  type="date"
                  className={styles.input}
                  value={backfillStartDate}
                  disabled={loading || !gmailConnected}
                  onChange={(event) => setBackfillStartDate(event.target.value)}
                />
              </div>

              <div className={styles.helperRow}>
                <span className={styles.helperText}>
                  Gmail connected:{" "}
                  {gmailConnected
                    ? syncSettings.gmail_connected_via === "env_fallback"
                      ? "Legacy env fallback"
                      : "OAuth"
                    : "No"}
                </span>
                <span className={styles.helperText}>
                  Initial start date: {syncSettings.backfill_start_date || "Not set"}
                </span>
              </div>

              {syncSettings.gmail_connected_via === "env_fallback" ? (
                <p className={styles.errorText}>
                  This user is still running on the legacy Gmail environment fallback. Connect Gmail
                  from Workspace Settings to switch to stored OAuth credentials.
                </p>
              ) : null}

              {syncSettings.sync_error ? (
                <p className={styles.errorText}>{syncSettings.sync_error}</p>
              ) : null}

              <div className={styles.actionsRow}>
                <button
                  className={styles.button}
                  onClick={() => void triggerBackfill()}
                  disabled={loading || !gmailConnected || !syncSettings.supportsSyncSchema}
                >
                  Queue Backfill
                </button>
                <button
                  className={`${styles.button} ${styles.success}`}
                  onClick={() => void triggerIncremental()}
                  disabled={loading || !gmailConnected || !syncSettings.supportsSyncSchema}
                >
                  Queue Incremental Sync
                </button>
              </div>
            </div>
          </div>
        ) : (
          <p className={styles.description}>Could not load sync settings.</p>
        )}
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Pipeline Configuration</h2>
        <p className={styles.description}>
          Control how often the shared orchestrator checks for new emails, how much backlog each run can process,
          and how long operational history is retained.
        </p>

        {configLoading ? (
          <p className={styles.description}>Loading configuration...</p>
        ) : config ? (
          <div className={styles.fieldGrid}>
            <div className={styles.configRow}>
              <label className={styles.label}>
                Sync Interval (hours)
                <Tooltip iconOnly content="How often the shared orchestrator checks for new emails. Frequent syncs consume more AI API quota." />
              </label>
              <select
                className={styles.select}
                value={config.schedule_interval_hours}
                disabled={loading}
                onChange={(event) =>
                  void updateConfig({ schedule_interval_hours: Number(event.target.value) })
                }
              >
                <option value={1}>Every 1 hour</option>
                <option value={2}>Every 2 hours</option>
                <option value={4}>Every 4 hours</option>
                <option value={8}>Every 8 hours</option>
                <option value={12}>Every 12 hours</option>
                <option value={24}>Every 24 hours</option>
              </select>
            </div>

            <div className={styles.configRow}>
              <label className={styles.label}>
                Log Retention (days)
                <Tooltip iconOnly content="How long pipeline execution logs and usage history are kept before being automatically deleted to save space." />
              </label>
              <select
                className={styles.select}
                value={config.retention_days}
                disabled={loading}
                onChange={(event) =>
                  void updateConfig({ retention_days: Number(event.target.value) })
                }
              >
                <option value={7}>7 days</option>
                <option value={14}>14 days</option>
                <option value={30}>30 days</option>
                <option value={60}>60 days</option>
                <option value={90}>90 days</option>
              </select>
            </div>

            <div className={styles.configRow}>
              <label className={styles.label}>
                Backfill Fairness Cap
                <Tooltip iconOnly content="Maximum number of emails processed per run. Large backfills are chunked so one user cannot monopolize the worker." />
              </label>
              <select
                className={styles.select}
                value={config.max_emails_per_run ?? 250}
                disabled={loading}
                onChange={(event) =>
                  void updateConfig({ max_emails_per_run: Number(event.target.value) })
                }
              >
                <option value={100}>100 emails / run</option>
                <option value={250}>250 emails / run</option>
                <option value={500}>500 emails / run</option>
                <option value={1000}>1000 emails / run</option>
              </select>
            </div>

            <div className={styles.configRow}>
              <label className={styles.label}>
                Pipeline Status
                <Tooltip iconOnly content="Pause the pipeline to stop scheduled syncs without losing data. On-demand syncs will still work." />
              </label>
              <button
                className={`${styles.button} ${config.is_paused ? styles.success : styles.warning}`}
                disabled={loading}
                onClick={() => void updateConfig({ is_paused: !config.is_paused })}
              >
                {config.is_paused ? "Resume Pipeline" : "Pause Pipeline"}
              </button>
            </div>

            <p className={styles.helperText}>
              If a mailbox has a large backlog, BewerbLens now stores everything immediately but only processes the
              configured chunk per run. Deferred emails stay queued for the next run instead of starving other users.
            </p>
          </div>
        ) : (
          <p className={styles.description}>
            Could not load pipeline configuration. Make sure the orchestrator is running.
          </p>
        )}
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>GDPR — Right to Access</h2>
        <p className={styles.description}>
          Export all your application data as a spreadsheet-friendly CSV for Excel or Google Sheets.
        </p>
        <button className={styles.button} onClick={() => void handleExport()} disabled={loading}>
          Export Data (CSV)
        </button>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>GDPR — Right to Erasure</h2>
        <p className={styles.description}>
          Permanently delete all your data from the system. This action cannot be undone.
        </p>
        <button
          className={`${styles.button} ${styles.danger}`}
          onClick={() => void handleDelete()}
          disabled={loading}
        >
          Delete All My Data
        </button>
      </div>

      {message ? <div className={styles.message}>{message}</div> : null}
      </div>

      <WorkspaceSettings showHeading={false} />
    </div>
  );
}
