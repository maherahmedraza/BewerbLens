"use client";

import { 
  PlayIcon, 
  CheckCircleIcon, 
  XCircleIcon, 
  ArrowPathIcon 
} from "@heroicons/react/24/solid";
import styles from "./PipelineMonitor.module.css";
import { usePipelineRuns, useTriggerRun, useRealtimePipeline } from "@/hooks/usePipeline";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { createClient } from "@/lib/supabase/client";

export default function PipelineMonitor() {
  const supabase = createClient();
  // 1. Live Realtime Subscription
  useRealtimePipeline();
  
  const queryClient = useQueryClient();

  // 2. Data Fetching
  const { data: runs, isLoading } = usePipelineRuns(1);
  const triggerMutation = useTriggerRun();
  
  const latestRun = runs?.[0];
  const isRunning = latestRun?.status === 'running' || latestRun?.status === 'pending' || triggerMutation.isPending;

  // 3. Fetch Steps for the latest run
  const { data: steps } = useQuery({
    queryKey: ['pipeline-steps', latestRun?.id],
    queryFn: async () => {
      if (!latestRun?.id) return [];
      const { data } = await supabase
        .from('pipeline_run_steps')
        .select('*')
        .eq('run_id', latestRun.id);
      return data || [];
    },
    enabled: !!latestRun?.id,
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
  }, [latestRun?.id]);

  const handleSync = async () => {
    try {
      await triggerMutation.mutateAsync({});
    } catch (error) {
      console.error("Failed to trigger manual sync:", error);
    }
  };

  const getStageStatus = (stage: string) => {
    if (!latestRun) return "pending";
    if (latestRun.status === 'success') return "success";
    if (latestRun.status === 'failed') return "error";
    
    const step = steps?.find((s: any) => s.step_name === stage);
    if (!step) return "pending";
    
    if (step.status === 'success') return "success";
    if (step.status === 'running') return "active";
    if (step.status === 'failed') return "error";
    return "pending";
  };

  const calculateProgress = () => {
    if (!latestRun) return 0;
    if (latestRun.status === 'success') return 100;
    if (latestRun.status === 'failed') return 100;
    
    if (!steps || steps.length === 0) return 0;
    
    // Stages: Ingestion (33%), Analysis (33%), Persistence (34%)
    let totalProgress = 0;
    const stageWeights: Record<string, number> = {
      'ingestion': 33,
      'analysis': 33,
      'persistence': 34
    };

    steps.forEach((step: any) => {
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
            {isRunning ? `Syncing (${progress}%)` : "System Idle"}
          </span>
        </div>
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
        />
        <StageItem 
          title="Analysis" 
          status={getStageStatus("analysis")} 
          description="Gemini LLM Processing" 
        />
        <StageItem 
          title="Persistence" 
          status={getStageStatus("persistence")} 
          description="Supabase Synchronization" 
        />
      </div>
    </div>
  );
}

function StageItem({ title, status, description }: { title: string; status: string; description: string }) {
  return (
    <div className={`${styles.stage} ${styles[status]}`}>
      <div className={styles.stageIcon}>
        {status === "success" && <CheckCircleIcon className={styles.check} />}
        {status === "active" && <ArrowPathIcon className={styles.spin} />}
        {status === "error" && <XCircleIcon className={styles.errorIcon} />}
        {status === "pending" && <div className={styles.dot} />}
      </div>
      <div className={styles.stageContent}>
        <h4 className={styles.stageTitle}>{title}</h4>
        <p className={styles.stageDesc}>{description}</p>
      </div>
    </div>
  );
}
