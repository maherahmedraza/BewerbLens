import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { createClient } from '@/lib/supabase/client';
import api from '@/lib/api';

const supabase = createClient();

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
 */
export function usePipelineRuns(limit = 20) {
  return useQuery({
    queryKey: ['pipeline-runs', limit],
    queryFn: async () => {
      const { data } = await api.get(`/runs/history?limit=${limit}`);
      return data;
    },
    refetchOnWindowFocus: true,
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

/**
 * Hook to update the pipeline configuration with Optimistic UI updates.
 */
export function useUpdateConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (patch: any) => {
      const { data } = await api.patch('/config/', patch);
      return data;
    },
    onMutate: async (newConfig) => {
      // Cancel any outgoing refetches (so they don't overwrite our optimistic update)
      await queryClient.cancelQueries({ queryKey: ['pipeline-config'] });

      // Snapshot the previous value
      const previousConfig = queryClient.getQueryData(['pipeline-config']);

      // Optimistically update to the new value
      queryClient.setQueryData(['pipeline-config'], (old: any) => ({
        ...old,
        ...newConfig,
      }));

      // Return a context object with the snapshotted value
      return { previousConfig };
    },
    onError: (err, newConfig, context) => {
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
        (payload) => {
          const newRun = payload.new as any;
          // Update the localized query cache without a full network refetch
          queryClient.setQueryData(['pipeline-runs'], (old: any[] | undefined) => {
            if (!old) return [newRun];
            const index = old.findIndex((r: any) => r.id === newRun.id);
            if (index > -1) {
              const updated = [...old];
              updated[index] = newRun;
              return updated;
            }
            return [newRun, ...old];
          });
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
