"use client";

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
        emailRedirectTo: `${window.location.origin}/auth/callback`,
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
    <div className={styles.container}>
      <h1 className={styles.heading}>Sign In</h1>
      <p className={styles.description}>
        Enter your email to receive a magic link. No password required.
      </p>

      {sent ? (
        <div className={styles.success}>
          Magic link sent! Check your email at <strong>{email}</strong>.
        </div>
      ) : (
        <form onSubmit={handleSubmit} className={styles.form}>
          <input
            type="email"
            className={styles.input}
            placeholder="your@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <button className={styles.button} type="submit" disabled={loading}>
            {loading ? "Sending..." : "Send Magic Link"}
          </button>
          {error && <div className={styles.error}>{error}</div>}
        </form>
      )}
    </div>
  );
}
