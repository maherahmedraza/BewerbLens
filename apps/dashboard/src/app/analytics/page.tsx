import MonthlyChart from "@/components/charts/MonthlyChart";
import PlatformPie from "@/components/charts/PlatformPie";
import StatusFunnel from "@/components/charts/StatusFunnel";
import { createClient } from "@/lib/supabase/server";
import type { MonthlyApplication, PlatformBreakdown, ConversionFunnel, TopCompany, LocationBreakdown } from "@/lib/types";
import styles from "./page.module.css";

async function getMonthlyData(): Promise<MonthlyApplication[]> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("monthly_applications")
    .select("*")
    .order("month", { ascending: true });
  return (data as MonthlyApplication[]) || [];
}

async function getPlatformData(): Promise<PlatformBreakdown[]> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("platform_breakdown")
    .select("*")
    .order("count", { ascending: false });
  return (data as PlatformBreakdown[]) || [];
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
  return (data as LocationBreakdown[]) || [];
}

export default async function AnalyticsPage() {
  const [monthlyData, platformData, funnelData, companies, locations] =
    await Promise.all([
      getMonthlyData(),
      getPlatformData(),
      getFunnelData(),
      getTopCompanies(),
      getLocations(),
    ]);

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1 className="heading">Analytics</h1>
        <p className="subheading">Deep dive into your application performance, platform trends, and geographic breakdown.</p>
      </header>

      <div className={styles.grid}>
        <div className={styles.chartCard}>
          <h3 className="sectionTitle">Monthly Trends</h3>
          <MonthlyChart data={monthlyData} />
        </div>
        
        <div className={styles.chartCard}>
          <h3 className="sectionTitle">Platform Distribution</h3>
          <PlatformPie data={platformData.map((p) => ({ platform: p.platform, count: p.count }))} />
        </div>

        <div className={styles.chartCard}>
          <h3 className="sectionTitle">Conversion Funnel</h3>
          <StatusFunnel data={funnelData} />
        </div>

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
      </div>
    </div>
  );
}
