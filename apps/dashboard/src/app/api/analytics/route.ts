import { subDays } from "date-fns";
import { NextResponse } from "next/server";

import type {
  UsageAnalyticsResponse,
  UsageMetricPoint,
  UsageMetricRow,
  UsageSummaryCard,
  UserBreakdownRow,
  UserSyncProfile,
} from "@/lib/types";
import { createClient } from "@/lib/supabase/server";

function asNumber(value: number | string | null | undefined) {
  if (typeof value === "number") {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

function calculateSuccessRate(success: number, failure: number) {
  const total = success + failure;
  return total === 0 ? 0 : (success / total) * 100;
}

function buildDateRange(windowDays: number) {
  return Array.from({ length: windowDays }, (_, index) =>
    subDays(new Date(), windowDays - index - 1).toISOString().slice(0, 10)
  );
}

function mergeErrorCategories(rows: UsageMetricRow[]) {
  return rows.reduce<Record<string, number>>((accumulator, row) => {
    const categories = row.error_categories || {};
    for (const [key, value] of Object.entries(categories)) {
      accumulator[key] = (accumulator[key] || 0) + asNumber(value);
    }
    return accumulator;
  }, {});
}

function aggregateWindow(rows: UsageMetricRow[]) {
  return rows.reduce(
    (totals, row) => ({
      emailsProcessed: totals.emailsProcessed + asNumber(row.emails_processed),
      gmailApiCalls: totals.gmailApiCalls + asNumber(row.gmail_api_calls),
      aiRequests: totals.aiRequests + asNumber(row.ai_requests),
      aiInputTokensEst: totals.aiInputTokensEst + asNumber(row.ai_input_tokens_est),
      aiOutputTokensEst: totals.aiOutputTokensEst + asNumber(row.ai_output_tokens_est),
      aiEstimatedCostUsd: totals.aiEstimatedCostUsd + asNumber(row.ai_estimated_cost_usd),
      telegramNotificationsSent:
        totals.telegramNotificationsSent + asNumber(row.telegram_notifications_sent),
      telegramNotificationsFailed:
        totals.telegramNotificationsFailed + asNumber(row.telegram_notifications_failed),
      successCount: totals.successCount + asNumber(row.success_count),
      failureCount: totals.failureCount + asNumber(row.failure_count),
    }),
    {
      emailsProcessed: 0,
      gmailApiCalls: 0,
      aiRequests: 0,
      aiInputTokensEst: 0,
      aiOutputTokensEst: 0,
      aiEstimatedCostUsd: 0,
      telegramNotificationsSent: 0,
      telegramNotificationsFailed: 0,
      successCount: 0,
      failureCount: 0,
    }
  );
}

function buildSummary(
  rows: UsageMetricRow[],
  profiles: UserSyncProfile[],
  windowDays: number
): UsageSummaryCard {
  const windowStart = subDays(new Date(), windowDays - 1).toISOString().slice(0, 10);
  const last30Start = subDays(new Date(), 29).toISOString().slice(0, 10);
  const recentRows = rows.filter((row) => row.recorded_for >= windowStart);
  const last30Rows = rows.filter((row) => row.recorded_for >= last30Start);
  const allTimeTotals = aggregateWindow(rows);
  const recentTotals = aggregateWindow(recentRows);
  const last30Totals = aggregateWindow(last30Rows);
  const latestProfile = [...profiles]
    .filter((profile) => Boolean(profile.last_synced_at))
    .sort((left, right) => (left.last_synced_at && right.last_synced_at ? right.last_synced_at.localeCompare(left.last_synced_at) : 0))[0];

  return {
    totalEmailsAllTime: allTimeTotals.emailsProcessed,
    totalEmailsLast30Days: last30Totals.emailsProcessed,
    gmailApiCallsWindow: recentTotals.gmailApiCalls,
    aiRequestsWindow: recentTotals.aiRequests,
    aiInputTokensWindow: recentTotals.aiInputTokensEst,
    aiOutputTokensWindow: recentTotals.aiOutputTokensEst,
    aiEstimatedCostUsdWindow: Number(recentTotals.aiEstimatedCostUsd.toFixed(4)),
    telegramNotificationsSentWindow: recentTotals.telegramNotificationsSent,
    telegramNotificationsFailedWindow: recentTotals.telegramNotificationsFailed,
    successRateWindow: Number(
      calculateSuccessRate(recentTotals.successCount, recentTotals.failureCount).toFixed(1)
    ),
    latestSyncAt: latestProfile?.last_synced_at || null,
    syncStatusBreakdown: profiles.reduce<Record<string, number>>((accumulator, profile) => {
      const key = profile.sync_status || "pending";
      accumulator[key] = (accumulator[key] || 0) + 1;
      return accumulator;
    }, {}),
    errorCategoriesWindow: mergeErrorCategories(recentRows),
  };
}

function buildTimeSeries(rows: UsageMetricRow[], windowDays: number): UsageMetricPoint[] {
  const buckets = new Map<string, UsageMetricPoint>();

  for (const day of buildDateRange(windowDays)) {
    buckets.set(day, {
      recorded_for: day,
      emails_processed: 0,
      gmail_api_calls: 0,
      ai_requests: 0,
      ai_estimated_cost_usd: 0,
      telegram_notifications_sent: 0,
      success_count: 0,
      failure_count: 0,
    });
  }

  for (const row of rows) {
    const bucket = buckets.get(row.recorded_for);
    if (!bucket) {
      continue;
    }
    bucket.emails_processed += asNumber(row.emails_processed);
    bucket.gmail_api_calls += asNumber(row.gmail_api_calls);
    bucket.ai_requests += asNumber(row.ai_requests);
    bucket.ai_estimated_cost_usd = Number(
      (bucket.ai_estimated_cost_usd + asNumber(row.ai_estimated_cost_usd)).toFixed(4)
    );
    bucket.telegram_notifications_sent += asNumber(row.telegram_notifications_sent);
    bucket.success_count += asNumber(row.success_count);
    bucket.failure_count += asNumber(row.failure_count);
  }

  return Array.from(buckets.values());
}

function buildPerUserBreakdown(
  rows: UsageMetricRow[],
  profiles: UserSyncProfile[],
  isAdmin: boolean
): UserBreakdownRow[] {
  if (!isAdmin) {
    return [];
  }

  const last30Start = subDays(new Date(), 29).toISOString().slice(0, 10);
  const rowsByUser = new Map<string, UsageMetricRow[]>();

  for (const row of rows) {
    const group = rowsByUser.get(row.user_id) || [];
    group.push(row);
    rowsByUser.set(row.user_id, group);
  }

  return profiles
    .map((profile) => {
      const userRows = rowsByUser.get(profile.id) || [];
      const last30Rows = userRows.filter((row) => row.recorded_for >= last30Start);
      const totals = aggregateWindow(last30Rows);
      return {
        user_id: profile.id,
        email: profile.email,
        full_name: profile.full_name,
        sync_mode: profile.sync_mode,
        sync_status: profile.sync_status,
        last_synced_at: profile.last_synced_at,
        emails_processed_last_30_days: totals.emailsProcessed,
        gmail_api_calls_last_30_days: totals.gmailApiCalls,
        ai_estimated_cost_usd_last_30_days: Number(totals.aiEstimatedCostUsd.toFixed(4)),
        telegram_notifications_sent_last_30_days: totals.telegramNotificationsSent,
        success_rate_last_30_days: Number(
          calculateSuccessRate(totals.successCount, totals.failureCount).toFixed(1)
        ),
      };
    })
    .sort(
      (left, right) =>
        right.emails_processed_last_30_days - left.emails_processed_last_30_days ||
        right.gmail_api_calls_last_30_days - left.gmail_api_calls_last_30_days
    );
}

export async function GET(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const windowDaysParam = Number(new URL(request.url).searchParams.get("windowDays") || "30");
  const windowDays = Number.isFinite(windowDaysParam)
    ? Math.min(Math.max(windowDaysParam, 7), 90)
    : 30;

  const { data: viewerProfile, error: viewerError } = await supabase
    .from("user_profiles")
    .select("id, email, full_name, role, sync_mode, sync_status, last_synced_at")
    .eq("id", user.id)
    .single();

  if (viewerError || !viewerProfile) {
    return NextResponse.json({ error: viewerError?.message || "Profile not found." }, { status: 404 });
  }

  const isAdmin = viewerProfile.role === "admin";
  const profileQuery = supabase
    .from("user_profiles")
    .select("id, email, full_name, role, sync_mode, sync_status, last_synced_at")
    .order("email", { ascending: true });
  const usageQuery = supabase
    .from("usage_metrics")
    .select(
      "user_id, recorded_for, emails_processed, gmail_api_calls, ai_requests, ai_input_tokens_est, ai_output_tokens_est, ai_estimated_cost_usd, telegram_notifications_sent, telegram_notifications_failed, success_count, failure_count, error_categories"
    )
    .order("recorded_for", { ascending: true });

  const [{ data: profiles, error: profilesError }, { data: usageRows, error: usageError }] =
    await Promise.all([
      isAdmin ? profileQuery : profileQuery.eq("id", user.id),
      isAdmin ? usageQuery : usageQuery.eq("user_id", user.id),
    ]);

  if (profilesError || usageError) {
    return NextResponse.json(
      { error: profilesError?.message || usageError?.message || "Failed to load analytics." },
      { status: 500 }
    );
  }

  const safeProfiles = (profiles || []) as UserSyncProfile[];
  const safeRows = (usageRows || []) as UsageMetricRow[];
  const response: UsageAnalyticsResponse = {
    viewerRole: viewerProfile.role,
    summary: buildSummary(safeRows, safeProfiles, windowDays),
    timeSeries: buildTimeSeries(
      safeRows.filter((row) => row.recorded_for >= subDays(new Date(), windowDays - 1).toISOString().slice(0, 10)),
      windowDays
    ),
    perUserBreakdown: buildPerUserBreakdown(safeRows, safeProfiles, isAdmin),
  };

  return NextResponse.json(response);
}
