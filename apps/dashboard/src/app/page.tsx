import Link from "next/link";
import Image from "next/image";

import {
  ArrowRightIcon,
  ChartBarSquareIcon,
  ShieldCheckIcon,
  SparklesIcon,
  BoltIcon,
  CommandLineIcon,
  EnvelopeIcon,
} from "@heroicons/react/24/outline";

import SignOutButton from "@/components/SignOutButton";
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

const integrationPills = ["Gmail OAuth", "Gemini AI", "Supabase Realtime", "Telegram Summary"];

const operatingLoop = [
  {
    step: "01",
    title: "Connect once",
    description: "Secure Google OAuth links each inbox to a private workspace with per-user visibility.",
    icon: EnvelopeIcon,
  },
  {
    step: "02",
    title: "Classify with context",
    description: "BewerbLens reads candidate mail, maps intent, and preserves stage artifacts for reliable reruns.",
    icon: SparklesIcon,
  },
  {
    step: "03",
    title: "Operate in real time",
    description: "Runs, statuses, and scheduler state refresh live so users never have to guess what is happening.",
    icon: BoltIcon,
  },
  {
    step: "04",
    title: "Act on outcomes",
    description: "Applications, analytics, and Telegram summaries close the loop from inbox to interview pipeline.",
    icon: CommandLineIcon,
  },
];

const premiumPillars = [
  {
    eyebrow: "One workspace",
    title: "Inbox, analytics, and controls stay together",
    description:
      "Competitors separate tracking, tailoring, and sync setup. BewerbLens keeps the operational loop in one calm surface.",
  },
  {
    eyebrow: "Private by design",
    title: "Built for real multi-user access",
    description:
      "Every view, run, and application record stays scoped to the signed-in user instead of pretending a single-user prototype is enough.",
  },
  {
    eyebrow: "Operational clarity",
    title: "The system tells you what changed",
    description:
      "Live runtime status, log detail, and end-of-run reports keep the product feeling reliable instead of opaque.",
  },
];

const footerColumns = [
  {
    title: "Platform",
    links: [
      { href: "/dashboard", label: "Dashboard" },
      { href: "/analytics", label: "Analytics" },
      { href: "/settings", label: "Settings" },
    ],
  },
  {
    title: "Integrations",
    links: [
      { href: "/settings#sync-controls", label: "Gmail sync" },
      { href: "/settings", label: "Telegram notifications" },
      { href: "/pipeline", label: "Pipeline logs" },
    ],
  },
  {
    title: "Trust",
    links: [
      { href: "/login", label: "Secure sign-in" },
      { href: "/settings", label: "Workspace controls" },
      { href: "/applications", label: "Application tracking" },
    ],
  },
];

export default async function LandingPage() {
  const user = await getViewer();
  const primaryHref = user ? "/dashboard" : "/login";
  const primaryLabel = user ? "Open dashboard" : "Login with Google";
  const secondaryHref = user ? "/settings" : "#features";
  const secondaryLabel = user ? "Open settings" : "Explore workflow";

  return (
    <div className={styles.page}>
      <div className={styles.topBar}>
        <div className={styles.topBarBrand}>
          <Image src="/bewerblens-logo.svg" alt="BewerbLens" width={40} height={40} className={styles.brandLogo} priority />
          <span className={styles.brandWordmark}>
            BewerbLens
            <small>Private application intelligence</small>
          </span>
        </div>
        <div className={styles.topBarActions}>
          <ThemeToggle className={styles.themeToggle} />
          {user ? (
            <SignOutButton className={styles.signOutButton}>Logout</SignOutButton>
          ) : null}
        </div>
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
            <Link href={secondaryHref} className={styles.secondaryAction}>
              {secondaryLabel}
            </Link>
          </div>

          <div className={styles.integrationRow}>
            {integrationPills.map((pill) => (
              <span key={pill} className={styles.integrationPill}>
                {pill}
              </span>
            ))}
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
              <span className={styles.brand}>
                <Image src="/bewerblens-logo.svg" alt="" width={24} height={24} aria-hidden="true" />
                BewerbLens
              </span>
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

      <section className={styles.features} id="features">
        {featureCards.map((feature) => (
          <article key={feature.title} className={styles.featureCard}>
            <feature.icon className={styles.featureIcon} />
            <h3>{feature.title}</h3>
            <p>{feature.description}</p>
          </article>
        ))}
      </section>

      <section className={styles.workflowSection}>
        <div className={styles.sectionIntro}>
          <div className={styles.badge}>Operating loop</div>
          <h2 className={styles.sectionTitle}>Everything that matters between Gmail and interview-ready insight.</h2>
          <p className={styles.sectionText}>
            Inspired by the strongest all-in-one job search products, but grounded in BewerbLens&apos; own advantage:
            reliable inbox automation, secure per-user access, and real operational feedback.
          </p>
        </div>

        <div className={styles.workflowGrid}>
          {operatingLoop.map((item) => (
            <article key={item.step} className={styles.workflowCard}>
              <div className={styles.workflowHeader}>
                <span className={styles.workflowStep}>{item.step}</span>
                <item.icon className={styles.workflowIcon} />
              </div>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.premiumSection}>
        <div className={styles.premiumPanel}>
          <div className={styles.badge}>Premium product feel</div>
          <h2 className={styles.sectionTitle}>A calmer product narrative than a spreadsheet, and more truthful telemetry than a static tracker.</h2>
          <p className={styles.sectionText}>
            BewerbLens feels premium when the interface is transparent: saved state is obvious, actions confirm instantly,
            and the system exposes the runtime facts users care about.
          </p>
        </div>
        <div className={styles.premiumGrid}>
          {premiumPillars.map((pillar) => (
            <article key={pillar.title} className={styles.premiumCard}>
              <span>{pillar.eyebrow}</span>
              <h3>{pillar.title}</h3>
              <p>{pillar.description}</p>
            </article>
          ))}
        </div>
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

      <footer className={styles.footer}>
        <div className={styles.footerBrand}>
          <span className={styles.badge}>Private multi-user pipeline</span>
          <h2 className={styles.footerTitle}>A calmer way to run application operations from Gmail to outcome.</h2>
          <p className={styles.footerText}>
            BewerbLens combines Gmail ingestion, AI classification, and protected per-user analytics in one workspace built for reliable follow-through.
          </p>
        </div>
        <div className={styles.footerGrid}>
          {footerColumns.map((column) => (
            <div key={column.title} className={styles.footerColumn}>
              <h3>{column.title}</h3>
              <div className={styles.footerLinks}>
                {column.links.map((link) => (
                  <Link key={link.label} href={link.href}>
                    {link.label}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </footer>
    </div>
  );
}
