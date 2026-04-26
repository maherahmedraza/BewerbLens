"use client";

import Link from "next/link";

import { ThemeToggle } from "@/components/ThemeToggle";
import { createClient } from "@/lib/supabase/client";
import { useState } from "react";
import styles from "./page.module.css";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback?next=/dashboard`,
      },
    });

    if (error) {
      setError(error.message);
    } else {
      setSent(true);
    }
    setLoading(false);
  }

  return (
    <div className={styles.page}>
      <div className={styles.topBar}>
        <Link href="/" className={styles.topBarBrand}>
          BewerbLens
        </Link>
        <ThemeToggle className={styles.themeToggle} />
      </div>

      <div className={styles.panel}>
        <section className={styles.marketing}>
          <Link href="/" className={styles.backLink}>
            BewerbLens
          </Link>
          <div className={styles.badge}>Secure sign in</div>
          <h1 className={styles.heading}>Enter your workspace with a magic link.</h1>
          <p className={styles.description}>
            No password, no shared inboxes, no mixed user data. Sign in to your private dashboard and
            continue where your pipeline left off.
          </p>
          <div className={styles.featureList}>
            <div>
              <strong>Private by default</strong>
              <span>Dashboard data stays scoped to the authenticated user.</span>
            </div>
            <div>
              <strong>Fast onboarding</strong>
              <span>Connect Gmail, link Telegram, and trigger your first run from one place.</span>
            </div>
          </div>
        </section>

        <section className={styles.formPanel}>
          <div className={styles.formHeader}>
            <div className={styles.badge}>Magic link login</div>
            <h2 className={styles.formTitle}>Sign in</h2>
            <p className={styles.formText}>Use the email address tied to your BewerbLens account.</p>
          </div>

          {sent ? (
            <div className={styles.success}>
              Magic link sent. Check <strong>{email}</strong> and continue to your dashboard.
            </div>
          ) : (
            <form onSubmit={handleSubmit} className={styles.form}>
              <label className={styles.label} htmlFor="email">
                Email address
              </label>
              <input
                id="email"
                type="email"
                className={styles.input}
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <button className={styles.button} type="submit" disabled={loading}>
                {loading ? "Sending link..." : "Send magic link"}
              </button>
              {error && <div className={styles.error}>{error}</div>}
            </form>
          )}
        </section>
      </div>
    </div>
  );
}
