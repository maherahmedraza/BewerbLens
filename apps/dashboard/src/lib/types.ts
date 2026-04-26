export interface Application {
  id: string;
  thread_id: string;
  company_name: string;
  job_title: string;
  platform: string;
  status: string;
  confidence: number;
  email_subject: string;
  email_from: string;
  date_applied: string;
  last_updated: string;
  notes: string;
  gmail_link: string;
  job_listing_url: string;
  location: string;
  job_location: string;
  job_city: string;
  job_country: string;
  work_mode: "Remote" | "Hybrid" | "On-site" | "Unknown";
  salary_range: string;
  source_email_id: string;
  status_history: StatusHistoryEntry[];
  email_count: number;
  is_active: boolean;
}

export interface StatusHistoryEntry {
  status: string;
  timestamp: string;
  changed_at?: string;
  date?: string;
  email_id?: string;
  email_subject: string;
  source_email_id: string;
  confidence: number;
}

export interface ApplicationStats {
  total_applications: number;
  applied: number;
  rejected: number;
  positive_response: number;
  interview: number;
  offer: number;
  response_rate_pct: number;
  success_rate_pct: number;
}

export interface MonthlyApplication {
  month: string;
  total: number;
  applied: number;
  rejected: number;
  positive: number;
}

export interface PlatformBreakdown {
  platform: string;
  count: number;
  rejected: number;
  positive: number;
}

export interface TopCompany {
  company_name: string;
  applications: number;
  rejected: number;
  positive: number;
  first_applied: string;
}

export interface LocationBreakdown {
  location: string;
  count: number;
  pct: number;
}

export interface ConversionFunnel {
  stage: string;
  count: number;
}

export interface SankeyFlowNode {
  name: string;
  status: string;
  depth: number;
  count: number;
}

export interface SankeyFlowLink {
  source: number;
  target: number;
  value: number;
}

export interface StatusFlowSankeySummary {
  total: number;
  active: number;
  applied: number;
  progressing: number;
  rejected: number;
  offers: number;
}

export interface StatusFlowSankeyData {
  nodes: SankeyFlowNode[];
  links: SankeyFlowLink[];
  summary: StatusFlowSankeySummary;
}

export interface PipelineConfig {
  retention_days?: number;
  schedule_interval_hours?: number;
  is_paused?: boolean;
}

export type UserRole = "user" | "admin";
export type SyncMode = "backfill" | "incremental";
export type SyncStatus = "pending" | "running" | "complete" | "failed";

export interface UserSyncProfile {
  id: string;
  email: string;
  full_name: string | null;
  role: UserRole;
  sync_mode: SyncMode;
  sync_status: SyncStatus;
  last_synced_at: string | null;
}

export interface UsageMetricRow {
  user_id: string;
  recorded_for: string;
  emails_processed: number;
  gmail_api_calls: number;
  ai_requests: number;
  ai_input_tokens_est: number;
  ai_output_tokens_est: number;
  ai_estimated_cost_usd: number;
  telegram_notifications_sent: number;
  telegram_notifications_failed: number;
  success_count: number;
  failure_count: number;
  error_categories: Record<string, number>;
}

export interface UsageSummaryCard {
  totalEmailsAllTime: number;
  totalEmailsLast30Days: number;
  gmailApiCallsWindow: number;
  aiRequestsWindow: number;
  aiInputTokensWindow: number;
  aiOutputTokensWindow: number;
  aiEstimatedCostUsdWindow: number;
  telegramNotificationsSentWindow: number;
  telegramNotificationsFailedWindow: number;
  successRateWindow: number;
  latestSyncAt: string | null;
  syncStatusBreakdown: Record<string, number>;
  errorCategoriesWindow: Record<string, number>;
}

export interface UsageMetricPoint {
  recorded_for: string;
  emails_processed: number;
  gmail_api_calls: number;
  ai_requests: number;
  ai_estimated_cost_usd: number;
  telegram_notifications_sent: number;
  success_count: number;
  failure_count: number;
}

export interface UserBreakdownRow {
  user_id: string;
  email: string;
  full_name: string | null;
  sync_mode: SyncMode;
  sync_status: SyncStatus;
  last_synced_at: string | null;
  emails_processed_last_30_days: number;
  gmail_api_calls_last_30_days: number;
  ai_estimated_cost_usd_last_30_days: number;
  telegram_notifications_sent_last_30_days: number;
  success_rate_last_30_days: number;
}

export interface UsageAnalyticsResponse {
  viewerRole: UserRole;
  summary: UsageSummaryCard;
  timeSeries: UsageMetricPoint[];
  perUserBreakdown: UserBreakdownRow[];
}

export type PipelineRunStatus =
  | "running"
  | "pending"
  | "success"
  | "failed"
  | "cancelling"
  | "cancelled";

export type PipelineStepStatus =
  | "pending"
  | "running"
  | "success"
  | "failed"
  | "skipped";

export interface PipelineRun {
  id: string;
  run_id: string;
  status: PipelineRunStatus;
  triggered_by: string;
  started_at?: string;
  ended_at?: string;
  current_phase?: string;
  duration_ms?: number;
  error_message?: string;
  summary_stats?: Record<string, number | string | boolean>;
}

export interface PipelineStep {
  run_id: string;
  step_name: "ingestion" | "analysis" | "persistence";
  status: PipelineStepStatus;
  progress_pct?: number;
  message?: string;
}

export const STATUS_COLORS: Record<string, string> = {
  Pending: "#00a4e4",
  Rejected: "#e3120b",
  "Positive Response": "#0f2e53",
  Interview: "#f59e0b",
  Offer: "#8b5cf6",
};

export const STATUS_EMOJI: Record<string, string> = {
  Pending: "⏳",
  Rejected: "❌",
  "Positive Response": "🎉",
  Interview: "🤝",
  Offer: "🏆",
};
