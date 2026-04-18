"use client";

import { 
  PauseIcon, 
  PlayIcon, 
  TrashIcon, 
  ClockIcon, 
  ShieldCheckIcon 
} from "@heroicons/react/24/solid";
import styles from "./ConfigPanel.module.css";
import { useCurrentConfig, useUpdateConfig } from "@/hooks/usePipeline";

export default function ConfigPanel() {
  const { data: config, isLoading } = useCurrentConfig();
  const updateMutation = useUpdateConfig();

  if (isLoading) {
    return <div className={styles.loading}>Loading Settings...</div>;
  }

  const handleUpdate = (patch: any) => {
    updateMutation.mutate(patch);
  };

  const isPaused = config?.is_paused || false;
  const retention = config?.retention_days || 30;
  const interval = config?.schedule_interval_hours?.toString() || "4.0";

  return (
    <div className={styles.card}>
      <h3 className={styles.title}>Pipeline Settings</h3>
      
      {/* ── Pause/Resume Control ───────────────────────────── */}
      <div className={styles.controlGroup}>
        <div className={styles.labelRow}>
          <div className={styles.labelInfo}>
            <span className={styles.label}>Global Status</span>
            <p className={styles.help}>Pause all scheduled runs</p>
          </div>
          <button 
            onClick={() => handleUpdate({ is_paused: !isPaused })}
            disabled={updateMutation.isPending}
            className={`${styles.toggle} ${isPaused ? styles.isPaused : ""}`}
          >
            {isPaused ? <PlayIcon className={styles.toggleIcon} /> : <PauseIcon className={styles.toggleIcon} />}
            {isPaused ? "Resume" : "Pause"}
          </button>
        </div>
      </div>

      {/* ── Schedule Interval ──────────────────────────────── */}
      <div className={styles.controlGroup}>
        <label className={styles.labelRow}>
          <div className={styles.labelInfo}>
            <span className={styles.label}>Sync Interval</span>
            <p className={styles.help}>How often to check for new emails</p>
          </div>
          <select 
            value={interval} 
            onChange={(e) => handleUpdate({ schedule_interval_hours: parseFloat(e.target.value) })}
            disabled={updateMutation.isPending}
            className={styles.select}
          >
            <option value="1.0">Every hour</option>
            <option value="4.0">Every 4 hours</option>
            <option value="12.0">Twice daily</option>
            <option value="24.0">Daily</option>
          </select>
        </label>
      </div>

      {/* ── Log Retention ─────────────────────────────────── */}
      <div className={styles.controlGroup}>
        <div className={styles.labelRow}>
          <div className={styles.labelInfo}>
            <span className={styles.label}>Log Retention</span>
            <p className={styles.help}>Keep run history for {retention} days</p>
          </div>
          <span className={styles.valueDisplay}>{retention} d</span>
        </div>
        <input 
          type="range" 
          min="1" 
          max="90" 
          value={retention} 
          onChange={(e) => handleUpdate({ retention_days: parseInt(e.target.value) })}
          disabled={updateMutation.isPending}
          className={styles.range}
        />
      </div>

      <div className={styles.footer}>
        <p className={styles.auditLink}>View Configuration Audit Trail</p>
      </div>
    </div>
  );
}
