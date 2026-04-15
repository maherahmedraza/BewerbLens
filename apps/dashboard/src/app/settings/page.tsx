"use client";

import { createClient } from "@/lib/supabase/client";
import api from "@/lib/api";
import { useState, useEffect } from "react";
import styles from "./page.module.css";

interface PipelineConfig {
  schedule_interval_hours: number;
  is_paused: boolean;
  retention_days: number;
}

export default function SettingsPage() {
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [config, setConfig] = useState<PipelineConfig | null>(null);
  const [configLoading, setConfigLoading] = useState(true);

  useEffect(() => {
    loadConfig();
  }, []);

  async function loadConfig() {
    try {
      const res = await api.get("/config/");
      setConfig(res.data);
    } catch {
      setConfig(null);
    } finally {
      setConfigLoading(false);
    }
  }

  async function updateConfig(patch: Partial<PipelineConfig>) {
    setLoading(true);
    setMessage("");
    try {
      const res = await api.patch("/config/", patch);
      setConfig(res.data);
      setMessage("Pipeline configuration updated.");
    } catch (error: any) {
      setMessage(`Update failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleExport() {
    setLoading(true);
    setMessage("");
    try {
      const supabase = createClient();
      const { data, error } = await supabase
        .from("applications")
        .select("*");

      if (error) throw error;

      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "applications-export.json";
      a.click();
      URL.revokeObjectURL(url);
      setMessage("Data exported successfully");
    } catch (error: any) {
      setMessage(`Export failed: ${error.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    if (!confirm("Are you sure? This will delete ALL your data. This cannot be undone.")) {
      return;
    }
    setLoading(true);
    setMessage("");
    try {
      const supabase = createClient();
      const { error } = await supabase.rpc("delete_all_data");
      if (error) throw error;
      setMessage("All data deleted successfully");
    } catch (error: any) {
      setMessage(`Delete failed: ${error.message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.container}>
      <h1 className={styles.heading}>Settings</h1>

      {/* Pipeline Configuration */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Pipeline Configuration</h2>
        <p className={styles.description}>
          Control how often your email pipeline syncs and manage its execution state.
        </p>

        {configLoading ? (
          <p className={styles.description}>Loading configuration...</p>
        ) : config ? (
          <div className={styles.configGrid}>
            <div className={styles.configRow}>
              <label className={styles.label}>Sync Interval (hours)</label>
              <select
                className={styles.select}
                value={config.schedule_interval_hours}
                disabled={loading}
                onChange={(e) =>
                  updateConfig({ schedule_interval_hours: parseFloat(e.target.value) })
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
              <label className={styles.label}>Log Retention (days)</label>
              <select
                className={styles.select}
                value={config.retention_days}
                disabled={loading}
                onChange={(e) =>
                  updateConfig({ retention_days: parseInt(e.target.value) })
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
              <label className={styles.label}>Pipeline Status</label>
              <button
                className={`${styles.button} ${config.is_paused ? styles.success : styles.warning}`}
                disabled={loading}
                onClick={() => updateConfig({ is_paused: !config.is_paused })}
              >
                {config.is_paused ? "▶ Resume Pipeline" : "⏸ Pause Pipeline"}
              </button>
            </div>
          </div>
        ) : (
          <p className={styles.description}>
            Could not load pipeline configuration. Is the orchestrator running?
          </p>
        )}
      </div>

      {/* GDPR Export */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>GDPR — Right to Access</h2>
        <p className={styles.description}>
          Export all your application data as a JSON file.
        </p>
        <button
          className={styles.button}
          onClick={handleExport}
          disabled={loading}
        >
          {loading ? "Exporting..." : "Export Data (JSON)"}
        </button>
      </div>

      {/* GDPR Delete */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>GDPR — Right to Erasure</h2>
        <p className={styles.description}>
          Permanently delete all your data from the system. This action cannot be undone.
        </p>
        <button
          className={`${styles.button} ${styles.danger}`}
          onClick={handleDelete}
          disabled={loading}
        >
          {loading ? "Deleting..." : "Delete All My Data"}
        </button>
      </div>

      {message && (
        <div className={styles.message}>
          {message}
        </div>
      )}
    </div>
  );
}
