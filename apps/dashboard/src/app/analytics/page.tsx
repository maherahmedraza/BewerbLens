import {
  buildMonthlyApplications,
  buildPlatformBreakdown,
  buildStatusFlowSankey,
  getApplicationsForCurrentUser,
} from "@/lib/server/applications";
import { createClient } from "@/lib/supabase/server";
import type { ApplicationStats, ConversionFunnel, TopCompany, LocationBreakdown } from "@/lib/types";
import AnalyticsChartsClient from "./AnalyticsChartsClient";
import UsageAnalyticsClient from "./UsageAnalyticsClient";
import styles from "./page.module.css";

async function getStats(): Promise<ApplicationStats | null> {
  const supabase = await createClient();
  const { data } = await supabase.from("application_stats").select("*").single();
  return (data as ApplicationStats | null) ?? null;
}

async function getFunnelData(): Promise<ConversionFunnel[]> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("application_stats")
    .select("*")
    .single();

  if (!data) return [];

  // Cascading funnel drop-off logic
  return [
    { stage: "Applications Submitted", count: data.total_applications },
    { stage: "Awaiting Response", count: data.applied },
    { stage: "Positive Response", count: data.positive_response + data.interview + data.offer },
    { stage: "Interview", count: data.interview + data.offer },
    { stage: "Offer", count: data.offer },
  ];
}

async function getTopCompanies(): Promise<TopCompany[]> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("top_companies")
    .select("*")
    .limit(10);
  return (data as TopCompany[]) || [];
}

async function getLocations(): Promise<LocationBreakdown[]> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("location_breakdown")
    .select("*")
    .limit(10);
  return ((data as LocationBreakdown[]) || []).map((row) => ({
    ...row,
    location: row.location || "Location not specified",
  }));
}

export default async function AnalyticsPage() {
  const [applications, stats, funnelData, companies, locations] =
    await Promise.all([
      getApplicationsForCurrentUser(),
      getStats(),
      getFunnelData(),
      getTopCompanies(),
      getLocations(),
    ]);
  const monthlyData = buildMonthlyApplications(applications);
  const platformData = buildPlatformBreakdown(applications);
  const sankeyData = buildStatusFlowSankey(applications);
  const activePipeline =
    (stats?.applied || 0) + (stats?.positive_response || 0) + (stats?.interview || 0);
  const insightCards = [
    {
      label: "Tracked applications",
      value: stats?.total_applications || 0,
      note: "Full corpus visible in your private workspace",
    },
    {
      label: "Active pipeline",
      value: activePipeline,
      note: "Still moving through response and interview stages",
    },
    {
      label: "Response rate",
      value: `${stats?.response_rate_pct ?? 0}%`,
      note: "Share of applications with positive progression",
    },
    {
      label: "Pipeline success",
      value: `${stats?.success_rate_pct ?? 0}%`,
      note: "Successful persistence outcomes across tracked activity",
    },
  ];

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <span className={styles.eyebrow}>Insight studio</span>
        <h1 className="heading">Every meaningful trend, flow, and cost signal in one analytics hub.</h1>
        <p className="subheading">
          Explore application momentum, platform concentration, status transitions, operational workload,
          and geographic spread without splitting context across multiple pages.
        </p>
      </header>

      <section className={styles.summaryGrid}>
        {insightCards.map((card) => (
          <article key={card.label} className={styles.summaryCard}>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
            <p>{card.note}</p>
          </article>
        ))}
      </section>

      <AnalyticsChartsClient
        monthlyData={monthlyData}
        platformData={platformData}
        funnelData={funnelData}
        sankeyData={sankeyData}
      />

      <div className={styles.listCardWrapper}>
        <div className={styles.listCard}>
          <h3 className="sectionTitle">Top Companies</h3>
          {companies.length === 0 ? (
            <p className={styles.empty}>No data available yet.</p>
          ) : (
            <ul className={styles.list}>
              {companies.map((c) => (
                <li key={c.company_name} className={styles.listItem}>
                  <span className={styles.listName}>{c.company_name}</span>
                  <span className={styles.listCount}>{c.applications} applied</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className={styles.listCard}>
          <h3 className="sectionTitle">Location Insights</h3>
          {locations.length === 0 ? (
            <p className={styles.empty}>No geographic data available.</p>
          ) : (
            <ul className={styles.list}>
              {locations.map((l) => (
                <li key={l.location} className={styles.listItem}>
                  <span className={styles.listName}>{l.location}</span>
                  <span className={styles.listCount}>{l.count} applications ({l.pct}%)</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <section className={styles.usageSection}>
        <div className={styles.usageHeader}>
          <h2 className="sectionTitle">Operational Analytics</h2>
          <p className="subheading">
            Gmail usage, AI workload, notification delivery, and sync health for the last 30 days.
          </p>
        </div>
        <UsageAnalyticsClient />
      </section>
    </div>
  );
}
