import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import type { ApplicationStats, LocationBreakdown, TopCompany } from "@/lib/types";

import styles from "./page.module.css";

async function getStats(): Promise<ApplicationStats | null> {
  const supabase = await createClient();
  const { data } = await supabase.from("application_stats").select("*").single();
  return (data as ApplicationStats | null) ?? null;
}

async function getTopCompanies(): Promise<TopCompany[]> {
  const supabase = await createClient();
  const { data } = await supabase.from("top_companies").select("*").limit(5);
  return (data as TopCompany[]) || [];
}

async function getLocations(): Promise<LocationBreakdown[]> {
  const supabase = await createClient();
  const { data } = await supabase.from("location_breakdown").select("*").limit(4);
  return ((data as LocationBreakdown[]) || []).map((row) => ({
    ...row,
    location: row.location || "Not specified",
  }));
}

export default async function DashboardOverviewPage() {
  const [stats, topCompanies, locations] = await Promise.all([
    getStats(),
    getTopCompanies(),
    getLocations(),
  ]);

  const activePipeline =
    (stats?.applied || 0) + (stats?.positive_response || 0) + (stats?.interview || 0);
  const conversionRate = stats?.total_applications
    ? Math.round((((stats.offer || 0) + (stats.interview || 0)) / stats.total_applications) * 100)
    : 0;

  const spotlightCards = [
    {
      label: "Tracked applications",
      value: stats?.total_applications || 0,
      note: "Live count across your private workspace",
    },
    {
      label: "Active pipeline",
      value: activePipeline,
      note: "Applied, positive response, and interview stages",
    },
    {
      label: "Response rate",
      value: `${stats?.response_rate_pct ?? 0}%`,
      note: "Share of applications with positive movement",
    },
    {
      label: "Conversion signal",
      value: `${conversionRate}%`,
      note: "Interviews and offers relative to total applications",
    },
  ];

  const quickActions = [
    {
      title: "Queue a fresh sync",
      description: "Open workspace controls to backfill or trigger an incremental Gmail pull.",
      href: "/settings#sync-controls",
      cta: "Open settings",
    },
    {
      title: "Inspect application trends",
      description: "Use the analytics hub for Sankey flow, funnel drop-off, platform mix, and usage telemetry.",
      href: "/analytics",
      cta: "Open analytics",
    },
    {
      title: "Review the pipeline",
      description: "Check run history, step progress, and any retries or failures in the processing pipeline.",
      href: "/pipeline",
      cta: "Open pipeline",
    },
  ];

  const pipelineSignals = [
    { label: "Offers", value: stats?.offer || 0, note: "Terminal wins in the current dataset" },
    {
      label: "Positive responses",
      value: stats?.positive_response || 0,
      note: "Non-terminal encouraging replies",
    },
    { label: "Interviews", value: stats?.interview || 0, note: "Applications moving into live conversations" },
    { label: "Rejected", value: stats?.rejected || 0, note: "Terminal negative outcomes captured safely" },
  ];

  return (
    <div className={styles.dashboard}>
      <section className={styles.heroGrid}>
        <div className={styles.heroCard}>
          <div className={styles.heroHeader}>
            <div>
              <span className={styles.eyebrow}>Private overview</span>
              <h1 className={styles.title}>A clearer command center for your application pipeline.</h1>
              <p className={styles.subtitle}>
                Follow momentum, inspect stage transitions, and keep your personal job search data
                separated and secure by design.
              </p>
            </div>
            <div className={styles.heroPill}>Multi-user safe</div>
          </div>

          <div className={styles.spotlightGrid}>
            {spotlightCards.map((card) => (
              <article key={card.label} className={styles.spotlightCard}>
                <span className={styles.spotlightLabel}>{card.label}</span>
                <strong className={styles.spotlightValue}>{card.value}</strong>
                <p className={styles.spotlightNote}>{card.note}</p>
              </article>
            ))}
          </div>

          <div className={styles.actionGrid}>
            {quickActions.map((action) => (
              <article key={action.title} className={styles.actionCard}>
                <h2>{action.title}</h2>
                <p>{action.description}</p>
                <Link href={action.href} className={styles.actionLink}>
                  {action.cta}
                </Link>
              </article>
            ))}
          </div>
        </div>

        <aside className={styles.sideRail}>
          <section className={styles.focusCard}>
            <span className={styles.eyebrow}>This cycle</span>
            <strong className={styles.focusValue}>{stats?.offer || 0}</strong>
            <p className={styles.focusLabel}>Offers captured so far</p>
            <div className={styles.focusMeta}>
              <div>
                <span>Positive responses</span>
                <strong>{stats?.positive_response || 0}</strong>
              </div>
              <div>
                <span>Interviews</span>
                <strong>{stats?.interview || 0}</strong>
              </div>
            </div>
          </section>

          <section className={styles.listCard}>
            <div className={styles.sectionHeader}>
              <div>
                <h2>Top companies</h2>
                <p>Where most of your tracked application activity is happening.</p>
              </div>
            </div>
            {topCompanies.length === 0 ? (
              <p className={styles.empty}>No company insights yet.</p>
            ) : (
              <ul className={styles.list}>
                {topCompanies.map((company) => (
                  <li key={company.company_name} className={styles.listItem}>
                    <div>
                      <strong>{company.company_name}</strong>
                      <span>{company.applications} applications</span>
                    </div>
                    <em>{company.positive} positive</em>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className={styles.listCard}>
            <div className={styles.sectionHeader}>
              <div>
                <h2>Location mix</h2>
                <p>Leading locations from your current tracked opportunities.</p>
              </div>
            </div>
            {locations.length === 0 ? (
              <p className={styles.empty}>No location data available.</p>
            ) : (
              <ul className={styles.list}>
                {locations.map((location) => (
                  <li key={location.location} className={styles.listItem}>
                    <div>
                      <strong>{location.location}</strong>
                      <span>{location.count} roles</span>
                    </div>
                    <em>{location.pct}%</em>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </section>

      <section className={styles.analyticsGrid}>
        <article className={styles.chartCard}>
          <div className={styles.sectionHeader}>
            <div>
              <h2>Pipeline health snapshot</h2>
              <p>Stage counts that matter while you decide whether to sync again, follow up, or focus on interviews.</p>
            </div>
          </div>
          <div className={styles.signalGrid}>
            {pipelineSignals.map((signal) => (
              <div key={signal.label} className={styles.signalCard}>
                <span>{signal.label}</span>
                <strong>{signal.value}</strong>
                <p>{signal.note}</p>
              </div>
            ))}
          </div>
        </article>

        <article className={styles.calloutCard}>
          <span className={styles.eyebrow}>Operational confidence</span>
          <h2>{stats?.success_rate_pct ?? 0}% success rate</h2>
          <p>
            Successful persistence events vs failed persistence attempts in the current application set.
          </p>
          <div className={styles.calloutMetrics}>
            <div>
              <span>Rejected</span>
              <strong>{stats?.rejected || 0}</strong>
            </div>
            <div>
              <span>Awaiting response</span>
              <strong>{stats?.applied || 0}</strong>
            </div>
          </div>
          <Link href="/analytics" className={styles.calloutLink}>
            Explore full analytics
          </Link>
        </article>

        <article className={`${styles.chartCard} ${styles.wideCard}`}>
          <div className={styles.sectionHeader}>
            <div>
              <h2>Where to focus next</h2>
              <p>A compact operational read on the strongest company and location clusters in your active search.</p>
            </div>
          </div>
          <div className={styles.dualLists}>
            <section className={styles.listCard}>
              <h3>Top companies</h3>
              {topCompanies.length === 0 ? (
                <p className={styles.empty}>No company insights yet.</p>
              ) : (
                <ul className={styles.list}>
                  {topCompanies.map((company) => (
                    <li key={company.company_name} className={styles.listItem}>
                      <div>
                        <strong>{company.company_name}</strong>
                        <span>{company.applications} applications</span>
                      </div>
                      <em>{company.positive} positive</em>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className={styles.listCard}>
              <h3>Location mix</h3>
              {locations.length === 0 ? (
                <p className={styles.empty}>No location data available.</p>
              ) : (
                <ul className={styles.list}>
                  {locations.map((location) => (
                    <li key={location.location} className={styles.listItem}>
                      <div>
                        <strong>{location.location}</strong>
                        <span>{location.count} roles</span>
                      </div>
                      <em>{location.pct}%</em>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </article>
      </section>
    </div>
  );
}
