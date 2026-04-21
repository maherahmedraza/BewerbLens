import StatsCards from "@/components/StatsCards";
import MonthlyChart from "@/components/charts/MonthlyChart";
import StatusFunnel from "@/components/charts/StatusFunnel";
import { createClient } from "@/lib/supabase/server";
import { buildMonthlyApplications, getApplicationsForCurrentUser } from "@/lib/server/applications";
import type { MonthlyApplication, ConversionFunnel } from "@/lib/types";
import styles from "./page.module.css";

async function getMonthlyData(): Promise<MonthlyApplication[]> {
  const applications = await getApplicationsForCurrentUser();
  return buildMonthlyApplications(applications);
}

async function getFunnelData(): Promise<ConversionFunnel[]> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("application_stats")
    .select("*")
    .single();

  if (!data) return [];

  return [
    { stage: "Applications Submitted", count: data.total_applications },
    { stage: "Awaiting Response", count: data.applied },
    { stage: "Positive Response", count: data.positive_response + data.interview + data.offer },
    { stage: "Interview", count: data.interview + data.offer },
    { stage: "Offer", count: data.offer },
  ];
}

export default async function DashboardPage() {
  const [monthlyData, funnelData] = await Promise.all([
    getMonthlyData(),
    getFunnelData(),
  ]);

  return (
    <div className={styles.dashboard}>
      <header className={styles.header}>
        <h1 className="heading">Overview</h1>
        <p className="subheading">
          Real-time analytics and tracking for your job application pipeline.
        </p>
      </header>
      
      <StatsCards />
      
      <div className={styles.chartsGrid}>
        <div className={styles.chartCard}>
          <h3 className="sectionTitle">Monthly Applications</h3>
          <MonthlyChart data={monthlyData} />
        </div>
        <div className={styles.chartCard}>
          <h3 className="sectionTitle">Conversion Funnel</h3>
          <StatusFunnel data={funnelData} />
        </div>
      </div>
    </div>
  );
}
