import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { createClient } from '@/lib/supabase/client';
import api from '@/lib/api';
import type { PipelineRun, PipelineStep } from '@/lib/types';

const supabase = createClient();

type PipelineConfig = {
  retention_days?: number;
  schedule_interval_hours?: number;
  is_paused?: boolean;
};

/**
 * Hook to fetch the global pipeline configuration.
 * Uses TanStack Query for caching and background refresh.
 */
export function useCurrentConfig() {
  return useQuery({
    queryKey: ['pipeline-config'],
    queryFn: async () => {
      const { data } = await api.get('/config/');
      return data;
    },
  });
}

/**
 * Hook to fetch the execution history.
 * Falls back to direct Supabase query if the orchestrator API is unreachable,
 * ensuring logs remain accessible even when the backend is offline.
 */
export function usePipelineRuns(limit = 20) {
  return useQuery({
    queryKey: ['pipeline-runs', limit],
    queryFn: async () => {
      try {
        const { data } = await api.get(`/runs/history?limit=${limit}`);
        return data as PipelineRun[];
      } catch {
        // Fallback: query Supabase directly so history/logs stay visible
        const { data, error } = await supabase
          .from('pipeline_runs')
          .select('*')
          .order('started_at', { ascending: false })
          .limit(limit);
        if (error) throw error;
        return (data || []) as PipelineRun[];
      }
    },
    refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      const runs = query.state.data as PipelineRun[] | undefined;
      const hasRunning = runs?.some((run) => ['running', 'pending', 'cancelling'].includes(run.status));
      return hasRunning ? 3000 : false;
    },
  });
}

/**
 * Hook to trigger a manual pipeline run.
 */
export function useTriggerRun() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (payload: { since_date?: string; user_id?: string } = {}) => {
      // Include user_id from current auth session
      const { data: { user } } = await supabase.auth.getUser();
      const fullPayload = { ...payload, user_id: user?.id };
      const { data } = await api.post('/runs/trigger', fullPayload);
      return data;
    },
    onSuccess: () => {
      // Invalidate both config and runs to ensure consistency
      queryClient.invalidateQueries({ queryKey: ['pipeline-runs'] });
      queryClient.invalidateQueries({ queryKey: ['pipeline-config'] });
    },
  });
}

function useRunActionMutation(action: 'cancel' | 'resume') {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (runId: string) => {
      const { data } = await api.post(`/runs/${runId}/${action}`);
      return data as PipelineRun;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-runs'] });
      queryClient.invalidateQueries({ queryKey: ['pipeline-config'] });
    },
  });
}

export function useCancelRun() {
  return useRunActionMutation('cancel');
}

export function useResumeRun() {
  return useRunActionMutation('resume');
}

export function useRerunStage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: { runId: string; stage: PipelineStep['step_name'] }) => {
      const { data } = await api.post(`/runs/${payload.runId}/rerun-stage`, { stage: payload.stage });
      return data as PipelineRun;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-runs'] });
      queryClient.invalidateQueries({ queryKey: ['pipeline-steps', variables.runId] });
    },
  });
}

/**
 * Hook to update the pipeline configuration with Optimistic UI updates.
 */
export function useUpdateConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (patch: PipelineConfig) => {
      const { data } = await api.patch('/config/', patch);
      return data as PipelineConfig;
    },
    onMutate: async (newConfig: PipelineConfig) => {
      // Cancel any outgoing refetches (so they don't overwrite our optimistic update)
      await queryClient.cancelQueries({ queryKey: ['pipeline-config'] });

      // Snapshot the previous value
      const previousConfig = queryClient.getQueryData<PipelineConfig>(['pipeline-config']);

      // Optimistically update to the new value
      queryClient.setQueryData<PipelineConfig>(['pipeline-config'], (old) => ({
        ...(old ?? {}),
        ...newConfig,
      }));

      // Return a context object with the snapshotted value
      return { previousConfig };
    },
    onError: (_err, _newConfig, context) => {
      // If the mutation fails, use the context returned from onMutate to roll back
      queryClient.setQueryData(['pipeline-config'], context?.previousConfig);
    },
    onSettled: () => {
      // Always refetch after error or success to keep in sync with server
      queryClient.invalidateQueries({ queryKey: ['pipeline-config'] });
    },
  });
}

/**
 * The "Realtime Magic": This hook establishes a Supabase Realtime channel
 * to listen for state changes in the database and push them to the UI instantly.
 */
export function useRealtimePipeline() {
  const queryClient = useQueryClient();

  useEffect(() => {
    // 1. Subscribe to pipeline_runs changes
      const runsChannel = supabase
      .channel('public:pipeline_runs')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'pipeline_runs' },
        () => {
          queryClient.invalidateQueries({ queryKey: ['pipeline-runs'] });
        }
      )
      .subscribe();

    // 2. Subscribe to pipeline_config changes
    const configChannel = supabase
      .channel('public:pipeline_config')
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'pipeline_config' },
        (payload) => {
          queryClient.setQueryData(['pipeline-config'], payload.new);
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(runsChannel);
      supabase.removeChannel(configChannel);
    };
  }, [queryClient]);
}
