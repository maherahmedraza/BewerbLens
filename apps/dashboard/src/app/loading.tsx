import styles from "./loading.module.css";

export default function Loading() {
  return (
    <div className={styles.shell} aria-live="polite">
      Loading BewerbLens…
    </div>
  );
}
