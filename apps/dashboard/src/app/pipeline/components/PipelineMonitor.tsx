"use client";

import { 
  PlayIcon, 
  PauseIcon,
  CheckCircleIcon, 
  XCircleIcon, 
  ArrowPathIcon,
  DocumentTextIcon,
} from "@heroicons/react/24/solid";
import styles from "./PipelineMonitor.module.css";
import { useCancelRun, usePipelineRuns, useRealtimePipeline, useResumeRun, useRerunStage, useTriggerRun } from "@/hooks/usePipeline";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { createClient } from "@/lib/supabase/client";
import type { PipelineRun, PipelineStep } from "@/lib/types";

const supabase = createClient();

export default function PipelineMonitor({ onViewLogs }: { onViewLogs?: (run: PipelineRun) => void }) {
  // 1. Live Realtime Subscription
  useRealtimePipeline();
  
  const queryClient = useQueryClient();

  // 2. Data Fetching
  const { data: runs } = usePipelineRuns(1);
  const triggerMutation = useTriggerRun();
  const cancelMutation = useCancelRun();
  const resumeMutation = useResumeRun();
  const rerunStageMutation = useRerunStage();
  
  const latestRun = runs?.[0];
  const isRunning =
    latestRun?.status === 'running' ||
    latestRun?.status === 'pending' ||
    latestRun?.status === 'cancelling' ||
    triggerMutation.isPending ||
    cancelMutation.isPending;

  // 3. Fetch Steps for the latest run (polls every 2s while running)
  const { data: steps } = useQuery({
    queryKey: ['pipeline-steps', latestRun?.id],
    queryFn: async () => {
      if (!latestRun?.id) return [];
      const { data } = await supabase
        .from('pipeline_run_steps')
        .select('*')
        .eq('run_id', latestRun.id);
      return (data || []) as PipelineStep[];
    },
    enabled: !!latestRun?.id,
    refetchInterval: isRunning ? 2000 : false,
  });

  // ── Sync with Realtime Steps ──────────────────────────
  useEffect(() => {
    if (!latestRun?.id) return;
    const channel = supabase.channel(`steps-${latestRun.id}`)
      .on('postgres_changes', { 
        event: '*', 
        schema: 'public', 
        table: 'pipeline_run_steps',
        filter: `run_id=eq.${latestRun.id}`
      }, () => {
        // Invalidate the steps query to refetch
        queryClient.invalidateQueries({ queryKey: ['pipeline-steps', latestRun.id] });
      })
      .subscribe();
    return () => { supabase.removeChannel(channel); };
  }, [latestRun?.id, queryClient]);

  const handleSync = async () => {
    try {
      await triggerMutation.mutateAsync({});
    } catch (error) {
      console.error("Failed to trigger manual sync:", error);
    }
  };

  const handleCancel = async () => {
    if (!latestRun?.id) return;
    await cancelMutation.mutateAsync(latestRun.id);
  };

  const handleResume = async () => {
    if (!latestRun?.id) return;
    await resumeMutation.mutateAsync(latestRun.id);
  };

  const handleRerunStage = async (stage: PipelineStep["step_name"]) => {
    if (!latestRun?.id) return;
    await rerunStageMutation.mutateAsync({ runId: latestRun.id, stage });
  };

  const getStageStatus = (stage: string) => {
    if (!latestRun) return "pending";
    if (latestRun.status === 'success') return "success";
    if (latestRun.status === 'cancelled') return "cancelled";
    
    // Use per-step data when available (even for failed runs)
    const step = steps?.find((value) => value.step_name === stage);
    if (step) {
      if (step.status === 'success') return "success";
      if (step.status === 'running') return "active";
      if (step.status === 'failed') return "error";
      if (step.status === 'skipped') return "skipped";
    }
    
    return "pending";
  };

  const calculateProgress = () => {
    if (!latestRun) return 0;
    if (latestRun.status === 'success') return 100;
    if (latestRun.status === 'failed') return 100;
    if (latestRun.status === 'cancelled') return 100;
    
    if (!steps || steps.length === 0) return 0;
    
    // Stages: Ingestion (33%), Analysis (33%), Persistence (34%)
    let totalProgress = 0;
    const stageWeights: Record<string, number> = {
      'ingestion': 33,
      'analysis': 33,
      'persistence': 34
    };

    steps.forEach((step) => {
      const weight = stageWeights[step.step_name] || 0;
      if (step.status === 'success') {
        totalProgress += weight;
      } else if (step.status === 'running') {
        totalProgress += (weight * (step.progress_pct || 0)) / 100;
      }
    });

    return Math.min(Math.round(totalProgress), 99);
  };

  const progress = calculateProgress();

  return (
    <div className={styles.card}>
      <div className={styles.statusHeader}>
        <div className={styles.indicatorContainer}>
          <div className={`${styles.pulse} ${isRunning ? styles.active : ""}`} />
          <span className={styles.statusText}>
            {isRunning ? `Syncing (${progress}%)` 
              : latestRun?.status === 'cancelled' ? "Last Run Cancelled"
              : latestRun?.status === 'failed' ? "Last Run Failed" 
              : "System Idle"}
          </span>
        </div>
        <div className={styles.buttonGroup}>
          <button 
            onClick={handleSync} 
            disabled={isRunning || triggerMutation.isPending}
            className={`${styles.syncButton} ${isRunning ? styles.loading : ""}`}
          >
            {isRunning || triggerMutation.isPending ? (
              <ArrowPathIcon className={styles.spinIcon} />
            ) : (
              <PlayIcon className={styles.icon} />
            )}
            {isRunning || triggerMutation.isPending ? "Syncing..." : "Manual Sync"}
          </button>

          {latestRun && (latestRun.status === 'running' || latestRun.status === 'pending') && (
            <button
              onClick={handleCancel}
              disabled={cancelMutation.isPending}
              className={styles.secondaryButton}
            >
              <PauseIcon className={styles.icon} />
              {cancelMutation.isPending ? "Stopping..." : "Stop Run"}
            </button>
          )}

          {latestRun && ['failed', 'cancelled'].includes(latestRun.status) && (
            <button
              onClick={handleResume}
              disabled={resumeMutation.isPending}
              className={styles.secondaryButton}
            >
              <PlayIcon className={styles.icon} />
              {resumeMutation.isPending ? "Resuming..." : "Resume Run"}
            </button>
          )}

          {latestRun && onViewLogs && (
            <button
              onClick={() => onViewLogs(latestRun)}
              className={styles.secondaryButton}
            >
              <DocumentTextIcon className={styles.icon} />
              View Logs
            </button>
          )}
        </div>
      </div>

      <div className={styles.progressContainer}>
        <div className={styles.progressTrack}>
          <div 
            className={styles.pBar} 
            style={{ 
              width: `${progress}%`,
              opacity: isRunning ? 1 : 0
            }} 
          />
        </div>
      </div>

      <div className={styles.stagesGrid}>
        <StageItem 
          title="Ingestion" 
          status={getStageStatus("ingestion")} 
          description="Fetching Gmail data"
          step={steps?.find((value) => value.step_name === 'ingestion')}
          onRerun={() => handleRerunStage('ingestion')}
          canRerun={Boolean(latestRun?.id) && !isRunning}
        />
        <StageItem 
          title="Analysis" 
          status={getStageStatus("analysis")} 
          description="Gemini LLM Processing"
          step={steps?.find((value) => value.step_name === 'analysis')}
          onRerun={() => handleRerunStage('analysis')}
          canRerun={Boolean(latestRun?.id) && !isRunning}
        />
        <StageItem 
          title="Persistence" 
          status={getStageStatus("persistence")} 
          description="Supabase Synchronization"
          step={steps?.find((value) => value.step_name === 'persistence')}
          onRerun={() => handleRerunStage('persistence')}
          canRerun={Boolean(latestRun?.id) && !isRunning}
        />
      </div>
    </div>
  );
}

function StageItem({
  title,
  status,
  description,
  step,
  onRerun,
  canRerun,
}: {
  title: string;
  status: string;
  description: string;
  step?: PipelineStep;
  onRerun: () => void;
  canRerun: boolean;
}) {
  const progressPct = step?.progress_pct || 0;
  const message = step?.message;

  return (
    <div className={`${styles.stage} ${styles[status]}`}>
      <div className={styles.stageIcon}>
        {status === "success" && <CheckCircleIcon className={styles.check} />}
        {status === "active" && <ArrowPathIcon className={styles.spin} />}
        {status === "error" && <XCircleIcon className={styles.errorIcon} />}
        {status === "cancelled" && <PauseIcon className={styles.errorIcon} />}
        {status === "pending" && <div className={styles.dot} />}
      </div>
      <div className={styles.stageContent}>
        <h4 className={styles.stageTitle}>
          {title}
          {status === "active" && <span className={styles.stagePct}>{progressPct}%</span>}
          {status === "success" && <span className={styles.stagePct}>100%</span>}
        </h4>
        <p className={styles.stageDesc}>
          {status === "error" && message ? message 
            : status === "cancelled" && message ? message
            : status === "active" && message ? message 
            : description}
        </p>
        {status === "active" && (
          <div className={styles.stageProgressTrack}>
            <div className={styles.stageProgressBar} style={{ width: `${progressPct}%` }} />
          </div>
        )}
        {canRerun && (
          <button className={styles.rerunButton} onClick={onRerun}>
            Rerun from {title}
          </button>
        )}
      </div>
    </div>
  );
}
