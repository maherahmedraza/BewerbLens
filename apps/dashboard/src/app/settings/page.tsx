"use client";

import { createClient } from "@/lib/supabase/client";
import { useState } from "react";
import styles from "./page.module.css";

export default function SettingsPage() {
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

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
