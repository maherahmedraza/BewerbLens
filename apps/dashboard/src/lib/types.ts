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
