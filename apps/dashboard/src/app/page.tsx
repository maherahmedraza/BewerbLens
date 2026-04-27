import Link from "next/link";

import { ArrowRightIcon, ChartBarSquareIcon, ShieldCheckIcon, SparklesIcon } from "@heroicons/react/24/outline";

import { ThemeToggle } from "@/components/ThemeToggle";
import { createClient } from "@/lib/supabase/server";

import styles from "./page.module.css";

async function getViewer() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return user;
}

const featureCards = [
  {
    title: "Private application workspace",
    description: "Each user sees only their own pipeline, sync state, analytics, and linked integrations.",
    icon: ShieldCheckIcon,
  },
  {
    title: "AI-first pipeline",
    description: "Gmail ingestion, Gemini classification, and persistence stay coordinated through Supabase.",
    icon: SparklesIcon,
  },
  {
    title: "Live analytics",
    description: "Track conversion, response trends, and pipeline health in one premium dashboard.",
    icon: ChartBarSquareIcon,
  },
];

const trustStats = [
  { value: "Multi-user", label: "RLS-protected data access" },
  { value: "Realtime", label: "Live pipeline updates" },
  { value: "3-stage", label: "Ingestion → analysis → persistence" },
];

export default async function LandingPage() {
  const user = await getViewer();
  const primaryHref = user ? "/dashboard" : "/login";
  const primaryLabel = user ? "Open dashboard" : "Login with Google";

  return (
    <div className={styles.page}>
      <div className={styles.topBar}>
        <div className={styles.topBarBrand}>BewerbLens</div>
        <ThemeToggle className={styles.themeToggle} />
      </div>

      <section className={styles.hero}>
        <div className={styles.heroCopy}>
          <div className={styles.badge}>AI pipeline for modern job search</div>
          <h1 className={styles.title}>
            Track every application in a calm, premium workspace built for real multi-user teams.
          </h1>
          <p className={styles.subtitle}>
            BewerbLens turns your Gmail inbox into a structured application pipeline with secure per-user
            access, AI classification, and analytics that actually help you move faster.
          </p>

          <div className={styles.actions}>
            <Link href={primaryHref} className={styles.primaryAction}>
              {primaryLabel}
              <ArrowRightIcon className={styles.actionIcon} />
            </Link>
            <Link href="/login" className={styles.secondaryAction}>
              Sign in
            </Link>
          </div>

          <div className={styles.trustRow}>
            {trustStats.map((stat) => (
              <div key={stat.label} className={styles.trustCard}>
                <strong>{stat.value}</strong>
                <span>{stat.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className={styles.heroVisual}>
          <div className={styles.visualShell}>
            <div className={styles.visualTopbar}>
              <span className={styles.brand}>BewerbLens</span>
              <div className={styles.visualNav}>
                <span>Overview</span>
                <span>Applications</span>
                <span>Insights</span>
              </div>
              <span className={styles.statusPill}>Private</span>
            </div>

            <div className={styles.visualGrid}>
              <article className={styles.visualCardLarge}>
                <div className={styles.kicker}>Pipeline overview</div>
                <h2>Application momentum</h2>
                <p>See submissions, responses, interviews, and offers in one view.</p>
                <div className={styles.fakeChart}>
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                </div>
              </article>

              <article className={styles.visualCard}>
                <div className={styles.kicker}>Response rate</div>
                <strong>38%</strong>
                <p>Positive replies climbing this month.</p>
              </article>

              <article className={styles.visualCard}>
                <div className={styles.kicker}>Team-safe data</div>
                <strong>Per-user access</strong>
                <p>Views and records stay scoped to each signed-in member.</p>
              </article>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.features}>
        {featureCards.map((feature) => (
          <article key={feature.title} className={styles.featureCard}>
            <feature.icon className={styles.featureIcon} />
            <h3>{feature.title}</h3>
            <p>{feature.description}</p>
          </article>
        ))}
      </section>

      <section className={styles.ctaSection}>
        <div>
          <div className={styles.badge}>Designed for focused execution</div>
          <h2 className={styles.ctaTitle}>From first sync to final offer, keep every stage visible.</h2>
          <p className={styles.ctaText}>
            Use the public landing page for onboarding, then move into a protected dashboard built for
            individual ownership, AI-assisted review, and fast operational insight.
          </p>
        </div>
        <Link href={primaryHref} className={styles.primaryAction}>
          {primaryLabel}
          <ArrowRightIcon className={styles.actionIcon} />
        </Link>
      </section>
    </div>
  );
}
