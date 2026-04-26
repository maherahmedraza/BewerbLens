"use client";

import { useEffect } from "react";

import styles from "./error.module.css";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className={styles.shell}>
      <div className={styles.card}>
        <p className={styles.eyebrow}>Application error</p>
        <h2 className={styles.title}>Something interrupted the dashboard.</h2>
        <p className={styles.description}>
          BewerbLens kept your data intact, but this screen could not finish rendering. Retry first,
          then refresh the page if the problem persists.
        </p>
        <div className={styles.actions}>
          <button type="button" className={`${styles.button} ${styles.buttonPrimary}`} onClick={reset}>
            Retry view
          </button>
          <button type="button" className={styles.button} onClick={() => window.location.reload()}>
            Refresh page
          </button>
        </div>
      </div>
    </div>
  );
}
