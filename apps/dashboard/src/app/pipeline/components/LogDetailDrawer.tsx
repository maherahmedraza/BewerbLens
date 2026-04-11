"use client";

import { XMarkIcon, CommandLineIcon, ClipboardIcon } from "@heroicons/react/24/outline";
import styles from "./LogDetailDrawer.module.css";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase";

interface LogDetailDrawerProps {
  onClose: () => void;
  run: any;
}

export default function LogDetailDrawer({ onClose, run }: LogDetailDrawerProps) {
  const queryClient = useQueryClient();
  const logEndRef = useRef<HTMLDivElement>(null);
  
  // 1. Fetch incremental logs
  const { data: incrementalLogs } = useQuery({
    queryKey: ['run-logs', run?.id],
    queryFn: async () => {
      if (!run?.id) return [];
      const { data } = await supabase
        .from('pipeline_run_logs')
        .select('*')
        .eq('run_id', run.id)
        .order('created_at', { ascending: true });
      return data || [];
    },
    enabled: !!run?.id,
  });

  // 2. Realtime subscription for live tailing
  useEffect(() => {
    if (!run?.id || run.status !== 'running') return;

    const channel = supabase.channel(`logs-${run.id}`)
      .on('postgres_changes', {
        event: 'INSERT',
        schema: 'public',
        table: 'pipeline_run_logs',
        filter: `run_id=eq.${run.id}`
      }, (payload) => {
        // Optimistic update or just invalidate
        queryClient.setQueryData(['run-logs', run.id], (old: any) => {
          return [...(old || []), payload.new];
        });
      })
      .subscribe();

    return () => { supabase.removeChannel(channel); };
  }, [run?.id, run?.status]);

  // 3. Auto-scroll to bottom
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [incrementalLogs]);

  const copyToClipboard = () => {
    const text = incrementalLogs?.map((l: any) => `[${l.level}] ${l.message}`).join('\n') || run?.logs_summary;
    if (text) {
      navigator.clipboard.writeText(text);
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
            <button className={styles.copyButton} onClick={copyToClipboard}>
              <ClipboardIcon className={styles.copyIcon} />
              Copy
            </button>
          </div>
          <div className={styles.logArea}>
            {incrementalLogs && incrementalLogs.length > 0 ? (
              incrementalLogs.map((log: any) => (
                <div key={log.id} className={styles.logLine}>
                  <span className={styles.logTime}>{new Date(log.created_at).toLocaleTimeString()}</span>
                  <span className={`${styles.logLevel} ${styles[log.level.toLowerCase()]}`}>
                    [{log.level}]
                  </span>
                  <span className={styles.logMsg}>{log.message}</span>
                </div>
              ))
            ) : run?.logs_summary ? (
              <pre>{run.logs_summary}</pre>
            ) : (
              <div className={styles.emptyLogs}>Waiting for logs...</div>
            )}
            <div ref={logEndRef} />
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
