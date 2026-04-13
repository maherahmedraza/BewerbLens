"use client";

import { XMarkIcon, CommandLineIcon, ClipboardIcon } from "@heroicons/react/24/outline";
import styles from "./LogDetailDrawer.module.css";
import EnhancedLogViewer from "@/components/EnhancedLogViewer";

interface LogDetailDrawerProps {
  onClose: () => void;
  run: any;
}

export default function LogDetailDrawer({ onClose, run }: LogDetailDrawerProps) {
  const copyToClipboard = () => {
    // Basic fallback depending on EnhancedLogViewer's internal implementation
    // The EnhancedLogViewer provides its own export button anyway
    if (run?.logs_summary) {
      navigator.clipboard.writeText(run.logs_summary);
    }
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.drawer} onClick={(e) => e.stopPropagation()}>
        <header className={styles.header}>
          <div className={styles.headerTitle}>
            <CommandLineIcon className={styles.headerIcon} />
            <div>
              <h3>Execution Logs</h3>
              <p>Run ID: {run?.run_id}</p>
            </div>
          </div>
          <button onClick={onClose} className={styles.closeButton}>
            <XMarkIcon className={styles.closeIcon} />
          </button>
        </header>

        <div className={styles.metaGrid}>
          <div className={styles.metaItem}>
            <span className={styles.metaLabel}>Status</span>
            <span className={`${styles.metaValue} ${styles[run?.status || 'pending']}`}>
              {(run?.status || 'pending').toUpperCase()}
            </span>
          </div>
          <div className={styles.metaItem}>
            <span className={styles.metaLabel}>Duration</span>
            <span className={styles.metaValue}>
              {run?.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : "-"}
            </span>
          </div>
          <div className={styles.metaItem}>
            <span className={styles.metaLabel}>Added</span>
            <span className={styles.metaValue} style={{ color: "var(--accent-green)" }}>
              {run?.summary_stats?.added || 0}
            </span>
          </div>
          <div className={styles.metaItem}>
            <span className={styles.metaLabel}>Updated</span>
            <span className={styles.metaValue} style={{ color: "var(--accent-blue)" }}>
              {run?.summary_stats?.updated || 0}
            </span>
          </div>
          <div className={styles.metaItem}>
            <span className={styles.metaLabel}>Trigger</span>
            <span className={styles.metaValue}>{(run?.triggered_by || "manual").toUpperCase()}</span>
          </div>
        </div>

        <div className={styles.logContainer}>
          <div className={styles.logHeader}>
            <span>Real-time Log Stream</span>
          </div>
          <div style={{ padding: '16px', background: '#1a1a1a', borderRadius: '8px', border: '1px solid #333' }}>
            {run?.id ? (
              <EnhancedLogViewer runId={run.id} isLive={run.status === 'running'} />
            ) : (
              <div className={styles.emptyLogs}>Waiting for logs...</div>
            )}
          </div>
        </div>

        {run?.error_message && (
          <div className={styles.errorBanner}>
            <h4>Error Detail</h4>
            <p>{run.error_message}</p>
          </div>
        )}
      </div>
    </div>
  );
}
