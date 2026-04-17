"use client";

import { 
  CheckCircleIcon, 
  XCircleIcon, 
  ClockIcon, 
  InformationCircleIcon,
  PauseIcon,
  PlayIcon,
} from "@heroicons/react/24/outline";
import styles from "./ExecutionHistory.module.css";
import { useCancelRun, usePipelineRuns, useResumeRun } from "@/hooks/usePipeline";
import { formatDistanceToNow } from "date-fns";
import type { PipelineRun } from "@/lib/types";

interface ExecutionHistoryProps {
  onViewLogs: (run: PipelineRun) => void;
}

export default function ExecutionHistory({ onViewLogs }: ExecutionHistoryProps) {
  const { data: runs, isLoading, error } = usePipelineRuns(20);
  const cancelMutation = useCancelRun();
  const resumeMutation = useResumeRun();

  if (isLoading) {
    return <div className={styles.loading}>Loading history...</div>;
  }

  if (error) {
    return <div className={styles.errorState}>Failed to load execution history.</div>;
  }

  const formatDuration = (seconds?: number) => {
    if (!seconds) return "-";
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    return `${(seconds / 60).toFixed(1)}m`;
  };

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Run ID</th>
            <th>Status</th>
            <th>Type</th>
            <th>Started At</th>
            <th>Duration</th>
            <th>Results</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(runs || []).map((run: PipelineRun) => (
            <tr key={run.id || run.run_id}>
              <td className={styles.runId}>{run.run_id}</td>
              <td>
                <span className={`${styles.badge} ${styles[run.status] || styles.pending}`}>
                  {run.status === "success" ? (
                    <CheckCircleIcon className={styles.badgeIcon} />
                  ) : run.status === "failed" ? (
                    <XCircleIcon className={styles.badgeIcon} />
                  ) : (
                    <ClockIcon className={styles.badgeIcon} />
                  )}
                  {(run.status || "pending").toUpperCase()}
                </span>
              </td>
              <td className={styles.triggerType}>{run.triggered_by}</td>
              <td className={styles.time}>
                {run.started_at ? formatDistanceToNow(new Date(run.started_at), { addSuffix: true }) : "-"}
              </td>
              <td className={styles.duration}>
                {formatDuration(run.duration_ms ? run.duration_ms / 1000 : undefined)}
              </td>
              <td>
                {run.status === "success" ? (
                  <div className={styles.stats}>
                    <span className={styles.added} title="New Applications">
                      +{run.summary_stats?.added || 0}
                    </span>
                    <span className={styles.updated} title="Updated Statuses">
                      ~{run.summary_stats?.updated || 0}
                    </span>
                  </div>
                ) : run.status === "failed" ? (
                  <span className={styles.error} title={run.error_message}>
                    {run.error_message?.substring(0, 20) || "Error"}...
                  </span>
                ) : (
                  <span className={styles.pending}>Processing...</span>
                )}
              </td>
              <td>
                <button 
                  className={styles.viewLogs}
                  onClick={() => onViewLogs(run)}
                  title="View Details & Logs"
                >
                  <InformationCircleIcon className={styles.infoIcon} />
                </button>
                {(run.status === "running" || run.status === "pending") && (
                  <button
                    className={styles.inlineAction}
                    onClick={() => cancelMutation.mutate(run.id)}
                    title="Stop run"
                  >
                    <PauseIcon className={styles.infoIcon} />
                  </button>
                )}
                {(run.status === "failed" || run.status === "cancelled") && (
                  <button
                    className={styles.inlineAction}
                    onClick={() => resumeMutation.mutate(run.id)}
                    title="Resume run"
                  >
                    <PlayIcon className={styles.infoIcon} />
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
