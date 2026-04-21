import "server-only";

import type { Application, MonthlyApplication, PlatformBreakdown, StatusHistoryEntry } from "@/lib/types";
import { normalizeStatus } from "@/lib/status";
import { createClient } from "@/lib/supabase/server";

const APPLICATION_EXPORT_COLUMNS = [
  "Company",
  "Job Title",
  "Platform",
  "Current Status",
  "Date Applied",
  "Last Updated",
  "Primary Location",
  "Work Mode",
  "Salary Range",
  "Email Subject",
  "Email From",
  "Gmail Link",
  "Job Listing URL",
  "Source Email ID",
  "Email Count",
  "Notes",
  "Status History",
] as const;

type ApplicationRow = Pick<
  Application,
  | "id"
  | "company_name"
  | "job_title"
  | "platform"
  | "status"
  | "date_applied"
  | "last_updated"
  | "location"
  | "job_location"
  | "job_city"
  | "job_country"
  | "work_mode"
  | "salary_range"
  | "email_subject"
  | "email_from"
  | "gmail_link"
  | "job_listing_url"
  | "source_email_id"
  | "email_count"
  | "notes"
> & {
  status_history: StatusHistoryEntry[] | string | null;
};

const APPLICATION_SELECT =
  "id, company_name, job_title, platform, status, date_applied, last_updated, location, job_location, job_city, job_country, work_mode, salary_range, email_subject, email_from, gmail_link, job_listing_url, source_email_id, email_count, notes, status_history";

function normalizeMonth(value: string | null | undefined) {
  if (!value) {
    return null;
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  return new Date(Date.UTC(parsed.getUTCFullYear(), parsed.getUTCMonth(), 1))
    .toISOString()
    .slice(0, 10);
}

function normalizePlatform(value: string | null | undefined) {
  const cleaned = value?.trim();
  return cleaned ? cleaned : "Direct";
}

function normalizeHistoryEntries(
  value: ApplicationRow["status_history"]
): StatusHistoryEntry[] {
  if (Array.isArray(value)) {
    return value;
  }

  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? (parsed as StatusHistoryEntry[]) : [];
    } catch {
      return [];
    }
  }

  return [];
}

function toCsvCell(value: string | number | null | undefined) {
  const normalized = value == null ? "" : String(value);
  return `"${normalized.replace(/"/g, '""')}"`;
}

function serializeStatusHistory(history: StatusHistoryEntry[]) {
  return history
    .map((entry) => {
      const timestamp = entry.changed_at || entry.timestamp || entry.date || "";
      const status = normalizeStatus(entry.status || "");
      const subject = entry.email_subject || "";
      return [timestamp, status, subject].filter(Boolean).join(" - ");
    })
    .join(" | ");
}

export async function getApplicationsForCurrentUser() {
  const supabase = await createClient();
  const pageSize = 1000;
  const applications: ApplicationRow[] = [];
  let from = 0;

  while (true) {
    const { data, error } = await supabase
      .from("applications")
      .select(APPLICATION_SELECT)
      .eq("is_active", true)
      .order("date_applied", { ascending: false })
      .range(from, from + pageSize - 1);

    if (error) {
      throw new Error(error.message);
    }

    const page = (data || []) as ApplicationRow[];
    applications.push(...page);

    if (page.length < pageSize) {
      break;
    }

    from += pageSize;
  }

  return applications;
}

export function buildMonthlyApplications(applications: ApplicationRow[]): MonthlyApplication[] {
  const buckets = new Map<string, MonthlyApplication>();
  const rejectedSeen = new Set<string>();
  const positiveSeen = new Set<string>();

  for (const application of applications) {
    const appliedMonth = normalizeMonth(application.date_applied);
    if (appliedMonth) {
      const bucket = buckets.get(appliedMonth) || {
        month: appliedMonth,
        total: 0,
        applied: 0,
        rejected: 0,
        positive: 0,
      };
      bucket.total += 1;
      bucket.applied += 1;
      buckets.set(appliedMonth, bucket);
    }

    const history = normalizeHistoryEntries(application.status_history);
    for (const entry of history) {
      const month = normalizeMonth(entry.changed_at || entry.timestamp || entry.date);
      if (!month) {
        continue;
      }

      const status = normalizeStatus(entry.status || "");
      const bucket = buckets.get(month) || {
        month,
        total: 0,
        applied: 0,
        rejected: 0,
        positive: 0,
      };

      if (status === "Rejected") {
        const rejectedKey = `${application.id}:${month}:rejected`;
        if (!rejectedSeen.has(rejectedKey)) {
          bucket.rejected += 1;
          rejectedSeen.add(rejectedKey);
        }
      }

      if (["Positive Response", "Interview", "Offer"].includes(status)) {
        const positiveKey = `${application.id}:${month}:positive`;
        if (!positiveSeen.has(positiveKey)) {
          bucket.positive += 1;
          positiveSeen.add(positiveKey);
        }
      }

      buckets.set(month, bucket);
    }
  }

  return Array.from(buckets.values()).sort((left, right) => left.month.localeCompare(right.month));
}

export function buildPlatformBreakdown(applications: ApplicationRow[]): PlatformBreakdown[] {
  const buckets = new Map<string, PlatformBreakdown>();

  for (const application of applications) {
    const platform = normalizePlatform(application.platform);
    const status = normalizeStatus(application.status);
    const bucket = buckets.get(platform) || {
      platform,
      count: 0,
      rejected: 0,
      positive: 0,
    };

    bucket.count += 1;
    if (status === "Rejected") {
      bucket.rejected += 1;
    }
    if (["Positive Response", "Interview", "Offer"].includes(status)) {
      bucket.positive += 1;
    }

    buckets.set(platform, bucket);
  }

  return Array.from(buckets.values()).sort((left, right) => right.count - left.count);
}

export function buildApplicationsCsv(applications: ApplicationRow[]) {
  const lines = [
    APPLICATION_EXPORT_COLUMNS.map((column) => toCsvCell(column)).join(","),
    ...applications.map((application) => {
      const history = normalizeHistoryEntries(application.status_history);
      const primaryLocation =
        application.job_city ||
        application.job_country ||
        application.job_location ||
        application.location ||
        "";

      return [
        application.company_name,
        application.job_title,
        normalizePlatform(application.platform),
        normalizeStatus(application.status),
        application.date_applied,
        application.last_updated,
        primaryLocation,
        application.work_mode,
        application.salary_range,
        application.email_subject,
        application.email_from,
        application.gmail_link,
        application.job_listing_url,
        application.source_email_id,
        application.email_count,
        application.notes,
        serializeStatusHistory(history),
      ]
        .map((value) => toCsvCell(value))
        .join(",");
    }),
  ];

  return `\uFEFF${lines.join("\n")}`;
}
