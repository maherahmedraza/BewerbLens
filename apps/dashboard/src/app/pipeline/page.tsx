"use client";

import { Suspense, useState } from "react";
import PipelineMonitor from "./components/PipelineMonitor";
import ExecutionHistory from "./components/ExecutionHistory";

import LogDetailDrawer from "./components/LogDetailDrawer";
import styles from "./page.module.css";
import type { PipelineRun } from "@/lib/types";

export default function PipelinePage() {
  const [selectedRun, setSelectedRun] = useState<PipelineRun | null>(null);

  const handleOpenLogs = (run: PipelineRun) => {
    setSelectedRun(run);
  };

  const handleCloseLogs = () => {
    setSelectedRun(null);
  };

  return (
    <div className={styles.container}>
      <header className={styles.pageHeader}>
        <div className={styles.headerInfo}>
          <h1 className="heading">Pipeline Orchestration</h1>
          <p className="subheading">
            Monitor real-time execution, inspect stage progress, and audit historical runs.
          </p>
        </div>
      </header>

      <div className={styles.noticeCard}>
        <h2 className={styles.noticeTitle}>Configuration lives in Workspace Settings</h2>
        <p className={styles.noticeText}>
          Sync interval, fairness caps, retention, Gmail connection, and notification settings are all managed from one place now.
        </p>
        <a href="/settings#sync-controls" className={styles.shortcutButton}>
          Open Settings
        </a>
      </div>

      <div className={styles.mainContent}>
        <Suspense fallback={<div className={styles.skeleton}>Loading Monitor...</div>}>
          <PipelineMonitor onViewLogs={handleOpenLogs} />
        </Suspense>

        <section className={styles.historySection}>
          <h2 className={styles.sectionTitle}>Execution History</h2>
          <Suspense fallback={<div className={styles.skeleton}>Loading History...</div>}>
            <ExecutionHistory onViewLogs={handleOpenLogs} />
          </Suspense>
        </section>
      </div>

      {/* Log Detail Overlay (Drawer) */}
      {selectedRun && (
        <LogDetailDrawer 
          run={selectedRun} 
          onClose={handleCloseLogs} 
        />
      )}
    </div>
  );
}
