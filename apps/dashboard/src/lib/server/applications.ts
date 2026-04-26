import "server-only";

import type {
  Application,
  MonthlyApplication,
  PlatformBreakdown,
  StatusFlowSankeyData,
  StatusHistoryEntry,
} from "@/lib/types";
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

const POSITIVE_STATUSES = new Set(["Positive Response", "Interview", "Offer"]);
const TERMINAL_STATUSES = new Set(["Rejected", "Offer"]);
const SANKEY_STATUSES = new Set(["Applied", "Positive Response", "Interview", "Offer", "Rejected"]);
const SANKEY_START = "Applications Submitted";

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

function getSortableTimestamp(value: string | null | undefined, fallbackIndex: number) {
  if (!value) {
    return Number.MAX_SAFE_INTEGER - 10_000 + fallbackIndex;
  }

  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? Number.MAX_SAFE_INTEGER - 10_000 + fallbackIndex : parsed;
}

function buildStatusSequence(application: ApplicationRow) {
  const sequence: string[] = [SANKEY_START];
  const pushStatus = (status: string) => {
    if (!SANKEY_STATUSES.has(status)) {
      return;
    }

    if (sequence[sequence.length - 1] !== status) {
      sequence.push(status);
    }
  };

  pushStatus("Applied");

  const history = normalizeHistoryEntries(application.status_history)
    .map((entry, index) => ({
      status: normalizeStatus(entry.status || ""),
      timestamp: getSortableTimestamp(entry.changed_at || entry.timestamp || entry.date, index),
      index,
    }))
    .filter((entry) => SANKEY_STATUSES.has(entry.status))
    .sort((left, right) =>
      left.timestamp === right.timestamp ? left.index - right.index : left.timestamp - right.timestamp
    );

  for (const entry of history) {
    pushStatus(entry.status);
  }

  pushStatus(normalizeStatus(application.status));

  return sequence;
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

export function buildStatusFlowSankey(applications: ApplicationRow[]): StatusFlowSankeyData {
  const nodes: StatusFlowSankeyData["nodes"] = [];
  const links: StatusFlowSankeyData["links"] = [];
  const nodeIndexByKey = new Map<string, number>();
  const linkIndexByKey = new Map<string, number>();

  const summary = {
    total: applications.length,
    active: 0,
    applied: 0,
    progressing: 0,
    rejected: 0,
    offers: 0,
  };

  for (const application of applications) {
    const currentStatus = normalizeStatus(application.status);

    if (currentStatus === "Applied") {
      summary.applied += 1;
    }
    if (POSITIVE_STATUSES.has(currentStatus)) {
      summary.progressing += 1;
    }
    if (currentStatus === "Rejected") {
      summary.rejected += 1;
    }
    if (currentStatus === "Offer") {
      summary.offers += 1;
    }
    if (!TERMINAL_STATUSES.has(currentStatus)) {
      summary.active += 1;
    }

    const sequence = buildStatusSequence(application);

    let previousNodeIndex: number | null = null;
    for (const [depth, status] of sequence.entries()) {
      const nodeKey = `${depth}:${status}`;
      let nodeIndex = nodeIndexByKey.get(nodeKey);

      if (nodeIndex == null) {
        nodeIndex = nodes.length;
        nodes.push({
          name: status,
          status,
          depth,
          count: 0,
        });
        nodeIndexByKey.set(nodeKey, nodeIndex);
      }

      nodes[nodeIndex].count += 1;

      if (previousNodeIndex != null && previousNodeIndex !== nodeIndex) {
        const linkKey = `${previousNodeIndex}:${nodeIndex}`;
        const existingLinkIndex = linkIndexByKey.get(linkKey);

        if (existingLinkIndex == null) {
          links.push({
            source: previousNodeIndex,
            target: nodeIndex,
            value: 1,
          });
          linkIndexByKey.set(linkKey, links.length - 1);
        } else {
          links[existingLinkIndex].value += 1;
        }
      }

      previousNodeIndex = nodeIndex;
    }
  }

  return {
    nodes,
    links,
    summary,
  };
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
