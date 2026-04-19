"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { UsageAnalyticsResponse } from "@/lib/types";

import styles from "./UsageAnalyticsClient.module.css";

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});

function formatDate(value: string | null) {
  if (!value) {
    return "Not synced yet";
  }
  return new Date(value).toLocaleString();
}

function formatStatus(status: string) {
  return status.replaceAll("_", " ");
}

export default function UsageAnalyticsClient() {
  const [analytics, setAnalytics] = useState<UsageAnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadAnalytics() {
      try {
        const response = await fetch("/api/analytics?windowDays=30", {
          cache: "no-store",
        });
        const payload = (await response.json()) as UsageAnalyticsResponse | { error?: string };
        if (!response.ok || !("summary" in payload)) {
          throw new Error(("error" in payload && payload.error) || "Failed to load usage analytics.");
        }
        setAnalytics(payload);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load usage analytics.");
      } finally {
        setLoading(false);
      }
    }

    void loadAnalytics();
  }, []);

  const sortedErrors = useMemo(() => {
    if (!analytics) {
      return [];
    }
    return Object.entries(analytics.summary.errorCategoriesWindow).sort((left, right) => right[1] - left[1]);
  }, [analytics]);

  if (loading) {
    return <p className={styles.loading}>Loading operational analytics...</p>;
  }

  if (error || !analytics) {
    return <p className={styles.empty}>{error || "Usage analytics are unavailable."}</p>;
  }

  return (
    <section className={styles.section}>
      <div className={styles.summaryGrid}>
        <div className={styles.summaryCard}>
          <span className={styles.summaryLabel}>Emails processed</span>
          <span className={styles.summaryValue}>{analytics.summary.totalEmailsAllTime}</span>
          <span className={styles.summaryHint}>
            {analytics.summary.totalEmailsLast30Days} in the last 30 days
          </span>
        </div>
        <div className={styles.summaryCard}>
          <span className={styles.summaryLabel}>Gmail API calls</span>
          <span className={styles.summaryValue}>{analytics.summary.gmailApiCallsWindow}</span>
          <span className={styles.summaryHint}>Last 30-day sync activity</span>
        </div>
        <div className={styles.summaryCard}>
          <span className={styles.summaryLabel}>AI requests</span>
          <span className={styles.summaryValue}>{analytics.summary.aiRequestsWindow}</span>
          <span className={styles.summaryHint}>
            {analytics.summary.aiInputTokensWindow} input / {analytics.summary.aiOutputTokensWindow} output tokens
          </span>
        </div>
        <div className={styles.summaryCard}>
          <span className={styles.summaryLabel}>Estimated AI cost</span>
          <span className={styles.summaryValue}>
            {currencyFormatter.format(analytics.summary.aiEstimatedCostUsdWindow)}
          </span>
          <span className={styles.summaryHint}>Last 30 days</span>
        </div>
        <div className={styles.summaryCard}>
          <span className={styles.summaryLabel}>Telegram notifications</span>
          <span className={styles.summaryValue}>
            {analytics.summary.telegramNotificationsSentWindow}
          </span>
          <span className={styles.summaryHint}>
            {analytics.summary.telegramNotificationsFailedWindow} failed
          </span>
        </div>
        <div className={styles.summaryCard}>
          <span className={styles.summaryLabel}>Run success rate</span>
          <span className={styles.summaryValue}>{analytics.summary.successRateWindow}%</span>
          <span className={styles.summaryHint}>
            Last sync: {formatDate(analytics.summary.latestSyncAt)}
          </span>
        </div>
      </div>

      <div className={styles.subgrid}>
        <div className={styles.chartCard}>
          <h3 className={styles.panelTitle}>Operational usage over time</h3>
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={analytics.timeSeries}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
              <XAxis dataKey="recorded_for" tick={{ fontSize: 12 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="emails_processed"
                name="Emails"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={false}
              />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="gmail_api_calls"
                name="Gmail API calls"
                stroke="#22c55e"
                strokeWidth={2}
                dot={false}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="ai_requests"
                name="AI requests"
                stroke="#8b5cf6"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className={styles.panel}>
          <h3 className={styles.panelTitle}>Sync status</h3>
          <ul className={styles.statusList}>
            {Object.entries(analytics.summary.syncStatusBreakdown).map(([status, count]) => (
              <li key={status} className={styles.statusItem}>
                <span className={styles.statusLabel}>{formatStatus(status)}</span>
                <span className={styles.statusValue}>{count}</span>
              </li>
            ))}
          </ul>

          <h3 className={styles.panelTitle} style={{ marginTop: 24 }}>
            Error categories
          </h3>
          {sortedErrors.length === 0 ? (
            <p className={styles.empty}>No recent pipeline errors.</p>
          ) : (
            <ul className={styles.errorList}>
              {sortedErrors.map(([category, count]) => (
                <li key={category} className={styles.errorItem}>
                  <span className={styles.errorLabel}>{formatStatus(category)}</span>
                  <span className={styles.errorValue}>{count}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {analytics.viewerRole === "admin" && analytics.perUserBreakdown.length > 0 ? (
        <div className={styles.tableCard}>
          <h3 className={styles.panelTitle}>Per-user operational breakdown</h3>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Sync mode</th>
                  <th>Status</th>
                  <th>Emails (30d)</th>
                  <th>Gmail calls (30d)</th>
                  <th>AI cost (30d)</th>
                  <th>Telegram sent</th>
                  <th>Success rate</th>
                </tr>
              </thead>
              <tbody>
                {analytics.perUserBreakdown.map((row) => (
                  <tr key={row.user_id}>
                    <td>
                      <div>{row.full_name || row.email}</div>
                      <div className={styles.secondaryCell}>{row.email}</div>
                    </td>
                    <td>{formatStatus(row.sync_mode)}</td>
                    <td>{formatStatus(row.sync_status)}</td>
                    <td>{row.emails_processed_last_30_days}</td>
                    <td>{row.gmail_api_calls_last_30_days}</td>
                    <td>{currencyFormatter.format(row.ai_estimated_cost_usd_last_30_days)}</td>
                    <td>{row.telegram_notifications_sent_last_30_days}</td>
                    <td>{row.success_rate_last_30_days}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}
