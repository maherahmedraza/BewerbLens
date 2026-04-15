// ╔══════════════════════════════════════════════════════════════╗
// ║  Enhanced Log Viewer — High-Performance UI Component        ║
// ║                                                             ║
// ║  Features:                                                  ║
// ║  • Virtual scrolling for 10,000+ log lines                  ║
// ║  • Efficient real-time updates via Supabase Realtime        ║
// ║  • Smart pagination for historical logs                     ║
// ║  • Search and filtering                                     ║
// ╚══════════════════════════════════════════════════════════════╝

"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createClient } from "@/lib/supabase/client";
import { List } from 'react-window';
import { AutoSizer } from 'react-virtualized-auto-sizer';

interface LogEntry {
  id: string;
  level: string;
  message: string;
  step_name: string;
  created_at: string;
}

interface EnhancedLogViewerProps {
  runId: string;
  isLive?: boolean;  // true for currently running, false for historical
}

export default function EnhancedLogViewer({ runId, isLive = false }: EnhancedLogViewerProps) {
  const supabase = createClient();
  const queryClient = useQueryClient();
  // @ts-ignore
  const listRef = useRef<any>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [levelFilter, setLevelFilter] = useState<string | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // ── Strategy 1: Paginated Loading for Historical Runs ─────────
  const PAGE_SIZE = 100;
  const [currentPage, setCurrentPage] = useState(0);

  const { data: logs, isLoading } = useQuery({
    queryKey: ['logs', runId, currentPage],
    queryFn: async () => {
      const start = currentPage * PAGE_SIZE;
      const end = start + PAGE_SIZE - 1;

      const { data, error } = await supabase
        .from('pipeline_run_logs')
        .select('*')
        .eq('run_id', runId)
        .order('created_at', { ascending: true })
        .range(start, end);

      if (error) throw error;
      return data as LogEntry[];
    },
    enabled: !!runId && !isLive,
    staleTime: Infinity,  // Historical logs never change
  });

  // ── Strategy 2: Real-Time Streaming for Live Runs ─────────────
  const { data: liveLogs } = useQuery({
    queryKey: ['live-logs', runId],
    queryFn: async () => {
      const { data } = await supabase
        .from('pipeline_run_logs')
        .select('*')
        .eq('run_id', runId)
        .order('created_at', { ascending: true });
      return data as LogEntry[];
    },
    enabled: !!runId && isLive,
    refetchInterval: isLive ? 2000 : false,  // Poll every 2s for live runs
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
        (payload) => {
          // Optimistically append new log
          queryClient.setQueryData(['live-logs', runId], (old: any) => {
            const newLogs = [...(old || []), payload.new as LogEntry];
            
            // Auto-scroll to bottom if enabled
            if (autoScroll && listRef.current) {
              setTimeout(() => {
                listRef.current?.scrollToItem(newLogs.length - 1, 'end');
              }, 100);
            }
            
            return newLogs;
          });
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [isLive, runId, queryClient, autoScroll]);

  // ── Filtering and Search ───────────────────────────────────────
  const allLogs = isLive ? liveLogs : logs;

  const filteredLogs = useMemo(() => {
    if (!allLogs) return [];

    return allLogs.filter((log) => {
      // Level filter
      if (levelFilter && log.level !== levelFilter) return false;

      // Search filter
      if (searchQuery && !log.message.toLowerCase().includes(searchQuery.toLowerCase())) {
        return false;
      }

      return true;
    });
  }, [allLogs, levelFilter, searchQuery]);

  // ── Virtual List Row Renderer ──────────────────────────────────
  const getItemSize = (index: number) => {
    const log = filteredLogs[index];
    const lineCount = Math.ceil(log.message.length / 80);
    return Math.max(lineCount * 20 + 10, 30);  // Minimum 30px per row
  };

  const LogRow = ({ index, style }: { index: number; style: any }) => {
    const log = filteredLogs[index];
    
    const levelColors: Record<string, string> = {
      INFO: '#3b82f6',
      WARNING: '#f59e0b',
      ERROR: '#ef4444',
      DEBUG: '#6b7280',
    };

    return (
      <div style={style} className="log-row">
        <span className="log-timestamp">
          {new Date(log.created_at).toLocaleTimeString()}
        </span>
        <span
          className="log-level"
          style={{ color: levelColors[log.level] || '#fff' }}
        >
          [{log.level}]
        </span>
        <span className="log-step">[{log.step_name}]</span>
        <span className="log-message">{log.message}</span>
      </div>
    );
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

      {/* Virtual Scrolling Log Area */}
      <div className="log-area" style={{ height: '500px', width: '100%' }}>
        {isLoading ? (
          <div className="loading" style={{ padding: 16 }}>Loading logs...</div>
        ) : filteredLogs.length === 0 ? (
          <div className="empty" style={{ padding: 16 }}>No logs found</div>
        ) : (
          <>
            {/* @ts-ignore */}
            <AutoSizer>
              {({ height, width }: { height: number; width: number }) => {
                const UntypedList = List as any;
                return (
                  <UntypedList
                    ref={listRef as any}
                    height={height}
                    width={width}
                    itemCount={filteredLogs.length}
                    itemSize={getItemSize}
                  >
                    {LogRow}
                  </UntypedList>
                );
              }}
            </AutoSizer>
          </>
        )}
      </div>

      {/* Pagination for Historical Logs */}
      {!isLive && (
        <div className="log-pagination">
          <button
            onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
            disabled={currentPage === 0}
          >
            Previous
          </button>
          <span>Page {currentPage + 1}</span>
          <button
            onClick={() => setCurrentPage((p) => p + 1)}
            disabled={!logs || logs.length < PAGE_SIZE}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}


// ╔══════════════════════════════════════════════════════════════╗
// ║  Log Viewer CSS                                             ║
// ╚══════════════════════════════════════════════════════════════╝

/*
.log-viewer-container {
  display: flex;
  flex-direction: column;
  background: #1a1a1a;
  border-radius: 8px;
  overflow: hidden;
}

.log-toolbar {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: #2a2a2a;
  border-bottom: 1px solid #3a3a3a;
}

.log-search {
  flex: 1;
  padding: 8px 12px;
  background: #1a1a1a;
  border: 1px solid #3a3a3a;
  color: #fff;
  border-radius: 4px;
}

.log-filter {
  padding: 8px 12px;
  background: #1a1a1a;
  border: 1px solid #3a3a3a;
  color: #fff;
  border-radius: 4px;
}

.log-area {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 13px;
  background: #0d1117;
}

.log-row {
  display: flex;
  gap: 8px;
  padding: 4px 12px;
  border-bottom: 1px solid #21262d;
  white-space: pre-wrap;
  word-break: break-word;
}

.log-timestamp {
  color: #6b7280;
  min-width: 80px;
}

.log-level {
  min-width: 60px;
  font-weight: 600;
}

.log-step {
  color: #8b949e;
  min-width: 100px;
}

.log-message {
  flex: 1;
  color: #c9d1d9;
}

.log-pagination {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: #2a2a2a;
  border-top: 1px solid #3a3a3a;
  justify-content: center;
}
*/
