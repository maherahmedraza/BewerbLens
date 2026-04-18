// ╔══════════════════════════════════════════════════════════════╗
// ║  Enhanced Log Viewer — High-Performance UI Component        ║
// ║                                                             ║
// ║  Features:                                                  ║
// ║  • Scrollable log display with auto-scroll                  ║
// ║  • Efficient real-time updates via polling + Realtime        ║
// ║  • Search and filtering                                     ║
// ╚══════════════════════════════════════════════════════════════╝

"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createClient } from "@/lib/supabase/client";

interface LogEntry {
  id: string;
  level: string;
  message: string;
  step_name: string;
  created_at: string;
}

interface EnhancedLogViewerProps {
  runId: string;
  isLive?: boolean;
}

export default function EnhancedLogViewer({ runId, isLive = false }: EnhancedLogViewerProps) {
  const supabase = createClient();
  const queryClient = useQueryClient();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [levelFilter, setLevelFilter] = useState<string | null>(null);
  const [stageFilter, setStageFilter] = useState<string | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // ── Fetch logs (works for both live and historical) ────────────
  const { data: logs, isLoading, error: fetchError } = useQuery({
    queryKey: ['logs', runId],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('pipeline_run_logs')
        .select('*')
        .eq('run_id', runId)
        .order('created_at', { ascending: true })
        .limit(1000);

      if (error) throw error;
      return data as LogEntry[];
    },
    enabled: !!runId,
    refetchInterval: isLive ? 2000 : false,
    staleTime: isLive ? 0 : Infinity,
  });

  // ── Real-Time Subscription (Live Runs Only) ────────────────────
  useEffect(() => {
    if (!isLive || !runId) return;

    const channel = supabase
      .channel(`live-logs-${runId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'pipeline_run_logs',
          filter: `run_id=eq.${runId}`,
        },
        () => {
          queryClient.invalidateQueries({ queryKey: ['logs', runId] });
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [isLive, runId, queryClient, supabase]);

  // ── Filtering and Search ───────────────────────────────────────
  const filteredLogs = useMemo(() => {
    if (!logs) return [];

    return logs.filter((log) => {
      if (levelFilter && log.level !== levelFilter) return false;
      if (stageFilter && log.step_name !== stageFilter) return false;
      if (searchQuery && !log.message.toLowerCase().includes(searchQuery.toLowerCase())) {
        return false;
      }
      return true;
    });
  }, [logs, levelFilter, stageFilter, searchQuery]);

  // ── Derive available stages for the filter ─────────────────────
  const availableStages = useMemo(() => {
    if (!logs) return [];
    return [...new Set(logs.map((l) => l.step_name).filter(Boolean))];
  }, [logs]);

  // ── Auto-scroll to bottom when new logs arrive ─────────────────
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [filteredLogs, autoScroll]);

  // ── Level Colors ───────────────────────────────────────────────
  const levelColors: Record<string, string> = {
    INFO: '#3b82f6',
    WARNING: '#f59e0b',
    ERROR: '#ef4444',
    DEBUG: '#6b7280',
    SUCCESS: '#10b981',
  };

  // ── Export Logs ────────────────────────────────────────────────
  const exportLogs = () => {
    const text = filteredLogs
      .map((l) => `[${l.level}] [${l.step_name}] ${l.message}`)
      .join('\n');

    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `logs-${runId}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // ── Render ─────────────────────────────────────────────────────
  if (fetchError) {
    return (
      <div className="log-viewer-container">
        <div style={{ padding: 16, color: '#ef4444' }}>
          Failed to load logs: {fetchError instanceof Error ? fetchError.message : 'Unknown error'}. 
          Check your authentication and Supabase connection.
        </div>
      </div>
    );
  }

  return (
    <div className="log-viewer-container">
      {/* Toolbar */}
      <div className="log-toolbar">
        <input
          type="text"
          placeholder="Search logs..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="log-search"
        />

        <select
          value={levelFilter || 'ALL'}
          onChange={(e) => setLevelFilter(e.target.value === 'ALL' ? null : e.target.value)}
          className="log-filter"
        >
          <option value="ALL">All Levels</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
          <option value="DEBUG">DEBUG</option>
        </select>

        {availableStages.length > 1 && (
          <select
            value={stageFilter || 'ALL'}
            onChange={(e) => setStageFilter(e.target.value === 'ALL' ? null : e.target.value)}
            className="log-filter"
          >
            <option value="ALL">All Stages</option>
            {availableStages.map((stage) => (
              <option key={stage} value={stage}>{stage}</option>
            ))}
          </select>
        )}

        <label className="auto-scroll-toggle">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
          />
          Auto-scroll
        </label>

        <button onClick={exportLogs} className="export-button">
          Export Logs
        </button>

        <span className="log-count">
          {filteredLogs.length} logs
        </span>
      </div>

      {/* Scrollable Log Area */}
      <div
        ref={scrollRef}
        className="log-area"
        style={{
          height: '400px',
          overflowY: 'auto',
          fontFamily: 'monospace',
          fontSize: '12px',
          lineHeight: '1.6',
          padding: '8px 12px',
        }}
      >
        {isLoading ? (
          <div style={{ padding: 16, color: '#888' }}>Loading logs...</div>
        ) : filteredLogs.length === 0 ? (
          <div style={{ padding: 16, color: '#888' }}>No logs found</div>
        ) : (
          filteredLogs.map((log) => (
            <div key={log.id} className="log-row" style={{ display: 'flex', gap: '8px', padding: '2px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
              <span className="log-timestamp" style={{ color: '#666', whiteSpace: 'nowrap', minWidth: '70px' }}>
                {new Date(log.created_at).toLocaleTimeString()}
              </span>
              <span
                className="log-level"
                style={{ color: levelColors[log.level] || '#fff', fontWeight: 600, whiteSpace: 'nowrap', minWidth: '60px' }}
              >
                [{log.level}]
              </span>
              <span className="log-step" style={{ color: '#888', whiteSpace: 'nowrap', minWidth: '90px' }}>
                [{log.step_name}]
              </span>
              <span className="log-message" style={{ color: '#e0e0e0', wordBreak: 'break-word' }}>
                {log.message}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
