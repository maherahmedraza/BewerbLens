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
  salary_range: string;
  source_email_id: string;
  status_history: StatusHistoryEntry[];
  email_count: number;
  is_active: boolean;
}

export interface StatusHistoryEntry {
  status: string;
  timestamp: string;
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
  summary_stats?: Record<string, number>;
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
